"""Adaptador asíncrono para el correo de activación de RF-01."""
from __future__ import annotations

import logging

from fastapi import BackgroundTasks

from src.identity_access.domain.repositories.correo_activacion_port import (
    CorreoActivacionPort,
)
from src.identity_access.infrastructure.email_templates import activation_email
from src.identity_access.infrastructure.repositories.notificacion_repository import (
    SqlAlchemyNotificacionRepository,
)
from src.shared.database import SessionLocal
from src.shared.notificacion_service import NotificacionService

logger = logging.getLogger(__name__)

TIPO_REGISTRO_USUARIO = 1


def procesar_correo_activacion_background(
    correo: str,
    nombre: str,
    token: str,
    id_usuario: int,
) -> None:
    """Procesa la notificación con una sesión independiente del request."""
    db = None
    try:
        db = SessionLocal()
        NotificacionService(
            port=SqlAlchemyNotificacionRepository(db),
            db=db,
        ).notificar(
            tipo_evento=TIPO_REGISTRO_USUARIO,
            id_usuario=id_usuario,
            correo_destino=correo,
            asunto_email="Activa tu cuenta en SGPMP",
            contenido_html_email=activation_email(nombre, token),
        )
    except Exception:
        logger.exception(
            "No fue posible procesar en segundo plano el correo de activación "
            "del usuario %s.",
            id_usuario,
        )
    finally:
        if db is not None:
            db.close()


class CorreoActivacionBackgroundAdapter(CorreoActivacionPort):
    """Agenda la notificación centralizada mediante ``BackgroundTasks``."""

    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self._background_tasks = background_tasks

    def programar_envio(
        self,
        correo: str,
        nombre: str,
        token: str,
        id_usuario: int,
    ) -> None:
        self._background_tasks.add_task(
            procesar_correo_activacion_background,
            correo=correo,
            nombre=nombre,
            token=token,
            id_usuario=id_usuario,
        )
