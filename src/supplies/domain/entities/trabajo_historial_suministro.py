"""Entidades del motor async de historial de suministros (RF-81 / CU-04).

Analogía con el motor batch ICA (RF-74) y con ``trabajo_reporte_gasto.py``
(RF-77). ``tipo_trabajo`` distingue ``CONSULTA_PESADA`` (nivel de volumen 3/4)
de ``EXPORTACION`` (> 10.000 registros).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync


@dataclass(eq=False)
class TrabajoHistorialSuministro:
    """Fila de cola: un trabajo pesado de historial pendiente de procesar."""

    tipo_trabajo: str  # CONSULTA_PESADA | EXPORTACION
    parametros: dict
    id_usuario_solicitante: int
    estado: EstadoTrabajoAsync = EstadoTrabajoAsync.PENDIENTE
    fecha_solicitud: Optional[datetime] = None
    fecha_procesado: Optional[datetime] = None
    id_cola: Optional[int] = None


@dataclass(eq=False)
class EjecucionHistorialSuministro:
    """Un intento de procesamiento de un ``TrabajoHistorialSuministro``."""

    id_cola: int
    estado: EstadoTrabajoAsync = EstadoTrabajoAsync.EN_PROCESO
    intento: int = 1
    hora_inicio: Optional[datetime] = None
    hora_fin: Optional[datetime] = None
    total_registros: Optional[int] = None
    resultado_json: Optional[dict] = None
    contenido_csv: Optional[str] = None
    nombre_archivo: Optional[str] = None
    id_ejecucion: Optional[int] = None

    def completar_consulta(self, *, hora_fin: datetime, total_registros: int, resultado_json: dict) -> None:
        self.estado = EstadoTrabajoAsync.COMPLETADO
        self.hora_fin = hora_fin
        self.total_registros = total_registros
        self.resultado_json = resultado_json

    def completar_exportacion(
        self, *, hora_fin: datetime, total_registros: int, contenido_csv: str, nombre_archivo: str
    ) -> None:
        self.estado = EstadoTrabajoAsync.COMPLETADO
        self.hora_fin = hora_fin
        self.total_registros = total_registros
        self.contenido_csv = contenido_csv
        self.nombre_archivo = nombre_archivo

    def fallar(self, *, hora_fin: datetime) -> None:
        self.estado = EstadoTrabajoAsync.FALLIDO
        self.hora_fin = hora_fin


@dataclass(eq=False)
class FalloHistorialSuministro:
    """Fallo técnico persistente tras agotar los reintentos configurados."""

    id_cola: int
    causa_fallo: str
    intentos: int
    timestamp_ultimo_intento: Optional[datetime] = None
    resuelto: bool = False
    id_fallo: Optional[int] = None
