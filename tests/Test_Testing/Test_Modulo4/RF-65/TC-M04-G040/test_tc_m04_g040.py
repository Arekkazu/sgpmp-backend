"""TC-M04-G040 — RF-65 / CU-02.

Subcasos: TC-M04-007, TC-M04-008, TC-M04-022, TC-M04-023.
Único tramo Dev: FA-08 modo EDGE/HIBRIDO exige hay_nodos_activos.
Producción usa NodoEdgeStubAdapter que siempre retorna True.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.prediction.infrastructure.adapters.nodo_edge_stub_adapter import NodoEdgeStubAdapter
from src.shared.errors import BusinessRuleError

_MOD4 = Path(__file__).resolve().parents[2]
if str(_MOD4) not in sys.path:
    sys.path.insert(0, str(_MOD4))
from rf65_dobles import NodoEdgeFijo, dto_motor, ensamblar  # noqa: E402


def test_tc_m04_022_edge_sin_nodos_rechaza_y_conserva_servidor() -> None:
    uc, repo, _, _, nodos, _ = ensamblar(nodos=NodoEdgeFijo(False))
    uc.execute(dto_motor(modo_ejecucion="SERVIDOR"), id_usuario=1)
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(dto_motor(modo_ejecucion="EDGE"), id_usuario=1)
    assert exc.value.code == "MODO_EDGE_SIN_NODOS"
    assert nodos.consultas[-1] == "MODELO_ESPECIES_GRANDES"
    vigente = repo.obtener_por_tipo("MODELO_ESPECIES_GRANDES")
    assert vigente.modo_ejecucion == "SERVIDOR"
    assert vigente.config_version == 1


def test_tc_m04_022_hibrido_sin_nodos_rechaza() -> None:
    uc, _, _, _, _, _ = ensamblar(nodos=NodoEdgeFijo(False))
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(dto_motor(modo_ejecucion="HIBRIDO"), id_usuario=1)
    assert exc.value.code == "MODO_EDGE_SIN_NODOS"


def test_tc_m04_022_stub_productivo_siempre_true() -> None:
    """Delimita el adaptador de producción; no prueba infraestructura Edge."""
    assert NodoEdgeStubAdapter().hay_nodos_activos("MODELO_ESPECIES_GRANDES") is True


def test_tc_m04_007_sincronizacion_versionado_edge() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-007: no hay cliente de sincronización de configuración al nodo. "
        "NodoEdgePort no aplica versiones ni mide ≤5 s."
    )


def test_tc_m04_008_fallback_fallo_edge() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-008: ConfigurarMotorUseCase no cambia a SERVIDOR ante timeout de nodo "
        "ni registra métricas de fallback ≤2 s."
    )


def test_tc_m04_023_reconciliacion_y_alerta_desincronizado() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-023: no hay estado FALLIDA de nodo, reconciliación >5 s ni "
        "ALERTA_NODO_DESINCRONIZADO en src/prediction."
    )
