"""Entidad de dominio ``IdentidadVisual`` — identidad visual institucional por finca (RF-26).

Una finca puede tener múltiples registros históricos; el activo es el de mayor ``version``.
La concurrencia optimista se controla con el campo ``version`` (entero).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.configuration.domain.value_objects.color_hex import ColorHex
from src.configuration.domain.value_objects.nombre_organizacion import NombreOrganizacion


@dataclass(eq=False)
class IdentidadVisual:
    id_finca: int
    id_usuario: int
    logo_path: Optional[str]
    primary_color: Optional[ColorHex]
    secondary_color: Optional[ColorHex]
    org_display_name: Optional[NombreOrganizacion]
    version: Optional[int]
    fecha_creacion: Optional[datetime]
    id_identidad_visual: Optional[int] = None

    @classmethod
    def crear(
        cls,
        *,
        id_finca: int,
        id_usuario: int,
        logo_path: Optional[str],
        primary_color: Optional[ColorHex],
        secondary_color: Optional[ColorHex],
        org_display_name: Optional[NombreOrganizacion],
    ) -> IdentidadVisual:
        return cls(
            id_finca=id_finca,
            id_usuario=id_usuario,
            logo_path=logo_path,
            primary_color=primary_color,
            secondary_color=secondary_color,
            org_display_name=org_display_name,
            version=1,
            fecha_creacion=datetime.now(timezone.utc),
        )

    def actualizar(
        self,
        *,
        id_usuario: int,
        logo_path: Optional[str],
        primary_color: Optional[ColorHex],
        secondary_color: Optional[ColorHex],
        org_display_name: Optional[NombreOrganizacion],
    ) -> None:
        self.id_usuario = id_usuario
        if logo_path is not None:
            self.logo_path = logo_path
        self.primary_color = primary_color
        self.secondary_color = secondary_color
        self.org_display_name = org_display_name
        self.version = (self.version or 0) + 1

    def _snapshot(self) -> dict:
        return {
            "id_finca": self.id_finca,
            "logo_path": self.logo_path,
            "primary_color": str(self.primary_color) if self.primary_color else None,
            "secondary_color": str(self.secondary_color) if self.secondary_color else None,
            "org_display_name": str(self.org_display_name) if self.org_display_name else None,
            "version": self.version,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IdentidadVisual):
            return NotImplemented
        if self.id_identidad_visual is None or other.id_identidad_visual is None:
            return self is other
        return self.id_identidad_visual == other.id_identidad_visual

    def __hash__(self) -> int:
        return hash(self.id_identidad_visual)
