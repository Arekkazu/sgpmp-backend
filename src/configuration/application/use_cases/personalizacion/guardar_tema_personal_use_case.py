"""Caso de uso: Guardar preferencia de tema visual personal del usuario (PATCH RF-27)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.tema_visual import TemaVisual
from src.configuration.domain.repositories.tema_visual_repository import TemaVisualRepository
from src.configuration.infrastructure.dto.guardar_tema_dto import GuardarTemaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual


class GuardarTemaPersonalUseCase:

    def __init__(self, db: Session, tema_repo: TemaVisualRepository) -> None:
        self.db = db
        self.tema_repo = tema_repo

    def execute(self, dto: GuardarTemaDTO, usuario_actual: UsuarioActual) -> TemaVisual:
        existente = self.tema_repo.obtener_por_usuario(usuario_actual.id_usuario)

        try:
            if existente is not None:
                existente.actualizar(theme_mode=dto.theme_mode)
                resultado = self.tema_repo.actualizar(existente)
            else:
                nuevo = TemaVisual.crear_personal(
                    id_usuario=usuario_actual.id_usuario,
                    theme_mode=dto.theme_mode,
                )
                resultado = self.tema_repo.guardar(nuevo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return resultado
