from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoActivo, EventoProductivo
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.ciclo_consulta_port import CicloConsultaPort
from src.biological_assets.domain.repositories.evento_activo_repository import EventoActivoRepository
from src.biological_assets.domain.repositories.parametros_especie_port import ParametrosEspeciePort
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_productivo_dto import RegistrarEventoProductivoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError

_NOMBRES_ESTADO = {1: 'ACTIVO', 2: 'INACTIVO', 3: 'EN_TRATAMIENTO', 4: 'AISLADO', 5: 'CERRADO', 6: 'BAJA'}


class RegistrarEventoProductivoUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
        evento_repo: EventoActivoRepository,
        parametros_port: ParametrosEspeciePort,
        ciclo_port: CicloConsultaPort,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo
        self.evento_repo = evento_repo
        self.parametros_port = parametros_port
        self.ciclo_port = ciclo_port

    def execute(self, id_activo: int, dto: RegistrarEventoProductivoDTO, usuario: UsuarioActual) -> EventoActivo:
        # FA-01: activo debe existir
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no existe.',
            )

        # E-01: RF-43 exige estado ACTIVO (no EN_TRATAMIENTO ni AISLADO)
        if activo.id_estado != EstadoActivo.ACTIVO:
            estado_actual = _NOMBRES_ESTADO.get(activo.id_estado, str(activo.id_estado))
            raise ConflictError(
                code='ESTADO_NO_ACTIVO',
                message=(
                    f'El activo {id_activo} se encuentra en estado {estado_actual}. '
                    'Solo se pueden registrar eventos productivos en activos con estado ACTIVO.'
                ),
            )

        # E-03: tipo_producto debe estar en el catálogo RF-16 para la especie
        metrica = self.parametros_port.obtener_metrica_productiva(
            activo.id_especie, dto.tipo_producto, activo.tipo
        )
        if metrica is None:
            raise BusinessRuleError(
                code='TIPO_PRODUCTO_NO_CATALOGADO',
                message=(
                    f'El tipo de producto "{dto.tipo_producto}" no está definido en el catálogo '
                    'para la especie del activo. Seleccione un tipo de producto válido.'
                ),
                field='tipo_producto',
            )

        # E-07: unidad_medida debe coincidir con la definida en RF-16 para el tipo_producto
        if dto.unidad_medida.strip().lower() != metrica.unidad_medida.strip().lower():
            raise ValidationError(
                code='UNIDAD_MEDIDA_INCOMPATIBLE',
                message=(
                    f'La unidad de medida "{dto.unidad_medida}" no es válida para el tipo de producto '
                    f'"{dto.tipo_producto}". La unidad válida es: {metrica.unidad_medida}.'
                ),
                field='unidad_medida',
            )

        # E-02: debe existir una fase productiva activa
        fase_activa = self.activo_repo.obtener_fase_activa(id_activo)
        if fase_activa is None:
            raise BusinessRuleError(
                code='SIN_FASE_PRODUCTIVA_ACTIVA',
                message=(
                    'El activo no tiene una fase productiva activa que permita el registro de eventos '
                    'productivos. Verifique el ciclo productivo del activo.'
                ),
            )

        # E-04: tipo_producto debe estar habilitado para el ciclo productivo activo
        if not self.ciclo_port.metrica_habilitada_en_ciclo(
            fase_activa.id_ciclo_productiva, metrica.id_metrica_produccion
        ):
            raise BusinessRuleError(
                code='TIPO_PRODUCTO_NO_HABILITADO_FASE',
                message=(
                    f'El tipo de producto "{dto.tipo_producto}" no está habilitado para el ciclo '
                    f'productivo activo "{fase_activa.nombre_ciclo}". Verifique la configuración de fases.'
                ),
                field='tipo_producto',
            )

        # E-05: validaciones de fecha
        ahora = datetime.now(timezone.utc)
        fecha_dt = datetime(
            dto.fecha_evento.year, dto.fecha_evento.month, dto.fecha_evento.day,
            tzinfo=timezone.utc,
        )

        if fecha_dt > ahora:
            raise ValidationError(
                code='FECHA_FUTURA',
                message=(
                    f'La fecha del evento {dto.fecha_evento.isoformat()} es posterior a la fecha '
                    'actual del sistema. No se permiten registros con fecha futura.'
                ),
                field='fecha_evento',
            )

        if activo.fecha_inicio_ciclo and dto.fecha_evento < activo.fecha_inicio_ciclo:
            raise ValidationError(
                code='FECHA_ANTERIOR_INICIO_ACTIVO',
                message=(
                    'La fecha del evento es anterior a la fecha de inicio del activo en el sistema. '
                    'No se permiten registros previos al registro del activo.'
                ),
                field='fecha_evento',
            )

        if fase_activa.fecha_inicio:
            fecha_inicio_fase = (
                fase_activa.fecha_inicio.date()
                if hasattr(fase_activa.fecha_inicio, 'date')
                else fase_activa.fecha_inicio
            )
            if dto.fecha_evento < fecha_inicio_fase:
                raise ValidationError(
                    code='FECHA_FUERA_DE_FASE',
                    message=(
                        f'La fecha del evento está fuera del período de la fase productiva activa '
                        f'"{fase_activa.nombre_ciclo}" (inicio: {fecha_inicio_fase.isoformat()}).'
                    ),
                    field='fecha_evento',
                )

        if fase_activa.fecha_finalizacion:
            fecha_fin_fase = (
                fase_activa.fecha_finalizacion.date()
                if hasattr(fase_activa.fecha_finalizacion, 'date')
                else fase_activa.fecha_finalizacion
            )
            if dto.fecha_evento > fecha_fin_fase:
                fecha_inicio_str = (
                    fecha_inicio_fase.isoformat()
                    if fase_activa.fecha_inicio
                    else '?'
                )
                raise ValidationError(
                    code='FECHA_FUERA_DE_FASE',
                    message=(
                        f'La fecha del evento está fuera del período de la fase productiva activa '
                        f'"{fase_activa.nombre_ciclo}" ({fecha_inicio_str} – {fecha_fin_fase.isoformat()}).'
                    ),
                    field='fecha_evento',
                )

        # E-08: verificar duplicidad (mismo tipo_producto + activo + fecha)
        if self.evento_repo.existe_productivo_duplicado(id_activo, metrica.id_metrica_produccion, dto.fecha_evento):
            raise ConflictError(
                code='EVENTO_PRODUCTIVO_DUPLICADO',
                message=(
                    f'Ya existe un evento productivo de tipo "{dto.tipo_producto}" registrado para el '
                    f'activo {id_activo} en la fecha {dto.fecha_evento.isoformat()}. '
                    'No se permiten registros duplicados.'
                ),
            )

        evento = EventoActivo(
            id_activo_biologico=id_activo,
            fecha=fecha_dt,
            id_usuario=usuario.id_usuario,
            descripcion=dto.observaciones,
            productivo=EventoProductivo(
                cantidad=dto.cantidad_producida,
                id_metrica_produccion=metrica.id_metrica_produccion,
                id_ciclo_productivo=fase_activa.id_ciclo_productiva,
                condiciones=dto.condiciones_produccion,
                tipo_producto=metrica.tipo_producto,
                unidad_medida=metrica.unidad_medida,
            ),
        )

        try:
            resultado = self.evento_repo.guardar(evento)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return resultado
