"""Caso de uso: marcar como leídas todas las notificaciones internas propias.

T-08 del reporte de usabilidad UAT (07/10/2026): hay usuarios con más de 169
notificaciones y no había forma de vaciar la bandeja salvo una por una.
"""
from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.notificacion_repository import (
    NotificacionRepository,
)


class MarcarTodasLeidasUseCase:
    """Solo toca las notificaciones del propio usuario (el filtro va en el repositorio)."""

    def __init__(self, notificaciones_repo: NotificacionRepository, db: Session):
        self.notificaciones_repo = notificaciones_repo
        self.db = db

    def execute(self, id_usuario: int) -> int:
        try:
            cambiadas = self.notificaciones_repo.marcar_todas_leidas(id_usuario)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return cambiadas
