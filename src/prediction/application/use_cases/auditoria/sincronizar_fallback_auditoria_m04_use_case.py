# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-37 RF-73 E8: sincroniza el respaldo local al repositorio central (FIFO) |
"""RF-73 E8: al recuperarse el repositorio central, los eventos del respaldo local se
sincronizan en orden FIFO, con su fecha original y ``origen_registro = FALLBACK``, y
se avisa al Administrador con ``AUDITORIA_FALLBACK_ACTIVADO`` (CRITICAL).

Un lote se confirma completo o no se confirma: si la BD vuelve a fallar a mitad, el
archivo queda para la próxima pasada y los eventos ya insertados se saltan por id.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.prediction.domain.repositories.aviso_version_modelo_port import AvisoFallbackAuditoriaPort
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.fallback_auditoria_m04_port import FallbackAuditoriaM04Port

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoSincronizacionFallback:
    eventos: int
    lotes: int
    inicio_contingencia: str | None


class SincronizarFallbackAuditoriaM04UseCase:
    def __init__(self, *, db: Session, repo: EventoAuditoriaM04Repository,
                 fallback: FallbackAuditoriaM04Port, aviso: AvisoFallbackAuditoriaPort) -> None:
        self._db = db
        self._repo = repo
        self._fallback = fallback
        self._aviso = aviso

    def execute(self) -> ResultadoSincronizacionFallback:
        eventos, lotes, fechas = 0, 0, []
        for lote in self._fallback.pendientes():
            try:
                insertados = sum(self._repo.registrar_desde_fallback(e) for e in lote.eventos)
                self._db.commit()
            except Exception:
                self._db.rollback()
                logger.exception("RF-73 E8: el respaldo %s no se pudo sincronizar; se reintenta.", lote.identificador)
                break  # FIFO: no se adelanta un lote más nuevo
            self._fallback.marcar_sincronizado(lote.identificador)
            eventos += insertados
            lotes += 1
            fechas += [str(e["fecha_evento"]) for e in lote.eventos if e.get("fecha_evento")]

        if not lotes:
            return ResultadoSincronizacionFallback(0, 0, None)
        inicio = min(fechas) if fechas else None
        try:
            self._repo.registrar(
                tipo_evento="AUDITORIA_FALLBACK_ACTIVADO",
                tipo_actor="SISTEMA",
                id_sistema="DESARROLLO_M04",
                severidad_evento="CRITICAL",
                resultado_operacion="EXITOSO",
                payload_evento={"inicio_contingencia": inicio, "eventos_sincronizados": eventos,
                                "lotes_sincronizados": lotes},
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            logger.exception("RF-73 E8: no se pudo registrar AUDITORIA_FALLBACK_ACTIVADO.")
        # Después del commit: el aviso nunca bloquea ni revierte la sincronización.
        self._aviso.avisar_fallback_activado(inicio_contingencia=inicio, eventos=eventos)
        return ResultadoSincronizacionFallback(eventos, lotes, inicio)
