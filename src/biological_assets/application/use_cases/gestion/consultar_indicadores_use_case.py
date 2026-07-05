from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, ResultadoIndicadores
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.indicadores_repository import IndicadoresRepository
from src.biological_assets.infrastructure.dto.consultar_indicadores_dto import ConsultarIndicadoresDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ConsultarIndicadoresUseCase:

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
        self, id_activo: int, dto: ConsultarIndicadoresDTO, usuario: UsuarioActual
    ) -> ResultadoIndicadores:
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe en los registros del sistema.',
            )

        resultado = self.indicadores_repo.calcular_indicadores(
            id_activo=id_activo,
            tipo_activo=activo.tipo,
            fecha_inicio=dto.fecha_inicio,
            fecha_fin=dto.fecha_fin,
            tipo_indicador=dto.tipo_indicador,
        )

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF51', tipo_evento='INDICADOR_CALCULADO',
                    clasificacion_biologica='GESTION_OPERATIVA', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    detalle_tecnico={'tipo_indicador': dto.tipo_indicador},
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return resultado
