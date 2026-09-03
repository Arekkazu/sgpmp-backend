"""Read-model ``AccesibilidadVisual`` — contraste WCAG 2.1 AA de la identidad visual.

RF-27 declara como requisito no funcional de accesibilidad que los temas garanticen
"una relación de contraste mínima de 4.5:1 entre texto y fondo, conforme al estándar
WCAG 2.1 nivel AA", y su flujo alterno *Incompatibilidad de contraste con Identidad
Visual (RF-26)* lo convierte en comportamiento observable: detectar el incumplimiento,
avisar al usuario y aplicar "una variante aclarada/oscurecida automáticamente".

El color institucional lo define RF-26 y el fondo lo define el tema de RF-27, así que
ninguno de los dos agregados puede resolver esto por su cuenta: este read-model es el
punto donde se cruzan. No se persiste — se calcula al leer, porque depende de constantes
de presentación que pueden cambiar sin que cambie el dato guardado.

Se evalúan **los dos temas**, no solo el activo: con ``theme_mode = 3`` (Sistema) el tema
efectivo cambia en el cliente sin que haya una petición nueva de por medio.

El aviso es **por tema**, no global. No es un detalle de forma: los dos fondos están en
extremos opuestos de la escala (blanco tiene luminancia 1.0; la superficie oscura, 0.009),
así que alcanzar 4.5:1 contra el claro exige luminancia <= 0.175 y contra el oscuro
>= 0.214. **Ningún color cumple en los dos a la vez.** Un aviso global estaría encendido
para cualquier color que un administrador pudiera elegir y la interfaz aprendería a
ignorarlo. El RF ya lo dice así: el color "tiene bajo contraste en el modo seleccionado".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.configuration.domain.value_objects.color_hex import (
    FONDO_CLARO,
    FONDO_OSCURO,
    RATIO_MINIMO_AA,
    ColorHex,
    ajustar_para_contraste,
    ratio_contraste,
)

# Texto literal del flujo alterno de RF-27.
_AVISO = (
    "Aviso de accesibilidad: El color institucional configurado tiene bajo contraste "
    "en el modo {tema}. Se aplicará una variante aclarada/oscurecida automáticamente "
    "para garantizar la legibilidad."
)

_TEMAS = (("claro", FONDO_CLARO), ("oscuro", FONDO_OSCURO))


@dataclass(frozen=True)
class ContrasteTema:
    """Evaluación de un color contra el fondo de un tema.

    ``aviso`` trae el texto del flujo alterno de RF-27 cuando no se cumple AA, y ``None``
    cuando sí — para que el cliente lo muestre sin decidir por su cuenta qué redactar.
    """

    fondo: str
    ratio: float
    cumple_aa: bool
    color_ajustado: str
    aviso: Optional[str]


@dataclass(frozen=True)
class ContrasteColor:
    """El mismo color evaluado en los dos temas."""

    claro: ContrasteTema
    oscuro: ContrasteTema


@dataclass(frozen=True)
class AccesibilidadVisual:
    minimo_aa: float
    primary_color: Optional[ContrasteColor]
    secondary_color: Optional[ContrasteColor]


def _evaluar_color(color: ColorHex) -> ContrasteColor:
    evaluaciones: dict[str, ContrasteTema] = {}
    for tema, fondo_hex in _TEMAS:
        fondo = ColorHex(fondo_hex)
        ratio = ratio_contraste(color, fondo)
        cumple = ratio >= RATIO_MINIMO_AA
        evaluaciones[tema] = ContrasteTema(
            fondo=fondo_hex,
            # Dos decimales: es una relación para mostrar y comparar contra 4.5, no una
            # medida de precisión. Redondear aquí evita que cada cliente lo haga distinto.
            ratio=round(ratio, 2),
            cumple_aa=cumple,
            color_ajustado=str(ajustar_para_contraste(color, fondo)),
            aviso=None if cumple else _AVISO.format(tema=tema),
        )
    return ContrasteColor(claro=evaluaciones["claro"], oscuro=evaluaciones["oscuro"])


def evaluar(
    primary_color: Optional[ColorHex],
    secondary_color: Optional[ColorHex],
) -> AccesibilidadVisual:
    """Evalúa los colores institucionales de una finca. Acepta ``None`` en ambos.

    Las columnas ``primary_color`` y ``secondary_color`` son nullable en BD, así que una
    identidad visual puede existir con solo logotipo y nombre. En ese caso no hay nada
    que evaluar y el bloque se devuelve vacío en vez de fallar.
    """
    return AccesibilidadVisual(
        minimo_aa=RATIO_MINIMO_AA,
        primary_color=_evaluar_color(primary_color) if primary_color else None,
        secondary_color=_evaluar_color(secondary_color) if secondary_color else None,
    )
