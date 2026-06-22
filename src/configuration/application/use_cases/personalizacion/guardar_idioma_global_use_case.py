"""Caso de uso: Guardar idioma global del sistema (PATCH RF-29 — Admin)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.preferencia_idioma import PreferenciaIdioma
from src.configuration.domain.repositories.preferencia_idioma_repository import PreferenciaIdiomaRepository
from src.configuration.infrastructure.dto.guardar_idioma_dto import GuardarIdiomaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual


class GuardarIdiomaGlobalUseCase:

    def __init__(self, db: Session, idioma_repo: PreferenciaIdiomaRepository) -> None:
        self.db = db
        self.idioma_repo = idioma_repo

    def execute(self, dto: GuardarIdiomaDTO, usuario_actual: UsuarioActual) -> PreferenciaIdioma:
        existente = self.idioma_repo.obtener_global()

        try:
            if existente is not None:
                existente.actualizar(locale_code=dto.locale_code)
                resultado = self.idioma_repo.actualizar(existente)
            else:
                nuevo = PreferenciaIdioma.crear_global(
                    id_usuario=usuario_actual.id_usuario,
                    locale_code=dto.locale_code,
                )
                resultado = self.idioma_repo.guardar(nuevo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return resultado
