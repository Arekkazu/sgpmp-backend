# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-21 | Arekkazu | DEV-32 RF-57: una alerta nueva llega a los usuarios de la finca con permiso y queda marcada |
"""DEV-32 (RF-57 Fase 8 y E7) con el adaptador real de RF-14."""
from datetime import datetime, timezone
import importlib
import pkgutil
from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        mod = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__, paquete + "."):
            importlib.import_module(item.name)


def test_alerta_nueva_notifica_a_la_finca_y_registra_el_fallo_de_correo(db_session, crear_usuario_db, monkeypatch):
    from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
    from src.shared import notificacion_service
    from src.telemetry.application.use_cases.alertas.notificar_alertas_use_case import NotificarAlertasUseCase
    from src.telemetry.infrastructure.adapters.notificacion_alerta_rf14_adapter import NotificacionAlertaRf14Adapter
    from src.telemetry.infrastructure.adapters.parametros_alertas_mlops_adapter import ParametrosAlertasMLOpsAdapter
    from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
    from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import (
        SqlAlchemyBitacoraAuditoriaIotRepository,
    )

    def smtp_caido(**_):
        raise ConnectionRefusedError("SMTP de prueba")

    monkeypatch.setattr(notificacion_service, "send_email", smtp_caido)
    db_session.execute(text("""
        INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
        VALUES (32, 'NOTIFICACION_ALERTA', 'Notificacion de una alerta de RF-57') ON CONFLICT (id_tipo_evento) DO NOTHING
    """))
    sufijo = uuid4().hex[:10].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
    finca = db_session.execute(text("""
        INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
        VALUES (:n, '{}'::jsonb, 1, now(), now(), true) RETURNING id_finca
    """), {"n": "Finca Notif " + sufijo}).scalar_one()
    area = db_session.execute(text("""
        INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo)
        VALUES (:n, :f, 10, true, 'Estanque') RETURNING id_infraestructura
    """), {"n": "Galpon " + sufijo, "f": finca}).scalar_one()
    productor = crear_usuario_db(id_rol=2, estado=2)
    ajeno = crear_usuario_db(id_rol=2, estado=2)  # mismo rol, otra finca: no recibe
    db_session.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"),
                       {"u": productor["id_usuario"], "f": finca})
    alerta = db_session.execute(text("""
        INSERT INTO modulo3.alertas (tipo_alerta, severidad, estado_alerta, origen_evento, fecha_evento,
                                     tipo_variable, id_infraestructura)
        VALUES ('ESTRES_TERMICO', 'CRITICO', 'ACTIVA', 'EDGE', now(), 'TEMPERATURA', :a) RETURNING id_alerta
    """), {"a": area}).scalar_one()
    db_session.commit()

    n = NotificarAlertasUseCase(
        db_session, SqlAlchemyAlertaRepository(db_session), NotificacionAlertaRf14Adapter(db_session),
        ParametrosAlertasMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db_session)),
        SqlAlchemyBitacoraAuditoriaIotRepository(db_session),
    ).execute(datetime.now(timezone.utc))

    assert n >= 1
    assert db_session.execute(text("SELECT fecha_notificacion IS NOT NULL FROM modulo3.alertas WHERE id_alerta = :a"),
                              {"a": alerta}).scalar_one()
    canales = dict(db_session.execute(text(
        "SELECT id_notificacion_canal, estado_envio::text FROM modulo1.notificaciones WHERE id_usuario = :u"
    ), {"u": productor["id_usuario"]}).all())
    assert canales == {2: "enviado", 1: "fallido"}  # bandeja entregada; correo caído (E7)
    assert db_session.execute(text("SELECT count(*) FROM modulo1.notificaciones WHERE id_usuario = :u"),
                              {"u": ajeno["id_usuario"]}).scalar_one() == 0
    assert db_session.execute(text(
        "SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento = 'NOTIFICACION_FALLIDA' "
        "AND entidad_afectada_id = :a"
    ), {"a": str(alerta)}).scalar_one() == 1
