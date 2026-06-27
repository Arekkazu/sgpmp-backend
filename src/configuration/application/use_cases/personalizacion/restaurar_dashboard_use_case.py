"""Caso de uso: Restaurar dashboard a la configuración predeterminada del rol (POST RF-28)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dashboard_layout import DashboardLayout
from src.configuration.domain.repositories.dashboard_layout_repository import DashboardLayoutRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual


class RestaurarDashboardUseCase:

    def __init__(self, db: Session, dashboard_repo: DashboardLayoutRepository) -> None:
        self.db = db
        self.dashboard_repo = dashboard_repo

    def execute(self, usuario_actual: UsuarioActual) -> DashboardLayout:
        default = DashboardLayout.default_para_rol(
            id_usuario=usuario_actual.id_usuario,
            id_rol=usuario_actual.id_rol,
        )

        existente = self.dashboard_repo.obtener_por_usuario(usuario_actual.id_usuario)

        try:
            if existente is not None:
                existente.actualizar(grid=default.grid, active_widget=default.active_widget)
                resultado = self.dashboard_repo.actualizar(existente)
            else:
                resultado = self.dashboard_repo.guardar(default)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return resultado
