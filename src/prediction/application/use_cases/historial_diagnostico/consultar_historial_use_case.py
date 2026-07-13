from __future__ import annotations

import base64
import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.historial_diagnostico import EventoHistorial, PaginaHistorial
from src.prediction.domain.repositories.activo_biologico_port import ActivoBiologicoPort
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.historial_diagnostico_repository import HistorialDiagnosticoRepository
from src.shared.errors import AuthorizationError, NotFoundError, ValidationError

_LIMITE = 50


class ConsultarHistorialUseCase:
    def __init__(
        self,
        *,
        db: Session,
        repo: HistorialDiagnosticoRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
        activo_port: ActivoBiologicoPort,
    ) -> None:
        self._db = db
        self._repo = repo
        self._auditoria_repo = auditoria_repo
        self._activo_port = activo_port

    def execute(
        self,
        *,
        id_activo_biologico: int,
        fecha_inicio: date,
        fecha_fin: date,
        nivel_riesgo: Optional[int],
        id_patologia: Optional[int],
        incluir_alertas: bool,
        cursor_paginacion: Optional[str],
        id_usuario: int,
        id_rol: int,
    ) -> PaginaHistorial:
        if not self._activo_port.activo_existe_y_accesible(id_activo_biologico, id_usuario, id_rol):
            raise NotFoundError(code="ACTIVO_NO_ENCONTRADO", message="El activo biológico no existe o no está disponible.")

        hoy = datetime.now(tz=timezone.utc).date()
        if fecha_inicio > fecha_fin:
            raise ValidationError(
                code="RANGO_FECHAS_INVALIDO",
                message="La fecha de inicio no puede ser posterior a la fecha de fin.",
                field="fecha_inicio",
            )
        if fecha_inicio > hoy or fecha_fin > hoy:
            raise ValidationError(
                code="RANGO_FECHAS_INVALIDO",
                message="No se pueden consultar rangos de fecha futuros.",
                field="fecha_fin",
            )

        cursor: Optional[tuple[datetime, str]] = None
        if cursor_paginacion:
            cursor = _decodificar_cursor(cursor_paginacion)

        dt_inicio = datetime.combine(fecha_inicio, datetime.min.time(), tzinfo=timezone.utc)
        dt_fin = datetime.combine(fecha_fin, datetime.max.time().replace(microsecond=999999), tzinfo=timezone.utc)

        filas = self._repo.consultar(
            id_activo_biologico=id_activo_biologico,
            fecha_inicio=dt_inicio,
            fecha_fin=dt_fin,
            nivel_riesgo=nivel_riesgo,
            id_patologia=id_patologia,
            incluir_alertas=incluir_alertas,
            cursor=cursor,
            limite=_LIMITE + 1,
        )

        hay_mas = len(filas) > _LIMITE
        if hay_mas:
            filas = filas[:_LIMITE]

        eventos = [
            EventoHistorial(
                id_evento=uuid.uuid4(),
                tipo_evento=f["tipo_evento"],
                id_activo_biologico=f["id_activo_biologico"],
                fecha_evento=f["fecha_evento"],
                id_resultado_inferencia=f["id_resultado_inferencia"],
                payload=f["payload"],
            )
            for f in filas
        ]

        cursor_siguiente: Optional[str] = None
        if hay_mas:
            ultimo = filas[-1]
            cursor_siguiente = _codificar_cursor(ultimo["fecha_evento"], str(ultimo["id_resultado_inferencia"]))

        try:
            self._repo.materializar_eventos(eventos)
            self._auditoria_repo.registrar(
                tipo_evento="CONSULTA_HISTORIAL_DIAGNOSTICO",
                tipo_actor="USUARIO",
                payload_evento={
                    "id_activo_biologico": id_activo_biologico,
                    "fecha_inicio": fecha_inicio.isoformat(),
                    "fecha_fin": fecha_fin.isoformat(),
                    "nivel_riesgo": nivel_riesgo,
                    "id_patologia": id_patologia,
                    "incluir_alertas": incluir_alertas,
                    "total_eventos_devueltos": len(eventos),
                    "con_cursor": cursor_paginacion is not None,
                },
                severidad_evento="INFO",
                id_usuario=id_usuario,
                id_referencia=str(id_activo_biologico),
                entidad_referencia="activo_biologico",
                resultado_operacion="OK",
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        return PaginaHistorial(
            eventos=eventos,
            cursor_siguiente=cursor_siguiente,
            total_pagina=len(eventos),
        )


def _codificar_cursor(fecha: datetime, id_resultado: str) -> str:
    payload = json.dumps({"ts": fecha.isoformat(), "id": id_resultado})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decodificar_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        fecha = datetime.fromisoformat(payload["ts"])
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha, payload["id"]
    except Exception:
        raise ValidationError(
            code="CURSOR_INVALIDO",
            message="El cursor de paginación es inválido. Reinicia la consulta desde la primera página.",
            field="cursor_paginacion",
        )
