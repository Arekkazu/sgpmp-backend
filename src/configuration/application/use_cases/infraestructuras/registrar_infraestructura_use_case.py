"""Caso de uso: Registrar área productiva (POST RF-20)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.repositories.auditoria_infraestructura_repository import AuditoriaInfraestructuraRepository
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.superficie import Superficie
from src.configuration.infrastructure.dto.registrar_infraestructura_dto import RegistrarInfraestructuraDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class RegistrarInfraestructuraUseCase:

    def __init__(
        self,
        db: Session,
        infra_repo: InfraestructuraRepository,
        finca_repo: FincaRepository,
        auditoria_repo: AuditoriaInfraestructuraRepository,
    ) -> None:
        self.db = db
        self.infra_repo = infra_repo
        self.finca_repo = finca_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RegistrarInfraestructuraDTO, usuario_actual: UsuarioActual) -> Infraestructura:
        finca = self.finca_repo.obtener_por_id(dto.finca_id)
        if finca is None:
            raise NotFoundError(
                code="FINCA_NO_ENCONTRADA",
                message=f"No existe una finca con ID {dto.finca_id}.",
            )
        if not finca.es_activo:
            raise BusinessRuleError(
                code="FINCA_INACTIVA",
                message="No se puede registrar infraestructura en una finca inactiva.",
            )

        nombre = NombreInfraestructura(dto.nombre_infraestructura)
        superficie = Superficie(dto.superficie)

        infra = Infraestructura.crear(
            nombre=nombre,
            tipo=dto.tipo_area.value,
            superficie=superficie,
            id_finca=dto.finca_id,
            descripcion=dto.descripcion_infraestructura,
        )

        try:
            infra_guardada = self.infra_repo.guardar(infra)
            self.auditoria_repo.registrar(
                id_infraestructura=infra_guardada.id_infraestructura,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=infra_guardada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return infra_guardada
