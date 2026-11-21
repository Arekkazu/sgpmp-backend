# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-218-G029 RF-68: calcular promedio temporal de densidades registradas en los últimos 30 días. |
"""Lecturas históricas de ocupación; sin dependencia de PostgreSQL ni del ORM."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

VENTANA_OCUPACION = timedelta(days=30)


@dataclass(frozen=True)
class MuestraOcupacion:
    id_registro: int
    fecha: datetime
    densidad: Decimal | None


@dataclass(frozen=True)
class OcupacionHistorica:
    densidad_promedio: Decimal | None
    desde: datetime
    hasta: datetime
    segundos_cubiertos: Decimal
    registros_utilizados: tuple[int, ...]

    def snapshot(self) -> dict:
        return {
            'fuente': 'auditoria.logs_dml:modulo2.detalles_activos_biologicos_poblacionales',
            'fecha_desde': self.desde.isoformat(),
            'fecha_hasta': self.hasta.isoformat(),
            'segundos_cubiertos': str(self.segundos_cubiertos),
            'segundos_ventana': str(_segundos(self.hasta - self.desde)),
            'muestras_utilizadas': len(self.registros_utilizados),
            'primer_id_registro': self.registros_utilizados[0] if self.registros_utilizados else None,
            'ultimo_id_registro': self.registros_utilizados[-1] if self.registros_utilizados else None,
            'densidad_promedio': str(self.densidad_promedio) if self.densidad_promedio is not None else None,
        }


def _segundos(intervalo: timedelta) -> Decimal:
    return Decimal(intervalo.days * 86400 + intervalo.seconds) + Decimal(intervalo.microseconds) / 1000000


def promediar_ocupacion(muestras: list[MuestraOcupacion], *, hasta: datetime) -> OcupacionHistorica:
    """Promedio sobre el tiempo conocido dentro de [hasta-30 días, hasta].

    El último registro previo delimita el estado inicial de la ventana. Un valor
    nulo, negativo o no finito interrumpe la cobertura; no prolonga el anterior.
    En un mismo instante prevalece el registro de mayor id. No se rellenan huecos.
    """
    desde = hasta - VENTANA_OCUPACION
    cursor = desde
    vigente: MuestraOcupacion | None = None
    acumulado = Decimal('0')
    cubierto = Decimal('0')
    utilizados: list[int] = []

    def acumular(fin: datetime) -> None:
        nonlocal acumulado, cubierto
        duracion = _segundos(fin - cursor)
        if (duracion > 0 and vigente is not None and vigente.densidad is not None
                and vigente.densidad.is_finite() and vigente.densidad >= 0):
            acumulado += vigente.densidad * duracion
            cubierto += duracion
            if not utilizados or utilizados[-1] != vigente.id_registro:
                utilizados.append(vigente.id_registro)

    for muestra in sorted((m for m in muestras if m.fecha <= hasta), key=lambda m: (m.fecha, m.id_registro)):
        if muestra.fecha <= desde:
            vigente = muestra
            continue
        acumular(muestra.fecha)
        cursor = muestra.fecha
        vigente = muestra
    acumular(hasta)
    return OcupacionHistorica(
        densidad_promedio=acumulado / cubierto if cubierto else None,
        desde=desde, hasta=hasta, segundos_cubiertos=cubierto,
        registros_utilizados=tuple(utilizados),
    )
