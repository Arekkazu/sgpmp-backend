"""Adaptador de alcance por finca contra ``modulo9`` (RF-25).

Implementación concreta de ``AlcanceFincaPort``. El único rol con alcance global
es el protegido (``modulo1.roles.es_protegido``, el Administrador del sistema de
RF-19/M01). El resto ve solo las fincas a las que tiene acceso activo en
``modulo9.usuarios_fincas``. Es la misma regla que aplica RLS en
``modulo9.fn_fincas_del_usuario`` (migración ``f68851f9a433``), así que la
aplicación y la base de datos no deciden distinto.

INC-M02-61-G52: antes se leía ``modulo9.fincas.id_usuario`` (1 finca = 1 dueño).
Un Veterinario o Ingeniero de Campo nunca es dueño de la finca que atiende, así
que su lista quedaba vacía y cada activo le respondía 404.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.alcance_finca_port import AlcanceFincaPort

_SQL_FINCAS_DEL_USUARIO = text(
    "SELECT id_finca FROM modulo9.usuarios_fincas "
    "WHERE id_usuario = :id_usuario AND es_activo IS TRUE"
)
_SQL_ROL_PROTEGIDO = text("SELECT modulo1.fn_rol_protegido(:id_rol)")


class AlcanceFincaAdapter(AlcanceFincaPort):
    """Resuelve el alcance de fincas del usuario consultando ``modulo9``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def es_global(self, id_rol: int) -> bool:
        return bool(self.db.execute(_SQL_ROL_PROTEGIDO, {"id_rol": id_rol}).scalar())

    def listar_ids_fincas_permitidas(self, id_usuario: int, id_rol: int) -> Optional[list[int]]:
        if self.es_global(id_rol):
            return None
        filas = self.db.execute(
            _SQL_FINCAS_DEL_USUARIO, {"id_usuario": id_usuario}
        ).fetchall()
        return [fila.id_finca for fila in filas]
