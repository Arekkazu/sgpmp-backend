"""Implementación SQLAlchemy del puerto ``DashboardLayoutRepository`` (RF-28)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dashboard_layout import DashboardLayout, WidgetConfig
from src.configuration.domain.repositories.dashboard_layout_repository import DashboardLayoutRepository
from src.configuration.infrastructure.models.dashboard_layout_default_model import DashboardLayoutDefaultModel
from src.configuration.infrastructure.models.dashboard_layout_model import DashboardLayoutModel
from src.identity_access.infrastructure.models.roles_model import Roles
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import NotFoundError


class SqlAlchemyDashboardLayoutRepository(DashboardLayoutRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _grid_desde_config(config: Optional[dict]) -> list[WidgetConfig]:
        return [WidgetConfig.from_dict(w) for w in (config or {}).get("grid", [])]

    @classmethod
    def _a_entidad(cls, orm: DashboardLayoutModel) -> DashboardLayout:
        return DashboardLayout(
            id_dashboard_layout=orm.id_dashboard_layout,
            id_usuario=orm.id_usuario,
            grid=cls._grid_desde_config(orm.config),
            active_widget=list(orm.active_widget or []),
            fecha_actualizacion=orm.fecha_actualizacion,
        )

    def obtener_por_usuario(self, id_usuario: int) -> Optional[DashboardLayout]:
        # El UNIQUE(id_usuario) hace que a lo sumo haya una fila, pero el orden
        # se conserva por si esta consulta corre contra un entorno sin la
        # migración aplicada todavía.
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

    def obtener_default_de_rol(self, id_usuario: int, id_rol: int) -> Optional[DashboardLayout]:
        orm = self.db.get(DashboardLayoutDefaultModel, id_rol)
        if orm is None:
            return None
        return DashboardLayout(
            id_usuario=id_usuario,
            grid=self._grid_desde_config(orm.config),
            active_widget=list(orm.active_widget or []),
            fecha_actualizacion=None,
        )

    def nombre_de_rol(self, id_rol: int) -> Optional[str]:
        return (
            self.db.query(Roles.nombre_rol)
            .filter(Roles.id_rol == id_rol)
            .scalar()
        )

    def version_perfil(self, id_usuario: int) -> Optional[int]:
        return (
            self.db.query(Usuarios.version)
            .filter(Usuarios.id_usuario == id_usuario)
            .scalar()
        )

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
        if orm is None:
            # Sin este guard la asignación de abajo reventaba con AttributeError
            # y salía como 500: la fila puede haber desaparecido entre la lectura
            # del use case y esta escritura.
            raise NotFoundError(
                code="DASHBOARD_LAYOUT_NO_ENCONTRADO",
                message="La configuración del dashboard que intenta actualizar ya no existe.",
            )
        orm.config = entidad.config_jsonb()
        orm.active_widget = entidad.active_widget
        orm.fecha_actualizacion = entidad.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)
