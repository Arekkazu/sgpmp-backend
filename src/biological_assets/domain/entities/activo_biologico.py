from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from src.shared.errors import BusinessRuleError, ConflictError, ValidationError


@dataclass
class DetalleIndividual:
    raza: str
    sexo: str
    fecha_nacimiento: datetime
    peso_inicial: Optional[Decimal] = None
    id_detalle: Optional[int] = None
    fecha_creacion: Optional[datetime] = None


@dataclass
class DetallePoblacional:
    cantidad_inicial: int
    cantidad_actual: int
    peso_promedio_inicial: Optional[Decimal] = None
    peso_promedio: Optional[Decimal] = None
    biomasa_total: Optional[Decimal] = None
    densidad: Optional[Decimal] = None
    id_detalle: Optional[int] = None


@dataclass
class EventoCrecimiento:
    tipo_medicion: str
    valor_medicion: Decimal
    unidad_medida: str
    tipo_agregacion: Optional[str] = None
    frecuencia: Optional[str] = None
    nuevo_peso_promedio: Optional[Decimal] = None
    cantidad_medida: Optional[int] = None


@dataclass
class EventoBaja:
    cantidad_afectada: int
    tipo: str
    detalles: Optional[str] = None


@dataclass
class EventoSanitario:
    tipo: str
    diagnostico: Optional[str] = None
    medicamento: Optional[str] = None
    dosis: Optional[Decimal] = None
    unidad_dosis: Optional[str] = None
    frecuencia: Optional[int] = None
    duracion: Optional[int] = None
    observaciones: Optional[str] = None


@dataclass
class EventoProductivo:
    cantidad: Decimal
    id_metrica_produccion: int
    id_ciclo_productivo: int
    condiciones: Optional[str] = None
    tipo_producto: Optional[str] = None
    unidad_medida: Optional[str] = None


@dataclass
class EventoReproductivo:
    categoria: str
    resultado: str
    numero_cria: int = 0
    id_padre: Optional[int] = None
    id_madre: Optional[int] = None


@dataclass
class EventoActivo:
    id_activo_biologico: int
    fecha: datetime
    id_usuario: int
    descripcion: Optional[str] = None
    id_eventos: Optional[int] = None
    crecimiento: Optional[EventoCrecimiento] = None
    baja: Optional[EventoBaja] = None
    sanitario: Optional[EventoSanitario] = None
    productivo: Optional[EventoProductivo] = None
    reproductivo: Optional[EventoReproductivo] = None


@dataclass
class RegistroHistorial:
    categoria: str
    fecha_evento: datetime
    descripcion: str
    detalle_especifico: dict
    usuario_responsable: str
    modulo_origen: str


@dataclass
class PaginaHistorial:
    registros: list[RegistroHistorial]
    total_registros: int
    pagina_actual: int
    total_paginas: int
    registros_por_pagina: int


@dataclass
class Transferencia:
    id_activo_biologico: int
    id_infraestructura_origen: int
    id_infraestructura_destino: int
    nombre_infra_origen: str
    nombre_infra_destino: str
    fecha_transferencia: datetime
    motivo_transferencia: str
    id_usuario: int
    id_movimiento: Optional[int] = None
    fecha_registro: Optional[datetime] = None


@dataclass
class FichaIntegral:
    id_activo_biologico: int
    identificador: Optional[str]
    tipo: str
    especie: str
    fecha_registro: Optional[date]
    dias_en_sistema: Optional[int]
    estado_actual: str
    infraestructura_asociada: Optional[str]
    fase_productiva_activa: Optional[str]
    raza: Optional[str]
    sexo: Optional[str]
    fecha_nacimiento: Optional[date]
    peso_actual: Optional[Decimal]
    unidad_peso: Optional[str]
    fecha_ultimo_peso: Optional[date]
    cantidad_actual: Optional[int]
    biomasa_total: Optional[Decimal]
    densidad: Optional[Decimal]
    eventos_sanitarios: list[dict]
    eventos_productivos: list[dict]
    eventos_crecimiento: list[dict]
    eventos_reproductivos: list[dict]
    indicadores: list[dict]
    advertencias: list[str]


@dataclass
class GestionFase:
    id_activo_biologico: int
    id_ciclo_productiva: int
    nombre_ciclo: str
    fecha_inicio: datetime
    es_activa: bool
    id_usuario: int
    id_gestion_fases: Optional[int] = None
    nombre_fase_actual: Optional[str] = None
    paso_actual: Optional[int] = None
    total_pasos: Optional[int] = None
    fecha_finalizacion: Optional[datetime] = None
    motivo_cambio: Optional[str] = None


@dataclass
class HistoricoEstado:
    id_activo_biologico: int
    id_estado_anterior: int
    id_estado_nuevo: int
    fecha_cambio: datetime
    modulo_origen: str
    id_usuario: int
    id_historico: Optional[int] = None
    nombre_estado_anterior: Optional[str] = None
    nombre_estado_nuevo: Optional[str] = None
    motivo_cambio: Optional[str] = None


