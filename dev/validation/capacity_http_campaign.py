"""Run the complementary HTTP channel only after browser measurements finish."""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT/'.scratch/rendimiento-ampliado/evidencias'


def execute(users, seconds, requests):
    name = 'http-'+str(users)
    with (EV/(name+'.log')).open('x') as log:
        code = subprocess.run([str(ROOT/'rag-service/.venv/bin/python'), str(ROOT/'dev/validation/capacity_http.py'),
            '--stage', name, '--users', str(users), '--seconds', str(seconds), '--requests', str(requests),
            '--output', str(EV/(name+'.json'))], cwd=ROOT, check=False, env=os.environ, stdout=log, stderr=subprocess.STDOUT).returncode
    d = json.loads((EV/(name+'.json')).read_text())
    print(name, code, d.get('summary'), d.get('stop_reason'), flush=True)
    return d


while True:
    gate = EV/'complementarias-finalizadas.json'
    if gate.exists() and json.loads(gate.read_text()).get('blocked'):
        raise SystemExit('HTTP capacity load stopped: provider/campaign gate')
    path = EV/'mixta-10.json'
    if path.exists() and json.loads(path.read_text()).get('finished_utc'):
        break
    time.sleep(5)
if execute(1, 0, 10).get('accepted'):
    for users in [50, 100]:
        if not execute(users, 300, 500).get('accepted'):
            break
(EV/'http-finalizado.json').write_text(json.dumps({'complete': True, 'note': 'HTTP measurement excludes browser rendering; see per-stage acceptance.'})+'\n')
