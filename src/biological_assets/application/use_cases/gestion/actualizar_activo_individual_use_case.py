from __future__ import annotations

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.infrastructure.dto.actualizar_activo_individual_dto import ActualizarActivoIndividualDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ActualizarActivoIndividualUseCase:
    def __init__(self, db: Session, repo: ActivoBiologicoRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(self, id_activo: int, dto: ActualizarActivoIndividualDTO, usuario: UsuarioActual) -> ActivoBiologico:
        activo = self.repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )

        # actualizar_detalle_individual valida internamente que tipo == INDIVIDUAL
        activo.actualizar_detalle_individual(
            raza=dto.raza,
            sexo=dto.sexo,
            fecha_nacimiento=dto.fecha_nacimiento,
            peso_inicial=dto.peso_inicial,
        )

        try:
            activo = self.repo.actualizar_detalle_individual(activo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return activo
