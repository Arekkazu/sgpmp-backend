"""TC-M04-G039 — RF-65 / CU-02.

Subcasos: TC-M04-006, TC-M04-019, TC-M04-020.
Auditoría: EventoAuditoriaM04Repository.registrar (append). No hay UPDATE/DELETE en el puerto.
La tabla SQL no se toca aquí. ResultadoInferenciaModel no tiene config_version.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from src.prediction.domain.repositories.evento_auditoria_m04_repository import (
    EventoAuditoriaM04Repository,
)
from src.prediction.infrastructure.models.resultado_inferencia_model import ResultadoInferenciaModel
from src.prediction.infrastructure.routers import auditoria_m04_router

_MOD4 = Path(__file__).resolve().parents[2]
if str(_MOD4) not in sys.path:
    sys.path.insert(0, str(_MOD4))
from rf65_dobles import dto_motor, ensamblar  # noqa: E402


def test_tc_m04_006_auditoria_registra_usuario_version_y_diff() -> None:
    uc, _, auditoria, _, _, _ = ensamblar()
    uc.execute(dto_motor(), id_usuario=11)
    uc.execute(dto_motor(umbral_riesgo_alto=Decimal("0.71"), umbral_alerta_critica=Decimal("0.81")), id_usuario=12)
    assert len(auditoria.eventos) == 2
    segundo = auditoria.eventos[1]
    assert segundo["id_usuario"] == 12
    assert segundo["tipo_evento"] == "CONFIGURACION_MOTOR_CAMBIADA"
    payload = segundo["payload_evento"]
    assert payload["accion"] == "ACTUALIZADA"
    assert payload["valores_anteriores"]["config_version"] == 1
    assert payload["valores_nuevos"]["config_version"] == 2
    assert payload["valores_nuevos"]["umbral_riesgo_alto"] == "0.71"


def test_tc_m04_006_puerto_auditoria_solo_append() -> None:
    metodos = set(EventoAuditoriaM04Repository.__abstractmethods__)
    assert {"registrar", "consultar", "obtener_por_id"} <= metodos
    assert "actualizar" not in metodos
    assert "eliminar" not in metodos
    assert "delete" not in metodos
    rutas = [getattr(r, "path", "") + (getattr(r, "methods", set()) and str(r.methods)) for r in auditoria_m04_router.router.routes]
    texto = " ".join(rutas)
    assert "POST" not in texto
    assert "PUT" not in texto
    assert "PATCH" not in texto
    assert "DELETE" not in texto


def test_tc_m04_006_inmutabilidad_sql_historial() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-006 (SQL): no se ejecuta UPDATE/DELETE contra modulo4.eventos_auditoria_m04. "
        "La ausencia de endpoint de escritura no demuestra trigger/REVOKE en PostgreSQL. "
        "Falta entorno de BD de prueba aislada."
    )


def test_tc_m04_019_inferencia_en_curso_no_guarda_config_version() -> None:
    columnas = set(ResultadoInferenciaModel.__table__.columns.keys())
    assert "config_version" not in columnas
    pytest.skip(
        "BLOQUEADO TC-M04-019: resultados_inferencia no tiene config_version. "
        "No hay forma de observar que una inferencia iniciada conserve N tras un cambio a N+1."
    )


def test_tc_m04_020_fallo_al_aplicar_no_cambia_vigente() -> None:
    uc, repo, auditoria, _, _, db = ensamblar()
    uc.execute(dto_motor(), id_usuario=1)
    repo.actualizar_ok = False
    with pytest.raises(RuntimeError, match="fallo simulado al aplicar"):
        uc.execute(dto_motor(umbral_riesgo_alto=Decimal("0.75"), umbral_alerta_critica=Decimal("0.85")), id_usuario=1)
    assert db.rollbacks >= 1
    vigente = repo.obtener_por_tipo("MODELO_ESPECIES_GRANDES")
    assert vigente.config_version == 1
    assert vigente.umbral_riesgo_alto == Decimal("0.70")
    assert len(auditoria.eventos) == 1
