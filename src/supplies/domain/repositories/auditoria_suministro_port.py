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
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


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


class AuditoriaSuministroPort(ABC):
    """Contrato de registro de eventos de auditoría de RF-78/RF-79."""

    @abstractmethod
    def registrar(self, evento: EventoAuditoriaSuministro) -> None:
        """Persiste el evento de auditoría. No hace ``commit``."""
        raise NotImplementedError
