from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, EventoAuditoria
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.infrastructure.dto.actualizar_activo_individual_dto import ActualizarActivoIndividualDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ActualizarActivoIndividualUseCase:
    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.bitacora_repo = bitacora_repo

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
        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF35', tipo_evento='ACTIVO_ACTUALIZACION_FALLIDA',
                        clasificacion_biologica='GESTION_OPERATIVA', resultado='FALLIDO',
                        severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                        id_activo_biologico=id_activo,
                        detalle_tecnico={'error': str(exc)},
                        id_usuario_responsable=usuario.id_usuario,
                    ))
                    self.db.commit()
                except Exception:
                    pass
            raise

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF35', tipo_evento='ACTIVO_INDIVIDUAL_ACTUALIZADO',
                    clasificacion_biologica='GESTION_OPERATIVA', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    descripcion=f'Detalle individual actualizado para activo {id_activo}',
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return activo
