from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoAuditoria, EventoBaja, HistoricoEstado
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_baja_dto import RegistrarEventoBajaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError


class RegistrarEventoBajaUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
        infra_port: InfraestructuraConsultaPort,
        historico_repo: HistoricoEstadoRepository,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo
        self.infra_port = infra_port
        self.historico_repo = historico_repo
        self.bitacora_repo = bitacora_repo

    def execute(self, id_activo: int, dto: RegistrarEventoBajaDTO, usuario: UsuarioActual) -> EventoActivo:
        # E-01: activo debe existir
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no existe.',
            )

        # E-02: no se permite baja sobre activo ya en estado BAJA
        if activo.id_estado == EstadoActivo.BAJA:
            raise ConflictError(
                code='ACTIVO_YA_EN_BAJA',
                message=(
                    f'El activo {id_activo} ya ha sido dado de baja previamente. '
                    'No se pueden registrar múltiples salidas definitivas para el mismo individuo o lote.'
                ),
            )

        # E-03: fecha_baja no futura ni anterior al último evento
        ahora = datetime.now(timezone.utc)
        fecha_dt = datetime(
            dto.fecha_baja.year, dto.fecha_baja.month, dto.fecha_baja.day,
            tzinfo=timezone.utc,
        )
        if fecha_dt > ahora:
            raise ValidationError(
                code='FECHA_BAJA_FUTURA',
                message='La fecha de baja no puede ser posterior a la fecha actual del sistema.',
                field='fecha_baja',
            )

        ultima_fecha = self.evento_repo.obtener_ultima_fecha(id_activo)
        if ultima_fecha is not None:
            ultima_utc = ultima_fecha.astimezone(timezone.utc)
            ultimo_dia = ultima_utc.date()
            if dto.fecha_baja < ultimo_dia:
                raise ValidationError(
                    code='FECHA_BAJA_CRONOLOGICAMENTE_INVALIDA',
                    message=(
                        f'La fecha de baja no puede ser anterior al último registro de actividad '
                        f'registrado el {ultimo_dia.isoformat()}.'
                    ),
                    field='fecha_baja',
                )

        id_estado_anterior = activo.id_estado
        cantidad_evento: int

        if activo.tipo == 'INDIVIDUAL':
            # Baja total: el activo individual sale definitivamente
            cantidad_evento = 1
            self._procesar_baja_con_cierre(activo, id_activo, fecha_dt, dto.motivo_baja, usuario)

        else:
            # LOTE (POBLACIONAL)
            dp = activo.detalle_poblacional
            if dp is None:
                raise BusinessRuleError(
                    code='DETALLE_POBLACIONAL_AUSENTE',
                    message='El activo no tiene detalle poblacional registrado.',
                )

            cantidad_actual = dp.cantidad_actual or 0

            # Determinar cantidad a dar de baja
            if dto.cantidad_afectada is None:
                # Baja total del lote
                cantidad_baja = cantidad_actual
            else:
                cantidad_baja = dto.cantidad_afectada

            # E-04: cantidad no puede superar la existencia
            if cantidad_baja > cantidad_actual:
                raise BusinessRuleError(
                    code='CANTIDAD_BAJA_SUPERIOR_EXISTENCIA',
                    message=(
                        f'La cantidad a dar de baja ({cantidad_baja}) es superior a la existencia '
                        f'actual del lote ({cantidad_actual}).'
                    ),
                    field='cantidad_afectada',
                )

            cantidad_evento = cantidad_baja
            activo.aplicar_evento_baja(cantidad_baja)

            # Recalcular densidad
            infra = self.infra_port.obtener_activa(activo.id_infraestructura)
            if infra and infra.superficie and infra.superficie > 0:
                dp.densidad = Decimal(str(dp.cantidad_actual or 0)) / infra.superficie

            if dp.cantidad_actual == 0:
                # Baja total: cierre automático del lote
                self._procesar_baja_con_cierre(activo, id_activo, fecha_dt, dto.motivo_baja, usuario)

        evento = EventoActivo(
            id_activo_biologico=id_activo,
            fecha=fecha_dt,
            id_usuario=usuario.id_usuario,
            descripcion=None,
            baja=EventoBaja(
                cantidad_afectada=cantidad_evento,
                tipo=dto.tipo_baja,
                detalles=dto.motivo_baja,
            ),
        )

        try:
            resultado = self.evento_repo.guardar(evento)

            if activo.tipo == 'POBLACIONAL' and activo.detalle_poblacional is not None:
                self.activo_repo.actualizar_detalle_poblacional(activo)

            # Si hay cierre, la gestión y el histórico ya fueron encolados (flush pendiente)
            # El trigger sincroniza id_estado en activos_biologicos al commit
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF45', tipo_evento='BAJA_REGISTRO_FALLIDO',
                        clasificacion_biologica='CONTROL_ESTADO', resultado='FALLIDO',
                        severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                        id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                        detalle_tecnico={'error': str(exc), 'tipo_baja': dto.tipo_baja},
                        id_usuario_responsable=usuario.id_usuario,
                    ))
                    self.db.commit()
                except Exception:
                    pass
            raise

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF45', tipo_evento='BAJA_REGISTRADA',
                    clasificacion_biologica='CONTROL_ESTADO', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    descripcion=f'Baja registrada: {dto.tipo_baja} — {dto.motivo_baja}',
                    detalle_tecnico={'tipo_baja': dto.tipo_baja, 'motivo': dto.motivo_baja},
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return resultado

    def _procesar_baja_con_cierre(
        self,
        activo,
        id_activo: int,
        fecha_dt: datetime,
        motivo: str,
        usuario: UsuarioActual,
    ) -> None:
        id_estado_anterior = activo.id_estado

        # Cerrar gestión de fase activa si existe (igual que cerrar_ciclo_use_case)
        fase_activa = self.activo_repo.obtener_fase_activa(id_activo)
        if fase_activa is not None:
            self.activo_repo.cerrar_gestion_activa(
                id_activo, fecha_dt, f'Baja del activo: {motivo}', usuario.id_usuario
            )

        # Registrar histórico de estado → trigger actualiza activos_biologicos.id_estado a BAJA
        self.historico_repo.registrar(
            id_activo=id_activo,
            id_estado_anterior=id_estado_anterior,
            id_estado_nuevo=EstadoActivo.BAJA,
            fecha=fecha_dt,
            motivo=motivo,
            usuario_id=usuario.id_usuario,
            modulo_origen='modulo2',
        )
