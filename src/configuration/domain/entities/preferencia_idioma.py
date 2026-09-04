"""Entidad de dominio ``PreferenciaIdioma`` — preferencia de idioma del usuario (RF-29).

Jerarquía de resolución: preferencia individual → idioma global → 'es-CO'.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.shared.errors import ValidationError

LOCALES_PERMITIDOS = {"es-CO", "en-US"}
LOCALE_DEFAULT = "es-CO"


@dataclass(eq=False)
class PreferenciaIdioma:
    id_usuario: int
    locale_code: str
    es_por_defecto: bool
    fecha_actualizacion: Optional[datetime]
    id_preferencia_idioma: Optional[int] = None

    @classmethod
    def crear_personal(
        cls,
        *,
        id_usuario: int,
        locale_code: str,
    ) -> PreferenciaIdioma:
        cls._validar_locale(locale_code)
        return cls(
            id_usuario=id_usuario,
            locale_code=locale_code,
            es_por_defecto=False,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

    @classmethod
    def crear_global(
        cls,
        *,
        id_usuario: int,
        locale_code: str,
    ) -> PreferenciaIdioma:
        cls._validar_locale(locale_code)
        return cls(
            id_usuario=id_usuario,
            locale_code=locale_code,
            es_por_defecto=True,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

    def actualizar(self, *, locale_code: str) -> None:
        self._validar_locale(locale_code)
        self.locale_code = locale_code
        self.fecha_actualizacion = datetime.now(timezone.utc)

    @staticmethod
    def _validar_locale(locale_code: str) -> None:
        if locale_code not in LOCALES_PERMITIDOS:
            raise ValidationError(
                code="IDIOMA_NO_DISPONIBLE",
                message=(
                    f"Idioma no disponible: El código de cultura '{locale_code}' no está "
                    "soportado actualmente. Los idiomas disponibles son Español (es-CO) "
                    "e Inglés (en-US)."
                ),
                field="locale_code",
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PreferenciaIdioma):
            return NotImplemented
        if self.id_preferencia_idioma is None or other.id_preferencia_idioma is None:
            return self is other
        return self.id_preferencia_idioma == other.id_preferencia_idioma

    def __hash__(self) -> int:
        return hash(self.id_preferencia_idioma)
