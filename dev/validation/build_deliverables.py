"""Build corrected, editable deliverables from canonical tables and real evidence.

Requires python-docx, openpyxl, python-pptx, matplotlib. Does not edit originals.
Run after validation; incomplete/failed evidence is never turned into PASS.
"""

import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.util import Inches as PI, Pt as PP
from pptx.dml.color import RGBColor as PC

from report_content import RF, RNF, HU, CASES, RISKS, CASE_TEST_TYPES
import figures
from test_inventory import inventory, APPLICATION

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "informe y rúbrica/corregido"
EV = ROOT / ".scratch/cumplimiento-rubrica-final/evidencias"
ASSETS = OUT / "recursos"
BLUE = "153B59"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def flag(value):
    return "Sí" if value else "No"


def read(name):
    path = EV / name
    return json.loads(path.read_text()) if path.exists() else {}


def junit(name):
    path = EV / name
    if not path.exists():
        return []
    return list(ET.parse(path).getroot().iter("testcase"))


PYTEST = junit("pytest.xml")
PHPUNIT = junit("phpunit.xml")
IA = read("evaluacion-ia.json")
LOAD = read("carga.json")
FUNC = read("funcionales.json")
NAV = read("navegacion.json")
UI = read("interfaz.json")
ENV = read("entorno.json")
CAPACITY_PATH = ROOT / ".scratch/rendimiento-ampliado/evidencias/resumen.json"
CAPACITY = json.loads(CAPACITY_PATH.read_text()) if CAPACITY_PATH.exists() else {}
DEFECTS = read("defectos.json").get("defects", [])


def tests_ok(tests):
    return bool(tests) and all(
        not any(c.tag in ("failure", "error", "skipped") for c in t) for t in tests
    )


def case_result(case):
    key, hu, obj, technique, pre, inp, steps, expected, family, selector = case
    passed, detail, evidence = None, "Sin ejecución registrada.", ""
    if family == "pytest":
        tests = [
            t
            for t in PYTEST
            if selector in (t.get("name", "") + t.get("classname", ""))
        ]
        if tests:
            passed, detail = (
                tests_ok(tests),
                f"{len(tests)} prueba(s) seleccionada(s): "
                + "; ".join(t.get("name", "") for t in tests),
            )
        evidence = "pytest.xml"
    elif family == "evaluation" and IA.get("complete"):
        s = IA["summary"]
        passed = (
            (s["positive_passed"] >= math.ceil(s["positive_total"] * 0.9))
            if selector == "positive"
            else s["negative_passed"] == s["negative_total"]
        )
        detail = f"{s['positive_passed']}/{s['positive_total']} positivas; {s['negative_passed']}/{s['negative_total']} negativas. Umbral positivas: 90%."
        evidence = "evaluacion-ia.json"
    elif family == "functional":
        c = next((x for x in FUNC.get("cases", []) if x["id"] == selector), None)
        if c:
            passed = c["passed"]
            observed = c["observed"]
            if isinstance(observed, dict) and "answer" in observed:
                answer = observed["answer"]
                excerpt = (
                    answer[-1100:]
                    if selector in ("weekly", "followup")
                    else answer[:1100]
                )
                detail = (
                    "Pregunta: "
                    + observed.get("question", "")
                    + "\nRespuesta: "
                    + excerpt
                )
                if len(answer) > 1100:
                    detail += "\n[Respuesta íntegra en la evidencia JSON.]"
            else:
                if selector == "limits":
                    detail = (
                        "Mensaje vacío: " + ("rechazado correctamente" if observed["empty_rejected"] else "no fue rechazado")
                        + ". Mensaje de 1.001 caracteres: "
                        + ("rechazado correctamente" if observed["1001_rejected"] else "no fue rechazado")
                        + ". Se verificaron ambos límites de entrada."
                    )
                elif isinstance(observed, dict) and "second_session_empty" in observed:
                    detail = (
                        "Al abrir una segunda sesión, "
                        + ("el historial estaba vacío y no se compartió la conversación de la primera sesión" if observed["second_session_empty"] else "se encontró historial que debía estar aislado")
                        + ". Al usar la opción de limpiar, "
                        + ("se borró el historial de la conversación" if observed["cleared"] else "el historial no se borró correctamente")
                        + "."
                    )
                else:
                    raise ValueError(f"Falta interpretar el resultado funcional de {key}")
        evidence = "funcionales.json#" + selector
    elif family == "navigation" and NAV.get("complete"):
        passed, detail = (
            True,
            f"{len(NAV['cases'])} consultas y apertura de destinos comprobadas por aserciones; ver enlaces por caso.",
        )
        evidence = "navegacion.json"
    elif family == "ui" and UI:
        passed = all(x.get("complete") for x in UI.values())
        detail = "Chromium: escritorio 1280×1100 y móvil 390×844. Respuestas interceptadas; cero llamadas IA en esta prueba."
        evidence = "interfaz.json"
    elif family == "suites":
        passed = tests_ok(PYTEST) and tests_ok(PHPUNIT)
        detail = f"{len(PYTEST)} pruebas Python; {len(PHPUNIT)} pruebas PHP. Ver JUnit para estado individual."
        evidence = "pytest.xml; phpunit.xml"
    elif family == "load" and LOAD.get("complete"):
        s = LOAD["summary"]
        if selector == "latency":
            passed = s["successful_within_10_percent"] >= 95
        elif selector == "errors":
            passed = (
                s["errors"] == 0
                and s["requests"] == 100
                and LOAD["configuration"]["virtual_users"] == 10
            )
        else:
            passed = LOAD["availability"].get("percent", 0) >= 95
        a = LOAD["availability"]
        detail = (
            f"En la ejecución inicial, los servicios respondieron en {a['successful_samples']} "
            f"de {a['samples']} comprobaciones HTTP ({a['percent']}%). "
            "Esta medición describe disponibilidad durante esa ejecución; "
            "no garantiza disponibilidad mensual ni que las respuestas de IA sean correctas."
            if selector == "availability" else
            f"En la ejecución inicial se realizaron {s['requests']} consultas, "
            f"con {s['errors']} errores; el {s['successful_within_10_percent']}% "
            "respondió correctamente en un máximo de 10 segundos."
        )
        evidence = "carga.json"
        stages = [r for r in CAPACITY.get("stages", []) if not r["stage"].startswith("baseline")]
        if stages:
            primary = [r for r in stages if r["stage"].startswith(("nivel-", "sostenida-", "recuperacion-"))]
            if selector == "latency":
                levels = [r for r in primary if r["stage"].startswith("nivel-")]
                passed = bool(levels) and all(r["complete"] and r.get("successful_within_10_percent", 0) >= 95 and r.get("errors", 0) == 0 for r in levels)
            elif selector == "errors":
                checked = primary + [r for r in stages if r["stage"].startswith(("pico-", "mixta-"))]
                passed = bool(checked) and all(r["complete"] and r.get("errors", 0) == 0 and r.get("warmup_errors", 0) == 0 for r in checked)
            else:
                passed = bool(primary) and all(r.get("health_samples", 0) > 0 and r["healthy_paired_samples"] / r["health_samples"] >= .95 for r in primary)
            detail = "Referencia inicial (10 sesiones, dos cuentas): " + detail
            detail += " Campaña ampliada, estados independientes: " + "; ".join(
                f"{r['stage']}: {r['users']} cuentas, {r.get('requests', 0)} consultas, {r.get('successful_within_10_percent', '—')}% correctas ≤10 s, p95={r.get('p95_seconds', '—')} s, completa={flag(r['complete'])}, cumple={flag(r['accepted'])}"
                for r in stages)
            # Make the acceptance meaning explicit in the spreadsheet cell.
            # CP-011 is the latency criterion; CP-012 is the prolonged-load
            # stability criterion. Keep the factual stage data above as trace.
            if key == "CP-011":
                detail = (
                    "Rendimiento: se exige que al menos el 95% de las respuestas "
                    "correctas llegue en 10 s o menos. Con 10 cuentas: 100% "
                    "(p95 7,16 s); con 25: 99,4% (p95 8,55 s) en prueba breve; "
                    "con 50: 61,636% y p95 13,09 s. Como el nivel de 50 no alcanza "
                    "el umbral, CP-011 FALLÓ. El equipo local también estuvo bajo "
                    "presión de CPU y memoria, por lo que la medición corresponde "
                    "al entorno completo. El p95 significa que el 95% de las "
                    "consultas terminó dentro del tiempo indicado."
                )
            elif key == "CP-012":
                detail = (
                    "Estabilidad con carga prolongada y escenarios ampliados: "
                    "la fase sostenida prevista para 15 min se detuvo tras "
                    "161,485 s y 225 consultas, con 6 errores porque se agotó "
                    "la cuota diaria de Gemini embeddings. No terminó la duración "
                    "prevista ni se completaron los escenarios posteriores; por "
                    "ello CP-012 FALLÓ como criterio de ejecución sin errores, "
                    "pero el resultado es inconcluso sobre estabilidad prolongada. "
                    "Se requiere repetir la evaluación con cuota suficiente "
                    "para determinar si mantiene la estabilidad durante 15 minutos."
                )
            elif key == "CP-033":
                detail = "Disponibilidad HTTP durante la carga: " + "; ".join(
                    f"{r['users']} cuentas ({r['stage']}): los servicios respondieron "
                    f"en {r['healthy_paired_samples']} de {r['health_samples']} comprobaciones "
                    f"({100 * r['healthy_paired_samples'] / r['health_samples']:.2f}%)"
                    for r in primary if r.get("health_samples", 0)
                ) + (
                    ". Se alcanzó el mínimo del 95% en las fases medidas, por lo que "
                    "CP-033 aprobó. Esta comprobación verifica que los servicios "
                    "responden por HTTP; la velocidad del chat se evalúa en CP-011 "
                    "y los errores por cuota en CP-012. No representa disponibilidad mensual."
                    if passed else ". No se alcanzó el mínimo del 95% en todas las fases medidas."
                )
            evidence += "; rendimiento-ampliado/resumen.json"
    elif family == "environment" and ENV:
        bindings = ENV.get("bindings", [])
        passed = bool(bindings) and "Listen 127.0.0.1:8088" in ENV.get(
            "apache_listen", ""
        )
        for b in bindings:
            for entries in (b.get("ports") or {}).values():
                passed = passed and all(e["HostIp"] == "127.0.0.1" for e in entries)
        detail = "Configuración de puertos Docker y Listen de Apache registrada; ver CP-010 para comprobación del HTML sin claves."
        evidence = "entorno.json; funcionales.json#injection"
    elif family == "artifact":
        audit = read("artefactos.json")
        if audit:
            passed = audit.get("passed", False)
            detail = audit.get("summary", "Ver validación de artefactos")
        evidence = "artefactos.json"
    state = (
        "APROBADO" if passed is True else "FALLÓ" if passed is False else "PENDIENTE"
    )
    return {
        "id": key,
        "status": state,
        "observed": detail,
        "evidence": evidence,
        "date": TODAY,
    }


