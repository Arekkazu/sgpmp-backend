"""Entidad de dominio :class:`EjecucionBatchICA` (RF-74 / motor batch).

Modela una corrida del batch de cálculo ICA y sus transiciones de estado:
``EN_EJECUCION`` → ``COMPLETADO`` | ``INTERRUMPIDO`` (FA-06 ventana excedida,
FA-12 interrupción manual).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.shared.errors import FlowError
from src.supplies.domain.value_objects.eficiencia_enums import EstadoEjecucionBatch


@dataclass(eq=False)
class EjecucionBatchICA:
    """Corrida del motor batch ICA."""

    tipo_disparo: str  # AUTOMATICO | MANUAL
    hora_inicio: datetime
    num_workers: int
    limite_configurado: Optional[int] = None
    estado: EstadoEjecucionBatch = EstadoEjecucionBatch.EN_EJECUCION
    cantidad_activos_total: int = 0
    cantidad_activos_procesados: int = 0
    cantidad_activos_pendientes: int = 0
    cantidad_fallidos: int = 0
    hora_fin: Optional[datetime] = None
    hora_corte: Optional[datetime] = None
    causa_interrupcion: Optional[str] = None
    id_usuario_disparo: Optional[int] = None
    id_usuario_interrupcion: Optional[int] = None
    id_ejecucion: Optional[int] = None

    @property
    def esta_en_ejecucion(self) -> bool:
        return self.estado == EstadoEjecucionBatch.EN_EJECUCION

    def completar(self, *, hora_fin: datetime) -> None:
        if not self.esta_en_ejecucion:
            raise FlowError(
                code="BATCH_NO_EN_EJECUCION",
                message=f"La ejecución {self.id_ejecucion} no está en ejecución; estado actual {self.estado.value}.",
            )
        self.estado = EstadoEjecucionBatch.COMPLETADO
        self.hora_fin = hora_fin
        self.cantidad_activos_pendientes = max(
            self.cantidad_activos_total - self.cantidad_activos_procesados, 0
        )

    def interrumpir(self, *, causa: str, hora_corte: datetime, id_usuario: Optional[int] = None) -> None:
        if not self.esta_en_ejecucion:
            raise FlowError(
                code="BATCH_NO_EN_EJECUCION",
                message=f"La ejecución {self.id_ejecucion} no está en ejecución; estado actual {self.estado.value}.",
            )
        self.estado = EstadoEjecucionBatch.INTERRUMPIDO
        self.causa_interrupcion = causa
        self.hora_corte = hora_corte
        self.hora_fin = hora_corte
        self.id_usuario_interrupcion = id_usuario
        self.cantidad_activos_pendientes = max(
            self.cantidad_activos_total - self.cantidad_activos_procesados, 0
        )
