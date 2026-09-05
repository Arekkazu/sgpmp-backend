"""Value object ``MotivoCorreccion`` — motivo obligatorio de una corrección (RF-78 E7).

Mínimo 20 caracteres (mismo criterio que ``JustificacionAnulacion``/
``JustificacionPrecio``), máximo 500 (tamaño de columna ``motivo_correccion``
en ``registro_suministro``/``provision_nic41``).
"""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError

MIN_LONGITUD = 20
MAX_LONGITUD = 500


@dataclass(frozen=True)
class MotivoCorreccion:
    """Motivo de corrección validado (mínimo 20, máximo 500 caracteres)."""

    valor: str

    def __post_init__(self) -> None:
        texto = (self.valor or "").strip()
        if len(texto) < MIN_LONGITUD:
            raise ValidationError(
                code="MOTIVO_CORRECCION_INSUFICIENTE",
                message=(
                    f"El motivo de la corrección debe tener al menos {MIN_LONGITUD} "
                    "caracteres. Describa la razón del ajuste con mayor detalle."
                ),
                field="motivo_correccion",
            )
        if len(texto) > MAX_LONGITUD:
            raise ValidationError(
                code="MOTIVO_CORRECCION_MUY_LARGO",
                message=f"El motivo de la corrección no puede superar los {MAX_LONGITUD} caracteres.",
                field="motivo_correccion",
            )
        object.__setattr__(self, "valor", texto)
