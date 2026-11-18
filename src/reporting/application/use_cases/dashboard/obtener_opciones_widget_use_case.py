# | Fecha      | Nombre   | Que se hizo                                                   |
# |------------|----------|---------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: valores elegibles de las opciones de un widget      |
"""Caso de uso: qué se puede elegir en cada opción de un widget (RF-103, "Configurar widget").

Las áreas, especies y sensores son los de la finca activa; las opciones de lista devuelven sus
valores tal cual (el front pone el texto de cada uno).
"""
from __future__ import annotations

from typing import Any, Optional

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.reporting.application.use_cases.dashboard.obtener_datos_widget_use_case import ObtenerDatosWidgetUseCase
from src.reporting.domain.widgets import AREA, AREAS, ESPECIES, SENSORES


class ObtenerOpcionesWidgetUseCase:
    """Valores elegibles por opción, con las mismas reglas de acceso que los datos del widget."""

    def __init__(self, datos_widget: ObtenerDatosWidgetUseCase) -> None:
        self.datos_widget = datos_widget

    def execute(self, clave: str, id_finca: Optional[int], usuario: UsuarioActual) -> dict[str, list[dict[str, Any]]]:
        definicion, _ = self.datos_widget.autorizar(clave, usuario)
        self.datos_widget.validar_finca(id_finca, definicion, usuario)
        datos = self.datos_widget.datos
        resultado: dict[str, list[dict[str, Any]]] = {}
        for opcion in definicion.opciones:
            if opcion.tipo in (AREAS, AREA):
                resultado[opcion.nombre] = datos.areas_de_finca(id_finca) if id_finca else []
            elif opcion.tipo == ESPECIES:
                resultado[opcion.nombre] = datos.especies_de_finca(id_finca) if id_finca else []
            elif opcion.tipo == SENSORES:
                resultado[opcion.nombre] = datos.sensores_de_finca(id_finca) if id_finca else []
            else:
                resultado[opcion.nombre] = [{"valor": v} for v in opcion.valores]
        return resultado