@dataclass
class HistorialInfraestructura:
    id_historial: int
    id_activo_biologico: int
    id_infraestructura: int
    nombre_infraestructura: str
    tipo_infraestructura: str
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]


@dataclass
class IndicadorZootecnico:
    tipo: str
    unidad: str
    fecha_calculo: datetime
    disponible: bool
    valor: Optional[Decimal] = None
    periodo_inicio: Optional[date] = None
    periodo_fin: Optional[date] = None
    variables_usadas: dict = field(default_factory=dict)


@dataclass
class ResultadoIndicadores:
    id_activo_biologico: int
    tipo_activo: str
    indicadores: list[IndicadorZootecnico] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)


@dataclass
class SeccionDatosConsolidados:
    historial_eventos: list[dict] = field(default_factory=list)
    historial_fases: list[dict] = field(default_factory=list)
    historico_estados: list[dict] = field(default_factory=list)
    metricas_actuales: dict = field(default_factory=dict)
    total_registros: int = 0
    pagina_actual: int = 1
    total_paginas: int = 1
    registros_por_pagina: int = 20


@dataclass
class DatosConsolidados:
    id_activo_biologico: int
    identificador: Optional[str]
    tipo_activo: str
    especie: str
    estado_actual: str
    infraestructura_asociada: Optional[str]
    fase_productiva_activa: Optional[str]
    fecha_generacion: datetime
    secciones: SeccionDatosConsolidados = field(default_factory=SeccionDatosConsolidados)


@dataclass
class AsociacionSensorActivo:
    id_activo_biologico: int
    tipo_activo: str           # INDIVIDUAL | LOTE
    tipo_asociacion: str       # directa | ambiental | poblacional
    dispositivo_iot_id: int
    sensor_id: int
    id_infraestructura: int
    id_usuario: int
    fecha_inicio: datetime
    estado_asociacion: str = 'ACTIVA'
    fecha_fin: Optional[datetime] = None
    motivo: Optional[str] = None
    id_asociacion_activo_sensor: Optional[int] = None
    fecha_creacion: Optional[datetime] = None


