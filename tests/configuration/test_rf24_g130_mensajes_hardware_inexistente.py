"""#509: contrato HTTP de hardware inexistente; repositorios en memoria, sin BD."""
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


MENSAJE_ESPERADO = (
    "Error de referencia: El sensor o dispositivo especificado no existe. "
    "No se puede registrar una calibración sobre un hardware inexistente."
)


def _cliente(monkeypatch, *, fallo_auditoria=False, alcance=None):
    fecha = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
    historial = []
    for id_calibracion in (15, 14, 13, 12, 11, 10):
        cal = Calibracion.crear(
            id_dispositivo_iot=3, id_sensor=6, valor_referencia=Decimal("22.5000"),
            fecha_calibracion=fecha, id_usuario=4,
        )
        cal.id_calibracion = id_calibracion
        historial.append(cal)

    sensores = Mock()
    sensores.obtener_por_id.side_effect = lambda id_sensor: (
        SimpleNamespace(id_dispositivo_iot=3, categoria="TEMPERATURA")
        if id_sensor == 6 else None
    )
    dispositivos = Mock()
    dispositivos.obtener_por_id.side_effect = lambda id_dispositivo, ids_fincas_permitidas=None: (
        SimpleNamespace(es_activo=True)
        if id_dispositivo == 3 and (ids_fincas_permitidas is None or 21 in ids_fincas_permitidas)
        else None
    )
    asociaciones = Mock()
    asociaciones.obtener_asociacion_activa.return_value = SimpleNamespace(id_infraestructura=1)
    calibraciones = Mock()
    calibraciones.listar_por_sensor.side_effect = lambda id_sensor: [
        cal for cal in historial if cal.id_sensor == id_sensor
    ]

    def guardar(calibracion):
        calibracion.id_calibracion = 16
        historial.append(calibracion)
        return calibracion

    calibraciones.guardar.side_effect = guardar
    rangos = Mock()
    rangos.obtener_por_categoria.return_value = RangoCalibracion(
        "TEMPERATURA", Decimal("0"), Decimal("45"),
    )
    auditoria, eventos, db = Mock(), Mock(), Mock()
    if fallo_auditoria:
        eventos.registrar.side_effect = RuntimeError("Auditoría no disponible")
    fincas = Mock()
    fincas.listar_ids_fincas_permitidas.return_value = alcance
    for nombre, repo in (
        ("SqlAlchemySensorRepository", sensores),
        ("SqlAlchemyDispositivoIotRepository", dispositivos),
        ("SqlAlchemySensorAreaRepository", asociaciones),
        ("SqlAlchemyCalibracionRepository", calibraciones),
        ("SqlAlchemyRangoCalibracionRepository", rangos),
        ("SqlAlchemyAuditoriaCalibracionRepository", auditoria),
        ("SqlAlchemyEventoRepository", eventos),
        ("AlcanceFincaAdapter", fincas),
    ):
        monkeypatch.setattr(sensor_router, nombre, lambda _db, repo=repo: repo)
    monkeypatch.setattr(rbac, "tiene_permiso", lambda *args, **kwargs: True)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(sensor_router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=4, id_token=1, id_rol=4, id_estado_cuenta=2,
    )
    return SimpleNamespace(
        cliente=TestClient(app, raise_server_exceptions=False), db=db, sensores=sensores,
        dispositivos=dispositivos, asociaciones=asociaciones, calibraciones=calibraciones,
        rangos=rangos, auditoria=auditoria, eventos=eventos, historial=historial,
        body={"id_dispositivo_iot": 3, "id_infraestructura": 1,
              "valor_referencia": "22.5000", "modo_calibracion": "SENSOR",
              "fecha_calibracion": fecha.isoformat()},
    )


def _historial(estado, id_sensor):
    respuesta = estado.cliente.get(f"/configuracion/sensores/{id_sensor}/calibraciones")
    assert respuesta.status_code == 200
    return respuesta.json()


