from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion._event_validations import validar_fecha_evento
from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoAuditoria, EventoCrecimiento, GestionFase
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.ciclo_consulta_port import CicloConsultaPort
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.domain.repositories.parametros_especie_port import ParametrosEspeciePort
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import RegistrarEventoCrecimientoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError


class RegistrarEventoCrecimientoUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
        infra_port: InfraestructuraConsultaPort,
        parametros_port: ParametrosEspeciePort,
        ciclo_port: CicloConsultaPort,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo
        self.infra_port = infra_port
        self.parametros_port = parametros_port
        self.ciclo_port = ciclo_port
        self.bitacora_repo = bitacora_repo

    def execute(
        self, id_activo: int, dto: RegistrarEventoCrecimientoDTO, usuario: UsuarioActual
    ) -> tuple[EventoActivo, bool]:
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(code='ACTIVO_NO_ENCONTRADO', message=f'El activo biológico con id {id_activo} no existe.')

        # RF-40: solo ACTIVO permite eventos de crecimiento
        if activo.id_estado != EstadoActivo.ACTIVO:
            from src.biological_assets.application.use_cases.gestion._event_validations import _NOMBRES_ESTADO
            estado_actual = _NOMBRES_ESTADO.get(activo.id_estado, str(activo.id_estado))
            raise ConflictError(
                code='ESTADO_NO_PERMITE_EVENTOS',
                message=(
                    f'El activo no se encuentra en estado ACTIVO. '
                    f'Estado actual: {estado_actual}. '
                    f'Los eventos de crecimiento solo se pueden registrar sobre activos en estado ACTIVO.'
                ),
            )

        # RF-40: debe tener fase productiva activa
        fase = self.activo_repo.obtener_fase_activa(id_activo)
        if fase is None:
            raise BusinessRuleError(
                code='SIN_FASE_ACTIVA',
                message='El activo no tiene una fase productiva activa. Asocie el activo a un ciclo productivo antes de registrar eventos de crecimiento.',
            )

        fecha = dto.fecha or datetime.now(timezone.utc)
        validar_fecha_evento(fecha, activo, self.evento_repo)

        # FA-07 (CU06): tipo_agregacion prohibido para activos INDIVIDUAL
        if activo.tipo == 'INDIVIDUAL' and dto.tipo_agregacion is not None:
            raise ValidationError(
                code='AGREGACION_NO_PERMITIDA',
                message='El campo tipo_agregacion no aplica a activos de tipo INDIVIDUAL.',
                field='tipo_agregacion',
            )

        # FA-05 (CU06): tipo_medicion debe estar configurado para la especie
        parametro = self.parametros_port.obtener_por_tipo_medicion(
            activo.id_especie, dto.tipo_medicion, activo.tipo
        )
        if parametro is None:
            raise BusinessRuleError(
                code='TIPO_MEDICION_NO_CONFIGURADO',
                message=f"El tipo de medición '{dto.tipo_medicion}' no está configurado para esta especie.",
            )

        # FA-04 (CU06): valor dentro del rango permitido por especie (si hay rango configurado)
        if parametro.valor_min is not None and dto.valor_medicion < parametro.valor_min:
            raise BusinessRuleError(
                code='VALOR_FUERA_DE_RANGO',
                message=(
                    f'El valor {dto.valor_medicion} es menor al mínimo permitido '
                    f'({parametro.valor_min}) para esta especie.'
                ),
                field='valor_medicion',
            )
        if parametro.valor_max is not None and dto.valor_medicion > parametro.valor_max:
            raise BusinessRuleError(
                code='VALOR_FUERA_DE_RANGO',
                message=(
                    f'El valor {dto.valor_medicion} supera el máximo permitido '
                    f'({parametro.valor_max}) para esta especie.'
                ),
                field='valor_medicion',
            )

        # RF-40: validaciones específicas por tipo de activo
        if activo.tipo == 'POBLACIONAL':
            if dto.nuevo_peso_promedio is None:
                raise ValidationError(
                    code='NUEVO_PESO_REQUERIDO',
                    message='El campo nuevo_peso_promedio es obligatorio para activos de tipo POBLACIONAL.',
                    field='nuevo_peso_promedio',
                )
            if dto.cantidad_medida is None:
                raise ValidationError(
                    code='CANTIDAD_MEDIDA_REQUERIDA',
                    message='El campo cantidad_medida es obligatorio para activos de tipo POBLACIONAL.',
                    field='cantidad_medida',
                )
            if dto.tipo_agregacion is None:
                raise ValidationError(
                    code='TIPO_AGREGACION_REQUERIDO',
                    message='El campo tipo_agregacion es obligatorio para activos de tipo POBLACIONAL.',
                    field='tipo_agregacion',
                )

            infra = self.infra_port.obtener_activa(activo.id_infraestructura)
            superficie = infra.superficie if infra and infra.superficie else None
            activo.aplicar_evento_crecimiento(
                nuevo_peso_promedio=dto.nuevo_peso_promedio,
                superficie=superficie,
            )

        evento = EventoActivo(
            id_activo_biologico=id_activo,
            fecha=fecha,
            id_usuario=usuario.id_usuario,
            descripcion=dto.descripcion,
            crecimiento=EventoCrecimiento(
                tipo_medicion=dto.tipo_medicion,
                valor_medicion=dto.valor_medicion,
                unidad_medida=dto.unidad_medida,
                tipo_agregacion=dto.tipo_agregacion,
                frecuencia=dto.frecuencia,
                nuevo_peso_promedio=dto.nuevo_peso_promedio,
                cantidad_medida=dto.cantidad_medida,
            ),
        )

        try:
            resultado = self.evento_repo.guardar(evento)
            if activo.tipo == 'POBLACIONAL':
                self.activo_repo.actualizar_detalle_poblacional(activo)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF40', tipo_evento='EVENTO_CRECIMIENTO_FALLIDO',
                        clasificacion_biologica='TRANSFORMACION_BIOLOGICA', resultado='FALLIDO',
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
                    rf_origen='RF40', tipo_evento='EVENTO_CRECIMIENTO_REGISTRADO',
                    clasificacion_biologica='TRANSFORMACION_BIOLOGICA', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=id_activo, tipo_activo=activo.tipo,
                    descripcion=f'Evento de crecimiento: {dto.tipo_medicion} = {dto.valor_medicion} {dto.unidad_medida}',
                    detalle_tecnico={'tipo_medicion': dto.tipo_medicion, 'valor': str(dto.valor_medicion)},
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        # <<extend>> RF-37 (CU06): avance automático de fase cuando la duración configurada se cumple
        fase_avanzada = self._evaluar_avance_fase(id_activo, fase, fecha, usuario)

        return resultado, fase_avanzada

    def _evaluar_avance_fase(
        self,
        id_activo: int,
        fase: GestionFase,
        fecha: datetime,
        usuario: UsuarioActual,
    ) -> bool:
        if fase.id_ciclo_productiva is None:
            return False

        ciclo = self.ciclo_port.obtener_ciclo_con_fases(fase.id_ciclo_productiva)
        if ciclo is None or not ciclo.fases:
            return False

        # Calcular paso_actual contando gestiones previas en este ciclo
        todas = self.activo_repo.obtener_gestiones_fases(id_activo)
        gestiones_en_ciclo = [g for g in todas if g.id_ciclo_productiva == fase.id_ciclo_productiva]
        paso_actual = len(gestiones_en_ciclo)  # 1-based (ya incluye la activa)

        if paso_actual > len(ciclo.fases) or paso_actual < 1:
            return False

        if paso_actual >= len(ciclo.fases):
            return False  # no hay fase siguiente

        fase_config = ciclo.fases[paso_actual - 1]
        fecha_utc = fecha.astimezone(timezone.utc)
        inicio_utc = fase.fecha_inicio.astimezone(timezone.utc)
        elapsed_days = (fecha_utc - inicio_utc).days

        if elapsed_days < fase_config.duracion_dias:
            return False

        try:
            self.activo_repo.cerrar_gestion_activa(id_activo, fecha, 'Avance automático por duración de fase', usuario.id_usuario)
            siguiente = ciclo.fases[paso_actual]
            nueva_gestion = GestionFase(
                id_gestion_fases=None,
                id_activo_biologico=id_activo,
                id_ciclo_productiva=fase.id_ciclo_productiva,
                nombre_ciclo=ciclo.nombre,
                nombre_fase_actual=siguiente.nombre_fase,
                paso_actual=paso_actual + 1,
                total_pasos=len(ciclo.fases),
                fecha_inicio=fecha,
                fecha_finalizacion=None,
                es_activa=True,
                id_usuario=usuario.id_usuario,
                motivo_cambio='Avance automático por duración de fase',
            )
            self.activo_repo.crear_gestion_fase(nueva_gestion)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False
