# | Fecha      | Nombre   | Que se hizo                                             |
# |------------|----------|---------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-107 RNF-03: crear o editar un mensaje del catálogo |
"""Caso de uso: el Administrador crea o reemplaza el texto de una clave de error sin tocar código (RNF-03)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.mensaje_error import MensajeError
from src.configuration.domain.repositories.catalogo_mensajes_error_repository import CatalogoMensajesErrorRepository


class GuardarMensajeErrorUseCase:

    def __init__(self, db: Session, repo: CatalogoMensajesErrorRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(self, clave: str, idioma: str, mensaje: str, texto_accion: Optional[str],
                ruta_accion: Optional[str], es_activo: bool, id_usuario: int) -> MensajeError:
        entrada = MensajeError(clave=clave, idioma=idioma, mensaje=mensaje, texto_accion=texto_accion,
                               ruta_accion=ruta_accion, es_activo=es_activo, id_usuario=id_usuario)
        try:
            guardado = self.repo.guardar(entrada)
            self.db.commit()
            return guardado
        except Exception:
            self.db.rollback()
            raise
