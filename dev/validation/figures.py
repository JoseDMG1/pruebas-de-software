"""Generate code-native diagrams and measured performance charts for the report."""

import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "informe y rúbrica/corregido/recursos"
EVIDENCE = ROOT / ".scratch/cumplimiento-rubrica-final/evidencias"
BLUE = "#153b59"


def diagram(name, title, boxes, links, footer="", size=(11, 6)):
    fig, ax = plt.subplots(figsize=size)
    ax.set(xlim=(0, 11), ylim=(0, 6))
    ax.axis("off")
    ax.set_title(title, fontsize=15, color=BLUE, weight="bold", pad=16)
    for x, y, w, h, text in boxes:
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0.08",
                facecolor="#eef4f8",
                edgecolor=BLUE,
                lw=1.4,
            )
        )
        ax.text(
            x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9, color=BLUE
        )
    for a, b, label in links:
        ax.annotate(
            "",
            xy=b,
            xytext=a,
            arrowprops={"arrowstyle": "->", "color": "#527b8d", "lw": 1.5},
        )
        ax.text(
            (a[0] + b[0]) / 2,
            (a[1] + b[1]) / 2 + 0.16,
            label,
            ha="center",
            va="center",
            fontsize=8,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1},
        )
    if footer:
        ax.text(0.1, 0.12, footer, fontsize=8, color="#52606a", wrap=True)
    fig.tight_layout()
    for ext in ["png", "svg"]:
        fig.savefig(OUT / f"{name}.{ext}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    diagram(
        "despliegue",
        "Despliegue local y límites de confianza",
        [
            (0.2, 3.5, 2, 1.2, "Navegador\nChat Moodle\n127.0.0.1:8088"),
            (3.2, 3.5, 2.1, 1.2, "Moodle / PHP\nAutenticación\ny permisos"),
            (6.5, 3.5, 2.2, 1.2, "FastAPI / RAG\n127.0.0.1:8000\nValida firma"),
            (3.2, 1, 2.1, 1.2, "PostgreSQL Moodle\nCursos, tareas\ny calificaciones"),
            (
                6.5,
                1,
                2.2,
                1.2,
                "PostgreSQL + pgvector\nDocumentos, fragmentos\ny embeddings",
            ),
            (9.3, 3.5, 1.5, 1.2, "DeepSeek\nChat / intención"),
            (9.3, 1, 1.5, 1.2, "Gemini\nEmbeddings"),
        ],
        [
            ((2.2, 4.1), (3.2, 4.1), "HTTP local"),
            ((5.3, 4.1), (6.5, 4.1), "JSON firmado"),
            ((4.2, 3.5), (4.2, 2.2), "Lectura autorizada"),
            ((7.6, 3.5), (7.6, 2.2), "SQL"),
            ((8.7, 4.1), (9.3, 4.1), "HTTPS"),
            ((8.7, 3.6), (9.3, 2.2), "HTTPS"),
        ],
        "La firma protege autenticidad e integridad; no cifra HTTP. Las APIs remotas requieren conexión a internet.",
    )
    diagram(
        "clases",
        "Clases principales y responsabilidades (vista simplificada)",
        [
            (
                0.2,
                3.6,
                2.7,
                1.5,
                "academic_assistant\n───────────────\n+ ask(question, context)\nCoordina la consulta",
            ),
            (
                0.2,
                1,
                2.7,
                1.5,
                "academic_context_provider\n───────────────\n+ collect_for_plan(...)\nLee datos autorizados",
            ),
            (
                4,
                3.6,
                2.7,
                1.5,
                "conversation_store\n───────────────\n+ append(...) / clear()\nContexto de sesión",
            ),
            (
                7.8,
                3.6,
                2.8,
                1.5,
                "QueryService\n───────────────\n+ interpret() / ask()\n+ documentary_evidence()",
            ),
            (
                4,
                1,
                2.7,
                1.5,
                "Repository\n───────────────\n+ retrieve() / save()\n+ delete()",
            ),
            (
                7.8,
                1,
                2.8,
                1.5,
                "DeepSeekChatProvider\n───────────────\n+ interpret() / generate()\nAdaptador del modelo",
            ),
        ],
        [
            ((1.5, 3.6), (1.5, 2.5), "usa"),
            ((2.9, 4.3), (4, 4.3), "sesión"),
            ((1.5, 5.25), (9.2, 5.25), "API: JSON firmado"),
            ((8.7, 3.6), (6, 2.5), "usa"),
            ((9.2, 3.6), (9.2, 2.5), "usa"),
        ],
        "Las flechas indican uso; la comunicación Moodle–QueryService pasa por la API, no por acceso directo entre lenguajes.",
    )
    # Correct the API edge explicitly in a separate sequence view; classes are responsibility overview.
    diagram(
        "entidades",
        "Modelo de datos documental (relaciones principales)",
        [
            (0.2, 3.8, 2.3, 1.2, "tipo_documento\nPK id_tipo_documento\nnombre"),
            (4, 3.8, 2.5, 1.2, "documento\nPK id_documento\nclave, versión, alcance"),
            (
                8.1,
                3.8,
                2.5,
                1.2,
                "fragmento\nPK id_fragmento\nFK id_documento\ntexto, páginas",
            ),
            (0.2, 1, 2.3, 1.2, "curso_moodle\nPK course_id\nactive"),
            (4, 1, 2.5, 1.2, "documento_curso\nPK/FK id_documento\nPK/FK course_id"),
            (
                8.1,
                1,
                2.5,
                1.2,
                "fragmento_embedding\nPK/FK id_fragmento\nPK/FK id_espacio",
            ),
        ],
        [
            ((2.5, 4.4), (4, 4.4), "1 → N"),
            ((6.5, 4.4), (8.1, 4.4), "1 → N"),
            ((5.2, 3.8), (5.2, 2.2), "1 → N"),
            ((2.5, 1.6), (4, 1.6), "1 → N"),
            ((9.3, 3.8), (9.3, 2.2), "1 → N"),
        ],
        "espacio_embedding define proveedor, modelo y dimensiones (1:N con fragmento_embedding).\nproceso_indexacion registra cada carga (N:1 con documento). Moodle mantiene usuarios y notas en su propia base.",
    )
    # Sequence diagrams are generated with native lines and text, not screenshots of obsolete diagrams.
    for name, title, events in [
        (
            "secuencia-exitosa",
            "Consulta documental autorizada",
            [
                (0, 1, "Pregunta y sesión"),
                (1, 2, "Interpretar: JSON firmado"),
                (2, 3, "Clasificar intención"),
                (3, 2, "Plan estructurado"),
                (2, 1, "Plan validado"),
                (1, 2, "Consulta y permisos efectivos"),
                (2, 3, "Embeddings / evidencia / respuesta"),
                (3, 2, "Hechos y citas verificables"),
                (2, 1, "Respuesta y fuentes"),
                (1, 0, "Respuesta visible"),
            ],
        ),
        (
            "secuencia-sin-evidencia",
            "Consulta sin evidencia suficiente",
            [
                (0, 1, "Pregunta"),
                (1, 2, "Consulta firmada y permisos"),
                (2, 3, "Recuperar documentos permitidos"),
                (3, 2, "Sin pasajes suficientes"),
                (2, 1, "Abstención sin fuentes inventadas"),
                (1, 0, "Mensaje para precisar la consulta"),
            ],
        ),
        (
            "secuencia-error",
            "Error de comunicación o proveedor",
            [
                (0, 1, "Pregunta"),
                (1, 2, "Petición validada"),
                (2, 3, "Llamada al proveedor"),
                (3, 2, "Error / timeout; reintentos acotados"),
                (2, 1, "Error controlado sin secretos"),
                (1, 0, "Conservar pregunta y permitir reintento"),
            ],
        ),
    ]:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis("off")
        ax.set(xlim=(-0.5, 3.5), ylim=(-1, len(events) + 2))
        labels = ["Persona", "Moodle", "API / RAG", "Datos / proveedores"]
        for i, label in enumerate(labels):
            ax.text(i, len(events) + 1, label, ha="center", weight="bold", color=BLUE)
            ax.plot([i, i], [-0.5, len(events) + 0.5], "--", color="#aab8c2", lw=1)
        for j, (a, b, label) in enumerate(events):
            y = len(events) - j
            ax.annotate(
                "",
                xy=(b, y),
                xytext=(a, y),
                arrowprops={"arrowstyle": "->", "color": BLUE},
            )
            ax.text((a + b) / 2, y + 0.13, label, ha="center", fontsize=8)
        ax.set_title(title, color=BLUE, fontsize=15, pad=18)
        fig.tight_layout()
        fig.savefig(OUT / f"{name}.png", dpi=180, bbox_inches="tight")
        plt.close(fig)
    loadpath = EVIDENCE / "carga.json"
    if loadpath.exists():
        load = json.loads(loadpath.read_text())
        samples = load.get("samples", [])
        if samples:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.scatter(
                range(1, len(samples) + 1),
                [s["seconds"] for s in samples],
                c=["#13837a" if s["ok"] else "#b91c1c" for s in samples],
                s=24,
            )
            ax.axhline(10, color="#b91c1c", ls="--", label="Umbral: 10 s")
            ax.set(
                xlabel="Solicitud (orden por ronda y usuario virtual)",
                ylabel="Tiempo hasta respuesta visible (s)",
                title="Chat Moodle: todas las solicitudes medidas",
            )
            ax.legend()
            ax.grid(alpha=0.2)
            fig.tight_layout()
            fig.savefig(OUT / "carga.png", dpi=180)
            plt.close(fig)
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.hist(
                [s["seconds"] for s in samples],
                bins=15,
                color="#153b59",
                edgecolor="white",
            )
            ax.axvline(10, color="#b91c1c", ls="--", label="10 s")
            ax.set(
                xlabel="Latencia (s)",
                ylabel="Solicitudes",
                title="Distribución de latencias; sin excluir errores o valores lentos",
            )
            ax.legend()
            fig.tight_layout()
            fig.savefig(OUT / "distribucion.png", dpi=180)
            plt.close(fig)


if __name__ == "__main__":
    main()
