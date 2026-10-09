"""Read-model ``ObservacionVision`` — vector de comportamiento de una cámara (RF-53/RF-56).

Lo que RF-24 VISION necesita de cada observación: su índice de calidad (RF-62)
y los componentes del vector. Lo produce M03 (``modulo3.observaciones_vision``,
POST /iot/telemetria/vision) y llega por ``ObservacionVisionPort``.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ObservacionVision:
    """Vector de comportamiento de una cámara en una ventana de tiempo, con su aptitud
    para IA (RF-62).
    """
    id_dispositivo_iot: int
    fecha_observacion: datetime.datetime
    # RF-62: índice de calidad de visión.
    es_apto_para_ia: bool
    cobertura_ventana: float      # fracción [0, 1] de la ventana con señal
    n_tracks: int                 # tracks válidos en la ventana
    # Componentes del vector (p. ej. densidad_actividad, dispersion_espacial,
    # tasa_movimiento). Cada etapa trabaja cada componente por separado.
    componentes: dict[str, float] = field(default_factory=dict)
