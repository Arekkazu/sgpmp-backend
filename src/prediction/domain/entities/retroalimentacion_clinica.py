from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.shared.errors import BusinessRuleError, ValidationError

_ESTADOS_VALIDOS = frozenset({"CORRECTO", "PARCIAL", "INCORRECTO", "SIN_EVENTO"})
_ESTADOS_CON_DIAGNOSTICO = frozenset({"PARCIAL", "INCORRECTO"})
_FUENTES_VALIDAS = frozenset({"OBSERVACION_DIRECTA", "LABORATORIO", "HISTORIAL_CLINICO", "OTRO"})
_MAX_DIAGNOSTICOS = 3


@dataclass(eq=False)
class RetroalimentacionClinica:
    id_resultado_inferencia: uuid.UUID
    id_activo_biologico: int
    estado_retroalimentacion: str
    diagnosticos_reales: Optional[list[int]]
    fuente_diagnostico: Optional[str]
    es_fuente_desconocida: bool
    es_conflicto_retroalimentacion: bool
    observaciones_clinicas: Optional[str]
    id_usuario_veterinario: int
    estado_registro: str

    id_retroalimentacion: Optional[uuid.UUID] = None
    fecha_retroalimentacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        id_resultado_inferencia: uuid.UUID,
        id_activo_biologico: int,
        estado_retroalimentacion: str,
        diagnosticos_reales: Optional[list[int]],
        fuente_diagnostico: Optional[str],
        observaciones_clinicas: Optional[str],
        id_usuario_veterinario: int,
        es_conflicto_retroalimentacion: bool = False,
    ) -> "RetroalimentacionClinica":
        estado = estado_retroalimentacion.upper() if estado_retroalimentacion else ""
        if estado not in _ESTADOS_VALIDOS:
            raise BusinessRuleError(
                code="ESTADO_RETROALIMENTACION_INVALIDO",
                message="El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO.",
                field="estado_retroalimentacion",
            )

        diags = diagnosticos_reales or []
        if len(diags) > _MAX_DIAGNOSTICOS:
            raise ValidationError(
                code="DEMASIADOS_DIAGNOSTICOS",
                message=f"Se permiten máximo {_MAX_DIAGNOSTICOS} diagnósticos reales.",
                field="diagnosticos_reales",
            )

        fuente = fuente_diagnostico.upper() if fuente_diagnostico else None
        if fuente is not None and fuente not in _FUENTES_VALIDAS:
            raise ValidationError(
                code="FUENTE_DIAGNOSTICO_INVALIDA",
                message="El valor de fuente_diagnostico no es válido. Valores permitidos: OBSERVACION_DIRECTA, LABORATORIO, HISTORIAL_CLINICO, OTRO.",
                field="fuente_diagnostico",
            )

        # FA-12: sin fuente pero con diagnóstico obligatorio → fuente_desconocida
        requiere_diagnostico = estado in _ESTADOS_CON_DIAGNOSTICO
        es_fuente_desconocida = requiere_diagnostico and bool(diags) and fuente is None

        return cls(
            id_resultado_inferencia=id_resultado_inferencia,
            id_activo_biologico=id_activo_biologico,
            estado_retroalimentacion=estado,
            diagnosticos_reales=diags if diags else None,
            fuente_diagnostico=fuente,
            es_fuente_desconocida=es_fuente_desconocida,
            es_conflicto_retroalimentacion=es_conflicto_retroalimentacion,
            observaciones_clinicas=observaciones_clinicas,
            id_usuario_veterinario=id_usuario_veterinario,
            estado_registro="ACTIVO",
        )

    def _snapshot(self) -> dict:
        return {
            "id_retroalimentacion": str(self.id_retroalimentacion),
            "id_resultado_inferencia": str(self.id_resultado_inferencia),
            "id_activo_biologico": self.id_activo_biologico,
            "estado_retroalimentacion": self.estado_retroalimentacion,
            "diagnosticos_reales": self.diagnosticos_reales,
            "fuente_diagnostico": self.fuente_diagnostico,
            "es_fuente_desconocida": self.es_fuente_desconocida,
            "es_conflicto_retroalimentacion": self.es_conflicto_retroalimentacion,
            "id_usuario_veterinario": self.id_usuario_veterinario,
            "fecha_retroalimentacion": (
                self.fecha_retroalimentacion.isoformat() if self.fecha_retroalimentacion else None
            ),
        }
