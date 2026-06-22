"""Caso de uso: Obtener contexto de interfaz adaptativa del usuario (GET RF-25)."""
from __future__ import annotations

from src.configuration.domain.entities.contexto_interfaz import ContextoInterfaz
from src.configuration.domain.repositories.contexto_interfaz_repository import ContextoInterfazRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual


class ObtenerContextoUseCase:

    def __init__(self, contexto_repo: ContextoInterfazRepository) -> None:
        self.contexto_repo = contexto_repo

    def execute(self, usuario_actual: UsuarioActual) -> ContextoInterfaz:
        return self.contexto_repo.obtener_por_usuario(
            id_usuario=usuario_actual.id_usuario,
            id_rol=usuario_actual.id_rol,
        )
