"""TC-M03-G36 — TC-M03-075 y TC-M03-080 (RF-55.1, procesamiento Edge).

No modifica codigo productivo. No inventa dispositivos, umbrales, mediciones ni
clasificaciones. No llama a POST /iot/eventos-edge como si fuera RF-55.1.
"""
from __future__ import annotations

import ast
import inspect
import json
from datetime import datetime, timezone
from html import escape as html_escape
from pathlib import Path

import pytest

DIR = Path(__file__).resolve().parent
RESULTADOS = DIR / "Resultados"
REPO_ROOT = DIR.parents[4]
SRC = REPO_ROOT / "src"
TESTS_ROOT = REPO_ROOT / "tests"
ANOTACIONES = REPO_ROOT / "anotaciones" / "modulo_3"

EVIDENCIA: dict = {
    "caso": "TC-M03-G36",
    "revision": 1,
    "modulo": "M03",
    "cu": "CU-02",
    "rf": "RF-55",
    "rf_especifico": "RF-55.1",
    "tipo": "Funcional / Resiliencia",
    "herramienta": "Python + pytest + inspeccion (simulacion Edge no presente en el repo)",
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "criterio_tiempo_ms": 500,
    "inspeccion": {},
    "subcasos": {
        "TC-M03-075": {"resultado": "PENDIENTE"},
        "TC-M03-080": {"resultado": "PENDIENTE"},
    },
    "estado_global": "PENDIENTE",
    "auditoria": (
        "Sin cambios en src/. Sin DML. Sin inventar IDs/umbrales/mediciones. "
        "Sin usar POST /iot/eventos-edge como clasificador RF-55.1."
    ),
}

_NOMBRES_PROCESADOR = (
    "rf55",
    "rf_55",
    "procesar_medicion",
    "procesamiento_edge",
    "clasificar_umbral",
    "desviacion_simple",
    "buffer_local",
    "edge_sim",
    "simulacion_edge",
)


