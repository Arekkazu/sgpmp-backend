# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-25 | Arekkazu | INC-M04-154-G085 / INC-M04-152-G083 RF-73: eventos que faltaban |
"""RF-73: CONFLICTO_RETROALIMENTACION llegaba como AUDITORIA_EVENTO_INVALIDO
(payload con otra clave) y un hash inválido en la OTA no dejaba HASH_INVALIDO_DETECTADO."""
from __future__ import annotations

import contextlib
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case import (
    RegistrarRetroalimentacionUseCase,
)
from src.prediction.infrastructure.dto.registrar_retroalimentacion_dto import RegistrarRetroalimentacionDTO
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)
from tests.prediction.test_dev15_orquestador_ota import _distribuida


class _Sesion:
    def __init__(self): self.guardados = []
    def begin_nested(self): return contextlib.nullcontext()
    def add(self, orm): self.guardados.append(orm)
    def flush(self): pass
    def commit(self): pass
    def rollback(self): pass


def test_conflicto_de_retroalimentacion_queda_en_la_bitacora():
    sesion = _Sesion()
    resultados = Mock()
    resultados.obtener_por_id.return_value = {
        "fecha_inferencia": datetime.now(timezone.utc) - timedelta(days=1), "id_activo_biologico": 876,
    }
    repo = Mock()
    repo.obtener_por_resultado_y_usuario.return_value = None
    repo.listar_por_resultado.return_value = [
        SimpleNamespace(estado_retroalimentacion="CORRECTO", id_usuario_veterinario=1)]

    def guardar(entidad):
        entidad.id_retroalimentacion = uuid.uuid4()
        return entidad

    repo.guardar.side_effect = guardar
    patologias = Mock()
    patologias.obtener_por_id.return_value = SimpleNamespace(es_activo=True)
    parametros = Mock()
    parametros.obtener.return_value = {"ventana_retroalimentacion_dias": SimpleNamespace(valor=90, minimo=None, maximo=None)}
    auditoria = SqlAlchemyEventoAuditoriaM04Repository(sesion, Mock(), reintentos=1, pausa_reintento=0)
    RegistrarRetroalimentacionUseCase(
        db=sesion, repo=repo, resultado_port=resultados, patologia_repo=patologias,
        auditoria_repo=auditoria, parametros_port=parametros,
    ).execute(RegistrarRetroalimentacionDTO(
        id_resultado_inferencia=uuid.uuid4(), id_activo_biologico=876,
        estado_retroalimentacion="INCORRECTO", diagnosticos_reales=[1],
    ), id_usuario_veterinario=2)

    tipos = [e.tipo_evento for e in sesion.guardados]
    assert tipos == ["RETROALIMENTACION_REGISTRADA", "CONFLICTO_RETROALIMENTACION"]
    payload = sesion.guardados[1].payload_evento
    assert payload["numero_retroalimentaciones"] == 2 and payload["activo_biologico_id"] == 876
    assert payload["estados_registrados"] == ["CORRECTO", "INCORRECTO"]


def test_hash_invalido_en_critical_failure_registra_hash_invalido_detectado():
    ctx, (canary, *_) = _distribuida()
    ctx.reportar(canary, "critical_failure", causa="HASH_INVALIDO", hash_recibido="abc")
    tipos = [e["tipo_evento"] for e in ctx.auditoria.eventos]
    assert tipos == ["DISTRIBUCION_FALLIDA", "HASH_INVALIDO_DETECTADO"]
    payload = ctx.auditoria.eventos[1]["payload_evento"]
    despliegue = ctx.despliegues.filas[canary]
    assert payload["hash_esperado"] == despliegue.hash_modelo_sha256 and payload["hash_recibido"] == "abc"
    assert (payload["device_id"], payload["id_version"]) == (despliegue.id_dispositivo_iot, despliegue.id_version_modelo)


def test_hash_invalido_en_rollback_tambien_se_registra():
    ctx, (canary, *_) = _distribuida()
    ctx.reportar(canary, "rollback", causa="HASH_INVALIDO")
    assert [e["tipo_evento"] for e in ctx.auditoria.eventos] == ["DISTRIBUCION_FALLIDA", "HASH_INVALIDO_DETECTADO"]
    assert ctx.despliegues.filas[canary].resultado_validacion_hash is False


def test_falla_sin_causa_de_hash_no_registra_hash_invalido():
    ctx, (canary, *_) = _distribuida()
    ctx.reportar(canary, "critical_failure", causa="ENERGIA_INSUFICIENTE")
    assert [e["tipo_evento"] for e in ctx.auditoria.eventos] == ["DISTRIBUCION_FALLIDA"]
