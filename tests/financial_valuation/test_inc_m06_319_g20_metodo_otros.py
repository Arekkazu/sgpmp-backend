# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-319-G20 RF-84: la confirmación rechaza campos desconocidos (método por componente) |
"""INC-M06-319-G20 / RF-84: «otros costos de disposición» siempre es MANUAL (metodo_costo_otros = ENUM (MANUAL)).

Antes, enviar metodo_costo_otros o costos_manuales.metodo_otros con PARAMETRIZADO respondía 201: el DTO
ignoraba los campos desconocidos. El método por componente no es un campo de la API (se deriva de si el
componente viene en costos_manuales), así que cualquier campo de método se rechaza con 400."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.financial_valuation.domain.services.nic41 import costos_venta
from src.financial_valuation.infrastructure.factories.m06_factory import M06
from src.financial_valuation.infrastructure.routers import m06_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers

JUSTIFICACION = "Costo de sacrificio en planta pactado con el comprador de la subasta."


class _Q:
    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return object()  # permiso concedido


@pytest.fixture
def cliente(monkeypatch):
    llamadas: list = []

    class _Caso:
        def execute(self, id_activo, id_usuario, **kwargs):
            llamadas.append(kwargs)
            return {"id_reconocimiento_inicial": 1}

    monkeypatch.setattr(M06, "confirmar_reconocimiento", lambda self: _Caso())
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(m06_router.router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *_a: _Q())
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, llamadas


@pytest.mark.parametrize("cuerpo, campo", [
    ({"metodo_costo_otros": "PARAMETRIZADO", "costos_manuales": {"otros": 500000}, "justificacion": JUSTIFICACION},
     "metodo_costo_otros"),
    ({"costos_manuales": {"otros": 500000, "metodo_otros": "PARAMETRIZADO"}, "justificacion": JUSTIFICACION},
     "costos_manuales.metodo_otros"),
    ({"metodo_costo_otros": "PARAMETRIZADO"}, "metodo_costo_otros"),
])
def test_marcar_otros_como_parametrizado_se_rechaza(cliente, cuerpo, campo) -> None:
    client, llamadas = cliente

    respuesta = client.post("/finanzas/reconocimientos/7", json=cuerpo)

    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "VAL_ENTRADA"
    assert campo in [f["field"] for f in respuesta.json()["fields"]]
    assert llamadas == []  # no se reconoce el activo


def test_otros_sin_justificacion_se_rechaza(cliente) -> None:
    client, llamadas = cliente

    respuesta = client.post("/finanzas/reconocimientos/7", json={"costos_manuales": {"otros": 500000}})

    assert respuesta.status_code == 400 and llamadas == []


def test_otros_con_justificacion_se_acepta_como_manual(cliente) -> None:
    client, llamadas = cliente

    respuesta = client.post("/finanzas/reconocimientos/7",
                            json={"costos_manuales": {"otros": 500000}, "justificacion": JUSTIFICACION})

    assert respuesta.status_code == 201
    assert llamadas[0]["costos_manuales"]["otros"] == Decimal("500000")
    costos = costos_venta(Decimal("10000000"), Decimal("0.01"), Decimal("0.02"), Decimal("0"), llamadas[0]["costos_manuales"])
    assert costos.metodos["otros"] == "MANUAL" and costos.otros == Decimal("500000")


def test_sin_costos_manuales_otros_no_se_deduce(cliente) -> None:
    client, llamadas = cliente

    assert client.post("/finanzas/reconocimientos/7", json={}).status_code == 201
    costos = costos_venta(Decimal("10000000"), Decimal("0.01"), Decimal("0.02"), Decimal("0"), llamadas[0]["costos_manuales"])
    assert costos.otros == Decimal("0") and "otros" not in costos.metodos  # «otros» nunca se parametriza
