# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79 R7/R11: monto = Σ costo_registro    |
"""Servicio de dominio: construcción del reporte consolidado NIC-41 (RF-79).

**Puro**: no toca BD. Recibe todos los registros (``REGISTRO`` y ``CORRECCION``)
de una instancia de ciclo y el acumulado vigente. El monto es la fórmula de
RF-78 R7: ``Σ costo_registro`` de todas las filas — una CORRECCION es un ajuste
que suma (R12), negativo cuando compensa (RNF-09).

Verifica la consistencia exigida por la Restricción 11 de RF-79: si el monto
recalculado a partir de los registros no coincide exactamente con
``acumulado.acumulado_total_ciclo`` ni con lo provisto incrementalmente, marca ``es_reporte_potencialmente_incompleto
= True`` (CA-11) en vez de fallar — el reporte se genera igual, con la
advertencia, preservando la trazabilidad del incidente.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.supplies.domain.entities.acumulado_ciclo import AcumuladoCiclo
from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto


@dataclass(frozen=True)
class ResultadoConsolidacion:
    """Resultado puro de consolidar los registros de una instancia de ciclo."""

    monto_provision: Decimal
    desglose_categoria: dict[str, Decimal]
    lista_registros: list[dict]
    es_reporte_potencialmente_incompleto: bool


def construir_consolidado(
    registros: list[RegistroSuministroDirecto],
    acumulado: AcumuladoCiclo,
    *,
    suma_incremental: Optional[Decimal] = None,
    eventos_sin_entregar: int = 0,
) -> ResultadoConsolidacion:
    """Construye el consolidado NIC-41 a partir del ledger completo de una instancia de ciclo.

    ``suma_incremental`` es la suma de los eventos INCREMENTAL emitidos hacia M06
    para el ciclo y ``eventos_sin_entregar`` los que siguen en el outbox: si la
    suma difiere del monto o queda alguno sin entregar, el reporte se marca
    potencialmente incompleto (RF-79 R11, E6 y E7 f).
    """
    monto_provision = sum((r.costo_registro for r in registros), Decimal("0"))

    desglose_categoria: dict[str, Decimal] = {}
    for registro in registros:
        desglose_categoria[registro.tipo_suministro] = (
            desglose_categoria.get(registro.tipo_suministro, Decimal("0")) + registro.costo_registro
        )

    es_incompleto = (
        monto_provision != acumulado.acumulado_total_ciclo
        or (suma_incremental is not None and suma_incremental != monto_provision)
        or eventos_sin_entregar > 0
    )

    lista_registros = [_a_dict(registro) for registro in registros]

    return ResultadoConsolidacion(
        monto_provision=monto_provision,
        desglose_categoria=desglose_categoria,
        lista_registros=lista_registros,
        es_reporte_potencialmente_incompleto=es_incompleto,
    )


def _a_dict(registro: RegistroSuministroDirecto) -> dict:
    """Serializa un registro a un dict JSON-compatible para ``lista_registros`` (jsonb)."""
    return {
        "id_registro_suministro": str(registro.id_registro_suministro),
        "tipo_suministro": registro.tipo_suministro,
        "tipo_operacion": registro.tipo_operacion,
        "cantidad": str(registro.cantidad),
        "unidad_medida": registro.unidad_medida,
        "precio_unitario_resuelto": str(registro.precio_unitario_resuelto),
        "costo_registro": str(registro.costo_registro),
        "origen_precio": registro.origen_precio,
        "fecha_aplicacion": registro.fecha_aplicacion.isoformat(),
        "naturaleza_costo": registro.naturaleza_costo,
        "id_registro_original": (
            str(registro.id_registro_original) if registro.id_registro_original else None
        ),
        "motivo_correccion": registro.motivo_correccion,
        "fecha_registro": registro.fecha_registro.isoformat() if registro.fecha_registro else None,
    }
