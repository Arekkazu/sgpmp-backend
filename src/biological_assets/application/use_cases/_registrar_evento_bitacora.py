"""RF-52 restricción 3: un fallo en la bitácora no bloquea el flujo operativo
de M02. Pero el patrón anterior (`except Exception: pass`) descartaba ese
fallo sin dejar rastro — la ausencia de un evento dejaba de probar que la
operación no ocurrió (issue #265). `registrar_evento_bitacora` conserva el
"mejor esfuerzo" (la operación de negocio ya se resolvió, nunca se revierte
por esto) pero deja constancia siempre: log de aplicación con severidad
CRITICAL y el evento completo en un buffer local.

RF-52 E1 ("Fallo persistente del repositorio de auditoría"): ese buffer no es
solo evidencia, se recupera. La siguiente escritura exitosa, o la tarea
periódica de `main.py`, persiste los eventos pendientes en orden cronológico y
deja un registro INDISPONIBILIDAD_AUDITORIA con el periodo que la bitácora
estuvo caída.

RF-52 E3 ("Tormenta de eventos"): con carga normal todo se escribe en el
momento, como siempre. Si la tasa supera el umbral, los eventos INFO que no son
de transformación biológica se encolan en el mismo buffer —durable, así que
ninguno se descarta— y la tarea periódica los persiste por lotes. CRITICAL,
ERROR, WARNING y TRANSFORMACION_BIOLOGICA se siguen escribiendo de inmediato.
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import (
    BitacoraAuditoriaRepository,
)

logger = logging.getLogger(__name__)

# Relativo al directorio de trabajo, como el resto de logs/ del backend.
_DIR = Path("logs")


def _buffer() -> Path:
    return _DIR / "audit_buffer_M02.jsonl"


def _en_proceso() -> Path:
    return _DIR / "audit_buffer_M02.procesando.jsonl"


@contextmanager
def _bloqueo(nombre: str, esperar: bool = True) -> Iterator[None]:
    """Exclusión entre procesos (workers de uvicorn) e hilos sobre el buffer.

    Con ``esperar=False`` lanza ``BlockingIOError`` si otro ya lo tiene.
    """
    _DIR.mkdir(exist_ok=True)
    with open(_DIR / f"audit_buffer_M02.{nombre}.lock", "a") as candado:
        fcntl.flock(candado, fcntl.LOCK_EX if esperar else fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(candado, fcntl.LOCK_UN)


class ControlCarga:
    """RF-52 E3: detecta la tormenta de eventos con una ventana deslizante por proceso.

    Entra en alta carga por encima del umbral y sale por debajo de la mitad, para
    no oscilar cuando la tasa ronda el borde. El umbral es configurable porque el
    RF no fija cuál es "la capacidad de procesamiento".
    """

    def __init__(
        self,
        umbral: float | None = None,
        ventana_segundos: float = 5.0,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self.umbral = umbral if umbral is not None else float(
            os.getenv("AUDITORIA_M02_EVENTOS_POR_SEGUNDO", "100")
        )
        self.ventana = ventana_segundos
        self._reloj = reloj
        self._marcas: deque[float] = deque()
        self._candado = threading.Lock()
        self.en_alta_carga = False
        self.encolados = 0
        self._inicio: datetime | None = None

    def _tasa(self, ahora: float) -> float:
        while self._marcas and self._marcas[0] <= ahora - self.ventana:
            self._marcas.popleft()
        return len(self._marcas) / self.ventana

    def registrar_evento(self) -> dict | None:
        """Cuenta un evento; si con él empieza la alta carga, devuelve el detalle del inicio."""
        with self._candado:
            ahora = self._reloj()
            self._marcas.append(ahora)
            tasa = self._tasa(ahora)
            if self.en_alta_carga or tasa <= self.umbral:
                return None
            self.en_alta_carga = True
            self.encolados = 0
            self._inicio = datetime.now(timezone.utc)
            return {"tasa_eventos_por_segundo": tasa, "umbral": self.umbral}

    def contar_encolado(self) -> None:
        with self._candado:
            self.encolados += 1

    def revisar_fin(self) -> dict | None:
        """Si la alta carga ya pasó, la cierra y devuelve el resumen del episodio."""
        with self._candado:
            if not self.en_alta_carga or self._tasa(self._reloj()) >= self.umbral / 2:
                return None
            self.en_alta_carga = False
            return {
                "desde": self._inicio.isoformat() if self._inicio else None,
                "hasta": datetime.now(timezone.utc).isoformat(),
                "eventos_encolados": self.encolados,
            }


_control = ControlCarga()


def _es_diferible(evento: EventoAuditoria) -> bool:
    return evento.severidad_log == "INFO" and evento.clasificacion_biologica != "TRANSFORMACION_BIOLOGICA"


def _evento_rf52(tipo_evento: str, descripcion: str, detalle: dict) -> EventoAuditoria:
    return EventoAuditoria(
        rf_origen="RF52",
        tipo_evento=tipo_evento,
        clasificacion_biologica="GESTION_OPERATIVA",
        resultado="EXITOSO",
        severidad_log="WARNING",
        timestamp_evento=datetime.now(timezone.utc),
        descripcion=descripcion,
        detalle_tecnico=detalle,
    )


def _guardar_en_buffer(evento: EventoAuditoria, motivo: str, error: Exception | None = None) -> None:
    try:
        linea = json.dumps(
            {
                "evento": asdict(evento),
                "motivo": motivo,
                "encolado_en": datetime.now(timezone.utc).isoformat(),
                "error": str(error) if error else None,
            },
            default=str,
        )
        with _bloqueo("buffer"):
            with open(_buffer(), "a", encoding="utf-8") as f:
                f.write(linea + "\n")
    except Exception:
        logger.exception("No se pudo guardar el evento en el buffer de auditoría RF-52 (M02)")


def _leer_pendientes(ruta: Path) -> list[dict]:
    pendientes = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            pendientes.append(json.loads(linea))
        except json.JSONDecodeError:
            # Línea truncada por un proceso que murió a mitad de escritura:
            # no es recuperable, pero no puede bloquear al resto del buffer.
            logger.error("Línea ilegible en el buffer de auditoría RF-52, se descarta: %r", linea)
    return pendientes


def _evento_desde_buffer(datos: dict) -> EventoAuditoria:
    datos["timestamp_evento"] = datetime.fromisoformat(datos["timestamp_evento"])
    return EventoAuditoria(**datos)


def _recuperar_buffer(bitacora_repo: BitacoraAuditoriaRepository, db: Session) -> None:
    if not (_buffer().exists() or _en_proceso().exists()):
        return
    try:
        with _bloqueo("recuperacion", esperar=False):
            # Bajo el candado del buffer solo se hace el traspaso: quien encola
            # mientras tanto espera una copia de archivo, no la escritura en la BD.
            with _bloqueo("buffer"):
                if _buffer().exists():
                    with open(_en_proceso(), "a", encoding="utf-8") as destino:
                        destino.write(_buffer().read_text(encoding="utf-8"))
                    _buffer().unlink()

            pendientes = _leer_pendientes(_en_proceso())
            eventos = sorted(
                (_evento_desde_buffer(p["evento"]) for p in pendientes),
                key=lambda e: e.timestamp_evento,
            )
            for evento in eventos:
                bitacora_repo.registrar(evento)

            fallos = [p for p in pendientes if p.get("motivo") == "FALLO"]
            if fallos:
                recuperado_en = datetime.now(timezone.utc)
                bitacora_repo.registrar(_evento_rf52(
                    "INDISPONIBILIDAD_AUDITORIA",
                    f"Bitácora recuperada: {len(fallos)} eventos pendientes por la caída persistidos.",
                    {
                        "desde": min(p["encolado_en"] for p in fallos),
                        "hasta": recuperado_en.isoformat(),
                        "eventos_recuperados": len(fallos),
                    },
                ))
            db.commit()
            # ponytail: si el proceso muere entre el commit y este unlink, el lote se
            # reprocesa y queda duplicado en la bitácora. Duplicar es preferible a
            # perder (RF-52 E1); deduplicar exigiría una llave idempotente por evento.
            _en_proceso().unlink()
    except BlockingIOError:
        return  # otro hilo o proceso ya está recuperando el buffer
    except Exception:
        db.rollback()
        logger.exception("No se pudo recuperar el buffer de auditoría RF-52 (M02); se reintentará")


def _persistir(bitacora_repo: BitacoraAuditoriaRepository, db: Session, evento: EventoAuditoria) -> bool:
    try:
        bitacora_repo.registrar(evento)
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        logger.critical(
            "Fallo al registrar evento de auditoría RF-52: rf_origen=%s tipo_evento=%s "
            "id_activo=%s id_usuario=%s. El evento queda en %s hasta que la bitácora se recupere.",
            evento.rf_origen,
            evento.tipo_evento,
            evento.id_activo_biologico,
            evento.id_usuario_responsable,
            _buffer(),
            exc_info=True,
        )
        _guardar_en_buffer(evento, "FALLO", exc)
        return False


def _cerrar_alta_carga_si_termino(bitacora_repo: BitacoraAuditoriaRepository, db: Session) -> None:
    fin = _control.revisar_fin()
    if fin is not None:
        _persistir(bitacora_repo, db, _evento_rf52(
            "ALTA_CARGA_AUDITORIA_FIN",
            f"Fin de alta carga en la bitácora: {fin['eventos_encolados']} eventos INFO encolados.",
            fin,
        ))


def registrar_evento_bitacora(
    bitacora_repo: BitacoraAuditoriaRepository | None,
    db: Session,
    evento: EventoAuditoria,
) -> None:
    """Registra `evento` en RF-52 sin bloquear ni revertir la operación de negocio.

    Si `bitacora_repo` es None, no hace nada (auditoría no configurada). Si el
    registro falla, se revierte solo el intento de escritura de auditoría
    (`db.rollback()`), se alerta con severidad CRITICAL en el log de aplicación
    y el evento queda en el buffer local — nunca se propaga la excepción, para
    no tumbar un flujo operativo válido de M02 por un problema de
    infraestructura de auditoría. Con carga normal, una escritura exitosa se
    aprovecha para vaciar lo que haya quedado en el buffer.
    """
    if bitacora_repo is None:
        return

    inicio = _control.registrar_evento()
    if inicio is not None:
        _persistir(bitacora_repo, db, _evento_rf52(
            "ALTA_CARGA_AUDITORIA_INICIO",
            "Inicio de alta carga en la bitácora: los eventos INFO se encolan y se persisten por lotes.",
            inicio,
        ))

    if _control.en_alta_carga and _es_diferible(evento):
        _guardar_en_buffer(evento, "ALTA_CARGA")
        _control.contar_encolado()
        return

    if _persistir(bitacora_repo, db, evento) and not _control.en_alta_carga:
        _recuperar_buffer(bitacora_repo, db)
    _cerrar_alta_carga_si_termino(bitacora_repo, db)


def procesar_buffer_bitacora(bitacora_repo: BitacoraAuditoriaRepository, db: Session) -> None:
    """Tarea periódica (`main.py`): persiste por lotes la cola de alta carga (E3) y lo
    pendiente por una caída (E1), fuera de cualquier request. También cierra el
    episodio de alta carga cuando la tasa bajó aunque no lleguen eventos nuevos.
    """
    _cerrar_alta_carga_si_termino(bitacora_repo, db)
    _recuperar_buffer(bitacora_repo, db)
