"""Implementación SQLAlchemy del puerto ``DashboardLayoutRepository`` (RF-28)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dashboard_layout import DashboardLayout, WidgetConfig
from src.configuration.domain.repositories.dashboard_layout_repository import DashboardLayoutRepository
from src.configuration.infrastructure.models.dashboard_layout_model import DashboardLayoutModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyDashboardLayoutRepository(DashboardLayoutRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: DashboardLayoutModel) -> DashboardLayout:
        grid_raw = (orm.config or {}).get("grid", [])
        grid = [WidgetConfig.from_dict(w) for w in grid_raw]
        return DashboardLayout(
            id_dashboard_layout=orm.id_dashboard_layout,
            id_usuario=orm.id_usuario,
            grid=grid,
            active_widget=list(orm.active_widget or []),
            fecha_actualizacion=orm.fecha_actualizacion,
        )

    def obtener_por_usuario(self, id_usuario: int) -> Optional[DashboardLayout]:
        orm = (
            self.db.query(DashboardLayoutModel)
            .filter(DashboardLayoutModel.id_usuario == id_usuario)
            .order_by(
                DashboardLayoutModel.fecha_actualizacion.desc().nullslast(),
                DashboardLayoutModel.id_dashboard_layout.desc(),
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, entidad: DashboardLayout) -> DashboardLayout:
        orm = DashboardLayoutModel(
            id_usuario=entidad.id_usuario,
            config=entidad.config_jsonb(),
            active_widget=entidad.active_widget,
            fecha_actualizacion=entidad.fecha_actualizacion,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

    def actualizar(self, entidad: DashboardLayout) -> DashboardLayout:
        orm = self.db.get(DashboardLayoutModel, entidad.id_dashboard_layout)
        orm.config = entidad.config_jsonb()
        orm.active_widget = entidad.active_widget
        orm.fecha_actualizacion = entidad.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)
