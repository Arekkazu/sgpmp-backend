# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #394 RF-36: estado de la densidad del lote frente al límite de su etapa o especie |
"""Política de densidad para activos poblacionales (RF-36)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Optional

from src.shared.errors import BusinessRuleError, ConflictError


def calcular_y_validar_densidad(
    *,
    cantidad_actual: int,
    superficie: Decimal,
    densidad_maxima_por_especie: Decimal | None,
) -> Decimal:
    """Calcula la densidad y exige el límite biológico configurado en M09."""
    if superficie <= 0:
        raise BusinessRuleError(
            code='SUPERFICIE_INFRAESTRUCTURA_INVALIDA',
            message='La infraestructura debe tener una superficie mayor a cero para calcular la densidad.',
            field='id_infraestructura',
        )

    if densidad_maxima_por_especie is None:
        raise BusinessRuleError(
            code='DENSIDAD_MAXIMA_NO_CONFIGURADA',
            message='La especie no tiene configurada una densidad máxima en M09.',
            field='id_especie',
        )

    densidad = Decimal(str(cantidad_actual)) / superficie
    if densidad > densidad_maxima_por_especie:
        raise ConflictError(
            code='DENSIDAD_MAXIMA_SUPERADA',
            message='La densidad del lote supera el máximo permitido para la especie.',
        )
    return densidad


@dataclass(frozen=True)
class EstadoDensidadLote:
    """Densidad del lote frente al límite que le aplica (RF-36, #394).

    ``estado``: OK, AVISO (llegó al aviso preventivo), EXCEDE o SIN_CONFIGURAR (ni la etapa ni la especie
    tienen máximo). ``fuente``: de dónde sale el máximo, ETAPA o ESPECIE; gana el más estricto."""
    estado: str
    densidad_maxima: Optional[Decimal] = None
    fuente: Optional[str] = None
    nombre_etapa: Optional[str] = None
    porcentaje_del_maximo: Optional[Decimal] = None
    aviso_preventivo_pct: int = 90
    superficie: Optional[Decimal] = None
    capacidad_maxima: Optional[int] = None
    cupo_disponible: Optional[int] = None
    biomasa_maxima: Optional[Decimal] = None
    biomasa_por_m2: Optional[Decimal] = None


def evaluar_densidad(*, cantidad: Optional[int], superficie: Optional[Decimal], densidad_especie: Optional[Decimal],
                     limite_etapa, biomasa_total: Optional[Decimal] = None) -> EstadoDensidadLote:
    """``limite_etapa``: el de la fase activa del lote (``LimiteEtapa``) o ``None``."""
    aviso = limite_etapa.aviso_preventivo_pct if limite_etapa else 90
    etapa = limite_etapa.nombre_etapa if limite_etapa else None
    biomasa_maxima = limite_etapa.biomasa_maxima if limite_etapa else None
    candidatos = [(Decimal(m), f) for m, f in ((limite_etapa.densidad_maxima if limite_etapa else None, 'ETAPA'),
                                               (densidad_especie, 'ESPECIE')) if m is not None]
    if not candidatos or cantidad is None or not superficie or superficie <= 0:
        return EstadoDensidadLote(estado='SIN_CONFIGURAR', nombre_etapa=etapa, aviso_preventivo_pct=aviso,
                                  superficie=superficie, biomasa_maxima=biomasa_maxima)
    maxima, fuente = min(candidatos, key=lambda c: c[0])
    superficie = Decimal(superficie)
    densidad = Decimal(cantidad) / superficie
    porcentaje = (densidad / maxima * 100).quantize(Decimal('0.01'))
    capacidad = int((maxima * superficie).to_integral_value(rounding=ROUND_FLOOR))
    estado = 'EXCEDE' if densidad > maxima else 'AVISO' if porcentaje >= aviso else 'OK'
    return EstadoDensidadLote(
        estado=estado, densidad_maxima=maxima, fuente=fuente, nombre_etapa=etapa, porcentaje_del_maximo=porcentaje,
        aviso_preventivo_pct=aviso, superficie=superficie, capacidad_maxima=capacidad,
        cupo_disponible=max(capacidad - cantidad, 0), biomasa_maxima=biomasa_maxima,
        biomasa_por_m2=(Decimal(biomasa_total) / superficie).quantize(Decimal('0.01')) if biomasa_total is not None else None,
    )
