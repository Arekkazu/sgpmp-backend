# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-87 v1.1 / RF-93: comprobante NIC 41 y estado de resultados desde las líneas |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-302-G01 RF-82/RF-86: hecho RECONOCIMIENTO_DONACION |
"""Consolidaciones del cierre (RF-87 v1.1) y del estado de resultados (RF-93). Python puro."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from src.financial_valuation.domain.services.nic41 import CERO, hash_sha256
from src.financial_valuation.domain.value_objects.nic41 import Sentido, TipoHecho


@dataclass(frozen=True)
class LineaContable:
    id_linea: int
    tipo_hecho: str
    sentido: str
    numero_id_tributaria: str
    id_especie: int
    cuenta_debito: str
    cuenta_credito: str
    valor: Decimal


@dataclass(frozen=True)
class Comprobante:
    codigo: str
    numero_id_tributaria: str
    tipo_hecho: str
    id_especie: int
    fecha_comprobante: date
    lineas: list[dict]
    valor_total: Decimal
    ids_lineas: list[int]

    @property
    def hash_integridad(self) -> str:
        return hash_sha256({"codigo": self.codigo, "fecha": self.fecha_comprobante, "lineas": self.lineas})


def consolidar_comprobantes(lineas: Iterable[LineaContable], fin_periodo: date) -> list[Comprobante]:
    """Un comprobante por (titular, tipo_hecho, especie), con una línea por par de cuentas distinto
    (suma de valores) e identificador ``NIC-{NIT}-{AAAAMM}-{TIPO_HECHO}-{ESPECIE}`` (RF-87 v1.1)."""
    grupos: dict[tuple, dict[tuple, Decimal]] = defaultdict(lambda: defaultdict(lambda: CERO))
    ids: dict[tuple, list[int]] = defaultdict(list)
    for linea in lineas:
        clave = (linea.numero_id_tributaria, linea.tipo_hecho, linea.id_especie)
        grupos[clave][(linea.cuenta_debito, linea.cuenta_credito)] += linea.valor
        ids[clave].append(linea.id_linea)
    comprobantes = []
    for (nit, tipo, especie), pares in sorted(grupos.items()):
        detalle = [{"cuenta_debito": d, "cuenta_credito": c, "valor": str(v)} for (d, c), v in sorted(pares.items())]
        comprobantes.append(Comprobante(
            codigo=f"NIC-{nit}-{fin_periodo:%Y%m}-{tipo}-{especie}",
            numero_id_tributaria=nit, tipo_hecho=tipo, id_especie=especie, fecha_comprobante=fin_periodo,
            lineas=detalle, valor_total=sum(pares.values(), CERO), ids_lineas=ids[(nit, tipo, especie)],
        ))
    return comprobantes


# --- RF-93: estado de resultados ---------------------------------------------------------------

INGRESOS = ("ganancia_transformacion_biologica", "ganancia_precio_mercado", "ganancia_reconocimiento_inicial",
            "ingresos_productos_agricolas", "ganancia_ajustes_periodos_anteriores")
GASTOS = ("perdida_transformacion_biologica", "perdida_precio_mercado", "perdida_reconocimiento_inicial",
          "costos_mantenimiento", "inversiones_llevadas_a_gasto", "bajas_activos", "depreciacion_activos_costo",
          "deterioro_activos_costo", "perdida_ajustes_periodos_anteriores")

_COMPONENTE_LINEA = {
    (TipoHecho.VARIACION_VR_TB.value, Sentido.GANANCIA.value): "ganancia_transformacion_biologica",
    (TipoHecho.VARIACION_VR_TB.value, Sentido.PERDIDA.value): "perdida_transformacion_biologica",
    (TipoHecho.VARIACION_VR_PM.value, Sentido.GANANCIA.value): "ganancia_precio_mercado",
    (TipoHecho.VARIACION_VR_PM.value, Sentido.PERDIDA.value): "perdida_precio_mercado",
    (TipoHecho.RECONOCIMIENTO_NACIMIENTO.value, Sentido.UNICO.value): "ganancia_reconocimiento_inicial",
    (TipoHecho.RECONOCIMIENTO_DONACION.value, Sentido.UNICO.value): "ganancia_reconocimiento_inicial",
    (TipoHecho.RECONOCIMIENTO_DIFERENCIA.value, Sentido.GANANCIA.value): "ganancia_reconocimiento_inicial",
    (TipoHecho.RECONOCIMIENTO_DIFERENCIA.value, Sentido.PERDIDA.value): "perdida_reconocimiento_inicial",
    (TipoHecho.PRODUCTO_AGRICOLA.value, Sentido.UNICO.value): "ingresos_productos_agricolas",
    (TipoHecho.BAJA_ACTIVO.value, Sentido.UNICO.value): "bajas_activos",
    (TipoHecho.DEPRECIACION_ACTIVO_COSTO.value, Sentido.UNICO.value): "depreciacion_activos_costo",
    (TipoHecho.DETERIORO_ACTIVO_COSTO.value, Sentido.UNICO.value): "deterioro_activos_costo",
    (TipoHecho.AJUSTE_PERIODO_ANTERIOR.value, Sentido.GANANCIA.value): "ganancia_ajustes_periodos_anteriores",
    (TipoHecho.AJUSTE_PERIODO_ANTERIOR.value, Sentido.PERDIDA.value): "perdida_ajustes_periodos_anteriores",
}


@dataclass(frozen=True)
class MovimientoResultado:
    """Una línea de asiento (``es_reverso`` si revierte otra) vista desde el estado de resultados."""

    tipo_hecho: str
    sentido: str
    valor: Decimal
    es_reverso: bool = False


@dataclass(frozen=True)
class CostoPeriodo:
    naturaleza: Optional[str]
    politica: Optional[str]
    monto: Decimal
    es_reverso: bool = False


@dataclass(frozen=True)
class EstadoResultados:
    componentes: dict[str, Decimal]

    @property
    def total_ingresos(self) -> Decimal:
        return sum((self.componentes[c] for c in INGRESOS), CERO)

    @property
    def total_gastos(self) -> Decimal:
        return sum((self.componentes[c] for c in GASTOS), CERO)

    @property
    def resultado_neto(self) -> Decimal:
        return self.total_ingresos - self.total_gastos


def estado_resultados(movimientos: Iterable[MovimientoResultado], costos: Iterable[CostoPeriodo]) -> EstadoResultados:
    """RF-93. Los costos de mantenimiento salen de RF-90 (todos los orígenes, también los que
    viajan como factura), no de las líneas ``CONSUMO_INSUMO``, para no contarlos dos veces. Las
    inversiones capitalizadas y los costos de venta no son gasto (RF-84, RF-90 CA-10/CA-11)."""
    comp = {c: CERO for c in INGRESOS + GASTOS}
    for m in movimientos:
        nombre = _COMPONENTE_LINEA.get((m.tipo_hecho, m.sentido))
        if nombre is not None:
            comp[nombre] += -m.valor if m.es_reverso else m.valor
    for c in costos:
        monto = -c.monto if c.es_reverso else c.monto
        if c.naturaleza == "MANTENIMIENTO":
            comp["costos_mantenimiento"] += monto
        elif c.naturaleza == "INVERSION" and c.politica == "GASTO":
            comp["inversiones_llevadas_a_gasto"] += monto
    return EstadoResultados(comp)
