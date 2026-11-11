# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-08 | destroyerban | INC-M06-316-G16 RF-84: referencia documental de los costos manuales |
"""INC-M06-316-G16 / RF-84 R4: los costos de venta manuales exigen una referencia documental y la guardan.

Antes bastaba una justificación de 20 a 1.000 caracteres: comisiones a 250.000 sin documento respondían 201."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.financial_valuation.application.services.valorador import Valorador
from src.financial_valuation.application.use_cases.reconocimiento.confirmar_reconocimiento_use_case import (
    ConfirmarReconocimientoUseCase,
)
from src.financial_valuation.domain.services.precios import Precio
from src.financial_valuation.infrastructure.routers import m06_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import ValidationError

D = Decimal
JUSTIFICACION = "Comisión pactada con el comprador de la subasta de noviembre por encima del parámetro."


def _caso() -> ConfirmarReconocimientoUseCase:
    # La regla va antes de tocar repositorios: si llegara a usarlos, la prueba fallaría con AttributeError.
    return ConfirmarReconocimientoUseCase(db=None, activos=None, valoraciones=None, proponedor=None, contabilizador=None)


@pytest.mark.parametrize("referencia", [None, "", "   "])
def test_costos_manuales_sin_referencia_se_rechazan(referencia) -> None:
    with pytest.raises(ValidationError) as excinfo:
        _caso().execute(1, 9, costos_manuales={"comisiones": D("250000"), "transporte": None},
                        justificacion=JUSTIFICACION, referencia_documental=referencia)

    assert excinfo.value.code == "REFERENCIA_DOCUMENTAL_REQUERIDA"
    assert excinfo.value.field == "referencia_documental"
    assert excinfo.value.status_code == 400


def test_sin_costos_manuales_no_se_exige_referencia() -> None:
    caso = _caso()
    caso.activos = SimpleNamespace(obtener=lambda _id: None)  # llega hasta la búsqueda del activo

    with pytest.raises(Exception) as excinfo:
        caso.execute(1, 9, costos_manuales={"comisiones": None})

    assert getattr(excinfo.value, "code", None) == "ACTIVO_NO_ENCONTRADO"


class _Q:
    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return object()  # permiso concedido


def test_contrato_http_400_sin_referencia_documental() -> None:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(m06_router.router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *_a: _Q())
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)

    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = client.post("/finanzas/reconocimientos/1", json={
            "costos_manuales": {"comisiones": 250000}, "justificacion": JUSTIFICACION})

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "REFERENCIA_DOCUMENTAL_REQUERIDA"
    assert [f["field"] for f in cuerpo["fields"]] == ["referencia_documental"]


def _valorar(costos_manuales, referencia):
    precio = Precio(id_precio_mercado=12, id_especie=2, categoria="PESO_KG", precio_unitario=D("25000"),
                    unidad_medida="kg", fuente="MERCADO_ACTIVO", fecha_vigencia=date(2026, 9, 1))
    config = SimpleNamespace(
        costos_venta_vigentes=lambda _e: SimpleNamespace(pct_transporte=D("0.01"), pct_comisiones=D("0.02"),
                                                         pct_impuestos=D("0"), id_parametro_costo_venta=1),
        parametro_especie=lambda _e: None)
    activo = SimpleNamespace(id_activo_biologico=7, identificador="BOV-007", especie="Bovino", id_especie=2,
                             cabezas=1, id_evento_peso=None, magnitud=lambda _c: (D("400"), "kg"))
    return Valorador(None, config).valorar(activo, date(2026, 11, 8), 3, 9, precio_congelado=precio,
                                           costos_manuales=costos_manuales, justificacion=JUSTIFICACION,
                                           referencia_documental=referencia).calculo


def test_el_calculo_guarda_la_referencia_de_los_costos_manuales() -> None:
    calculo = _valorar({"comisiones": D("250000")}, "Factura FE-1234 Subastas del Huila")

    assert calculo.json_metodo_costo["referencia_documental"] == "Factura FE-1234 Subastas del Huila"
    assert calculo.json_metodo_costo["comisiones"] == "MANUAL"
    assert calculo.costo_comisiones == D("250000") and calculo.valor_neto == D("9650000")
    assert calculo.justificacion == JUSTIFICACION


def test_sin_costos_manuales_el_calculo_no_lleva_referencia() -> None:
    calculo = _valorar(None, None)

    assert "referencia_documental" not in calculo.json_metodo_costo
