"""Caso de uso: Datos de los widgets visibles del dashboard del usuario (GET RF-28).

Devuelve una entrada por widget visible del layout. Un widget sin fuente de datos
configurada, o cuya fuente no devolvió filas, se marca ``sin_datos`` en vez de
omitirse: el RF exige que conserve su posición en la grilla y que no rompa a los
demás widgets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.configuration.domain.entities.widget import MENSAJE_SIN_DATOS
from src.configuration.domain.repositories.dashboard_layout_repository import DashboardLayoutRepository
from src.configuration.domain.repositories.widget_datos_repository import WidgetDatosRepository
from src.configuration.domain.repositories.widget_repository import WidgetRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual


@dataclass
class WidgetConDatos:
    id_widget: int
    clave: str
    nombre: str
    posicion_fila: int
    posicion_columna: int
    span_columnas: int
    orden: int
    sin_datos: bool
    mensaje: str | None
    datos: list[dict[str, Any]]


class ObtenerDatosDashboardUseCase:

    def __init__(
        self,
        dashboard_repo: DashboardLayoutRepository,
        widget_repo: WidgetRepository,
        datos_repo: WidgetDatosRepository,
    ) -> None:
        self.dashboard_repo = dashboard_repo
        self.widget_repo = widget_repo
        self.datos_repo = datos_repo

    def execute(self, usuario_actual: UsuarioActual) -> list[WidgetConDatos]:
        layout = self.dashboard_repo.obtener_por_usuario(usuario_actual.id_usuario)
        if layout is None:
            layout = self.dashboard_repo.obtener_default_de_rol(
                id_usuario=usuario_actual.id_usuario,
                id_rol=usuario_actual.id_rol,
            )
        if layout is None:
            return []

        catalogo = {w.id_widget: w for w in self.widget_repo.obtener_activos()}
        legibles = self.widget_repo.ids_legibles_por_rol(usuario_actual.id_rol)

        resultado: list[WidgetConDatos] = []
        for celda in sorted(layout.grid, key=lambda c: c.orden):
            if not celda.visible:
                continue
            widget = catalogo.get(celda.id_widget)
            # Un widget que salió del catálogo, o que el rol dejó de poder leer,
            # no se cuela en la respuesta.
            if widget is None or widget.id_widget not in legibles:
                continue

            filas = self.datos_repo.obtener(widget.fuente_datos) if widget.fuente_datos else []
            sin_datos = not filas
            resultado.append(
                WidgetConDatos(
                    id_widget=widget.id_widget,
                    clave=widget.clave,
                    nombre=widget.nombre,
                    posicion_fila=celda.posicion_fila,
                    posicion_columna=celda.posicion_columna,
                    span_columnas=celda.span_columnas,
                    orden=celda.orden,
                    sin_datos=sin_datos,
                    mensaje=MENSAJE_SIN_DATOS if sin_datos else None,
                    datos=filas,
                )
            )
        return resultado
