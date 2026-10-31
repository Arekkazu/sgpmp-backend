# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-38 RF-59: zona horaria, truncado con aviso, bitácora y vacíos temporales |
# | 2026-10-23 | destroyerban | DEV-39 RF-58: vista por permiso, GRIS sin umbral y anomalías visibles |
# | 2026-10-26 | Arekkazu | INC-M03 lote 26-10 RF-58/59: combinaciones R12, varias variables, activo, alertas y series |
# | 2026-10-26 | Leandro | ISSUE-678 G87 RF-58: distinguir calidad del valor operativo y momento de la condición actual. |
# | 2026-10-28 | destroyerban | INC-M03-177-G57B RF-58: conteo del semáforo sin repetir la consulta de estados |
# | 2026-10-30 | Arekkazu | INC-M04-225-G112 RF-59: categoria_variable, estado_dato y origen_dato como filtro único |
# | 2026-10-31 | Claude | INC-M03-247-G92 RF-58: unidad de cada semáforo base para el estado general |
# | 2026-10-31 | Claude | INC-M03-246-G88 RF-58: semáforo con la última lectura, el umbral vigente y su tolerancia T |
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


# RF-58 Fase 3: T por defecto cuando el umbral de M09 no la configura (10 % del rango).
TOLERANCIA_SEMAFORO_DEFECTO_PCT = Decimal('0.10')
# Calidades cuyo valor sí describe la condición actual del sensor (ERROR_CALIBRACION no).
CALIDADES_CON_VALOR_SEMAFORO = ('LECTURA_VALIDA', 'FUERA_DE_RANGO')


@dataclass
class UmbralSemaforo:
    """G88: umbral RF-17 vigente de una especie del área, lo que necesita el semáforo RF-58."""
    valor_min: Decimal
    valor_max: Decimal
    tolerancia_semaforo: Optional[Decimal] = None
    niveles: list[dict] = field(default_factory=list)


@dataclass
class EstadoSensorActual:
    """Read-model RF-58: estado actual de un sensor para el dashboard."""
    id_sensor: int
    id_dispositivo_iot: int
    nombre_sensor: str
    tipo_variable: str
    categoria_variable: str
    ultimo_valor: Optional[Decimal]
    ultima_unidad: Optional[str]
    ultimo_timestamp_captura: Optional[datetime]
    estado_semaforo: str        # VERDE / AMARILLO / ROJO / GRIS
    estado_calidad: Optional[str]
    estado_desviacion: Optional[str]
    estado_conectividad: Optional[str]  # ACTIVO / SIN_SEÑAL / BUFFER_ACTIVO / INACTIVO
    tiempo_sin_reporte_min: Optional[int]
    dato_desactualizado: bool
    id_alerta: Optional[int]
    severidad_alerta: Optional[str]
    tendencia: Optional[str]
    id_infraestructura: Optional[int]
    nombre_infraestructura: Optional[str]
    id_finca: Optional[int]
    nombre_finca: Optional[str]
    nivel_bateria_pct: Optional[Decimal]
    calidad_senal_rssi: Optional[Decimal]
    calidad_senal_snr: Optional[Decimal]
    # ISSUE-678: el valor y su fecha pueden preceder a la condición actual del sensor.
    estado_calidad_valor_operativo: Optional[str] = None
    timestamp_estado_actual: Optional[datetime] = None
    # DEV-39 (RF-58 E7, R2, E2): los calcula el use case.
    sin_umbral: bool = False            # GRIS porque la variable no tiene umbral en M09
    indicador_anomalia: bool = False    # FUERA_DE_RANGO / ERROR_CALIBRACION
    es_valor_operativo: bool = True     # Describe el valor mostrado, no la condición posterior.
    etiqueta_estado: Optional[str] = None  # "Sin umbral configurado", "Requiere calibración"...
    # G88 (RF-58 Fase 3): el semáforo se calcula en cada consulta con la última lectura
    # (también FUERA_DE_RANGO) y el umbral vigente; None = sin lectura para resolverlo.
    valor_condicion_actual: Optional[Decimal] = None
    calidad_condicion_actual: Optional[str] = None
    umbrales_vigentes: Optional[list[UmbralSemaforo]] = None


