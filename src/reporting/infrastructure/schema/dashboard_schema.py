# | Fecha      | Nombre   | Que se hizo                                  |
# |------------|----------|----------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: respuesta de datos de un widget    |
"""Schemas de respuesta del dashboard por widgets (RF-103)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel


class DatosWidgetResponse(BaseModel):
    """Datos de un widget. ``estado``: OK, SIN_DATOS (con ``mensaje``) o ERROR (con ``mensaje``).

    ``huella`` cambia solo si cambian los datos. ``alcance``: ``todas`` cuando el widget mostró
    toda la finca porque lo elegido no es de ella o no se eligió nada.
    """
    clave: str
    estado: Literal["OK", "SIN_DATOS", "ERROR"]
    mensaje: Optional[str]
    actualizado_en: datetime
    huella: str
    alcance: Optional[Literal["seleccion", "todas"]] = None
    datos: dict[str, Any]

    model_config = {"from_attributes": True}


class ValorOpcionResponse(BaseModel):
    """Un valor elegible: ``nombre`` (y ``area`` en sensores) para los que vienen de la finca."""
    valor: int | str
    nombre: Optional[str] = None
    area: Optional[str] = None
