# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: entrega del outbox a M06           |
"""Caso de uso: entregar a M06 los eventos del outbox de provisiones (RF-79).

Corre en segundo plano cada pocos segundos (CA-1: ≤ 5 s desde la persistencia).
Entrega en orden de creación; si un evento de un ciclo falla, los siguientes de
ese mismo ciclo esperan, para que M06 los reciba en orden cronológico (CA-13).

- Éxito (ACK de recepción): ENTREGADO y ``PROVISION_INCREMENTAL_ENTREGADA`` en
  RF-80; un CONSOLIDADO marca además la fecha de entrega del reporte.
- Fallo: reintento a los 5/15/30/60 s. Al quinto fallo, estado
  PROVISION_PENDIENTE, eventos ``PROVISION_INCREMENTAL_FALLIDA`` (con los 5
  timestamps) y ``PROVISION_PENDIENTE`` en RF-80 y alerta al administrador (E1,
  CA-8, CA-9). El evento no se pierde: se sigue intentando cada 30 s (E7 d).
- Más de 10.000 eventos sin entregar: alerta CRÍTICA al administrador (E7 e).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.supplies.domain.entities.evento_provision_m06 import EventoProvisionM06, ModalidadProvision
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.notificacion_suministros_port import NotificacionSuministrosPort
from src.supplies.domain.repositories.outbox_provision_m06_repository import OutboxProvisionM06Repository
from src.supplies.domain.repositories.provision_m06_port import ProvisionM06Port
from src.supplies.domain.repositories.provision_nic41_repository import ProvisionNic41Repository

logger = logging.getLogger(__name__)

_LOTE = 100
_UMBRAL_ALERTA_CRITICA = 10_000
# Recurso provision_nic41 (56), acción E: quien opera la provisión recibe las alertas.
_RECURSO_PROVISION, _ACCION_EJECUTAR = 56, 5
_ultima_alerta_critica: Optional[datetime] = None


class DespacharProvisionesM06UseCase:
    def __init__(
        self,
        db: Session,
        outbox_repo: OutboxProvisionM06Repository,
        provision_repo: ProvisionNic41Repository,
        auditoria_port: AuditoriaSuministroPort,
        m06_port: ProvisionM06Port,
        notificador: NotificacionSuministrosPort,
        id_usuario_sistema: int,
    ) -> None:
        self.db = db
        self.outbox_repo = outbox_repo
        self.provision_repo = provision_repo
        self.auditoria_port = auditoria_port
        self.m06_port = m06_port
        self.notificador = notificador
        self.id_usuario_sistema = id_usuario_sistema

    def ejecutar(self) -> int:
        ahora = datetime.now(timezone.utc)
        entregados = 0
        ciclos_detenidos: set[Optional[int]] = set()
        for evento in self.outbox_repo.listar_listos(ahora, _LOTE):
            if evento.id_gestion_fases in ciclos_detenidos:
                continue
            if self._entregar(evento):
                entregados += 1
            else:
                ciclos_detenidos.add(evento.id_gestion_fases)
        self._alertar_si_desborda(ahora)
        return entregados

    def _entregar(self, evento: EventoProvisionM06) -> bool:
        try:
            self.m06_port.entregar(evento)
        except Exception as exc:
            logger.warning("Entrega a M06 del evento %s falló: %s", evento.id_evento_provision, exc)
            self._registrar_fallo(evento, exc)
            return False
        ahora = datetime.now(timezone.utc)
        evento.marcar_entregado(ahora)
        try:
            self.outbox_repo.actualizar(evento)
            if evento.modalidad == ModalidadProvision.CONSOLIDADO.value and evento.id_provision:
                self.provision_repo.marcar_entregado(evento.id_provision, ahora)
            self._auditar(evento, "PROVISION_INCREMENTAL_ENTREGADA", "EXITOSO")
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("No se pudo marcar entregado el evento %s.", evento.id_evento_provision)
        return True

    def _registrar_fallo(self, evento: EventoProvisionM06, exc: Exception) -> None:
        alertar = evento.registrar_fallo(datetime.now(timezone.utc))
        try:
            self.outbox_repo.actualizar(evento)
            if alertar:
                self._auditar(evento, "PROVISION_INCREMENTAL_FALLIDA", "FALLIDO", causa=str(exc))
                self._auditar(evento, "PROVISION_PENDIENTE", "FALLIDO", causa=str(exc))
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("No se pudo registrar el fallo de entrega del evento %s.", evento.id_evento_provision)
            return
        if alertar:
            self.notificador.a_permiso(
                _RECURSO_PROVISION, _ACCION_EJECUTAR, "PROVISION_M06_PENDIENTE",
                f"La provisión de costos {evento.id_evento_provision} (activo {evento.id_activo_biologico}) no se "
                f"pudo entregar a M06 tras {evento.numero_intentos} intentos. Queda en estado PROVISION_PENDIENTE "
                "y se seguirá reintentando.",
                {"id_evento_provision": str(evento.id_evento_provision), "numero_reintentos": evento.numero_intentos},
            )

    def _auditar(self, evento: EventoProvisionM06, tipo: str, resultado: str, causa: Optional[str] = None) -> None:
        self.auditoria_port.registrar(
            EventoAuditoriaSuministro(
                entidad_afectada="outbox_provisiones_m06",
                tipo_operacion=tipo,
                id_usuario=self.id_usuario_sistema,
                resultado=resultado,
                id_activo_biologico=evento.id_activo_biologico,
                id_gestion_fases=evento.id_gestion_fases,
                costo_afectado=evento.costo_registro,
                detalle_causa=(
                    f"id_evento_provision={evento.id_evento_provision}; modalidad={evento.modalidad}"
                    + (f"; id_registro_suministro={evento.id_registro_suministro}" if evento.id_registro_suministro else "")
                    + (f"; causa={causa}" if causa else "")
                )[:1000],
                numero_reintentos=evento.numero_intentos if resultado == "FALLIDO" else None,
                fecha_intentos=evento.intentos_recientes if resultado == "FALLIDO" else [],
            )
        )

    def _alertar_si_desborda(self, ahora: datetime) -> None:
        global _ultima_alerta_critica
        if _ultima_alerta_critica is not None and ahora - _ultima_alerta_critica < timedelta(hours=1):
            return
        pendientes = self.outbox_repo.contar_pendientes()
        if pendientes <= _UMBRAL_ALERTA_CRITICA:
            return
        _ultima_alerta_critica = ahora
        self.notificador.a_permiso(
            _RECURSO_PROVISION, _ACCION_EJECUTAR, "PROVISION_M06_PENDIENTE",
            f"CRÍTICO: la cola de provisión hacia M06 tiene {pendientes} eventos pendientes de entrega. "
            "Intervención manual puede ser necesaria.",
            {"pendientes": pendientes},
        )
