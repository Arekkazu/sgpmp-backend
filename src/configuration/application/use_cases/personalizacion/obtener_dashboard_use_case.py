"""Caso de uso: Obtener layout del dashboard del usuario (GET RF-28).

Si no tiene configuración guardada, devuelve el layout predeterminado de su rol.
"""
from __future__ import annotations

from src.configuration.domain.entities.dashboard_layout import DashboardLayout
from src.configuration.domain.repositories.dashboard_layout_repository import DashboardLayoutRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual


class ObtenerDashboardUseCase:

    def __init__(self, dashboard_repo: DashboardLayoutRepository) -> None:
        self.dashboard_repo = dashboard_repo

    def execute(self, usuario_actual: UsuarioActual) -> DashboardLayout:
        layout = self.dashboard_repo.obtener_por_usuario(usuario_actual.id_usuario)
        if layout is None:
            return DashboardLayout.default_para_rol(
                id_usuario=usuario_actual.id_usuario,
                id_rol=usuario_actual.id_rol,
            )
        return layout
