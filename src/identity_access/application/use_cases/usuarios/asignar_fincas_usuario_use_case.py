"""Caso de uso: asignar/desasignar fincas a un usuario (RF-25).

Operación exclusiva de administración (RBAC ``U`` sobre el recurso Usuarios).
La lista enviada es el conjunto completo de fincas a las que el usuario accede,
en ``modulo9.usuarios_fincas`` (M:N). Varias personas pueden atender una misma
finca (RF-46: el Veterinario consulta los activos de la finca asignada), así
que una finca con otro dueño ya no se rechaza con 409 (INC-M02-61-G52). Retirar
una finca de la lista desactiva el acceso; ``fincas.id_usuario`` (propietario)
no se toca.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.asignar_fincas_dto import AsignarFincasDTO
from src.shared.errors import NotFoundError


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

        for id_finca in ids_deseados:
            existe = self.db.execute(
                text("SELECT 1 FROM modulo9.fincas WHERE id_finca = :id"),
                {"id": id_finca},
            ).first()
            if existe is None:
                raise NotFoundError(
                    code="FINCA_NO_ENCONTRADA",
                    message=f"No existe una finca con ID {id_finca}.",
                )

        # Revocar el acceso a las fincas que ya no están en la lista.
        self.db.execute(
            text(
                "UPDATE modulo9.usuarios_fincas SET es_activo = FALSE "
                "WHERE id_usuario = :id_usuario AND es_activo IS TRUE "
                "AND id_finca != ALL(:ids_fincas)"
            ),
            {"id_usuario": id_usuario, "ids_fincas": list(ids_deseados) or [0]},
        )

        # Conceder (o reactivar) el acceso a las fincas solicitadas.
        if ids_deseados:
            self.db.execute(
                text(
                    "INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) "
                    "SELECT :id_usuario, unnest(CAST(:ids_fincas AS integer[])) "
                    "ON CONFLICT ON CONSTRAINT uq_usuario_finca DO UPDATE SET es_activo = TRUE"
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
