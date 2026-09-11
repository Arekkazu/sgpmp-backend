"""DTO de entrada para guardar la preferencia de idioma (PATCH RF-29)."""
from typing import Optional

from src.shared.base_dto import BaseDTO


class GuardarIdiomaDTO(BaseDTO):
    locale_code: str
    # Versión del perfil que el cliente recibió en el GET. Opcional: un cliente
    # que no la envíe se salta la comprobación de concurrencia en vez de fallar.
    version_perfil: Optional[int] = None
