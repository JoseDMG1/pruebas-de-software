"""Real-browser capacity stages, distinct accounts, semantic checks and telemetry.

Each invocation creates a new evidence file (refuses overwrite). Login is excluded.
The generator shares the host with the system; telemetry records this limitation.
"""
import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import subprocess
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from load_chat import summarize
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = 'http://127.0.0.1:8088'
CHAT = BASE + '/local/acadassistant/index.php'
QUESTIONS = [
    ('rule', '¿Cuál es la nota mínima aprobatoria?'),
    ('courses', '¿Qué cursos tengo?'),
    ('teachers', '¿Qué profesores me enseñan?'),
    ('support', '¿Cómo solicito orientación psicológica?'),
    ('calendar', 'Llévame a mi calendario de Moodle'),
]
EXTENDED = [
    ('tasks', '¿Qué tareas tengo pendientes en Biologia 102?'),
    ('weekly', 'Organiza mis pendientes de Biologia 102 de esta semana; puedo estudiar lunes y miércoles dos horas.'),
    ('mixed', '¿Qué cursos tengo y cuál es la nota mínima aprobatoria?'),
]
CONTAINERS = ['rag-service-api-1', 'rag-service-db-1',
              'pruebasdesoftware-moodle-1', 'pruebasdesoftware-moodle-db-1']


def utc():
    return datetime.now(timezone.utc).isoformat()


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn')


def semantic_check(kind, answer, turn, links, profile):
    a, t = norm(answer), norm(turn)
    if kind == 'tasks':
        return 'informe de laboratorio' in a and 'pendient' in a and 'biologia' in a
    if kind == 'weekly':
        return 'plan' in a and 'informe de laboratorio' in a and ('borrador provisional' in a or 'dias y horas' in a)
    if kind == 'mixed':
        return semantic_check('courses', answer, turn, links, profile) and semantic_check('rule', answer, turn, links, profile)
    if kind == 'rule':
        return bool(re.search(r'\b11\b', a)) and 'reglamento' in t and ('[1]' in t or 'document' in t)
    if kind == 'courses':
        return bool(profile['expected_courses']) and all(norm(c) in a for c in profile['expected_courses']) and all(norm(c) not in a for c in profile.get('forbidden_courses', ['Metodología de Investigación 103']))
    if kind == 'teachers':
        return 'docent' in a and any(n in a for n in ['carla rojas', 'diego salinas', 'valeria nunez', 'jorge rivas'])
    if kind == 'support':
        return 'bienestar@udv.edu.pe' in a and 'cita' in a and ('[1]' in t or 'document' in t)
    if kind == 'calendar':
        return any(u.startswith(BASE + '/calendar/') for u in links)
    return False


def summary(samples, elapsed):
    s = summarize(samples, elapsed)
    values = sorted(x['seconds'] for x in samples)
    s['p99_seconds'] = values[math.ceil(.99 * len(values)) - 1] if values else None
    s['semantic_errors'] = sum(x.get('error') == 'semantic_mismatch' for x in samples)
    s['transport_or_application_errors'] = s['errors'] - s['semantic_errors']
    return s


def host_sample():
    mem = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
    cpu = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:]))
    return {'timestamp_utc': utc(), 'load_average': os.getloadavg(),
            'mem_total_kib': mem['MemTotal'], 'mem_available_kib': mem['MemAvailable'],
            'swap_used_kib': mem['SwapTotal'] - mem['SwapFree'],
            'cpu_total_ticks': sum(cpu[:8]), 'cpu_idle_ticks': cpu[3] + cpu[4]}


def telemetry():
    sample = host_sample()
    # Process command names only: never record arguments or environment secrets.
    rss = subprocess.run(['ps', '-eo', 'comm=,rss='], capture_output=True, text=True, timeout=3, check=False)
    sample['browser_rss_kib'] = sum(int(line.split()[-1]) for line in rss.stdout.splitlines()
        if any(name in line.split()[0].lower() for name in ['chrome', 'chromium', 'headless']))
    try:
        p = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}', *CONTAINERS],
                           capture_output=True, text=True, timeout=12, check=False)
        sample['containers'] = [json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]
        sample['container_stats_ok'] = p.returncode == 0
    except Exception as exc:  # noqa: BLE001 - Record failure type without exposing exception contents.
        sample['container_stats_error'] = type(exc).__name__
    for name, url in [('rag', 'http://127.0.0.1:8000/health'), ('moodle', BASE + '/login/index.php')]:
        start = time.monotonic()
        try:
            with urlopen(url, timeout=4) as response:
                sample[name + '_healthy'] = response.status == 200
        except Exception:  # noqa: BLE001 - Failed probes must remain in the measured denominator.
            sample[name + '_healthy'] = False
        sample[name + '_probe_seconds'] = round(time.monotonic() - start, 3)
    return sample


