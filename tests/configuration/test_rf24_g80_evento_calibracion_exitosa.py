"""#508: POST e historial RF-10 reales, con unidad de trabajo en memoria.

El repositorio RF-10 real crea el ORM y su SHA-256; la sesión simula consultas
y transacciones. No reemplaza una integración con PostgreSQL.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.sql import operators

from src.configuration.domain.entities.calibracion import Calibracion
from src.configuration.domain.entities.rango_calibracion import RangoCalibracion
from src.configuration.infrastructure.routers import sensor_router
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.models.eventos_model import Eventos
from src.identity_access.infrastructure.models.permisos_model import Permisos
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.routers import auditoria_routers
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.middlewares import RequestContextMiddleware


TIPO_EXITOSA = 30
URL = "/configuracion/sensores/6"
BODY = {
    "id_dispositivo_iot": 3, "id_infraestructura": 1,
    "valor_referencia": "22.5000", "modo_calibracion": "SENSOR",
    "fecha_calibracion": "2026-10-07T12:00:00Z",
}


class _Consulta:
    def __init__(self, filas):
        self.filas = list(filas)

    def filter(self, *criterios):
        for criterio in criterios:
            nombre = criterio.left.key
            valor = getattr(criterio.right, "value", True)
            operador = criterio.operator
            if operador is operators.in_op:
                self.filas = [fila for fila in self.filas if getattr(fila, nombre) in valor]
            elif operador is operators.is_:
                self.filas = [fila for fila in self.filas if getattr(fila, nombre) is valor]
            else:
                self.filas = [fila for fila in self.filas if operador(getattr(fila, nombre), valor)]
        return self

    def order_by(self, *_orden):
        self.filas.sort(key=lambda fila: (fila.fecha_evento, fila.id_evento), reverse=True)
        return self

    def offset(self, cantidad):
        self.filas = self.filas[cantidad:]
        return self

    def limit(self, cantidad):
        self.filas = self.filas[:cantidad]
        return self

    def first(self):
        return self.filas[0] if self.filas else None

    def all(self):
        return self.filas

    def count(self):
        return len(self.filas)


class _Db:
    def __init__(self):
        self.calibraciones, self.auditorias, self.eventos = [], [], []
        self.pendientes_cal, self.pendientes_aud, self.pendientes_eventos = [], [], []
        self.permisos = [
            SimpleNamespace(id_rol=4, id_recurso=12, id_accion=accion, es_activo=True)
            for accion in (1, 2)
        ] + [SimpleNamespace(id_rol=1, id_recurso=6, id_accion=2, es_activo=True)]
        self.fallo_evento = self.fallo_commit = False
        self.pasos = []
        self.rollbacks = 0

    def query(self, *modelos):
        if len(modelos) == 1 and modelos[0] is Eventos:
            return _Consulta(self.eventos + self.pendientes_eventos)
        if len(modelos) == 1 and modelos[0] is Permisos:
            return _Consulta(self.permisos)
        # Sin nombre desnormalizado ni baseline: todos los eventos nuevos tienen hash.
        return _Consulta([])

    def add(self, evento):
        evento.id_evento = len(self.eventos) + len(self.pendientes_eventos) + 1
        self.pendientes_eventos.append(evento)
        self.pasos.append("evento_rf10")

    def flush(self):
        if self.fallo_evento and any(e.tipo_evento == TIPO_EXITOSA for e in self.pendientes_eventos):
            raise RuntimeError("No se pudo escribir el evento RF-10")

    def commit(self):
        self.pasos.append("commit")
        if self.fallo_commit and self.pendientes_cal:
            raise RuntimeError("No se pudo confirmar la transacción")
        self.calibraciones.extend(self.pendientes_cal)
        self.auditorias.extend(self.pendientes_aud)
        self.eventos.extend(self.pendientes_eventos)
        self._limpiar_pendientes()

    def rollback(self):
        self.rollbacks += 1
        self._limpiar_pendientes()

    def _limpiar_pendientes(self):
        self.pendientes_cal.clear()
        self.pendientes_aud.clear()
        self.pendientes_eventos.clear()


@pytest.fixture
def estado(monkeypatch):
    db = _Db()
    for id_calibracion in range(10, 15):
        anterior = Calibracion.crear(
            id_dispositivo_iot=3, id_sensor=6, valor_referencia=Decimal("20.0000"),
            fecha_calibracion=datetime(2026, 10, 6, tzinfo=timezone.utc), id_usuario=4,
        )
        anterior.id_calibracion = id_calibracion
        db.calibraciones.append(anterior)
    repo_eventos = SqlAlchemyEventoRepository(db)
    for tipo in (3, 19):  # Eventos ajenos: nunca sustituyen una calibración.
        repo_eventos.registrar(tipo_evento=tipo, exitoso=True, id_usuario=4, detalle={})
    db.commit()
    db.pasos.clear()

    def guardar(calibracion):
        calibracion.id_calibracion = 15
        db.pendientes_cal.append(calibracion)
        db.pasos.append("calibracion")
        return calibracion

    def auditar(**datos):
        db.pendientes_aud.append(datos)
        db.pasos.append("auditoria_m09")

    calibraciones = Mock()
    calibraciones.guardar.side_effect = guardar
    calibraciones.listar_por_sensor.side_effect = lambda _: list(db.calibraciones)
    sensores = Mock()
    sensores.obtener_por_id.return_value = SimpleNamespace(id_dispositivo_iot=3, categoria="TEMPERATURA")
    dispositivos = Mock()
    dispositivos.obtener_por_id.return_value = SimpleNamespace(es_activo=True)
    asociaciones = Mock()
    asociaciones.obtener_asociacion_activa.return_value = SimpleNamespace(id_infraestructura=1)
    rangos = Mock()
    rangos.obtener_por_categoria.return_value = RangoCalibracion("TEMPERATURA", Decimal("0"), Decimal("45"))
    auditoria = Mock()
    auditoria.registrar.side_effect = auditar
    alcance = Mock()
    alcance.listar_ids_fincas_permitidas.return_value = [21]
    usuarios = Mock()
    usuarios.obtener_por_id.return_value = object()
    for nombre, repo in (
        ("SqlAlchemySensorRepository", sensores),
        ("SqlAlchemyDispositivoIotRepository", dispositivos),
        ("SqlAlchemySensorAreaRepository", asociaciones),
        ("SqlAlchemyCalibracionRepository", calibraciones),
        ("SqlAlchemyRangoCalibracionRepository", rangos),
        ("SqlAlchemyAuditoriaCalibracionRepository", auditoria),
        ("AlcanceFincaAdapter", alcance),
    ):
        monkeypatch.setattr(sensor_router, nombre, lambda _db, repo=repo: repo)
    monkeypatch.setattr(auditoria_routers, "SqlAlchemyUsuarioRepository", lambda _db: usuarios)
    actor = {"actual": UsuarioActual(id_usuario=4, id_token=1, id_rol=4, id_estado_cuenta=2)}
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(sensor_router.router)
    app.include_router(auditoria_routers.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: actor["actual"]
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield SimpleNamespace(cliente=cliente, db=db, actor=actor,
                              calibraciones=calibraciones, auditoria=auditoria)


def _consultar_rf10(estado, inicio, fin, **filtros):
    estado.actor["actual"] = UsuarioActual(id_usuario=1, id_token=2, id_rol=1, id_estado_cuenta=2)
    return estado.cliente.get("/auditoria/", params={
        "id_usuario": 4, "fecha_desde": inicio.isoformat(), "fecha_hasta": fin.isoformat(),
        "categoria": "MODIFICACION", "tipo_evento": TIPO_EXITOSA, **filtros,
    })


@pytest.mark.parametrize("valor", ["0.0000", "22.5000", "45.0000"])
def test_calibracion_exitosa_se_recupera_en_rf10_con_hash_y_correlacion(estado, valor):
    existentes = [(e.id_evento, e.hash_integridad, deepcopy(e.detalle)) for e in estado.db.eventos]
    historial_pre = estado.cliente.get(f"{URL}/calibraciones")
    assert historial_pre.status_code == 200
    inicio = datetime.now(timezone.utc) - timedelta(minutes=1)
    respuesta = estado.cliente.post(f"{URL}/calibrar", json={**BODY, "valor_referencia": valor})
    fin = datetime.now(timezone.utc) + timedelta(minutes=1)
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["id_calibracion"] == 15
    assert estado.db.pasos == ["calibracion", "auditoria_m09", "evento_rf10", "commit"]
    historial = estado.cliente.get(f"{URL}/calibraciones")
    assert historial.status_code == 200
    assert historial.json()["total"] == historial_pre.json()["total"] + 1
    assert historial.json()["items"][:-1] == historial_pre.json()["items"]
    assert historial.json()["items"][-1]["id_calibracion"] == 15
    auditoria = _consultar_rf10(estado, inicio, fin)
    assert auditoria.status_code == 200, auditoria.text
    assert auditoria.json()["total"] == 1
    [evento] = auditoria.json()["items"]
    assert evento["tipo_evento"] == TIPO_EXITOSA
    assert evento["id_usuario"] == 4
    assert inicio <= datetime.fromisoformat(evento["fecha_evento"]) <= fin
    assert evento["resultado"] == "exitoso"  # Enum existente de RF-10.
    assert evento["modulo"] == "MODULO9"
    assert evento["categoria"] == "MODIFICACION"
    assert evento["integridad_ok"] is True and evento["integridad"] == "INTEGRO"
    detalle = evento["detalle"]
    assert detalle["operacion"] == "CALIBRACION_SENSOR"
    assert detalle["id_calibracion"] == 15
    assert detalle["id_sensor"] == 6 and detalle["id_dispositivo_iot"] == 3
    assert detalle["id_usuario"] == 4 and detalle["id_infraestructura"] == 1
    assert detalle["valor_referencia"] == valor
    assert detalle["fecha_calibracion"] == "2026-10-07T12:00:00+00:00"
    assert detalle["modo_calibracion"] == "SENSOR"
    assert detalle["ip"] == "testclient" and detalle["user_agent"]
    assert [(e.id_evento, e.hash_integridad, e.detalle) for e in estado.db.eventos[:2]] == existentes


@pytest.mark.parametrize("fallo", ["rf10", "m09", "commit"])
def test_fallo_revierta_calibracion_y_ambas_auditorias(estado, fallo):
    existentes = [(e.id_evento, e.hash_integridad) for e in estado.db.eventos]
    calibraciones_antes = [(c.id_calibracion, c._snapshot()) for c in estado.db.calibraciones]
    if fallo == "rf10":
        estado.db.fallo_evento = True
    elif fallo == "m09":
        estado.auditoria.registrar.side_effect = RuntimeError("Auditoría M09 no disponible")
    else:
        estado.db.fallo_commit = True
    respuesta = estado.cliente.post(f"{URL}/calibrar", json=BODY)
    assert respuesta.status_code == 500, respuesta.text
    if fallo != "commit":
        assert respuesta.json()["error_code"] == "AUDITORIA_CALIBRACION_FALLIDA"
    assert [(c.id_calibracion, c._snapshot()) for c in estado.db.calibraciones] == calibraciones_antes
    assert estado.db.auditorias == []
    assert [(e.id_evento, e.hash_integridad) for e in estado.db.eventos] == existentes
    assert estado.db.pendientes_cal == [] and estado.db.pendientes_eventos == []
    assert estado.db.rollbacks == 1


@pytest.mark.parametrize("rechazo", ["formato", "permiso"])
def test_rechazos_conservan_evento_fallido_y_no_emiten_exito(estado, rechazo):
    if rechazo == "permiso":
        estado.db.permisos = [p for p in estado.db.permisos if (p.id_rol, p.id_recurso, p.id_accion) != (4, 12, 1)]
    respuesta = estado.cliente.post(f"{URL}/calibrar", json={**BODY, "valor_referencia": "abc" if rechazo == "formato" else BODY["valor_referencia"]})
    assert respuesta.status_code == (400 if rechazo == "formato" else 403)
    [evento] = estado.db.eventos[2:]
    assert evento.tipo_evento == 29 and evento.resultado.value == "fallido"
    assert evento.id_usuario == 4 and evento.detalle["id_sensor"] == 6
    assert evento.hash_integridad == SqlAlchemyEventoRepository._calcular_hash(evento)
    estado.calibraciones.guardar.assert_not_called()
    assert estado.db.auditorias == []


def test_rf10_detecta_alteracion_de_datos_correlacionados(estado):
    inicio = datetime.now(timezone.utc) - timedelta(minutes=1)
    respuesta = estado.cliente.post(f"{URL}/calibrar", json=BODY)
    assert respuesta.status_code == 201
    exitosas = [e for e in estado.db.eventos if e.tipo_evento == TIPO_EXITOSA]
    assert len(exitosas) == 1
    exitosas[0].detalle["valor_referencia"] = "999.0000"
    auditoria = _consultar_rf10(estado, inicio, datetime.now(timezone.utc) + timedelta(minutes=1))
    assert auditoria.status_code == 500
    assert auditoria.json()["error_code"] == "INTEGRIDAD_AUDITORIA_VIOLADA"
