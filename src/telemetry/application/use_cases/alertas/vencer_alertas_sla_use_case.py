# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-31 RF-57: tarea periódica de SLA vencido → VENCIDA, incumplimiento y escalamiento (E10) |
"""Caso de uso: vencer alertas sin atender por SLA (RF-57 E10, CA-12, Restricción 12).

Una alerta operativa ACTIVA que supera su ``fecha_vencimiento`` (5 min CRITICO,
30 min MODERADO, 2 h LEVE desde su generación) pasa a VENCIDA. Se registra el
incumplimiento en la bitácora RF-63 y, para CRITICO y MODERADO, el escalamiento
al Veterinario o al Administrador. El envío de la notificación de escalamiento
es de DEV-32 (canal de correo de RF-14).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.domain.entities.alerta import Alerta, SeveridadAlerta
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
    EntidadAfectadaTipo,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository

logger = logging.getLogger(__name__)

# Restricción 12: LEVE no escala, solo registra el incumplimiento.
_SEVERIDADES_QUE_ESCALAN = {SeveridadAlerta.CRITICO.value, SeveridadAlerta.MODERADO.value}
DESTINATARIOS_ESCALAMIENTO = ("Veterinario", "Administrador")


class VencerAlertasSlaUseCase:

    def __init__(self, db: Session, alerta_repo: AlertaRepository, auditoria_repo: BitacoraAuditoriaIotRepository) -> None:
        self.db = db
        self.alerta_repo = alerta_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, ahora: Optional[datetime] = None) -> int:
        """Devuelve cuántas alertas pasaron a VENCIDA."""
        ahora = ahora or datetime.now(timezone.utc)
        try:
            vencidas = self.alerta_repo.vencer_activas_con_sla_cumplido(ahora)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # Auditoría después del commit: si falla, la alerta ya quedó VENCIDA (best-effort, RF-63).
        auditoria = RegistrarEventoAuditoriaIotUseCase(self.db, self.auditoria_repo)
        for alerta in vencidas:
            self._auditar(auditoria, alerta, ahora)
        return len(vencidas)

    @staticmethod
    def _auditar(auditoria: RegistrarEventoAuditoriaIotUseCase, alerta: Alerta, ahora: datetime) -> None:
        critica = alerta.severidad == SeveridadAlerta.CRITICO.value
        detalle = {
            "severidad": alerta.severidad,
            "tipo_alerta": alerta.tipo_alerta,
            "id_infraestructura": alerta.id_infraestructura,
            "fecha_generacion": alerta.fecha_generacion.isoformat() if alerta.fecha_generacion else None,
            "fecha_vencimiento": alerta.fecha_vencimiento.isoformat() if alerta.fecha_vencimiento else None,
            "fecha_deteccion": ahora.isoformat(),
        }
        auditoria.execute(
            tipo_evento="SLA_ALERTA_INCUMPLIDO",
            resultado=TipoResultado.ADVERTENCIA,
            componente_origen=ComponenteOrigen.RF57,
            severidad_log=SeveridadLog.CRITICAL if critica else SeveridadLog.WARNING,
            descripcion=f"Alerta {alerta.severidad} sin atender dentro del SLA: pasa a VENCIDA.",
            entidad_afectada_tipo=EntidadAfectadaTipo.ALERTA,
            entidad_afectada_id=str(alerta.id_alerta),
            accion_detallada=detalle,
        )
        if alerta.severidad in _SEVERIDADES_QUE_ESCALAN:
            auditoria.execute(
                tipo_evento="ESCALAMIENTO_ALERTA_SLA",
                resultado=TipoResultado.EXITOSO,
                componente_origen=ComponenteOrigen.RF57,
                severidad_log=SeveridadLog.CRITICAL if critica else SeveridadLog.WARNING,
                descripcion=f"Alerta {alerta.severidad} vencida escalada a {' o '.join(DESTINATARIOS_ESCALAMIENTO)}.",
                entidad_afectada_tipo=EntidadAfectadaTipo.ALERTA,
                entidad_afectada_id=str(alerta.id_alerta),
                accion_detallada={**detalle, "destinatarios": list(DESTINATARIOS_ESCALAMIENTO)},
            )
