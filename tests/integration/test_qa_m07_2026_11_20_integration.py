# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-20 | Arekkazu | QA-M07 CU07 H-01 y CU04 H-03: días del filtro de la auditoría y aviso por mensaje |
"""Reporte de QA de M07 del 2026-11-19 contra PostgreSQL."""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.domain.repositories.auditoria_integracion_repository import FiltrosAuditoria
from src.accounting_integration.infrastructure.adapters.alerta_administrador_adapter import alertador_administrador
from src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository import (
    SqlAlchemyAuditoriaIntegracionRepository,
)
from src.shared.database import declarar_identidad_sistema

pytestmark = pytest.mark.integration

ENDPOINT = "/qa-m07/cu07-h01"


def test_cu07_h01_un_evento_de_las_8_58_pm_cae_en_el_dia_de_colombia(db_session, en_colombia):
    # 2026-11-19 01:58 UTC es el 18/11 a las 8:58 p. m. en Colombia.
    instante = datetime(2026, 11, 19, 1, 58, tzinfo=timezone.utc)
    repo = SqlAlchemyAuditoriaIntegracionRepository(db_session)
    repo.registrar(EventoIntegracion(
        tipo_evento="SOLICITUD_RECHAZADA", fecha_evento=instante, fecha_registro=instante, endpoint=ENDPOINT,
        metodo_http="GET", codigo_resultado="REGLA_NEGOCIO", codigo_http=422, latencia_ms=1,
        numero_id_tributaria="901444215"))

    def total(dia):
        return repo.consultar(FiltrosAuditoria(desde=dia, hasta=dia, endpoint=ENDPOINT), 1, 10)[1]

    assert total(date(2026, 11, 18)) == 1
    assert total(date(2026, 11, 19)) == 0


def test_cu04_h03_dos_avisos_distintos_seguidos_llegan_los_dos(db_session, crear_usuario_db):
    admin = crear_usuario_db(id_rol=1, estado=2)["id_usuario"]

    def sesion():
        db = Session(bind=db_session.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint")
        db.execute(text("SET LOCAL ROLE sgpmp_app"))
        declarar_identidad_sistema(db)
        return db

    alertar = alertador_administrador(sesion)
    cuatro = "La versión 4.0 del contrato contable no pudo activarse: QA-M07 H-03 límite"
    cinco = "La versión 5.0 del contrato contable no pudo activarse: QA-M07 H-03 anexo"
    alertar(cuatro, {"version_contrato": "4.0"})
    alertar(cinco, {"version_contrato": "5.0"})
    alertar(cuatro, {"version_contrato": "4.0"})  # mismo mensaje en la ventana: no se repite
    db_session.execute(text("RESET ROLE"))
    avisos = db_session.execute(text("""
        SELECT mensaje, ocurrencias FROM modulo1.notificaciones
         WHERE id_usuario = :u AND mensaje LIKE '%QA-M07 H-03%'
    """), {"u": admin}).all()
    assert sorted((a.mensaje, a.ocurrencias) for a in avisos) == [(cuatro, 1), (cinco, 1)]
