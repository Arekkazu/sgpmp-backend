# | Fecha      | Nombre   | Que se hizo                                                         |
# |------------|----------|---------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: entrega por push con reintentos, correo de críticas y purga |
# | 2026-11-18 | Arekkazu | M08 RF-105 R6: respeta las preferencias de canal del usuario |
"""Entrega en segundo plano de las notificaciones (RF-105 Fase 3) y su retención (restricción 3).

La fila interna es la fuente de verdad: ya está en la bandeja apenas se registra. Este proceso
corre cada pocos segundos y toma las internas CRÍTICA o ADVERTENCIA cuyo push falta:

- Push a todos los dispositivos del usuario. Sin dispositivos no hay a quién enviarlo: queda
  entregada solo en la bandeja.
- Si el push falla: reintentos a 1, 5 y 15 minutos; después queda en la bandeja y el fallo solo en
  el log técnico, sin error visible (CA-7).
- CRÍTICA: además el correo, en la primera entrega (lo que ya envió en el momento quien registró
  —M01, M03— no se vuelve a enviar por correo).

Así llegan por push los avisos que M05, M06 y M07 solo dejaban en la bandeja, sin tocar esos módulos.

R6: si el usuario apagó el push o el correo de ese nivel en sus preferencias, no se envía por ese canal; la
notificación ya está en su bandeja (que no se puede apagar).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.notificacion_repository import EntregaPendiente, NotificacionRepository
from src.identity_access.domain.value_objects.nivel_notificacion import CRITICA, EMAIL, PUSH, titulo_push
from src.shared.email import send_email
from src.shared.firebase import send_push
from src.shared.plantilla_correo import renderizar_correo

logger = logging.getLogger(__name__)

_ID_CANAL_EMAIL = 1
_INTENTOS_MAX = 4
# Espera antes del siguiente intento, según cuántos van (restricción 5: 1, 5 y 15 minutos).
_ESPERA_MINUTOS = {1: 1, 2: 5, 3: 15}
_RETENCION_INFORMATIVAS = timedelta(days=30)


class EntregarNotificacionesUseCase:

    def __init__(
        self,
        db: Session,
        notificaciones_repo: NotificacionRepository,
        enviar_push: Callable[..., bool] = send_push,
        enviar_correo: Callable[..., None] = send_email,
    ) -> None:
        self.db = db
        self.repo = notificaciones_repo
        self.enviar_push = enviar_push
        self.enviar_correo = enviar_correo

    def execute(self, ahora: Optional[datetime] = None, limite: int = 50) -> int:
        ahora = ahora or datetime.now(timezone.utc)
        correos: list[EntregaPendiente] = []
        try:
            pendientes = self.repo.pendientes_de_entrega(limite)
            for pendiente in pendientes:
                self._push(pendiente, ahora)
                if pendiente.nivel == CRITICA and pendiente.intentos_push == 0:
                    correos.append(pendiente)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        # Correos después del commit: si el SMTP falla, los intentos de push ya quedaron guardados.
        for pendiente in correos:
            self._correo(pendiente)
        return len(pendientes)

    def _push(self, pendiente: EntregaPendiente, ahora: datetime) -> None:
        habilitado = self.repo.canal_habilitado(pendiente.id_usuario, pendiente.nivel, PUSH)
        tokens = self.repo.buscar_fcm_tokens(pendiente.id_usuario) if habilitado else []
        datos = {**pendiente.contexto, "id_notificacion": pendiente.id_notificacion, "nivel": pendiente.nivel}
        titulo = titulo_push(pendiente.nivel, pendiente.modulo)
        # Se intenta en todos los dispositivos; basta con que uno lo reciba.
        resultados = [self.enviar_push(token=t, titulo=titulo, cuerpo=pendiente.mensaje, datos=datos) for t in tokens]
        entregada = not tokens or any(resultados)
        intentos = pendiente.intentos_push + 1
        proximo = None
        if not entregada and intentos < _INTENTOS_MAX:
            proximo = ahora + timedelta(minutes=_ESPERA_MINUTOS[intentos])
        elif not entregada:
            logger.warning("RF-105: push de la notificación %s sin entregar tras %s intentos; queda en la bandeja.",
                           pendiente.id_notificacion, intentos)
        self.repo.registrar_intento_push(pendiente.id_notificacion, entregada, proximo)

    def _correo(self, pendiente: EntregaPendiente) -> None:
        if not self.repo.canal_habilitado(pendiente.id_usuario, pendiente.nivel, EMAIL):
            return
        correo = self.repo.buscar_correo_usuario(pendiente.id_usuario)
        if not correo:
            return
        titulo = titulo_push(pendiente.nivel, pendiente.modulo)
        try:
            id_correo = self.repo.registrar(
                id_evento=pendiente.id_evento, id_usuario=pendiente.id_usuario, id_canal=_ID_CANAL_EMAIL,
                mensaje=pendiente.mensaje, estado="en_cola", nivel=pendiente.nivel,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("RF-105: no se pudo registrar el correo de la notificación %s", pendiente.id_notificacion)
            return
        enviado = False
        try:
            self.enviar_correo(
                to=correo, subject=titulo, intentos=1,
                html_body=renderizar_correo(titulo=titulo, parrafos=[pendiente.mensaje], evento=titulo,
                                            tono="atencion"),
            )
            enviado = True
        except Exception:
            logger.exception("RF-105: falló el correo de la notificación %s", pendiente.id_notificacion)
        try:
            self.repo.actualizar_estado(id_correo, "enviado" if enviado else "fallido")
            self.db.commit()
        except Exception:
            self.db.rollback()


class PurgarNotificacionesUseCase:
    """Borra las INFORMATIVAS leídas o descartadas de más de 30 días (RF-105 restricción 3, CA-6)."""

    def __init__(self, db: Session, notificaciones_repo: NotificacionRepository) -> None:
        self.db = db
        self.repo = notificaciones_repo

    def execute(self, ahora: Optional[datetime] = None) -> int:
        ahora = ahora or datetime.now(timezone.utc)
        try:
            borradas = self.repo.purgar_informativas(ahora - _RETENCION_INFORMATIVAS)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return borradas
