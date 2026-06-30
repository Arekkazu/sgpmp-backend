from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, PaginaHistorial
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
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
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.transferencia_repo = transferencia_repo
        self.bitacora_repo = bitacora_repo

    def execute(self, id_activo: int, dto: ConsultarHistorialDTO, usuario: UsuarioActual) -> PaginaHistorial:
        # E-01: el activo debe existir
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no fue encontrado en el sistema.',
            )

        resultado = self.transferencia_repo.consultar_historial(
            id_activo=id_activo,
            fecha_inicio=dto.fecha_inicio,
            fecha_fin=dto.fecha_fin,
            categoria=dto.categoria_evento,
            pagina=dto.pagina,
            page_size=dto.page_size,
        )

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF46', tipo_evento='HISTORIAL_CONSULTADO',
                    clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo,
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return resultado
