# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-19 | Leandro | INC-M07-371-G58 RF-102: verificar el SHA-256 antes y después del traslado. |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Archiva lotes de RF-102 y confirma cada traslado solo tras verificar la copia."""
from datetime import datetime
from hmac import compare_digest
from typing import Protocol

from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion


class ArchivoAuditoria(Protocol):
    """Puerto de archivado de eventos de auditoría de integración."""
    def bloquear_archivado(self) -> bool:
        """Toma el lock de archivado; ``False`` si otro proceso lo tiene."""
        ...

    def candidatos_archivo(
        self, despues_de: tuple[datetime, str] | None, limite: int,
    ) -> list[tuple[EventoIntegracion, str, datetime]]:
        """Lista los eventos vencidos a partir del cursor."""
        ...

    def archivar(self, ids: list[str]) -> list[tuple[EventoIntegracion, str]]:
        """Traslada los eventos indicados al archivo."""
        ...


class TransaccionArchivo(Protocol):
    """Transacción del archivado."""
    def commit(self) -> None:
        """Confirma la transacción."""
        ...

    def rollback(self) -> None:
        """Revierte la transacción."""
        ...


class ArchivarAuditoriaIntegracionUseCase:
    """Archiva por lotes los eventos de auditoría de integración vencidos."""
    def __init__(self, archivo: ArchivoAuditoria, transaccion: TransaccionArchivo) -> None:
        self.archivo = archivo
        self.transaccion = transaccion

    def ejecutar_lote(self, cursor: tuple[datetime, str] | None) -> tuple[tuple[datetime, str] | None, int, list[str]]:
        """Archiva un lote y devuelve el cursor siguiente, la cantidad y los ids archivados."""
        try:
            if not self.archivo.bloquear_archivado():
                self.transaccion.rollback()
                return None, 0, []
            candidatas = self.archivo.candidatos_archivo(cursor, 100)
            if not candidatas:
                self.transaccion.rollback()
                return None, 0, []
            originales = {}
            corruptos = []
            for evento, hash_guardado, _ in candidatas:
                if compare_digest(evento.hash_integridad, hash_guardado):
                    originales[evento.id_evento_integracion] = (evento, hash_guardado)
                else:
                    corruptos.append(evento.id_evento_integracion)
            if originales:
                copias = self.archivo.archivar(list(originales))
                if {e.id_evento_integracion: (e, h) for e, h in copias} != originales or any(
                    not compare_digest(e.hash_integridad, h) for e, h in copias
                ):
                    raise RuntimeError("No se pudo comprobar la integridad del lote archivado.")
            self.transaccion.commit()
        except Exception:
            self.transaccion.rollback()
            raise
        ultimo, _, vencimiento = candidatas[-1]
        return (vencimiento, ultimo.id_evento_integracion), len(originales), corruptos
