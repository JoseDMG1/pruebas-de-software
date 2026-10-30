"""Complementary native Moodle HTTP load, explicitly excluding browser rendering.

Uses real login/cookies/sesskey and the Moodle controller, not a direct RAG bypass.
The HTML parser retains only answer text/destination URLs; no tokens are exported.
"""
import argparse
import asyncio
import hashlib
import json
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import httpx
from capacity_chat import (
    BASE,
    CHAT,
    QUESTIONS,
    ROOT,
    semantic_check,
    summary,
    telemetry,
    utc,
)


class Page(HTMLParser):
    VOID = frozenset({'input', 'img', 'br', 'hr', 'meta', 'link', 'source', 'area', 'wbr', 'embed', 'param', 'col', 'base'})

    def __init__(self, html):
        super().__init__()
        self.depth = 0
        self.turn_depth = self.answer_depth = None
        self.answer, self.turn, self.links, self.inputs = [], [], [], {}
        self.error = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = a.get('class', '').split()
        if tag not in self.VOID:
            self.depth += 1
        if tag == 'input' and a.get('name'):
            self.inputs[a['name']] = a.get('value', '')
        if 'alert-danger' in classes or a.get('id') == 'assistant-error':
            self.error = True
        if 'local-acadassistant-turn' in classes:
            self.turn_depth = self.depth
            self.answer, self.turn, self.links = [], [], []
        if 'local-acadassistant-answer' in classes:
            self.answer_depth = self.depth
        if tag == 'a' and self.turn_depth is not None and a.get('href'):
            self.links.append(urljoin(BASE, a['href']))

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.answer_depth == self.depth:
            self.answer_depth = None
        if self.turn_depth == self.depth:
            self.turn_depth = None
        self.depth = max(0, self.depth-1)

    def handle_data(self, data):
        if self.answer_depth is not None:
            self.answer.append(data)
        if self.turn_depth is not None:
            self.turn.append(data)


async def run(args):
    out = Path(args.output)
    if out.exists():
        raise ValueError('Refusing to overwrite evidence')
    env = dict(line.split('=', 1) for line in (ROOT/'.moodle.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
    questions = [q for q in QUESTIONS if q[0] in ('courses', 'teachers', 'calendar')] if args.mix == 'academic' else QUESTIONS
    profiles = json.loads((ROOT/'.scratch/rendimiento-ampliado/evidencias/perfiles.json').read_text())['profiles'][:args.users]
    report = {'stage': args.stage, 'timestamp_utc': utc(), 'complete': False, 'configuration': vars(args),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'measurement': 'Native Moodle authenticated POST + redirect GET through real RAG/providers; ends at HTML receipt, excludes browser rendering. Separate from browser E2E results.',
              'profiles': profiles, 'questions': questions, 'samples': [], 'warmup': [], 'telemetry': []}
    stop = asyncio.Event()
    clients, tokens = [], []

    def save():
        temp = out.with_suffix('.tmp')
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        temp.replace(out)

    async def monitor():
        while not stop.is_set():
            report['telemetry'].append(await asyncio.to_thread(telemetry))
            save()
            try:
                await asyncio.wait_for(stop.wait(), 5)
            except TimeoutError:
                pass

    async def reset(i):
        started = time.monotonic()
        try:
            response = await clients[i].post(CHAT, data={'sesskey': tokens[i], 'action': 'new'})
            response.raise_for_status()
            parsed = Page(response.text)
            if parsed.error or not parsed.inputs.get('sesskey'):
                raise ValueError('reset_rejected')
            tokens[i] = parsed.inputs['sesskey']
            return None
        except Exception as exc:  # noqa: BLE001 - Record failure type without exposing exception contents.
            return {'username': profiles[i]['username'], 'kind': 'reset', 'timestamp_utc': utc(),
                    'seconds': round(time.monotonic()-started, 4), 'ok': False,
                    'error': 'reset_'+type(exc).__name__, 'answer': ''}

    async def ask(i, turn):
        kind, question = questions[(i+max(0, turn-1)) % len(questions)]
        result = {'username': profiles[i]['username'], 'round': turn, 'kind': kind, 'question': question,
                  'timestamp_utc': utc(), 'ok': False, 'error': None, 'answer': ''}
        started = time.monotonic()
        try:
            response = await clients[i].post(CHAT, data={'sesskey': tokens[i], 'action': 'ask', 'question': question})
            result['seconds'] = round(time.monotonic()-started, 4)
            response.raise_for_status()
            page = Page(response.text)
            answer = ' '.join(page.answer)
            result['answer'], result['links'] = answer, page.links
            if page.error or '/login/' in str(response.url):
                result['error'] = 'application_error'
            else:
                result['ok'] = semantic_check(kind, answer, ' '.join(page.turn), page.links, profiles[i])
                if not result['ok']:
                    result['error'] = 'semantic_mismatch'
        except Exception as exc:  # noqa: BLE001 - Record failure type without exposing exception contents.
            result.setdefault('seconds', round(time.monotonic()-started, 4))
            result['error'] = type(exc).__name__
        return result

    monitor_task = asyncio.create_task(monitor())
    try:
        for profile in profiles:
            client = httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(150, connect=10), limits=httpx.Limits(max_connections=2))
            clients.append(client)
            login = await client.get(BASE+'/login/index.php')
            token = Page(login.text).inputs['logintoken']
            response = await client.post(BASE+'/login/index.php', data={'username': profile['username'], 'password': env['MOODLE_DEMO_PASSWORD'], 'logintoken': token})
            if '/login/' in str(response.url):
                raise ValueError('login_rejected')
            chat = await client.get(CHAT)
            tokens.append(Page(chat.text).inputs['sesskey'])
        report['warmup'] = await asyncio.gather(*(ask(i, 0) for i in range(args.users)))
        if any(not r['ok'] for r in report['warmup']):
            report['stop_reason'] = 'warmup_failed'
            return 2
        started = time.monotonic()
        report['measurement_started_utc'] = utc()
        turn = 0
        while time.monotonic()-started < args.seconds or len(report['samples']) < args.requests:
            turn += 1
            failures = await asyncio.gather(*(reset(i) for i in range(args.users)))
            async def one(i, errors=failures, round_id=turn):
                return errors[i] or await ask(i, round_id)
            samples = await asyncio.gather(*(one(i) for i in range(args.users)))
            report['samples'].extend(samples)
            report['summary'] = summary(report['samples'], time.monotonic()-started)
            save()
            print(json.dumps({'stage': args.stage, **report['summary']}), flush=True)
            if sum(not x['ok'] for x in samples)/len(samples) > .05:
                report['stop_reason'] = 'over_5_percent_errors_in_wave'
                break
            if time.monotonic()-started > 1200:
                report['stop_reason'] = 'stage_time_budget'
                break
        report['complete'] = 'stop_reason' not in report
        report['accepted'] = report['complete'] and report['summary']['accepted']
        return 0 if report['accepted'] else 1
    except Exception as exc:  # noqa: BLE001 - Record failure type without exposing exception contents.
        report['stop_reason'] = type(exc).__name__
        return 2
    finally:
        report['finished_utc'] = utc()
        stop.set()
        await monitor_task
        await asyncio.gather(*(client.aclose() for client in clients))
        save()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', required=True)
    p.add_argument('--users', type=int, choices=range(1,101), required=True)
    p.add_argument('--seconds', type=int, default=300)
    p.add_argument('--requests', type=int, default=500)
    p.add_argument('--output', required=True)
    p.add_argument('--mix', choices=['base', 'academic'], default='base')
    raise SystemExit(asyncio.run(run(p.parse_args())))
