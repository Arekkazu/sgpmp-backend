"""TC-M04-G037 — RF-65 / CU-02.

Subcasos: TC-M04-001, TC-M04-002, TC-M04-003.
Contrato: ConfigurarMotorUseCase. Persistencia = repositorio en memoria, no SQL.
Hot-reload hacia Edge no existe en este use case.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from src.shared.errors import BusinessRuleError

_MOD4 = Path(__file__).resolve().parents[2]
if str(_MOD4) not in sys.path:
    sys.path.insert(0, str(_MOD4))
from rf65_dobles import dto_motor, ensamblar  # noqa: E402


def test_tc_m04_001_configuracion_valida_en_use_case() -> None:
    uc, repo, auditoria, _, _, db = ensamblar()
    entidad, es_nueva = uc.execute(dto_motor(), id_usuario=9)
    assert es_nueva is True
    assert entidad.umbral_riesgo_alto == Decimal("0.70")
    assert entidad.umbral_alerta_critica == Decimal("0.80")
    assert entidad.ventana_temporal_min == 10
    assert entidad.config_version == 1
    assert entidad.modo_ejecucion == "SERVIDOR"
    guardada = repo.obtener_por_tipo(entidad.tipo_modelo)
    assert guardada is not None
    assert guardada.umbral_riesgo_alto == Decimal("0.70")
    assert db.commits >= 1
    assert auditoria.eventos[0]["tipo_evento"] == "CONFIGURACION_MOTOR_CAMBIADA"
    assert auditoria.eventos[0]["id_usuario"] == 9
    assert auditoria.eventos[0]["payload_evento"]["accion"] == "CREADA"


def test_tc_m04_001_hot_reload_edge() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-001 (hot-reload): ConfigurarMotorUseCase no notifica nodos Edge. "
        "NodoEdgePort solo expone hay_nodos_activos. No hay canal de sincronización ≤5 s."
    )


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("umbral_riesgo_alto", Decimal("0.50")),
        ("umbral_riesgo_alto", Decimal("0.95")),
        ("umbral_alerta_critica", Decimal("0.50")),
        ("umbral_alerta_critica", Decimal("0.95")),
        ("ventana_temporal_min", 5),
        ("ventana_temporal_min", 15),
    ],
)
def test_tc_m04_002_limites_validos(campo, valor) -> None:
    kwargs = {campo: valor}
    if campo == "umbral_riesgo_alto" and valor == Decimal("0.95"):
        kwargs["umbral_alerta_critica"] = Decimal("0.95")
    if campo == "umbral_alerta_critica" and valor == Decimal("0.50"):
        kwargs["umbral_riesgo_alto"] = Decimal("0.50")
    uc, repo, _, _, _, _ = ensamblar()
    entidad, _ = uc.execute(dto_motor(**kwargs), id_usuario=1)
    assert getattr(entidad, campo) == valor
    assert repo.obtener_por_tipo(entidad.tipo_modelo) is not None


@pytest.mark.parametrize(
    "campo,valor,codigo",
    [
        ("umbral_riesgo_alto", Decimal("0.49"), "UMBRAL_RIESGO_FUERA_RANGO"),
        ("umbral_riesgo_alto", Decimal("0.96"), "UMBRAL_RIESGO_FUERA_RANGO"),
        ("umbral_alerta_critica", Decimal("0.49"), "UMBRAL_CRITICA_FUERA_RANGO"),
        ("umbral_alerta_critica", Decimal("0.96"), "UMBRAL_CRITICA_FUERA_RANGO"),
        ("ventana_temporal_min", 4, "VENTANA_TEMPORAL_FUERA_RANGO"),
        ("ventana_temporal_min", 16, "VENTANA_TEMPORAL_FUERA_RANGO"),
    ],
)
def test_tc_m04_002_fuera_de_rango_no_persiste(campo, valor, codigo) -> None:
    uc, repo, auditoria, _, _, db = ensamblar()
    uc.execute(dto_motor(), id_usuario=1)
    vigente = repo.obtener_por_tipo("MODELO_ESPECIES_GRANDES")
    assert vigente.config_version == 1
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(dto_motor(**{campo: valor}), id_usuario=1)
    assert exc.value.code == codigo
    assert exc.value.status_code == 422
    despues = repo.obtener_por_tipo("MODELO_ESPECIES_GRANDES")
    assert despues.umbral_riesgo_alto == Decimal("0.70")
    assert despues.config_version == 1
    assert len(auditoria.eventos) == 1
    assert db.rollbacks == 0


def test_tc_m04_003_alerta_menor_que_riesgo_no_guarda() -> None:
    uc, repo, auditoria, _, _, _ = ensamblar()
    uc.execute(dto_motor(), id_usuario=1)
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(
            dto_motor(umbral_riesgo_alto=Decimal("0.80"), umbral_alerta_critica=Decimal("0.70")),
            id_usuario=1,
        )
    assert exc.value.code == "UMBRAL_CRITICA_MENOR_QUE_RIESGO"
    assert exc.value.status_code == 422
    vigente = repo.obtener_por_tipo("MODELO_ESPECIES_GRANDES")
    assert vigente.umbral_riesgo_alto == Decimal("0.70")
    assert vigente.umbral_alerta_critica == Decimal("0.80")
    assert vigente.config_version == 1
    assert all(e["payload_evento"]["accion"] != "ACTUALIZADA" for e in auditoria.eventos)
