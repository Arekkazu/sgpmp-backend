"""Adaptador de alcance por finca contra ``modulo9`` (RF-25).

Implementación concreta de ``AlcanceFincaPort``. La decisión "global vs.
restringido" se resuelve por RBAC usando ``tiene_permiso`` sobre el recurso
``fincas`` (id_recurso=9): quien puede gestionarlas (actualizar/desactivar)
conserva la vista global; el resto queda limitado a las fincas vinculadas a su
usuario por ``modulo9.fincas.id_usuario``.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.alcance_finca_port import AlcanceFincaPort
from src.shared.rbac import tiene_permiso

_RECURSO_FINCAS = 9
_ACCION_ACTUALIZAR = 3
_ACCION_DESACTIVAR = 4

_SQL_FINCAS_DEL_USUARIO = text(
    "SELECT id_finca FROM modulo9.fincas WHERE id_usuario = :id_usuario"
)


class AlcanceFincaAdapter(AlcanceFincaPort):
    """Resuelve el alcance de fincas del usuario consultando ``modulo9``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def es_global(self, id_rol: int) -> bool:
        return (
            tiene_permiso(self.db, id_rol, _RECURSO_FINCAS, _ACCION_ACTUALIZAR)
            or tiene_permiso(self.db, id_rol, _RECURSO_FINCAS, _ACCION_DESACTIVAR)
        )

    def listar_ids_fincas_permitidas(self, id_usuario: int, id_rol: int) -> Optional[list[int]]:
        if self.es_global(id_rol):
            return None
        filas = self.db.execute(
            _SQL_FINCAS_DEL_USUARIO, {"id_usuario": id_usuario}
        ).fetchall()
        return [fila.id_finca for fila in filas]
