# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-14 | destroyerban | INC-M06-043B-G65 RF-92: monto de compromisos y garantías mayor que cero |
"""INC-M06-043B-G65 / RF-92 (TC-92-043): un compromiso vigente o una garantía con monto cero o negativo se
rechaza con 400 VAL_ENTRADA en su campo, antes de mirar el período; el monto sigue siendo opcional."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from src.financial_valuation.infrastructure.dto.m06_dto import CompromisoDTO, PignoracionDTO
from src.financial_valuation.infrastructure.routers import m06_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers

MENSAJE = "El monto debe ser mayor que cero."


@pytest.mark.parametrize("monto", [-1000, 0, "-0.0001"])
def test_compromiso_con_monto_no_positivo_se_rechaza(monto):
    with pytest.raises(PydanticValidationError) as error:
        CompromisoDTO(descripcion="Compromiso de venta", monto_estimado=monto)
    assert MENSAJE in str(error.value)


@pytest.mark.parametrize("monto", [-5, 0])
def test_garantia_con_monto_no_positivo_se_rechaza(monto):
    with pytest.raises(PydanticValidationError) as error:
        PignoracionDTO(id_activo_biologico=7, entidad_acreedora="Banco Agrario", monto_garantia=monto)
    assert MENSAJE in str(error.value)


def test_montos_positivos_y_vacios_se_siguen_aceptando():
    assert CompromisoDTO(descripcion="Compromiso", monto_estimado="1500.50").monto_estimado == Decimal("1500.50")
    assert CompromisoDTO(descripcion="Compromiso").monto_estimado is None
    assert PignoracionDTO(id_activo_biologico=7, entidad_acreedora="Banco", monto_garantia=1).monto_garantia == 1
    assert PignoracionDTO(id_activo_biologico=7, entidad_acreedora="Banco").monto_garantia is None


class _Q:
    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return object()  # permiso concedido


@pytest.mark.parametrize("monto", [-1000, 0])
def test_contrato_http_400_con_el_campo_indicado(monto):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(m06_router.router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *_a: _Q())
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)

    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = client.post("/finanzas/periodos/999999999/revelaciones", json={"compromisos_vigentes": [
            {"descripcion": "QA M06 compromiso negativo", "monto_estimado": monto, "contraparte": "Banco QA"}]})

    assert respuesta.status_code == 400, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "VAL_ENTRADA"
    assert cuerpo["fields"] == [{"field": "compromisos_vigentes.0.monto_estimado",
                                 "message": MENSAJE + " Si no lo conoce, déjelo vacío."}]