RESULTS = [case_result(c) for c in CASES]
RUBRIC = [
    (
        "Historias de usuario y aceptación",
        3,
        "HU completas, identificadas y priorizadas; roles, beneficio y criterios verificables; trazabilidad a funcionalidades.",
        "10 HU; tablas RF/RNF, criterios y matriz RF→HU→CP.",
        "Documentado",
    ),
    (
        "Diseño de casos de prueba",
        4,
        "Matriz exhaustiva con ID, HU, objetivo, precondiciones, datos, pasos, esperado, técnica; positivos, negativos y límites, trazabilidad.",
        "36 casos completos y escenarios IA clasificados; Excel y anexo de casos.",
        "Documentado",
    ),
    (
        "Ejecución de pruebas funcionales",
        3,
        "Registra real vs esperado, estado, fecha, evidencias y cobertura; comprueba integración e IA.",
        "JUnit, resultados funcionales, navegación, interfaz y evaluación IA.",
        f"{sum(r['status'] == 'APROBADO' for r in RESULTS)}/{len(RESULTS)} casos aprobados; detalle y límites en anexos",
    ),
    (
        "Pruebas de rendimiento",
        3,
        "Escenario y carga justificados, herramienta/configuración reproducible, p95, throughput y errores; compara umbrales y analiza hallazgos.",
        "carga.json y rendimiento-ampliado/: etapas, scripts, recursos, cuota y gráficas.",
        "Caracterización ejecutada; latencia a 50 y estabilidad sostenida no aprobadas; ver DEF-08/09" if CAPACITY else ("Cumple objetivo" if LOAD.get("complete") and LOAD.get("summary", {}).get("accepted") else "Objetivo pendiente o incumplido"),
    ),
    (
        "Gestión de defectos",
        2,
        "Defectos documentados con ID, severidad, pasos, evidencia, estado y reprueba; si no hay defectos, demuestra búsqueda sustentada.",
        "Registro de defectos y pruebas de regresión; se conserva ejecución inicial.",
        f"{len(DEFECTS)} defectos registrados; estados y repruebas identificados",
    ),
    (
        "Aplicativo e integración de IA",
        2,
        "Funciones principales operativas; IA evaluada con consultas correctas, ambiguas, erróneas y fuera de alcance.",
        "Interfaz real, casos de permisos, planificación y evaluación documental.",
        "Verificado en ejecuciones de referencia; campaña nueva detecta bloqueo documental por cuota"
        if FUNC.get("complete")
        and all(c["passed"] for c in FUNC.get("cases", []))
        and IA.get("summary", {}).get("accepted")
        and NAV.get("complete")
        else "Validación parcial: consultar casos",
    ),
    (
        "Informe técnico y evidencias",
        2,
        "Informe coherente, completo, con trazabilidad, métricas, análisis, limitaciones, resultados y anexos.",
        "DOCX/PDF, Excel, scripts, evidencias y control de cambios.",
        "Documentado; revisión visual adjunta",
    ),
    (
        "Exposición y sustentación",
        1,
        "PPT ordenado, demostración técnica, explica decisiones y responde preguntas con dominio.",
        "PPT y guion con preguntas para ensayo.",
        "Material preparado; exposición oral pendiente",
    ),
]


