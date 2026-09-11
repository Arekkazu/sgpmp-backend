"""Caso de uso: Obtener idioma resuelto del usuario (GET RF-29).

Jerarquía: preferencia individual → idioma global → 'es-CO'.
"""
from __future__ import annotations

from src.configuration.domain.entities.preferencia_idioma import LOCALE_DEFAULT
from src.configuration.domain.repositories.preferencia_idioma_repository import PreferenciaIdiomaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual


class ObtenerIdiomaResueltoUseCase:

    def __init__(self, idioma_repo: PreferenciaIdiomaRepository) -> None:
        self.idioma_repo = idioma_repo

    def execute(self, usuario_actual: UsuarioActual) -> dict:
        version = self.idioma_repo.version_perfil(usuario_actual.id_usuario)

        personal = self.idioma_repo.obtener_por_usuario(usuario_actual.id_usuario)
        if personal is not None:
            return {
                "locale_code": personal.locale_code,
                "fuente": "personal",
                "id_preferencia_idioma": personal.id_preferencia_idioma,
                "version_perfil": version,
            }

        global_ = self.idioma_repo.obtener_global()
        if global_ is not None:
            return {
                "locale_code": global_.locale_code,
                "fuente": "global",
                "id_preferencia_idioma": global_.id_preferencia_idioma,
                "version_perfil": version,
            }

        return {
            "locale_code": LOCALE_DEFAULT,
            "fuente": "defecto",
            "id_preferencia_idioma": None,
            "version_perfil": version,
        }
