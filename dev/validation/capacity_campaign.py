"""Adaptive bounded campaign; never overlaps stages or silently retries failed runs."""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / '.scratch/rendimiento-ampliado/evidencias'
PYTHON = ROOT / 'rag-service/.venv/bin/python'


def execute(name, users, seconds, requests, pause=0):
    command = [str(PYTHON), str(ROOT/'dev/validation/capacity_chat.py'), '--stage', name,
               '--users', str(users), '--seconds', str(seconds), '--requests', str(requests),
               '--max-seconds', str(max(seconds+300, 1200)), '--pause', str(pause),
               '--output', str(EV/(name+'.json'))]
    print('START', name, users, seconds, requests, flush=True)
    with (EV/(name+'.log')).open('x') as log:
        result = subprocess.run(command, check=False, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                env=os.environ | {'PLAYWRIGHT_BROWSERS_PATH': str(ROOT/'rag-service/.cache/ms-playwright')})
    d = json.loads((EV/(name+'.json')).read_text())
    print('END', name, result.returncode, d.get('summary'), d.get('stop_reason'), flush=True)
    return d


def main():
    while True:
        d = json.loads((EV/'nivel-10.json').read_text())
        if d.get('finished_utc'):
            break
        time.sleep(3)
    stable = 10 if d.get('accepted') else 1
    for users in [25, 50, 75, 100]:
        d = execute('nivel-'+str(users), users, 300, 500)
        if d.get('accepted'):
            stable = users
        else:
            break
    # Recovery at the original level measures whether degradation persists.
    execute('recuperacion-10', 10, 300, 100)
    # A bounded 15-minute endurance screen precedes any production-length soak.
    endurance = execute('sostenida-'+str(stable), stable, 900, max(100, stable*10), pause=3)
    (EV/'campana-finalizada.json').write_text(json.dumps({'highest_accepted_level': stable, 'endurance_accepted': endurance.get('accepted', False),
        'blocked': 'provider_throttling_requires_diagnosis' if any(e.get('code') == 'gemini_throttled' for e in endurance.get('server_errors', [])) else None,
        'scope': '15-minute local endurance screen; not 60-minute or production soak. Increasing browser setup itself ramps load; synchronized request waves are spikes, not a separately controlled 10-to-N-to-10 live population.'}, indent=2)+'\n')


if __name__ == '__main__':
    main()
