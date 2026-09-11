"""RF-26 / RF-27 — Contraste WCAG 2.1 nivel AA del color institucional.

RF-27 declara como requisito no funcional de accesibilidad que los temas garanticen
"una relación de contraste mínima de 4.5:1 entre texto y fondo, conforme al estándar
WCAG 2.1 nivel AA", y su flujo alterno *Incompatibilidad de contraste con Identidad
Visual (RF-26)* lo vuelve comportamiento observable: detectar que el color institucional
no cumple sobre el fondo del tema, avisar, y aplicar "una variante aclarada/oscurecida
automáticamente para garantizar la legibilidad".

Antes de este cambio no existía nada de eso: `ColorHex` validaba el formato con una
expresión regular y nada más, así que un administrador podía fijar `#FFFFFF` como color
primario y el sistema lo aceptaba sin objeción — blanco sobre blanco.

Verifica con fakes (sin BD; modulo9 no existe en la BD `pruebas`).
"""
from __future__ import annotations

import pytest

from src.configuration.domain.entities import accesibilidad_visual
from src.configuration.domain.value_objects.color_hex import (
    FONDO_CLARO,
    FONDO_OSCURO,
    RATIO_MINIMO_AA,
    ColorHex,
    ajustar_para_contraste,
    ratio_contraste,
)

# Colores institucionales reales sembrados en dev (modulo9.identidad_visuales).
REMANSO_PRIMARIO = "#1A6B3C"    # verde oscuro: cumple en claro, falla en oscuro
REMANSO_SECUNDARIO = "#A8D5B5"  # verde claro: falla en claro, cumple en oscuro


# ---- La fórmula de WCAG 2.1 ---- #

def test_luminancia_de_los_extremos_es_la_de_la_especificacion() -> None:
    """Ancla la fórmula: si la conversión sRGB se rompe, todo lo demás miente en silencio."""
    assert ColorHex("#000000").luminancia_relativa() == pytest.approx(0.0)
    assert ColorHex("#FFFFFF").luminancia_relativa() == pytest.approx(1.0)


def test_contraste_maximo_es_21_a_1() -> None:
    """Blanco sobre negro es el tope teórico de la escala WCAG."""
    assert ratio_contraste(ColorHex("#FFFFFF"), ColorHex("#000000")) == pytest.approx(21.0)


def test_contraste_de_un_color_consigo_mismo_es_1_a_1() -> None:
    """El caso que el RF quiere impedir: texto invisible sobre su propio fondo."""
    assert ratio_contraste(ColorHex("#1A6B3C"), ColorHex("#1A6B3C")) == pytest.approx(1.0)


def test_el_ratio_no_depende_del_orden_de_los_argumentos() -> None:
    """WCAG define la relación entre el más claro y el más oscuro, no entre texto y fondo."""
    uno, otro = ColorHex(REMANSO_PRIMARIO), ColorHex(FONDO_CLARO)
    assert ratio_contraste(uno, otro) == pytest.approx(ratio_contraste(otro, uno))


# ---- El ajuste automático que pide el flujo alterno ---- #

def test_un_color_que_ya_cumple_se_devuelve_intacto() -> None:
    """Ajustar lo que ya es legible desdibujaría la marca sin ganar accesibilidad."""
    color, fondo = ColorHex(REMANSO_PRIMARIO), ColorHex(FONDO_CLARO)
    assert ratio_contraste(color, fondo) >= RATIO_MINIMO_AA
    assert ajustar_para_contraste(color, fondo) == color


def test_color_oscuro_sobre_fondo_oscuro_se_aclara_hasta_cumplir() -> None:
    """El escenario textual del flujo alterno de RF-27: modo oscuro + color institucional."""
    color, fondo = ColorHex(REMANSO_PRIMARIO), ColorHex(FONDO_OSCURO)
    assert ratio_contraste(color, fondo) < RATIO_MINIMO_AA

    ajustado = ajustar_para_contraste(color, fondo)
    assert ajustado != color
    assert ratio_contraste(ajustado, fondo) >= RATIO_MINIMO_AA
    assert ajustado.luminancia_relativa() > color.luminancia_relativa()


def test_color_claro_sobre_fondo_claro_se_oscurece_hasta_cumplir() -> None:
    """La dirección contraria: el color de apoyo de la misma finca, en modo claro."""
    color, fondo = ColorHex(REMANSO_SECUNDARIO), ColorHex(FONDO_CLARO)
    assert ratio_contraste(color, fondo) < RATIO_MINIMO_AA

    ajustado = ajustar_para_contraste(color, fondo)
    assert ratio_contraste(ajustado, fondo) >= RATIO_MINIMO_AA
    assert ajustado.luminancia_relativa() < color.luminancia_relativa()


