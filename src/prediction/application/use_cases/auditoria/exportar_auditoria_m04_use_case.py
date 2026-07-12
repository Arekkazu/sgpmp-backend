from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository

_CAMPOS_CSV = [
    "id_evento", "tipo_evento", "modulo", "fecha_evento", "tipo_actor",
    "correlacion_id", "severidad_evento", "origen_registro",
    "id_usuario", "id_sistema", "id_referencia", "entidad_referencia",
    "resultado_operacion", "codigo_error", "descripcion_error",
    "origen_dato", "version_modelo", "latencia_ms",
    "es_payload_truncado", "hash_evento", "payload_evento",
]


class ExportarAuditoriaM04UseCase:
    def __init__(self, db: Session, repo: EventoAuditoriaM04Repository) -> None:
        self._db = db
        self._repo = repo

    def exportar(
        self,
        *,
        tipo_evento: Optional[str],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        id_usuario: Optional[int],
        id_sistema: Optional[str],
        id_referencia: Optional[str],
        severidad_evento: Optional[str],
        formato: str,
        id_usuario_exportador: int,
    ) -> tuple[str | bytes, str, str]:
        items, _ = self._repo.consultar(
            tipo_evento=tipo_evento,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            id_usuario=id_usuario,
            id_sistema=id_sistema,
            id_referencia=id_referencia,
            severidad_evento=severidad_evento,
            pagina=1,
            por_pagina=10000,
        )
        self._emitir_evento_exportacion(id_usuario_exportador, len(items), formato)

        if formato == "csv":
            return self._a_csv(items), "text/csv", "auditoria_m04.csv"

        data = json.dumps(
            [self._evento_a_dict(e) for e in items],
            default=str,
            ensure_ascii=False,
        )
        return data, "application/json", "auditoria_m04.json"

    def _a_csv(self, items) -> str:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=_CAMPOS_CSV, extrasaction="ignore")
        writer.writeheader()
        for e in items:
            writer.writerow(self._evento_a_dict(e))
        return output.getvalue()

    def _evento_a_dict(self, e) -> dict:
        return {
            "id_evento": str(e.id_evento),
            "tipo_evento": e.tipo_evento,
            "modulo": e.modulo,
            "fecha_evento": e.fecha_evento.isoformat() if e.fecha_evento else None,
            "tipo_actor": e.tipo_actor,
            "correlacion_id": str(e.correlacion_id),
            "severidad_evento": e.severidad_evento,
            "origen_registro": e.origen_registro,
            "id_usuario": e.id_usuario,
            "id_sistema": e.id_sistema,
            "id_referencia": e.id_referencia,
            "entidad_referencia": e.entidad_referencia,
            "resultado_operacion": e.resultado_operacion,
            "codigo_error": e.codigo_error,
            "descripcion_error": e.descripcion_error,
            "origen_dato": e.origen_dato,
            "version_modelo": e.version_modelo,
            "latencia_ms": e.latencia_ms,
            "es_payload_truncado": e.es_payload_truncado,
            "hash_evento": e.hash_evento,
            "payload_evento": json.dumps(e.payload_evento, default=str, ensure_ascii=False),
        }

    def _emitir_evento_exportacion(self, id_usuario: int, total: int, formato: str) -> None:
        try:
            self._repo.registrar(
                tipo_evento="EXPORTACION_AUDITORIA_M04",
                tipo_actor="USUARIO",
                id_usuario=id_usuario,
                severidad_evento="INFO",
                payload_evento={"total_registros": total, "formato": formato},
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
