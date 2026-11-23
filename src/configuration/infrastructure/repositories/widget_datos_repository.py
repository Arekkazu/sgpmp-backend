# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Implementación SQLAlchemy del puerto ``WidgetDatosRepository`` (RF-28).

Lee las vistas ``modulo9.vw_rf28_widget_*`` que ya existían en el esquema y que
ningún código consumía. El nombre de la fuente se resuelve contra una lista
blanca: aunque hoy provenga de nuestra propia tabla de catálogo, nunca se
interpola texto libre dentro de un FROM.

La consulta filtra explícitamente por las fincas del usuario
(``fn_fincas_del_usuario``, la misma función que usa la RLS; el Administrador
sigue viendo todas), igual que el repositorio de widgets de M08.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# Tope de filas por widget: un panel de dashboard resume, no pagina.
_LIMITE_FILAS = 50

_FUENTES_PERMITIDAS = {
    "vw_rf28_widget_estado_dispositivos": "modulo9.vw_rf28_widget_estado_dispositivos",
    "vw_rf28_widget_estado_fincas": "modulo9.vw_rf28_widget_estado_fincas",
    "vw_rf28_widget_dispositivos_sin_configuracion": (
        "modulo9.vw_rf28_widget_dispositivos_sin_configuracion"
    ),
}


class SqlAlchemyWidgetDatosRepository:
    """Lee los datos de los widgets del tablero desde su vista."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener(self, fuente_datos: str, id_usuario: int) -> list[dict[str, Any]]:
        """Devuelve las filas de la fuente de datos del widget, solo de las fincas del usuario."""
        vista = _FUENTES_PERMITIDAS.get(fuente_datos)
        if vista is None:
            return []
        filas = self.db.execute(
            text(
                f"SELECT * FROM {vista} "  # nosec B608 - la vista sale de la lista blanca
                "WHERE id_finca IN (SELECT id_finca FROM modulo9.fn_fincas_del_usuario(:usuario)) "
                "LIMIT :limite"
            ),
            {"usuario": id_usuario, "limite": _LIMITE_FILAS},
        ).mappings().all()
        return [dict(f) for f in filas]
