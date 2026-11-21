# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: atender y descartar comparten la búsqueda de la propia |
# | 2026-11-21 | destroyerban | INC-M08-383-G014 RF-105: notificación ajena → 403 con el mensaje del RF |
"""Casos de uso del ciclo de vida de una notificación interna propia (RF-14, RF-105).

NUEVA → LEÍDA al abrirla; ATENDIDA con la acción documentada; DESCARTADA solo si no es crítica. Una
notificación ajena responde 403 con el mensaje de RF-105 restricción 4 / CU03 FA3 y una inexistente 404;
en ninguno de los dos casos cambia nada (además, la política RLS de UPDATE solo deja tocar las propias).
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.notificacion import Notificacion
from src.identity_access.domain.repositories.notificacion_repository import (
    NotificacionRepository,
)
from src.shared.errors import AuthorizationError, NotFoundError


class MarcarNotificacionLeidaUseCase:
    """Actualiza la lectura sin permitir acceso a notificaciones ajenas."""

    def __init__(self, notificaciones_repo: NotificacionRepository, db: Session):
        self.notificaciones_repo = notificaciones_repo
        self.db = db

    def execute(
        self,
        id_notificacion: int,
        id_usuario: int,
    ) -> Notificacion:
        return self._aplicar(id_notificacion, id_usuario, lambda n, ahora: n.marcar_como_leida(ahora))

    def _aplicar(self, id_notificacion: int, id_usuario: int, cambio) -> Notificacion:
        notificacion = self.notificaciones_repo.obtener_interna(
            id_notificacion=id_notificacion,
            id_usuario=id_usuario,
        )
        if notificacion is None:
            if self.notificaciones_repo.existe_interna(id_notificacion):
                raise AuthorizationError(
                    code="NOTIFICACION_AJENA",
                    message="No tiene permisos para modificar notificaciones de otros usuarios.",
                )
            raise NotFoundError(
                code="NOTIFICACION_NO_ENCONTRADA",
                message="La notificación solicitada no existe.",
            )

        cambio(notificacion, datetime.now(timezone.utc))
        try:
            self.notificaciones_repo.guardar(notificacion)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return notificacion


class AtenderNotificacionUseCase(MarcarNotificacionLeidaUseCase):
    """→ ATENDIDA. En una crítica exige la acción documentada (400 si no dice qué se hizo)."""

    def execute(self, id_notificacion: int, id_usuario: int, accion_documentada: Optional[str] = None) -> Notificacion:
        return self._aplicar(id_notificacion, id_usuario,
                             lambda n, ahora: n.atender(accion_documentada, ahora))


class DescartarNotificacionUseCase(MarcarNotificacionLeidaUseCase):
    """→ DESCARTADA. Una crítica responde 422: se cierra atendiéndola."""

    def execute(self, id_notificacion: int, id_usuario: int) -> Notificacion:
        return self._aplicar(id_notificacion, id_usuario, lambda n, ahora: n.descartar(ahora))