async def run(args):
    out = Path(args.output)
    if out.exists():
        raise ValueError('Refusing to overwrite evidence')
    out.parent.mkdir(parents=True, exist_ok=True)
    questions = QUESTIONS + EXTENDED if args.mix == 'extended' else QUESTIONS
    profiles = json.loads(Path(args.profiles).read_text())['profiles'][:args.users]
    if len(profiles) != args.users or len({p['username'] for p in profiles}) != args.users:
        raise ValueError('Insufficient distinct identities')
    env = dict(line.split('=', 1) for line in (ROOT / '.moodle.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
    report = {'complete': False, 'stage': args.stage, 'timestamp_utc': utc(),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'configuration': vars(args), 'profiles': profiles, 'questions': questions,
              'measurement': 'Submit click to rendered response, measured before semantic extraction. Login/warmup excluded; resets and declared pauses included in throughput. No harness retries. Same host generates load and runs services.',
              'samples': [], 'warmup': [], 'telemetry': []}
    stop = asyncio.Event()

    def save():
        tmp = out.with_suffix('.tmp')
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        tmp.replace(out)

    async def monitor():
        while not stop.is_set():
            report['telemetry'].append(await asyncio.to_thread(telemetry))
            save()
            try:
                await asyncio.wait_for(stop.wait(), timeout=5)
            except TimeoutError:
                pass

    async def ask(page, profile, kind, question, turn):
        started = time.monotonic()
        result = {'username': profile['username'], 'round': turn, 'kind': kind,
                  'timestamp_utc': utc(), 'question': question, 'ok': False, 'error': None, 'answer': ''}
        try:
            count = await page.locator('.local-acadassistant-turn').count()
            await page.locator('#assistant-question').fill(question)
            started = time.monotonic()
            await page.get_by_role('button', name='Send question', exact=True).click(timeout=30000)
            await page.wait_for_function("document.querySelector('#assistant-form').dataset.submitting === 'false'", timeout=150000)
            result['seconds'] = round(time.monotonic() - started, 4)
            if await page.locator('.alert-danger,#assistant-error').count():
                result['error'] = 'application_error'
            elif await page.locator('.local-acadassistant-turn').count() <= count:
                result['error'] = 'missing_new_answer'
            else:
                last = page.locator('.local-acadassistant-turn').last
                result['answer'] = await last.locator('.local-acadassistant-answer').inner_text()
                text = await last.inner_text()
                links = await last.locator('a').evaluate_all('(els) => els.map(e => e.href)')
                result['links'] = links
                result['ok'] = semantic_check(kind, result['answer'], text, links, profile)
                if not result['ok']:
                    result['error'] = 'semantic_mismatch'
        except Exception as exc:  # noqa: BLE001 - Record failure type without exposing exception contents.
            result['error'] = type(exc).__name__
            result.setdefault('seconds', round(time.monotonic() - started, 4))
        return result

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        pages = []
        monitoring = asyncio.create_task(monitor())
        report['browser'] = browser.version
        started = None
        try:
            for profile in profiles:
                if host_sample()['mem_available_kib'] < 1024 * 1024:
                    report['stop_reason'] = 'generator_setup_available_memory_below_1GiB'
                    return 2
                ctx = await browser.new_context(viewport={'width': 1280, 'height': 900})
                page = await ctx.new_page()
                await page.goto(BASE + '/login/index.php')
                await page.wait_for_load_state('networkidle')
                await page.locator('#username').fill(profile['username'])
                await page.locator('#password').fill(env['MOODLE_DEMO_PASSWORD'])
                await page.locator('#loginbtn').click()
                await page.wait_for_url(lambda url: '/login/' not in url)
                await page.goto(CHAT)
                await page.locator('.local-acadassistant-chat--enhanced').wait_for()
                pages.append(page)
                report['prepared_sessions'] = len(pages)
                save()
            report['warmup'] = await asyncio.gather(*[
                ask(page, profiles[i], *questions[i % len(questions)], 0) for i, page in enumerate(pages)])
            save()
            # A real warmup failure is preserved, never silently retried.
            if any(not r['ok'] for r in report['warmup']):
                report['stop_reason'] = 'warmup_failed'
                return 2
            started = time.monotonic()
            report['measurement_started_utc'] = utc()
            turn = 0
            while time.monotonic() - started < args.seconds or len(report['samples']) < args.requests:
                turn += 1
                elapsed = time.monotonic() - started
                phase = ('base' if elapsed < 60 else 'pico' if elapsed < 120 else 'recuperacion') if args.pattern == 'spike' else 'constante'
                active_pages = pages[:min(10, len(pages))] if args.pattern == 'spike' and phase != 'pico' else pages
                async def one(i, page, round_id=turn):
                    reset_started = time.monotonic()
                    try:
                        await page.get_by_role('button', name='New conversation', exact=True).click(timeout=30000)
                        await page.wait_for_load_state('networkidle', timeout=30000)
                        await page.locator('.local-acadassistant-chat--enhanced').wait_for(timeout=30000)
                    except Exception as exc:  # noqa: BLE001 - Record failure type without exposing exception contents.
                        return {'username': profiles[i]['username'], 'round': round_id, 'kind': 'reset',
                                'timestamp_utc': utc(), 'seconds': round(time.monotonic() - reset_started, 4), 'ok': False,
                                'error': 'reset_' + type(exc).__name__, 'answer': ''}
                    # Barrier below ensures request wave starts only after all resets.
                    return None
                reset_results = await asyncio.gather(*(one(i, p) for i, p in enumerate(active_pages)))
                async def measured(i, p, failures=reset_results, round_id=turn):
                    return failures[i] or await ask(p, profiles[i], *questions[(i + round_id - 1) % len(questions)], round_id)
                samples = await asyncio.gather(*(measured(i, p) for i, p in enumerate(active_pages)))
                for sample in samples:
                    sample['phase'] = phase
                    sample['active_users'] = len(active_pages)
                report['samples'].extend(samples)
                report['summary'] = summary(report['samples'], time.monotonic() - started)
                save()
                print(json.dumps({'stage': args.stage, 'round': turn, **report['summary']}, ensure_ascii=False), flush=True)
                recent = [s for s in report['samples'] if datetime.fromisoformat(s['timestamp_utc']).timestamp() >= time.time()-60]
                recent = recent or samples  # Preserve long timeout waves outside the 60-second window.
                if recent and sum(not s['ok'] for s in recent) / len(recent) > .05:
                    report['stop_reason'] = 'over_5_percent_errors_in_last_minute'
                    break
                if host_sample()['mem_available_kib'] < 512 * 1024:
                    report['stop_reason'] = 'host_available_memory_below_512MiB'
                    break
                if time.monotonic() - started >= args.max_seconds:
                    report['stop_reason'] = 'stage_time_budget'
                    break
                if args.pause:
                    await asyncio.sleep(args.pause)
            report['complete'] = (time.monotonic() - started >= args.seconds and len(report['samples']) >= args.requests and 'stop_reason' not in report)
            report['summary'] = summary(report['samples'], time.monotonic() - started)
            report['accepted'] = report['complete'] and report['summary']['accepted']
            return 0 if report['accepted'] else 1
        except Exception as exc:  # noqa: BLE001 - Record failure type without exposing exception contents.
            report['stop_reason'] = type(exc).__name__
            return 2
        finally:
            report['finished_utc'] = utc()
            # Extract only operational error fields, never raw logs or request bodies.
            try:
                logs = await asyncio.to_thread(subprocess.run,
                    ['docker', 'logs', '--since', report['timestamp_utc'], '--until', report['finished_utc'], 'rag-service-api-1'],
                    capture_output=True, text=True, timeout=10, check=False)
                errors = []
                for line in (logs.stdout + logs.stderr).splitlines():
                    try:
                        event = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if isinstance(event, dict) and event.get('code') and re.fullmatch('[a-z_]+', str(event['code'])):
                        errors.append({key: event.get(key) for key in ['timestamp', 'operation', 'status', 'elapsed_ms', 'code']})
                report['server_errors'] = errors
            except Exception as exc:  # noqa: BLE001 - Record failure type without exposing exception contents.
                report['server_log_collection_error'] = type(exc).__name__
            stop.set()
            await monitoring
            await browser.close()
            save()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', required=True)
    p.add_argument('--users', type=int, choices=range(1, 101), required=True)
    p.add_argument('--seconds', type=int, default=300)
    p.add_argument('--requests', type=int, default=500)
    p.add_argument('--max-seconds', type=int, default=1200)
    p.add_argument('--pause', type=float, default=0)
    p.add_argument('--pattern', choices=['constant', 'spike'], default='constant')
    p.add_argument('--mix', choices=['base', 'extended'], default='base')
    p.add_argument('--profiles', default='.scratch/rendimiento-ampliado/evidencias/perfiles.json')
    p.add_argument('--output', required=True)
    raise SystemExit(asyncio.run(run(p.parse_args())))
