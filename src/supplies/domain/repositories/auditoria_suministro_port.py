# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-80: emisión, reintentos y sus fechas   |
# | 2026-11-07 | Leandro | INC-M05-272-G25 RF-77: admitir contexto estructurado del reporte o archivo auditado. |
# | 2026-11-08 | Leandro | INC-M05-278-G39 RF-80: emitir UUID estable y documentar datos ausentes en eventos incompletos. |
"""Puerto de auditoría de eventos de negocio RF-78/RF-79 (CU-05).

Puerto angosto de escritura (patrón ``NotificacionMedicamentoPort``): el use
case construye un ``EventoAuditoriaSuministro`` y lo entrega tal cual; la
implementación mapea a una fila de ``modulo5.auditorias_suministros``.
``hash_integridad`` lo calcula el trigger de BD (``trg_audit_hash``), no se
recibe aquí. Los 8 valores de ``tipo_operacion`` de negocio se agregaron al
enum PG en el Gap 4 de ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4


@dataclass(frozen=True)
class EventoAuditoriaSuministro:
    """Evento de negocio de RF-78/RF-79 a registrar en ``auditorias_suministros``."""

    entidad_afectada: str
    tipo_operacion: str
    id_usuario: int
    resultado: str
    id_activo_biologico: Optional[int] = None
    id_ciclo_productivo: Optional[int] = None
    id_gestion_fases: Optional[int] = None
    costo_afectado: Optional[Decimal] = None
    origen_precio: Optional[str] = None
    detalle_causa: Optional[str] = None
    numero_reintentos: Optional[int] = None
    registro_incompleto: bool = False
    fecha_intentos: list[datetime] = field(default_factory=list)
    fecha_emision: Optional[datetime] = None
    datos_nuevos: Optional[dict] = None
    id_evento_m05: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.registro_incompleto:
            return
        faltantes = []
        if self.id_activo_biologico is None:
            faltantes.append("activo biológico")
        if self.id_ciclo_productivo is None:
            faltantes.append("ciclo productivo")
        if self.tipo_operacion in {
            "SUMINISTRO_REGISTRADO", "SUMINISTRO_CORREGIDO", "ACUMULADO_ACTUALIZADO",
            "CICLO_CONSOLIDADO", "REPORTE_COSTOS_GENERADO",
        } and self.costo_afectado is None:
            faltantes.append("costo afectado")
        detalle = (self.detalle_causa or "").strip()
        if faltantes:
            campos = "Campos faltantes: " + ", ".join(faltantes) + "."
            if campos not in detalle:
                detalle = f"{detalle} {campos}".strip()
        elif not detalle:
            detalle = (
                "Campos faltantes: detalle de la causa. "
                "El emisor no identificó otros datos ausentes."
            )
        object.__setattr__(self, "detalle_causa", detalle)


class AuditoriaSuministroPort(ABC):
    """Contrato de registro de eventos de auditoría de RF-78/RF-79."""

    @abstractmethod
    def registrar(self, evento: EventoAuditoriaSuministro) -> None:
        """Persiste el evento de auditoría. No hace ``commit``."""
        raise NotImplementedError
