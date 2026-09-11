"""Schema de respuesta para el contexto adaptativo de interfaz (RF-25)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from src.configuration.infrastructure.schema.accesibilidad_schema import AccesibilidadResponse


class IdentidadVisualContextoResponse(BaseModel):
    """Marca institucional de la finca activa, para pintar el shell de la aplicación.

    Es un subconjunto de ``IdentidadVisualResponse``: no lleva ids internos, versión ni
    autor, porque quien lee el contexto pinta la interfaz, no administra el registro.
    Editarlo sigue siendo exclusivo del recurso 23 (solo Administrador).
    """

    logo_path: Optional[str]
    primary_color: Optional[str]
    secondary_color: Optional[str]
    org_display_name: Optional[str]


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
    # `null` cuando el usuario no tiene finca asignada o la finca no tiene identidad
    # configurada: el cliente cae a su marca por defecto sin ningún caso especial.
    identidad_visual: Optional[IdentidadVisualContextoResponse]
    accesibilidad: Optional[AccesibilidadResponse]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, entity) -> ContextoInterfazResponse:
        identidad = entity.identidad_visual
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
            identidad_visual=(
                None
                if identidad is None
                else IdentidadVisualContextoResponse(
                    logo_path=identidad.logo_path,
                    primary_color=identidad.primary_color.valor if identidad.primary_color else None,
                    secondary_color=identidad.secondary_color.valor if identidad.secondary_color else None,
                    org_display_name=(
                        identidad.org_display_name.valor if identidad.org_display_name else None
                    ),
                )
            ),
            accesibilidad=AccesibilidadResponse.from_entity(entity.accesibilidad),
        )
