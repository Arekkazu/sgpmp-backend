"""Entidad de dominio ``Widget`` — catálogo de widgets del dashboard (RF-28).

Cada widget declara el ``id_recurso`` cuyo permiso de lectura lo habilita. Así el
RF-28 puede rechazar con 403 un widget que no corresponde al rol del usuario sin
que ningún ``id_rol`` quede escrito en el código: la decisión sale de
``modulo1.permisos``, igual que el resto del RBAC.

``fuente_datos`` nombra la vista que alimenta el widget. Un widget sin fuente no
es un error: responde "Sin datos disponibles", que es el fallback que el propio
RF prescribe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Texto literal del flujo alterno de "widget sin datos operativos" del RF-28.
MENSAJE_SIN_DATOS = "Sin datos disponibles para el sensor o periodo seleccionado."


@dataclass(frozen=True)
class Widget:
    id_widget: int
    clave: str
    nombre: str
    grupo: str
    span_predeterminado: int
    id_recurso: int
    fuente_datos: Optional[str] = None
