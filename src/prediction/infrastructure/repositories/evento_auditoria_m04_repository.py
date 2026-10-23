# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-48 RF-72 E8: incidente de persistencia en RF-73   |
# | 2026-10-23 | Arekkazu     | DEV-37 RF-73 E2/E8: reintentos, respaldo completo y sincronizacion desde el respaldo |
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.orm import Session

from src.prediction.domain.entities.evento_auditoria_m04 import EventoAuditoriaM04
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.fallback_auditoria_m04_port import FallbackAuditoriaM04Port
from src.prediction.infrastructure.adapters.fallback_auditoria_m04_archivo import FallbackAuditoriaM04Archivo
from src.prediction.infrastructure.models.evento_auditoria_m04_model import EventoAuditoriaM04Model
from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import InfrastructureError, NotFoundError
from src.shared.tipo_modelo import POBLACIONAL, paradigma_de

logger = logging.getLogger(__name__)

# Campos mínimos requeridos en payload_evento por tipo_evento (solo eventos que genera Desarrollo)
_PAYLOAD_REQUERIDO: dict[str, list[str]] = {
    "RETROALIMENTACION_REGISTRADA": [
        "id_resultado_inferencia", "estado_retroalimentacion", "id_usuario_veterinario",
    ],
    "CONFLICTO_RETROALIMENTACION": [
        "id_resultado_inferencia", "numero_retroalimentaciones",
    ],
    "VERSION_APROBADA": ["tipo_modelo", "id_version"],
    "VERSION_RECHAZADA": ["tipo_modelo", "id_version"],
    "VERSION_ACTIVADA": ["tipo_modelo", "id_version_nueva"],
    "VERSION_DEPRECADA": ["tipo_modelo", "id_version"],
    "VERSION_REGISTRADA": ["tipo_modelo", "id_version"],
    "CATALOGO_PATOLOGIA_AGREGADA": ["id_patologia", "nombre"],
    "CATALOGO_PATOLOGIA_MODIFICADA": ["id_patologia"],
    "CATALOGO_PATOLOGIA_INACTIVADA": ["id_patologia"],
    "MOTOR_CONFIG_ACTUALIZADO": ["id_configuracion"],
}

_PAYLOAD_MAX_BYTES = 64 * 1024  # 64 KB


