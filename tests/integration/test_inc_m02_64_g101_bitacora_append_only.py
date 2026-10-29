"""INC-M02-64-G101 (#489, RF-52 CA-3): la bitácora de M02 es append-only en la base.

RF-52, restricción 1: la inmutabilidad "debe estar implementada a nivel de base
de datos, no solo a nivel de lógica de negocio". Sin trigger, cualquier conexión
con privilegios podía modificar o borrar registros. La migración 785d330f7541
bloquea UPDATE, DELETE y TRUNCATE (SQLSTATE P0252) para todos los roles; el
INSERT, único camino de la aplicación, sigue funcionando.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
    SqlAlchemyBitacoraAuditoriaRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def id_registro(db_session: Session) -> int:
    tipo_evento = f'FIXTURE_G101_{uuid.uuid4().hex[:8].upper()}'
    SqlAlchemyBitacoraAuditoriaRepository(db_session).registrar(
        EventoAuditoria(
            rf_origen='RF52',
            tipo_evento=tipo_evento,
            clasificacion_biologica='GESTION_OPERATIVA',
            timestamp_evento=datetime.now(timezone.utc),
            descripcion='Fixture INC-M02-64-G101',
        )
    )
    return db_session.execute(
        text('SELECT id_bitacora FROM modulo2.bitacora_auditoria_m02 WHERE tipo_evento = :t'),
        {'t': tipo_evento},
    ).scalar_one()


@pytest.mark.parametrize(
    'sentencia',
    [
        "UPDATE modulo2.bitacora_auditoria_m02 SET descripcion = 'alterado' WHERE id_bitacora = :id",
        'DELETE FROM modulo2.bitacora_auditoria_m02 WHERE id_bitacora = :id',
        'TRUNCATE modulo2.bitacora_auditoria_m02',
    ],
    ids=['update', 'delete', 'truncate'],
)
def test_la_base_rechaza_modificar_o_borrar_la_bitacora(db_session: Session, id_registro: int, sentencia: str) -> None:
    with pytest.raises(DBAPIError) as rechazo:
        with db_session.begin_nested():
            db_session.execute(text(sentencia), {'id': id_registro})

    assert rechazo.value.orig.pgcode == 'P0252'
    assert 'IMMUTABLE_AUDIT' in str(rechazo.value.orig)
    descripcion = db_session.execute(
        text('SELECT descripcion FROM modulo2.bitacora_auditoria_m02 WHERE id_bitacora = :id'),
        {'id': id_registro},
    ).scalar_one()
    assert descripcion == 'Fixture INC-M02-64-G101'
