# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: identificar consultas globales sin inventar entidades de negocio. |
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-04 RF-73: consultar versiones no emite HISTORIAL_CONSULTADO |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso de consulta de versiones de modelo."""
from __future__ import annotations

from typing import Optional

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.shared.errors import NotFoundError


class ConsultarVersionesUseCase:
    """CU09 H-04: consultar versiones no deja evento. HISTORIAL_CONSULTADO es del
    historial diagnóstico (RF-67); abrir Modelos IA dejaba entre 5 y 7 por carga."""

    def __init__(self, *, repo: VersionModeloRepository) -> None:
        self._repo = repo

    def listar(
        self,
        *,
        tipo_modelo: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[VersionModelo], int]:
        """Lista las versiones de modelo con filtros."""
        return self._repo.listar(tipo_modelo=tipo_modelo, estado=estado, limit=limit, offset=offset)

    def obtener_por_id(self, id_version: int) -> VersionModelo:
        """Devuelve la versión.

        Raises:
            NotFoundError: Si la versión no existe.
        """
        entidad = self._repo.obtener_por_id(id_version)
        if entidad is None:
            raise NotFoundError(
                code="VERSION_MODELO_NO_ENCONTRADA",
                message=f"No existe la versión de modelo con id {id_version}.",
            )
        return entidad
