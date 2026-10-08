"""INC-M09-69-G75: contrato HTTP de calibración, con persistencia en memoria."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.domain.entities.calibracion import Calibracion
from src.configuration.domain.entities.rango_calibracion import RangoCalibracion
from src.configuration.infrastructure.routers import sensor_router
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared import rbac
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers


@pytest.fixture
def calibracion_http(monkeypatch):
    """Router, DTO, caso de uso y handlers reales; repositorios sin conexión externa."""
    db = Mock()
    fecha = datetime(2026, 10, 7, tzinfo=timezone.utc)
    historial = []
    for id_calibracion in range(10, 15):
        calibracion = Calibracion.crear(
            id_dispositivo_iot=1, id_sensor=1, valor_referencia=Decimal("20"),
            fecha_calibracion=fecha, id_usuario=1, ganancia=Decimal("1"),
            offset=Decimal("20"), observaciones="Histórico existente",
        )
        calibracion.id_calibracion = id_calibracion
        historial.append(calibracion)

    def guardar(calibracion):
        calibracion.id_calibracion = max(c.id_calibracion for c in historial) + 1
        historial.append(calibracion)
        return calibracion

    calibraciones = Mock()
    calibraciones.guardar.side_effect = guardar
    calibraciones.listar_por_sensor.side_effect = lambda _: list(historial)
    rango = RangoCalibracion("TEMPERATURA", Decimal("0.0000"), Decimal("45.0000"))
    rangos = Mock()
    rangos.obtener_por_categoria.return_value = rango
    sensores = Mock()
    sensores.obtener_por_id.return_value = SimpleNamespace(
        id_dispositivo_iot=1, categoria="TEMPERATURA",
    )
    dispositivos = Mock()
    dispositivos.obtener_por_id.return_value = SimpleNamespace(es_activo=True)
    asociaciones = Mock()
    asociaciones.obtener_asociacion_activa.return_value = SimpleNamespace(id_infraestructura=1)
    auditoria, eventos = Mock(), Mock()
    for nombre, repo in (
        ("SqlAlchemySensorRepository", sensores),
        ("SqlAlchemyDispositivoIotRepository", dispositivos),
        ("SqlAlchemySensorAreaRepository", asociaciones),
        ("SqlAlchemyCalibracionRepository", calibraciones),
        ("SqlAlchemyRangoCalibracionRepository", rangos),
        ("SqlAlchemyAuditoriaCalibracionRepository", auditoria),
        ("SqlAlchemyEventoRepository", eventos),
    ):
        monkeypatch.setattr(sensor_router, nombre, lambda db, repo=repo: repo)
    monkeypatch.setattr(rbac, "tiene_permiso", lambda *args, **kwargs: True)
    monkeypatch.setattr(sensor_router, "_alcance", lambda db, usuario: [1])

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(sensor_router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2,
    )
    with TestClient(app) as cliente:
        yield SimpleNamespace(
            cliente=cliente, db=db, calibraciones=calibraciones,
            auditoria=auditoria, eventos=eventos, rango=rango,
        )


def _payload(valor, **extras):
    return {
        "id_dispositivo_iot": 1, "id_infraestructura": 1,
        "valor_referencia": valor, "fecha_calibracion": "2026-10-07T00:00:00Z",
        "modo_calibracion": "SENSOR", **extras,
    }


def _historial(cliente):
    respuesta = cliente.get("/configuracion/sensores/1/calibraciones")
    assert respuesta.status_code == 200
    return respuesta.json()


@pytest.mark.parametrize(
    ("valor", "codigo", "mensaje"),
    [
        (-0.0001, "VALOR_FUERA_DE_RANGO",
         "Valor fuera de límites: El ajuste de -0.0001 excede los rangos de seguridad "
         "para la variable TEMPERATURA. Verifique el estándar de calibración utilizado."),
        (45.0001, "VALOR_FUERA_DE_RANGO",
         "Valor fuera de límites: El ajuste de 45.0001 excede los rangos de seguridad "
         "para la variable TEMPERATURA. Verifique el estándar de calibración utilizado."),
        ("", "VALOR_CALIBRACION_INVALIDO",
         "Error de formato: El valor de referencia debe ser un número decimal válido. "
         "Verifique la entrada ''."),
        (None, "VALOR_CALIBRACION_INVALIDO",
         "Error de formato: El valor de referencia debe ser un número decimal válido. "
         "Verifique la entrada 'null'."),
        ("abc", "VALOR_CALIBRACION_INVALIDO",
         "Error de formato: El valor de referencia debe ser un número decimal válido. "
         "Verifique la entrada 'abc'."),
    ],
    ids=["LOW", "HIGH", "EMPTY", "NULL", "ABC"],
)
def test_rechazo_con_mensaje_exacto_sin_alterar_historial(
    calibracion_http, valor, codigo, mensaje,
):
    estado = calibracion_http
    antes = _historial(estado.cliente)
    respuesta = estado.cliente.post("/configuracion/sensores/1/calibrar", json=_payload(valor))
    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == codigo
    assert cuerpo["message"] == mensaje
    assert cuerpo["fields"] == [{"field": "valor_referencia", "message": mensaje}]
    estado.calibraciones.guardar.assert_not_called()
    estado.auditoria.registrar.assert_not_called()
    assert _historial(estado.cliente) == antes
    assert estado.rango == RangoCalibracion("TEMPERATURA", Decimal("0.0000"), Decimal("45.0000"))
    estado.eventos.registrar.assert_called_once()
    evento = estado.eventos.registrar.call_args.kwargs
    assert evento["exitoso"] is False
    assert evento["detalle"]["codigo_error"] == codigo
    assert evento["detalle"]["motivo"] == mensaje


@pytest.mark.parametrize("valor", ["0.0000", "45.0000"], ids=["MINIMO", "MAXIMO"])
def test_limites_validos_conservan_201_y_el_historial(calibracion_http, valor):
    estado = calibracion_http
    antes = _historial(estado.cliente)
    respuesta = estado.cliente.post("/configuracion/sensores/1/calibrar", json=_payload(valor))
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert Decimal(cuerpo["valor_referencia"]) == Decimal(valor)
    assert Decimal(cuerpo["offset"]) == Decimal(valor)
    estado.calibraciones.guardar.assert_called_once()
    estado.auditoria.registrar.assert_called_once()
    estado.eventos.registrar.assert_not_called()
    estado.db.commit.assert_called_once()
    estado.db.rollback.assert_not_called()
    despues = _historial(estado.cliente)
    assert despues["total"] == antes["total"] + 1
    assert despues["items"][:-1] == antes["items"]
    assert despues["items"][-1]["id_calibracion"] == cuerpo["id_calibracion"]


def test_offset_fuera_de_rango_conserva_rechazo_y_campo(calibracion_http):
    estado = calibracion_http
    respuesta = estado.cliente.post(
        "/configuracion/sensores/1/calibrar", json=_payload(20, offset=45.0001),
    )
    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "VALOR_FUERA_DE_RANGO"
    assert cuerpo["fields"][0]["field"] == "offset"
    estado.calibraciones.guardar.assert_not_called()


def test_fallo_auditoria_de_rechazo_conserva_400_y_mensaje(calibracion_http):
    estado = calibracion_http
    estado.eventos.registrar.side_effect = RuntimeError("Auditoría no disponible")
    respuesta = estado.cliente.post("/configuracion/sensores/1/calibrar", json=_payload(None))
    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "VALOR_CALIBRACION_INVALIDO"
    assert respuesta.json()["message"] == (
        "Error de formato: El valor de referencia debe ser un número decimal válido. "
        "Verifique la entrada 'null'."
    )
    estado.calibraciones.guardar.assert_not_called()
    estado.db.rollback.assert_called_once()
