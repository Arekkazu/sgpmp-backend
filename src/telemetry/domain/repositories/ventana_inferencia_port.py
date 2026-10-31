# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-56/RF-66: ventana de lecturas del activo para el motor IA     |
# | 2026-10-31 | Arekkazu | RF-17/RF-66 C3: rangos de la especie del activo desde M09        |
"""Contrato IA-1 v1 (decisión D-B del plan del motor): el backend envía con cada paquete
el activo al que pertenece y su ventana de lecturas, porque el paquete de RF-56 es una sola
lectura de una variable y el modelo individual (ET-02) necesita la serie del animal."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

from src.telemetry.domain.entities.telemetria import PaqueteInferencia

#: ET-02 usa la ventana anterior (deltas) y la actividad de la hora previa (t_act).
DURACION_VENTANA = timedelta(hours=2)


@dataclass(frozen=True)
class VentanaActivo:
    id_activo_biologico: Optional[int]
    #: Formato largo: ``{"timestamp", "variable", "valor", "apto_para_ia"}``, una fila por lectura.
    lecturas: list[dict[str, Any]] = field(default_factory=list)
    #: ET-02 C3: bandas RF-17 de la especie del activo, ``{variable_et02: {"sano": [min, max],
    #: "plausible": [min, max]}}``. Sano = tramo ``normal``; plausible = ``valor_min``–``valor_max``
    #: del umbral. Solo las variables con umbral activo; el motor usa sus valores propios en las demás.
    rangos_especie: dict[str, dict[str, list[float]]] = field(default_factory=dict)


class VentanaInferenciaPort(ABC):
    @abstractmethod
    def ventanas(self, paquetes: list[PaqueteInferencia]) -> dict[int, VentanaActivo]:
        """``{id_paquetes_inferencia: VentanaActivo}``. Un paquete cuyo sensor no está asociado
        a un activo individual queda con ``id_activo_biologico=None`` y sin lecturas."""
