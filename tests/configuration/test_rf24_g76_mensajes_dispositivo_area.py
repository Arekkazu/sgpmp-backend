"""Issue #506: contrato HTTP de G76 con repositorios en memoria, sin BD."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.domain.entities.calibracion import Calibracion
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.entities.rango_calibracion import RangoCalibracion
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.routers import sensor_router
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared import rbac
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers


def _cliente(monkeypatch, *, activo=True, serial="IOT-G76-6", id_sensor=6,
             id_area=1, area_asociada=1, ids_historial=(14, 13, 12, 11, 10),
             fallo_auditoria=False):
    dispositivo = DispositivoIot.crear(
        serial=SerialDispositivo(serial), descripcion="Dispositivo de prueba G76",
        id_infraestructura=id_area, id_tipo_dispositivo=1, es_activo=activo,
    )
    dispositivo.id_dispositivo_iot = 3
    sensor = SimpleNamespace(id_dispositivo_iot=3, categoria="TEMPERATURA")
    asociacion = (SimpleNamespace(id_infraestructura=area_asociada)
                  if area_asociada is not None else None)
    fecha = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
    historial = [
        Calibracion.crear(
            id_dispositivo_iot=3, id_sensor=id_sensor, valor_referencia=Decimal("25"),
            fecha_calibracion=fecha, id_usuario=7,
        ) for _ in ids_historial
    ]
    for calibracion, id_calibracion in zip(historial, ids_historial):
        calibracion.id_calibracion = id_calibracion

    def guardar(calibracion):
        calibracion.id_calibracion = 99
        historial.append(calibracion)
        return calibracion

    db = Mock()
    calibraciones = Mock()
    calibraciones.guardar.side_effect = guardar
    calibraciones.listar_por_sensor.side_effect = lambda _: list(historial)
    dispositivos = Mock()
    dispositivos.obtener_por_id.return_value = dispositivo
    sensores = Mock()
    sensores.obtener_por_id.return_value = sensor
    asociaciones = Mock()
    asociaciones.obtener_asociacion_activa.return_value = asociacion
    rango = RangoCalibracion("TEMPERATURA", Decimal("0"), Decimal("45"))
    rangos = Mock()
    rangos.obtener_por_categoria.return_value = rango
    auditoria = Mock()
    eventos = Mock()
    if fallo_auditoria:
        eventos.registrar.side_effect = RuntimeError("Auditoría no disponible")
    alcance = Mock()
    alcance.listar_ids_fincas_permitidas.return_value = [21]
    for nombre, repo in (
        ("SqlAlchemySensorRepository", sensores),
        ("SqlAlchemyDispositivoIotRepository", dispositivos),
        ("SqlAlchemySensorAreaRepository", asociaciones),
        ("SqlAlchemyCalibracionRepository", calibraciones),
        ("SqlAlchemyRangoCalibracionRepository", rangos),
        ("SqlAlchemyAuditoriaCalibracionRepository", auditoria),
        ("SqlAlchemyEventoRepository", eventos),
        ("AlcanceFincaAdapter", alcance),
    ):
        monkeypatch.setattr(sensor_router, nombre, lambda _db, repo=repo: repo)
    monkeypatch.setattr(rbac, "tiene_permiso", lambda *args, **kwargs: True)
    usuario = UsuarioActual(id_usuario=7, id_token=1, id_rol=4, id_estado_cuenta=2)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(sensor_router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: usuario
    return SimpleNamespace(
        cliente=TestClient(app, raise_server_exceptions=False), db=db,
        calibraciones=calibraciones, dispositivos=dispositivos, auditoria=auditoria,
        eventos=eventos, asociaciones=asociaciones, rangos=rangos, rango=rango,
        dispositivo=dispositivo, asociacion=asociacion,
        url=f"/configuracion/sensores/{id_sensor}",
        body={"id_dispositivo_iot": 3, "id_infraestructura": id_area,
              "valor_referencia": "25.0000", "modo_calibracion": "SENSOR",
              "fecha_calibracion": fecha.isoformat()},
    )


def _historial(estado):
    respuesta = estado.cliente.get(f"{estado.url}/calibraciones")
    assert respuesta.status_code == 200
    return respuesta.json()


_ESCENARIOS = [
    pytest.param(
        dict(activo=False, serial="IOT-INACTIVO-6", ids_historial=()),
        422, "DISPOSITIVO_INACTIVO",
        "Operación rechazada: El dispositivo IOT-INACTIVO-6 está inactivo. "
        "Debe activar el dispositivo antes de proceder con el registro de nuevos parámetros de calibración.",
        id="TC-M09-146-historial-vacio",
    ),
    pytest.param(
        dict(activo=False, serial="EDGE_INACTIVO_26", id_sensor=26, id_area=17,
             area_asociada=17),
        422, "DISPOSITIVO_INACTIVO",
        "Operación rechazada: El dispositivo EDGE_INACTIVO_26 está inactivo. "
        "Debe activar el dispositivo antes de proceder con el registro de nuevos parámetros de calibración.",
        id="TC-M09-146-otro-serial-con-historial",
    ),
    pytest.param(
        dict(area_asociada=2), 400, "SENSOR_AREA_INVALIDA",
        "Conflicto de ubicación: El sensor 6 no está asociado al área 1. "
        "Verifique la ubicación física y lógica del equipo antes de calibrar.",
        id="TC-M09-147-area-distinta",
    ),
    pytest.param(
        dict(id_sensor=26, id_area=17, area_asociada=None),
        400, "SENSOR_AREA_INVALIDA",
        "Conflicto de ubicación: El sensor 26 no está asociado al área 17. "
        "Verifique la ubicación física y lógica del equipo antes de calibrar.",
        id="TC-M09-147-sin-asociacion-vigente",
    ),
]


@pytest.mark.parametrize("configuracion,http,codigo,mensaje", _ESCENARIOS)
def test_rechazo_contractual_conserva_historial(monkeypatch, configuracion, http, codigo, mensaje):
    estado = _cliente(monkeypatch, **configuracion)
    with estado.cliente:
        antes = _historial(estado)
        dispositivo_antes = estado.dispositivo._snapshot()
        asociacion_antes = vars(estado.asociacion).copy() if estado.asociacion else None
        rango_antes = vars(estado.rango).copy()
        respuesta = estado.cliente.post(f"{estado.url}/calibrar", json=estado.body)
        assert respuesta.status_code == http
        cuerpo = respuesta.json()
        assert cuerpo["error_code"] == codigo
        assert cuerpo["message"] == mensaje
        assert cuerpo["fields"] == (
            [{"field": "id_infraestructura", "message": mensaje}]
            if codigo == "SENSOR_AREA_INVALIDA" else []
        )
        assert _historial(estado) == antes
    assert estado.dispositivo._snapshot() == dispositivo_antes
    assert (vars(estado.asociacion) if estado.asociacion else None) == asociacion_antes
    assert vars(estado.rango) == rango_antes
    estado.calibraciones.guardar.assert_not_called()
    estado.auditoria.registrar.assert_not_called()
    estado.rangos.obtener_por_categoria.assert_not_called()
    estado.eventos.registrar.assert_called_once()
    evento = estado.eventos.registrar.call_args.kwargs
    assert evento["exitoso"] is False
    assert evento["detalle"]["codigo_error"] == codigo
    assert evento["detalle"]["codigo_http"] == http
    assert evento["detalle"]["motivo"] == mensaje
    estado.db.commit.assert_called_once()  # Confirma únicamente la auditoría del rechazo.
    estado.db.rollback.assert_not_called()
    estado.dispositivos.obtener_por_id.assert_called_with(3, ids_fincas_permitidas=[21])


@pytest.mark.parametrize("configuracion,http,codigo,mensaje", [_ESCENARIOS[0], _ESCENARIOS[2]])
def test_fallo_auditoria_conserva_rechazo(monkeypatch, configuracion, http, codigo, mensaje):
    estado = _cliente(monkeypatch, **configuracion, fallo_auditoria=True)
    with estado.cliente:
        antes = _historial(estado)
        respuesta = estado.cliente.post(f"{estado.url}/calibrar", json=estado.body)
        assert respuesta.status_code == http
        assert respuesta.json()["error_code"] == codigo
        assert respuesta.json()["message"] == mensaje
        assert _historial(estado) == antes
    estado.calibraciones.guardar.assert_not_called()
    estado.auditoria.registrar.assert_not_called()
    estado.db.commit.assert_not_called()
    estado.db.rollback.assert_called_once()


@pytest.mark.parametrize("valor", ["0.0000", "25.0000", "45.0000"])
def test_dispositivo_activo_y_area_asociada_permiten_calibrar(monkeypatch, valor):
    estado = _cliente(monkeypatch)
    with estado.cliente:
        antes = _historial(estado)
        respuesta = estado.cliente.post(f"{estado.url}/calibrar", json={**estado.body, "valor_referencia": valor})
        assert respuesta.status_code == 201
        assert respuesta.json()["id_calibracion"] == 99
        assert respuesta.json()["valor_referencia"] == float(valor)
        despues = _historial(estado)
        assert despues["total"] == antes["total"] + 1
        assert despues["items"][:-1] == antes["items"]
    estado.calibraciones.guardar.assert_called_once()
    estado.auditoria.registrar.assert_called_once()
    # RF-10 (#508): la calibración exitosa deja un único evento CALIBRACION_EXITOSA.
    estado.eventos.registrar.assert_called_once()
    assert estado.eventos.registrar.call_args.kwargs["tipo_evento"] == 30
    assert estado.eventos.registrar.call_args.kwargs["exitoso"] is True
    estado.db.commit.assert_called_once()
    estado.db.rollback.assert_not_called()
