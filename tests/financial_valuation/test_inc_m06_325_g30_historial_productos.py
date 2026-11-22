# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-325-G30 RF-85 RNF-85-05: historial de productos con filtros, evento y usuario |
"""INC-M06-325-G30 / RF-85 RNF-85-05: el historial de productos agrícolas se filtra por activo, período, tipo de
producto y rango de valores, y cada registro trae su evento productivo y el usuario.

Antes, GET /finanzas/periodos/{id}/productos no declaraba ningún parámetro de consulta y no devolvía
id_evento_productivo ni el usuario."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.financial_valuation.application.use_cases.valoracion.consultar_productos_agricolas_use_case import (
    ConsultarProductosAgricolasUseCase,
)
from src.financial_valuation.infrastructure.factories import m06_factory
from src.financial_valuation.infrastructure.routers import m06_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import ValidationError


class _Q:
    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return object()  # permiso concedido


@pytest.fixture
def cliente(monkeypatch):
    consultas: list[dict] = []
    monkeypatch.setattr(m06_factory.M06, "valoraciones", SimpleNamespace(
        productos_agricolas=lambda filtros: consultas.append(filtros) or [{"id_evento_productivo": 500}]))
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(m06_router.router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *_a: _Q())
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, consultas


def test_el_listado_del_periodo_acepta_los_filtros(cliente) -> None:
    client, consultas = cliente

    respuesta = client.get("/finanzas/periodos/4/productos", params={
        "tipo": "PRODUCTO_PERIODICO", "id_activo_biologico": 7, "id_especie": 2, "producto_agricola": "Leche",
        "valor_min": "100000", "valor_max": "700000"})

    assert respuesta.status_code == 200 and respuesta.json() == [{"id_evento_productivo": 500}]
    assert consultas == [{"tipo": "PRODUCTO_PERIODICO", "id_activo_biologico": 7, "id_especie": 2,
                          "producto_agricola": "Leche", "valor_min": Decimal("100000"), "valor_max": Decimal("700000"),
                          "id_periodo_contable": 4}]


def test_historial_completo_sin_periodo(cliente) -> None:
    client, consultas = cliente

    assert client.get("/finanzas/productos", params={"tipo": "PRODUCTO_DE_CONSUMO"}).status_code == 200
    assert consultas[0]["tipo"] == "PRODUCTO_DE_CONSUMO" and consultas[0]["id_periodo_contable"] is None


@pytest.mark.parametrize("params, campo", [
    ({"tipo": "LECHE"}, "tipo"),
    ({"valor_min": "-1"}, "valor_min"),
    ({"valor_max": "abc"}, "valor_max"),
    ({"id_activo_biologico": 0}, "id_activo_biologico"),
])
def test_un_filtro_fuera_del_catalogo_responde_400(cliente, params, campo) -> None:
    client, consultas = cliente

    respuesta = client.get("/finanzas/productos", params=params)

    assert respuesta.status_code == 400 and respuesta.json()["error_code"] == "VAL_ENTRADA"
    assert campo in [f["field"] for f in respuesta.json()["fields"]] and consultas == []


def test_rango_invertido_responde_400(cliente) -> None:
    client, consultas = cliente

    respuesta = client.get("/finanzas/productos", params={"valor_min": "700000", "valor_max": "100000"})

    assert respuesta.status_code == 400 and respuesta.json()["error_code"] == "RANGO_VALOR_INVALIDO"
    assert [f["field"] for f in respuesta.json()["fields"]] == ["valor_min"] and consultas == []


def test_rango_igual_es_valido() -> None:
    caso = ConsultarProductosAgricolasUseCase(SimpleNamespace(productos_agricolas=lambda f: [f]))
    filtros = {"valor_min": Decimal("5"), "valor_max": Decimal("5")}
    assert caso.execute(filtros) == [filtros]
    with pytest.raises(ValidationError):
        caso.execute({"valor_min": Decimal("6"), "valor_max": Decimal("5")})
