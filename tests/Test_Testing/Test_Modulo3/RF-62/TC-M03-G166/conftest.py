"""conftest.py — Configuración de Pytest local para TC-M03-G166.

Aislamiento:
- Se ejecuta con `--confcutdir=tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G166` para ignorar
  el `tests/conftest.py` raíz y evitar imports innecesarios de `main.py`.
- Implementa los hooks oficiales para:
  1. Imprimir el Banner normativo de la Decisión D7 mediante pytest_report_header (visible sin -s).
  2. Guardar y actualizar la metadata viva en pytest-html (conteo inicial/final/delta de modulo1.eventos).
  3. Fixture autouse de sesión para medir inocuidad en modulo1.eventos antes y después de los tests funcionales.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Generator, List, Optional

import pytest

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from spec_tc_m03_g166 import SpecTCM03G166
from helpers_tc_m03_g166 import SandboxClient, cargar_configuracion_entorno, extraer_filas

# Diccionario vivo de estado para reporte y metadata HTML
_METADATA_EVENTOS: dict[str, str] = {
    "conteo_inicial": "NO MEDIDO",
    "conteo_final": "NO MEDIDO",
    "delta": "NO MEDIDO",
}

# Referencia a la metadata inyectada en pytest_metadata
_METADATA_DICT_REF: Optional[dict] = None


def pytest_configure(config: pytest.Config) -> None:
    """Registra markers personalizados para evitar warnings en ejecución estricta."""
    config.addinivalue_line(
        "markers",
        "backend_defect: Documenta defecto de backend conocido; su fallo es correcto y esperado.",
    )
    config.addinivalue_line(
        "markers",
        "no_fail_si_bloqueado: el test se ejecuta incluso si el setup "
        "detecta bloqueo externo (broker 503).",
    )


def pytest_report_header(config: pytest.Config) -> List[str]:
    """Hook oficial de Pytest: emite el Banner D7 RESUELTO en el encabezado de consola (compatible con cp1252)."""
    lineas = [
        "=" * 78,
        " [BANNER D7 RESUELTO] TC-M03-G166 -- ESTADO DE EVALUACION DE CALIDAD",
        "=" * 78,
        " * D7 RESUELTO: literal VIGENTE; catálogo {VIGENTE, SUPERADA}; RFC de aclaración en trámite.",
        f" * Estado Superado Normativo : {SpecTCM03G166.Estados.estado_superado} (RF-62 restriccion 9)",
        f" * Estado Vigente Definido   : {SpecTCM03G166.Estados.estado_vigente}",
        f" * Catalogo de Estados       : {SpecTCM03G166.Estados.catalogo_estados}",
        f" * Estados Definidos (D7)    : {SpecTCM03G166.Estados.ESTADOS_DEFINIDOS}",
        " * Regla canónica            : Máximo UNA evaluación VIGENTE por lectura.",
        " * Defecto conocido          : /evaluar duplica VIGENTES (invariante debe fallar hoy).",
        "=" * 78,
    ]
    return lineas


def pytest_metadata(metadata: dict) -> None:
    """Inyecta metadata viva en pytest-html y almacena la referencia para actualización."""
    global _METADATA_DICT_REF
    _METADATA_DICT_REF = metadata
    metadata["Caso de Prueba"] = "TC-M03-G166 (RF-62 / RF-57 / RF-63)"
    metadata["Módulo"] = "Módulo 3 - Telemetría IoT"
    metadata["Decisión D7 (Estados)"] = "DEFINIDO"
    metadata["Auditoría modulo1.eventos Inicial"] = _METADATA_EVENTOS["conteo_inicial"]
    metadata["Auditoría modulo1.eventos Final"] = _METADATA_EVENTOS["conteo_final"]
    metadata["Auditoría modulo1.eventos Delta"] = _METADATA_EVENTOS["delta"]


def actualizar_metadata_reporte(inicial: str, final: str, delta: str) -> None:
    """Actualiza tanto el diccionario vivo interno como la referencia de pytest-html."""
    _METADATA_EVENTOS["conteo_inicial"] = inicial
    _METADATA_EVENTOS["conteo_final"] = final
    _METADATA_EVENTOS["delta"] = delta
    if _METADATA_DICT_REF is not None:
        _METADATA_DICT_REF["Auditoría modulo1.eventos Inicial"] = inicial
        _METADATA_DICT_REF["Auditoría modulo1.eventos Final"] = final
        _METADATA_DICT_REF["Auditoría modulo1.eventos Delta"] = delta


def consultar_conteo_eventos(cfg: dict[str, str], client_factory=None) -> Tuple[Optional[int], Optional[str]]:
    """Consulta el total de registros en modulo1.eventos usando un run efímero con secreto.

    Retorna: (total_conteo, motivo_error)
    """
    run_efimero = f"test-audit-{uuid.uuid4().hex[:8]}"
    if client_factory:
        client = client_factory(cfg["TEST_BASE_URL"], run_efimero, cfg["TEST_SANDBOX_SECRET"])
    else:
        client = SandboxClient(cfg["TEST_BASE_URL"], run_efimero, cfg["TEST_SANDBOX_SECRET"])

    motivo: Optional[str] = None
    try:
        resp = client.execute_query("SELECT COUNT(*) AS total FROM modulo1.eventos")
        if resp.status_code == 200:
            rows = extraer_filas(resp)
            if rows:
                val = rows[0].get("total", rows[0].get("count", 0))
                return int(val), None
            motivo = "Respuesta sin filas"
        else:
            motivo = f"HTTP {resp.status_code}"
    except Exception as exc:
        motivo = f"Excepción {type(exc).__name__}"
    finally:
        try:
            resp_del = client.delete(f"test-control/runs/{run_efimero}")
            # Tolera 200 (éxito) y 404 (run ya cerrado/inexistente); cualquier otro se registra
            if resp_del.status_code not in (200, 404):
                motivo = f"{motivo or 'OK'} | Fallo DELETE run efímero: HTTP {resp_del.status_code}"
        except Exception as exc_del:
            motivo = f"{motivo or 'OK'} | Excepción DELETE run efímero: {type(exc_del).__name__}"

    return None, motivo


@pytest.fixture(scope="session", autouse=True)
def auditoria_sesion_modulo1_eventos(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Fixture autouse de sesión para medir inocuidad en modulo1.eventos.

    Se activa ÚNICAMENTE si la sesión incluye tests funcionales de TC-M03-G166
    (evita invocarse en pruebas unitarias puras como test_unitario_local_g166.py).
    """
    items = getattr(request.session, "items", [])
    es_suite_funcional = any("test_tc_m03_g166.py" in str(getattr(it, "fspath", "")) for it in items)

    if not es_suite_funcional:
        yield
        return

    try:
        cfg = cargar_configuracion_entorno()
    except Exception as exc:
        motivo_cfg = f"NO MEDIDO: fallo configuración ({type(exc).__name__})"
        actualizar_metadata_reporte(motivo_cfg, motivo_cfg, "NO CALCULADO")
        yield
        return

    c_inicial, err_inicial = consultar_conteo_eventos(cfg)
    txt_inicial = str(c_inicial) if c_inicial is not None else f"NO MEDIDO: {err_inicial}"
    actualizar_metadata_reporte(txt_inicial, "EN PROGRESO", "EN PROGRESO")

    yield

    c_final, err_final = consultar_conteo_eventos(cfg)
    txt_final = str(c_final) if c_final is not None else f"NO MEDIDO: {err_final}"

    if c_inicial is not None and c_final is not None:
        delta = c_final - c_inicial
        if delta == 0:
            txt_delta = "0 (Inocuidad confirmada)"
        else:
            txt_delta = f"+{delta} (REVISAR: puede ser actividad ajena en TEST)"
    else:
        txt_delta = "NO CALCULADO"

    actualizar_metadata_reporte(txt_inicial, txt_final, txt_delta)
