"""Adaptador en segundo plano para correos de recuperación de RF-08."""
from __future__ import annotations

import logging

from fastapi import BackgroundTasks

from src.identity_access.domain.repositories.correo_recuperacion_port import (
    CorreoRecuperacionPort,
)
from src.identity_access.infrastructure.email_templates import (
    activation_email,
    recovery_email,
)
from src.identity_access.infrastructure.repositories.notificacion_repository import (
    SqlAlchemyNotificacionRepository,
)
from src.shared.database import SessionLocal
from src.shared.notificacion_service import NotificacionService

logger = logging.getLogger(__name__)

TIPO_SOLICITUD_RECUPERACION = 7
FLUJO_RECUPERACION = "recuperacion"
FLUJO_ACTIVACION = "activacion"


def procesar_correo_recuperacion_background(
    correo: str,
    nombre: str,
    token: str,
    id_usuario: int,
    flujo: str,
) -> None:
    """Despacha el correo con una sesión independiente de la petición."""
    db = None
    try:
        if flujo == FLUJO_ACTIVACION:
            asunto = "Activa tu cuenta en SGPMP"
            contenido = activation_email(nombre, token)
        else:
            asunto = "Restablece tu contraseña en SGPMP"
            contenido = recovery_email(nombre, token)

        db = SessionLocal()
        NotificacionService(
            port=SqlAlchemyNotificacionRepository(db),
            db=db,
        ).notificar(
            tipo_evento=TIPO_SOLICITUD_RECUPERACION,
            id_usuario=id_usuario,
            correo_destino=correo,
            asunto_email=asunto,
            contenido_html_email=contenido,
            aplicar_anti_spam_email=False,
        )
    except Exception:
        logger.exception(
            "No fue posible procesar en segundo plano el correo de %s "
            "del usuario %s.",
            flujo,
            id_usuario,
        )
    finally:
        if db is not None:
            db.close()


class CorreoRecuperacionBackgroundAdapter(CorreoRecuperacionPort):
    """Agenda los correos mediante ``BackgroundTasks`` de FastAPI."""

    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self._background_tasks = background_tasks

    def programar_recuperacion(
        self,
        correo: str,
        nombre: str,
        token: str,
        id_usuario: int,
    ) -> None:
        self._programar(correo, nombre, token, id_usuario, FLUJO_RECUPERACION)

    def programar_activacion(
        self,
        correo: str,
        nombre: str,
        token: str,
        id_usuario: int,
    ) -> None:
        self._programar(correo, nombre, token, id_usuario, FLUJO_ACTIVACION)

    def _programar(
        self,
        correo: str,
        nombre: str,
        token: str,
        id_usuario: int,
        flujo: str,
    ) -> None:
        self._background_tasks.add_task(
            procesar_correo_recuperacion_background,
            correo=correo,
            nombre=nombre,
            token=token,
            id_usuario=id_usuario,
            flujo=flujo,
        )
