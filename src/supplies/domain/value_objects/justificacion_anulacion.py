"""Value object ``JustificacionAnulacion`` — motivo obligatorio de una anulación.

RF-75 (Entradas / E6) y RF-76 (Restricción 5 / E9) exigen un mínimo de 20
caracteres. El CHECK de la BD (``chk_consumo_anulacion`` / ``chk_medicamento_anulacion``)
refuerza la misma cota. El máximo es 255 (tamaño de columna).
"""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError

MIN_LONGITUD = 20
MAX_LONGITUD = 255


@dataclass(frozen=True)
class JustificacionAnulacion:
    """Justificación de anulación validada (mínimo 20, máximo 255 caracteres)."""

    valor: str

    def __post_init__(self) -> None:
        texto = (self.valor or "").strip()
        if len(texto) < MIN_LONGITUD:
            raise ValidationError(
                code="JUSTIFICACION_INSUFICIENTE",
                message=(
                    f"La justificación de anulación debe tener al menos {MIN_LONGITUD} "
                    "caracteres. Describa el motivo de la anulación con mayor detalle."
                ),
                field="justificacion_anulacion",
            )
        if len(texto) > MAX_LONGITUD:
            raise ValidationError(
                code="JUSTIFICACION_MUY_LARGA",
                message=f"La justificación de anulación no puede superar los {MAX_LONGITUD} caracteres.",
                field="justificacion_anulacion",
            )
        object.__setattr__(self, "valor", texto)
