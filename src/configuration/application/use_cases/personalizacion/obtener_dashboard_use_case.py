"""Caso de uso: Obtener layout del dashboard del usuario (GET RF-28).

Si no tiene configuración guardada, devuelve el layout predeterminado de su rol.
Un rol sin default devuelve una grilla vacía: el 500 del RF está reservado al
flujo de restaurar, donde el usuario sí pidió explícitamente los valores base.
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
        if layout is not None:
            return layout

        default = self.dashboard_repo.obtener_default_de_rol(
            id_usuario=usuario_actual.id_usuario,
            id_rol=usuario_actual.id_rol,
        )
        if default is not None:
            return default

        return DashboardLayout(
            id_usuario=usuario_actual.id_usuario,
            grid=[],
            active_widget=[],
            fecha_actualizacion=None,
        )
