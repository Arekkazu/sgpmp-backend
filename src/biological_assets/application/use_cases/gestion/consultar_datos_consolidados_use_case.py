from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import DatosConsolidados, EventoAuditoria
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
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
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.indicadores_repo = indicadores_repo
        self.bitacora_repo = bitacora_repo

    def execute(
        self, id_activo: int, dto: DatosConsolidadosDTO, usuario: UsuarioActual
    ) -> DatosConsolidados:
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe en los registros del sistema.',
            )

        resultado = self.indicadores_repo.obtener_datos_consolidados(
            id_activo=id_activo,
            tipo_dato=dto.tipo_dato,
            fecha_inicio=dto.fecha_inicio,
            fecha_fin=dto.fecha_fin,
            pagina=dto.pagina,
            page_size=dto.page_size,
        )

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF50', tipo_evento='DATOS_ANALITICOS_CONSULTADOS',
                    clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo,
                    detalle_tecnico={'tipo_dato': dto.tipo_dato},
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return resultado
