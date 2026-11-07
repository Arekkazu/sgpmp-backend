# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-04 RF-60: parámetros de heartbeat por categoría y ventanas de visión de una cámara |
from __future__ import annotations

from typing import Optional

from src.shared.errors import NotFoundError, ValidationError
from src.telemetry.domain.entities.parametros_heartbeat_categoria import (
    ParametrosHeartbeatCategoria, ResumenVentanasVision, parametros_por_categoria, resumir_ventanas,
)
from src.telemetry.domain.repositories.parametros_heartbeat_categoria_port import ParametrosHeartbeatCategoriaPort

CANTIDAD_MAXIMA_VENTANAS = 50


class ConsultarParametrosHeartbeatUseCase:
    """AJF-04: solo lectura. La pantalla de dispositivos dejaba de usar valores quemados."""

    def __init__(self, port: ParametrosHeartbeatCategoriaPort) -> None:
        self._port = port

    def por_categoria(self) -> list[ParametrosHeartbeatCategoria]:
        return parametros_por_categoria(self._port.leer_configuracion())

    def ventanas_vision(self, id_dispositivo_iot: int, ids_fincas: Optional[list[int]], cantidad: int = 10) -> ResumenVentanasVision:
        if not 1 <= cantidad <= CANTIDAD_MAXIMA_VENTANAS:
            raise ValidationError(code='CANTIDAD_INVALIDA',
                                  message=f'cantidad debe estar entre 1 y {CANTIDAD_MAXIMA_VENTANAS}.', field='cantidad')
        categoria = self._port.categoria_dispositivo(id_dispositivo_iot, ids_fincas)
        if categoria is None:
            raise NotFoundError(code='DISPOSITIVO_NO_ENCONTRADO', message='El dispositivo no existe o no está en tus fincas.')
        es_camara = categoria == 'CAMARA'
        ventanas = self._port.ventanas_recientes(id_dispositivo_iot, cantidad) if es_camara else []
        n, cobertura, duracion = self._port.parametros_ventanas()
        return resumir_ventanas(es_camara, ventanas, n, cobertura, duracion)
