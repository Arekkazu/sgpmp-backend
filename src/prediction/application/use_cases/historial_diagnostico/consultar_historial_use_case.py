# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-25 | Arekkazu | INC-M04-143/146 RF-67: cursor sobre (fecha_evento, id_evento) estables |
from __future__ import annotations

import base64
import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.historial_diagnostico import PaginaHistorial
from src.prediction.domain.repositories.activo_biologico_port import ActivoBiologicoPort
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.historial_diagnostico_repository import HistorialDiagnosticoRepository
from src.shared.errors import AuthorizationError, NotFoundError, ValidationError
from src.shared.fechas import fin_dia_usuario, hoy_usuario, inicio_dia_usuario

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

        hoy = hoy_usuario()
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

        cursor: Optional[tuple[datetime, uuid.UUID]] = None
        if cursor_paginacion:
            cursor = _decodificar_cursor(cursor_paginacion)

        dt_inicio = inicio_dia_usuario(fecha_inicio)
        dt_fin = fin_dia_usuario(fecha_fin)

        eventos = self._repo.consultar(
            id_activo_biologico=id_activo_biologico,
            fecha_inicio=dt_inicio,
            fecha_fin=dt_fin,
            nivel_riesgo=nivel_riesgo,
            id_patologia=id_patologia,
            incluir_alertas=incluir_alertas,
            cursor=cursor,
            limite=_LIMITE + 1,
        )

        # RF-67: máximo 50 eventos por página, cursor sobre (timestamp_evento, id_evento).
        cursor_siguiente: Optional[str] = None
        if len(eventos) > _LIMITE:
            eventos = eventos[:_LIMITE]
            cursor_siguiente = _codificar_cursor(eventos[-1].fecha_evento, eventos[-1].id_evento)

        try:
            self._repo.materializar_eventos(eventos)
            self._auditoria_repo.registrar(
                tipo_evento="HISTORIAL_CONSULTADO",
                tipo_actor="USUARIO",
                payload_evento={
                    "consulta": "HISTORIAL_DIAGNOSTICO",
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
                resultado_operacion="EXITOSO",
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


def _codificar_cursor(fecha: datetime, id_evento: uuid.UUID) -> str:
    payload = json.dumps({"ts": fecha.isoformat(), "id": str(id_evento)})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decodificar_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        fecha = datetime.fromisoformat(payload["ts"])
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha, uuid.UUID(payload["id"])
    except Exception:
        raise ValidationError(
            code="CURSOR_INVALIDO",
            message="El cursor de paginación es inválido. Reinicia la consulta desde la primera página.",
            field="cursor_paginacion",
        )
