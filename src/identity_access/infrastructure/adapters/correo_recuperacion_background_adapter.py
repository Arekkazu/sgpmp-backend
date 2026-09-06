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
from src.identity_access.infrastructure.repositories.usuario_repository import (
    SqlAlchemyUsuarioRepository,
)
from src.shared.database import SessionLocal
from src.shared.notificacion_service import NotificacionService

logger = logging.getLogger(__name__)

TIPO_SOLICITUD_RECUPERACION = 7
FLUJO_RECUPERACION = "recuperacion"
FLUJO_ACTIVACION = "activacion"

# Las alertas operativas se entregan a quienes pueden consultar la auditoría.
# Así el destinatario se resuelve mediante RBAC y no con un id de rol fijo.
RECURSO_AUDITORIA = 6
ACCION_LEER = 2
ID_CANAL_INTERNO = 2

_MENSAJE_ALERTA_SMTP = (
    "Fallo crítico del servicio SMTP: no se pudo enviar un correo de "
    "recuperación de contraseña después de agotar los reintentos."
)


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
        notificaciones_repo = SqlAlchemyNotificacionRepository(db)
        email_enviado = NotificacionService(
            port=notificaciones_repo,
            db=db,
        ).notificar(
            tipo_evento=TIPO_SOLICITUD_RECUPERACION,
            id_usuario=id_usuario,
            correo_destino=correo,
            asunto_email=asunto,
            contenido_html_email=contenido,
            aplicar_anti_spam_email=False,
        )
        if email_enviado is False:
            _alertar_administradores_fallo_smtp(
                db=db,
                notificaciones_repo=notificaciones_repo,
                id_usuario=id_usuario,
                flujo=flujo,
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


def _alertar_administradores_fallo_smtp(
    db,
    notificaciones_repo: SqlAlchemyNotificacionRepository,
    id_usuario: int,
    flujo: str,
) -> None:
    """Crea una notificación interna para los responsables de auditoría.

    La alerta es best-effort: un segundo fallo técnico aquí no debe interrumpir
    el procesamiento en segundo plano, que ya terminó de todas formas. Usa la
    misma sesión independiente del correo, para no reabrir la del request
    (INC-M01-14-044, movida a este adaptador por INC-M01-21-041 al pasar el
    envío a segundo plano).
    """
    try:
        destinatarios = SqlAlchemyUsuarioRepository(db).listar_ids_con_permiso(
            id_recurso=RECURSO_AUDITORIA,
            id_accion=ACCION_LEER,
        )
        if not destinatarios:
            logger.error(
                "No se creó la alerta interna de fallo SMTP: sin destinatarios RBAC"
            )
            return

        id_evento = notificaciones_repo.buscar_ultimo_evento_id(
            id_usuario=id_usuario,
            tipo_evento=TIPO_SOLICITUD_RECUPERACION,
        )
        if id_evento is None:
            logger.error(
                "No se creó la alerta interna de fallo SMTP: evento de recuperación ausente"
            )
            return

        mensaje = f"{_MENSAJE_ALERTA_SMTP} Usuario relacionado: {id_usuario}. Flujo: {flujo}."
        for id_destinatario in destinatarios:
            notificaciones_repo.registrar(
                id_evento=id_evento,
                id_usuario=id_destinatario,
                id_canal=ID_CANAL_INTERNO,
                mensaje=mensaje,
                estado="enviado",
            )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "No se pudo persistir la alerta interna por fallo SMTP para usuario=%s",
            id_usuario,
        )


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