@dataclass(frozen=True)
class SemaforoBaseSensor:
    """G57B: lo que necesita el semáforo efectivo de un sensor, sin lecturas ni contexto.

    El conteo del semáforo (M3-08) cubre todo el alcance; traer ``EstadoSensorActual``
    completo de cada sensor solo para contar repetía la consulta pesada del dashboard.
    """
    estado_semaforo: Optional[str]
    dato_desactualizado: bool
    id_alerta: Optional[int]
    severidad_alerta: Optional[str]
    # G92: unidad productiva vigente del sensor; el estado general de la unidad
    # se calcula con todos sus sensores, no con los de la página consultada.
    id_infraestructura: Optional[int] = None
    # G88: mismos datos que EstadoSensorActual para el semáforo calculado.
    valor_condicion_actual: Optional[Decimal] = None
    calidad_condicion_actual: Optional[str] = None
    umbrales_vigentes: Optional[list[UmbralSemaforo]] = None


@dataclass
class ResumenUnidadProductiva:
    """Read-model RF-58: estado agregado de una unidad productiva."""
    id_infraestructura: int
    nombre_infraestructura: str
    id_finca: int
    nombre_finca: str
    total_sensores: int
    sensores_online: int
    sensores_sin_senal: int
    sensores_con_error: int
    estado_general: str         # peor semáforo entre todos sus sensores
    alertas_activas_count: int
    ultimo_dato_recibido: Optional[datetime]
    # CU04 E1 (INC-M03-205-G93): la unidad sin sensores sale en GRIS con este mensaje.
    mensaje_estado: Optional[str] = None


MENSAJE_UNIDAD_SIN_DATOS = 'Sin datos disponibles'


@dataclass
class LecturaHistorica:
    """Read-model RF-59: una lectura del historial telemétrico."""
    id_telemetria: int
    id_sensor: int
    nombre_sensor: Optional[str]
    id_variable: int
    tipo_variable: str
    categoria_variable: str
    valor: Optional[Decimal]
    valor_ajustado: Optional[Decimal]
    unidad_medida: str
    timestamp_captura: datetime
    estado_calidad: str
    estado_semaforo_historico: str  # calculado contra umbral vigente en timestamp_captura
    origen_dato: str            # TIEMPO_REAL / BUFFER_LOCAL / EDGE_AGREGADO
    id_infraestructura: Optional[int]
    infraestructura: Optional[str]
    finca: Optional[str]
    id_activo_biologico: Optional[int]
    especie: Optional[str]
    id_especie: Optional[int]
    id_alerta: Optional[int]
    nivel_bateria_pct: Optional[Decimal]
    calidad_senal_rssi: Optional[Decimal]
    calidad_senal_snr: Optional[Decimal]
    # Fase 4 / Salida 1 (INC-M03-183-G112): contexto del activo (lote o individuo).
    identificador_activo: Optional[str] = None
    tipo_activo: Optional[str] = None
    # RF-17 — identifica el umbral M09 usado para calcular estado_semaforo_historico
    id_umbral_ambiental: Optional[int] = None
    valor_min_umbral: Optional[Decimal] = None
    valor_max_umbral: Optional[Decimal] = None
    version_umbral: Optional[datetime] = None


@dataclass
class ResumenEstadistico:
    """Read-model RF-59: estadísticas de una variable en el período consultado."""
    tipo_variable: str
    valor_minimo: Optional[Decimal]
    valor_maximo: Optional[Decimal]
    valor_promedio: Optional[Decimal]
    total_lecturas: int
    pct_dentro_rango: Optional[float]
    pct_fuera_rango: Optional[float]
    total_alertas_en_periodo: int = 0
    desviacion_estandar: Optional[Decimal] = None


@dataclass
class AlertaCorrelacionada:
    """RF-59 Salida 5 / CA-8: alerta de RF-57 del periodo, ligada a una lectura consultada."""
    id_alerta: int
    tipo_alerta: str
    severidad: str
    timestamp_generacion: Optional[datetime]
    variable_afectada: Optional[str]
    estado_final: str


