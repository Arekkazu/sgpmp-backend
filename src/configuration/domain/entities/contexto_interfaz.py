"""Read-model ``ContextoInterfaz`` — contexto de la interfaz adaptativa del usuario (RF-25).

No es un agregado persistible. Se construye en el momento de la consulta
uniendo datos de usuarios, roles, fincas, especies y permisos.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.configuration.domain.entities.accesibilidad_visual import AccesibilidadVisual
from src.configuration.domain.entities.identidad_visual import IdentidadVisual


@dataclass
class ContextoInterfaz:
    id_usuario: int
    nombre_completo: str
    id_rol: int
    nombre_rol: str
    id_finca: Optional[int]
    finca_activa: Optional[str]
    departamento: Optional[str]
    especies_configuradas: list[str]
    modulos_autorizados: list[str]
    # Identidad visual de la finca activa (RF-26) y su contraste WCAG (RF-27).
    # Viajan aquí porque este es el único endpoint que todos los roles pueden leer
    # y el único que resuelve usuario -> finca: el recurso 23 es solo de
    # Administrador, así que ningún otro rol podría conocer su propia marca.
    identidad_visual: Optional[IdentidadVisual] = None
    accesibilidad: Optional[AccesibilidadVisual] = None
    # Áreas productivas activas de la finca (RF-20). Solo interesa si hay o no:
    # junto con `especies_configuradas` decide el flujo alterno de abajo.
    tiene_infraestructura: bool = False

    @property
    def finca_sin_catalogo(self) -> bool:
        """RF-25, flujo alterno "Finca sin especies productivas configuradas".

        El RF lo define sobre las dos cosas a la vez —"no se han registrado
        especies (RF-15) **ni** infraestructura (RF-20)"—, así que una finca con
        áreas pero sin especies (o al revés) sigue teniendo contexto que pintar y
        responde 200. Solo la finca recién creada, sin nada configurado, es 204.
        """
        return (
            self.id_finca is not None
            and not self.especies_configuradas
            and not self.tiene_infraestructura
        )
