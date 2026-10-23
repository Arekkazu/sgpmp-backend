# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
"""RF-73 E8: respaldo en disco ``logs/audit_fallback_M04_YYYYMMDD.log`` (JSON por línea).

Mismo esquema de exclusión que el buffer de la bitácora de M02
(``_registrar_evento_bitacora.py``): ``flock`` entre workers de uvicorn e hilos.
Para sincronizar, los archivos del día se mueven a ``audit_fallback_M04_procesando/``
bajo el candado de escritura (quien guarda mientras tanto solo espera ese
traspaso) y se leen en orden de nombre y de línea, que es el orden en que se
guardaron.
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.prediction.domain.repositories.respaldo_auditoria_m04_port import RespaldoAuditoriaM04Port

logger = logging.getLogger(__name__)

_PATRON = "audit_fallback_M04_????????.log"


class RespaldoAuditoriaM04ArchivoAdapter(RespaldoAuditoriaM04Port):
    def __init__(self, directorio: Optional[Path] = None) -> None:
        # Relativo al directorio de trabajo, como el resto de logs/ del backend.
        self._dir = Path(directorio or os.getenv("AUDITORIA_M04_DIR_RESPALDO", "logs"))
        self._procesando = self._dir / "audit_fallback_M04_procesando"

    def _archivo_del_dia(self) -> Path:
        return self._dir / f"audit_fallback_M04_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"

    @contextmanager
    def _bloqueo(self, nombre: str, esperar: bool = True) -> Iterator[None]:
        self._dir.mkdir(parents=True, exist_ok=True)
        with open(self._dir / f"audit_fallback_M04.{nombre}.lock", "a") as candado:
            fcntl.flock(candado, fcntl.LOCK_EX if esperar else fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(candado, fcntl.LOCK_UN)

    def guardar(self, evento: dict) -> None:
        linea = json.dumps(evento, default=str, ensure_ascii=False)
        with self._bloqueo("escritura"):
            with open(self._archivo_del_dia(), "a", encoding="utf-8") as f:
                f.write(linea + "\n")

    def hay_pendientes(self) -> bool:
        return any(self._dir.glob(_PATRON)) or any(self._procesando.glob(_PATRON))

    @contextmanager
    def pendientes(self) -> Iterator[Optional[list[dict]]]:
        try:
            candado = self._bloqueo("sincronizacion", esperar=False)
            candado.__enter__()
        except BlockingIOError:
            yield None  # otro hilo o proceso ya está sincronizando
            return
        try:
            with self._bloqueo("escritura"):
                self._procesando.mkdir(exist_ok=True)
                for origen in sorted(self._dir.glob(_PATRON)):
                    destino = self._procesando / origen.name
                    with open(destino, "a", encoding="utf-8") as f:
                        f.write(origen.read_text(encoding="utf-8"))
                    origen.unlink()
            archivos = sorted(self._procesando.glob(_PATRON))
            yield [evento for archivo in archivos for evento in _leer(archivo)]
            for archivo in archivos:
                archivo.unlink()
        finally:
            candado.__exit__(None, None, None)


def _leer(archivo: Path) -> list[dict]:
    eventos = []
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            eventos.append(_normalizar(json.loads(linea), archivo, linea))
        except json.JSONDecodeError:
            # Línea truncada por un proceso que murió a mitad de escritura: no es
            # recuperable, pero no puede bloquear al resto del respaldo.
            logger.error("Línea ilegible en el respaldo de auditoría M04 (%s), se descarta: %r", archivo.name, linea)
    return eventos


def _normalizar(evento: dict, archivo: Path, linea: str) -> dict:
    """Las líneas del respaldo anterior a DEV-37 no traen id_evento ni fecha_evento.

    Se completan para que la sincronización no se atasque con ellas: id derivado
    de la línea (estable entre reintentos, así no se duplica) y, como fecha, el
    inicio del día del archivo (marcada como aproximada).
    """
    evento.setdefault("id_evento", str(uuid.uuid5(uuid.NAMESPACE_URL, f"{archivo.name}:{linea}")))
    evento["correlacion_id"] = evento.get("correlacion_id") or evento["id_evento"]
    if not evento.get("fecha_evento"):
        dia = datetime.strptime(archivo.stem.rsplit("_", 1)[-1], "%Y%m%d").replace(tzinfo=timezone.utc)
        evento["fecha_evento"] = dia.isoformat()
        evento.setdefault("respaldo", {})["fecha_aproximada"] = True
    return evento