@dataclass
class VacioTemporal:
    """RF-59 E7 / CA-17: intervalo sin lecturas de un sensor y variable, mayor que
    3 × su frecuencia de muestreo (minutos)."""
    sensor_id: int
    tipo_variable: str
    desde: datetime
    hasta: datetime
    duracion_min: int
    frecuencia_esperada_min: int


#: RF-59 Restricción 12: combinaciones válidas además del rango de fechas (que siempre va).
#: Se agregan "solo fechas" (CA-1, con el límite de 90 días de E4) y el activo biológico
#: solo, que es una entrada propia del RF (RF-61, caso 220). INC-M04-225-G112: también
#: categoria_variable, estado_dato y origen_dato solos, que las Entradas del RF declaran
#: opcionales (Restricción 3, Fase 3, CA-6) y la Restricción 12 no menciona solos.
COMBINACIONES_FILTROS_VALIDAS: tuple[frozenset[str], ...] = (
    frozenset(),
    frozenset({'tipo_variable'}),
    frozenset({'categoria_variable'}),
    frozenset({'estado_dato'}),
    frozenset({'origen_dato'}),
    frozenset({'sensor_id'}),
    frozenset({'id_unidad_productiva'}),
    frozenset({'especie'}),
    frozenset({'tipo_variable', 'id_unidad_productiva'}),
    frozenset({'tipo_variable', 'especie'}),
    frozenset({'sensor_id', 'estado_dato'}),
    frozenset({'categoria_variable', 'id_unidad_productiva'}),
    frozenset({'id_activo_biologico'}),
)


def describir_combinaciones_validas() -> str:
    return '; '.join(
        ' + '.join(['fechas', *sorted(c)]) for c in COMBINACIONES_FILTROS_VALIDAS
    )


@dataclass
class FiltrosHistorial:
    """Parámetros validados de consulta histórica (RF-59).

    ``tipo_variable`` admite varias variables (CA-9): lista, o texto separado por comas.
    """
    fecha_inicio: date
    fecha_fin: date
    sensor_id: Optional[int] = None
    tipo_variable: Optional[list[str] | str] = None
    categoria_variable: Optional[str] = None
    id_infraestructura: Optional[int] = None
    especie: Optional[str] = None
    estado_dato: Optional[str] = None
    origen_dato: Optional[str] = None
    incluir_alertas: bool = False
    pagina: int = 1
    por_pagina: int = 100
    orden: str = 'DESC'
    ids_fincas_permitidas: Optional[list[int]] = None
    id_activo_biologico: Optional[int] = None

    def __post_init__(self) -> None:
        valores = [self.tipo_variable] if isinstance(self.tipo_variable, str) else (self.tipo_variable or [])
        tipos: list[str] = []
        for valor in valores:
            for parte in valor.split(','):
                parte = parte.strip()
                if parte and parte not in tipos:
                    tipos.append(parte)
        self.tipo_variable = tipos or None

    def filtros_presentes(self) -> frozenset[str]:
        """Nombres (de la Restricción 12) de los filtros aplicados además del rango de fechas."""
        presentes = {
            'sensor_id': self.sensor_id is not None,
            'tipo_variable': bool(self.tipo_variable),
            'categoria_variable': bool(self.categoria_variable),
            'id_unidad_productiva': self.id_infraestructura is not None,
            'especie': bool(self.especie),
            'estado_dato': bool(self.estado_dato),
            'origen_dato': bool(self.origen_dato),
            'id_activo_biologico': self.id_activo_biologico is not None,
        }
        return frozenset(k for k, v in presentes.items() if v)

    def tiene_filtro_adicional(self) -> bool:
        """True si hay al menos un filtro adicional además del rango de fechas."""
        return bool(self.filtros_presentes())

    def combinacion_valida(self) -> bool:
        """RF-59 Restricción 12 (INC-M03-184-G113): solo las combinaciones listadas."""
        if self.fecha_inicio is None or self.fecha_fin is None:
            return False
        return self.filtros_presentes() in COMBINACIONES_FILTROS_VALIDAS


