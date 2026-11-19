# | Fecha      | Nombre   | Que se hizo                                                |
# |------------|----------|------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-107 RNF-03: validación del catálogo de mensajes      |
"""RF-107 RNF-03 — catálogo de mensajes de error: reglas de cada entrada (sin BD)."""
from __future__ import annotations

import pytest

from src.configuration.domain.entities.mensaje_error import MensajeError
from src.shared.errors import ValidationError


def test_mensaje_con_boton_hacia_una_pantalla_del_sistema():
    m = MensajeError("PERIODO_NO_CERRADO", "es-CO", "  El período no está cerrado.  ", "Ir al cierre", "/finanzas/")
    assert m.mensaje == "El período no está cerrado." and m.ruta_accion == "finanzas"


@pytest.mark.parametrize("datos", [
    {"clave": "periodo", "idioma": "es-CO", "mensaje": "Texto válido"},
    {"clave": "CLAVE", "idioma": "fr-FR", "mensaje": "Texto válido"},
    {"clave": "CLAVE", "idioma": "es-CO", "mensaje": "corto"[:4]},
    {"clave": "CLAVE", "idioma": "es-CO", "mensaje": "Texto válido", "texto_accion": "Ir"},
    {"clave": "CLAVE", "idioma": "es-CO", "mensaje": "Texto válido", "texto_accion": "Ir",
     "ruta_accion": "https://malicioso.example.com"},
])
def test_entradas_invalidas_responden_400(datos):
    with pytest.raises(ValidationError):
        MensajeError(**datos)
