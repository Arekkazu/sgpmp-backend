"""Resolver el artefacto de un despliegue OTA a partir de su URL firmada (DEV-15, D6 paso 4).

El nodo no tiene JWT: la URL que recibió en ``ota/notify`` es la credencial. Se
valida la firma HMAC y el vencimiento, y que el despliegue siga en curso. El
archivo vive en ``OTA_ARTEFACTOS_DIR`` + ``versiones_modelos.ruta_artefacto``; la
ruta final nunca puede salir de ese directorio.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.domain.repositories.ota_edge_port import UrlDescargaPort
from src.prediction.domain.repositories.version_modelo_repository import VersionModeloRepository
from src.shared.errors import AuthenticationError, GoneError, NotFoundError


class ObtenerArtefactoOtaUseCase:

    def __init__(
        self,
        *,
        despliegue_repo: DespliegueOtaRepository,
        version_repo: VersionModeloRepository,
        url_port: UrlDescargaPort,
        directorio_artefactos: str | None = None,
    ) -> None:
        self._despliegue_repo = despliegue_repo
        self._version_repo = version_repo
        self._url_port = url_port
        # RF-69 guarda ruta_artefacto como ruta absoluta dentro de MODELOS_STORAGE_PATH:
        # sin OTA_ARTEFACTOS_DIR explícito se sirve desde ese mismo almacén.
        self._directorio = Path(
            directorio_artefactos
            or os.environ.get("OTA_ARTEFACTOS_DIR")
            or os.environ.get("MODELOS_STORAGE_PATH", "/tmp/sgpmp_modelos")
        )

    def execute(self, id_despliegue: int, expira: int, firma: str) -> Path:
        if not self._url_port.es_valida(id_despliegue, expira, firma, datetime.now(timezone.utc)):
            raise AuthenticationError(code="URL_DESCARGA_INVALIDA", message="La URL de descarga no es válida o venció.")
        despliegue = self._despliegue_repo.obtener_por_id(id_despliegue)
        if despliegue is None:
            raise NotFoundError(code="DESPLIEGUE_OTA_NO_ENCONTRADO", message=f"No existe el despliegue OTA {id_despliegue}.")
        if despliegue.esta_terminado:
            raise GoneError(code="DESPLIEGUE_OTA_TERMINADO", message="El despliegue OTA ya terminó: el artefacto no se sirve.")
        version = self._version_repo.obtener_por_id(despliegue.id_version_modelo)
        ruta = (version.ruta_artefacto if version else None) or ""
        base = self._directorio.resolve()
        archivo = (base / ruta).resolve()
        if not ruta or base not in archivo.parents or not archivo.is_file():
            raise NotFoundError(code="ARTEFACTO_NO_DISPONIBLE", message="El artefacto del modelo no está disponible.")
        return archivo
