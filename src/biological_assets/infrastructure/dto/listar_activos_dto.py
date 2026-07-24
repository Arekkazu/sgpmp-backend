from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from src.biological_assets.domain.value_objects.tipo_activo import TipoActivo
from src.shared.base_dto import BaseDTO

_TIPOS_VALIDOS = {t.value for t in TipoActivo}


class ListarActivosDTO(BaseDTO):
    tipo: Optional[str] = None
    id_especie: Optional[int] = None
    id_estado: Optional[int] = None
    id_infraestructura: Optional[int] = None
    pagina: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator('tipo', mode='before')
    @classmethod
    def validar_tipo(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).strip().upper()
        if v_str not in _TIPOS_VALIDOS:
            raise ValueError(
                f'Tipo inválido. Valores permitidos: {", ".join(sorted(_TIPOS_VALIDOS))}.'
            )
        return v_str
