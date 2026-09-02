from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion._cambio_estado import aplicar_cambio_estado
from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, HistoricoEstado
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository
from src.biological_assets.infrastructure.dto.cambiar_estado_dto import CambiarEstadoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class CambiarEstadoUseCase:
    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        historico_repo: HistoricoEstadoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.historico_repo = historico_repo
        self.bitacora_repo = bitacora_repo

    def execute(self, id_activo: int, dto: CambiarEstadoDTO, usuario: UsuarioActual) -> HistoricoEstado:
        activo = self.repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )

        id_estado_anterior = activo.id_estado
        fecha = datetime.combine(dto.fecha_cambio_estado, datetime.min.time()).replace(tzinfo=timezone.utc)

        try:
            # aplicar_cambio_estado valida BAJA irreversible, estado redundante y matriz de
            # transiciones, y registra el histórico (el INSERT dispara trg_sincronizar_estado_activo
            # que actualiza activos_biologicos.id_estado). CambiarEstadoDTO ya excluye CERRADO/BAJA:
            # esos estados solo se alcanzan vía CerrarCicloUseCase (RF-38) o RegistrarEventoBajaUseCase
            # (RF-45), que aplican sus propias validaciones y efectos secundarios.
            historico = aplicar_cambio_estado(
                activo=activo,
                id_estado_nuevo=dto.id_estado_nuevo,
                fecha=fecha,
                motivo=dto.motivo_cambio,
                usuario_id=usuario.id_usuario,
                historico_repo=self.historico_repo,
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF44', tipo_evento='ESTADO_CAMBIO_FALLIDO',
                        clasificacion_biologica='CONTROL_ESTADO', resultado='FALLIDO',
                        severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                        id_activo_biologico=id_activo,
                        detalle_tecnico={'error': str(exc), 'id_estado_nuevo': dto.id_estado_nuevo},
                        id_usuario_responsable=usuario.id_usuario,
                    ))
                    self.db.commit()
                except Exception:
                    pass
            raise

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF44', tipo_evento='ESTADO_CAMBIADO',
                    clasificacion_biologica='CONTROL_ESTADO', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo,
                    descripcion=f'Estado cambiado: {id_estado_anterior} → {dto.id_estado_nuevo}',
                    detalle_tecnico={'estado_anterior': id_estado_anterior, 'estado_nuevo': dto.id_estado_nuevo, 'motivo': dto.motivo_cambio},
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return historico
