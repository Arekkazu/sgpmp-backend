# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-105 R6: consultar y guardar las preferencias de canal     |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Casos de uso: preferencias de notificación del usuario (RF-105 R6, CA-14).

Por cada nivel (CRÍTICA, ADVERTENCIA, INFORMATIVA) el usuario decide si además de la bandeja recibe push y correo.
Sin preferencia guardada rigen los valores por defecto del RF (push en crítica y advertencia, correo solo en
crítica). La bandeja interna siempre está activa: es la fuente de toda notificación (R9) y no se puede apagar."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.notificacion_repository import NotificacionRepository
from src.identity_access.domain.value_objects.nivel_notificacion import CANALES_EXTERNOS, NIVELES, canal_por_defecto

IN_APP = "IN_APP"


def _vista(guardadas: dict[tuple[str, str], bool]) -> list[dict[str, Any]]:
    filas = []
    for nivel in NIVELES:
        filas.append({"nivel": nivel, "canal": IN_APP, "habilitado": True, "por_defecto": True, "editable": False})
        for canal in CANALES_EXTERNOS:
            guardada = guardadas.get((nivel, canal))
            filas.append({"nivel": nivel, "canal": canal, "editable": True, "por_defecto": guardada is None,
                          "habilitado": canal_por_defecto(nivel, canal) if guardada is None else guardada})
    return filas


class ConsultarPreferenciasNotificacionUseCase:
    """Consulta las preferencias de canal de notificación del usuario."""

    def __init__(self, repo: NotificacionRepository) -> None:
        self.repo = repo

    def execute(self, id_usuario: int) -> list[dict[str, Any]]:
        """Devuelve las preferencias por nivel y canal del usuario."""
        return _vista(self.repo.preferencias(id_usuario))


class GuardarPreferenciasNotificacionUseCase:
    """Guarda las preferencias de canal de notificación del usuario."""

    def __init__(self, repo: NotificacionRepository, db: Session) -> None:
        self.repo = repo
        self.db = db

    def execute(self, id_usuario: int, cambios: list[tuple[str, str, bool]]) -> list[dict[str, Any]]:
        """Aplica los cambios de preferencias y devuelve las preferencias resultantes."""
        try:
            self.repo.guardar_preferencias(id_usuario, {(nivel, canal): habilitado for nivel, canal, habilitado in cambios})
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return _vista(self.repo.preferencias(id_usuario))
