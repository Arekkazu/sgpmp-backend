"""Caso de uso: asignar/desasignar fincas a un usuario (RF-25).

Operación exclusiva de administración (RBAC ``U`` sobre el recurso Usuarios).
Refleja la relación ``modulo9.fincas.id_usuario`` (1 finca = 1 dueño): asignar
una finca que ya tiene otro dueño se rechaza con 409; desmarcar una finca la
deja sin dueño (``id_usuario NULL``).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.asignar_fincas_dto import AsignarFincasDTO
from src.shared.errors import ConflictError, NotFoundError


class AsignarFincasUsuarioUseCase:

    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(
        self,
        id_usuario: int,
        dto: AsignarFincasDTO,
        usuario_actual: UsuarioActual,
    ) -> dict:
        if not self._existe_usuario(id_usuario):
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message="El usuario solicitado no existe.",
            )

        ids_deseados = set(dto.ids_fincas)

        # Validar existencia y dueño actual de cada finca solicitada.
        for id_finca in ids_deseados:
            fila = self.db.execute(
                text("SELECT id_usuario, nombre FROM modulo9.fincas WHERE id_finca = :id"),
                {"id": id_finca},
            ).mappings().first()
            if fila is None:
                raise NotFoundError(
                    code="FINCA_NO_ENCONTRADA",
                    message=f"No existe una finca con ID {id_finca}.",
                )
            if fila["id_usuario"] is not None and fila["id_usuario"] != id_usuario:
                raise ConflictError(
                    code="FINCA_YA_ASIGNADA",
                    message=f"La finca '{fila['nombre']}' ya está asignada a otro usuario.",
                    field="ids_fincas",
                )

        # Desasignar fincas que este usuario poseía y ya no están en la lista.
        self.db.execute(
            text(
                "UPDATE modulo9.fincas SET id_usuario = NULL, fecha_actualizacion = NOW() "
                "WHERE id_usuario = :id_usuario AND id_finca != ALL(:ids_fincas)"
            ),
            {"id_usuario": id_usuario, "ids_fincas": list(ids_deseados) or [0]},
        )

        # Asignar las fincas solicitadas.
        if ids_deseados:
            self.db.execute(
                text(
                    "UPDATE modulo9.fincas SET id_usuario = :id_usuario, fecha_actualizacion = NOW() "
                    "WHERE id_finca = ANY(:ids_fincas)"
                ),
                {"id_usuario": id_usuario, "ids_fincas": list(ids_deseados)},
            )

        self.db.commit()

        return {
            "id_usuario": id_usuario,
            "ids_fincas": sorted(ids_deseados),
        }

    def _existe_usuario(self, id_usuario: int) -> bool:
        return (
            self.db.execute(
                text("SELECT 1 FROM modulo1.usuarios WHERE id_usuario = :id"),
                {"id": id_usuario},
            ).first()
            is not None
        )
