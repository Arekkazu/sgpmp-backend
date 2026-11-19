# | Fecha      | Nombre   | Que se hizo                                                             |
# |------------|----------|-------------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: instantánea de lectura con la identidad de quien pidió el reporte |
"""Instantánea de datos de un reporte (RF-104 Fase 2.1, CA-12, RNF-08).

Abre una sesión aparte en ``REPEATABLE READ`` y solo lectura: todas las consultas del reporte ven la BD tal como
estaba en la primera, aunque los módulos fuente cambien mientras se genera (M06 y M07 quedan consistentes entre
sí). Actúa como el usuario que pidió el reporte —también desde el proceso en segundo plano— para que la RLS acote
lo que ve, con su zona horaria para «hoy» y los días calendario. No persiste nada.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import text

from src.reporting.domain.repositories.fuente_reportes_repository import FuenteReportesRepository
from src.reporting.infrastructure.repositories.fuente_reportes_repository import SqlAlchemyFuenteReportesRepository
from src.shared.database import SessionLocal, declarar_identidad, sesion_sistema
from src.shared.fechas import establecer_zona_usuario, restablecer_zona_usuario

_SQL_ROL = text("SELECT r.nombre_rol FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol "
                "WHERE u.id_usuario = :id")


def _nombre_rol(id_usuario: int) -> str:
    db = sesion_sistema()
    try:
        return db.execute(_SQL_ROL, {"id": id_usuario}).scalar() or ""
    finally:
        db.close()


@contextmanager
def abrir_instantanea(id_usuario: int, zona_horaria: str) -> Generator[FuenteReportesRepository]:
    token = establecer_zona_usuario(zona_horaria)
    db = SessionLocal()
    try:
        declarar_identidad(db, id_usuario, _nombre_rol(id_usuario))
        db.connection(execution_options={"isolation_level": "REPEATABLE READ", "postgresql_readonly": True})
        yield SqlAlchemyFuenteReportesRepository(db)
    finally:
        db.rollback()
        db.close()
        restablecer_zona_usuario(token)
