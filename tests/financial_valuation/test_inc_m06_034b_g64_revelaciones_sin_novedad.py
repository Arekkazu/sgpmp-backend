# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-14 | destroyerban | INC-M06-034B-G64 RF-92: la declaración sin novedad no admite compromisos ni pignorados |
"""INC-M06-034B-G64 / RF-92 (TC-92-034): declarar «sin novedad» es afirmar que no hay compromisos ni activos
pignorados, así que ir junto con alguno es una contradicción que se rechaza con 400, antes de mirar el período."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from src.financial_valuation.infrastructure.dto.m06_dto import InformeRevelacionesDTO
from src.financial_valuation.infrastructure.routers import m06_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers

COMPROMISO = {"descripcion": "QA M06 contradiccion"}
PIGNORADO = {"id_activo_biologico": 7, "entidad_acreedora": "Banco Agrario"}


@pytest.mark.parametrize("cuerpo", [
    {"declaracion_sin_novedad": True, "compromisos_vigentes": [COMPROMISO]},
    {"declaracion_sin_novedad": True, "activos_pignorados": [PIGNORADO]},
    {"declaracion_sin_novedad": True, "compromisos_vigentes": [COMPROMISO], "activos_pignorados": [PIGNORADO]},
])
def test_sin_novedad_con_compromisos_o_pignorados_se_rechaza(cuerpo):
    with pytest.raises(PydanticValidationError) as error:
        InformeRevelacionesDTO.model_validate(cuerpo)
    assert "no puede ir junto con compromisos o activos pignorados" in str(error.value)


@pytest.mark.parametrize("cuerpo", [
    {"declaracion_sin_novedad": True},
    {"compromisos_vigentes": [COMPROMISO]},
    {"activos_pignorados": [PIGNORADO]},
    {"declaracion_sin_novedad": False, "compromisos_vigentes": [COMPROMISO], "activos_pignorados": [PIGNORADO]},
    {"declaracion_sin_novedad": True, "compromisos_vigentes": [], "activos_pignorados": []},
])
def test_combinaciones_coherentes_se_siguen_aceptando(cuerpo):
    InformeRevelacionesDTO.model_validate(cuerpo)


class _Q:
    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return object()  # permiso concedido


def test_contrato_http_400_antes_de_la_regla_del_periodo():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(m06_router.router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *_a: _Q())
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=9, id_token=1, id_rol=5, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)

    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = client.post("/finanzas/periodos/999999999/revelaciones",
                                json={"declaracion_sin_novedad": True, "compromisos_vigentes": [COMPROMISO]})

    assert respuesta.status_code == 400, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "VAL_ENTRADA"
    assert any("no puede ir junto con compromisos o activos pignorados" in f["message"] for f in cuerpo["fields"])
