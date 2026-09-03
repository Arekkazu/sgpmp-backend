"""Caso de uso: Obtener contexto de interfaz adaptativa del usuario (GET RF-25).

Además del rol, la finca activa y las especies configuradas, resuelve la identidad
visual de esa finca (RF-26) y su contraste WCAG 2.1 AA contra los dos temas (RF-27),
para que el cliente construya la interfaz con una sola petición al iniciar sesión —
que es lo que el proceso de RF-25 describe paso por paso.
"""
from __future__ import annotations

from src.configuration.domain.entities import accesibilidad_visual
from src.configuration.domain.entities.contexto_interfaz import ContextoInterfaz
from src.configuration.domain.repositories.contexto_interfaz_repository import ContextoInterfazRepository
from src.configuration.domain.repositories.identidad_visual_repository import IdentidadVisualRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual


class ObtenerContextoUseCase:

    def __init__(
        self,
        contexto_repo: ContextoInterfazRepository,
        identidad_repo: IdentidadVisualRepository,
    ) -> None:
        self.contexto_repo = contexto_repo
        self.identidad_repo = identidad_repo

    def execute(self, usuario_actual: UsuarioActual) -> ContextoInterfaz:
        contexto = self.contexto_repo.obtener_por_usuario(
            id_usuario=usuario_actual.id_usuario,
            id_rol=usuario_actual.id_rol,
        )

        # Sin finca asignada no hay identidad institucional que resolver. Es el flujo
        # alterno "Usuario sin finca asociada" del RF-25: 200 con el contexto vacío y la
        # vista de bienvenida, no un error.
        if contexto.id_finca is None:
            return contexto

        identidad = self.identidad_repo.obtener_por_finca(contexto.id_finca)
        if identidad is None:
            return contexto

        contexto.identidad_visual = identidad
        contexto.accesibilidad = accesibilidad_visual.evaluar(
            identidad.primary_color, identidad.secondary_color
        )
        return contexto
