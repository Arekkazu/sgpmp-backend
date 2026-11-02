# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ventana de retroalimentación desde M09     |
# | 2026-10-31 | Arekkazu | RF-71: mínimos de registros para solicitar y reentrenar, desde M09 |
"""Ventana de retroalimentación de RF-72 y mínimos de RF-71, configurables desde M09.

Antes solo se cargaba con ``scripts/configurar_parametros_dev14.py``. El rango 7..365 lo
valida DEV-14 (``ConfigurarParametrosMLOpsUseCase``) y RF-72 lo lee en cada registro.

Los mínimos de RF-71 dicen cuántas retroalimentaciones nuevas hacen falta para solicitar
(200) y para ejecutar (500) el reentrenamiento del modelo individual.
"""
from __future__ import annotations

from src.configuration.application.use_cases.configuracion_global.parametros_alertas_use_case import (
    ParametrosAlertasUseCase,
)
from src.configuration.domain.entities.parametro_mlops import (
    RF71_MIN_REENTRENAMIENTO,
    RF71_MIN_REENTRENAMIENTO_BASE,
    RF71_MIN_SOLICITUD,
    RF71_MIN_SOLICITUD_BASE,
    RF72_VENTANA,
)

PARAMETROS_RETROALIMENTACION = {
    # Sin valor base: RF-72 falla expresamente si el parámetro no está sembrado (DEV-14).
    RF72_VENTANA: (None, "Días calendario desde la inferencia para registrar retroalimentación (7 a 365)"),
    RF71_MIN_SOLICITUD: (RF71_MIN_SOLICITUD_BASE,
                         "RF-71: retroalimentaciones nuevas desde las que se puede solicitar el reentrenamiento"),
    RF71_MIN_REENTRENAMIENTO: (RF71_MIN_REENTRENAMIENTO_BASE,
                               "RF-71: retroalimentaciones nuevas mínimas para ejecutar el reentrenamiento"),
}


class ParametrosRetroalimentacionUseCase(ParametrosAlertasUseCase):
    catalogo = PARAMETROS_RETROALIMENTACION
    codigo_invalido, rf = "PARAMETRO_RETROALIMENTACION_INVALIDO", "RF-72"
