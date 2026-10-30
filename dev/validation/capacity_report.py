"""Summarize preserved capacity stages without discarding failures or calibration."""
import json
import math
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / '.scratch/rendimiento-ampliado/evidencias'


def stage_row(path):
    d = json.loads(path.read_text())
    s = d.get('summary', {})
    all_samples = d.get('telemetry', [])
    samples = [x for x in all_samples if d.get('measurement_started_utc') and x['timestamp_utc'] >= d['measurement_started_utc']]
    cpu = []
    for before, after in pairwise(samples):
        total = after['cpu_total_ticks'] - before['cpu_total_ticks']
        idle = after['cpu_idle_ticks'] - before['cpu_idle_ticks']
        if total > 0:
            cpu.append(100 * (1 - idle / total))
    phases = {}
    for phase in sorted({x.get('phase', 'constante') for x in d.get('samples', [])}):
        group = [x for x in d['samples'] if x.get('phase', 'constante') == phase]
        latencies = sorted(x['seconds'] for x in group)
        phases[phase] = {'requests': len(group), 'errors': sum(not x['ok'] for x in group),
            'successful_within_10_percent': round(100*sum(x['ok'] and x['seconds'] <= 10 for x in group)/len(group), 3),
            'p95_seconds': latencies[math.ceil(.95*len(group))-1],
            'active_users': sorted({x.get('active_users', d['configuration']['users']) for x in group})}
    return {
        'channel': 'HTTP Moodle sin navegador' if d['stage'].startswith('http-') else 'Chat en navegador',
        'phases': phases, 'mix': d['configuration'].get('mix', 'base'), 'pattern': d['configuration'].get('pattern', 'constant'),
        'file': path.name, 'stage': d['stage'], 'timestamp_utc': d.get('timestamp_utc'), 'users': d['configuration']['users'],
        'requested_seconds': d['configuration']['seconds'],
        'complete': d.get('complete', False), 'accepted': d.get('accepted', False),
        'stop_reason': d.get('stop_reason'), 'warmup_errors': sum(not x['ok'] for x in d.get('warmup', [])),
        **s,
        'cpu_mean_percent': round(sum(cpu)/len(cpu), 2) if cpu else None,
        'cpu_peak_sample_percent': round(max(cpu), 2) if cpu else None,
        'minimum_available_ram_mib': round(min(x['mem_available_kib'] for x in samples)/1024, 1) if samples else None,
        'peak_browser_rss_mib': round(max(x.get('browser_rss_kib', 0) for x in samples)/1024, 1) if samples else None,
        'resource_window': 'measured phase only; empty for warmup/setup failures',
        'peak_swap_mib': round(max(x['swap_used_kib'] for x in samples)/1024, 1) if samples else None,
        'health_samples': len(samples),
        'healthy_paired_samples': sum(x.get('rag_healthy', False) and x.get('moodle_healthy', False) for x in samples),
    }


def main():
    rows = []
    for path in sorted(EV.glob('*.json')):
        d = json.loads(path.read_text())
        if 'stage' in d and 'configuration' in d:
            rows.append(stage_row(path))
    rows.sort(key=lambda r: r.get('timestamp_utc') or '')
    (EV/'resumen.json').write_text(json.dumps({'stages': rows,
        'limits': 'Browser stages plus explicitly separate native Moodle HTTP stages (without rendering); local host shared with Chromium, real remote providers, prepared student identities based on two enrolment profiles. Semantic checks are minimum automatic oracles, not human assessment of every claim. Historical calibration failures retained.'}, ensure_ascii=False, indent=2)+'\n')
    lines = ['# Campaña ampliada de rendimiento', '',
             'Resultados por ejecución. No se eliminan respuestas lentas ni fallos. La calibración del arnés se identifica por separado. Las etapas http-* usan el controlador autenticado de Moodle pero excluyen el navegador: no se equiparan al tiempo desde clic hasta respuesta visible.', '',
             '| Etapa | Cuentas | Solicitudes medidas | Duración medida (s) | Correctas ≤10 s | p95 (s) | p99 (s) | Errores | Completa / cumple |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['stage']} | {r['users']} | {r.get('requests', 0)} | {r.get('elapsed_seconds', '—')} | {r.get('successful_within_10_percent', '—')}% | {r.get('p95_seconds', '—')} | {r.get('p99_seconds', '—')} | {r.get('errors', 0)} | {'Sí' if r['complete'] else 'No'} / {'Sí' if r['accepted'] else 'No'} |")
    lines += ['', 'La aprobación requiere ejecución completa, cero errores y ≥95% correctas en ≤10 s. Calentamiento y acceso quedan fuera de la latencia; reinicios de conversación y pausas declaradas forman parte del throughput. Los resúmenes de recursos y disponibilidad filtran la fase medida; los JSON conservan también la preparación. No es un SLA.', '',
              'La calibración baseline-1 tuvo un falso negativo de gratuidad no solicitada; ver ajustes-arnes.md. No se atribuye al producto. Los resultados posteriores usan correo/cita/fuente como criterio de esa pregunta.', '', '## Recursos y límites por etapa', '']
    for r in rows:
        lines.append(f"- {r['stage']}: CPU media {r['cpu_mean_percent']}%, pico muestreado {r['cpu_peak_sample_percent']}%; RAM disponible mínima {r['minimum_available_ram_mib']} MiB; swap máximo {r['peak_swap_mib']} MiB; RSS agregado de procesos de navegador {r['peak_browser_rss_mib']} MiB (incluye memoria compartida y otros navegadores del host, no es memoria exclusiva). Sondas conjuntas correctas {r['healthy_paired_samples']}/{r['health_samples']}. Motivo de parada: {r['stop_reason'] or 'finalización prevista'}. Fallos de calentamiento: {r['warmup_errors']}.")
    lines += ['', '## Fases del pico', '']
    for r in rows:
        if r['pattern'] == 'spike':
            for phase, values in r['phases'].items():
                lines.append(f"- {r['stage']} / {phase}: {values['active_users']} cuentas activas; {values['requests']} consultas; {values['errors']} errores; {values['successful_within_10_percent']}% correctas ≤10 s; p95 {values['p95_seconds']} s.")
    (EV/'resultados.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
