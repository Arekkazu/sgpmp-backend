# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66/RF-69: el motor IA descarga el artefacto de una versión    |
"""Archivo ``.onnx`` de una versión ACTIVO o SOMBRA, para que el motor IA lo descargue.

RF-69 guarda ``ruta_artefacto`` dentro de ``MODELOS_STORAGE_PATH``; la ruta final nunca puede
salir de ese directorio (misma regla que la descarga OTA).
"""
from __future__ import annotations

import os
from pathlib import Path

from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.shared.errors import NotFoundError

ESTADOS_DESCARGABLES = ("ACTIVO", "SOMBRA")


class ObtenerArtefactoVersionUseCase:
    def __init__(self, repo: VersionModeloRepository, directorio: str | None = None) -> None:
        self._repo = repo
        self._directorio = Path(directorio or os.environ.get("MODELOS_STORAGE_PATH", "/tmp/sgpmp_modelos"))

    def execute(self, id_version: int) -> Path:
        version = self._repo.obtener_por_id(id_version)
        if version is None or version.estado_version not in ESTADOS_DESCARGABLES:
            raise NotFoundError(
                code="VERSION_NO_DESCARGABLE",
                message=f"La versión {id_version} no existe o no está en ACTIVO ni en SOMBRA.",
            )
        ruta = version.ruta_artefacto or ""
        base = self._directorio.resolve()
        archivo = (base / ruta).resolve()
        if not ruta or base not in archivo.parents or not archivo.is_file():
            raise NotFoundError(code="ARTEFACTO_NO_DISPONIBLE", message="El artefacto del modelo no está disponible.")
        return archivo
