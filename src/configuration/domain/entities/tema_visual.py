"""Entidad de dominio ``TemaVisual`` — preferencia de tema visual del usuario (RF-27).

Un registro puede ser personal (es_global=False) o global del sistema (es_global=True).
La jerarquía de resolución es: preferencia individual → global → CLARO (1).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from typing import Optional

from src.shared.errors import ValidationError


class ThemeMode(IntEnum):
    CLARO = 1
    OSCURO = 2
    SISTEMA = 3


@dataclass(eq=False)
class TemaVisual:
    id_usuario: int
    theme_mode: ThemeMode
    es_global: bool
    fecha_actualizacion: datetime
    id_tema_visual: Optional[int] = None

    @classmethod
    def crear_personal(
        cls,
        *,
        id_usuario: int,
        theme_mode: int,
    ) -> TemaVisual:
        cls._validar_mode(theme_mode)
        return cls(
            id_usuario=id_usuario,
            theme_mode=ThemeMode(theme_mode),
            es_global=False,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

    @classmethod
    def crear_global(
        cls,
        *,
        id_usuario: int,
        theme_mode: int,
    ) -> TemaVisual:
        cls._validar_mode(theme_mode)
        return cls(
            id_usuario=id_usuario,
            theme_mode=ThemeMode(theme_mode),
            es_global=True,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

    def actualizar(self, *, theme_mode: int) -> None:
        self._validar_mode(theme_mode)
        self.theme_mode = ThemeMode(theme_mode)
        self.fecha_actualizacion = datetime.now(timezone.utc)

    @staticmethod
    def _validar_mode(theme_mode: int) -> None:
        try:
            ThemeMode(theme_mode)
        except ValueError:
            raise ValidationError(
                code="TEMA_INVALIDO",
                message=(
                    f"El identificador de tema '{theme_mode}' no es válido. "
                    "Los valores permitidos son 1 (Claro), 2 (Oscuro) o 3 (Automático)."
                ),
                field="theme_mode",
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TemaVisual):
            return NotImplemented
        if self.id_tema_visual is None or other.id_tema_visual is None:
            return self is other
        return self.id_tema_visual == other.id_tema_visual

    def __hash__(self) -> int:
        return hash(self.id_tema_visual)
