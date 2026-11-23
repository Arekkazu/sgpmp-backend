# | Fecha      | Nombre   | Que se hizo                                                    |
# |------------|----------|----------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: opciones por widget y frecuencia de actualización   |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Entidad de dominio ``DashboardLayout`` — configuración del dashboard por usuario (RF-28).

Grilla 4×3 con máximo 12 widgets activos. El JSONB se estructura como
``{"grid": [...WidgetConfig...], "frecuencia_actualizacion": 30}``; cada celda puede llevar las
opciones que el usuario eligió para ese widget en ``parametros`` (RF-103). La columna de array
``active_widget`` contiene las claves de los indicadores visibles.

Los layouts predeterminados por rol ya no viven acá: están en
``modulo9.dashboard_layouts_default``. Tenerlos quemados obligaba a nombrar
``id_rol`` dentro del dominio y dejaba fuera a todo rol creado después del seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.shared.errors import ConflictError, ValidationError

_MAX_WIDGETS = 12
_MAX_FILAS = 3
_MAX_COLUMNAS = 4
# RF-103 Restricción 2: refresco automático de 30 s por defecto, configurable entre 15 y 120.
FRECUENCIA_DEFECTO = 30
_FRECUENCIA_MIN, _FRECUENCIA_MAX = 15, 120


