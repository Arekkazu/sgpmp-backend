# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-19 | Leandro | INC-M07-371-G58 RF-102: probar límites, inmutabilidad, recuperación y reintento. |
"""Regresiones de RF-102 con PostgreSQL y la identidad de servicio existente."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.accounting_integration.application.use_cases.clientes.registrar_cliente_externo_use_case import SolicitudCliente
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion, TIPOS_AUDITOR
from src.accounting_integration.infrastructure import archivo_auditoria_worker
from src.accounting_integration.infrastructure.adapters.alerta_administrador_adapter import alertador_administrador
from src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository import (
    SqlAlchemyAuditoriaIntegracionRepository,
)
from src.shared.database import declarar_identidad, declarar_identidad_sistema
from tests.integration.test_m07_integracion_aaef_integration import cliente_http  # noqa: F401

pytestmark = pytest.mark.integration


def _evento(tipo, fecha, **campos):
    return EventoIntegracion(
        tipo_evento=tipo, fecha_evento=fecha, fecha_registro=fecha, endpoint="/rf102/g58", metodo_http="GET",
        codigo_resultado="OK", codigo_http=200, latencia_ms=1, numero_id_tributaria="900555111",
        hash_contenido="a" * 64, tamano_payload_bytes=64, version_contrato="3.0",
        ip_origen="203.0.113.55", json_detalle={"resultado": "Registro de prueba"}, **campos,
    )


def _corte(db, anos):
    return db.scalar(text("""
        SELECT ((now() AT TIME ZONE 'UTC') - make_interval(years => :anos)) AT TIME ZONE 'UTC'
    """), {"anos": anos}).astimezone(timezone.utc)


def _en_tabla(db, historico=False):
    tabla = "eventos_integracion_archivados" if historico else "eventos_integracion"
    return dict(db.execute(text(f"""
        SELECT id_evento_integracion::text, hash_integridad FROM modulo7.{tabla}
        WHERE endpoint = '/rf102/g58'
    """)).all())


@pytest.fixture
def trabajador(db_session, monkeypatch):
    avisos = []

    def sesion_trabajo():
        db = Session(bind=db_session.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint")
        db.execute(text("SET LOCAL ROLE sgpmp_app"))
        declarar_identidad_sistema(db)
        return db

    monkeypatch.setattr(archivo_auditoria_worker, "sesion_sistema", sesion_trabajo)

    def alertador(_fabrica):
        return lambda _mensaje, detalle: avisos.append(detalle)

    monkeypatch.setattr(archivo_auditoria_worker, "alertador_administrador", alertador)
    return avisos


def test_worker_retencion_por_tipo_y_recuperacion_http(
    db_session, trabajador, cliente_http, crear_usuario_db, crear_auth_headers,
):
    admin = crear_usuario_db(id_rol=1, estado=2)
    productor = crear_usuario_db(id_rol=2, estado=2)
    cliente = db_session.execute(text("SELECT min(id_cliente_externo) FROM modulo7.clientes_externos")).scalar_one()
    if cliente is None:
        # PAQUETE_AAEF requiere cliente. Usar la misma fila que crea RF-101.
        from src.accounting_integration.infrastructure.factoria import M07

        externo, _ = M07(db_session).registrar_cliente().execute(
            SolicitudCliente("qa-retencion", "Cliente QA retención", "qa-retencion",
                             (datetime.now(timezone.utc) + timedelta(days=5)).date()),
            admin["id_usuario"],
        )
        cliente = externo.id_cliente_externo
    cinco, diez = _corte(db_session, 5), _corte(db_session, 10)
    margen = timedelta(hours=1)
    viejos = [_evento("SOLICITUD_RECHAZADA", cinco - margen)]
    vigentes = [_evento("SOLICITUD_RECHAZADA", cinco + margen)]
    for tipo in TIPOS_AUDITOR:
        viejos.append(_evento(tipo, diez - margen, id_cliente_externo=cliente))
        vigentes.append(_evento(tipo, diez + margen, id_cliente_externo=cliente))
    vigentes.append(replace(_evento("SOLICITUD_RECHAZADA", diez), fecha_registro=datetime.now(timezone.utc)))
    repo = SqlAlchemyAuditoriaIntegracionRepository(db_session)
    for evento in viejos + vigentes:
        repo.registrar(evento)

    assert archivo_auditoria_worker.ejecutar_archivado()
    db_session.execute(text("RESET ROLE"))
    assert _en_tabla(db_session, True) == {e.id_evento_integracion: e.hash_integridad for e in viejos}
    assert _en_tabla(db_session) == {e.id_evento_integracion: e.hash_integridad for e in vigentes}
    assert archivo_auditoria_worker.ejecutar_archivado()
    db_session.execute(text("RESET ROLE"))
    assert len(_en_tabla(db_session, True)) == len(viejos)
    assert trabajador == []

    admin_headers = crear_auth_headers(admin)
    ruta = "/integracion/auditoria"
    r = cliente_http.get(ruta, headers=admin_headers, params={"endpoint": "/rf102/g58", "tamano": 2})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == len(viejos + vigentes)
    assert len(r.json()["items"]) == 2
    exportacion = cliente_http.get(ruta + "/exportar", headers=admin_headers, params={
        "formato": "json", "endpoint": "/rf102/g58",
    })
    assert exportacion.status_code == 200, exportacion.text
    assert {x["id_evento_integracion"] for x in exportacion.json()} == {e.id_evento_integracion for e in viejos + vigentes}
    assert all(x["integridad"] == "INTEGRO" for x in exportacion.json())
    assert cliente_http.get(ruta, headers=crear_auth_headers(productor)).status_code == 403


def test_fallo_despues_de_copiar_revierte_y_reintenta(db_session, trabajador, monkeypatch):
    fecha = _corte(db_session, 10)
    bueno = _evento("SOLICITUD_RECHAZADA", fecha)
    corrupto = _evento("SOLICITUD_RECHAZADA", fecha)
    repo = SqlAlchemyAuditoriaIntegracionRepository(db_session)
    repo.registrar(bueno)
    repo.registrar(corrupto)
    # Sólo la preparación de esta fila simula corrupción fuera de la aplicación.
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("""
        UPDATE modulo7.eventos_integracion SET hash_integridad = repeat('0', 64)
        WHERE id_evento_integracion = CAST(:id AS uuid)
    """), {"id": corrupto.id_evento_integracion})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    archivar = SqlAlchemyAuditoriaIntegracionRepository.archivar

    def copia_fallida(repo, ids):
        assert archivar(repo, ids)
        return []

    with monkeypatch.context() as cambios:
        cambios.setattr(SqlAlchemyAuditoriaIntegracionRepository, "archivar", copia_fallida)
        assert not archivo_auditoria_worker.ejecutar_archivado()
    db_session.execute(text("RESET ROLE"))
    assert set(_en_tabla(db_session)) == {bueno.id_evento_integracion, corrupto.id_evento_integracion}
    assert _en_tabla(db_session, True) == {}
    assert trabajador[-1]["causa"] == "FALLO_ARCHIVADO"

    assert archivo_auditoria_worker.ejecutar_archivado()
    db_session.execute(text("RESET ROLE"))
    assert _en_tabla(db_session, True) == {bueno.id_evento_integracion: bueno.hash_integridad}
    assert _en_tabla(db_session) == {corrupto.id_evento_integracion: "0" * 64}
    assert trabajador[-1]["ids_evento"] == [corrupto.id_evento_integracion]
    with pytest.raises(DBAPIError) as exc, db_session.begin_nested():
        db_session.execute(text("""
            INSERT INTO modulo7.eventos_integracion SELECT * FROM modulo7.eventos_integracion_archivados
            WHERE id_evento_integracion = CAST(:id AS uuid)
        """), {"id": bueno.id_evento_integracion})
    assert exc.value.orig.pgcode == "23505"


def test_dos_conexiones_no_procesan_el_mismo_lote(integration_engine, db_session, trabajador):
    antiguo = _evento("SOLICITUD_RECHAZADA", _corte(db_session, 10))
    SqlAlchemyAuditoriaIntegracionRepository(db_session).registrar(antiguo)
    with integration_engine.connect() as otra_replica:
        otra_replica.execute(text("SELECT pg_advisory_xact_lock(102, 7)"))
        assert archivo_auditoria_worker.ejecutar_archivado()
        db_session.execute(text("RESET ROLE"))
        assert _en_tabla(db_session, True) == {}
        assert antiguo.id_evento_integracion in _en_tabla(db_session)

    assert archivo_auditoria_worker.ejecutar_archivado()
    db_session.execute(text("RESET ROLE"))
    assert _en_tabla(db_session, True) == {antiguo.id_evento_integracion: antiguo.hash_integridad}
    assert trabajador == []


def test_fallo_del_archivado_genera_aviso_critico_por_administrador(
    db_session, trabajador, crear_usuario_db, monkeypatch,
):
    admins = {crear_usuario_db(id_rol=1, estado=2)["id_usuario"] for _ in range(2)}
    productor = crear_usuario_db(id_rol=2, estado=2)["id_usuario"]
    monkeypatch.setattr(archivo_auditoria_worker, "alertador_administrador", alertador_administrador)

    def fallo(repo, cursor, limite):
        repo.db.execute(text("SELECT modulo7.fn_simular_fallo_de_archivo_rf102()"))

    with monkeypatch.context() as cambios:
        cambios.setattr(SqlAlchemyAuditoriaIntegracionRepository, "candidatos_archivo", fallo)
        assert not archivo_auditoria_worker.ejecutar_archivado()
    db_session.execute(text("RESET ROLE"))
    avisos = db_session.execute(text("""
        SELECT n.id_usuario, e.id_usuario AS propietario, n.nivel
          FROM modulo1.notificaciones n JOIN modulo1.eventos e USING (id_evento)
         WHERE e.modulo = 'MODULO7' AND e.detalle->>'causa' = 'FALLO_ARCHIVADO'
    """)).all()
    assert {(a.id_usuario, a.propietario, a.nivel) for a in avisos if a.id_usuario in admins} == {
        (uid, uid, "CRITICA") for uid in admins
    }
    assert productor not in {a.id_usuario for a in avisos}


def test_solo_el_servicio_traslada_y_la_bd_protege_el_registro(db_session, crear_usuario_db):
    uid = crear_usuario_db(id_rol=1, estado=2)["id_usuario"]
    reciente = _evento("SOLICITUD_RECHAZADA", _corte(db_session, 5) + timedelta(hours=1))
    viejo = _evento("SOLICITUD_RECHAZADA", _corte(db_session, 10))
    repo = SqlAlchemyAuditoriaIntegracionRepository(db_session)
    repo.registrar(reciente)
    repo.registrar(viejo)
    db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
    declarar_identidad(db_session, uid, "Administrador")
    with pytest.raises(DBAPIError) as exc, db_session.begin_nested():
        repo.archivar([viejo.id_evento_integracion])
    assert exc.value.orig.pgcode == "42501"
    for sql in (
        "DELETE FROM modulo7.eventos_integracion",
        "INSERT INTO modulo7.eventos_integracion_archivados SELECT * FROM modulo7.eventos_integracion",
        "DELETE FROM modulo7.identidades_eventos_integracion",
    ):
        with pytest.raises(DBAPIError) as exc, db_session.begin_nested():
            db_session.execute(text(sql))
        assert exc.value.orig.pgcode == "42501"

    declarar_identidad_sistema(db_session)
    assert repo.archivar([reciente.id_evento_integracion]) == []
    assert repo.archivar([viejo.id_evento_integracion]) == [(viejo, viejo.hash_integridad)]
    db_session.execute(text("RESET ROLE"))
    for sql in (
        "DELETE FROM modulo7.eventos_integracion",
        "UPDATE modulo7.eventos_integracion_archivados SET hash_integridad = repeat('0',64)",
        "DELETE FROM modulo7.eventos_integracion_archivados",
        "TRUNCATE modulo7.eventos_integracion_archivados",
    ):
        with pytest.raises(DBAPIError, match="TGR-M07-14"), db_session.begin_nested():
            db_session.execute(text(sql))
