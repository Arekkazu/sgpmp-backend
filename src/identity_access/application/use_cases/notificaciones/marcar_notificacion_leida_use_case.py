"""Caso de uso para marcar como leída una notificación interna propia."""
from sqlalchemy.orm import Session

from src.identity_access.domain.entities.notificacion import Notificacion
from src.identity_access.domain.repositories.notificacion_repository import (
    NotificacionRepository,
)
from src.shared.errors import NotFoundError


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
        notificacion = self.notificaciones_repo.obtener_interna(
            id_notificacion=id_notificacion,
            id_usuario=id_usuario,
        )
        if notificacion is None:
            raise NotFoundError(
                code="NOTIFICACION_NO_ENCONTRADA",
                message="La notificación solicitada no existe.",
            )

        try:
            notificacion.marcar_como_leida()
            self.notificaciones_repo.guardar(notificacion)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return notificacion