def make_excel():
    wb = Workbook()
    wb.remove(wb.active)

    def sheet(name, headers, rows, widths=None):
        ws = wb.create_sheet(name)
        ws.append(headers)
        for row in rows:
            ws.append([str(x) if isinstance(x, (dict, list)) else x for x in row])
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor=BLUE)
            cell.font = Font(color="FFFFFF", bold=True, size=11)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.font = Font(name="Calibri", size=11)
                if cell.row % 2 == 0:
                    cell.fill = PatternFill("solid", fgColor="EEF4F8")
            maxlines = max(
                math.ceil(
                    len(str(c.value or "")) / ((widths or [30] * len(headers))[i] * 0.9)
                )
                for i, c in enumerate(row)
            )
            ws.row_dimensions[row[0].row].height = min(390, max(42, maxlines * 15))
        for i in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(i)].width = (
                widths or [30] * len(headers)
            )[i - 1]
        ws.row_dimensions[1].height = 32
        ws.sheet_view.zoomScale = 85
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A3
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_title_rows = "1:1"
        ws.print_options.horizontalCentered = True
        ws.oddFooter.center.text = "Grupo 1 · Página &P de &N"
        return ws

    sheet(
        "01 Requisitos funcionales",
        [
            "ID",
            "Nombre",
            "Descripción concreta",
            "Criterio de aceptación",
            "HU",
            "Casos",
        ],
        RF,
        [12, 28, 65, 75, 22, 28],
    )
    sheet(
        "02 Requisitos no funcionales",
        ["ID", "Atributo", "Qué se mide/controla", "Métrica y límites", "HU", "Casos"],
        RNF,
        [13, 28, 65, 75, 22, 28],
    )
    sheet(
        "03 Identificación riesgos",
        [
            "ID",
            "Riesgo",
            "Causa y consecuencia",
            "Probabilidad (1–3)",
            "Impacto (1–3)",
            "P×I",
            "Nivel",
            "Responsable",
        ],
        [
            (
                i,
                n,
                d,
                p,
                im,
                p * im,
                "Alto" if p * im >= 6 else "Medio" if p * im >= 3 else "Bajo",
                who,
            )
            for i, n, d, p, im, who, mit, e in RISKS
        ],
        [12, 35, 68, 20, 20, 12, 15, 26],
    )
    matrix = [
        (
            "Probabilidad 1",
            "Exposición baja a la causa en el entorno local; estimación del equipo.",
        ),
        (
            "Probabilidad 2",
            "La causa puede ocurrir durante integración o uso de servicios externos.",
        ),
        (
            "Probabilidad 3",
            "Causa recurrente o inherente al uso de IA y cambio de alcance.",
        ),
        ("Impacto 1", "Afectación menor; no bloquea una función principal."),
        ("Impacto 2", "Afectación parcial; exige corrección o repetir una prueba."),
        (
            "Impacto 3",
            "Bloquea función principal, compromete datos o invalida evidencia.",
        ),
        (
            "Nivel",
            "P×I: 1–2 Bajo; 3–4 Medio; 6–9 Alto. Estimación ordinal, no probabilidad estadística.",
        ),
    ]
    matrix += [
        (
            f"P={p}, I={im}",
            ", ".join(r[0] for r in RISKS if r[3] == p and r[4] == im)
            or "Sin riesgos asignados",
        )
        for p in (3, 2, 1)
        for im in (1, 2, 3)
    ]
    sheet(
        "04 Matrices riesgos",
        ["Criterio / celda", "Definición / riesgos"],
        matrix,
        [35, 110],
    )
    sheet(
        "05 Mitigación riesgos",
        ["ID", "Riesgo", "Responsable", "Control y alcance real", "Verificación"],
        [(r[0], r[1], r[5], r[6], r[7]) for r in RISKS],
        [12, 35, 25, 95, 48],
    )
    sheet(
        "06 Plan de pruebas",
        [
            "ID CP",
            "HU",
            "Objetivo",
            "Tipo de prueba",
            "Precondiciones",
            "Datos de entrada",
            "Pasos",
            "Resultado esperado",
        ],
        [(*c[:3], CASE_TEST_TYPES[c[0]], *c[4:8]) for c in CASES],
        [12, 20, 30, 28, 45, 50, 65, 65],
    )
    sheet(
        "07 Historias de usuario",
        [
            "ID",
            "Rol",
            "Nombre",
            "Historia y beneficio",
            "Prioridad",
            "Requisitos",
            "Criterios verificables",
        ],
        HU,
        [12, 30, 30, 65, 15, 40, 80],
    )
    sheet(
        "08 Ejecución",
        [
            "ID CP",
            "Esperado",
            "Obtenido",
            "Estado",
            "Fecha UTC",
            "Evidencia (carpeta evidencias)",
        ],
        [
            (c[0], c[7], r["observed"], r["status"], r["date"], r["evidence"])
            for c, r in zip(CASES, RESULTS)
        ],
        [12, 65, 100, 18, 16, 45],
    )
    trace = []
    for row in RF + RNF:
        ids = row[5].split(", ")
        states = [r["status"] for r in RESULTS if r["id"] in ids]
        state = (
            "FALLÓ"
            if "FALLÓ" in states
            else "PENDIENTE"
            if "PENDIENTE" in states
            else "APROBADO"
        )
        trace.append((row[0], row[1], row[4], row[5], state))
    sheet(
        "09 Trazabilidad",
        ["Requisito", "Función / atributo", "HU", "Casos", "Estado agregado"],
        trace,
        [15, 40, 28, 45, 23],
    )
    sheet(
        "10 Defectos",
        [
            "ID",
            "Severidad",
            "Problema",
            "Pasos de reproducción",
            "Esperado",
            "Obtenido inicial",
            "Corrección",
            "Estado",
            "Reprueba / evidencia",
        ],
        [
            (
                d.get(k, "")
                for k in [
                    "id",
                    "severity",
                    "title",
                    "steps",
                    "expected",
                    "actual",
                    "fix",
                    "status",
                    "retest",
                ]
            )
            for d in DEFECTS
        ],
        [12, 17, 40, 60, 55, 65, 65, 20, 70],
    )
    metrics = [
        (
            "Rendimiento",
            "Usuarios virtuales",
            LOAD.get("configuration", {}).get("virtual_users", "Pendiente"),
            "10 sesiones independientes",
        ),
        (
            "Rendimiento",
            "Solicitudes medidas",
            LOAD.get("summary", {}).get("requests", "Pendiente"),
            "100; calentamiento excluido",
        ),
        (
            "Rendimiento",
            "p95 segundos",
            LOAD.get("summary", {}).get("p95_seconds", "Pendiente"),
            "≤10 s",
        ),
        (
            "Rendimiento",
            "Throughput req/s",
            LOAD.get("summary", {}).get("throughput_requests_per_second", "Pendiente"),
            "Descriptivo; incluye resets entre rondas",
        ),
        (
            "Rendimiento",
            "Errores %",
            LOAD.get("summary", {}).get("error_percent", "Pendiente"),
            "0%",
        ),
        (
            "Rendimiento",
            "Exitosas en ≤10s (%)",
            LOAD.get("summary", {}).get("successful_within_10_percent", "Pendiente"),
            "≥95%",
        ),
        (
            "Disponibilidad",
            "Muestras HTTP exitosas (%)",
            LOAD.get("availability", {}).get("percent", "Pendiente"),
            "≥95% en ventana de carga",
        ),
        (
            "IA",
            "Positivas correctas",
            f"{IA.get('summary', {}).get('positive_passed', '?')}/36",
            "≥33/36",
        ),
        (
            "IA",
            "Abstenciones",
            f"{IA.get('summary', {}).get('negative_passed', '?')}/5",
            "5/5",
        ),
    ]
    metrics = [("Referencia inicial" if row[0] in ("Rendimiento", "Disponibilidad") else row[0], *row[1:]) for row in metrics]
    for stage in CAPACITY.get("stages", []):
        if stage["stage"].startswith("baseline"):
            continue
        metrics.extend([
            (stage["stage"], "Cuentas distintas / solicitudes medidas", f"{stage['users']} / {stage.get('requests', 0)}", "Campaña nueva: identidades distintas; perfiles de matrícula basados en dos grupos."),
            (stage["stage"], "Duración medida (s)", stage.get("elapsed_seconds", "No iniciada"), "Login y calentamiento excluidos; pausas y reinicios incluidos en throughput."),
            (stage["stage"], "Correctas en ≤10 s (%)", stage.get("successful_within_10_percent", "No medida"), "Meta nominal ≥95%; controles mínimos de respuesta y permisos."),
            (stage["stage"], "p95 / p99 (s)", f"{stage.get('p95_seconds', '—')} / {stage.get('p99_seconds', '—')}", "Todas las solicitudes medidas, incluidos errores y extremos."),
            (stage["stage"], "Errores medidos / calentamiento", f"{stage.get('errors', 0)} / {stage.get('warmup_errors', 0)}", "Un calentamiento fallido no se convierte en etapa aprobada."),
            (stage["stage"], "Completa / cumple", f"{flag(stage['complete'])} / {flag(stage['accepted'])}", "Evidencia: rendimiento-ampliado/" + stage["file"] + "; parada: " + str(stage.get("stop_reason") or "finalización prevista")),
        ])
    sheet(
        "11 Rendimiento e IA",
        ["Grupo", "Métrica", "Resultado real", "Criterio / interpretación"],
        metrics,
        [23, 40, 25, 80],
    )
    sheet(
        "12 Rúbrica",
        ["Criterio", "Máximo", "Excelente (literal)", "Evidencia", "Estado / límite"],
        RUBRIC,
        [38, 12, 95, 75, 45],
    )
    sheet(
        "13 Cambios y términos",
        ["Elemento", "Definición / cambio"],
        CHANGES + TERMS,
        [32, 120],
    )
    from openpyxl.comments import Comment
    plan = wb["06 Plan de pruebas"]
    plan["D1"].comment = Comment("Clasificación por finalidad principal. Valores: Unitarias, Integración, Funcionales, Exploratorias, Rendimiento y Seguridad. No hay planes exploratorios acreditados entre estos 36 registros.", "Grupo 1")
    plan["D16"].comment = Comment("CP-015 ejecuta una regresión de suites mixtas: contiene comprobaciones unitarias y de integración. Se registra Integración como categoría principal; no significa que toda la suite sea de ese nivel.", "Grupo 1")
    plan["D36"].comment = Comment("CP-035 verifica el funcionamiento y la reproducibilidad del entregable documental. Se agrupa en Funcionales dentro de las seis categorías solicitadas; no es un recorrido funcional del chat.", "Grupo 1")
    wb.save(OUT / "Tablas del informe - corregidas.xlsx")


CHANGES = [
    (
        "Arquitectura",
        "Bedrock/IAM/CloudWatch se sustituyen en la descripción del despliegue actual por DeepSeek, Gemini, FastAPI, PostgreSQL y autorización Moodle.",
    ),
    (
        "Tiempo",
        "CP-011 deja de exigir 5 s al RAG. RNF-01 mide el chat completo: ≥95% exitosas en ≤10 s bajo la carga especificada.",
    ),
    (
        "Calidad",
        "Se unifican RNF-06, HU-02 y R02 en ≥90% positivas; se modifica el evaluador y se prueba el límite de aceptación.",
    ),
    (
        "Sesión",
        "Se reemplaza historial ambiguo por contexto temporal de la sesión. No se ofrece historial persistente.",
    ),
    (
        "Transporte",
        "Se sustituye HTTPS interno como obligación de despliegue público por HTTP local restringido y firma; HTTPS se conserva hacia proveedores externos. La firma no cifra tráfico.",
    ),
    (
        "Documentos",
        "PDF con texto extraíble. No se promete Word, OCR ni backups S3 diarios; límites configurables con valores predeterminados comprobables.",
    ),
    (
        "Plan de pruebas",
        "Se conservan CP-001…015 y se amplía a CP-036 con datos, pasos, esperado, técnica, estado y evidencia.",
    ),
    (
        "Funciones actuales",
        "Se agregan HU-08…10 y RF-12…14 para datos académicos, navegación y planificación.",
    ),
    (
        "Disponibilidad",
        "95% se refiere a muestras HTTP durante una ventana acotada, no a un SLA mensual.",
    ),
]
TERMS = [
    (
        "API REST y JSON",
        "Interfaz por HTTP entre programas. JSON es el formato de campos y valores intercambiados; el contrato define cuáles se aceptan.",
    ),
    (
        "Aserción firmada",
        "Mensaje generado por Moodle que vincula identidad, permisos y cuerpo de la solicitud, con vencimiento. La firma detecta alteración; no cifra el contenido.",
    ),
    (
        "Reprueba",
        "Nueva ejecución del caso que detectó un defecto, después de corregirlo, conservando el resultado anterior para comparación.",
    ),
    (
        "Arnés de pruebas",
        "Script que prepara entradas, ejecuta el flujo y compara resultados con expectativas explícitas, guardando la evidencia.",
    ),
    (
        "RAG",
        "Recuperación aumentada: buscar fragmentos permitidos y usarlos como evidencia para responder una pregunta documental.",
    ),
    (
        "Embedding",
        "Representación numérica del texto para comparar significado; una coincidencia vectorial no demuestra que una respuesta sea verdadera.",
    ),
    (
        "Fragmento",
        "Porción de texto de un documento que conserva su ubicación de página y posición.",
    ),
    (
        "Consulta documental",
        "Pregunta sustentada en documentos accesibles; incluye fuente o indica falta de evidencia.",
    ),
    (
        "Consulta académica",
        "Pregunta sobre registros visibles de Moodle, como tareas o notas; la autorización se calcula para la persona.",
    ),
    (
        "Capacidad efectiva",
        "Permiso que Moodle calcula para una persona en un contexto concreto; el nombre del rol escrito en el chat no lo modifica.",
    ),
    (
        "Contexto de sesión",
        "Mensajes y referencias temporales para interpretar seguimientos; se eliminan al reiniciar, cerrar o expirar la sesión.",
    ),
    (
        "p95",
        "Ordenar todas las duraciones y tomar la posición techo(0,95×N). Se acompaña con porcentaje de respuestas exitosas en ≤10 s.",
    ),
    (
        "Throughput",
        "Solicitudes completadas divididas por los segundos reales de la fase medida; aquí incluye los reinicios de conversación entre rondas.",
    ),
    (
        "Usuario virtual",
        "Contexto de navegador con cookies independientes. Diez sesiones reutilizan dos cuentas; no representa diez personas distintas.",
    ),
    (
        "Acierto documental",
        "Respuesta que contiene los hechos esperados y cita el documento correcto. Se conserva revisión de discrepancias semánticas.",
    ),
]


