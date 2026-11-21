# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: desactivar una arista de transmisión       |
"""Baja lógica: la arista deja de contar para la exposición de RF-68. El RLS ya oculta las de áreas
ajenas, así que una arista que el usuario no ve es 404."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.arista_transmision import AristaTransmision
from src.configuration.domain.repositories.arista_transmision_repository import AristaTransmisionRepository
from src.shared.errors import BusinessRuleError, NotFoundError


class DesactivarAristaTransmisionUseCase:

    def __init__(self, db: Session, arista_repo: AristaTransmisionRepository) -> None:
        self.db = db
        self.arista_repo = arista_repo

    def execute(self, id_arista: int) -> AristaTransmision:
        arista = self.arista_repo.obtener_por_id(id_arista)
        if arista is None:
            raise NotFoundError(code="ARISTA_NO_ENCONTRADA", message=f"No existe la arista {id_arista}.")
        if not arista.es_activo:
            raise BusinessRuleError(code="ARISTA_YA_INACTIVA", message="La arista ya está inactiva.")
        arista.desactivar()
        try:
            arista = self.arista_repo.actualizar(arista)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return arista
