# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-53: guarda la captura de una ventana de visión                |
"""La cámara se valida igual que en la ingesta del sobre D4 (serial del topic, activa, de tipo
cámara y en el área que dice); la imagen solo se guarda en disco con las más recientes."""
from __future__ import annotations

import base64
import binascii

from src.shared.almacen_capturas import guardar_captura
from src.shared.errors import AuthenticationError, BusinessRuleError, ValidationError
from src.telemetry.domain.repositories.dispositivo_port import DispositivoPort
from src.telemetry.infrastructure.dto.captura_vision_dto import CapturaVisionDTO


class IngerirCapturaVisionUseCase:

    def __init__(self, dispositivo_port: DispositivoPort) -> None:
        self.dispositivo_port = dispositivo_port

    def execute(self, dto: CapturaVisionDTO) -> int:
        camara = self.dispositivo_port.obtener_camara_por_serial(dto.serial)
        if camara is None or not camara.es_activo:
            raise AuthenticationError(code="ERROR_AUTENTICACION",
                                      message="El dispositivo no existe o no está en estado ACTIVO.")
        if not camara.es_camara:
            raise BusinessRuleError(code="DISPOSITIVO_NO_ES_CAMARA",
                                    message=f"El dispositivo {camara.id_dispositivo_iot} no es una cámara de visión.",
                                    field="serial")
        if camara.id_infraestructura != dto.area_id:
            raise BusinessRuleError(code="AREA_NO_COINCIDE",
                                    message=f"La cámara {camara.id_dispositivo_iot} no está asociada al área {dto.area_id}.",
                                    field="area_id")
        try:
            jpeg = base64.b64decode(dto.imagen_jpeg_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ValidationError(code="CAPTURA_INVALIDA", message="La captura no es base64 válido.",
                                  field="imagen_jpeg_base64")
        guardar_captura(camara.id_dispositivo_iot, dto.ventana_fin, dto.n_individuos_observados, jpeg)
        return camara.id_dispositivo_iot
