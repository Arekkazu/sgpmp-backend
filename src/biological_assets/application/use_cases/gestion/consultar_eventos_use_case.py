from __future__ import annotations

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoActivo
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.shared.errors import BusinessRuleError, NotFoundError


class ConsultarEventosUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo

    def execute(self, id_activo: int) -> list[EventoActivo]:
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(code='ACTIVO_NO_ENCONTRADO', message=f'El lote con id {id_activo} no existe.')
        if activo.tipo != 'POBLACIONAL':
            raise BusinessRuleError(
                code='TIPO_INVALIDO',
                message='El historial de eventos de lote solo aplica a activos de tipo POBLACIONAL.',
            )
        return self.evento_repo.listar_por_activo(id_activo)
