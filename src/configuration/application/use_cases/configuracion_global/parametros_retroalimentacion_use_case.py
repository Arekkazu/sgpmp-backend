# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ventana de retroalimentación desde M09     |
"""Ventana de retroalimentación de RF-72, configurable por el administrador desde M09.

Antes solo se cargaba con ``scripts/configurar_parametros_dev14.py``. El rango 7..365 lo
valida DEV-14 (``ConfigurarParametrosMLOpsUseCase``) y RF-72 lo lee en cada registro.
"""
from __future__ import annotations

from src.configuration.application.use_cases.configuracion_global.parametros_alertas_use_case import (
    ParametrosAlertasUseCase,
)
from src.configuration.domain.entities.parametro_mlops import RF72_VENTANA

PARAMETROS_RETROALIMENTACION = {
    # Sin valor base: RF-72 falla expresamente si el parámetro no está sembrado (DEV-14).
    RF72_VENTANA: (None, "Días calendario desde la inferencia para registrar retroalimentación (7 a 365)"),
}


class ParametrosRetroalimentacionUseCase(ParametrosAlertasUseCase):
    catalogo = PARAMETROS_RETROALIMENTACION
    codigo_invalido, rf = "PARAMETRO_RETROALIMENTACION_INVALIDO", "RF-72"
