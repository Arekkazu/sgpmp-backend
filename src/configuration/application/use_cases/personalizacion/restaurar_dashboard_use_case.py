"""Caso de uso: Restaurar dashboard a la configuración predeterminada del rol (POST RF-28)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dashboard_layout import DashboardLayout
from src.configuration.domain.repositories.dashboard_layout_repository import DashboardLayoutRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import InfrastructureError


class RestaurarDashboardUseCase:

    def __init__(self, db: Session, dashboard_repo: DashboardLayoutRepository) -> None:
        self.db = db
        self.dashboard_repo = dashboard_repo

    def execute(self, usuario_actual: UsuarioActual) -> DashboardLayout:
        default = self.dashboard_repo.obtener_default_de_rol(
            id_usuario=usuario_actual.id_usuario,
            id_rol=usuario_actual.id_rol,
        )
        if default is None:
            # Pasa con roles creados después del seed de layouts base. La
            # configuración actual del usuario queda intacta: no se escribe nada.
            nombre_rol = self.dashboard_repo.nombre_de_rol(usuario_actual.id_rol)
            raise InfrastructureError(
                code="RESTAURACION_SIN_DEFAULT",
                message=(
                    "Fallo de restauración: No se encontró una configuración predeterminada "
                    f"para el rol {nombre_rol or usuario_actual.id_rol}. Se mantendrá su "
                    "configuración actual; por favor, contacte a soporte."
                ),
            )

        existente = self.dashboard_repo.obtener_por_usuario(usuario_actual.id_usuario)

        try:
            if existente is not None:
                existente.actualizar(grid=default.grid, active_widget=default.active_widget)
                resultado = self.dashboard_repo.actualizar(existente)
            else:
                resultado = self.dashboard_repo.guardar(
                    DashboardLayout.crear(
                        id_usuario=usuario_actual.id_usuario,
                        grid=default.grid,
                        active_widget=default.active_widget,
                    )
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return resultado