@pytest.mark.parametrize("fallo_auditoria", [False, True], ids=["auditoria-ok", "auditoria-falla"])
@pytest.mark.parametrize("id_sensor,id_dispositivo,codigo", [
    pytest.param(6, 999999, "DISPOSITIVO_NO_ENCONTRADO", id="TC-M09-256"),
    pytest.param(999999, 3, "SENSOR_NO_ENCONTRADO", id="TC-M09-257"),
])
def test_hardware_inexistente_conserva_404_e_historial(
    monkeypatch, id_sensor, id_dispositivo, codigo, fallo_auditoria,
):
    estado = _cliente(monkeypatch, fallo_auditoria=fallo_auditoria)
    with estado.cliente:
        antes = {sensor: _historial(estado, sensor) for sensor in (6, 999999)}
        assert antes[6]["total"] == 6
        assert [item["id_calibracion"] for item in antes[6]["items"]] == [15, 14, 13, 12, 11, 10]
        assert antes[999999] == {"total": 0, "items": []}
        respuesta = estado.cliente.post(
            f"/configuracion/sensores/{id_sensor}/calibrar",
            json={**estado.body, "id_dispositivo_iot": id_dispositivo},
        )
        assert respuesta.status_code == 404
        cuerpo = respuesta.json()
        assert cuerpo["error_code"] == codigo
        assert cuerpo["message"] == MENSAJE_ESPERADO
        assert cuerpo["fields"] == [] and "id_calibracion" not in cuerpo
        assert {sensor: _historial(estado, sensor) for sensor in antes} == antes
    estado.calibraciones.guardar.assert_not_called()
    estado.auditoria.registrar.assert_not_called()
    estado.asociaciones.obtener_asociacion_activa.assert_not_called()
    estado.rangos.obtener_por_categoria.assert_not_called()
    estado.dispositivos.obtener_por_id.assert_called_once_with(
        id_dispositivo, ids_fincas_permitidas=None,
    )
    if id_dispositivo == 3:
        estado.sensores.obtener_por_id.assert_called_once_with(id_sensor)
    else:
        estado.sensores.obtener_por_id.assert_not_called()
    estado.eventos.registrar.assert_called_once()
    evento = estado.eventos.registrar.call_args.kwargs
    assert evento["tipo_evento"] == 29 and evento["exitoso"] is False
    assert evento["detalle"]["codigo_error"] == codigo
    assert evento["detalle"]["codigo_http"] == 404
    assert evento["detalle"]["motivo"] == MENSAJE_ESPERADO
    assert evento["detalle"]["id_sensor"] == id_sensor
    assert evento["detalle"]["id_dispositivo_iot"] == id_dispositivo
    if fallo_auditoria:
        estado.db.commit.assert_not_called()
        estado.db.rollback.assert_called_once()
    else:
        estado.db.commit.assert_called_once()  # Confirma exclusivamente el evento de rechazo.
        estado.db.rollback.assert_not_called()


def test_dispositivo_fuera_de_alcance_sigue_oculto(monkeypatch):
    estado = _cliente(monkeypatch, alcance=[])
    with estado.cliente:
        respuesta = estado.cliente.post("/configuracion/sensores/6/calibrar", json=estado.body)
    assert respuesta.status_code == 404
    assert respuesta.json()["error_code"] == "DISPOSITIVO_NO_ENCONTRADO"
    assert respuesta.json()["message"] == MENSAJE_ESPERADO
    estado.dispositivos.obtener_por_id.assert_called_once_with(3, ids_fincas_permitidas=[])
    estado.sensores.obtener_por_id.assert_not_called()
    estado.calibraciones.guardar.assert_not_called()


@pytest.mark.parametrize("valor", ["0.0000", "22.5000", "45.0000"])
def test_hardware_existente_conserva_registro_valido(monkeypatch, valor):
    estado = _cliente(monkeypatch, alcance=[21])
    with estado.cliente:
        antes = _historial(estado, 6)
        respuesta = estado.cliente.post(
            "/configuracion/sensores/6/calibrar", json={**estado.body, "valor_referencia": valor},
        )
        assert respuesta.status_code == 201
        assert respuesta.json()["id_calibracion"] == 16
        assert respuesta.json()["valor_referencia"] == float(valor)
        despues = _historial(estado, 6)
        assert despues["total"] == 7 and despues["items"][:-1] == antes["items"]
    estado.calibraciones.guardar.assert_called_once()
    estado.auditoria.registrar.assert_called_once()
    estado.db.commit.assert_called_once()
    estado.db.rollback.assert_not_called()


def test_otro_flujo_conserva_mensaje_generico(monkeypatch):
    estado = _cliente(monkeypatch)
    with estado.cliente:
        respuesta = estado.cliente.post("/configuracion/sensores/999999/asociar", json={
            "id_dispositivo_iot": 3, "id_infraestructura": 1, "punto_instalacion": "Prueba G130",
        })
    # RF-22 (TC-M09-G62): el sensor inexistente al asociar es 422, no 404.
    assert respuesta.status_code == 422
    assert respuesta.json()["error_code"] == "SENSOR_DISPOSITIVO_INVALIDO"
    assert respuesta.json()["message"].startswith("Inconsistencia de hardware: El sensor 999999")
    estado.eventos.registrar.assert_not_called()
