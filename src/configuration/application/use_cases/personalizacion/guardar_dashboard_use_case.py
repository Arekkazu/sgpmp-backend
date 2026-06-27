"""Caso de uso: Guardar configuración del dashboard del usuario (PATCH RF-28).

Valida la grilla (max 12 widgets, sin solapamiento, sin desborde).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dashboard_layout import DashboardLayout, WidgetConfig
from src.configuration.domain.repositories.dashboard_layout_repository import DashboardLayoutRepository
from src.configuration.infrastructure.dto.guardar_dashboard_dto import GuardarDashboardDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual


class GuardarDashboardUseCase:

    def __init__(self, db: Session, dashboard_repo: DashboardLayoutRepository) -> None:
        self.db = db
        self.dashboard_repo = dashboard_repo

    def execute(self, dto: GuardarDashboardDTO, usuario_actual: UsuarioActual) -> DashboardLayout:
        grid = [
            WidgetConfig(
                id_widget=w.id_widget,
                posicion_fila=w.posicion_fila,
                posicion_columna=w.posicion_columna,
                span_columnas=w.span_columnas,
                visible=w.visible,
                orden=w.orden,
            )
            for w in dto.layout_config
        ]

        existente = self.dashboard_repo.obtener_por_usuario(usuario_actual.id_usuario)

        try:
            if existente is not None:
                existente.actualizar(grid=grid, active_widget=dto.active_widget)
                resultado = self.dashboard_repo.actualizar(existente)
            else:
                nuevo = DashboardLayout.crear(
                    id_usuario=usuario_actual.id_usuario,
                    grid=grid,
                    active_widget=dto.active_widget,
                )
                resultado = self.dashboard_repo.guardar(nuevo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return resultado
