"""Caso de uso: Obtener tema visual resuelto del usuario (GET RF-27).

Jerarquía: preferencia individual → tema global → CLARO (1).
"""
from __future__ import annotations

from src.configuration.domain.entities.tema_visual import ThemeMode
from src.configuration.domain.repositories.tema_visual_repository import TemaVisualRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual


class ObtenerTemaResueltoUseCase:

    def __init__(self, tema_repo: TemaVisualRepository) -> None:
        self.tema_repo = tema_repo

    def execute(self, usuario_actual: UsuarioActual) -> dict:
        personal = self.tema_repo.obtener_por_usuario(usuario_actual.id_usuario)
        if personal is not None:
            return {
                "theme_mode": personal.theme_mode.value,
                "fuente": "personal",
                "id_tema_visual": personal.id_tema_visual,
            }

        global_ = self.tema_repo.obtener_global()
        if global_ is not None:
            return {
                "theme_mode": global_.theme_mode.value,
                "fuente": "global",
                "id_tema_visual": global_.id_tema_visual,
            }

        return {
            "theme_mode": ThemeMode.CLARO.value,
            "fuente": "defecto",
            "id_tema_visual": None,
        }
