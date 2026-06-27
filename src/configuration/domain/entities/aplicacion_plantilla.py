"""Read-model ``AplicacionPlantilla`` — registro de aplicación de una plantilla (RF-32).

Append-only: representa un evento de aplicación con antes/después.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(eq=False)
class AplicacionPlantilla:
    """Registro de una aplicación de plantilla sobre una configuración destino."""

    id_usuario: int
    id_plantilla: int
    target_config: dict
    fecha_aplicacion: datetime
    id_aplicacion_plantilla: Optional[int] = None
    before_snapshot: Optional[dict] = None
    after_snapshot: Optional[dict] = None

    @classmethod
    def crear(
        cls,
        *,
        id_usuario: int,
        id_plantilla: int,
        target_config: dict,
        fecha_aplicacion: datetime,
        before_snapshot: Optional[dict] = None,
        after_snapshot: Optional[dict] = None,
    ) -> AplicacionPlantilla:
        return cls(
            id_usuario=id_usuario,
            id_plantilla=id_plantilla,
            target_config=target_config,
            fecha_aplicacion=fecha_aplicacion,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )
