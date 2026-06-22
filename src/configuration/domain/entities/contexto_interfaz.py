"""Read-model ``ContextoInterfaz`` — contexto de la interfaz adaptativa del usuario (RF-25).

No es un agregado persistible. Se construye en el momento de la consulta
uniendo datos de usuarios, roles, fincas, especies y permisos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


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
