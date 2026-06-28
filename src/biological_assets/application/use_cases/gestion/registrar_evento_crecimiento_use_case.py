from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion._event_validations import validar_fecha_evento
from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoCrecimiento
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
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
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo
        self.infra_port = infra_port

    def execute(self, id_activo: int, dto: RegistrarEventoCrecimientoDTO, usuario: UsuarioActual) -> EventoActivo:
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
        except Exception:
            self.db.rollback()
            raise

        return resultado
