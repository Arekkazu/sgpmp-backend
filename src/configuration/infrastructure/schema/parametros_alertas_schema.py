# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-168-G76 RF-57: respuesta de los parámetros de alertas |
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel


class ParametroAlertaSchema(BaseModel):
    nombre: str
    descripcion: str
    valor: Optional[Any] = None
    valor_configurado: Optional[Any] = None
    valor_base: Optional[Any] = None
    fuente: str
    rango_minimo: Optional[Decimal] = None
    rango_maximo: Optional[Decimal] = None

    model_config = {"from_attributes": True}
