"""Issue #507: mensaje del 403 de calibración, con RBAC y repositorios en memoria."""
from dataclasses import asdict
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
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers


MENSAJE_RF24 = (
    "Acceso denegado: La calibración de sensores es una función crítica restringida "
    "exclusivamente al Ingeniero de Campo o al Administrador."
)
MENSAJE_GENERICO = "Acceso denegado. Su rol no tiene permisos para realizar esta operación."
URL = "/configuracion/sensores/6"
BODY = {
    "id_dispositivo_iot": 3, "id_infraestructura": 1,
    "valor_referencia": "25.0000", "fecha_calibracion": "2026-10-07T12:00:00Z",
    "modo_calibracion": "SENSOR",
}

# IDs arbitrarios de la matriz simulada: la autorización depende de permisos,
# no de los IDs ni de las etiquetas de los roles.
ROLES_SIN_CREATE = [pytest.param(102, True, id="Productor"),
                   pytest.param(107, False, id="Contador")]


class _ConsultaPermisos:
    def __init__(self, db):
        self.db = db
        self.criterios = []

    def filter(self, *criterios):
        self.criterios.extend(criterios)
        return self

    def first(self):
        valores = [
            criterio.right.value for criterio in self.criterios
            if getattr(getattr(criterio, "right", None), "value", None) is not None
        ]
        clave = tuple(valores[-3:])  # id_rol, id_recurso, id_accion
        self.db.consultas.append(clave)
        return object() if clave in self.db.permisos else None


class _Db:
    def __init__(self, permisos):
        self.permisos = set(permisos)
        self.consultas = []
        self.commit = Mock()
        self.rollback = Mock()

    def query(self, *_args):
        return _ConsultaPermisos(self)


def _cliente(monkeypatch, *, id_rol=102, lectura=True, crear=False,
             estado_cuenta=2, fallo_auditoria=False, autenticado=True):
    permisos = {(901, 12, 2)}  # Lector de control para PRE/POST, sin CREATE.
    if lectura:
        permisos.add((id_rol, 12, 2))
    if crear:
        permisos.add((id_rol, 12, 1))
    db = _Db(permisos)
    fecha = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
    historial = [
        Calibracion.crear(id_dispositivo_iot=3, id_sensor=6,
                         valor_referencia=Decimal("25"), fecha_calibracion=fecha,
                         id_usuario=7) for _ in range(5)
    ]
    for calibracion, id_calibracion in zip(historial, (14, 13, 12, 11, 10)):
        calibracion.id_calibracion = id_calibracion

    def guardar(calibracion):
        calibracion.id_calibracion = 99
        historial.append(calibracion)
        return calibracion

    calibraciones = Mock()
    calibraciones.guardar.side_effect = guardar
    calibraciones.listar_por_sensor.side_effect = lambda _: list(historial)
    sensores = Mock()
    sensores.obtener_por_id.return_value = SimpleNamespace(id_dispositivo_iot=3, categoria="TEMPERATURA")
    dispositivos = Mock()
    dispositivos.obtener_por_id.return_value = SimpleNamespace(es_activo=True)
    asociaciones = Mock()
    asociaciones.obtener_asociacion_activa.return_value = SimpleNamespace(id_infraestructura=1)
    rangos = Mock()
    rangos.obtener_por_categoria.return_value = RangoCalibracion("TEMPERATURA", Decimal("0"), Decimal("45"))
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
    registrar = Mock(wraps=sensor_router.RegistrarCalibracionUseCase)
    monkeypatch.setattr(sensor_router, "RegistrarCalibracionUseCase", registrar)
    usuario = UsuarioActual(id_usuario=7, id_token=1, id_rol=id_rol, id_estado_cuenta=estado_cuenta)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(sensor_router.router)
    app.dependency_overrides[get_db] = lambda: db
    if autenticado:
        app.dependency_overrides[get_current_user] = lambda: usuario
    return SimpleNamespace(
        cliente=TestClient(app, raise_server_exceptions=False), app=app, usuario=usuario,
        db=db, calibraciones=calibraciones, auditoria=auditoria, eventos=eventos,
        registrar=registrar,
    )


def _historial_con_lector(estado):
    lector = UsuarioActual(id_usuario=99, id_token=1, id_rol=901, id_estado_cuenta=2)
    estado.app.dependency_overrides[get_current_user] = lambda: lector
    try:
        respuesta = estado.cliente.get(f"{URL}/calibraciones")
        assert respuesta.status_code == 200
        return respuesta.json()
    finally:
        estado.app.dependency_overrides[get_current_user] = lambda: estado.usuario