def make_doc():
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(2)
    sec.bottom_margin = Cm(2)
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)
    sec.page_height = Cm(29.7)
    sec.page_width = Cm(21)
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)
    style.paragraph_format.space_after = Pt(6)
    for name in ["Heading 1", "Heading 2", "Heading 3"]:
        doc.styles[name].font.color.rgb = RGBColor.from_string(BLUE)
    footer = sec.footer.paragraphs[0]
    footer.alignment = 2
    footer.add_run("Grupo 1 · Pruebas de Software | ")
    f = OxmlElement("w:fldSimple")
    f.set(qn("w:instr"), "PAGE")
    footer._p.append(f)

    def p(text="", style=None):
        return doc.add_paragraph(str(text), style)

    def h(text, level=1):
        return doc.add_heading(text, level)

    def table(headers, rows, widths=None):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Light Shading Accent 1"
        t.autofit = False
        for c, v in zip(t.rows[0].cells, headers):
            c.text = str(v)
        repeat = OxmlElement("w:tblHeader")
        t.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in rows:
            cells = t.add_row().cells
            for cell, v in zip(cells, row):
                cell.text = str(v)
        for row in t.rows:
            # Keep rows together, while allowing long tables to continue with headers.
            prop = OxmlElement("w:cantSplit")
            row._tr.get_or_add_trPr().append(prop)
            for j, c in enumerate(row.cells):
                if widths:
                    c.width = Cm(widths[j])
                for par in c.paragraphs:
                    par.paragraph_format.space_after = Pt(3)
                    for run in par.runs:
                        run.font.size = Pt(9)
        if widths:
            for col, w in zip(t.columns, widths):
                col.width = Cm(w)
        p()
        return t

    def pic(name, caption, width=6.2):
        path = ASSETS / name
        if path.exists():
            doc.add_picture(str(path), width=Inches(width))
            doc.paragraphs[-1].paragraph_format.keep_with_next = True
            p(caption, "Caption")

    logo = ASSETS / "logo-original.png"
    if logo.exists():
        doc.add_picture(str(logo), width=Inches(3.8))
    p("Facultad de Ingeniería")
    h(
        "Desarrollo de un Gestor Académico Virtual basado en IA Generativa para consultas de información en una app universitaria",
        0,
    )
    p("Avance de Proyecto Final I · versión corregida y validación final")
    p("Pruebas de Software (32852) · Grupo 1")
    p("DOCENTE\nChristian Janderson Quiroz Angulo")
    members = [
        "Diego Fernando Napa Alvarez (U22234939)",
        "Lorena Kim Negrillo (U22229186)",
        "Pablo Adrian Boza Torres (U22239512)",
        "José Daniel Medina García (U22232430)",
        "Percy Alonzo Chabria Loayza (U20217294)",
        "Jacknylls Ederly Flores Mamani (U20306493)",
    ]
    p("INTEGRANTES\n" + "\n".join(members))
    p("Lima, Perú — 2026")
    p(
        "Conserva el cronograma del informe presentado. Las fechas de evidencias corresponden a su ejecución y no modifican la entrega académica."
    )
    doc.add_page_break()
    h("Contenido")
    # LibreOffice updates this field when exporting; a text list also remains usable in readers.
    toc = OxmlElement("w:fldSimple")
    toc.set(qn("w:instr"), 'TOC \\o "1-2" \\h \\z \\u')
    doc.add_paragraph()._p.append(toc)
    for name in [
        "1. Introducción",
        "2. Planificación",
        "3. Análisis y requisitos",
        "4. Diseño actualizado",
        "5. Estrategia y ejecución de pruebas",
        "6. Rendimiento y calidad de IA",
        "7. Gestión de defectos",
        "8. Cumplimiento de la rúbrica",
        "9. Conclusiones y limitaciones",
        "10. Referencias",
        "Anexo A. Casos de prueba",
        "Anexo B. Reproducción y evidencias",
    ]:
        p(name)
    doc.add_page_break()
    h("1. Introducción")
    h("1.1 Contexto y problema", 2)
    p(
        "Estudiantes y docentes consultan información distribuida entre documentos institucionales y pantallas de Moodle. Localizar una norma, identificar una tarea pendiente o abrir el informe correcto requiere conocer la ubicación de cada recurso. El problema abordado es facilitar ese acceso sin omitir la procedencia de los datos ni los permisos de la persona."
    )
    h("1.2 Solución y objetivo general", 2)
    p(
        "El proyecto implementa y valida un asistente integrado en Moodle para consultar información universitaria en lenguaje natural. Moodle autentica y autoriza; un servicio RAG independiente interpreta solicitudes y recupera evidencia documental. DeepSeek atiende la interpretación y generación; Gemini calcula embeddings. Las consultas de notas y tareas se respaldan en los registros autorizados de Moodle."
    )
    p(
        "Objetivo general: comprobar que el asistente responde y orienta dentro de su alcance, con fuentes verificables, permisos efectivos y resultados medidos mediante pruebas reproducibles."
    )
    h("1.3 Objetivos específicos", 2)
    for x in [
        "Procesar PDF con texto extraíble, mantener versiones y filtrar documentos según acceso.",
        "Integrar el chat con una API validada y solicitudes firmadas.",
        "Verificar consultas académicas, navegación, sesión y planificación semanal.",
        "Medir exactitud documental, latencia bajo diez sesiones concurrentes y disponibilidad observada.",
        "Registrar defectos y repruebas, manteniendo trazabilidad desde requisitos hasta evidencias.",
    ]:
        p(x, "List Bullet")
    h("1.4 Antecedentes", 2)
    p(
        "Khan, Khan y Ali (2025) presentan un asistente universitario con modelos de lenguaje y recuperación documental para consultas de admisión, cursos e instalaciones. Este antecedente motiva el acceso mediante preguntas, pero sus resultados no sustituyen la evaluación de este proyecto [1]."
    )
    p(
        "Kuratomi et al. (2025) evalúan un asistente para la Universidad de São Paulo y muestran la importancia de recuperar el contexto correcto. El trabajo también identifica limitaciones de recuperación y generación; por eso aquí se comprueban hechos y fuentes por separado [2]."
    )
    p(
        "Németh et al. (2025) estudian un tutor con RAG en cuatro cursos de educación superior. Su contexto de tutoría difiere del presente asistente, que consulta información y organiza pendientes sin resolver ejercicios de asignatura [3]."
    )
    h("1.5 Alcance y entorno", 2)
    p(
        "La entrega corresponde a una instalación local de pruebas con datos preparados para la evaluación. Incluye documentos institucionales comunes y de curso; cursos, docentes, tareas, notas y calendario autorizados; enlaces nativos y planes semanales. No implica acceso a un campus de producción ni validación de políticas de una institución real."
    )
    p(
        "El chat consulta y orienta. Entregar tareas, calificar o modificar cursos exige usar las pantallas nativas de Moodle. Pagos personales, analítica agregada, tutoría de asignaturas e historial persistente quedan fuera del alcance. Los servicios de IA requieren internet aunque Moodle y las bases se ejecuten localmente."
    )
    p(
        "La ruta local /api/v1/demo/chat/query se habilita exclusivamente para evaluar el corpus institucional y no exige la firma de integración. No recibe el contexto académico personal de Moodle. Se diferencia de /api/v1/chat, cuyos endpoints protegidos validan identidad, firma y permisos. La exposición continúa restringida a localhost; el modo de evaluación debe deshabilitarse al cambiar ese alcance."
    )
    h("2. Planificación")
    h("2.1 Roles asignados", 2)
    original = Document(
        ROOT / "informe y rúbrica/APF1 - Pruebas de Software - Grupo 1.docx"
    )
    roles = [[c.text for c in row.cells] for row in original.tables[0].rows]
    table(roles[0], roles[1:], [3, 4, 9.5])
    p(
        "Se conserva la asignación del informe original. Esta tabla describe responsabilidades; no atribuye a cada integrante ejecuciones que no estén registradas."
    )
    h("2.2 Stack tecnológico del entorno evaluado", 2)
    table(
        ["Componente", "Tecnología y responsabilidad"],
        [
            (
                "Interfaz / permisos",
                "Moodle 5.3dev, plugin local_acadassistant y PHP; sesiones, autorización y enlaces nativos.",
            ),
            ("Servicio RAG", "Python y FastAPI; contratos, recuperación y respuestas."),
            (
                "IA de conversación",
                "DeepSeek deepseek-flash; interpretación y generación documental.",
            ),
            ("Embeddings", "Gemini gemini-embedding-001, 768 dimensiones."),
            (
                "Persistencia",
                "PostgreSQL para Moodle; PostgreSQL con pgvector para documentos y vectores.",
            ),
            (
                "Operación",
                "Docker Compose en localhost; configuración sensible fuera del control de versiones.",
            ),
            (
                "Pruebas",
                "pytest, PHPUnit y Playwright; carga escrita en Python contra Chromium real.",
            ),
        ],
        [4.2, 12.3],
    )
    h("2.3 Cronograma y metodología", 2)
    p(
        "Se conserva la planificación Scrum del APF1: seis sprints de dos semanas, desde la semana 7 hasta la 18. La planificación no constituye evidencia de que se realizaron ceremonias o que todos los objetivos se alcanzaron en la fecha prevista."
    )
    table(
        ["Sprint", "Semanas del cronograma original"],
        [(str(i), f"{5 + 2 * i}–{6 + 2 * i}") for i in range(1, 7)],
        [4, 12.5],
    )
    p(
        "El plan de pruebas original inicia el 17/09/2026. La validación incorporada en esta versión conserva su propia fecha UTC en cada reporte, diferenciada del cronograma académico."
    )
    h("3. Análisis y requisitos")
    h("3.1 Lenguaje utilizado", 2)
    table(["Término", "Significado concreto"], TERMS, [3.7, 12.8])
    h("3.2 Requisitos funcionales", 2)
    for r in RF:
        table(
            ["ID y función", "Descripción y criterio verificable"],
            [
                (
                    r[0] + " · " + r[1],
                    r[2]
                    + "\nAceptación: "
                    + r[3]
                    + "\nTrazabilidad: "
                    + r[4]
                    + " → "
                    + r[5],
                )
            ],
            [4, 12.5],
        )
    h("3.3 Requisitos no funcionales", 2)
    for r in RNF:
        table(
            ["ID y atributo", "Medición y aceptación"],
            [
                (
                    r[0] + " · " + r[1],
                    r[2]
                    + "\nCriterio: "
                    + r[3]
                    + "\nTrazabilidad: "
                    + r[4]
                    + " → "
                    + r[5],
                )
            ],
            [4, 12.5],
        )
    h("3.4 Historias de usuario", 2)
    for r in HU:
        h(r[0] + " · " + r[2], 3)
        table(
            ["Campo", "Definición"],
            [
                ("Rol / prioridad", r[1] + " / " + r[4]),
                (
                    "Historia",
                    "Como " + r[1].lower() + ", " + r[3][0].lower() + r[3][1:],
                ),
                ("Criterios de aceptación", r[6]),
                ("Requisitos", r[5]),
                ("Casos", ", ".join(c[0] for c in CASES if r[0] in c[1])),
            ],
            [3.7, 12.8],
        )
    h("3.5 Riesgos y mitigaciones", 2)
    p(
        "Se utiliza P×I con escala ordinal de 1 a 3. Probabilidad: baja exposición (1), posible durante pruebas (2), causa recurrente o inherente (3). Impacto: afectación menor (1), funcionalidad parcial (2), bloqueo principal o compromiso de datos (3). Nivel: Bajo 1–2, Medio 3–4, Alto 6–9. No son probabilidades estadísticas."
    )
    table(
        ["ID / nivel", "Riesgo y consecuencia", "Control / verificación"],
        [
            (
                r[0] + f" · {r[3]}×{r[4]}={r[3] * r[4]}",
                r[1] + ": " + r[2],
                r[6] + "\nResponsable: " + r[5] + "\nEvidencia: " + r[7],
            )
            for r in RISKS
        ],
        [2.2, 5.4, 8.9],
    )
    table(
        ["P \\ I", "Bajo (1)", "Medio (2)", "Alto (3)"],
        [
            (
                str(pv),
                *[
                    ", ".join(r[0] for r in RISKS if r[3] == pv and r[4] == iv) or "—"
                    for iv in (1, 2, 3)
                ],
            )
            for pv in (3, 2, 1)
        ],
        [2.5, 4.6, 4.7, 4.7],
    )
    h("4. Diseño actualizado")
    p(
        "Los diagramas representan responsabilidades y relaciones presentes en el código. Reemplazan diseños basados en servicios que ya no integran el despliegue evaluado."
    )
    for name, caption in [
        (
            "clases.png",
            "Clases principales; se omiten adaptadores secundarios para legibilidad.",
        ),
        (
            "entidades.png",
            "Relaciones documentales según migraciones 001–004; las tablas nativas de Moodle permanecen separadas.",
        ),
        (
            "despliegue.png",
            "Servicios locales y llamadas externas; permisos calculados por Moodle.",
        ),
        (
            "secuencia-exitosa.png",
            "Flujo simplificado de consulta documental con autorización.",
        ),
        (
            "secuencia-sin-evidencia.png",
            "Flujo alterno: abstención sin información suficiente.",
        ),
        (
            "secuencia-error.png",
            "Flujo alterno: fallo controlado y posibilidad de reintento.",
        ),
    ]:
        pic(name, caption)
    h("4.1 Interfaz implementada", 2)
    for name in ["documental", "courses", "weekly"]:
        shot = EV / f"{name}.png"
        if shot.exists():
            doc.add_picture(str(shot), width=Inches(6.2))
            p("Captura de la ejecución real: " + name + ".", "Caption")
    h("5. Estrategia y ejecución de pruebas")
    p(
        "La estrategia combina pruebas unitarias y de contrato con proveedores simulados, integración con bases aisladas, interfaz controlada y recorridos con proveedores reales. No se confunden las respuestas interceptadas del test de interfaz con validación de IA."
    )
    p(
        "Criterios de entrada: servicios locales accesibles, corpus preparado, cuentas de prueba, claves configuradas en servidor y pruebas sin datos de producción. Criterios de salida: casos trazados, resultados y defectos conservados; los fallos no se convierten en aprobación por estar documentados."
    )
    p(
        "Técnicas: particiones válidas e inválidas, valores límite, transición de estados, control de permisos, inyección de fallos, regresión y carga. Los 36 casos completos se encuentran en el Anexo A y en el Excel editable."
    )
    table(
        ["Ejecución", "Resultado registrado", "Evidencia"],
        [
            (
                "Python",
                f"{len(PYTEST)} pruebas; "
                + (
                    "sin fallos ni omisiones"
                    if tests_ok(PYTEST)
                    else "revisar fallos/omisiones"
                ),
                "pytest.xml / pytest.log",
            ),
            (
                "Plugin Moodle",
                f"{len(PHPUNIT)} pruebas; "
                + (
                    "sin fallos ni omisiones"
                    if tests_ok(PHPUNIT)
                    else "revisar resultados"
                ),
                "phpunit.xml / phpunit.log",
            ),
            ("Funcional con IA", str(FUNC.get("summary", {})), "funcionales.json"),
            (
                "Navegación",
                f"Completo: {NAV.get('complete', False)}; {len(NAV.get('cases', []))} consultas",
                "navegacion.json",
            ),
            ("Interfaz", "Escritorio y móvil; respuestas controladas", "interfaz.json"),
        ],
        [3.5, 7.5, 5.5],
    )
    h("5.1 Tipos de pruebas aplicados", 2)
    p("Se aplicaron pruebas unitarias, de integración, funcionales, de rendimiento y de seguridad. A continuación se explica para qué se utilizó cada tipo, cómo se ejecutó y qué resultados produjo. Los resultados corresponden a las ejecuciones conservadas del 29/10/2026.")
    p("Las 295 pruebas Python y las 53 del plugin Moodle son totales por herramienta. Los subtotales descritos a continuación identifican verificaciones concretas; no deben sumarse entre tipos porque algunas comprobaciones de seguridad también verifican la integración o el funcionamiento del chat.")
    applied = [row for row in inventory(PYTEST, FUNC, LOAD) if row[0] != "Exploratorias"]
    for index, row in enumerate(applied, 1):
        name, definition, available, result, evidence, limits = row
        label = ("de " if name in ("Integración", "Rendimiento", "Seguridad") else "") + name.lower()
        h(f"5.1.{index} Pruebas {label}", 3)
        p(definition)
        application = APPLICATION[name]
        if name == "Rendimiento" and CAPACITY.get("stages"):
            application = [
                ("Método", "Se midió el chat real con Chromium y, por separado, el controlador HTTP autenticado de Moodle. Ambos atraviesan los proveedores reales; el canal HTTP no incluye renderizado y no se equipara a la experiencia completa del navegador."),
                ("Identidades", "Se prepararon cien cuentas distintas de estudiante a partir de dos perfiles de matrícula. Cada etapa indica cuántas cuentas se abrieron y cuántas consultas se midieron; preparar una cuenta no demuestra capacidad concurrente para atenderla."),
                ("Escenarios", "Se ejecutó una referencia de diez cuentas, se aumentó la concurrencia hasta encontrar un incumplimiento, se retiró carga para observar recuperación y se añadió una fase sostenida. La fase sostenida falló por cuota del proveedor; el pico no superó el calentamiento. La mezcla ampliada y la calibración HTTP documental fallaron en calentamiento; la carga HTTP alta quedó pendiente. Ver estados por etapa en la sección 6.3."),
                ("Validación de respuesta", "No basta recibir texto: se comprueban hechos mínimos, matrícula permitida, fuente o destino según la pregunta. Las respuestas incorrectas y los errores permanecen en el denominador."),
                ("Criterio", "La referencia es ≥95% de solicitudes correctas en ≤10 s, cero errores y ejecución completa. El nivel que incumple sirve para caracterizar el límite, no se presenta como aprobado."),
                ("Duración y recursos", "Las etapas completas de concurrencia y recuperación duraron al menos cinco minutos. La sostenida tenía objetivo de quince minutos, pero se detuvo tras 161,485 s por errores del proveedor; no acreditó esa duración. Se registran CPU, RAM, swap y contenedores en el equipo compartido con Chromium. No equivale a operación continua de producción."),
            ]
            result = "; ".join(f"{r['stage']}: {r.get('requests', 0)} consultas, {r.get('successful_within_10_percent', '—')}% correctas ≤10 s, cumple={flag(r['accepted'])}" for r in CAPACITY["stages"] if not r["stage"].startswith("baseline"))
            evidence = "rendimiento-ampliado/resumen.json, resultados.md y JSON de cada etapa."
            limits = "La referencia histórica se conserva en carga.json. Los resultados nuevos corresponden al hardware, mezcla y duración indicados; no son una capacidad garantizada del campus. HTTP y navegador se interpretan por separado."
        for aspect, description in application:
            paragraph = doc.add_paragraph()
            paragraph.add_run(aspect + ". ").bold = True
            paragraph.add_run(description)
        p("Resultado obtenido: " + result)
        p("Evidencia: " + evidence)
        p("Alcance del resultado: " + limits)
    h("5.2 Estado de las pruebas exploratorias", 2)
    p("No se dispone de evidencia de una sesión formal de pruebas exploratorias; por ello no se presentan como un tipo aplicado. Sí se registró investigación de defectos de horarios, navegación y conexiones, seguida de correcciones y repruebas. Esos registros acreditan diagnóstico, pero no sustituyen una bitácora exploratoria con objetivo, duración, recorrido y observaciones.")
    p("El catálogo de casos de prueba y sus resultados se conserva por separado en el Anexo A. La descripción de tipos de esta sección no utiliza identificadores de casos ni historias de usuario.")
    h("6. Rendimiento y calidad de IA")
    h("6.1 Carga inicial de referencia: escenario y reproducibilidad", 2)
    p(
        "Diez usuarios virtuales usan contextos de Chromium con cookies independientes. Se reutilizan dos cuentas de estudiante para reproducir sus permisos, sin afirmar diez personas diferentes. Cada ronda envía diez consultas simultáneas. Diez rondas producen cien solicitudes medidas, después de diez consultas de calentamiento. La mezcla equilibrada contiene nota mínima, cursos, docentes, bienestar y calendario."
    )
    p(
        "El cronómetro empieza al pulsar enviar y termina al aparecer una respuesta nueva. Incluye navegador, Moodle, API, bases y proveedores. Se excluyen login y calentamiento; el throughput incluye los reinicios entre rondas. No hay reintentos del arnés; los adaptadores conservan sus reintentos configurados. Errores, respuestas lentas y valores extremos se mantienen en el denominador."
    )
    p(
        "El escenario prueba el umbral acordado, no carga sostenida de producción ni el máximo de usuarios del sistema. Dos consultas por cada tipo en cada ronda impiden que una mezcla de saludos triviales o respuestas locales oculte el costo documental."
    )
    s = LOAD.get("summary", {})
    av = LOAD.get("availability", {})
    table(
        ["Métrica", "Resultado", "Criterio"],
        [
            ("Solicitudes", s.get("requests", "Pendiente"), "100 medidas"),
            (
                "p95 (s)",
                s.get("p95_seconds", "Pendiente"),
                "≤10 s, con éxito requerido",
            ),
            ("Mediana (s)", s.get("median_seconds", "Pendiente"), "Descriptiva"),
            ("Máximo (s)", s.get("maximum_seconds", "Pendiente"), "Conservar extremos"),
            (
                "Throughput (req/s)",
                s.get("throughput_requests_per_second", "Pendiente"),
                "Descriptivo",
            ),
            (
                "Errores",
                str(s.get("errors", "?")) + " / " + str(s.get("requests", "?")),
                "0",
            ),
            (
                "Éxito en ≤10 s (%)",
                s.get("successful_within_10_percent", "Pendiente"),
                "≥95%",
            ),
            (
                "Duración medida (s)",
                s.get("elapsed_seconds", "Pendiente"),
                "Ventana explícita",
            ),
            (
                "Disponibilidad HTTP (%)",
                av.get("percent", "Pendiente"),
                "≥95% muestras; " + str(av.get("samples", 0)) + " muestras",
            ),
        ],
        [5, 5.5, 6],
    )
    if LOAD.get("complete"):
        p(
            "Resultado del objetivo de carga: "
            + (
                "CUMPLIDO en esta ejecución."
                if s.get("accepted")
                else "NO CUMPLIDO en esta ejecución. No se modifica el umbral para acomodar el resultado."
            )
        )
        p(
            f"El p95 de {s.get('p95_seconds')} s resume la cola de latencias; el máximo de {s.get('maximum_seconds')} s muestra la variabilidad. El throughput de {s.get('throughput_requests_per_second')} req/s corresponde a este arnés cerrado y a su mezcla. No se extrapola a concurrencias superiores ni a una tasa de llegada constante."
        )
    baseline = read("carga-inicial.json").get("summary", {})
    if baseline:
        h("6.1.1 Diagnóstico y comparación con la línea base", 3)
        p(
            f"Antes de la corrección: {baseline.get('successful_within_10_percent')}% en ≤10 s, p95 {baseline.get('p95_seconds')} s y {baseline.get('errors')} errores. La línea base se conserva íntegra en carga-inicial.json; la configuración, mezcla y tamaño de muestra se mantienen en la reprueba."
        )
        p(
            "El perfil por etapas localizó una conexión TCP de 19,7116 s dentro de una llamada DeepSeek de 21,9073 s. Se sustituyó la apertura de una conexión por llamada por un cliente HTTPX con hasta 20 conexiones persistentes y límite de establecimiento de 3 s. Se conserva el tiempo de lectura configurado y los reintentos acotados. No se almacenan respuestas ni decisiones de permisos en caché."
        )
        p(
            "La prueba de transporte verifica sobre un servidor HTTP local que dos llamadas reutilizan el mismo puerto TCP y que la credencial de la primera no se agrega a la segunda. La reprueba de carga utiliza el flujo real completo; la comparación está sujeta a la variabilidad externa del proveedor."
        )
    pic("carga.png", "Todas las solicitudes medidas; línea roja = umbral acordado.")
    pic("distribucion.png", "Distribución de latencias sin descartar extremos.")
    h("6.2 Exactitud documental y escenarios de IA", 2)
    si = IA.get("summary", {})
    p(
        f"Se ejecutaron 36 consultas con respuesta esperada y cinco sin cobertura. Resultado: {si.get('positive_passed', '?')}/36 positivas y {si.get('negative_passed', '?')}/5 abstenciones. El mínimo aprobado es 33 positivas y cinco abstenciones. El evaluador exige hechos esperados y clave documental; no es una evaluación humana independiente."
    )
    p(
        "Las preguntas ambiguas, con premisa errónea y fuera del ámbito se evalúan además en el chat real. El caso de premisa errónea pregunta si la nota mínima es 20; debe corregirse a 11 con fuente. La referencia «¿Y esa?» sin antecedente debe pedir precisión. Una receta no debe obtener una respuesta culinaria."
    )
    p(
        f"Latencia secuencial del endpoint documental: mediana {si.get('median_seconds', '?')} s; p95 {si.get('p95_seconds', '?')} s. No equivale a p95 del chat bajo carga. El conjunto completo y las respuestas están en evaluacion-ia.json."
    )
    if CAPACITY.get("stages"):
        h("6.3 Campaña ampliada: cuentas distintas y verificación de respuestas", 2)
        p("La nueva campaña conserva la ejecución inicial como referencia y mide de nuevo el chat completo con identidades locales distintas. Se prepararon cien cuentas de estudiante basadas en dos perfiles de matrícula; la cantidad preparada no equivale a la cantidad concurrente medida. Las etapas ejecutadas y sus resultados se presentan abajo, incluidos fallos y etapas incompletas.")
        p("Cada consulta se mide desde enviar hasta ver una respuesta nueva. El verificador comprueba hechos mínimos: nota 11 con fuente; cursos del perfil sin cursos prohibidos; presencia de docentes conocidos; correo y cita de orientación psicológica con fuente; enlace nativo de calendario. Estos controles no sustituyen una evaluación humana completa. Se mantienen ≥95% correctas en ≤10 s y cero errores como referencia de aceptación. Una etapa incompleta no aprueba aunque sus muestras disponibles sean rápidas. En la columna de errores, el primer número corresponde a la fase medida y el segundo al calentamiento.")
        table(["Etapa / cuentas", "Muestras / segundos", "Correctas ≤10 s / errores med.+calent.", "p95 / p99 (s)", "Completa / cumple"], [
            (r["stage"] + " / " + str(r["users"]),
             str(r.get("requests", 0)) + " / " + str(r.get("elapsed_seconds", "—")),
             str(r.get("successful_within_10_percent", "—")) + "% / " + str(r.get("errors", 0)) + "+" + str(r.get("warmup_errors", 0)),
             str(r.get("p95_seconds", "—")) + " / " + str(r.get("p99_seconds", "—")),
             flag(r["complete"]) + " / " + flag(r["accepted"]))
            for r in CAPACITY["stages"] if not r["stage"].startswith(("baseline", "http-"))
        ], [3.5, 3.1, 3.5, 3.4, 3])
        if (ASSETS / "capacidad-ampliada.png").exists():
            pic("capacidad-ampliada.png", "Etapas de navegador con muestras medidas: se conservan los incumplimientos. Los calentamientos fallidos sin muestras medidas se detallan en la tabla.")
        p("Se registran CPU, memoria disponible, swap, consumo de contenedores y sondas HTTP. El equipo de cuatro CPU lógicas y aproximadamente 11 GiB de RAM también ejecuta Chromium: la saturación del generador limita lo que puede inferirse del servidor. Los niveles superiores se detienen ante degradación o límites de recursos, sin ocultar muestras. Un límite observado no demuestra que todos los niveles inferiores o superiores sean seguros en producción.")
        p("La fase sostenida estaba programada para quince minutos, pero se detuvo tras 161,485 s y 225 consultas al superar el criterio de errores. No aprobó estabilidad. El pico de 10 a 25 a 10 cuentas falló en el calentamiento y no produjo muestras medidas. La mezcla ampliada falló en calentamiento (4/10 respuestas no válidas, incluida una respuesta académica parcial sin la parte documental). La calibración HTTP documental también falló en calentamiento (1/1). No se ejecutaron sus fases medidas ni la carga HTTP alta debido a la cuota del proveedor. La recuperación previa a ese agotamiento sí se midió por separado. La preparación y el calentamiento se excluyen de la latencia; los reinicios de conversación y pausas declaradas se incluyen en el throughput. Consultar rendimiento-ampliado/resultados.md y los JSON por etapa para parámetros, respuestas, recursos, motivos de parada y muestras completas.")
        http_stages = [r for r in CAPACITY["stages"] if r["stage"].startswith("http-")]
        if http_stages:
            h("6.3.1 Canal complementario HTTP de Moodle", 3)
            p("La carga HTTP alta quedó pendiente por agotamiento de cuota. Se ejecutó únicamente un control de tres consultas académicas con una cuenta, login, cookies y token de sesión reales. Este control verificó que los datos académicos siguieran respondiendo sin usar embeddings. Termina al recibir el HTML y excluye el renderizado: no acredita capacidad concurrente ni equivale a tiempo del chat en navegador.")
            table(["Etapa / cuentas", "Solicitudes", "Correctas ≤10 s", "p95 (s)", "Completa / cumple"], [
                (r["stage"] + " / " + str(r["users"]), r.get("requests", 0),
                 str(r.get("successful_within_10_percent", "—")) + "%", r.get("p95_seconds", "—"),
                 flag(r["complete"]) + " / " + flag(r["accepted"])) for r in http_stages
            ], [3.5, 3.1, 3.5, 3.4, 3])
        p("Diagnóstico confirmado: seis errores query/gemini_throttled en la prueba sostenida; una solicitud diagnóstica independiente devolvió HTTP 429, cuota EmbedContentRequestsPerDayPerProjectPerModel-FreeTier y límite de 1000. El alcance es el proyecto/modelo, no solo esta ejecución. Ver cuota-gemini.json. Debe restablecerse o ampliarse la cuota antes de repetir la fase sostenida; 25 cuentas solo aprobaron la carga breve, no estabilidad prolongada.")
        p("La calibración inicial encontró un falso negativo del arnés: la pregunta sobre cómo pedir orientación psicológica no exigía que la respuesta indicara un precio. Se corrigió el criterio a correo, cita y fuente, con una prueba de regresión, antes de las mediciones de concurrencia. Se conservó el fallo inicial y no se atribuye al producto.")
    h("7. Gestión de defectos")
    p(
        "Se distinguen defectos del producto, del evaluador y del diseño de pruebas. La evidencia inicial se conserva para mostrar qué falló y por qué una corrección es válida. Severidad alta: compromete acceso/datos o bloquea una función principal; media: resultado o validación incorrectos con operación alternativa; baja: presentación o documentación sin bloqueo."
    )
    for d in DEFECTS:
        h(d["id"] + " · " + d["title"], 2)
        table(
            ["Campo", "Registro"],
            [
                (k, d.get(v, ""))
                for k, v in [
                    ("Severidad", "severity"),
                    ("Reproducción", "steps"),
                    ("Esperado", "expected"),
                    ("Obtenido inicial", "actual"),
                    ("Corrección", "fix"),
                    ("Estado", "status"),
                    ("Reprueba / evidencia", "retest"),
                ]
            ],
            [3.7, 12.8],
        )
    h("8. Cumplimiento de la rúbrica")
    p(
        "Se transcriben los descriptores Excelente del archivo de rúbrica. El puntaje es asignado por el docente; esta matriz identifica evidencia y límites, sin autocalificar el trabajo con 20 puntos."
    )
    table(
        ["Criterio / máximo", "Excelente", "Evidencia / estado"],
        [(f"{r[0]} ({r[1]})", r[2], r[3] + "\n" + r[4]) for r in RUBRIC],
        [3.6, 6.6, 6.3],
    )
    h("9. Conclusiones y limitaciones")
    p(
        "La versión corregida vincula requisitos, diez historias y 36 casos con resultados verificables. La separación entre permisos de Moodle y respuesta documental evita delegar autorización al modelo. Los resultados automatizados, funcionales y documentales se conservan con sus condiciones de ejecución."
    )
    if CAPACITY:
        p("La campaña ampliada cambia la aceptación de CP-011 y CP-012: el nivel de 50 cuentas no cumple latencia y la estabilidad sostenida falla por cuota diaria. Los resultados previos se conservan como referencia histórica; no representan aprobación del alcance ampliado ni garantizan que la consulta documental siga disponible con cuota agotada.")
    p(
        "Los umbrales de rendimiento y exactitud se comparan con medidas reales en la sección 6. Una ejecución exitosa evidencia esos escenarios; no prueba ausencia de fallos en preguntas nuevas, disponibilidad prolongada ni compatibilidad con todas las versiones de Moodle."
    )
    for x in [
        "Entorno local con datos preparados; HTTP interno sin cifrado, restringido al host.",
        "Dependencia de conectividad, cuota y comportamiento de proveedores externos; las respuestas y latencias pueden variar.",
        "La carga inicial usó dos cuentas; la campaña ampliada utiliza identidades distintas y declara duración y recursos por etapa. No certifica capacidad de producción.",
        "La validación técnica de interfaz no es un estudio de usabilidad con participantes independientes.",
        "La planificación acepta horas enteras verificables; si el horario no está completamente declarado, ofrece un borrador o pide precisión.",
        "El PPT y guion preparan la sustentación; el dominio oral y las respuestas ante el docente deben demostrarlos los integrantes.",
    ]:
        p(x, "List Bullet")
    h("9.1 Cambios respecto al APF1 presentado", 2)
    table(["Elemento", "Corrección"], CHANGES, [3.5, 13])
    h("10. Referencias")
    for text in REFERENCES:
        p(text)
    p(
        "Documentación interna consultada: GLOSSARY.md; docs/adr/0001-moodle-autoriza-datos-academicos.md; docs/presentacion-asistente.md; migraciones SQL y pruebas del repositorio. La rúbrica y el APF1 originales se conservan en la carpeta superior."
    )
    doc.add_page_break()
    h("Anexo A. Casos de prueba")
    p(
        "Los datos y pasos permiten repetir cada caso. Las referencias a tests identifican fixtures y aserciones exactas; los resultados extensos se conservan íntegros en JSON/JUnit y en el Excel."
    )
    for c, r in zip(CASES, RESULTS):
        h(c[0] + " · " + c[2], 2)
        table(
            ["Campo", "Detalle"],
            [
                ("HU / técnica", c[1] + " / " + c[3]),
                ("Precondiciones", c[4]),
                ("Datos", c[5]),
                ("Pasos", c[6]),
                ("Esperado", c[7]),
                (
                    "Obtenido",
                    r["observed"][:1800]
                    + (
                        " [ver respuesta completa en evidencia]"
                        if len(r["observed"]) > 1800
                        else ""
                    ),
                ),
                ("Estado / fecha", r["status"] + " / " + r["date"] + " UTC"),
                ("Evidencia", r["evidence"]),
            ],
            [3.2, 13.3],
        )
    h("Anexo B. Reproducción y evidencias")
    p(
        "Ejecutar desde la raíz del repositorio. Las claves se configuran localmente; no se incluyen en los entregables. Consulte GUIA-DE-ENTREGA.md para comandos completos y preservación de datos."
    )
    for command in COMMANDS:
        p(command)
    p(
        "Entorno registrado: "
        + str(ENV.get("platform", ""))
        + "; CPU lógicas: "
        + str(ENV.get("cpu_count", ""))
        + ". Versiones exactas de PHP/Moodle/PostgreSQL en phpunit.log; navegador en funcionales.json y carga.json."
    )
    p(
        "El árbol de trabajo contiene cambios previos. Los hashes del manifiesto identifican los archivos utilizados; no se atribuye toda la validación únicamente al commit HEAD."
    )
    doc.save(OUT / "APF1 - Pruebas de Software - Grupo 1 - corregido.docx")


