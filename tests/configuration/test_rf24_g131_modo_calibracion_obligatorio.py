"""#510: modo obligatorio, validación HTTP y no persistencia; sin BD real."""
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
def estado(monkeypatch):
    fecha = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
    historial = []
    for id_sensor, ids in ((6, (10, 11, 12, 13, 14, 15)), (9, (3, 9))):
        for id_calibracion in ids:
            cal = Calibracion.crear(
                id_dispositivo_iot=3 if id_sensor == 6 else 4, id_sensor=id_sensor,
                valor_referencia=Decimal("22.5000"), fecha_calibracion=fecha, id_usuario=4,
            )
            cal.id_calibracion = id_calibracion
            historial.append(cal)

    sensores = Mock()
    sensores.obtener_por_id.side_effect = lambda id_sensor: {
        6: SimpleNamespace(id_dispositivo_iot=3, categoria="TEMPERATURA"),
        9: SimpleNamespace(id_dispositivo_iot=4, categoria="TEMPERATURA"),
    }.get(id_sensor)
    dispositivo = SimpleNamespace(es_activo=True, serial=SimpleNamespace(valor="IOT-G131"))
    dispositivos = Mock()
    dispositivos.obtener_por_id.side_effect = lambda id_dispositivo, ids_fincas_permitidas=None: (
        dispositivo if id_dispositivo in (3, 4) else None
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
    fincas = Mock()
    fincas.listar_ids_fincas_permitidas.return_value = [21]
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
    ejecuciones = Mock()
    execute_original = sensor_router.RegistrarCalibracionUseCase.execute

    def execute(self, *args, **kwargs):
        ejecuciones(*args, **kwargs)
        return execute_original(self, *args, **kwargs)

    monkeypatch.setattr(sensor_router.RegistrarCalibracionUseCase, "execute", execute)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(sensor_router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=4, id_token=1, id_rol=4, id_estado_cuenta=2,
    )
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield SimpleNamespace(
            cliente=cliente, app=app, db=db, dispositivo=dispositivo,
            sensores=sensores, dispositivos=dispositivos, asociaciones=asociaciones,
            calibraciones=calibraciones, rangos=rangos, auditoria=auditoria,
            eventos=eventos, ejecuciones=ejecuciones,
            body={"id_dispositivo_iot": 3, "id_infraestructura": 1,
                  "valor_referencia": "22.5000", "modo_calibracion": "SENSOR",
                  "fecha_calibracion": fecha.isoformat()},
        )


def _historial(estado, id_sensor=6):
    respuesta = estado.cliente.get(f"/configuracion/sensores/{id_sensor}/calibraciones")
    assert respuesta.status_code == 200
    return respuesta.json()


def _sin_persistencia(estado):
    estado.calibraciones.guardar.assert_not_called()
    estado.auditoria.registrar.assert_not_called()


@pytest.mark.parametrize("cambio", [
    pytest.param({}, id="TC-M09-259-ausente"),
    pytest.param({"modo_calibracion": "OTRO"}, id="TC-M09-260-OTRO"),
    pytest.param({"modo_calibracion": ""}, id="TC-M09-260-vacio"),
    pytest.param({"modo_calibracion": None}, id="null"),
    pytest.param({"modo_calibracion": 1}, id="numero"),
    pytest.param({"modo_calibracion": True}, id="booleano"),
    pytest.param({"modo_calibracion": "sensor"}, id="minusculas"),
    pytest.param({"modo_calibracion": "VISION"}, id="vision-no-soportada-en-este-endpoint"),
])
def test_modo_ausente_o_invalido_se_rechaza_antes_del_caso_de_uso(estado, cambio):
    antes = _historial(estado)
    assert antes["total"] == 6
    assert [item["id_calibracion"] for item in antes["items"]] == [10, 11, 12, 13, 14, 15]
    body = {campo: valor for campo, valor in estado.body.items() if campo != "modo_calibracion"}
    respuesta = estado.cliente.post("/configuracion/sensores/6/calibrar", json={**body, **cambio})
    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "VAL_ENTRADA"
    assert "id_calibracion" not in respuesta.json()
    assert any(error["field"] == "modo_calibracion" for error in respuesta.json()["fields"])
    assert _historial(estado) == antes
    estado.ejecuciones.assert_not_called()
    _sin_persistencia(estado)
    estado.eventos.registrar.assert_not_called()
    estado.db.commit.assert_not_called()
    estado.db.rollback.assert_not_called()
    estado.asociaciones.obtener_asociacion_activa.assert_not_called()
    estado.rangos.obtener_por_categoria.assert_not_called()


def test_openapi_publica_modo_obligatorio_sin_default(estado):
    respuesta = estado.cliente.get("/openapi.json")
    assert respuesta.status_code == 200
    contrato = respuesta.json()
    body = contrato["paths"]["/configuracion/sensores/{id_sensor}/calibrar"]["post"]["requestBody"]
    assert body["content"]["application/json"]["schema"]["$ref"].endswith("/RegistrarCalibracionDTO")
    dto = contrato["components"]["schemas"]["RegistrarCalibracionDTO"]
    assert "modo_calibracion" in dto["required"]
    modo = dto["properties"]["modo_calibracion"]
    assert "default" not in modo
    # Literal[SENSOR] (#514) se publica inline como const; un Enum, como $ref.
    if "$ref" in modo:
        modo = contrato["components"]["schemas"][modo["$ref"].rsplit("/", 1)[1]]
    assert modo.get("enum", [modo.get("const")]) == ["SENSOR"]


@pytest.mark.parametrize("valor", ["0.0000", "22.5000", "45.0000"])
def test_sensor_explicito_conserva_calibracion_valida(estado, valor):
    antes = _historial(estado)
    respuesta = estado.cliente.post(
        "/configuracion/sensores/6/calibrar", json={**estado.body, "valor_referencia": valor},
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["id_calibracion"] == 16
    assert respuesta.json()["modo_calibracion"] == "SENSOR"
    assert respuesta.json()["valor_referencia"] == float(valor)
    despues = _historial(estado)
    assert despues["total"] == 7 and despues["items"][:-1] == antes["items"]
    estado.ejecuciones.assert_called_once()
    estado.calibraciones.guardar.assert_called_once()
    estado.auditoria.registrar.assert_called_once()
    assert estado.auditoria.registrar.call_args.kwargs["valores_nuevos"]["modo_calibracion"] == "SENSOR"
    estado.db.commit.assert_called_once()
    estado.db.rollback.assert_not_called()


@pytest.mark.parametrize("id_sensor,cambios,http,codigo", [
    pytest.param(9, {}, 422, "SENSOR_DISPOSITIVO_INVALIDO", id="TC-M09-258"),
    pytest.param(6, {"id_infraestructura": 2}, 400, "SENSOR_AREA_INVALIDA", id="area"),
    pytest.param(6, {"valor_referencia": "45.0001"}, 400, "VALOR_FUERA_DE_RANGO", id="rango"),
    pytest.param(6, {"valor_referencia": "abc"}, 400, "VALOR_CALIBRACION_INVALIDO", id="formato"),
    pytest.param(6, {"id_dispositivo_iot": 999999}, 404, "DISPOSITIVO_NO_ENCONTRADO", id="dispositivo"),
    pytest.param(999999, {}, 404, "SENSOR_NO_ENCONTRADO", id="sensor"),
])
def test_validaciones_existentes_se_conservan(estado, id_sensor, cambios, http, codigo):
    antes = {sensor: _historial(estado, sensor) for sensor in (6, 9)}
    assert [item["id_calibracion"] for item in antes[9]["items"]] == [3, 9]
    respuesta = estado.cliente.post(
        f"/configuracion/sensores/{id_sensor}/calibrar", json={**estado.body, **cambios},
    )
    assert respuesta.status_code == http
    assert respuesta.json()["error_code"] == codigo
    assert "id_calibracion" not in respuesta.json()
    assert {sensor: _historial(estado, sensor) for sensor in antes} == antes
    _sin_persistencia(estado)
    estado.eventos.registrar.assert_called_once()
    assert estado.eventos.registrar.call_args.kwargs["detalle"]["codigo_error"] == codigo


def test_autorizacion_se_conserva(estado, monkeypatch):
    antes = _historial(estado)
    monkeypatch.setattr(rbac, "tiene_permiso", lambda *args, **kwargs: False)
    respuesta = estado.cliente.post("/configuracion/sensores/6/calibrar", json=estado.body)
    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"
    estado.ejecuciones.assert_not_called()
    _sin_persistencia(estado)
    monkeypatch.setattr(rbac, "tiene_permiso", lambda *args, **kwargs: True)
    assert _historial(estado) == antes


def test_dispositivo_inactivo_sigue_rechazado(estado):
    antes = _historial(estado)
    estado.dispositivo.es_activo = False
    respuesta = estado.cliente.post("/configuracion/sensores/6/calibrar", json=estado.body)
    assert respuesta.status_code == 422
    assert respuesta.json()["error_code"] == "DISPOSITIVO_INACTIVO"
    assert _historial(estado) == antes
    _sin_persistencia(estado)
