from pydantic import Field
from src.shared.base_dto import BaseDTO


class FcmTokenDTO(BaseDTO):
    token: str = Field(..., min_length=1, max_length=500)