def _calcular_hash(tipo_evento: str, payload: dict, fecha: str) -> str:
    canonical = json.dumps(
        {"tipo_evento": tipo_evento, "payload_evento": payload, "fecha": fecha},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# RF-73 v2.0 (RFC-009): las métricas mínimas dependen del paradigma del modelo. Sin
# esto un modelo POBLACIONAL (sin F1/recall) nunca podría emitir su aprobación.
_EVENTOS_CON_METRICAS = {"VERSION_APROBADA", "VERSION_RECHAZADA"}
_METRICAS_MINIMAS: dict[str, list[str]] = {
    POBLACIONAL: ["calibracion_completada", "tasa_falsos_positivos_rutina", "tasa_deteccion_eventos_clinicos"],
}
_METRICAS_SUPERVISADAS = ["f1_score_global", "recall_clase_riesgo_alto"]


def _validar_payload(tipo_evento: str, payload: dict) -> list[str]:
    requeridos = list(_PAYLOAD_REQUERIDO.get(tipo_evento, []))
    if tipo_evento in _EVENTOS_CON_METRICAS:
        requeridos += _METRICAS_MINIMAS.get(paradigma_de(payload.get("tipo_modelo")), _METRICAS_SUPERVISADAS)
    return [campo for campo in requeridos if campo not in payload]


# RF-73 E2: reintentos ante una falla transitoria de la BD antes del respaldo local.
_REINTENTOS = 3
_ESPERA_BASE_SEG = 0.1


def _es_transitorio(exc: Exception) -> bool:
    """Caída o corte de conexión: reintentable. Un CHECK, un enum o una FK no lo son."""
    return isinstance(exc, (OperationalError, InterfaceError)) or (
        isinstance(exc, DBAPIError) and exc.connection_invalidated
    )


def _a_entidad(orm: EventoAuditoriaM04Model) -> EventoAuditoriaM04:
    return EventoAuditoriaM04(
        id_evento=orm.id_evento,
        tipo_evento=orm.tipo_evento,
        modulo=orm.modulo,
        fecha_evento=orm.fecha_evento,
        tipo_actor=orm.tipo_actor,
        correlacion_id=orm.correlacion_id,
        payload_evento=orm.payload_evento,
        es_payload_truncado=orm.es_payload_truncado,
        severidad_evento=orm.severidad_evento,
        origen_registro=orm.origen_registro,
        id_usuario=orm.id_usuario,
        id_sistema=orm.id_sistema,
        id_referencia=orm.id_referencia,
        entidad_referencia=orm.entidad_referencia,
        resultado_operacion=orm.resultado_operacion,
        codigo_error=orm.codigo_error,
        descripcion_error=orm.descripcion_error,
        origen_dato=orm.origen_dato,
        version_modelo=orm.version_modelo,
        latencia_ms=orm.latencia_ms,
        hash_evento=orm.hash_evento,
    )


class SqlAlchemyEventoAuditoriaM04Repository(EventoAuditoriaM04Repository):
    def __init__(self, db: Session, fallback: Optional[FallbackAuditoriaM04Port] = None) -> None:
        self._db = db
        self._fallback = fallback or FallbackAuditoriaM04Archivo()

    def registrar(
        self,
        *,
        tipo_evento: str,
        tipo_actor: str,
        payload_evento: dict,
        severidad_evento: str = "INFO",
        id_usuario: Optional[int] = None,
        id_sistema: Optional[str] = None,
        id_referencia: Optional[str] = None,
        entidad_referencia: Optional[str] = None,
        resultado_operacion: Optional[str] = None,
        correlacion_id: Optional[uuid.UUID] = None,
        codigo_error: Optional[str] = None,
        descripcion_error: Optional[str] = None,
    ) -> None:
        campos_faltantes = _validar_payload(tipo_evento, payload_evento)
        if campos_faltantes:
            self._registrar_invalido(tipo_evento, payload_evento, campos_faltantes, correlacion_id)
            return

        payload_final, truncado = _truncar_payload(payload_evento)
        sev_final = "WARNING" if truncado else severidad_evento
        fecha = datetime.now(timezone.utc)
        hash_ev = _calcular_hash(tipo_evento, payload_final, fecha.isoformat())
        corr = correlacion_id or uuid.uuid4()
        # id y fecha se fijan aquí: si el evento termina en el respaldo, se sincroniza
        # con los mismos valores y sin duplicarse (RF-73 E8).
        datos = dict(
            id_evento=uuid.uuid4(),
            fecha_evento=fecha,
            tipo_evento=tipo_evento,
            tipo_actor=tipo_actor,
            payload_evento=payload_final,
            es_payload_truncado=truncado,
            severidad_evento=sev_final,
            id_usuario=id_usuario,
            id_sistema=id_sistema,
            id_referencia=id_referencia,
            entidad_referencia=entidad_referencia,
            resultado_operacion=resultado_operacion,
            correlacion_id=corr,
            origen_registro="DESARROLLO_M04",
            hash_evento=hash_ev,
            codigo_error=codigo_error,
            descripcion_error=descripcion_error,
        )
        for intento in range(1, _REINTENTOS + 1):
            try:
                # Savepoint: un intento fallido no invalida la transacción del caso de uso.
                with self._db.begin_nested():
                    self._db.add(EventoAuditoriaM04Model(**datos))
                    self._db.flush()
                return
            except Exception as exc:
                if not _es_transitorio(exc):
                    # Un CHECK, un enum o una FK fallaría igual al sincronizar y trabaría
                    # la cola FIFO del respaldo: solo se registra en el log técnico.
                    logger.critical("RF-73: evento de auditoría M04 rechazado por la BD tipo=%s: %s", tipo_evento, exc)
                    _lanzar_fallo_persistencia(exc)
                if intento == _REINTENTOS:
                    self._activar_respaldo(datos, exc, intento)
                    _lanzar_fallo_persistencia(exc)
                logger.warning("RF-73 E2: reintento %d de la auditoría M04 tipo=%s.", intento, tipo_evento)
                time.sleep(_ESPERA_BASE_SEG * 2 ** (intento - 1))

    def _activar_respaldo(self, datos: dict, exc: Exception, intentos: int) -> None:
        """RF-73 E2/E8: el evento va al respaldo local y se deja AUDITORIA_FALLA_PERSISTENCIA
        (CRITICAL) en el mismo respaldo, porque el repositorio central no responde."""
        self._fallback.escribir(datos)
        self._fallback.escribir(dict(
            id_evento=uuid.uuid4(),
            fecha_evento=datetime.now(timezone.utc),
            tipo_evento="AUDITORIA_FALLA_PERSISTENCIA",
            tipo_actor="SISTEMA",
            id_sistema="DESARROLLO_M04",
            payload_evento={"id_evento_respaldado": str(datos["id_evento"]),
                            "tipo_evento_respaldado": datos["tipo_evento"],
                            "intentos": intentos, "error": type(exc).__name__},
            es_payload_truncado=False,
            severidad_evento="CRITICAL",
            correlacion_id=datos["correlacion_id"],
            resultado_operacion="FALLIDO",
            codigo_error="AUDITORIA_M04_NO_PERSISTIDA",
        ))
        # "Se notifica al sistema de monitoreo": CRITICAL en el log técnico.
        logger.critical(
            "RF-73 E2: AUDITORIA_FALLA_PERSISTENCIA tipo=%s tras %d intento(s): %s",
            datos["tipo_evento"], intentos, exc,
        )

    def registrar_desde_fallback(self, evento: dict) -> bool:
        id_evento = uuid.UUID(str(evento["id_evento"]))
        if self._db.get(EventoAuditoriaM04Model, id_evento) is not None:
            return False
        try:
            self._db.add(EventoAuditoriaM04Model(
                id_evento=id_evento,
                fecha_evento=datetime.fromisoformat(str(evento["fecha_evento"])),
                tipo_evento=evento["tipo_evento"],
                tipo_actor=evento["tipo_actor"],
                payload_evento=evento.get("payload_evento") or {},
                es_payload_truncado=bool(evento.get("es_payload_truncado", False)),
                severidad_evento=evento.get("severidad_evento", "INFO"),
                id_usuario=evento.get("id_usuario"),
                id_sistema=evento.get("id_sistema"),
                id_referencia=evento.get("id_referencia"),
                entidad_referencia=evento.get("entidad_referencia"),
                resultado_operacion=evento.get("resultado_operacion"),
                correlacion_id=uuid.UUID(str(evento["correlacion_id"])),
                origen_registro="FALLBACK",
                hash_evento=evento.get("hash_evento"),
                codigo_error=evento.get("codigo_error"),
                descripcion_error=evento.get("descripcion_error"),
            ))
            self._db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
        return True

    def _registrar_invalido(
        self,
        tipo_evento_orig: str,
        payload_orig: dict,
        campos_faltantes: list[str],
        correlacion_id: Optional[uuid.UUID],
    ) -> None:
        payload = {
            "tipo_evento_original": tipo_evento_orig,
            "campos_faltantes": campos_faltantes,
            "payload_recibido": payload_orig,
        }
        try:
            self._db.add(EventoAuditoriaM04Model(
                tipo_evento="AUDITORIA_EVENTO_INVALIDO",
                tipo_actor="SISTEMA",
                # chk_eam_actor_exclusivo: un actor SISTEMA exige id_sistema; sin él
                # este evento nunca llegaba a guardarse.
                id_sistema="DESARROLLO_M04",
                payload_evento=payload,
                severidad_evento="ERROR",
                correlacion_id=correlacion_id or uuid.uuid4(),
                origen_registro="DESARROLLO_M04",
                hash_evento=_calcular_hash(
                    "AUDITORIA_EVENTO_INVALIDO", payload, datetime.now(timezone.utc).isoformat()
                ),
            ))
            self._db.flush()
        except Exception as exc:
            logger.error("Error al persistir evento AUDITORIA_EVENTO_INVALIDO: %s", exc)
            _lanzar_fallo_persistencia(exc)

    def consultar(
        self,
        *,
        tipo_evento: Optional[str] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        id_usuario: Optional[int] = None,
        id_sistema: Optional[str] = None,
        id_referencia: Optional[str] = None,
        severidad_evento: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> tuple[list[EventoAuditoriaM04], int]:
        q = select(EventoAuditoriaM04Model)

        if tipo_evento:
            q = q.where(EventoAuditoriaM04Model.tipo_evento == tipo_evento)
        if fecha_desde:
            q = q.where(EventoAuditoriaM04Model.fecha_evento >= fecha_desde)
        if fecha_hasta:
            q = q.where(EventoAuditoriaM04Model.fecha_evento <= fecha_hasta)
        if id_usuario is not None:
            q = q.where(EventoAuditoriaM04Model.id_usuario == id_usuario)
        if id_sistema:
            q = q.where(EventoAuditoriaM04Model.id_sistema == id_sistema)
        if id_referencia:
            q = q.where(EventoAuditoriaM04Model.id_referencia == id_referencia)
        if severidad_evento:
            q = q.where(EventoAuditoriaM04Model.severidad_evento == severidad_evento)

        total_q = select(func.count()).select_from(q.subquery())
        total = self._db.execute(total_q).scalar_one()

        offset = (pagina - 1) * por_pagina
        items = (
            self._db.execute(
                q.order_by(EventoAuditoriaM04Model.fecha_evento.desc()).offset(offset).limit(por_pagina)
            )
            .scalars()
            .all()
        )
        return [_a_entidad(row) for row in items], total

    def obtener_por_id(self, id_evento: uuid.UUID) -> EventoAuditoriaM04:
        orm = self._db.get(EventoAuditoriaM04Model, id_evento)
        if orm is None:
            raise NotFoundError(
                code="EVENTO_AUDITORIA_NO_ENCONTRADO",
                message=f"No existe el evento de auditoría con id {id_evento}.",
            )
        return _a_entidad(orm)


def _lanzar_fallo_persistencia(exc: Exception) -> None:
    """D-03: un flush fallido deja la sesión inutilizable, así que no se puede tragar.

    Antes se registraba en el log y se seguía: el ``commit`` siguiente del use
    case fallaba con ``PendingRollbackError`` (500 sin causa) o, si el use case
    lo atrapaba, el evento se perdía en silencio. Va como 500 y no por
    ``raise_from_db_error``: los valores del evento los arma el servidor, no el
    cliente, así que un CHECK o un enum inválido no es un 400.
    """
    raise InfrastructureError(
        code="AUDITORIA_M04_NO_PERSISTIDA",
        message="No se pudo registrar el evento de auditoría de predicción.",
        original_error=exc,
    ) from exc


def _truncar_payload(payload: dict) -> tuple[dict, bool]:
    raw = json.dumps(payload, default=str)
    if len(raw.encode()) <= _PAYLOAD_MAX_BYTES:
        return payload, False
    # Truncar serialización y agregar flag
    truncado = raw.encode()[:_PAYLOAD_MAX_BYTES].decode(errors="ignore")
    try:
        resultado = json.loads(truncado)
    except json.JSONDecodeError:
        resultado = {"payload_truncado_raw": truncado[:500]}
    resultado["payload_truncado"] = True
    return resultado, True