@pytest.mark.parametrize("id_rol,lectura", ROLES_SIN_CREATE)
def test_rol_sin_create_recibe_mensaje_rf24_y_no_altera_historial(monkeypatch, id_rol, lectura):
    estado = _cliente(monkeypatch, id_rol=id_rol, lectura=lectura)
    usuario_antes = asdict(estado.usuario)
    permisos_antes = estado.db.permisos.copy()
    with estado.cliente:
        antes = _historial_con_lector(estado)
        respuesta = estado.cliente.post(f"{URL}/calibrar", json=BODY)
        assert respuesta.status_code == 403
        cuerpo = respuesta.json()
        assert cuerpo["error_code"] == "ACCESO_DENEGADO"
        assert cuerpo["message"] == MENSAJE_RF24
        assert cuerpo["fields"] == []
        assert "id_calibracion" not in cuerpo
        assert _historial_con_lector(estado) == antes
    assert asdict(estado.usuario) == usuario_antes
    assert estado.db.permisos == permisos_antes
    assert estado.db.consultas.count((id_rol, 12, 1)) == 1
    estado.registrar.assert_not_called()
    estado.calibraciones.guardar.assert_not_called()
    estado.auditoria.registrar.assert_not_called()
    estado.eventos.registrar.assert_called_once()
    evento = estado.eventos.registrar.call_args.kwargs
    assert evento["exitoso"] is False
    assert evento["id_usuario"] == 7
    assert evento["detalle"]["id_sensor"] == 6
    assert evento["detalle"]["codigo_error"] == "ACCESO_DENEGADO"
    assert evento["detalle"]["codigo_http"] == 403
    assert evento["detalle"]["motivo"] == MENSAJE_RF24
    estado.db.commit.assert_called_once()  # Solo confirma la auditoría del rechazo.
    estado.db.rollback.assert_not_called()


@pytest.mark.parametrize("id_rol", [pytest.param(101, id="Administrador"),
                                   pytest.param(104, id="Ingeniero"),
                                   pytest.param(899, id="permiso-dinamico")])
def test_create_autoriza_segun_rbac_y_conserva_flujo_valido(monkeypatch, id_rol):
    estado = _cliente(monkeypatch, id_rol=id_rol, crear=True)
    with estado.cliente:
        antes = _historial_con_lector(estado)
        respuesta = estado.cliente.post(f"{URL}/calibrar", json=BODY)
        assert respuesta.status_code == 201
        assert respuesta.json()["id_calibracion"] == 99
        despues = _historial_con_lector(estado)
        assert despues["total"] == antes["total"] + 1
        assert despues["items"][:-1] == antes["items"]
    assert (id_rol, 12, 1) in estado.db.consultas
    estado.calibraciones.guardar.assert_called_once()
    estado.auditoria.registrar.assert_called_once()
    estado.eventos.registrar.assert_not_called()
    estado.db.commit.assert_called_once()
    estado.db.rollback.assert_not_called()


@pytest.mark.parametrize("id_rol,lectura", ROLES_SIN_CREATE)
def test_fallo_auditoria_no_cambia_el_403_ni_su_mensaje(monkeypatch, id_rol, lectura):
    estado = _cliente(monkeypatch, id_rol=id_rol, lectura=lectura, fallo_auditoria=True)
    with estado.cliente:
        antes = _historial_con_lector(estado)
        respuesta = estado.cliente.post(f"{URL}/calibrar", json=BODY)
        assert respuesta.status_code == 403
        assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"
        assert respuesta.json()["message"] == MENSAJE_RF24
        assert _historial_con_lector(estado) == antes
    estado.registrar.assert_not_called()
    estado.calibraciones.guardar.assert_not_called()
    estado.db.commit.assert_not_called()
    estado.db.rollback.assert_called_once()


def test_cuenta_no_activa_conserva_su_error_especifico(monkeypatch):
    estado = _cliente(monkeypatch, id_rol=101, crear=True, estado_cuenta=1)
    with estado.cliente:
        respuesta = estado.cliente.post(f"{URL}/calibrar", json=BODY)
    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "CUENTA_NO_ACTIVA"
    assert respuesta.json()["message"] == (
        "Acceso denegado. Su cuenta no se encuentra activa, por lo que los permisos de su rol no son efectivos."
    )
    assert estado.db.consultas == []
    estado.registrar.assert_not_called()


def test_sin_autenticacion_conserva_401(monkeypatch):
    estado = _cliente(monkeypatch, autenticado=False)
    with estado.cliente:
        respuesta = estado.cliente.post(f"{URL}/calibrar", json=BODY)
    assert respuesta.status_code == 401
    assert respuesta.json()["message"] != MENSAJE_RF24
    estado.registrar.assert_not_called()
    estado.eventos.registrar.assert_not_called()


@pytest.mark.parametrize("metodo,ruta,body", [
    ("GET", f"{URL}/calibraciones", None),
    ("POST", f"{URL}/asociar", {"id_infraestructura": 1}),
])
def test_otros_endpoints_conservan_mensaje_rbac_generico(monkeypatch, metodo, ruta, body):
    estado = _cliente(monkeypatch, id_rol=107, lectura=False)
    with estado.cliente:
        respuesta = estado.cliente.request(metodo, ruta, json=body)
    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"
    assert respuesta.json()["message"] == MENSAJE_GENERICO
    estado.eventos.registrar.assert_not_called()
    estado.registrar.assert_not_called()
