"""Servicio de dominio: cálculo del reporte de gastos acumulados (RF-77).

Puro: no toca BD. Recibe las líneas de gasto ya recolectadas (período actual y
gasto del período anterior ya sumado) y produce el desglose por categoría, el
desglose temporal, la tendencia y la lista de eventos sin costo. Se reutiliza
tal cual desde el flujo síncrono y desde el worker del motor async — así ambos
caminos calculan exactamente igual.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from src.supplies.domain.entities.reporte_gasto import (
    DesgloseCategoria,
    DesglosePeriodo,
    LineaGasto,
    RegistroSinCosto,
    TendenciaGasto,
)
from src.supplies.domain.value_objects.reporte_gasto_enums import EstadoTendencia, GranularidadDesglose

_CERO = Decimal("0")


@dataclass(frozen=True)
class ResultadoCalculoReporteGasto:
    gasto_total_acumulado: Decimal
    desglose_categorias: list[DesgloseCategoria]
    desglose_temporal: list[DesglosePeriodo]
    registros_sin_costo: list[RegistroSinCosto]
    tendencia: TendenciaGasto
    sin_datos: bool


class CalculadoraReporteGasto:
    """Calcula de forma pura los agregados del reporte de gastos (RF-77)."""

    def calcular(
        self,
        *,
        lineas: list[LineaGasto],
        tipo_periodo: str,
        gasto_periodo_anterior: Optional[Decimal],
        periodo_anterior_recortado: bool = False,
        fecha_inicio_ciclo_recorte: Optional[date] = None,
    ) -> ResultadoCalculoReporteGasto:
        valorizadas = [l for l in lineas if l.monto is not None]
        sin_costo = [l for l in lineas if l.monto is None]

        gasto_total = sum((l.monto for l in valorizadas), _CERO)

        desglose_categorias = self._desglose_categorias(valorizadas, gasto_total)
        desglose_temporal = self._desglose_temporal(valorizadas, tipo_periodo)
        registros_sin_costo = [
            RegistroSinCosto(categoria=l.categoria, id_origen=l.id_origen, fecha=l.fecha, descripcion=l.descripcion)
            for l in sin_costo
        ]
        tendencia = self._tendencia(
            gasto_total, gasto_periodo_anterior, periodo_anterior_recortado, fecha_inicio_ciclo_recorte
        )

        return ResultadoCalculoReporteGasto(
            gasto_total_acumulado=gasto_total,
            desglose_categorias=desglose_categorias,
            desglose_temporal=desglose_temporal,
            registros_sin_costo=registros_sin_costo,
            tendencia=tendencia,
            sin_datos=not valorizadas,
        )

    @staticmethod
    def _desglose_categorias(valorizadas: list[LineaGasto], gasto_total: Decimal) -> list[DesgloseCategoria]:
        grupos: dict[str, list[LineaGasto]] = {}
        for l in valorizadas:
            grupos.setdefault(l.categoria, []).append(l)
        resultado = []
        for categoria, items in sorted(grupos.items()):
            subtotal = sum((x.monto for x in items), _CERO)
            porcentaje = (subtotal / gasto_total * 100) if gasto_total else _CERO
            resultado.append(
                DesgloseCategoria(
                    categoria=categoria,
                    subtotal=subtotal,
                    num_registros=len(items),
                    porcentaje=porcentaje,
                )
            )
        return resultado

    @staticmethod
    def _desglose_temporal(valorizadas: list[LineaGasto], tipo_periodo: str) -> list[DesglosePeriodo]:
        if tipo_periodo == GranularidadDesglose.CICLO_COMPLETO.value:
            return []
        grupos: dict[str, list[LineaGasto]] = {}
        for l in valorizadas:
            if tipo_periodo == GranularidadDesglose.SEMANAL.value:
                iso_year, iso_week, _ = l.fecha.isocalendar()
                etiqueta = f"{iso_year}-W{iso_week:02d}"
            else:  # MENSUAL
                etiqueta = f"{l.fecha.year}-{l.fecha.month:02d}"
            grupos.setdefault(etiqueta, []).append(l)
        resultado = []
        for etiqueta, items in sorted(grupos.items()):
            fechas = [x.fecha for x in items]
            resultado.append(
                DesglosePeriodo(
                    etiqueta=etiqueta,
                    fecha_inicio=min(fechas),
                    fecha_fin=max(fechas),
                    monto=sum((x.monto for x in items), _CERO),
                )
            )
        return resultado

    @staticmethod
    def _tendencia(
        gasto_actual: Decimal,
        gasto_anterior: Optional[Decimal],
        recortado: bool,
        fecha_recorte: Optional[date],
    ) -> TendenciaGasto:
        anterior = gasto_anterior if gasto_anterior is not None else _CERO
        nota: Optional[str] = None
        if anterior == 0 and gasto_actual > 0:
            estado = EstadoTendencia.SIN_BASE_COMPARATIVA.value
            variacion = None
            nota = (
                "No existen gastos registrados en el período anterior equivalente. "
                "No es posible calcular variación porcentual."
            )
        elif anterior == 0 and gasto_actual == 0:
            estado = EstadoTendencia.SIN_MOVIMIENTO.value
            variacion = None
        else:
            estado = EstadoTendencia.CALCULADA.value
            variacion = (gasto_actual - anterior) / anterior * 100

        if recortado and fecha_recorte is not None:
            recorte_nota = f"El período anterior fue recortado al inicio del ciclo productivo ({fecha_recorte.isoformat()})."
            nota = f"{nota} {recorte_nota}" if nota else recorte_nota

        return TendenciaGasto(
            gasto_periodo_actual=gasto_actual,
            gasto_periodo_anterior=anterior,
            variacion_porcentual=variacion,
            estado=estado,
            nota=nota,
        )
