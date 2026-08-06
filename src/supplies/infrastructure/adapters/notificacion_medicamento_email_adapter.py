"""Adaptador de notificaciones por correo del período de retiro (RF-76 pasos 9 y 13).

Resuelve destinatarios con SQL directo (mismo patrón que
``evento_sanitario_m02_adapter.py``: no hay modelo ORM de ``usuarios`` en este
módulo). El Productor es el dueño registrado del activo
(``modulo2.activos_biologicos.id_usuario``, siempre presente); el Veterinario
es opcional (``id_usuario_veterinario`` del registro de medicamento, solo se
conoce cuando quien registró tenía ese rol).

Envío *best-effort*: cada intento va en su propio ``try/except`` con log en
fallo, nunca propaga. El dato de negocio (medicamento o reversión de estado)
ya quedó persistido antes de notificar; un fallo de SMTP no debe convertir una
operación exitosa en un error para el cliente.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.email import send_email
from src.supplies.domain.repositories.notificacion_medicamento_port import NotificacionMedicamentoPort
from src.supplies.infrastructure.email_templates import fin_retiro_email, inicio_retiro_email

logger = logging.getLogger(__name__)

_SQL_PRODUCTOR = text(
    "SELECT u.nombre, u.apellidos, u.correo_electronico "
    "FROM modulo2.activos_biologicos ab "
    "JOIN modulo1.usuarios u ON u.id_usuario = ab.id_usuario "
    "WHERE ab.id_activo_biologico = :id_activo"
)

_SQL_USUARIO = text(
    "SELECT nombre, apellidos, correo_electronico FROM modulo1.usuarios WHERE id_usuario = :id_usuario"
)


class NotificacionMedicamentoEmailAdapter(NotificacionMedicamentoPort):
    """Envía las notificaciones de RF-76 por correo electrónico."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def notificar_inicio_retiro(
        self,
        id_activo: int,
        id_usuario_veterinario: Optional[int],
        nombre_medicamento: str,
        fecha_fin_retiro: date,
    ) -> None:
        productor = self._productor_de_activo(id_activo)
        if productor is not None:
            self._enviar(
                productor[1],
                "Inicio de período de retiro por aplicación de medicamento",
                inicio_retiro_email(productor[0], nombre_medicamento, fecha_fin_retiro),
            )

        if id_usuario_veterinario is not None:
            veterinario = self._usuario(id_usuario_veterinario)
            if veterinario is not None:
                self._enviar(
                    veterinario[1],
                    "Inicio de período de retiro por aplicación de medicamento",
                    inicio_retiro_email(veterinario[0], nombre_medicamento, fecha_fin_retiro),
                )

    def notificar_fin_retiro(self, id_activo: int, fecha_fin_retiro: date) -> None:
        productor = self._productor_de_activo(id_activo)
        if productor is not None:
            self._enviar(
                productor[1],
                "Fin de período de retiro",
                fin_retiro_email(productor[0], fecha_fin_retiro),
            )

    # ── Resolución de destinatarios ──────────────────────────────────────────

    def _productor_de_activo(self, id_activo: int) -> Optional[tuple[str, str]]:
        row = self.db.execute(_SQL_PRODUCTOR, {"id_activo": id_activo}).fetchone()
        if row is None or not row.correo_electronico:
            return None
        return (f"{row.nombre} {row.apellidos}".strip(), row.correo_electronico)

    def _usuario(self, id_usuario: int) -> Optional[tuple[str, str]]:
        row = self.db.execute(_SQL_USUARIO, {"id_usuario": id_usuario}).fetchone()
        if row is None or not row.correo_electronico:
            return None
        return (f"{row.nombre} {row.apellidos}".strip(), row.correo_electronico)

    # ── Envío best-effort ────────────────────────────────────────────────────

    @staticmethod
    def _enviar(correo: str, asunto: str, html: str) -> None:
        try:
            send_email(to=correo, subject=asunto, html_body=html)
        except Exception as exc:  # best-effort: nunca interrumpe el flujo de negocio
            logger.warning("No se pudo enviar la notificación de retiro a %s: %s", correo, exc)
