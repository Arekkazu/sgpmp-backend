# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-78 E2: justificación faltante → 422    |
"""Value object ``JustificacionPrecio`` — justificación obligatoria de un precio manual.

RF-78 Restricción 10 / E2: obligatoria cuando ``origen_precio=MANUAL`` (no hay
integración M40 en este sistema — decisión ya tomada en CU-01 — así que todo
registro directo de SERVICIO_VETERINARIO/INSEMINACION la exige). Mínimo 20
caracteres, mismo criterio que ``JustificacionAnulacion``; máximo 500 (tamaño
de columna ``justificacion_precio``/``motivo_correccion``). Sin justificación
válida responde 422 con el mensaje de E2.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import BusinessRuleError

MIN_LONGITUD = 20
MAX_LONGITUD = 500


@dataclass(frozen=True)
class JustificacionPrecio:
    """Justificación de precio manual validada (mínimo 20, máximo 500 caracteres)."""

    valor: str | None

    def __post_init__(self) -> None:
        texto = (self.valor or "").strip()
        if len(texto) < MIN_LONGITUD:
            raise BusinessRuleError(
                code="JUSTIFICACION_PRECIO_REQUERIDA",
                message=(
                    "Se requiere justificación_precio cuando el precio no proviene de M40 con antigüedad "
                    f"≤ 30 días (mínimo {MIN_LONGITUD} caracteres)."
                ),
                field="justificacion_precio",
            )
        if len(texto) > MAX_LONGITUD:
            raise BusinessRuleError(
                code="JUSTIFICACION_PRECIO_MUY_LARGA",
                message=f"La justificación del precio no puede superar los {MAX_LONGITUD} caracteres.",
                field="justificacion_precio",
            )
        object.__setattr__(self, "valor", texto)
