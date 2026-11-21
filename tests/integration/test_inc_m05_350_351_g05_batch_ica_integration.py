# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-12 | Leandro | INC-M05-350/351-G05 RF-74: verificar el corte, la bandeja por rol y la migración en PostgreSQL. |
"""Regresión de TC-M05-015d con las rutas reales y PostgreSQL."""

from datetime import datetime

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.database import declarar_identidad_sistema
from src.supplies.infrastructure.adapters import notificacion_suministros_m01_adapter
from src.supplies.infrastructure.routers.batch_ica_router import router

pytestmark = pytest.mark.integration

_BATCH = "/suministros/eficiencia-alimenticia/batch"


def test_interrupcion_manual_persiste_motivo_y_avisa_a_los_dos_roles(
    integration_app, client, db_session, crear_usuario_db, crear_auth_headers, monkeypatch,
):
    integration_app.include_router(router)

    def sesion_notificaciones():
        sesion = Session(bind=db_session.connection(), join_transaction_mode="create_savepoint")
        declarar_identidad_sistema(sesion)
        return sesion

    monkeypatch.setattr(notificacion_suministros_m01_adapter, "sesion_sistema", sesion_notificaciones)
    admin = crear_usuario_db(id_rol=1)
    productor = crear_usuario_db(id_rol=2)
    veterinario = crear_usuario_db(id_rol=3)
    inactivo = crear_usuario_db(id_rol=2, estado=1)
    admin_headers = crear_auth_headers(admin)
    productor_headers = crear_auth_headers(productor)
    veterinario_headers = crear_auth_headers(veterinario)
    corrida = db_session.scalar(text("""
        INSERT INTO modulo5.ejecuciones_batch_ica (
            tipo_disparo, cantidad_activos_total, cantidad_activos_procesados, cantidad_activos_pendientes
        ) VALUES ('MANUAL', 10, 3, 2)
        RETURNING id_ejecucion
    """))
    db_session.commit()

    en_curso = client.post(f"{_BATCH}/ejecutar", headers=admin_headers, json={"solo_cola": False})
    assert en_curso.status_code == 409 and en_curso.json()["error_code"] == "BATCH_EN_CURSO"
    ruta = f"{_BATCH}/{corrida}/interrumpir"
    motivo = "QA TC-M05-015d: detener el lote de cálculo para una revisión controlada"
    denegado = client.post(ruta, headers=productor_headers, json={"motivo": motivo})
    assert denegado.status_code == 403, denegado.text
    respuesta = client.post(ruta, headers=admin_headers, json={"motivo": motivo})
    assert respuesta.status_code == 200, respuesta.text
    corte = respuesta.json()
    assert corte["estado"] == "INTERRUMPIDO" and corte["causa_interrupcion"] == "MANUAL"
    assert corte["motivo_interrupcion"] == motivo and corte["cantidad_activos_pendientes"] == 9
    guardado = db_session.execute(text("""
        SELECT id_usuario_interrupcion, hora_corte, motivo_interrupcion
        FROM modulo5.ejecuciones_batch_ica WHERE id_ejecucion = :corrida
    """), {"corrida": corrida}).one()
    assert guardado == (admin["id_usuario"], datetime.fromisoformat(corte["hora_corte"]), motivo)
    panel = client.get(f"{_BATCH}/estado", headers=admin_headers)
    assert panel.status_code == 200, panel.text
    fila, = [item for item in panel.json() if item["id_ejecucion"] == corrida]
    for campo in ("hora_corte", "hora_fin"):
        assert datetime.fromisoformat(fila[campo]) == datetime.fromisoformat(corte[campo])
    assert fila["causa_interrupcion"] == "MANUAL" and fila["motivo_interrupcion"] == motivo
    repetido = client.post(ruta, headers=admin_headers, json={})
    assert repetido.status_code == 422 and repetido.json()["error_code"] == "BATCH_NO_EN_EJECUCION"
    inexistente = client.post(f"{_BATCH}/2147483647/interrumpir", headers=admin_headers, json={})
    assert inexistente.status_code == 404 and inexistente.json()["error_code"] == "EJECUCION_NO_ENCONTRADA"

    avisos = db_session.execute(text("""
        SELECT n.id_usuario, e.id_usuario AS id_usuario_evento, n.mensaje
        FROM modulo1.notificaciones n
        JOIN modulo1.eventos e USING (id_evento)
        JOIN modulo1.tipos_eventos t ON t.id_tipo_evento = e.tipo_evento
        WHERE t.nombre = 'BATCH_ICA_INTERRUMPIDO' AND e.detalle->>'id_ejecucion' = :corrida
          AND n.id_usuario IN (:admin, :productor, :veterinario, :inactivo)
    """), {"corrida": str(corrida), "admin": admin["id_usuario"], "productor": productor["id_usuario"],
           "veterinario": veterinario["id_usuario"], "inactivo": inactivo["id_usuario"]}).all()
    assert sorted(a.id_usuario for a in avisos) == sorted((admin["id_usuario"], productor["id_usuario"]))
    assert all(a.id_usuario == a.id_usuario_evento for a in avisos)
    mensaje = avisos[0].mensaje
    assert "interrumpido manualmente" in mensaje and motivo not in mensaje
    for rol, headers, espera in (
        ("Administrador", admin_headers, True),
        ("Productor", productor_headers, True),
        ("Veterinario", veterinario_headers, False),
    ):
        bandeja = client.get("/notificaciones", headers=headers)
        assert bandeja.status_code == 200, bandeja.text
        recibido = any(aviso["mensaje"] == mensaje for aviso in bandeja.json()["items"])
        assert recibido == espera, rol


def test_migracion_recupera_causa_y_motivo_historicos(db_session, crear_usuario_db):
    assert db_session.get_bind().engine.url.host in ("127.0.0.1", "localhost", "::1")
    admin = crear_usuario_db(id_rol=1)
    revision = ScriptDirectory.from_config(Config("alembic.ini")).get_revision("f108174bc001").module
    with Operations.context(MigrationContext.configure(db_session.connection())):
        revision.downgrade()
        db_session.execute(text("""
            INSERT INTO modulo5.ejecuciones_batch_ica (estado, causa_interrupcion, id_usuario_interrupcion)
            VALUES ('INTERRUMPIDO', 'Motivo anterior', :admin),
                   ('INTERRUMPIDO', 'VENTANA_EXCEDIDA', NULL),
                   ('INTERRUMPIDO', 'REINICIO_SERVIDOR', NULL)
        """), {"admin": admin["id_usuario"]})
        revision.upgrade()
    filas = db_session.execute(text("""
        SELECT causa_interrupcion, motivo_interrupcion
        FROM modulo5.ejecuciones_batch_ica ORDER BY id_ejecucion
    """)).all()
    assert filas[-3:] == [
        ("MANUAL", "Motivo anterior"), ("VENTANA_EXCEDIDA", None), ("REINICIO_SERVIDOR", None),
    ]