# Orden de severidad del semáforo para agregación de peor estado
_ORDEN_SEMAFORO = {'ROJO': 4, 'AMARILLO': 3, 'GRIS': 2, 'VERDE': 1, 'SIN_DATOS': 0}


class SemaforoCalculator:
    """Lógica pura de cálculo del semáforo (RF-58 Fase 3, RF-59 Restricción 16)."""

    @staticmethod
    def calcular(
        valor: Decimal,
        umbral_min: Decimal,
        umbral_max: Decimal,
        tolerancia_pct: float = 10.0,
    ) -> str:
        T = (umbral_max - umbral_min) * Decimal(str(tolerancia_pct / 100))
        if umbral_min <= valor <= umbral_max:
            return 'VERDE'
        elif (umbral_min - T) < valor < umbral_min or umbral_max < valor < (umbral_max + T):
            return 'AMARILLO'
        else:
            return 'ROJO'

    @staticmethod
    def calcular_por_niveles(
        valor: Decimal,
        niveles: list[dict],
    ) -> str:
        """Determina el semáforo a partir de las bandas RF-17 (normal/precaucion/critico).

        Un valor fuera de todas las bandas configuradas (por debajo de la banda normal
        o por encima de la crítica) se trata como ROJO: es más seguro asumir el peor
        caso que quedarse en un estado optimista sin banda que lo respalde.
        """
        mapa_color = {'normal': 'VERDE', 'precaucion': 'AMARILLO', 'critico': 'ROJO'}
        for nivel in niveles:
            if nivel['limite_inferior'] <= valor <= nivel['limite_superior']:
                return mapa_color.get(nivel['nivel'], 'ROJO')
        return 'ROJO'

    @staticmethod
    def calcular_rf58(
        valor: Decimal,
        valor_min: Decimal,
        valor_max: Decimal,
        niveles: Optional[list[dict]] = None,
        tolerancia: Optional[Decimal] = None,
    ) -> str:
        """G88 — RF-58 Fase 3 sobre un umbral RF-17.

        Dentro de [valor_min, valor_max] manda la banda RF-17 (normal / precaución /
        crítico; sin bandas, VERDE). Fuera del rango: AMARILLO si la distancia al borde
        es menor que la tolerancia T y ROJO si la alcanza o la supera. Sin T configurada
        se usa el 10 % del rango, lo que el semáforo aplicaba antes de ser configurable.
        """
        if valor_min <= valor <= valor_max:
            if niveles:
                return SemaforoCalculator.calcular_por_niveles(valor=valor, niveles=niveles)
            return 'VERDE'
        T = tolerancia if tolerancia is not None else (valor_max - valor_min) * TOLERANCIA_SEMAFORO_DEFECTO_PCT
        distancia = (valor_min - valor) if valor < valor_min else (valor - valor_max)
        return 'AMARILLO' if distancia < T else 'ROJO'

    @staticmethod
    def calcular_con_umbrales(valor: Decimal, umbrales: list['UmbralSemaforo']) -> str:
        """G88: con varias especies en el área, el peor color entre sus umbrales vigentes."""
        return SemaforoCalculator.peor_semaforo([
            SemaforoCalculator.calcular_rf58(valor, u.valor_min, u.valor_max, u.niveles, u.tolerancia_semaforo)
            for u in umbrales
        ])

    @staticmethod
    def aplicar_reglas_alerta(
        estado_base: str,
        tiene_alerta_critica: bool,
        tiene_alerta_activa: bool,
    ) -> str:
        """CA-4: alerta CRITICA → ROJO; alerta activa y estado VERDE → AMARILLO."""
        if tiene_alerta_critica:
            return 'ROJO'
        if tiene_alerta_activa and estado_base == 'VERDE':
            return 'AMARILLO'
        return estado_base

    @staticmethod
    def peor_semaforo(estados: list[str]) -> str:
        """Retorna el estado más grave entre una lista (para resumen de unidad productiva)."""
        if not estados:
            return 'SIN_DATOS'
        return max(estados, key=lambda s: _ORDEN_SEMAFORO.get(s, 0))