@dataclass
class WidgetConfig:
    """Posición y tamaño de un widget dentro de la grilla 4×3 del dashboard."""
    id_widget: int
    posicion_fila: int
    posicion_columna: int
    span_columnas: int
    visible: bool
    orden: int
    # Opciones elegidas en "Configurar widget" (RF-103); vacío = valores por defecto del widget.
    parametros: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serializa la configuración del widget."""
        datos = {
            "id_widget": self.id_widget,
            "posicion_fila": self.posicion_fila,
            "posicion_columna": self.posicion_columna,
            "span_columnas": self.span_columnas,
            "visible": self.visible,
            "orden": self.orden,
        }
        if self.parametros:
            datos["parametros"] = self.parametros
        return datos

    @classmethod
    def from_dict(cls, d: dict) -> WidgetConfig:
        """Crea la configuración del widget desde un diccionario."""
        return cls(
            id_widget=d["id_widget"],
            posicion_fila=d["posicion_fila"],
            posicion_columna=d["posicion_columna"],
            span_columnas=d["span_columnas"],
            visible=d["visible"],
            orden=d["orden"],
            parametros=d.get("parametros") or {},
        )


@dataclass(eq=False)
class DashboardLayout:
    """Dashboard de un usuario (RF-28): grilla 4×3 con hasta 12 widgets activos sin
    solapamientos.
    """
    id_usuario: int
    grid: list[WidgetConfig]
    active_widget: list[str]
    fecha_actualizacion: Optional[datetime]
    id_dashboard_layout: Optional[int] = None
    frecuencia_actualizacion: int = FRECUENCIA_DEFECTO

    @classmethod
    def crear(
        cls,
        *,
        id_usuario: int,
        grid: list[WidgetConfig],
        active_widget: list[str],
        frecuencia_actualizacion: int = FRECUENCIA_DEFECTO,
    ) -> DashboardLayout:
        """Crea la entidad validando sus datos."""
        cls._validar(grid, active_widget)
        cls._validar_frecuencia(frecuencia_actualizacion)
        return cls(
            id_usuario=id_usuario,
            grid=grid,
            active_widget=active_widget,
            fecha_actualizacion=datetime.now(timezone.utc),
            frecuencia_actualizacion=frecuencia_actualizacion,
        )

    def actualizar(self, *, grid: list[WidgetConfig], active_widget: list[str],
                   frecuencia_actualizacion: Optional[int] = None) -> None:
        """Actualiza los datos editables validándolos."""
        self._validar(grid, active_widget)
        if frecuencia_actualizacion is not None:
            self._validar_frecuencia(frecuencia_actualizacion)
            self.frecuencia_actualizacion = frecuencia_actualizacion
        self.grid = grid
        self.active_widget = active_widget
        self.fecha_actualizacion = datetime.now(timezone.utc)

    @staticmethod
    def _validar_frecuencia(segundos: int) -> None:
        if not _FRECUENCIA_MIN <= segundos <= _FRECUENCIA_MAX:
            raise ValidationError(
                code="VAL_ENTRADA",
                message=(f"La actualización automática debe ser de {_FRECUENCIA_MIN} a "
                         f"{_FRECUENCIA_MAX} segundos."),
                field="frecuencia_actualizacion",
            )

    @classmethod
    def _validar(cls, grid: list[WidgetConfig], active_widget: list[str]) -> None:
        cls._validar_grid(grid)
        cls._validar_active_widget(active_widget)

    @staticmethod
    def _validar_grid(grid: list[WidgetConfig]) -> None:
        # Un widget oculto no cuenta para el límite ni ocupa celda: el propio RF
        # ofrece "desactive un widget antes de agregar uno nuevo" como remedio,
        # así que apagar uno tiene que liberar de verdad su lugar en la grilla.
        activos = [w for w in grid if w.visible]

        if len(activos) > _MAX_WIDGETS:
            raise ValidationError(
                code="LIMITE_WIDGETS_ALCANZADO",
                message=(
                    f"Límite de widgets alcanzado: El dashboard permite un máximo de "
                    f"{_MAX_WIDGETS} elementos activos simultáneamente. Por favor, "
                    "desactive un widget antes de agregar uno nuevo."
                ),
                field="layout_config",
            )

        # Los rangos sí se validan sobre todo el grid, visible u oculto: un widget
        # apagado con coordenadas basura vuelve a encenderse algún día.
        for w in grid:
            if w.posicion_fila < 1 or w.posicion_fila > _MAX_FILAS:
                raise ValidationError(
                    code="POSICION_FILA_INVALIDA",
                    message=f"La fila {w.posicion_fila} no es válida. Valores permitidos: 1–{_MAX_FILAS}.",
                    field="posicion_fila",
                )
            if w.posicion_columna < 1 or w.posicion_columna > _MAX_COLUMNAS:
                raise ValidationError(
                    code="POSICION_COLUMNA_INVALIDA",
                    message=f"La columna {w.posicion_columna} no es válida. Valores permitidos: 1–{_MAX_COLUMNAS}.",
                    field="posicion_columna",
                )
            if w.span_columnas not in (1, 2):
                raise ValidationError(
                    code="SPAN_INVALIDO",
                    message="El span de columnas debe ser 1 o 2.",
                    field="span_columnas",
                )
            if w.posicion_columna + w.span_columnas - 1 > _MAX_COLUMNAS:
                raise ValidationError(
                    code="DESBORDE_HORIZONTAL",
                    message=(
                        f"Error de dimensiones: Un widget con extensión de {w.span_columnas} "
                        "columnas no puede ubicarse en la última columna "
                        f"(columna {_MAX_COLUMNAS}) de la grilla."
                    ),
                    field="posicion_columna",
                )

        # Solapamiento: una celda ocupada dos veces, ya sea directamente o porque
        # cae dentro del rango de expansión de un widget de span 2.
        celdas_ocupadas: set[tuple[int, int]] = set()
        for w in activos:
            for col_offset in range(w.span_columnas):
                celda = (w.posicion_fila, w.posicion_columna + col_offset)
                if celda in celdas_ocupadas:
                    raise ConflictError(
                        code="SOLAPAMIENTO_WIDGETS",
                        message=(
                            f"Conflicto de posición: La ubicación en la fila {celda[0]} y "
                            f"columna {celda[1]} ya está ocupada por otro elemento o se "
                            "encuentra dentro del rango de expansión de un widget adyacente."
                        ),
                        field="layout_config",
                    )
                celdas_ocupadas.add(celda)

    @staticmethod
    def _validar_active_widget(active_widget: list[str]) -> None:
        # Sin este tope, el límite de 12 se burlaba entero: `layout_config: []`
        # más un `active_widget` de 500 entradas pasaba sin objeción.
        if len(active_widget) > _MAX_WIDGETS:
            raise ValidationError(
                code="LIMITE_WIDGETS_ALCANZADO",
                message=(
                    f"Límite de widgets alcanzado: El dashboard permite un máximo de "
                    f"{_MAX_WIDGETS} elementos activos simultáneamente. Por favor, "
                    "desactive un widget antes de agregar uno nuevo."
                ),
                field="active_widget",
            )
        if len(set(active_widget)) != len(active_widget):
            raise ValidationError(
                code="ACTIVE_WIDGET_DUPLICADO",
                message="La lista de indicadores activos no puede repetir un mismo identificador.",
                field="active_widget",
            )

    def config_jsonb(self) -> dict:
        """Configuración del tablero en el formato guardado en la base."""
        return {"grid": [w.to_dict() for w in self.grid], "frecuencia_actualizacion": self.frecuencia_actualizacion}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DashboardLayout):
            return NotImplemented
        if self.id_dashboard_layout is None or other.id_dashboard_layout is None:
            return self is other
        return self.id_dashboard_layout == other.id_dashboard_layout

    def __hash__(self) -> int:
        return hash(self.id_dashboard_layout)
