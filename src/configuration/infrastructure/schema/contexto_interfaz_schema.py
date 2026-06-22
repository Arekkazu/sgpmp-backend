"""Schema de respuesta para el contexto adaptativo de interfaz (RF-25)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ContextoInterfazResponse(BaseModel):
    id_usuario: int
    nombre_completo: str
    id_rol: int
    nombre_rol: str
    id_finca: Optional[int]
    finca_activa: Optional[str]
    departamento: Optional[str]
    especies_configuradas: list[str]
    modulos_autorizados: list[str]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, entity) -> ContextoInterfazResponse:
        return cls(
            id_usuario=entity.id_usuario,
            nombre_completo=entity.nombre_completo,
            id_rol=entity.id_rol,
            nombre_rol=entity.nombre_rol,
            id_finca=entity.id_finca,
            finca_activa=entity.finca_activa,
            departamento=entity.departamento,
            especies_configuradas=entity.especies_configuradas,
            modulos_autorizados=entity.modulos_autorizados,
        )
