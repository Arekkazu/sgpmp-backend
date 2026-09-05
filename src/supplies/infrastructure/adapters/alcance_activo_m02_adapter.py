"""Adaptador de alcance de activos por rol contra ``modulo2`` (RF-81 / CU-04).

Única pieza del sistema con lógica condicional por ``id_rol`` para esta
funcionalidad — deliberado: aísla la deuda de que no existe un modelo real de
"unidad productiva asignada a un usuario" (ver
``anotaciones/modulo_5/cu04_gaps_bd_rf77_rf81.md``). El use case y el router
no saben nada de roles; solo llaman a ``AlcanceActivoPort``.

Regla interina: el Gestor de Granja (id_rol=7) solo ve los activos que él
mismo registró (``modulo2.activos_biologicos.id_usuario``). El resto de roles
con permiso RBAC sobre el recurso 52 (Administrador, Productor, Veterinario,
Contador, Revisor Fiscal) no tienen restricción de alcance.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.supplies.domain.repositories.alcance_activo_port import AlcanceActivoPort

_ROL_GESTOR_GRANJA = 7

_SQL_ACTIVOS_DEL_USUARIO = text(
    "SELECT id_activo_biologico FROM modulo2.activos_biologicos WHERE id_usuario = :id_usuario"
)


class AlcanceActivoM02Adapter(AlcanceActivoPort):
    """Resuelve el alcance de activos del usuario consultando ``modulo2``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar_ids_activos_permitidos(self, id_usuario: int, id_rol: int) -> Optional[list[int]]:
        if id_rol != _ROL_GESTOR_GRANJA:
            return None
        filas = self.db.execute(_SQL_ACTIVOS_DEL_USUARIO, {"id_usuario": id_usuario}).fetchall()
        return [f.id_activo_biologico for f in filas]
