from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion._cambio_estado import aplicar_cambio_estado
from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, HistoricoEstado
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.cerrar_ciclo_dto import CerrarCicloDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError


class CerrarCicloUseCase:
    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
        historico_repo: HistoricoEstadoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.evento_repo = evento_repo
        self.historico_repo = historico_repo
        self.bitacora_repo = bitacora_repo

    def execute(self, id_activo: int, dto: CerrarCicloDTO, usuario: UsuarioActual) -> HistoricoEstado:
        # FA-01: activo debe existir
        activo = self.repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )

        # FA-02: estado debe permitir transición a CERRADO
        if activo.id_estado in (EstadoActivo.CERRADO, EstadoActivo.BAJA):
            nombre = 'CERRADO' if activo.id_estado == EstadoActivo.CERRADO else 'BAJA'
            raise ConflictError(
                code='ESTADO_INVALIDO_PARA_CIERRE',
                message=(
                    f'El activo biológico ya se encuentra en estado {nombre}. '
                    'No es posible realizar un nuevo cierre de ciclo.'
                ),
            )

        # FA-06: no debe tener sensores IoT activos
        if self.repo.tiene_sensores_activos(id_activo):
            raise BusinessRuleError(
                code='SENSORES_ACTIVOS',
                message=(
                    'El activo tiene sensores IoT vinculados activos. '
                    'Desvincule los sensores antes de cerrar el ciclo productivo.'
                ),
            )

        # FA-05: debe tener al menos una fase productiva activa
        fase_activa = self.repo.obtener_fase_activa(id_activo)
        if fase_activa is None:
            raise BusinessRuleError(
                code='SIN_FASE_ACTIVA',
                message=(
                    'El activo no presenta una fase productiva activa. '
                    'Verifique la integridad del ciclo de vida antes de cerrar.'
                ),
            )

        # FA-04: validar fecha contra último evento registrado
        ultima_fecha_evento = self.evento_repo.obtener_ultima_fecha(id_activo)
        if ultima_fecha_evento is not None:
            ultimo_dia_evento = ultima_fecha_evento.date() if isinstance(ultima_fecha_evento, datetime) else ultima_fecha_evento
            if dto.fecha_cierre < ultimo_dia_evento:
                raise ValidationError(
                    code='FECHA_CIERRE_ANTERIOR_ULTIMO_EVENTO',
                    message=(
                        f'La fecha de cierre no puede ser anterior al último registro de actividad '
                        f'del activo ({ultimo_dia_evento.isoformat()}).'
                    ),
                    field='fecha_cierre',
                )

        motivo_completo = dto.motivo_cierre
        if dto.descripcion_cierre:
            motivo_completo = f'{dto.motivo_cierre} — {dto.descripcion_cierre}'

        fecha_cierre_dt = datetime.combine(dto.fecha_cierre, datetime.min.time()).replace(tzinfo=timezone.utc)

        try:
            # Cerrar fase primero: el trigger trg_fn_fase_activo_estado_valido bloquea
            # cambios en gestiones_fases si el activo ya está en CERRADO.
            self.repo.cerrar_gestion_activa(id_activo, fecha_cierre_dt, motivo_completo, usuario.id_usuario)
            # aplicar_cambio_estado registra el histórico (el INSERT dispara
            # trg_sincronizar_estado_activo que actualiza activos_biologicos.id_estado)
            historico = aplicar_cambio_estado(
                activo=activo,
                id_estado_nuevo=EstadoActivo.CERRADO,
                fecha=fecha_cierre_dt,
                motivo=motivo_completo,
                usuario_id=usuario.id_usuario,
                historico_repo=self.historico_repo,
                modulo_origen='RF-38',
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF38', tipo_evento='CICLO_CIERRE_FALLIDO',
                        clasificacion_biologica='CONTROL_ESTADO', resultado='FALLIDO',
                        severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                        id_activo_biologico=id_activo, tipo_activo=activo.tipo,
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
                    rf_origen='RF38', tipo_evento='CICLO_CERRADO',
                    clasificacion_biologica='CONTROL_ESTADO', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    descripcion=f'Ciclo productivo cerrado: {dto.motivo_cierre}',
                    detalle_tecnico={'motivo': motivo_completo, 'fecha_cierre': dto.fecha_cierre.isoformat()},
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return historico
