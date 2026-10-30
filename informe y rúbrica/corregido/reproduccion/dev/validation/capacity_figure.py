"""Plot all measured post-calibration stages, including failed acceptance."""
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
rows = json.loads((ROOT/'.scratch/rendimiento-ampliado/evidencias/resumen.json').read_text())['stages']
rows = [r for r in rows if not r['stage'].startswith(('baseline', 'http-')) and r.get('requests', 0)]
fig, axes = plt.subplots(1, 2, figsize=(12, max(4, len(rows)*.55)), layout='constrained')
names = [r['stage'] for r in rows]
colors = ['#247c5c' if r['accepted'] else '#b54b39' for r in rows]
axes[0].barh(names, [r['p95_seconds'] for r in rows], color=colors)
axes[0].axvline(10, color='#153b59', linestyle='--', label='Referencia: 10 segundos')
axes[0].set_xlabel('p95 del chat completo (segundos)')
axes[0].legend()
axes[1].barh(names, [r['successful_within_10_percent'] for r in rows], color=colors)
axes[1].axvline(95, color='#153b59', linestyle='--', label='Meta: ≥95%')
axes[1].set_xlabel('Respuestas correctas en ≤10 s (%)')
axes[1].set_xlim(0, 105)
axes[1].legend()
for ax in axes:
    ax.invert_yaxis()
    ax.spines[['top','right']].set_visible(False)
fig.suptitle('Rendimiento ampliado · verde: etapa completa que cumple; rojo: no cumple')
out = ROOT/'informe y rúbrica/corregido/recursos/capacidad-ampliada.png'
fig.savefig(out, dpi=180)
print(out)