REFERENCES = [
    "[1] Khan, U. H., Khan, M. H., & Ali, R. (2025). Large Language Model based Educational Virtual Assistant using RAG Framework. Procedia Computer Science, 252, 905–911. https://doi.org/10.1016/j.procs.2025.01.051",
    "[2] Kuratomi, G., Pirozelli, P., Cozman, F. G., & Peres, S. M. (2025). A RAG-Based Institutional Assistant. arXiv:2501.13880. https://arxiv.org/abs/2501.13880",
    "[3] Németh, R., Tátrai, A., Szabó, M., Zaletnyik, P. T., & Tamási, Á. (2025). Exploring the use of retrieval-augmented generation models in higher education: A pilot study on artificial intelligence-based tutoring. Social Sciences & Humanities Open, 12, 101751. https://doi.org/10.1016/j.ssaho.2025.101751",
]
REFERENCES.append(
    "[4] HTTPX. Clients y Timeouts. Documentación oficial consultada durante la corrección. https://www.python-httpx.org/advanced/clients/ ; https://www.python-httpx.org/advanced/timeouts/"
)

COMMANDS = [
    "bash dev/moodle/up.sh",
    "(cd rag-service && TEST_DATABASE_URL=postgresql://rag:rag_local_dev@localhost:55432/rag PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright .venv/bin/pytest -q --strict-markers --require-complete)",
    "docker compose -f compose.moodle.yaml exec -T moodle vendor/bin/phpunit --testsuite local_acadassistant_testsuite",
    "PLAYWRIGHT_BROWSERS_PATH=rag-service/.cache/ms-playwright rag-service/.venv/bin/python dev/validation/functional_chat.py",
    "PLAYWRIGHT_BROWSERS_PATH=rag-service/.cache/ms-playwright rag-service/.venv/bin/python dev/moodle/smoke_navigation.py",
    "(cd rag-service && .venv/bin/python scripts/evaluate_demo.py --output ../.scratch/cumplimiento-rubrica-final/evidencias/evaluacion-ia.json)",
    "PLAYWRIGHT_BROWSERS_PATH=rag-service/.cache/ms-playwright rag-service/.venv/bin/python dev/validation/load_chat.py",
]


