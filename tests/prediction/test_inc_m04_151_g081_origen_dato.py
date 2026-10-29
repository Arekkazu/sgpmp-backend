# | Fecha      | Nombre   | Que se hizo                                          |
# |------------|----------|------------------------------------------------------|
# | 2026-10-25 | Arekkazu | INC-M04-151-G081 RF-73: origen_dato en la bitácora M04 |
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: conservar pruebas de origen con referencia valida. |
"""INC-M04-151-G081 (RF-73): ``origen_dato`` quedaba NULL en todos los eventos.

Es obligatorio en RF-73 (EDGE/BACKEND/HIBRIDO, dónde ocurrió el evento): se
deriva del actor si el emisor no lo da, y viaja también al respaldo local.
"""
from __future__ import annotations

import contextlib

import pytest

from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)


class _Sesion:
    def __init__(self, fallas: int = 0):
        self.fallas, self.flushes, self.guardados, self._pendiente = fallas, 0, [], None

    def begin_nested(self): return contextlib.nullcontext()
    def add(self, orm): self._pendiente = orm

    def flush(self):
        self.flushes += 1
        if self.flushes <= self.fallas:
            raise RuntimeError("could not connect to server")
        self.guardados.append(self._pendiente)


class _Respaldo:
    def __init__(self): self.eventos = []
    def guardar(self, evento): self.eventos.append(evento)


def _registrar(sesion, respaldo=None, **kw):
    repo = SqlAlchemyEventoAuditoriaM04Repository(sesion, respaldo or _Respaldo(), reintentos=1, pausa_reintento=0)
    repo.registrar(
        tipo_evento="VERSION_REGISTRADA", id_referencia="v1", payload_evento={"tipo_modelo": "INDIVIDUAL", "id_version": "v1"}, **kw,
    )


@pytest.mark.parametrize("tipo_actor, extra, esperado", [
    ("USUARIO", {"id_usuario": 1}, "BACKEND"),
    ("SISTEMA", {"id_sistema": "motor_inferencia"}, "BACKEND"),
    ("DISPOSITIVO_EDGE", {"id_sistema": "edge-01"}, "EDGE"),
    ("SISTEMA", {"id_sistema": "motor_inferencia", "origen_dato": "HIBRIDO"}, "HIBRIDO"),
])
def test_origen_dato_se_persiste(tipo_actor, extra, esperado):
    sesion = _Sesion()
    _registrar(sesion, tipo_actor=tipo_actor, **extra)
    assert sesion.guardados[0].origen_dato == esperado


def test_evento_invalido_y_respaldo_conservan_origen_dato():
    sesion = _Sesion()
    SqlAlchemyEventoAuditoriaM04Repository(sesion, _Respaldo(), reintentos=1, pausa_reintento=0).registrar(
        tipo_evento="VERSION_REGISTRADA", tipo_actor="USUARIO", id_usuario=1, payload_evento={},
    )
    assert sesion.guardados[0].tipo_evento == "AUDITORIA_EVENTO_INVALIDO"
    assert sesion.guardados[0].origen_dato == "BACKEND"

    respaldo = _Respaldo()
    _registrar(_Sesion(fallas=99), respaldo, tipo_actor="DISPOSITIVO_EDGE", id_sistema="edge-01")
    assert [e["origen_dato"] for e in respaldo.eventos] == ["EDGE", "BACKEND"]
