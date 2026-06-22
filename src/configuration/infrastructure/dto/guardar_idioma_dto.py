"""DTO de entrada para guardar la preferencia de idioma (PATCH RF-29)."""
from src.shared.base_dto import BaseDTO


class GuardarIdiomaDTO(BaseDTO):
    locale_code: str
