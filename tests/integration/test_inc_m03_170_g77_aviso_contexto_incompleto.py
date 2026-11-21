# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-170-G77 RF-57 E6: el administrador recibe el aviso de contexto incompleto (worker real) |
"""INC-M03-170-G77 (RF-57 E6, TC-M03-N21): aviso al Administrador para completar la asociación del sensor.

Worker real de notificaciones (NotificarAlertasUseCase + adaptador RF-14) contra PostgreSQL real.
Reproduce la causa: el Administrador ya tenía una notificación de alerta en los últimos 5 minutos y el
anti-spam por tipo de evento descartaba el aviso.
"""
from datetime import datetime, timedelta, timezone
import importlib
import pkgutil
from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

_AVISO = "%Complete la asociación del sensor%"


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        mod = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__, paquete + "."):
            importlib.import_module(item.name)


@pytest.fixture
def entorno(db_session, crear_usuario_db, monkeypatch):
    from src.shared import notificacion_service
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_: None)  # sin SMTP real
    db_session.execute(text("""INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
        VALUES (32, 'NOTIFICACION_ALERTA', 'Notificacion de una alerta de RF-57') ON CONFLICT (id_tipo_evento) DO NOTHING"""))
    rol_admin = db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol='Administrador'")).scalar_one()
    admin = crear_usuario_db(id_rol=rol_admin, estado=2)["id_usuario"]
    sufijo = uuid4().hex[:10].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
    finca = db_session.execute(text("""INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion,
        fecha_creacion, es_activo) VALUES (:n, '{}'::jsonb, 1, now(), now(), true) RETURNING id_finca"""),
        {"n": "Finca Aviso " + sufijo}).scalar_one()
    area = db_session.execute(text("""INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo)
        VALUES (:n, :f, 10, true, 'Estanque') RETURNING id_infraestructura"""), {"n": "Unidad " + sufijo, "f": finca}).scalar_one()
    device = db_session.execute(text("""INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,
        id_infraestructura,id_tipo_dispositivo) VALUES (:s,'G77',true,now(),:a,3) RETURNING id_dispositivo_iot"""),
        {"s": sufijo, "a": area}).scalar_one()
    sensores = [db_session.execute(text("""INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
        VALUES (:d,true,:n) RETURNING id_sensores"""), {"d": device, "n": f"S{i}"}).scalar_one() for i in range(2)]
    db_session.commit()
    return {"db": db_session, "admin": admin, "area": area, "sensores": sensores}


def _alerta_sin_contexto(db, area, sensor):
    id_alerta = db.execute(text("""INSERT INTO modulo3.alertas (tipo_alerta, severidad, estado_alerta, origen_evento,
        fecha_evento, tipo_variable, id_infraestructura, id_sensor, tiene_contexto_incompleto)
        VALUES ('RIESGO_HIDRICO', 'LEVE', 'ACTIVA', 'EDGE', now(), 'OXIGENO_DISUELTO', :a, :s, true) RETURNING id_alerta"""),
        {"a": area, "s": sensor}).scalar_one()
    db.commit()
    return id_alerta


def _worker(db, ahora):
    from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
    from src.telemetry.application.use_cases.alertas.notificar_alertas_use_case import NotificarAlertasUseCase
    from src.telemetry.infrastructure.adapters.notificacion_alerta_rf14_adapter import NotificacionAlertaRf14Adapter
    from src.telemetry.infrastructure.adapters.parametros_alertas_mlops_adapter import ParametrosAlertasMLOpsAdapter
    from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
    from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
    return NotificarAlertasUseCase(db, SqlAlchemyAlertaRepository(db), NotificacionAlertaRf14Adapter(db),
                                   ParametrosAlertasMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db)),
                                   SqlAlchemyBitacoraAuditoriaIotRepository(db)).execute(ahora)


def _avisos(db, admin, sensor=None):
    patron = f"%Complete la asociación del sensor {sensor} %" if sensor else _AVISO
    return db.execute(text("SELECT count(*) FROM modulo1.notificaciones WHERE id_usuario=:u "
                           "AND id_notificacion_canal = 2 AND mensaje LIKE :p"), {"u": admin, "p": patron}).scalar_one()


def test_n21_aviso_llega_aunque_haya_otra_notificacion_de_alerta_reciente(entorno):
    from src.telemetry.infrastructure.adapters.notificacion_alerta_rf14_adapter import NotificacionAlertaRf14Adapter
    db, admin = entorno["db"], entorno["admin"]
    # El Administrador acaba de recibir otra notificación de alerta (tipo 32): antes esto descartaba el aviso.
    NotificacionAlertaRf14Adapter(db).enviar(admin, "Alerta CRITICO previa", "Otra alerta.", agrupable=True)
    _alerta_sin_contexto(db, entorno["area"], entorno["sensores"][0])
    _worker(db, datetime.now(timezone.utc))
    assert _avisos(db, admin, entorno["sensores"][0]) == 1


def test_un_aviso_por_sensor_en_la_misma_vuelta_y_otro_sensor_tambien_avisa(entorno):
    db, admin, (s1, s2) = entorno["db"], entorno["admin"], entorno["sensores"]
    for sensor in (s1, s1, s2):
        _alerta_sin_contexto(db, entorno["area"], sensor)
    _worker(db, datetime.now(timezone.utc))
    assert (_avisos(db, admin, s1), _avisos(db, admin, s2)) == (1, 1)


def test_no_se_repite_el_aviso_del_mismo_sensor_en_24_horas(entorno):
    db, admin, s1 = entorno["db"], entorno["admin"], entorno["sensores"][0]
    _alerta_sin_contexto(db, entorno["area"], s1)
    _worker(db, datetime.now(timezone.utc))
    _alerta_sin_contexto(db, entorno["area"], s1)
    _worker(db, datetime.now(timezone.utc) + timedelta(seconds=1))
    assert _avisos(db, admin, s1) == 1
