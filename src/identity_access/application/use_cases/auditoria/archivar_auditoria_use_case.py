"""Caso de uso del archivado automático de eventos de auditoría RF-10."""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository


MESES_RETENCION_MINIMA = 12
TAMANO_LOTE_ARCHIVADO = 5_000
MAXIMO_LOTES_POR_EJECUCION = 20


@dataclass(frozen=True)
class ResultadoArchivadoAuditoria:
    """Resumen operacional de una ejecución del proceso de retención."""

    fecha_corte: datetime
    eventos_archivados: int
    lotes_procesados: int
    bloqueo_adquirido: bool
    limite_alcanzado: bool


def restar_meses(fecha: datetime, meses: int) -> datetime:
    """Resta meses calendario conservando zona horaria y ajustando fin de mes."""
    indice_mes = fecha.year * 12 + (fecha.month - 1) - meses
    anio, mes_cero = divmod(indice_mes, 12)
    mes = mes_cero + 1
    dia = min(fecha.day, monthrange(anio, mes)[1])
    return fecha.replace(year=anio, month=mes, day=dia)


class ArchivarAuditoriaUseCase:
    """Copia a almacenamiento histórico los eventos con más de 12 meses."""

    def __init__(self, eventos_repo: EventoRepository, db: Session):
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(
        self,
        fecha_referencia: datetime | None = None,
    ) -> ResultadoArchivadoAuditoria:
        referencia = fecha_referencia or datetime.now(timezone.utc)
        if referencia.tzinfo is None:
            referencia = referencia.replace(tzinfo=timezone.utc)
        fecha_corte = restar_meses(referencia, MESES_RETENCION_MINIMA)

        try:
            if not self.eventos_repo.adquirir_bloqueo_archivado():
                self.db.rollback()
                return ResultadoArchivadoAuditoria(
                    fecha_corte=fecha_corte,
                    eventos_archivados=0,
                    lotes_procesados=0,
                    bloqueo_adquirido=False,
                    limite_alcanzado=False,
                )

            total = 0
            lotes = 0
            ultimo_lote = 0
            for _ in range(MAXIMO_LOTES_POR_EJECUCION):
                ultimo_lote = self.eventos_repo.archivar_eventos_anteriores(
                    fecha_corte=fecha_corte,
                    limite=TAMANO_LOTE_ARCHIVADO,
                )
                if ultimo_lote == 0:
                    break
                total += ultimo_lote
                lotes += 1
                if ultimo_lote < TAMANO_LOTE_ARCHIVADO:
                    break

            limite_alcanzado = (
                lotes == MAXIMO_LOTES_POR_EJECUCION
                and ultimo_lote == TAMANO_LOTE_ARCHIVADO
            )
            self.db.commit()
            return ResultadoArchivadoAuditoria(
                fecha_corte=fecha_corte,
                eventos_archivados=total,
                lotes_procesados=lotes,
                bloqueo_adquirido=True,
                limite_alcanzado=limite_alcanzado,
            )
        except Exception:
            self.db.rollback()
            raise
