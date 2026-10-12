"""Caso de uso: asignar/desasignar fincas a un usuario (RF-25).

Operación exclusiva de administración (RBAC ``U`` sobre el recurso Usuarios).
La lista enviada es el conjunto completo de fincas a las que el usuario accede,
en ``modulo9.usuarios_fincas`` (M:N). Varias personas pueden atender una misma
finca (RF-46: el Veterinario consulta los activos de la finca asignada), así
que una finca con otro dueño ya no se rechaza con 409 (INC-M02-61-G52). Retirar
una finca de la lista desactiva el acceso (la columna ``fincas.id_usuario`` se
retiró en F3: no hay otro registro de propietario).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.asignar_fincas_dto import AsignarFincasDTO
from src.shared.errors import GoneError, NotFoundError


class AsignarFincasUsuarioUseCase:
    """Sincroniza `modulo9.usuarios_fincas` con la lista de fincas recibida.

    Activa las fincas de la lista y desactiva las que ya no aparecen; responde
    404 si el usuario o alguna finca no existe y 410 si el usuario fue eliminado.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(
        self,
        id_usuario: int,
        dto: AsignarFincasDTO,
        usuario_actual: UsuarioActual,
    ) -> dict:
        usuario = self._estado_usuario(id_usuario)
        if usuario is None:
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message="El usuario solicitado no existe.",
            )
        # RF-06: la eliminación es lógica e irreversible; mismo 410 que la
        # edición de perfil (RF-11) para un usuario ya ELIMINADO.
        if usuario.id_estado_cuenta == Cuenta.ESTADO_ELIMINADO:
            raise GoneError(
                code="USUARIO_ELIMINADO",
                message=(
                    "El registro ya no está disponible. El usuario fue eliminado "
                    "y no se le pueden asignar fincas."
                ),
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

    def _estado_usuario(self, id_usuario: int):
        return self.db.execute(
            text(
                "SELECT c.id_estado_cuenta FROM modulo1.usuarios u "
                "LEFT JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario "
                "WHERE u.id_usuario = :id"
            ),
            {"id": id_usuario},
        ).first()
