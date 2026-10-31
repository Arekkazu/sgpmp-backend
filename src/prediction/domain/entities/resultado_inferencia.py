# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: resultado que el motor IA devuelve al backend             |
"""RF-66 — Resultado de inferencia individual que entrega el motor IA (`motor-ia`).

Inmutable una vez persistido (Restricción 5, `fn_historial_diagnostico_inmutable`).
El motor genera ``id_resultado_inferencia``: si reintenta el envío, el mismo id
identifica el mismo resultado y no se duplica.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

#: CA-1: el motor produce el resultado en ≤ 2 s desde que recibe el paquete de RF-56.
LATENCIA_MAXIMA_MS = 2000


@dataclass
class ResultadoInferencia:
    id_resultado_inferencia: uuid.UUID
    id_activo_biologico: int
    tipo_modelo: str
    id_version_modelo: int
    nivel_riesgo: int
    probabilidad_riesgo: dict
    probabilidad_enfermedad: dict
    confianza_global: Decimal
    contexto_incompleto: bool
    modo_ejecucion: str
    modo_sombra: bool
    fecha_inferencia: datetime
    #: Lo resuelve el backend desde el activo; el motor no lo envía.
    id_especie: Optional[int] = None
    id_paquete_inferencia: Optional[int] = None
    fase_productiva: Optional[str] = None
    id_patologia: Optional[int] = None
    latencia_ms: Optional[int] = None
    fecha_inicio_ventana: Optional[datetime] = None
    fecha_fin_ventana: Optional[datetime] = None
    tiene_alerta_generada: bool = False

    @property
    def latencia_excedida(self) -> bool:
        return self.latencia_ms is not None and self.latencia_ms > LATENCIA_MAXIMA_MS
