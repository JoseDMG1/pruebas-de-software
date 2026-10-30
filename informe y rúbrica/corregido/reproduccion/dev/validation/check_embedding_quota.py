"""Single diagnostic request; exports only quota metadata, never credentials or raw error text."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
from rag_service.config import Settings

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', default='.scratch/rendimiento-ampliado/evidencias/cuota-gemini.json')
path = ROOT / parser.parse_args().output
if path.exists():
    raise ValueError('Refusing to overwrite diagnostic evidence')
s = Settings(_env_file=ROOT/'rag-service/.env')
response = httpx.post(
    'https://generativelanguage.googleapis.com/v1beta/models/'+s.gemini_embedding_model+':embedContent',
    headers={'x-goog-api-key': s.gemini_api_key.get_secret_value()},
    json={'content': {'parts': [{'text': 'Comprobación de disponibilidad para la evaluación local.'}]},
          'taskType': 'RETRIEVAL_QUERY', 'outputDimensionality': s.gemini_embedding_dimensions},
    timeout=30,
)
body = response.json()
report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'http_status': response.status_code,
          'model': s.gemini_embedding_model, 'quota_violations': [], 'retry_delay': None}
for detail in body.get('error', {}).get('details', []):
    for violation in detail.get('violations', []):
        report['quota_violations'].append({key: violation.get(key) for key in ['quotaMetric', 'quotaId', 'quotaValue']})
    if 'retryDelay' in detail:
        report['retry_delay'] = detail['retryDelay']
if response.status_code == 200:
    report['embedding_dimensions'] = len(body.get('embedding', {}).get('values', []))
path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(report, ensure_ascii=False))
