# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
"""Aviso por correo de RF-73 E8 (DEV-37), con el canal de RF-14 como los avisos de DEV-48.

Destinatarios por permiso, no por ``id_rol``: quien administra la bitácora de M04,
es decir, quien puede exportarla (recurso 46, acción E). Desde DB-08 el
Veterinario también puede leerla (R), pero la alerta es para el Administrador.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.prediction.domain.repositories.aviso_auditoria_m04_port import AvisoAuditoriaM04Port
from src.prediction.infrastructure.adapters.aviso_version_modelo_email_adapter import (
    RECURSO_AUDITORIA_M04,
    AvisoVersionModeloEmailAdapter,
)
from src.prediction.infrastructure.email_templates import fallback_auditoria_activado_email

ACCION_EJECUTAR = 5


class AvisoAuditoriaM04EmailAdapter(AvisoAuditoriaM04Port):
    def __init__(self, db: Session) -> None:
        # Reusa la resolución de destinatarios (como_sistema, sin el usuario de
        # servicio) y el envío best-effort de los avisos de versiones.
        self._correo = AvisoVersionModeloEmailAdapter(db)

    def avisar_fallback_activado(self, resumen: dict) -> None:
        for nombre, correo in self._correo._destinatarios(RECURSO_AUDITORIA_M04, ACCION_EJECUTAR):
            self._correo._enviar(
                correo,
                "Alerta crítica: la bitácora de Predicción usó el respaldo local",
                fallback_auditoria_activado_email(nombre, resumen),
            )
