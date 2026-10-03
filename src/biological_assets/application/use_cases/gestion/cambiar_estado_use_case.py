from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.application.use_cases.gestion._auditoria_rechazos import (
    ejecutar_con_auditoria_de_rechazo,
)
from src.biological_assets.application.use_cases.gestion._cambio_estado import aplicar_cambio_estado
from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, HistoricoEstado, registros_rf46
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.cambiar_estado_dto import CambiarEstadoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, NotFoundError


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
        return ejecutar_con_auditoria_de_rechazo(
            lambda: self._execute(id_activo, dto, usuario),
            db=self.db,
            bitacora_repo=self.bitacora_repo,
            obtener_activo=self.repo.obtener_por_id,
            id_activo=id_activo,
            id_usuario=usuario.id_usuario,
            rf_origen='RF44',
            tipo_evento_rechazado='ESTADO_CAMBIO_RECHAZADO',
            clasificacion_biologica='CONTROL_ESTADO',
            tipos_por_codigo={
                'ESTADO_REDUNDANTE': 'ESTADO_REDUNDANTE_DETECTADO',
                'TRANSICION_INVALIDA': 'TRANSICION_NO_PERMITIDA',
                'VALIDACIONES_PREVIAS_REQUERIDAS': 'TRANSICION_NO_PERMITIDA',
            },
        )

    def _execute(self, id_activo: int, dto: CambiarEstadoDTO, usuario: UsuarioActual) -> HistoricoEstado:
        activo = self.repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )

        # E-05/E-06/E-07 son "HTTP 422" en RF-44; por eso viven aquí y no en el DTO,
        # donde un validador de Pydantic sale siempre como 400.
        if dto.id_estado_nuevo in (EstadoActivo.CERRADO, EstadoActivo.BAJA):
            modulo = 'RF-38 (cierre de ciclo)' if dto.id_estado_nuevo == EstadoActivo.CERRADO else 'RF-45 (registro de baja)'
            raise BusinessRuleError(
                code='VALIDACIONES_PREVIAS_REQUERIDAS',
                message=(
                    f'El proceso {modulo} no completó las validaciones previas requeridas antes de '
                    f'invocar el cambio de estado. Operación rechazada. El estado {dto.estado_nuevo} '
                    'solo se establece desde ese proceso, no con el cambio manual.'
                ),
                field='estado_nuevo',
            )

        # INC-M02-29-g36 / #411: la referencia es la fecha UTC, no la local del servidor.
        if dto.fecha_cambio_estado > datetime.now(timezone.utc).date():
            raise BusinessRuleError(
                code='FECHA_FUTURA',
                message=(
                    f'La fecha del cambio de estado {dto.fecha_cambio_estado.isoformat()} es posterior a la '
                    'fecha actual del sistema. No se permiten registros con fecha futura.'
                ),
                field='fecha_cambio_estado',
            )

        motivo = dto.motivo_cambio.strip()
        if not motivo:
            raise BusinessRuleError(
                code='MOTIVO_REQUERIDO',
                message=(
                    'El campo motivo del cambio de estado es obligatorio. '
                    'Ingrese una justificación para continuar.'
                ),
                field='motivo_cambio',
            )

        id_estado_anterior = activo.id_estado
        fecha = datetime.combine(dto.fecha_cambio_estado, datetime.min.time()).replace(tzinfo=timezone.utc)

        try:
            # aplicar_cambio_estado valida BAJA irreversible, estado redundante y matriz de
            # transiciones, y registra el histórico (el INSERT dispara trg_sincronizar_estado_activo
            # que actualiza activos_biologicos.id_estado). CERRADO/BAJA ya se rechazaron arriba:
            # esos estados solo se alcanzan vía CerrarCicloUseCase (RF-38) o RegistrarEventoBajaUseCase
            # (RF-45), que aplican sus propias validaciones y efectos secundarios.
            historico = aplicar_cambio_estado(
                activo=activo,
                id_estado_nuevo=dto.id_estado_nuevo,
                fecha=fecha,
                motivo=motivo,
                usuario_id=usuario.id_usuario,
                historico_repo=self.historico_repo,
                modulo_origen='MANUAL',
            )
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
                rf_origen='RF44', tipo_evento='ESTADO_CAMBIO_FALLIDO',
                clasificacion_biologica='CONTROL_ESTADO', resultado='FALLIDO',
                severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                id_activo_biologico=id_activo,
                detalle_tecnico={'error': str(exc), 'id_estado_nuevo': dto.id_estado_nuevo},
                id_usuario_responsable=usuario.id_usuario,
            ))
            raise

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF44', tipo_evento='ESTADO_CAMBIADO',
            clasificacion_biologica='CONTROL_ESTADO', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo,
            descripcion=f'Estado cambiado: {id_estado_anterior} → {dto.id_estado_nuevo}',
            detalle_tecnico={
                'estado_anterior': id_estado_anterior,
                'estado_nuevo': dto.id_estado_nuevo,
                'motivo': motivo,
                'registros_rf46': registros_rf46(historicos_estados_activos=historico.id_historico),
            },
            id_usuario_responsable=usuario.id_usuario,
        ))

        return historico
