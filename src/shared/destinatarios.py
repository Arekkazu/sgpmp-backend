# | Fecha      | Nombre   | Que se hizo                                                              |
# |------------|----------|--------------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-105: Administradores como destinatarios de respaldo de los avisos |
"""RF-105 Fase 1: si un aviso no tiene destinatarios con el rol que le corresponde en la finca, se envía al
Administrador para que no se pierda. El usuario de servicio (procesos de fondo) no recibe avisos."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.database import CORREO_USUARIO_SERVICIO, como_sistema

_SQL_ADMINISTRADORES = text("""
    SELECT u.id_usuario FROM modulo1.usuarios u
    WHERE modulo1.fn_rol_protegido(u.id_rol) AND u.correo_electronico <> :servicio
    ORDER BY u.id_usuario
""")


def ids_administradores(db: Session) -> list[int]:
    """Administradores (rol protegido). Se leen como sistema: la RLS de usuarios solo deja ver el propio."""
    with como_sistema(db):
        return list(db.execute(_SQL_ADMINISTRADORES, {"servicio": CORREO_USUARIO_SERVICIO}).scalars().all())
