"""Adaptador de alcance por finca contra ``modulo9`` (RF-25).

Implementación concreta de ``AlcanceFincaPort``. Ningún rol tiene alcance
global, ni siquiera el Administrador: cada usuario ve solo las fincas a las que
tiene acceso activo en ``modulo9.usuarios_fincas`` (decisión del DBA en el PR
#485, F4 del control de acceso por BD). Es la misma regla que aplica RLS, así
que la aplicación y la base de datos no deciden distinto.

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


class AlcanceFincaAdapter(AlcanceFincaPort):
    """Resuelve el alcance de fincas del usuario consultando ``modulo9``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def es_global(self, id_rol: int) -> bool:
        return False

    def listar_ids_fincas_permitidas(self, id_usuario: int, id_rol: int) -> Optional[list[int]]:
        filas = self.db.execute(
            _SQL_FINCAS_DEL_USUARIO, {"id_usuario": id_usuario}
        ).fetchall()
        return [fila.id_finca for fila in filas]
