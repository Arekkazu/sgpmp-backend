# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-89: prioridad de fuente, vigencia y estado efectivo del precio |
# | 2026-11-08 | destroyerban | INC-M06-310-G12 RF-83: motivo de la estimación y precio usado |
# | 2026-11-11 | Arekkazu | TC-M06-G106 RF-89 FA-6: el precio corregido sale del cálculo y queda CORREGIDO |
"""Reglas de RF-89 sobre el repositorio de precios (NIC 41 ¶17). Python puro.

El estado de un precio depende de la fecha (PROGRAMADO, ACTIVO, VENCIDO, SUPERADO) y el
repositorio es inmutable, así que se calcula al leer en lugar de guardarse. Un precio que otro
corrige (FA-6) queda CORREGIDO y deja de contar: su corrección ocupa su lugar con la misma fecha.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from src.financial_valuation.domain.value_objects.nic41 import PRIORIDAD_FUENTES, FuentePrecio


@dataclass(frozen=True)
class Precio:
    id_precio_mercado: int
    id_especie: int
    categoria: str
    precio_unitario: Decimal
    unidad_medida: str
    fuente: str
    fecha_vigencia: date
    fecha_vencimiento: Optional[date] = None
    id_metrica_produccion: Optional[int] = None
    evidencia: str = ""
    justificacion: Optional[str] = None
    id_precio_corregido: Optional[int] = None

    def vigente_en(self, dia: date) -> bool:
        return self.fecha_vigencia <= dia and (self.fecha_vencimiento is None or self.fecha_vencimiento >= dia)


def _corregidos(precios: Iterable[Precio]) -> set[int]:
    return {p.id_precio_corregido for p in precios if p.id_precio_corregido is not None}


def _mas_reciente(precios: Iterable[Precio], dia: date) -> Optional[Precio]:
    """El de mayor fecha de vigencia que ya empezó; desempata el registro más nuevo (CA-11). Un
    precio corregido no cuenta (FA-6); la corrección es de su mismo grupo, así que basta la lista."""
    lista = list(precios)
    corregidos = _corregidos(lista)
    candidatos = [p for p in lista if p.fecha_vigencia <= dia and p.id_precio_mercado not in corregidos]
    return max(candidatos, key=lambda p: (p.fecha_vigencia, p.id_precio_mercado), default=None)


def precio_vigente(precios: Iterable[Precio], dia: date) -> Optional[Precio]:
    """RF-89: dentro de cada fuente manda el más reciente (y reemplaza a los anteriores); entre
    fuentes, MERCADO_ACTIVO > UPRA > ESTIMADA aunque otra fuente sea más reciente (CA-14)."""
    lista = list(precios)
    for fuente in PRIORIDAD_FUENTES:
        ultimo = _mas_reciente((p for p in lista if p.fuente == fuente.value), dia)
        if ultimo is not None and ultimo.vigente_en(dia):
            return ultimo
    return None


def ultimo_precio_conocido(precios: Iterable[Precio], dia: date) -> Optional[Precio]:
    """Último precio de cualquier fuente aunque haya vencido: estimación de RF-83 FA-1 para un
    activo que ya se mide a valor razonable (NIC 41 ¶31 impide pasarlo a costo)."""
    return _mas_reciente(precios, dia)


def motivo_estimacion(precio: Precio, dia: date) -> Optional[str]:
    """Por qué una medición con ``precio`` en ``dia`` es estimada (RF-83 FA-1); ``None`` si no lo es.

    ``SIN_PRECIO_VIGENTE``: se usó el último precio conocido porque no había uno vigente.
    ``FUENTE_ESTIMADA``: el precio vigente es una estimación del Contador (RF-89, fuente ESTIMADA)."""
    if not precio.vigente_en(dia):
        return "SIN_PRECIO_VIGENTE"
    if precio.fuente == FuentePrecio.ESTIMADA.value:
        return "FUENTE_ESTIMADA"
    return None


def estado_precio(precio: Precio, mismos: Iterable[Precio], hoy: date) -> str:
    """Estado efectivo para el historial (RF-89 paso 2). ``mismos``: precios de la misma
    especie, categoría, métrica y fuente."""
    mismos = list(mismos)
    if precio.id_precio_mercado in _corregidos(mismos):  # FA-6
        return "CORREGIDO"
    if precio.fecha_vigencia > hoy:
        return "PROGRAMADO"
    ultimo = _mas_reciente(mismos, hoy)
    if ultimo is not None and ultimo.id_precio_mercado != precio.id_precio_mercado:
        return "SUPERADO"
    if precio.fecha_vencimiento is not None and precio.fecha_vencimiento < hoy:
        return "VENCIDO"
    return "ACTIVO"


def desviacion_pct(nuevo: Decimal, anterior: Decimal) -> Decimal:
    """Variación porcentual contra el precio vigente anterior o, en una corrección, contra el precio
    que se corrige (RF-89 paso 5j / FA-7)."""
    return abs(Decimal(nuevo) - Decimal(anterior)) / Decimal(anterior) * 100


def es_fuente_valida(fuente: str) -> bool:
    return fuente in {f.value for f in FuentePrecio}
