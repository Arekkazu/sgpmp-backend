# | Fecha      | Nombre   | Que se hizo                                                           |
# |------------|----------|-----------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-227-G067 / INC-M04-228-G068 RF-72: estado literal y activo en BAJA |
"""RF-72: dominio literal de estado_retroalimentacion (#862) y activo en BAJA (#863)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.domain.entities.parametro_mlops import RF72_VENTANA, ParametroMLOps
from src.identity_access.infrastructure.dependencies import get_current_user
from src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case import (
    RegistrarRetroalimentacionUseCase,
)
from src.prediction.infrastructure.dto.registrar_retroalimentacion_dto import RegistrarRetroalimentacionDTO
from src.prediction.infrastructure.routers import retroalimentacion_clinica_router
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError


def _use_case(*, activo_en_baja=False):
    resultados = Mock()
    resultados.obtener_por_id.return_value = {
        "fecha_inferencia": datetime.now(timezone.utc) - timedelta(days=1),
        "id_activo_biologico": 885,
        "activo_en_baja": activo_en_baja,
    }
    repo = Mock()
    repo.obtener_por_resultado_y_usuario.return_value = None
    repo.listar_por_resultado.return_value = []
    repo.guardar.side_effect = lambda e: e
    parametros = Mock()
    parametros.obtener.return_value = {RF72_VENTANA: ParametroMLOps(RF72_VENTANA, 90, 7, 365)}
    return RegistrarRetroalimentacionUseCase(
        db=Mock(), repo=repo, resultado_port=resultados, patologia_repo=Mock(),
        auditoria_repo=Mock(), parametros_port=parametros,
    ), repo


def _dto(estado):
    return RegistrarRetroalimentacionDTO(
        id_resultado_inferencia=uuid.uuid4(), id_activo_biologico=885, estado_retroalimentacion=estado,
    )


@pytest.mark.parametrize("estado", ["correcto", "Correcto", 123, None, "", "DESCONOCIDO", [1], " CORRECTO"])
def test_estado_fuera_del_dominio_literal_es_422_sin_persistir(estado):
    use_case, repo = _use_case()
    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(_dto(estado), 7)
    assert (exc.value.status_code, exc.value.code) == (422, "ESTADO_RETROALIMENTACION_INVALIDO")
    repo.guardar.assert_not_called()


@pytest.mark.parametrize("estado", ["CORRECTO", "SIN_EVENTO"])
def test_estados_validos_se_registran(estado):
    use_case, repo = _use_case()
    assert use_case.execute(_dto(estado), 7).estado_retroalimentacion == estado
    repo.guardar.assert_called_once()


def test_activo_en_baja_rechaza_sin_persistir():
    use_case, repo = _use_case(activo_en_baja=True)
    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(_dto("CORRECTO"), 7)
    assert (exc.value.status_code, exc.value.code) == (422, "ACTIVO_EN_BAJA")
    repo.guardar.assert_not_called()


def _cliente() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(retroalimentacion_clinica_router.router)
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: None
    app.dependency_overrides.update({
        dep.dependency: (lambda: None)
        for ruta in retroalimentacion_clinica_router.router.routes for dep in ruta.dependencies
    })
    return TestClient(app, raise_server_exceptions=False)


def test_campo_ausente_es_422_identificando_el_campo():
    respuesta = _cliente().post("/prediccion/retroalimentacion", json={
        "id_resultado_inferencia": str(uuid.uuid4()), "id_activo_biologico": 885,
    })
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["fields"][0]["field"] == "estado_retroalimentacion"
