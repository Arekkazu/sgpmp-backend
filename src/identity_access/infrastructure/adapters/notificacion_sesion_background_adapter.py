"""Adaptador en segundo plano para las notificaciones de inicio de sesión.

QA M01 2.2: bajo logins concurrentes, el endpoint dejaba de responder dentro
del timeout del frontend (>15-30s). La causa no era el hashing de contraseña
ni el pool de conexiones: ``LoginUseCase``/``SsoLoginUseCase`` llamaban
``NotificacionService.notificar()`` de forma síncrona *dentro* del request, y
esa llamada intenta ``send_email`` vía SMTP bloqueante (``smtplib.SMTP`` sin
``timeout``) con 3 reintentos y 5s de pausa entre cada uno — hasta 3 conexiones
SMTP potencialmente colgadas más ~10s de sleep, todo mientras el request
mantiene abierta su conexión de DB (tomada al inicio por
``database._conectar_con_reintentos``). Unos pocos logins simultáneos bastan
para saturar el pool de conexiones y el threadpool síncrono de FastAPI.

Mismo patrón que ``CorreoActivacionBackgroundAdapter``/
``CorreoRecuperacionBackgroundAdapter`` (RF-01/RF-08, INC-M01-21-041): agenda
la notificación con ``BackgroundTasks`` y una sesión de DB propia, para que la
respuesta HTTP no espere el despacho SMTP/FCM. Sin Port dedicado en
``domain/`` porque los use cases de sesión ya reciben ``notificacion_service``
sin tipo (duck typing) — esta clase es un reemplazo directo con el mismo
método ``notificar()``.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import BackgroundTasks

from src.identity_access.infrastructure.repositories.notificacion_repository import (
    SqlAlchemyNotificacionRepository,
)
from src.shared.database import SessionLocal
from src.shared.notificacion_service import NotificacionService

logger = logging.getLogger(__name__)


def _procesar_notificacion_sesion_background(
    tipo_evento: int,
    id_usuario: int,
    correo_destino: Optional[str],
) -> None:
    """Despacha la notificación con una sesión de DB independiente del request."""
    db = None
    try:
        db = SessionLocal()
        NotificacionService(
            port=SqlAlchemyNotificacionRepository(db),
            db=db,
        ).notificar(
            tipo_evento=tipo_evento,
            id_usuario=id_usuario,
            correo_destino=correo_destino,
        )
    except Exception:
        logger.exception(
            "No fue posible procesar en segundo plano la notificación de sesión "
            "tipo=%s del usuario %s.",
            tipo_evento,
            id_usuario,
        )
    finally:
        if db is not None:
            db.close()


class NotificacionSesionBackgroundAdapter:
    """Sustituto de ``NotificacionService`` que agenda ``notificar()`` en segundo plano.

    Se pasa donde antes se instanciaba ``NotificacionService(...)`` en los
    routers de sesión — mismo método público, sin cambios en los use cases.
    """

    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self._background_tasks = background_tasks

    def notificar(
        self,
        tipo_evento: int,
        id_usuario: int,
        correo_destino: Optional[str] = None,
    ) -> None:
        self._background_tasks.add_task(
            _procesar_notificacion_sesion_background,
            tipo_evento=tipo_evento,
            id_usuario=id_usuario,
            correo_destino=correo_destino,
        )
