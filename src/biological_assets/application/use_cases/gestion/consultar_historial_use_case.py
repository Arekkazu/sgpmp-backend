from __future__ import annotations

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import PaginaHistorial
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.transferencia_repository import TransferenciaRepository
from src.biological_assets.infrastructure.dto.consultar_historial_dto import ConsultarHistorialDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ConsultarHistorialUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        transferencia_repo: TransferenciaRepository,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.transferencia_repo = transferencia_repo

    def execute(self, id_activo: int, dto: ConsultarHistorialDTO, usuario: UsuarioActual) -> PaginaHistorial:
        # E-01: el activo debe existir
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no fue encontrado en el sistema.',
            )

        return self.transferencia_repo.consultar_historial(
            id_activo=id_activo,
            fecha_inicio=dto.fecha_inicio,
            fecha_fin=dto.fecha_fin,
            categoria=dto.categoria_evento,
            pagina=dto.pagina,
            page_size=dto.page_size,
        )
