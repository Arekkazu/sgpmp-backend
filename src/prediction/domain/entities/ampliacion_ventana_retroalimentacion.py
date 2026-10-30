# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ampliación de ventana por resultado  |
"""Excepción justificada a la ventana de retroalimentación para un resultado (RF-72)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.shared.errors import BusinessRuleError

DIAS_MAXIMOS = 365


@dataclass
class AmpliacionVentanaRetroalimentacion:
    id_resultado_inferencia: uuid.UUID
    fecha_limite: datetime
    justificacion: str
    id_usuario_autorizador: int
    id_ampliacion_ventana_retroalimentacion: Optional[int] = None
    fecha_creacion: Optional[datetime] = None

    @classmethod
    def autorizar(
        cls, *, id_resultado_inferencia: uuid.UUID, dias_habilitados: int, justificacion: str,
        id_usuario_autorizador: int, ahora: datetime,
    ) -> "AmpliacionVentanaRetroalimentacion":
        """El resultado queda habilitado ``dias_habilitados`` días desde la autorización."""
        if not 1 <= dias_habilitados <= DIAS_MAXIMOS:
            raise BusinessRuleError(
                code="DIAS_AMPLIACION_INVALIDOS",
                message=f"Los días habilitados deben estar entre 1 y {DIAS_MAXIMOS}.",
                field="dias_habilitados",
            )
        return cls(
            id_resultado_inferencia=id_resultado_inferencia,
            fecha_limite=ahora + timedelta(days=dias_habilitados),
            justificacion=justificacion,
            id_usuario_autorizador=id_usuario_autorizador,
        )

    def _snapshot(self) -> dict:
        return {
            "id_ampliacion_ventana_retroalimentacion": self.id_ampliacion_ventana_retroalimentacion,
            "id_resultado_inferencia": str(self.id_resultado_inferencia),
            "fecha_limite": self.fecha_limite.isoformat(),
            "justificacion": self.justificacion,
            "id_usuario_autorizador": self.id_usuario_autorizador,
        }
