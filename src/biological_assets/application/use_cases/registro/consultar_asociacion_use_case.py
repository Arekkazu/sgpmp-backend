from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, HistorialInfraestructura
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError, ValidationError


class ConsultarAsociacionUseCase:

    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        id_activo: int,
        tipo_consulta: str,
        usuario: Optional[UsuarioActual] = None,
    ) -> Union[Optional[HistorialInfraestructura], list[HistorialInfraestructura]]:
        if tipo_consulta not in ('ACTIVA', 'HISTORIAL'):
            raise ValidationError(
                code='TIPO_CONSULTA_INVALIDO',
                message="tipo_consulta debe ser 'ACTIVA' o 'HISTORIAL'.",
                field='tipo_consulta',
            )

        activo = self.repo.obtener_por_id(id_activo)
        if not activo:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f"No existe un activo biológico con id {id_activo}.",
            )

        if tipo_consulta == 'ACTIVA':
            resultado = self.repo.obtener_asociacion_activa(id_activo)
        else:
            resultado = self.repo.obtener_historial_infraestructura(id_activo)

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF34', tipo_evento='INFRAESTRUCTURA_CONSULTADA',
                    clasificacion_biologica='ACCESO_DATOS', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo,
                    detalle_tecnico={'tipo_consulta': tipo_consulta},
                    id_usuario_responsable=usuario.id_usuario if usuario else None,
                ))
                self.db.commit()
            except Exception:
                pass

        return resultado
