"""Implementación SQLAlchemy del puerto ``WidgetDatosRepository`` (RF-28).

Lee las vistas ``modulo9.vw_rf28_widget_*`` que ya existían en el esquema y que
ningún código consumía. El nombre de la fuente se resuelve contra una lista
blanca: aunque hoy provenga de nuestra propia tabla de catálogo, nunca se
interpola texto libre dentro de un FROM.
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

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener(self, fuente_datos: str) -> list[dict[str, Any]]:
        vista = _FUENTES_PERMITIDAS.get(fuente_datos)
        if vista is None:
            return []
        filas = self.db.execute(
            text(f"SELECT * FROM {vista} LIMIT :limite"),
            {"limite": _LIMITE_FILAS},
        ).mappings().all()
        return [dict(f) for f in filas]
