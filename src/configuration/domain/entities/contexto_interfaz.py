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
