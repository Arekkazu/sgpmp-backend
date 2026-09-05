from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, EventoAuditoria
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ConsultarActivoUseCase:
    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.bitacora_repo = bitacora_repo

    def execute(self, id_activo: int, usuario: Optional[UsuarioActual] = None) -> ActivoBiologico:
        activo = self.repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF35', tipo_evento='ACTIVO_INDIVIDUAL_CONSULTA',
                    clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    id_usuario_responsable=usuario.id_usuario if usuario else None,
                ))
                self.db.commit()
            except Exception:
                pass

        return activo
