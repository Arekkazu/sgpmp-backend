# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
"""RF-73 E8 / CA-14: al recuperarse la BD, el respaldo local vuelve a la bitácora de M04.

Los eventos se insertan en orden FIFO con su ``id_evento`` y ``fecha_evento``
originales y ``origen_registro = FALLBACK``; luego se registra la alerta
AUDITORIA_FALLBACK_ACTIVADO (CRITICAL) con el inicio de la contingencia y se
avisa al Administrador. Si la BD sigue caída, todo se revierte y el respaldo se
conserva para el siguiente intento (la tarea periódica de ``main.py``).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.prediction.domain.repositories.aviso_auditoria_m04_port import AvisoAuditoriaM04Port
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.respaldo_auditoria_m04_port import RespaldoAuditoriaM04Port

logger = logging.getLogger(__name__)


@dataclass
class ResultadoSincronizacionRespaldo:
    eventos_sincronizados: int = 0
    eventos_ya_presentes: int = 0
    en_curso_por_otro: bool = False


class SincronizarRespaldoAuditoriaM04UseCase:
    def __init__(
        self,
        *,
        db: Session,
        repo: EventoAuditoriaM04Repository,
        respaldo: RespaldoAuditoriaM04Port,
        aviso: AvisoAuditoriaM04Port,
    ) -> None:
        self._db = db
        self._repo = repo
        self._respaldo = respaldo
        self._aviso = aviso

    def execute(self) -> ResultadoSincronizacionRespaldo:
        if not self._respaldo.hay_pendientes():
            return ResultadoSincronizacionRespaldo()

        with self._respaldo.pendientes() as pendientes:
            if pendientes is None:
                return ResultadoSincronizacionRespaldo(en_curso_por_otro=True)
            if not pendientes:  # solo líneas ilegibles: el respaldo se descarta
                return ResultadoSincronizacionRespaldo()
            resultado = ResultadoSincronizacionRespaldo()
            try:
                for evento in pendientes:  # FIFO: el orden en que se respaldaron
                    if self._repo.insertar_desde_respaldo(evento):
                        resultado.eventos_sincronizados += 1
                    else:
                        resultado.eventos_ya_presentes += 1
                resumen = _resumen(pendientes, resultado)
                self._repo.registrar(
                    tipo_evento="AUDITORIA_FALLBACK_ACTIVADO",
                    tipo_actor="SISTEMA",
                    id_sistema="DESARROLLO_M04",
                    severidad_evento="CRITICAL",
                    resultado_operacion="EXITOSO",
                    payload_evento=resumen,
                )
                self._db.commit()
            except Exception:
                # El bloque relanza: el respaldo se conserva para el siguiente intento.
                self._db.rollback()
                raise

        logger.critical(
            "AUDITORIA_FALLBACK_ACTIVADO: %s eventos de M04 sincronizados desde el respaldo local "
            "(contingencia desde %s).",
            resultado.eventos_sincronizados, resumen["inicio_contingencia"],
        )
        self._aviso.avisar_fallback_activado(resumen)
        return resultado


def _resumen(pendientes: list[dict], resultado: ResultadoSincronizacionRespaldo) -> dict:
    return {
        # El primer evento que no se pudo persistir marca el inicio de la contingencia.
        "inicio_contingencia": min(e["fecha_evento"] for e in pendientes),
        "fin_contingencia": datetime.now(timezone.utc).isoformat(),
        "eventos_sincronizados": resultado.eventos_sincronizados,
        "eventos_ya_presentes": resultado.eventos_ya_presentes,
        "fallas_persistencia": sum(1 for e in pendientes if e.get("tipo_evento") == "AUDITORIA_FALLA_PERSISTENCIA"),
        "tipos_evento": sorted({e["tipo_evento"] for e in pendientes}),
    }
