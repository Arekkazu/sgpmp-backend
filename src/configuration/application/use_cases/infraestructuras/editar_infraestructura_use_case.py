"""Caso de uso: Editar área productiva (PATCH RF-20). Concurrencia optimista (FA-14)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.repositories.auditoria_infraestructura_repository import AuditoriaInfraestructuraRepository
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.domain.repositories.tipo_area_repository import TipoAreaRepository
from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.superficie import Superficie
from src.configuration.infrastructure.dto.editar_infraestructura_dto import EditarInfraestructuraDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError, PreconditionFailedError


class EditarInfraestructuraUseCase:

    def __init__(
        self,
        db: Session,
        infra_repo: InfraestructuraRepository,
        finca_repo: FincaRepository,
        tipo_area_repo: TipoAreaRepository,
        auditoria_repo: AuditoriaInfraestructuraRepository,
    ) -> None:
        self.db = db
        self.infra_repo = infra_repo
        self.finca_repo = finca_repo
        self.tipo_area_repo = tipo_area_repo
        self.auditoria_repo = auditoria_repo

    def execute(
        self, id_infraestructura: int, dto: EditarInfraestructuraDTO, usuario_actual: UsuarioActual
    ) -> Infraestructura:
        infra = self.infra_repo.obtener_por_id(id_infraestructura)
        if infra is None:
            raise NotFoundError(
                code="INFRAESTRUCTURA_NO_ENCONTRADA",
                message=f"No existe un área productiva con ID {id_infraestructura}.",
            )

        finca = self.finca_repo.obtener_por_id(infra.id_finca)
        if finca is None or not finca.es_activo:
            raise BusinessRuleError(
                code="FINCA_INACTIVA_O_INEXISTENTE",
                message=(
                    "No es posible editar el área productiva porque la finca asociada "
                    "no existe o se encuentra inactiva."
                ),
            )

        ts_actual = infra.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion
        if ts_actual is not None and ts_dto is not None:
            if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message=(
                        "La información del área ha sido actualizada por otro usuario. "
                        "Por favor, refresque la vista antes de aplicar sus cambios."
                    ),
                )
        elif ts_actual != ts_dto:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message="El registro fue modificado por otro usuario. Recarga y reintenta.",
            )

        tipo_area = self.tipo_area_repo.obtener_por_nombre(dto.tipo_area)
        if tipo_area is None or not tipo_area.es_activo:
            raise BusinessRuleError(
                code="TIPO_AREA_NO_RECONOCIDO",
                message=(
                    f"El tipo de área '{dto.tipo_area}' no corresponde a ningún tipo activo "
                    "en el catálogo de infraestructura productiva."
                ),
                field="tipo_area",
            )

        snapshot_anterior = infra._snapshot()

        nombre = NombreInfraestructura(dto.nombre_infraestructura)
        superficie = Superficie(dto.superficie)

        infra.actualizar(
            nombre=nombre,
            tipo=tipo_area.nombre,
            superficie=superficie,
            descripcion=dto.descripcion_infraestructura,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

        try:
            infra_actualizada = self.infra_repo.actualizar(infra)
            self.auditoria_repo.registrar(
                id_infraestructura=infra_actualizada.id_infraestructura,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_nuevos=infra_actualizada._snapshot(),
                valores_anteriores=snapshot_anterior,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return infra_actualizada