@dataclass(eq=False)
class ActivoBiologico:
    id_especie: int
    tipo: str
    origen_financiero: str
    id_infraestructura: int
    id_estado: int
    id_usuario: int
    identificador: Optional[str] = None
    fecha_inicio_ciclo: Optional[date] = None
    detalles_procedencia: Optional[str] = None
    costo_adquisicion: Optional[Decimal] = None
    soporte_documental: Optional[str] = None
    descripcion: Optional[str] = None
    atributos_dinamicos: Optional[dict] = None
    detalle_individual: Optional[DetalleIndividual] = None
    detalle_poblacional: Optional[DetallePoblacional] = None
    id_activo_biologico: Optional[int] = None
    fecha_creacion: Optional[datetime] = None
    nombre_estado: Optional[str] = None

    @classmethod
    def crear(cls, dto: object, id_usuario: int) -> ActivoBiologico:
        from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo

        detalle_individual: Optional[DetalleIndividual] = None
        detalle_poblacional: Optional[DetallePoblacional] = None

        if getattr(dto, 'tipo_activo') == 'INDIVIDUAL':
            detalle_individual = DetalleIndividual(
                raza=dto.raza,
                sexo=dto.sexo,
                fecha_nacimiento=dto.fecha_nacimiento,
                peso_inicial=dto.peso_inicial,
            )
        else:
            detalle_poblacional = DetallePoblacional(
                cantidad_inicial=dto.cantidad_inicial,
                cantidad_actual=dto.cantidad_inicial,  # se inicializa = cantidad_inicial
                peso_promedio_inicial=dto.peso_promedio_inicial,
            )

        return cls(
            id_especie=dto.id_especie,
            tipo=dto.tipo_activo,
            origen_financiero=dto.origen_financiero,
            id_infraestructura=dto.id_infraestructura,
            id_estado=EstadoActivo.ACTIVO,
            id_usuario=id_usuario,
            identificador=dto.identificador,
            fecha_inicio_ciclo=dto.fecha_inicio_ciclo,
            detalles_procedencia=dto.detalles_procedencia,
            costo_adquisicion=dto.costo_adquisicion,
            soporte_documental=dto.soporte_documental,
            atributos_dinamicos=dto.atributos_dinamicos,
            detalle_individual=detalle_individual,
            detalle_poblacional=detalle_poblacional,
        )

    def actualizar_detalle_individual(
        self,
        raza: Optional[str],
        sexo: Optional[str],
        fecha_nacimiento: Optional[datetime],
        peso_inicial: Optional[Decimal],
    ) -> None:
        if self.tipo != 'INDIVIDUAL':
            raise ValidationError(
                code='TIPO_INVALIDO',
                message='Solo los activos de tipo INDIVIDUAL tienen detalle individual editable.',
            )
        if self.detalle_individual is None:
            raise ValidationError(
                code='DETALLE_INDIVIDUAL_AUSENTE',
                message='El activo no tiene detalle individual registrado.',
            )
        if raza is not None:
            self.detalle_individual.raza = raza
        if sexo is not None:
            self.detalle_individual.sexo = sexo
        if fecha_nacimiento is not None:
            self.detalle_individual.fecha_nacimiento = fecha_nacimiento
        if peso_inicial is not None:
            self.detalle_individual.peso_inicial = peso_inicial

    def _snapshot(self) -> dict:
        return {
            'id_activo_biologico': self.id_activo_biologico,
            'id_especie': self.id_especie,
            'tipo': self.tipo,
            'identificador': self.identificador,
            'origen_financiero': self.origen_financiero,
            'id_infraestructura': self.id_infraestructura,
            'id_estado': self.id_estado,
            'fecha_inicio_ciclo': self.fecha_inicio_ciclo.isoformat() if self.fecha_inicio_ciclo else None,
            'costo_adquisicion': str(self.costo_adquisicion) if self.costo_adquisicion else None,
            'soporte_documental': self.soporte_documental,
            'detalles_procedencia': self.detalles_procedencia,
        }

    def _validar_tipo_poblacional(self) -> None:
        if self.tipo != 'POBLACIONAL':
            raise BusinessRuleError(
                code='TIPO_INVALIDO',
                message='Esta operación solo aplica a activos de tipo POBLACIONAL.',
            )
        if self.detalle_poblacional is None:
            raise BusinessRuleError(
                code='DETALLE_POBLACIONAL_AUSENTE',
                message='El activo no tiene detalle poblacional registrado.',
            )

    def cambiar_estado(self, nuevo_id_estado: int) -> None:
        from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo, TRANSICIONES_VALIDAS

        if self.id_estado == EstadoActivo.BAJA:
            raise ConflictError(
                code='ESTADO_BAJA_IRREVERSIBLE',
                message='El activo se encuentra en estado BAJA. No se permite modificar el estado de activos dados de baja definitivamente.',
            )
        if self.id_estado == nuevo_id_estado:
            raise ConflictError(
                code='ESTADO_REDUNDANTE',
                message=f'El activo ya se encuentra en el estado solicitado. No se realizó ningún cambio.',
            )
        transiciones_permitidas = TRANSICIONES_VALIDAS.get(self.id_estado, set())
        if nuevo_id_estado not in transiciones_permitidas:
            nombres = {e.value: e.name for e in EstadoActivo}
            actual = nombres.get(self.id_estado, str(self.id_estado))
            nuevo = nombres.get(nuevo_id_estado, str(nuevo_id_estado))
            validos = ', '.join(nombres.get(v, str(v)) for v in sorted(transiciones_permitidas))
            raise BusinessRuleError(
                code='TRANSICION_INVALIDA',
                message=(
                    f'La transición {actual} → {nuevo} no está permitida. '
                    f'Transiciones válidas desde {actual}: {validos or "ninguna"}.'
                ),
            )
        self.id_estado = nuevo_id_estado

    def aplicar_evento_baja(self, cantidad_afectada: int) -> None:
        self._validar_tipo_poblacional()
        dp = self.detalle_poblacional
        cantidad_actual = dp.cantidad_actual or 0
        if cantidad_actual - cantidad_afectada < 0:
            raise BusinessRuleError(
                code='CANTIDAD_NEGATIVA',
                message=(
                    f'La baja de {cantidad_afectada} individuos dejaría la cantidad actual '
                    f'en negativo (actual: {cantidad_actual}).'
                ),
            )
        dp.cantidad_actual = cantidad_actual - cantidad_afectada
        if dp.peso_promedio is not None:
            dp.biomasa_total = Decimal(str(dp.cantidad_actual)) * dp.peso_promedio

    def aplicar_evento_crecimiento(self, nuevo_peso_promedio: Decimal, superficie: Decimal) -> None:
        self._validar_tipo_poblacional()
        dp = self.detalle_poblacional
        dp.peso_promedio = nuevo_peso_promedio
        cantidad_actual = Decimal(str(dp.cantidad_actual or 0))
        dp.biomasa_total = cantidad_actual * nuevo_peso_promedio
        if superficie and superficie > 0:
            dp.densidad = cantidad_actual / superficie

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ActivoBiologico):
            return NotImplemented
        if self.id_activo_biologico is None or other.id_activo_biologico is None:
            return self is other
        return self.id_activo_biologico == other.id_activo_biologico

    def __hash__(self) -> int:
        return hash(self.id_activo_biologico)
