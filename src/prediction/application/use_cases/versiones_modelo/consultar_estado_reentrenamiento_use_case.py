# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71: aviso de datos insuficientes para reentrenar el modelo individual |
"""RF-71: ¿tiene cada modelo individual retroalimentaciones suficientes para reentrenarse?

Por debajo del mínimo de solicitud (200 por defecto) se avisa que faltan datos; desde ahí se
puede solicitar, y desde el mínimo de RF-71 (500) se cumple la precondición del reentrenamiento.
Los dos mínimos se configuran en M09 (``/configuracion/parametros-retroalimentacion``); sin
configurar, valen el valor base.
"""
from __future__ import annotations

from src.configuration.domain.entities.parametro_mlops import (
    RF71_MIN_REENTRENAMIENTO,
    RF71_MIN_REENTRENAMIENTO_BASE,
    RF71_MIN_SOLICITUD,
    RF71_MIN_SOLICITUD_BASE,
    numero_configurado,
)
from src.configuration.domain.repositories.parametros_mlops_port import ParametrosMLOpsPort
from src.prediction.domain.entities.estado_reentrenamiento import (
    TIPOS_MODELO_INDIVIDUAL,
    EstadoReentrenamiento,
)
from src.prediction.domain.repositories.retroalimentacion_clinica_repository import (
    RetroalimentacionClinicaRepository,
)


class ConsultarEstadoReentrenamientoUseCase:
    def __init__(
        self, *, retroalimentacion_repo: RetroalimentacionClinicaRepository, parametros_port: ParametrosMLOpsPort
    ) -> None:
        self._retro = retroalimentacion_repo
        self._parametros = parametros_port

    def execute(self) -> list[EstadoReentrenamiento]:
        parametros = self._parametros.obtener([RF71_MIN_SOLICITUD, RF71_MIN_REENTRENAMIENTO])

        def minimo(nombre: str, base: int) -> int:
            if nombre not in parametros:
                return base
            return numero_configurado(parametros, nombre, minimo=1, entero=True)

        solicitud = minimo(RF71_MIN_SOLICITUD, RF71_MIN_SOLICITUD_BASE)
        reentrenamiento = minimo(RF71_MIN_REENTRENAMIENTO, RF71_MIN_REENTRENAMIENTO_BASE)
        conteos = self._retro.contar_nuevas_por_tipo_modelo(list(TIPOS_MODELO_INDIVIDUAL))
        return [
            EstadoReentrenamiento(tipo, *conteos.get(tipo, (0, None)), solicitud, reentrenamiento)
            for tipo in TIPOS_MODELO_INDIVIDUAL
        ]
