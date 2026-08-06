"""Entidades del motor async de generación de reportes de gastos (RF-77 / CU-04).

Analogía con el motor batch ICA (RF-74): ``TrabajoReporteGasto`` es la fila de
cola (un reporte solicitado con sus filtros en ``parametros``),
``EjecucionReporteGasto`` es cada intento de procesarlo y ``FalloReporteGasto``
es el fallo técnico persistente tras agotar los reintentos.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync


@dataclass(eq=False)
class TrabajoReporteGasto:
    """Fila de cola: un reporte de gastos pendiente de generación async."""

    parametros: dict
    id_usuario_solicitante: int
    estado: EstadoTrabajoAsync = EstadoTrabajoAsync.PENDIENTE
    fecha_solicitud: Optional[datetime] = None
    fecha_procesado: Optional[datetime] = None
    id_cola: Optional[int] = None


@dataclass(eq=False)
class EjecucionReporteGasto:
    """Un intento de procesamiento de un ``TrabajoReporteGasto``."""

    id_cola: int
    estado: EstadoTrabajoAsync = EstadoTrabajoAsync.EN_PROCESO
    intento: int = 1
    hora_inicio: Optional[datetime] = None
    hora_fin: Optional[datetime] = None
    id_reporte_resultado: Optional[int] = None
    resultado_json: Optional[dict] = None
    id_ejecucion: Optional[int] = None

    def completar(self, *, hora_fin: datetime, id_reporte_resultado: int, resultado_json: dict) -> None:
        self.estado = EstadoTrabajoAsync.COMPLETADO
        self.hora_fin = hora_fin
        self.id_reporte_resultado = id_reporte_resultado
        self.resultado_json = resultado_json

    def fallar(self, *, hora_fin: datetime) -> None:
        self.estado = EstadoTrabajoAsync.FALLIDO
        self.hora_fin = hora_fin


@dataclass(eq=False)
class FalloReporteGasto:
    """Fallo técnico persistente tras agotar los reintentos configurados."""

    id_cola: int
    causa_fallo: str
    intentos: int
    timestamp_ultimo_intento: Optional[datetime] = None
    resuelto: bool = False
    id_fallo: Optional[int] = None