def make_slides():
    prs = Presentation()
    prs.slide_width = PI(13.333)
    prs.slide_height = PI(7.5)
    s = LOAD.get("summary", {})
    si = IA.get("summary", {})
    slides = [
        (
            "Gestor Académico Virtual",
            "Pruebas de Software · Grupo 1\nMoodle + RAG · Validación local",
            None,
            "Presentar integrantes y problema: localizar información y tareas sin perder permisos ni fuentes.",
        ),
        (
            "Problema y alcance",
            "Documentos, cursos, docentes, tareas, notas y calendario.\nNavegación autorizada y planificación semanal.\nEl chat consulta; las escrituras se realizan en Moodle.",
            None,
            "Explicar una consulta documental y otra académica. Aclarar entorno local y datos preparados.",
        ),
        (
            "Arquitectura que se evaluó",
            "Moodle autoriza · RAG recupera evidencia · IA interpreta.",
            "despliegue.png",
            "Explicar qué datos salen hacia proveedores, firma versus cifrado y por qué el modelo no concede permisos.",
        ),
        (
            "Requisitos verificables",
            "10 historias de usuario · 36 casos de prueba.\nCada caso: datos, pasos, esperado, obtenido y evidencia.\nPositivos, negativos, límites y cambios de sesión.",
            None,
            "Abrir el Excel: mostrar una HU, su requisito y su caso ejecutado. No leer todas las filas.",
        ),
        (
            "Estrategia de pruebas",
            f"{len(PYTEST)} pruebas Python · {len(PHPUNIT)} pruebas Moodle.\nInterfaz controlada + recorridos con IA real.\nPermisos, fuentes, sesión, navegación y planificación.",
            None,
            "Distinguir suites simuladas de inferencias reales; señalar archivos JUnit y JSON.",
        ),
        (
            "Calidad de IA",
            f"{si.get('positive_passed', '?')}/36 positivas · {si.get('negative_passed', '?')}/5 abstenciones\nObjetivo: ≥90% positivas y todas las abstenciones.\nAdemás: ambigüedad, premisa errónea y fuera de alcance.",
            None,
            "Mostrar pregunta de nota mínima y la variante errónea con 20. Explicar limitaciones del comparador de hechos.",
        ),
        (
            "Carga: condiciones",
            "10 sesiones independientes · 100 consultas medidas.\n10 calentamientos excluidos · cinco tipos de consulta.\nDos cuentas reutilizadas; no diez personas distintas.",
            None,
            "Explicar medición desde clic hasta respuesta y throughput con resets. No extrapolar a producción.",
        ),
        (
            "Carga: resultados",
            f"p95: {s.get('p95_seconds', '?')} s · Throughput: {s.get('throughput_requests_per_second', '?')} req/s\nErrores: {s.get('errors', '?')} · Éxito ≤10 s: {s.get('successful_within_10_percent', '?')}%",
            "carga.png",
            "Comparar contra 95% en 10 s y cero errores. Reconocer cualquier meta incumplida sin cambiar el umbral.",
        ),
        (
            "Defectos y repruebas",
            "Umbral del evaluador: 80% → 90%.\nComparador: variante «gratuita».\nDisponibilidad incompleta: no inventar horas.\nConexiones HTTPS reutilizables para reducir esperas.\nRegistro con reproducción y evidencia.",
            None,
            "Mostrar evidencia inicial y prueba de regresión. Distinguir fallo del producto de falso negativo del arnés.",
        ),
        (
            "Demostración técnica",
            "1. Consultar norma y fuente.\n2. Consultar cursos y negar una nota ajena.\n3. Abrir tareas con empate y calendario.\n4. Planificar con horas explícitas y cambiar horario.",
            None,
            "Abrir sesión estudiante1; usar guion. No mostrar archivo .env ni contraseñas al proyectar.",
        ),
        (
            "Límites y decisiones",
            "Localhost; HTTP interno y HTTPS hacia proveedores.\nMuestra acotada; sin garantía de producción.\nSin historial persistente ni escrituras por chat.\nDependencia de conectividad y cuotas de IA.",
            None,
            "Explicar por qué el cambio de alcance es explícito en las tablas y qué sería necesario para desplegar públicamente.",
        ),
        (
            "Evidencia y conclusiones",
            "Informe corregido + Excel editable + reportes.\nTrazabilidad: requisito → HU → caso → resultado.\nEl docente evalúa el cumplimiento y la sustentación.",
            None,
            "Invitar preguntas. Ensayar: qué significa p95, cómo se autoriza, qué pasa sin fuentes y cómo se reprodujo un defecto.",
        ),
    ]
    if CAPACITY.get("stages"):
        stages = [r for r in CAPACITY["stages"] if not r["stage"].startswith("baseline")]
        measured = [r for r in stages if r.get("requests", 0)]
        levels = [r for r in measured if r["stage"].startswith("nivel-")]
        max_measured = max((r["users"] for r in levels), default=0)
        slides[6] = ("Carga ampliada: condiciones",
            f"Cuentas distintas · niveles medidos hasta {max_measured}.\nChat completo y comprobaciones mínimas de respuesta.\nCarga creciente y recuperación medidas. Sostenida: fallo por cuota.\nCPU/RAM y sondas HTTP · mismo equipo que Chromium.",
            None, "Distinguir cuentas preparadas, sesiones iniciadas y carga efectivamente medida. Excluir login/calientamiento de latencia; mantener errores en el denominador. La sostenida no completó sus quince minutos: falló por cuota diaria de Gemini. Pico, mezcla ampliada y calibración HTTP documental fallaron en calentamiento; la carga HTTP alta quedó pendiente.")
        focus = (levels + [r for r in measured if r["stage"].startswith(("sostenida", "mixta"))])[:5]
        body = "\n".join(f"{r['stage']}: {r.get('successful_within_10_percent', 0)}% ≤10 s · p95 {r.get('p95_seconds', 0):.2f} s" for r in focus)
        slides[7] = ("Carga ampliada: resultados", body,
            None, "Ver tabla completa en informe sección 6.3 y Excel hoja 11. Los niveles incompletos o fuera del objetivo no aprueban. Explicar la diferencia entre límite del servidor y límite del generador local; no extrapolar a un campus.")
        slides[8] = ("Hallazgos y estados abiertos",
            "DEF-08: cuota diaria de Gemini agotada.\nSostenida: seis errores; no completó quince minutos.\nDEF-09: cincuenta cuentas incumplen latencia.\nRecuperación a diez: aprobada antes del agotamiento.\nReprueba pendiente con cuota disponible.", None,
            "Conservar los fallos y distinguir las correcciones anteriores de estos hallazgos abiertos. La cuota es por proyecto/modelo; una prueba corta aprobada no certifica estabilidad.")
    for i, (title, body, figure, notes) in enumerate(slides, 1):
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        sl.background.fill.solid()
        sl.background.fill.fore_color.rgb = PC.from_string("F7FAFC")
        shape = sl.shapes.add_textbox(PI(0.65), PI(0.4), PI(12), PI(0.8))
        tf = shape.text_frame
        tf.text = title
        for par in tf.paragraphs:
            par.font.size = PP(30)
            par.font.bold = True
            par.font.color.rgb = PC.from_string(BLUE)
        box = sl.shapes.add_textbox(
            PI(0.7), PI(1.4), PI(12), PI(1.1 if figure else 4.7)
        )
        tf = box.text_frame
        tf.word_wrap = True
        for j, line in enumerate(body.split("\n")):
            par = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            par.text = line
            par.font.size = PP(22 if figure else 25)
            par.space_after = PP(20)
        if figure and (ASSETS / figure).exists():
            sl.shapes.add_picture(
                str(ASSETS / figure), PI(1.8), PI(2.7), width=PI(9.7), height=PI(4.1)
            )
        foot = sl.shapes.add_textbox(PI(0.7), PI(7.05), PI(12), PI(0.3))
        foot.text_frame.text = f"Grupo 1 · Pruebas de Software                                            {i:02d} / {len(slides)}"
        foot.text_frame.paragraphs[0].font.size = PP(11)
        sl.notes_slide.notes_text_frame.text = notes
    prs.save(OUT / "Sustentacion - Grupo 1.pptx")
    guide = "# Guion de sustentación\n\nTiempo sugerido: 12–15 minutos más preguntas. Repartir intervenciones según los roles del informe y ensayar.\n\n"
    for i, (title, body, figure, notes) in enumerate(slides, 1):
        guide += f"## Diapositiva {i}: {title}\n\n{notes}\n\n"
    guide += "## Preguntas para ensayo\n\n- ¿Por qué 95% en 10 segundos no significa que todas respondan en ese tiempo?\n- ¿Por qué una cita correcta no basta para demostrar que todos los hechos de la respuesta son correctos?\n- ¿Qué diferencia hay entre firma y cifrado?\n- ¿Cómo se impide que un estudiante vea las notas de otro?\n- ¿Qué se conserva y qué se borra al terminar la sesión?\n- ¿Por qué los resultados locales no demuestran capacidad de producción?\n- ¿Qué defectos se encontraron y qué evidencia comprueba su corrección?\n\nSi falla un proveedor en vivo, mostrar el error real y las evidencias fechadas; no presentar una captura histórica como ejecución actual.\n"
    (OUT / "Guion de sustentacion.md").write_text(guide)


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    ASSETS.mkdir(exist_ok=True)
    figures.main()
    make_excel()
    make_doc()
    make_slides()
    (OUT / "matriz-cumplimiento.md").write_text(
        "# Matriz de cumplimiento\n\nNo constituye una calificación; ver evidencia y límites.\n\n| Criterio | Máximo | Evidencia | Estado |\n|---|---:|---|---|\n"
        + "".join(f"| {r[0]} | {r[1]} | {r[3]} | {r[4]} |\n" for r in RUBRIC)
    )
    (EV / "resultados-casos.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2) + "\n"
    )
    print("Generados DOCX, XLSX, PPTX, diagramas, guion y matriz en", OUT)


if __name__ == "__main__":
    main()
