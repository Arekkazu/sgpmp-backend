"""Value object ``JustificacionPrecio`` — justificación obligatoria de un precio manual.

RF-78 Restricción 10 / E2: obligatoria cuando ``origen_precio=MANUAL`` (no hay
integración M40 en este sistema — decisión ya tomada en CU-01 — así que todo
registro directo de SERVICIO_VETERINARIO/INSEMINACION la exige). Mínimo 20
caracteres, mismo criterio que ``JustificacionAnulacion``; máximo 500 (tamaño
de columna ``justificacion_precio``/``motivo_correccion``).
"""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError

MIN_LONGITUD = 20
MAX_LONGITUD = 500


@dataclass(frozen=True)
class JustificacionPrecio:
    """Justificación de precio manual validada (mínimo 20, máximo 500 caracteres)."""

    valor: str

    def __post_init__(self) -> None:
        texto = (self.valor or "").strip()
        if len(texto) < MIN_LONGITUD:
            raise ValidationError(
                code="JUSTIFICACION_PRECIO_INSUFICIENTE",
                message=(
                    f"La justificación del precio debe tener al menos {MIN_LONGITUD} "
                    "caracteres. Se requiere cuando el precio no proviene de M40 con "
                    "antigüedad <= 30 días."
                ),
                field="justificacion_precio",
            )
        if len(texto) > MAX_LONGITUD:
            raise ValidationError(
                code="JUSTIFICACION_PRECIO_MUY_LARGA",
                message=f"La justificación del precio no puede superar los {MAX_LONGITUD} caracteres.",
                field="justificacion_precio",
            )
        object.__setattr__(self, "valor", texto)
