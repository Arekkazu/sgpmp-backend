from __future__ import annotations

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import DatosConsolidados
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.indicadores_repository import IndicadoresRepository
from src.biological_assets.infrastructure.dto.datos_consolidados_dto import DatosConsolidadosDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ConsultarDatosConsolidadosUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        indicadores_repo: IndicadoresRepository,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.indicadores_repo = indicadores_repo

    def execute(
        self, id_activo: int, dto: DatosConsolidadosDTO, usuario: UsuarioActual
    ) -> DatosConsolidados:
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe en los registros del sistema.',
            )

        return self.indicadores_repo.obtener_datos_consolidados(
            id_activo=id_activo,
            tipo_dato=dto.tipo_dato,
            fecha_inicio=dto.fecha_inicio,
            fecha_fin=dto.fecha_fin,
            pagina=dto.pagina,
            page_size=dto.page_size,
        )
