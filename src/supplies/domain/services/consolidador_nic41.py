"""Servicio de dominio: construcción del reporte consolidado NIC-41 (RF-79).

**Puro**: no toca BD. Recibe todos los registros (``REGISTRO`` y ``CORRECCION``)
de una instancia de ciclo y el acumulado vigente, y construye el desglose por
categoría y el monto total a partir del **estado efectivo** de cada suministro
(la corrección más reciente reemplaza al original que referencia — el original
no se elimina, pero su costo ya no cuenta por separado, tal como lo hace la
aritmética de deltas del trigger ``trg_acumular_costo_ciclo``).

Verifica la consistencia exigida por la Restricción 11 de RF-79: si el monto
recalculado a partir de los registros no coincide exactamente con
``acumulado.acumulado_total_ciclo``, marca ``es_reporte_potencialmente_incompleto
= True`` (CA-11) en vez de fallar — el reporte se genera igual, con la
advertencia, preservando la trazabilidad del incidente.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from src.supplies.domain.entities.acumulado_ciclo import AcumuladoCiclo
from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto

_FECHA_MIN = datetime.combine(date.min, time.min)


@dataclass(frozen=True)
class ResultadoConsolidacion:
    """Resultado puro de consolidar los registros de una instancia de ciclo."""

    monto_provision: Decimal
    desglose_categoria: dict[str, Decimal]
    lista_registros: list[dict]
    es_reporte_potencialmente_incompleto: bool


def construir_consolidado(
    registros: list[RegistroSuministroDirecto], acumulado: AcumuladoCiclo
) -> ResultadoConsolidacion:
    """Construye el consolidado NIC-41 a partir del ledger completo de una instancia de ciclo."""
    correccion_mas_reciente_por_original: dict[UUID, RegistroSuministroDirecto] = {}
    for registro in registros:
        if registro.tipo_operacion != "CORRECCION" or registro.id_registro_original is None:
            continue
        vigente = correccion_mas_reciente_por_original.get(registro.id_registro_original)
        if vigente is None or (registro.fecha_registro or _FECHA_MIN) >= (vigente.fecha_registro or _FECHA_MIN):
            correccion_mas_reciente_por_original[registro.id_registro_original] = registro

    efectivos: list[RegistroSuministroDirecto] = []
    for registro in registros:
        if registro.tipo_operacion != "REGISTRO":
            continue
        correccion = correccion_mas_reciente_por_original.get(registro.id_registro_suministro)
        efectivos.append(correccion if correccion is not None else registro)

    monto_provision = sum((e.costo_registro for e in efectivos), Decimal("0"))

    desglose_categoria: dict[str, Decimal] = {}
    for efectivo in efectivos:
        desglose_categoria[efectivo.tipo_suministro] = (
            desglose_categoria.get(efectivo.tipo_suministro, Decimal("0")) + efectivo.costo_registro
        )

    es_incompleto = monto_provision != acumulado.acumulado_total_ciclo

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
