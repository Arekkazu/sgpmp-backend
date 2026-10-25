# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: evento de provisión hacia M06      |
"""Entidad ``EventoProvisionM06`` (RF-79 — provisión de costos hacia M06).

Python puro. Un evento INCREMENTAL (cada movimiento del ledger de RF-78) o
CONSOLIDADO (reporte NIC-41 al cierre del ciclo) que espera en el outbox hasta
que M06 confirma la recepción (ACK, R9).

Reintentos (Fase 1 c / E1): backoff 0 s, 5 s, 15 s, 30 s, 60 s — cinco
intentos. Tras el quinto fallo el evento queda en ``PROVISION_PENDIENTE`` y se
alerta al administrador una sola vez; el evento no se pierde: se sigue
intentando cada 30 s (E7 d) hasta que M06 lo reciba.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

SCHEMA_VERSION = "1.0"
MAX_INTENTOS = 5
_ESPERA_TRAS_INTENTO = (timedelta(seconds=5), timedelta(seconds=15), timedelta(seconds=30), timedelta(seconds=60))
_ESPERA_RECUPERACION = timedelta(seconds=30)


class EstadoEventoProvision(str, Enum):
    PENDIENTE = "PENDIENTE"
    ENTREGADO = "ENTREGADO"
    PROVISION_PENDIENTE = "PROVISION_PENDIENTE"


class ModalidadProvision(str, Enum):
    INCREMENTAL = "INCREMENTAL"
    CONSOLIDADO = "CONSOLIDADO"


@dataclass(eq=False)
class EventoProvisionM06:
    modalidad: str
    id_activo_biologico: int
    contenido: dict
    id_evento_provision: UUID = field(default_factory=uuid4)
    schema_version: str = SCHEMA_VERSION
    id_gestion_fases: Optional[int] = None
    id_registro_suministro: Optional[UUID] = None
    id_provision: Optional[int] = None
    costo_registro: Optional[Decimal] = None
    estado: str = EstadoEventoProvision.PENDIENTE.value
    numero_intentos: int = 0
    fecha_intentos: list[datetime] = field(default_factory=list)
    fecha_proximo_intento: Optional[datetime] = None
    es_alerta_enviada: bool = False
    fecha_creacion: Optional[datetime] = None
    fecha_entrega: Optional[datetime] = None

    @classmethod
    def incremental(
        cls,
        *,
        id_activo_biologico: int,
        id_ciclo_productivo: int,
        id_gestion_fases: int,
        id_registro_suministro: UUID,
        tipo_suministro: str,
        tipo_operacion: str,
        costo_registro: Decimal,
        acumulado_total_ciclo: Decimal,
        acumulado_por_categoria: dict[str, Decimal],
        ahora: datetime,
    ) -> "EventoProvisionM06":
        """Evento de Fase 1 a: el acumulado actualizado tras un movimiento del ledger."""
        evento = cls(
            modalidad=ModalidadProvision.INCREMENTAL.value,
            id_activo_biologico=id_activo_biologico,
            id_gestion_fases=id_gestion_fases,
            id_registro_suministro=id_registro_suministro,
            costo_registro=costo_registro,
            contenido={},
            fecha_proximo_intento=ahora,
        )
        evento.contenido = {
            "id_evento_provision": str(evento.id_evento_provision),
            "schema_version": SCHEMA_VERSION,
            "modalidad": ModalidadProvision.INCREMENTAL.value,
            "id_activo": id_activo_biologico,
            "id_ciclo": id_ciclo_productivo,
            "id_gestion_fases": id_gestion_fases,
            "id_registro_suministro": str(id_registro_suministro),
            "id_tipo_suministro": tipo_suministro,
            "tipo_operacion": tipo_operacion,
            "costo_registro": str(costo_registro),
            "acumulado_total_ciclo": str(acumulado_total_ciclo),
            "acumulado_por_categoria": {k: str(v) for k, v in acumulado_por_categoria.items()},
            "timestamp": ahora.isoformat(),
        }
        return evento

    @classmethod
    def consolidado(cls, *, contenido: dict, id_activo_biologico: int, id_gestion_fases: int,
                    id_provision: int, ahora: datetime) -> "EventoProvisionM06":
        """Evento de Fase 2 h: el reporte consolidado NIC-41 ya persistido."""
        evento = cls(
            modalidad=ModalidadProvision.CONSOLIDADO.value,
            id_activo_biologico=id_activo_biologico,
            id_gestion_fases=id_gestion_fases,
            id_provision=id_provision,
            contenido={},
            fecha_proximo_intento=ahora,
        )
        evento.contenido = {
            **contenido,
            "id_evento_provision": str(evento.id_evento_provision),
            "schema_version": SCHEMA_VERSION,
            "modalidad": ModalidadProvision.CONSOLIDADO.value,
        }
        return evento

    def marcar_entregado(self, ahora: datetime) -> None:
        self.numero_intentos += 1
        self.fecha_intentos.append(ahora)
        self.estado = EstadoEventoProvision.ENTREGADO.value
        self.fecha_entrega = ahora

    def registrar_fallo(self, ahora: datetime) -> bool:
        """Registra un intento fallido. Devuelve ``True`` si hay que alertar ahora (5.º fallo)."""
        self.numero_intentos += 1
        self.fecha_intentos.append(ahora)
        if self.numero_intentos < MAX_INTENTOS:
            self.fecha_proximo_intento = ahora + _ESPERA_TRAS_INTENTO[self.numero_intentos - 1]
            return False
        self.estado = EstadoEventoProvision.PROVISION_PENDIENTE.value
        self.fecha_proximo_intento = ahora + _ESPERA_RECUPERACION
        alertar = not self.es_alerta_enviada
        self.es_alerta_enviada = True
        return alertar

    @property
    def intentos_recientes(self) -> list[datetime]:
        """Timestamps de los últimos 5 intentos (RF-80 CA-8: máximo 5 elementos)."""
        return self.fecha_intentos[-MAX_INTENTOS:]
