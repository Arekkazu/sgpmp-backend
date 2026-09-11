"""Implementación SQLAlchemy del puerto ``WidgetRepository`` (RF-28)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.widget import Widget
from src.configuration.domain.repositories.widget_repository import WidgetRepository
from src.configuration.infrastructure.models.widget_model import WidgetModel
from src.identity_access.infrastructure.models.permisos_model import Permisos

# Acción "Leer" en modulo1.acciones. Un widget se ve si el rol puede leer el
# recurso que lo gobierna.
_ACCION_LEER = 2


class SqlAlchemyWidgetRepository(WidgetRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: WidgetModel) -> Widget:
        return Widget(
            id_widget=orm.id_widget,
            clave=orm.clave,
            nombre=orm.nombre,
            grupo=orm.grupo,
            span_predeterminado=orm.span_predeterminado,
            id_recurso=orm.id_recurso,
            fuente_datos=orm.fuente_datos,
        )

    def obtener_activos(self) -> list[Widget]:
        filas = (
            self.db.query(WidgetModel)
            .filter(WidgetModel.es_activo.is_(True))
            .order_by(WidgetModel.id_widget)
            .all()
        )
        return [self._a_entidad(f) for f in filas]

    def ids_legibles_por_rol(self, id_rol: int) -> set[int]:
        filas = (
            self.db.query(WidgetModel.id_widget)
            .join(Permisos, Permisos.id_recurso == WidgetModel.id_recurso)
            .filter(
                WidgetModel.es_activo.is_(True),
                Permisos.id_rol == id_rol,
                Permisos.id_accion == _ACCION_LEER,
                Permisos.es_activo.is_(True),
            )
            .all()
        )
        return {f[0] for f in filas}