def _escribir() -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = EVIDENCIA
    (RESULTADOS / "TC-M03-G36.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    subs = payload.get("subcasos") or {}
    lineas = [
        "TC-M03-G36 — RF-55.1 / CU-02 — procesamiento Edge",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Global: {payload.get('estado_global')}",
        "",
        f"TC-M03-075: {(subs.get('TC-M03-075') or {}).get('resultado')}",
        f"TC-M03-080: {(subs.get('TC-M03-080') or {}).get('resultado')}",
        "",
        json.dumps(subs, ensure_ascii=False, indent=2, default=str),
        "",
        json.dumps(payload.get("inspeccion"), ensure_ascii=False, indent=2, default=str),
        "",
        payload.get("auditoria"),
    ]
    (RESULTADOS / "TC-M03-G36.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (RESULTADOS / "TC-M03-G36-evidencia.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M03-G36</title></head><body>"
        "<h1>TC-M03-G36 — TC-M03-075 / TC-M03-080</h1>"
        f"<p>Global: {html_escape(str(payload.get('estado_global')))}</p>"
        f"<pre>{html_escape(json.dumps(payload, ensure_ascii=False, indent=2, default=str))}</pre>"
        "</body></html>",
        encoding="utf-8",
    )


@pytest.fixture(scope="session")
def sesion():
    yield {}
    _escribir()


def _scan_py_hits(raiz: Path, limite: int = 80) -> list[dict]:
    hits: list[dict] = []
    if not raiz.is_dir():
        return hits
    for path in raiz.rglob("*.py"):
        try:
            rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            continue
        if any(p in rel for p in ("/.venv/", "/venv/", "__pycache__", "/.git/")):
            continue
        name_l = path.name.lower()
        name_hit = any(k in name_l or k in rel.lower() for k in _NOMBRES_PROCESADOR)
        body_hit = False
        snippet = None
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        low = text.lower()
        if "rf-55.1" in low or "rf55.1" in low or "procesamiento edge" in low:
            body_hit = True
        if "clasificacion_rf55" in low and "normal" in low:
            body_hit = True
        if name_hit or body_hit:
            for needle in ("RF-55.1", "procesar_medicion", "buffer_local", "DESVIACION_SIMPLE"):
                idx = text.find(needle)
                if idx >= 0:
                    snippet = text[max(0, idx - 40) : idx + 80].replace("\n", " ")
                    break
            hits.append({"path": rel, "por_nombre": name_hit, "por_contenido": body_hit, "snippet": snippet})
        if len(hits) >= limite:
            break
    return hits


def _inspect_recibir_evento_edge() -> dict:
    from src.telemetry.application.use_cases.inferencia.recibir_evento_edge_use_case import (
        RecibirEventoEdgeUseCase,
    )
    from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO

    src_execute = inspect.getsource(RecibirEventoEdgeUseCase.execute)
    fields = sorted(RecibirEventoEdgeDTO.model_fields.keys())
    return {
        "modulo": "src.telemetry.application.use_cases.inferencia.recibir_evento_edge_use_case",
        "clase": "RecibirEventoEdgeUseCase",
        "rol": "RF-56: recibe evento YA clasificado por RF-55 (AIOT). No implementa RF-55.1.",
        "dto_campos": fields,
        "dto_exige_clasificacion_entrada": "clasificacion_rf55" in fields,
        "execute_asigna_clasificacion_desde_dto": "clasificacion_rf55=dto.clasificacion_rf55" in src_execute,
        "execute_evalua_umbral_local": "umbral" in src_execute.lower(),
        "no_es_procesador_rf55_1": True,
    }


def _inspect_nodo_stub() -> dict:
    from src.prediction.infrastructure.adapters.nodo_edge_stub_adapter import NodoEdgeStubAdapter

    src = inspect.getsource(NodoEdgeStubAdapter)
    return {
        "modulo": "src.prediction.infrastructure.adapters.nodo_edge_stub_adapter",
        "clase": "NodoEdgeStubAdapter",
        "metodos": [m for m, _ in inspect.getmembers(NodoEdgeStubAdapter, predicate=inspect.isfunction)],
        "implementa_clasificacion_rf55": "clasificacion" in src.lower() or "umbral" in src.lower(),
        "rol": "Stub M04 (hay_nodos_activos). No procesa mediciones.",
    }


def _inspect_docs() -> dict:
    docs = {}
    for name in ("pendientes_frontend_m03.md", "M03-SPLIT.md"):
        path = ANOTACIONES / name
        docs[name] = {
            "existe": path.is_file(),
            "rf55_fuera_de_alcance_dev": False,
        }
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            docs[name]["rf55_fuera_de_alcance_dev"] = (
                "RF-55" in text and ("fuera de alcance" in text.lower() or "AIOT" in text)
            )
    return docs


def _hay_procesador_local(hits: list[dict], dto_info: dict, stub_info: dict) -> bool:
    if dto_info.get("execute_evalua_umbral_local"):
        return True
    if stub_info.get("implementa_clasificacion_rf55"):
        return True
    for h in hits:
        rel = h.get("path") or ""
        if rel.endswith("recibir_evento_edge_use_case.py"):
            continue
        if rel.endswith("recibir_evento_edge_dto.py"):
            continue
        if rel.endswith("evento_edge_repository.py"):
            continue
        if rel.endswith("nodo_edge_stub_adapter.py"):
            continue
        if "test_tc_m03_g36.py" in rel:
            continue
        if h.get("por_nombre") and any(
            x in rel.lower() for x in ("simulat", "edge_node", "rf55", "procesamiento_edge")
        ):
            return True
    return False


def _hay_buffer_edge_local(hits: list[dict]) -> bool:
    for h in hits:
        rel = (h.get("path") or "").lower()
        if "test_tc_m03_g36.py" in rel:
            continue
        if "buffer" in rel and "edge" in rel and "src/" in rel.replace("\\", "/"):
            if "evento_edge_repository" not in rel:
                return True
    return False


def _motivo_bloqueo(insp: dict) -> str:
    faltantes = []
    if not insp.get("mecanismo_procesamiento_edge"):
        faltantes.append(
            "mecanismo funcional de procesamiento Edge RF-55.1 "
            "(evaluar medicion vs umbral local y emitir NORMAL/DESVIACION_SIMPLE)"
        )
    if not insp.get("umbral_local_en_nodo"):
        faltantes.append("umbral disponible localmente en el nodo Edge (no se inventa desde M09/backend)")
    if not insp.get("simulacion_edge_en_tests"):
        faltantes.append("utilidad/fixture de simulacion Edge en tests/")
    if not insp.get("buffer_local_nodo"):
        faltantes.append("buffer local del nodo (RF-54 / AIOT); almacendado_buffer del backend no es el buffer del Edge")
    if not insp.get("mock_conectividad_nodo"):
        faltantes.append("mock/mecanismo de conectividad del nodo Edge")
    return (
        "BLOQUEADO: no se puede ejecutar RF-55.1 en este repositorio. Falta: "
        + "; ".join(faltantes)
        + ". Documentacion: RF-54 y RF-55 son AIOT (firmware/Edge), fuera de alcance Dev. "
        "POST /iot/eventos-edge es RF-56 y exige clasificacion_rf55 de entrada; usarlo "
        "implicaria inventar la clasificacion. No se fabrican mediciones ni umbrales."
    )


@pytest.fixture(scope="session")
def inspeccion(sesion):
    hits_src = _scan_py_hits(SRC)
    hits_tests = _scan_py_hits(TESTS_ROOT)
    dto_info = _inspect_recibir_evento_edge()
    stub_info = _inspect_nodo_stub()
    docs = _inspect_docs()
    sim_files = [
        h["path"]
        for h in hits_tests
        if any(k in (h["path"] or "").lower() for k in ("edge", "rf55", "buffer"))
        and "test_tc_m03_g36.py" not in (h["path"] or "")
    ]
    insp = {
        "repo_root": str(REPO_ROOT),
        "existe_test_modulo3_previo": any(
            p.is_file()
            for p in (TESTS_ROOT / "Test_Testing" / "Test_Modulo3").rglob("*")
            if p.name != "test_tc_m03_g36.py"
            and "TC-M03-G36" not in str(p)
            and p.suffix in {".py", ".json", ".ps1", ".html", ".txt"}
        ),
        "hits_src": hits_src[:40],
        "hits_tests_edge": sim_files[:40],
        "recibir_evento_edge": dto_info,
        "nodo_edge_stub": stub_info,
        "documentacion_m03": docs,
        "mecanismo_procesamiento_edge": _hay_procesador_local(hits_src, dto_info, stub_info),
        "umbral_local_en_nodo": False,
        "simulacion_edge_en_tests": bool(sim_files),
        "buffer_local_nodo": _hay_buffer_edge_local(hits_src),
        "mock_conectividad_nodo": False,
        "nota_buffer_backend": (
            "SqlAlchemyEventoEdgeRepository.guardar pone almacendado_buffer=not estado_conectividad "
            "cuando el backend YA recibio el evento. Eso no demuestra buffer local del nodo sin red."
        ),
    }
    insp["motivo_bloqueo"] = _motivo_bloqueo(insp)
    EVIDENCIA["inspeccion"] = insp
    return insp


def test_00_inspeccion_precondiciones(inspeccion):
    """La inspeccion debe ejecutarse y quedar en evidencia. No es defecto de producto."""
    assert inspeccion.get("recibir_evento_edge", {}).get("dto_exige_clasificacion_entrada") is True
    assert inspeccion.get("recibir_evento_edge", {}).get("execute_asigna_clasificacion_desde_dto") is True
    assert inspeccion.get("nodo_edge_stub", {}).get("implementa_clasificacion_rf55") is False
    assert inspeccion.get("mecanismo_procesamiento_edge") is False


def _base_subcaso(codigo: str, conectividad) -> dict:
    return {
        "resultado": "BLOQUEADO",
        "clasificacion_obtenida": None,
        "tiempo_procesamiento_ms": None,
        "medicion": None,
        "umbral": None,
        "evento_edge": None,
        "conectividad": conectividad,
        "buffer_local": None,
        "pytest": "skipped (precondicion)",
        "precondiciones": {
            "mecanismo_procesamiento_edge": False,
            "variable_valida_en_nodo": False,
            "umbral_local": False,
            "medicion_valida": False,
            "buffer_local": False,
        },
        "no_ejecutado": True,
        "conclusion": EVIDENCIA["inspeccion"].get("motivo_bloqueo"),
    }


def test_tc_m03_075_medicion_valida_con_conectividad(inspeccion):
    out = _base_subcaso("TC-M03-075", True)
    out["objetivo"] = (
        "Procesar medicion valida dentro de umbral local RF-55.1 y clasificar NORMAL, "
        "con conectividad habilitada. Envio a backend es secundario."
    )
    EVIDENCIA["subcasos"]["TC-M03-075"] = out
    pytest.skip(out["conclusion"])


def test_tc_m03_080_medicion_valida_sin_conectividad(inspeccion):
    out = _base_subcaso("TC-M03-080", False)
    out["objetivo"] = (
        "Procesar medicion valida RF-55.1 sin conectividad: clasificacion local "
        "y persistencia en buffer del nodo, sin depender de HTTP del backend."
    )
    out["precondiciones"]["conectividad_off"] = "no simulable: no hay mock de nodo Edge"
    EVIDENCIA["subcasos"]["TC-M03-080"] = out
    pytest.skip(out["conclusion"])


def test_zz_estado_global(inspeccion):
    r075 = (EVIDENCIA.get("subcasos") or {}).get("TC-M03-075") or {}
    r080 = (EVIDENCIA.get("subcasos") or {}).get("TC-M03-080") or {}
    resultados = {r075.get("resultado"), r080.get("resultado")}
    if "RECHAZADO" in resultados:
        EVIDENCIA["estado_global"] = "RECHAZADO"
    elif resultados == {"APROBADO"}:
        EVIDENCIA["estado_global"] = "APROBADO"
    else:
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    assert EVIDENCIA["estado_global"] == "BLOQUEADO"
    assert r075.get("resultado") == "BLOQUEADO"
    assert r080.get("resultado") == "BLOQUEADO"
    assert r075.get("clasificacion_obtenida") is None
    assert r080.get("clasificacion_obtenida") is None
    assert r075.get("tiempo_procesamiento_ms") is None
    assert r080.get("tiempo_procesamiento_ms") is None


def test_no_se_inventa_clasificador(inspeccion):
    """Guardrail: este archivo no debe definir un clasificador RF-55.1 ficticio."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    nombres = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))}
    prohibidos = {
        "clasificar_rf55",
        "procesar_medicion",
        "EdgeSimulator",
        "simular_edge",
        "evaluar_umbral",
    }
    choque = nombres & prohibidos
    assert not choque, f"ERROR DE PRUEBA: clasificador inventado en el test: {choque}"
