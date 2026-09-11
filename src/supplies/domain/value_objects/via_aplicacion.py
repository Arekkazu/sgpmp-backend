"""Value object ``ViaAplicacion`` — vía de administración del medicamento (RF-76).

RF-76 (Restricción 2) define seis vías: ORAL, INTRAMUSCULAR, INTRAVENOSA,
SUBCUTANEA, TOPICA, INTRAMAMARIA. El enum de la BD
(``modulo5.enum_registro_medicamenti_via_aplicacion``) usa códigos cortos para
tres de ellas (IM, IV, SC) y valores propios para el resto. Este VO acepta el
vocabulario del RF (o los códigos cortos de la BD) y expone ``codigo_bd`` para
la persistencia.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError

# Vocabulario RF (y códigos cortos de la BD) → código almacenado en la BD.
_ALIAS_A_CODIGO_BD: dict[str, str] = {
    "ORAL": "ORAL",
    "INTRAMUSCULAR": "IM",
    "IM": "IM",
    "INTRAVENOSA": "IV",
    "IV": "IV",
    "SUBCUTANEA": "SC",
    "SC": "SC",
    "TOPICA": "TOPICA",
    "INTRAMAMARIA": "INTRAMAMARIA",
}

_VIAS_VALIDAS = "ORAL, INTRAMUSCULAR, INTRAVENOSA, SUBCUTANEA, TOPICA, INTRAMAMARIA"


@dataclass(frozen=True)
class ViaAplicacion:
    """Vía de administración validada contra el dominio permitido por RF-76."""

    valor: str

    def __post_init__(self) -> None:
        normalizado = (self.valor or "").strip().upper()
        if normalizado not in _ALIAS_A_CODIGO_BD:
            raise ValidationError(
                code="VIA_ADMINISTRACION_INVALIDA",
                message=(
                    "La vía de administración no es válida. Valores permitidos: "
                    f"{_VIAS_VALIDAS}."
                ),
                field="via_administracion",
            )
        object.__setattr__(self, "valor", normalizado)

    @property
    def codigo_bd(self) -> str:
        """Código tal como se almacena en el enum de la BD (ORAL/IM/IV/SC/...)."""
        return _ALIAS_A_CODIGO_BD[self.valor]
