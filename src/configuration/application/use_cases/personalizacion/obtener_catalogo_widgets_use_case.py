"""Caso de uso: Catálogo de widgets disponibles para el rol del usuario (GET RF-28).

Sin este listado el 403 de "widget no disponible para su rol" sería un callejón
sin salida: la interfaz ofrecería widgets que el guardado va a rechazar.
"""
from __future__ import annotations

from src.configuration.domain.entities.widget import Widget
from src.configuration.domain.repositories.widget_repository import WidgetRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual


class ObtenerCatalogoWidgetsUseCase:

    def __init__(self, widget_repo: WidgetRepository) -> None:
        self.widget_repo = widget_repo

    def execute(self, usuario_actual: UsuarioActual) -> list[Widget]:
        legibles = self.widget_repo.ids_legibles_por_rol(usuario_actual.id_rol)
        return [w for w in self.widget_repo.obtener_activos() if w.id_widget in legibles]
