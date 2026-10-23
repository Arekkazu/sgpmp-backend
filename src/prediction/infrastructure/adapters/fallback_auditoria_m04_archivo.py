# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-37 RF-73 E2/E8: respaldo en audit_fallback_M04_YYYYMMDD.log y su lectura FIFO |
"""Respaldo de la auditoría de M04 en disco local (RF-73 E8).

Un archivo por día, ``audit_fallback_M04_YYYYMMDD.log``, un JSON por línea. Al
sincronizarse se renombra a ``.sincronizado`` para no volver a leerlo; si una línea
no se puede interpretar, el archivo se queda y se reporta en el log técnico.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from src.prediction.domain.repositories.fallback_auditoria_m04_port import FallbackAuditoriaM04Port, LoteFallback

logger = logging.getLogger(__name__)

_PATRON = "audit_fallback_M04_*.log"


def _serializar(valor) -> str:
    # Fechas en ISO 8601: así se reconstruyen igual al sincronizar.
    return valor.isoformat() if hasattr(valor, "isoformat") else str(valor)


def directorio_fallback() -> Path:
    return Path(os.getenv("AUDITORIA_M04_FALLBACK_DIR", "logs"))


class FallbackAuditoriaM04Archivo(FallbackAuditoriaM04Port):
    def __init__(self, directorio: Path | None = None) -> None:
        self._directorio = directorio or directorio_fallback()

    def escribir(self, evento: dict) -> None:
        try:
            self._directorio.mkdir(parents=True, exist_ok=True)
            archivo = self._directorio / f"audit_fallback_M04_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"
            linea = json.dumps({**evento, "origen_registro": "FALLBACK"}, default=_serializar)
            with open(archivo, "a", encoding="utf-8") as f:
                f.write(linea + "\n")
        except Exception:
            logger.exception("RF-73 E8: no se pudo escribir el respaldo de auditoría M04.")

    def pendientes(self) -> list[LoteFallback]:
        if not self._directorio.is_dir():
            return []
        lotes = []
        for archivo in sorted(self._directorio.glob(_PATRON)):
            try:
                with open(archivo, encoding="utf-8") as f:
                    eventos = [json.loads(linea) for linea in f if linea.strip()]
            except (OSError, json.JSONDecodeError):
                logger.exception("RF-73 E8: el respaldo %s no se pudo leer; se deja para revisión.", archivo.name)
                continue
            lotes.append(LoteFallback(identificador=str(archivo), eventos=eventos))
        return lotes

    def marcar_sincronizado(self, identificador: str) -> None:
        archivo = Path(identificador)
        archivo.rename(archivo.with_name(archivo.name + ".sincronizado"))
