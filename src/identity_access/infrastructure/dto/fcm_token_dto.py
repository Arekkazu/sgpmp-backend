"""DTO de entrada para el registro de tokens FCM de dispositivos móviles."""
from pydantic import Field
from src.shared.base_dto import BaseDTO


class FcmTokenDTO(BaseDTO):
    """Token FCM del dispositivo a registrar para recibir notificaciones push."""

    token: str = Field(..., min_length=1, max_length=500)
