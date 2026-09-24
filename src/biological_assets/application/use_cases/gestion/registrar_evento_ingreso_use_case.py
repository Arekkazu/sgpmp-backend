from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.application.use_cases.gestion._auditoria_rechazos import (
    ejecutar_con_auditoria_de_rechazo,
)
from src.biological_assets.application.use_cases.gestion._event_validations import validar_estado_permite_eventos
from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoAuditoria, EventoIngreso
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.infrastructure.dto.registrar_evento_ingreso_dto import RegistrarEventoIngresoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, ConflictError, NotFoundError, ValidationError


class RegistrarEventoIngresoUseCase:
    """RF-36 (tarea Taiga "Ficha de gestión de lote, densidad máxima, ingreso
    de individuos"): alta de individuos a un lote POBLACIONAL -- contraparte
    de RegistrarEventoBajaUseCase (RF-45), mismo patrón estructural."""

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
        infra_port: InfraestructuraConsultaPort,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo
        self.infra_port = infra_port
        self.bitacora_repo = bitacora_repo

    def execute(self, id_activo: int, dto: RegistrarEventoIngresoDTO, usuario: UsuarioActual) -> EventoActivo:
        return ejecutar_con_auditoria_de_rechazo(
            lambda: self._execute(id_activo, dto, usuario),
            db=self.db,
            bitacora_repo=self.bitacora_repo,
            obtener_activo=self.activo_repo.obtener_por_id,
            id_activo=id_activo,
            id_usuario=usuario.id_usuario,
            rf_origen='RF36',
            tipo_evento_rechazado='INGRESO_RECHAZADO',
            clasificacion_biologica='CONTROL_ESTADO',
        )

    def _execute(self, id_activo: int, dto: RegistrarEventoIngresoDTO, usuario: UsuarioActual) -> EventoActivo:
        # E-01: activo debe existir
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no existe.',
            )

        # E-02: el ingreso solo aplica a lotes POBLACIONALES -- un INDIVIDUAL
        # no puede "recibir" más individuos.
        if activo.tipo != 'POBLACIONAL':
            raise ValidationError(
                code='TIPO_INVALIDO',
                message='El ingreso de individuos solo aplica a activos de tipo POBLACIONAL (lotes).',
                field='id_activo',
            )

        dp = activo.detalle_poblacional
        if dp is None:
            raise BusinessRuleError(
                code='DETALLE_POBLACIONAL_AUSENTE',
                message='El activo no tiene detalle poblacional registrado.',
            )

        # E-03: mismo gate de estado operativo que crecimiento/sanitario/productivo
        validar_estado_permite_eventos(activo)

        # E-04: fecha_ingreso no futura ni anterior al último evento (mismo
        # patrón que RegistrarEventoBajaUseCase E-03)
        ahora = datetime.now(timezone.utc)
        fecha_dt = datetime(
            dto.fecha_ingreso.year, dto.fecha_ingreso.month, dto.fecha_ingreso.day,
            tzinfo=timezone.utc,
        )
        if fecha_dt > ahora:
            raise ValidationError(
                code='FECHA_INGRESO_FUTURA',
                message='La fecha de ingreso no puede ser posterior a la fecha actual del sistema.',
                field='fecha_ingreso',
            )

        ultima_fecha = self.evento_repo.obtener_ultima_fecha(id_activo)
        if ultima_fecha is not None:
            ultimo_dia = ultima_fecha.astimezone(timezone.utc).date()
            if dto.fecha_ingreso < ultimo_dia:
                raise ValidationError(
                    code='FECHA_INGRESO_CRONOLOGICAMENTE_INVALIDA',
                    message=(
                        f'La fecha de ingreso no puede ser anterior al último registro de actividad '
                        f'registrado el {ultimo_dia.isoformat()}.'
                    ),
                    field='fecha_ingreso',
                )

        # E-05: densidad máxima por especie (RF-36) -- mismo cálculo que
        # INC-M02-38-G25 usa para eventos de crecimiento
        # (capacidad_maxima / superficie de la infraestructura), pero
        # evaluado ANTES de aplicar el ingreso: este es el flujo que
        # realmente cambia cantidad_actual, así que es donde el límite
        # importa de verdad -- crecimiento solo lo valida contra la
        # cantidad ya existente, nunca la incrementa.
        infra = self.infra_port.obtener_activa(activo.id_infraestructura)
        cantidad_actual = dp.cantidad_actual or 0
        cantidad_resultante = cantidad_actual + dto.cantidad_ingresada
        if infra and infra.capacidad_maxima and infra.superficie and infra.superficie > 0:
            densidad_resultante = Decimal(cantidad_resultante) / infra.superficie
            densidad_maxima = Decimal(infra.capacidad_maxima) / infra.superficie
            if densidad_resultante > densidad_maxima:
                raise ConflictError(
                    code='DENSIDAD_MAXIMA_SUPERADA',
                    message=(
                        f'Ingresar {dto.cantidad_ingresada} individuos dejaría la densidad del lote '
                        f'en {densidad_resultante.quantize(Decimal("0.0001"))} ind/m², por encima del '
                        f'máximo permitido ({densidad_maxima.quantize(Decimal("0.0001"))} ind/m²) para '
                        f'la infraestructura donde reside.'
                    ),
                )

        activo.aplicar_evento_ingreso(dto.cantidad_ingresada)
        if infra and infra.superficie and infra.superficie > 0:
            activo.recalcular_densidad(infra.superficie)

        evento = EventoActivo(
            id_activo_biologico=id_activo,
            fecha=fecha_dt,
            id_usuario=usuario.id_usuario,
            descripcion=None,
            ingreso=EventoIngreso(
                cantidad_ingresada=dto.cantidad_ingresada,
                tipo=dto.tipo_ingreso,
                detalles=dto.motivo_ingreso,
            ),
        )

        try:
            resultado = self.evento_repo.guardar(evento)
            self.activo_repo.actualizar_detalle_poblacional(activo)
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
                rf_origen='RF36', tipo_evento='INGRESO_REGISTRO_FALLIDO',
                clasificacion_biologica='CONTROL_ESTADO', resultado='FALLIDO',
                severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                detalle_tecnico={'error': str(exc), 'tipo_ingreso': dto.tipo_ingreso},
                id_usuario_responsable=usuario.id_usuario,
            ))
            raise

        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF36', tipo_evento='INGRESO_REGISTRADO',
            clasificacion_biologica='CONTROL_ESTADO', resultado='EXITOSO',
            severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo, tipo_activo=activo.tipo,
            descripcion=f'Ingreso registrado: {dto.tipo_ingreso} — {dto.motivo_ingreso}',
            detalle_tecnico={'tipo_ingreso': dto.tipo_ingreso, 'cantidad_ingresada': dto.cantidad_ingresada},
            id_usuario_responsable=usuario.id_usuario,
        ))

        return resultado
