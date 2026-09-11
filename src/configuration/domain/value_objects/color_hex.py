"""Value object ``ColorHex`` — color en formato hexadecimal de 6 dígitos (#RRGGBB).

Además del formato, este módulo resuelve el contraste WCAG 2.1 nivel AA que RF-27 pide
como requisito no funcional de accesibilidad ("relación de contraste mínima de 4.5:1
entre texto y fondo") y que su flujo alterno *Incompatibilidad de contraste con Identidad
Visual (RF-26)* convierte en comportamiento: cuando el color institucional no cumple el
mínimo sobre el fondo del tema activo, el sistema debe aplicar "una variante aclarada u
oscurecida automáticamente para garantizar la legibilidad".

``FONDO_CLARO`` y ``FONDO_OSCURO`` son constantes espejo de las superficies del frontend
(``--surface-card`` en ``src/shared/design-system/tokens.css``, tema claro y
``[data-theme="dark"]``). Si el tema oscuro cambia de superficie, este es el archivo a
tocar: el cálculo de contraste carece de sentido contra un fondo que no es el real.
"""
from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass

from src.shared.errors import ValidationError

_HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

# Superficies sobre las que se evalúa el color institucional (ver docstring).
FONDO_CLARO = "#FFFFFF"
FONDO_OSCURO = "#171A15"

# WCAG 2.1 nivel AA para texto normal.
RATIO_MINIMO_AA = 4.5

# Paso del barrido de luminosidad al buscar la variante accesible.
_PASO_LUMINOSIDAD = 0.01


@dataclass(frozen=True)
class ColorHex:
    valor: str

    def __post_init__(self) -> None:
        if not isinstance(self.valor, str) or not _HEX_RE.match(self.valor):
            raise ValidationError(
                code="COLOR_HEX_INVALIDO",
                message=(
                    f"El color debe estar en formato hexadecimal de 6 dígitos (ej. #3A7BD5). "
                    f"Valor recibido: '{self.valor}'."
                ),
                field="color",
            )

    def __str__(self) -> str:
        return self.valor

    def rgb(self) -> tuple[float, float, float]:
        """Canales R, G y B normalizados a 0.0–1.0."""
        crudo = self.valor.lstrip("#")
        return tuple(int(crudo[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]

    def luminancia_relativa(self) -> float:
        """Luminancia relativa según WCAG 2.1 (0.0 = negro, 1.0 = blanco)."""
        canales = [
            c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            for c in self.rgb()
        ]
        rojo, verde, azul = canales
        return 0.2126 * rojo + 0.7152 * verde + 0.0722 * azul

    @classmethod
    def desde_rgb(cls, rojo: float, verde: float, azul: float) -> "ColorHex":
        """Construye el value object desde canales normalizados 0.0–1.0."""
        octetos = (round(max(0.0, min(1.0, canal)) * 255) for canal in (rojo, verde, azul))
        return cls("#" + "".join(f"{octeto:02X}" for octeto in octetos))


def ratio_contraste(uno: ColorHex, otro: ColorHex) -> float:
    """Relación de contraste WCAG 2.1 entre dos colores. Va de 1.0 (idénticos) a 21.0."""
    luminancias = sorted((uno.luminancia_relativa(), otro.luminancia_relativa()))
    return (luminancias[1] + 0.05) / (luminancias[0] + 0.05)


def ajustar_para_contraste(
    color: ColorHex,
    fondo: ColorHex,
    minimo: float = RATIO_MINIMO_AA,
) -> ColorHex:
    """Devuelve una variante de ``color`` que alcanza ``minimo`` sobre ``fondo``.

    Si el color ya cumple se devuelve tal cual, de modo que quien consuma el resultado
    pueda usarlo sin condicionales. Si no cumple, se mueve la luminosidad HLS en la
    dirección que aleja del fondo —aclarar sobre fondo oscuro, oscurecer sobre fondo
    claro— conservando matiz y saturación, que es lo que mantiene reconocible la marca.
    """
    if ratio_contraste(color, fondo) >= minimo:
        return color

    # ponytail: barrido lineal de 1% sobre L (<=100 iteraciones, microsegundos). Si algún
    # día hace falta preservar el matiz con más fidelidad, el reemplazo es una búsqueda
    # binaria en OKLCH.
    rojo, verde, azul = color.rgb()
    matiz, luminosidad, saturacion = colorsys.rgb_to_hls(rojo, verde, azul)
    # Alejarse del fondo: aclarar sobre fondo oscuro, oscurecer sobre fondo claro.
    aclarar = fondo.luminancia_relativa() < 0.5
    paso = _PASO_LUMINOSIDAD if aclarar else -_PASO_LUMINOSIDAD

    mejor = color
    objetivo = luminosidad
    while 0.0 <= objetivo + paso <= 1.0:
        objetivo += paso
        candidato = ColorHex.desde_rgb(*colorsys.hls_to_rgb(matiz, objetivo, saturacion))
        mejor = candidato
        if ratio_contraste(candidato, fondo) >= minimo:
            return candidato

    # Se agotó el rango: queda el extremo alcanzado, que es el máximo contraste posible
    # conservando el matiz. Nunca se devuelve algo peor que el color original.
    return mejor if ratio_contraste(mejor, fondo) >= ratio_contraste(color, fondo) else color
