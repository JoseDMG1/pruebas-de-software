"""Additional controlled spike and richer workload, after the primary campaign."""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT/'.scratch/rendimiento-ampliado/evidencias'


def execute(name, users, seconds, requests, extras):
    command = [str(ROOT/'rag-service/.venv/bin/python'), str(ROOT/'dev/validation/capacity_chat.py'),
               '--stage', name, '--users', str(users), '--seconds', str(seconds),
               '--requests', str(requests), '--output', str(EV/(name+'.json')), *extras]
    print('START', name, users, flush=True)
    with (EV/(name+'.log')).open('x') as log:
        r = subprocess.run(command, check=False, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                           env=os.environ | {'PLAYWRIGHT_BROWSERS_PATH': str(ROOT/'rag-service/.cache/ms-playwright')})
    print('END', name, r.returncode, flush=True)
    return json.loads((EV/(name+'.json')).read_text())


while not (EV/'campana-finalizada.json').exists():
    time.sleep(5)
meta = json.loads((EV/'campana-finalizada.json').read_text())
if meta.get('blocked') or not meta.get('endurance_accepted', False):
    (EV/'complementarias-finalizadas.json').write_text(json.dumps({'blocked': meta.get('blocked') or 'endurance_not_accepted'})+'\n')
    raise SystemExit('Complementary load stopped: endurance not accepted')
stable = meta['highest_accepted_level']
# A spike is only attempted at a population already demonstrated stable.
if stable > 10:
    execute('pico-10-'+str(stable)+'-10', stable, 300, 0, ['--pattern', 'spike'])
execute('mixta-10', 10, 300, 100, ['--mix', 'extended'])
print('Followup finished', flush=True)

(EV/'complementarias-finalizadas.json').write_text(json.dumps({'blocked': None})+'\n')
