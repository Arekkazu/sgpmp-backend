# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-14 | destroyerban | INC-M06-361-G24 RF-85 FA-4: la baja del activo cosechado corre en la misma sesión de M06 |
"""INC-M06-361-G24 (sin BD): la baja en M02 del activo cosechado al 100 % usa la sesión de M06, como usuario de
servicio. Una sesión aparte no ve lo que M06 tiene en su transacción externa (sandbox de QA) y M02 respondía
que el activo no existía. El flujo completo contra PostgreSQL está en la prueba de integración de la incidencia."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from unittest.mock import Mock

import pytest

from src.financial_valuation.infrastructure.adapters import baja_activo_m02_adapter as adaptador
from src.shared.errors import NotFoundError


@pytest.fixture
def entorno(monkeypatch):
    registro = {"identidad": [], "casos": []}

    @contextmanager
    def como_sistema(db):
        registro["identidad"].append(("sistema", db))
        try:  # como el real: la identidad se restaura también si el bloque falla
            yield
        finally:
            registro["identidad"].append(("restaurada", db))

    class _Caso:
        def __init__(self, db, **_repos):
            self.db = db
            registro["casos"].append(self)
            self.error = registro.get("error")

        def execute(self, id_activo, dto, usuario):
            self.llamada = (id_activo, dto, usuario)
            if self.error:
                raise self.error

    monkeypatch.setattr(adaptador, "como_sistema", como_sistema)
    monkeypatch.setattr(adaptador, "id_usuario_servicio", lambda _db: 99)
    monkeypatch.setattr(adaptador, "RegistrarEventoBajaUseCase", _Caso)
    return registro


def test_la_baja_usa_la_misma_sesion_como_usuario_de_servicio(entorno):
    db = Mock()
    assert adaptador.BajaActivoM02Adapter(db).dar_de_baja_por_cosecha(7, date(2026, 11, 13), "Cosechado") is None
    (caso,) = entorno["casos"]
    assert caso.db is db
    id_activo, dto, usuario = caso.llamada
    assert (id_activo, dto.tipo_baja, dto.fecha_baja, usuario.id_usuario) == (7, "sacrificio", date(2026, 11, 13), 99)
    assert entorno["identidad"] == [("sistema", db), ("restaurada", db)]
    db.close.assert_not_called()  # la sesión es de M06: el adaptador no la cierra


def test_si_m02_rechaza_devuelve_su_mensaje_sin_tocar_la_transaccion(entorno):
    entorno["error"] = NotFoundError(code="ACTIVO_NO_ENCONTRADO", message="El activo biológico con id 7 no existe.")
    db = Mock()
    assert adaptador.BajaActivoM02Adapter(db).dar_de_baja_por_cosecha(7, date(2026, 11, 13), "x") == (
        "El activo biológico con id 7 no existe.")
    db.rollback.assert_not_called()  # el caso de uso de M02 ya revirtió lo suyo
    assert entorno["identidad"][-1] == ("restaurada", db)


def test_un_error_tecnico_revierte_y_devuelve_un_mensaje_legible(entorno):
    entorno["error"] = RuntimeError("SQL interno")
    db = Mock()
    mensaje = adaptador.BajaActivoM02Adapter(db).dar_de_baja_por_cosecha(7, date(2026, 11, 13), "x")
    assert mensaje == "No se pudo registrar la baja en Activos biológicos por un error técnico."
    db.rollback.assert_called_once()