@pytest.mark.parametrize(
    "hex_color",
    ["#FFFFFF", "#000000", "#1A6B3C", "#A8D5B5", "#0D4E8A", "#82B4D8", "#007B8A", "#4A7C2F"],
)
@pytest.mark.parametrize("fondo_hex", [FONDO_CLARO, FONDO_OSCURO])
def test_el_ajuste_nunca_empeora_el_contraste(hex_color: str, fondo_hex: str) -> None:
    """Invariante de seguridad: pase lo que pase, la variante no es menos legible.

    Cubre los casos límite en los que no hay margen para mover la luminosidad
    (blanco puro, negro puro) y los seis colores sembrados en dev.
    """
    color, fondo = ColorHex(hex_color), ColorHex(fondo_hex)
    ajustado = ajustar_para_contraste(color, fondo)
    assert ratio_contraste(ajustado, fondo) >= ratio_contraste(color, fondo)


@pytest.mark.parametrize("hex_color", ["#FFFFFF", "#000000", "#1A6B3C", "#A8D5B5"])
@pytest.mark.parametrize("fondo_hex", [FONDO_CLARO, FONDO_OSCURO])
def test_la_variante_sigue_siendo_un_color_hexadecimal_valido(hex_color: str, fondo_hex: str) -> None:
    """El ajustado viaja al cliente como CSS: un valor fuera de rango rompería la interfaz."""
    ajustado = ajustar_para_contraste(ColorHex(hex_color), ColorHex(fondo_hex))
    assert ColorHex(ajustado.valor) == ajustado  # revalida contra la regex del value object


def test_blanco_puro_como_color_primario_deja_de_ser_invisible() -> None:
    """El caso que hoy el formulario acepta sin objetar: `#FFFFFF` sobre fondo blanco."""
    ajustado = ajustar_para_contraste(ColorHex("#FFFFFF"), ColorHex(FONDO_CLARO))
    assert ratio_contraste(ajustado, ColorHex(FONDO_CLARO)) >= RATIO_MINIMO_AA


# ---- El read-model que se expone en la API ---- #

def test_evaluar_reporta_los_dos_temas_para_cada_color() -> None:
    """Se devuelven las dos variantes, no solo la del tema resuelto.

    Con `theme_mode = 3` (Sistema) el tema efectivo cambia en el cliente sin que haya
    una petición nueva de por medio; si solo viajara la variante activa, el cambio de
    tema del sistema operativo dejaría la interfaz con el color equivocado.
    """
    resultado = accesibilidad_visual.evaluar(
        ColorHex(REMANSO_PRIMARIO), ColorHex(REMANSO_SECUNDARIO)
    )

    assert resultado.minimo_aa == RATIO_MINIMO_AA
    assert resultado.primary_color.claro.fondo == FONDO_CLARO
    assert resultado.primary_color.oscuro.fondo == FONDO_OSCURO
    assert resultado.primary_color.claro.cumple_aa is True
    assert resultado.primary_color.oscuro.cumple_aa is False
    assert resultado.secondary_color.claro.cumple_aa is False
    assert resultado.secondary_color.oscuro.cumple_aa is True


def test_el_aviso_usa_el_texto_del_flujo_alterno_de_rf27() -> None:
    """El mensaje es contrato con la interfaz: el RF lo especifica palabra por palabra."""
    resultado = accesibilidad_visual.evaluar(ColorHex(REMANSO_PRIMARIO), None)

    assert resultado.primary_color.oscuro.aviso == (
        "Aviso de accesibilidad: El color institucional configurado tiene bajo contraste "
        "en el modo oscuro. Se aplicará una variante aclarada/oscurecida automáticamente "
        "para garantizar la legibilidad."
    )


def test_el_tema_que_cumple_no_lleva_aviso() -> None:
    """Contraprueba: si el aviso fuera incondicional, la interfaz lo mostraría siempre."""
    resultado = accesibilidad_visual.evaluar(ColorHex(REMANSO_PRIMARIO), None)

    assert resultado.primary_color.claro.cumple_aa is True
    assert resultado.primary_color.claro.aviso is None


def test_ningun_color_cumple_aa_en_los_dos_temas_a_la_vez() -> None:
    """Por qué el aviso es por tema y no una lista global.

    Los dos fondos están en extremos opuestos de la escala: cumplir 4.5:1 contra el
    blanco exige luminancia <= 0.175 y contra la superficie oscura >= 0.214. La franja
    es vacía. Un aviso global estaría encendido para cualquier color elegible y la
    interfaz aprendería a ignorarlo. Si algún día el tema oscuro cambia de superficie y
    la franja se abre, esta prueba falla y avisa de que la decisión hay que revisarla.
    """
    claro, oscuro = ColorHex(FONDO_CLARO), ColorHex(FONDO_OSCURO)
    grises = (ColorHex(f"#{v:02X}{v:02X}{v:02X}") for v in range(256))

    assert not [
        gris.valor
        for gris in grises
        if ratio_contraste(gris, claro) >= RATIO_MINIMO_AA
        and ratio_contraste(gris, oscuro) >= RATIO_MINIMO_AA
    ]


def test_identidad_sin_colores_no_rompe_la_evaluacion() -> None:
    """`primary_color` y `secondary_color` son nullable en BD: puede haber solo logotipo."""
    resultado = accesibilidad_visual.evaluar(None, None)

    assert resultado.primary_color is None
    assert resultado.secondary_color is None
