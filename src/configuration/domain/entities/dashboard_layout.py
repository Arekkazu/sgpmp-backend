"""Entidad de dominio ``DashboardLayout`` — configuración del dashboard por usuario (RF-28).

Grilla 4×3 con máximo 12 widgets activos. El JSONB se estructura como
``{"grid": [...WidgetConfig...]}``. La columna de array ``active_widget``
contiene los identificadores de widgets visibles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.shared.errors import BusinessRuleError, ConflictError, ValidationError

_MAX_WIDGETS = 12
_MAX_FILAS = 3
_MAX_COLUMNAS = 4

# Layouts predeterminados por id_rol (vacío hasta definir el catálogo de widgets)
_DEFAULT_GRID_POR_ROL: dict[int, list[dict]] = {
    1: [],
    2: [],
    3: [],
    4: [],
    5: [],
}


@dataclass
class WidgetConfig:
    id_widget: int
    posicion_fila: int
    posicion_columna: int
    span_columnas: int
    visible: bool
    orden: int

    def to_dict(self) -> dict:
        return {
            "id_widget": self.id_widget,
            "posicion_fila": self.posicion_fila,
            "posicion_columna": self.posicion_columna,
            "span_columnas": self.span_columnas,
            "visible": self.visible,
            "orden": self.orden,
        }

    @classmethod
    def from_dict(cls, d: dict) -> WidgetConfig:
        return cls(
            id_widget=d["id_widget"],
            posicion_fila=d["posicion_fila"],
            posicion_columna=d["posicion_columna"],
            span_columnas=d["span_columnas"],
            visible=d["visible"],
            orden=d["orden"],
        )


@dataclass(eq=False)
class DashboardLayout:
    id_usuario: int
    grid: list[WidgetConfig]
    active_widget: list[str]
    fecha_actualizacion: Optional[datetime]
    id_dashboard_layout: Optional[int] = None

    @classmethod
    def crear(
        cls,
        *,
        id_usuario: int,
        grid: list[WidgetConfig],
        active_widget: list[str],
    ) -> DashboardLayout:
        cls._validar_grid(grid)
        return cls(
            id_usuario=id_usuario,
            grid=grid,
            active_widget=active_widget,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

    @classmethod
    def default_para_rol(cls, id_usuario: int, id_rol: int) -> DashboardLayout:
        grid_dicts = _DEFAULT_GRID_POR_ROL.get(id_rol, [])
        grid = [WidgetConfig.from_dict(d) for d in grid_dicts]
        return cls(
            id_usuario=id_usuario,
            grid=grid,
            active_widget=[],
            fecha_actualizacion=datetime.now(timezone.utc),
        )

    def actualizar(self, *, grid: list[WidgetConfig], active_widget: list[str]) -> None:
        self._validar_grid(grid)
        self.grid = grid
        self.active_widget = active_widget
        self.fecha_actualizacion = datetime.now(timezone.utc)

    @staticmethod
    def _validar_grid(grid: list[WidgetConfig]) -> None:
        activos = [w for w in grid if w.visible]
        if len(activos) > _MAX_WIDGETS:
            raise BusinessRuleError(
                code="LIMITE_WIDGETS_ALCANZADO",
                message=(
                    f"El dashboard permite un máximo de {_MAX_WIDGETS} widgets activos simultáneamente. "
                    "Por favor, desactive un widget antes de agregar uno nuevo."
                ),
            )

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
                        f"Un widget con span de {w.span_columnas} columnas no puede ubicarse "
                        f"en la columna {w.posicion_columna} (desborde fuera de la grilla)."
                    ),
                    field="posicion_columna",
                )

        # Verificar solapamiento de celdas
        celdas_ocupadas: set[tuple[int, int]] = set()
        for w in grid:
            for col_offset in range(w.span_columnas):
                celda = (w.posicion_fila, w.posicion_columna + col_offset)
                if celda in celdas_ocupadas:
                    raise ConflictError(
                        code="SOLAPAMIENTO_WIDGETS",
                        message=(
                            f"Conflicto de posición: la celda fila {celda[0]}, columna {celda[1]} "
                            "ya está ocupada por otro widget."
                        ),
                    )
                celdas_ocupadas.add(celda)

    def config_jsonb(self) -> dict:
        return {"grid": [w.to_dict() for w in self.grid]}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DashboardLayout):
            return NotImplemented
        if self.id_dashboard_layout is None or other.id_dashboard_layout is None:
            return self is other
        return self.id_dashboard_layout == other.id_dashboard_layout

    def __hash__(self) -> int:
        return hash(self.id_dashboard_layout)
