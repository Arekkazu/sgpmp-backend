"""Integración RF-10: migración y archivado inmutable en PostgreSQL."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.auditoria.archivar_auditoria_use_case import (
    ArchivarAuditoriaUseCase,
)
from src.identity_access.infrastructure.repositories.evento_repository import (
    SqlAlchemyEventoRepository,
)
from src.identity_access.infrastructure.repositories.notificacion_repository import (
    SqlAlchemyNotificacionRepository,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
MIGRACION = (
    ROOT
    / "alembic"
    / "versions"
    / "8fc28a787fc8_rf10_retencion_auditoria_12_meses.py"
)


def _aplicar_migracion_si_falta(db_session: Session) -> None:
    existe = db_session.execute(
        text("SELECT to_regclass('modulo1.eventos_archivados')")
    ).scalar_one()
    if existe is not None:
        return

    spec = importlib.util.spec_from_file_location("migracion_rf10_retencion", MIGRACION)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    contexto = MigrationContext.configure(db_session.connection())
    with Operations.context(contexto):
        modulo.upgrade()


def test_migracion_crea_archivo_con_indices_y_trigger_inmutable(
    db_session: Session,
) -> None:
    _aplicar_migracion_si_falta(db_session)

    columnas = set(
        db_session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='modulo1'
                  AND table_name='eventos_archivados'
                """
            )
        ).scalars()
    )
    indices = set(
        db_session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname='modulo1'
                  AND tablename='eventos_archivados'
                """
            )
        ).scalars()
    )
    trigger = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM pg_trigger
            WHERE tgrelid='modulo1.eventos_archivados'::regclass
              AND tgname='trg_proteger_eventos_archivados'
              AND NOT tgisinternal
            """
        )
    ).scalar_one()

    assert {
        "id_evento",
        "fecha_evento",
        "hash_integridad",
        "fecha_archivado",
    }.issubset(columnas)
    assert {
        "eventos_archivados_pkey",
        "ix_eventos_archivados_fecha",
        "ix_eventos_archivados_usuario_fecha",
    }.issubset(indices)
    assert trigger == 1


def test_bloqueo_asesor_impide_dos_archivados_simultaneos(
    integration_engine: Engine,
) -> None:
    conexion_uno = integration_engine.connect()
    conexion_dos = integration_engine.connect()
    transaccion_uno = conexion_uno.begin()
    transaccion_dos = conexion_dos.begin()
    sesion_uno = Session(bind=conexion_uno)
    sesion_dos = Session(bind=conexion_dos)
    try:
        assert SqlAlchemyEventoRepository(sesion_uno).adquirir_bloqueo_archivado()
        assert not SqlAlchemyEventoRepository(sesion_dos).adquirir_bloqueo_archivado()
    finally:
        sesion_uno.close()
        sesion_dos.close()
        transaccion_uno.rollback()
        transaccion_dos.rollback()
        conexion_uno.close()
        conexion_dos.close()


def test_archiva_solo_mayores_de_doce_meses_sin_borrar_originales(
    db_session: Session,
    crear_usuario_db,
    crear_evento_db,
) -> None:
    _aplicar_migracion_si_falta(db_session)
    usuario = crear_usuario_db()
    referencia = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)
    hash_original = "a" * 64
    antiguo = crear_evento_db(
        id_usuario=usuario["id_usuario"],
        tipo_evento=1,
        categoria="AUTENTICACION",
        fecha=datetime(2025, 8, 27, 3, 59, 59, tzinfo=timezone.utc),
        hash_integridad=hash_original,
    )
    limite = crear_evento_db(
        id_usuario=usuario["id_usuario"],
        tipo_evento=2,
        categoria="AUTENTICACION",
        fecha=datetime(2025, 8, 27, 4, 0, tzinfo=timezone.utc),
    )
    reciente = crear_evento_db(
        id_usuario=usuario["id_usuario"],
        tipo_evento=3,
        categoria="AUTENTICACION",
        fecha=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    id_notificacion = SqlAlchemyNotificacionRepository(db_session).registrar(
        id_evento=antiguo,
        id_usuario=usuario["id_usuario"],
        id_canal=2,
        mensaje="Referencia que debe conservar su FK",
        estado="en_cola",
    )

    caso = ArchivarAuditoriaUseCase(
        eventos_repo=SqlAlchemyEventoRepository(db_session),
        db=db_session,
    )
    resultado = caso.execute(referencia)
    repetido = caso.execute(referencia)

    archivados = db_session.execute(
        text(
            """
            SELECT id_evento, hash_integridad
            FROM modulo1.eventos_archivados
            WHERE id_evento IN (:antiguo, :limite, :reciente)
            ORDER BY id_evento
            """
        ),
        {"antiguo": antiguo, "limite": limite, "reciente": reciente},
    ).all()
    originales = db_session.execute(
        text(
            """
            SELECT id_evento
            FROM modulo1.eventos
            WHERE id_evento IN (:antiguo, :limite, :reciente)
            ORDER BY id_evento
            """
        ),
        {"antiguo": antiguo, "limite": limite, "reciente": reciente},
    ).scalars().all()
    notificacion_existe = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM modulo1.notificaciones
            WHERE id_notificacion=:id AND id_evento=:evento
            """
        ),
        {"id": id_notificacion, "evento": antiguo},
    ).scalar_one()

    assert resultado.eventos_archivados == 1
    assert repetido.eventos_archivados == 0
    assert archivados == [(antiguo, hash_original)]
    assert originales == sorted([antiguo, limite, reciente])
    assert notificacion_existe == 1

    with pytest.raises(DBAPIError, match="IMMUTABLE_RECORD"):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    """
                    UPDATE modulo1.eventos_archivados
                    SET categoria='MODIFICACION'
                    WHERE id_evento=:id
                    """
                ),
                {"id": antiguo},
            )
