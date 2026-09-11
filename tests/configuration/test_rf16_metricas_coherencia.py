"""RF-16 — Coherencia unidad_medida ↔ tipo_medicion en métricas (FA-10).

Incluye la regresión del fix del bug: 'l' es una unidad válida para VOLUMEN.
"""
from __future__ import annotations

import pytest

from src.configuration.application.use_cases.metricas.registrar_metrica_use_case import (
    _validar_coherencia_unidad,
)
from src.configuration.domain.value_objects.aplica_tipo_activo import AplicaTipoActivo
from src.configuration.domain.value_objects.tipo_medicion import TipoMedicion
from src.shared.errors import BusinessRuleError, ValidationError


def test_peso_kg_ok():
    _validar_coherencia_unidad(TipoMedicion.PESO, "kg")  # no debe lanzar


def test_peso_litros_incoherente():
    with pytest.raises(BusinessRuleError) as exc:
        _validar_coherencia_unidad(TipoMedicion.PESO, "litros")
    assert exc.value.code == "UNIDAD_MEDIDA_INCOHERENTE"


def test_volumen_litro_abreviado_ok():
    # Regresión: antes 'l' no estaba en el conjunto de VOLUMEN y fallaba indebidamente.
    _validar_coherencia_unidad(TipoMedicion.VOLUMEN, "l")
    _validar_coherencia_unidad(TipoMedicion.VOLUMEN, "L")  # case-insensitive


def test_otro_acepta_cualquier_unidad():
    _validar_coherencia_unidad(TipoMedicion.OTRO, "lo-que-sea")


def test_tipo_medicion_invalido_rechazado():
    with pytest.raises(ValidationError):
        TipoMedicion.desde_string("BASURA")


def test_aplica_tipo_activo_invalido_rechazado():
    with pytest.raises(ValidationError):
        AplicaTipoActivo.desde_string("NINGUNO")
