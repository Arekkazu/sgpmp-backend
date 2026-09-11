from __future__ import annotations

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.infrastructure.dto.consultar_bitacora_dto import ConsultarBitacoraDTO


class ConsultarBitacoraUseCase:

    def __init__(self, db: Session, bitacora_repo: BitacoraAuditoriaRepository) -> None:
        self.db = db
        self.bitacora_repo = bitacora_repo

    def execute(self, dto: ConsultarBitacoraDTO) -> tuple[list[EventoAuditoria], int]:
        return self.bitacora_repo.consultar(
            rf_origen=dto.rf_origen,
            tipo_evento=dto.tipo_evento,
            id_activo_biologico=dto.id_activo_biologico,
            clasificacion_biologica=dto.clasificacion_biologica,
            resultado=dto.resultado,
            severidad_log=dto.severidad_log,
            fecha_inicio=dto.fecha_inicio,
            fecha_fin=dto.fecha_fin,
            pagina=dto.pagina,
            page_size=dto.page_size,
        )
