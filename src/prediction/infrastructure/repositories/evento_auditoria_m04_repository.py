# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-48 RF-72 E8: incidente de persistencia en RF-73   |
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
# | 2026-10-25 | Arekkazu     | INC-M04-151-G081 RF-73: persiste origen_dato (EDGE/BACKEND/HIBRIDO) |
# | 2026-10-26 | Arekkazu     | INC-M04 G088/G092/G099 RF-73: truncado conserva mínimos, filtro correlacion_id, E7 |
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: rechazar eventos invalidos con evidencia E1 y resultado tipado. |
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.exc import DataError, IntegrityError

from src.prediction.domain.entities.evento_auditoria_m04 import EventoAuditoriaM04
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.respaldo_auditoria_m04_port import RespaldoAuditoriaM04Port
from src.prediction.infrastructure.models.evento_auditoria_m04_model import EventoAuditoriaM04Model
from src.shared.errors import InfrastructureError, NotFoundError
from src.prediction.domain.services.validacion_auditoria_m04 import (
    ResultadoRegistroAuditoriaM04, campos_requeridos as _campos_requeridos, validar_evento,
)

logger = logging.getLogger(__name__)

_PAYLOAD_MAX_BYTES = 64 * 1024  # 64 KB

#: RF-73 E7: holgura de reloj antes de tratar un timestamp como futuro.
_MAX_DESFASE_FUTURO_SEG = 60


def _calcular_hash(tipo_evento: str, payload: dict, fecha: str) -> str:
    canonical = json.dumps(
        {"tipo_evento": tipo_evento, "payload_evento": payload, "fecha": fecha},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validar_payload(tipo_evento: str, payload: dict) -> list[str]:
    return [c for c in _campos_requeridos(tipo_evento, payload) if c not in payload]


# RF-73 E2: reintentos ante falla de persistencia antes de ir al respaldo local.
_REINTENTOS = int(os.getenv("AUDITORIA_M04_REINTENTOS", "3"))
_PAUSA_REINTENTO = 0.2  # segundos; crece con cada intento (0.2, 0.4): cabe en los 2 s de RNF-01
_ID_SISTEMA = "DESARROLLO_M04"


def _origen_por_actor(tipo_actor: str) -> str:
    """RF-73: ``origen_dato`` dice dónde ocurrió el evento. Lo que reporta un nodo
    Edge ocurrió en el Edge; lo demás lo emite este backend."""
    return "EDGE" if tipo_actor == "DISPOSITIVO_EDGE" else "BACKEND"

# Columnas del evento que van al respaldo y vuelven en la sincronización.
_CAMPOS_RESPALDO = (
    "id_evento", "tipo_evento", "fecha_evento", "tipo_actor", "correlacion_id", "payload_evento",
    "es_payload_truncado", "severidad_evento", "id_usuario", "id_sistema", "id_referencia",
    "entidad_referencia", "resultado_operacion", "codigo_error", "descripcion_error", "hash_evento",
    "origen_dato",
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
    def __init__(
        self,
        db: Session,
        respaldo: Optional[RespaldoAuditoriaM04Port] = None,
        *,
        reintentos: int = _REINTENTOS,
        pausa_reintento: float = _PAUSA_REINTENTO,
    ) -> None:
        self._db = db
        if respaldo is None:
            from src.prediction.infrastructure.adapters.respaldo_auditoria_m04_archivo_adapter import (
                RespaldoAuditoriaM04ArchivoAdapter,
            )
            respaldo = RespaldoAuditoriaM04ArchivoAdapter()
        self._respaldo = respaldo
        self._reintentos = max(1, reintentos)
        self._pausa = pausa_reintento

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
        origen_dato: Optional[str] = None,
        timestamp_evento: Optional[datetime] = None,
    ) -> ResultadoRegistroAuditoriaM04:
        correlacion_id = correlacion_id or uuid.uuid4()
        id_evento = uuid.uuid4()
        errores = validar_evento(
            tipo_evento=tipo_evento, tipo_actor=tipo_actor, id_usuario=id_usuario,
            id_sistema=id_sistema, id_referencia=id_referencia, payload_evento=payload_evento,
        )
        if errores:
            return self._registrar_invalido(tipo_evento, payload_evento, errores, correlacion_id, id_evento)

        payload_final, truncado = _truncar_payload(payload_evento, _campos_requeridos(tipo_evento, payload_evento))
        sev_final = "WARNING" if truncado else severidad_evento
        ahora = datetime.now(timezone.utc)
        fecha, motivo_correccion = self._fecha_evento(timestamp_evento, correlacion_id, ahora)
        campos = dict(
            # id y fecha se fijan aquí: si el evento termina en el respaldo, la
            # sincronización conserva los originales (RF-73 CA-14).
            id_evento=id_evento,
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
            correlacion_id=correlacion_id,
            hash_evento=_calcular_hash(tipo_evento, payload_final, fecha.isoformat()),
            codigo_error=codigo_error,
            descripcion_error=descripcion_error,
            origen_dato=origen_dato or _origen_por_actor(tipo_actor),
        )
        try:
            self._persistir(campos, rechazo_controlado=True)
        except _RechazoEventoBD as exc:
            return self._registrar_invalido(tipo_evento, payload_evento, exc.campos, correlacion_id, id_evento)
        if motivo_correccion:
            self._registrar_timestamp_corregido(
                tipo_evento, id_evento, correlacion_id, timestamp_evento, fecha, motivo_correccion
            )
        return ResultadoRegistroAuditoriaM04(aceptado=True, id_evento=id_evento)

    def _fecha_evento(
        self, timestamp_evento: Optional[datetime], correlacion_id: uuid.UUID, ahora: datetime
    ) -> tuple[datetime, Optional[str]]:
        """RF-73 E7: un timestamp futuro, o anterior al último evento de su misma cadena
        (``correlacion_id``), se reemplaza por el del sistema. Devuelve (fecha, motivo)."""
        if timestamp_evento is None:
            return ahora, None
        if timestamp_evento.tzinfo is None:
            timestamp_evento = timestamp_evento.replace(tzinfo=timezone.utc)
        if (timestamp_evento - ahora).total_seconds() > _MAX_DESFASE_FUTURO_SEG:
            return ahora, "FUTURO"
        ultimo = self._db.execute(
            select(func.max(EventoAuditoriaM04Model.fecha_evento))
            .where(EventoAuditoriaM04Model.correlacion_id == correlacion_id)
        ).scalar_one_or_none()
        if ultimo is not None and timestamp_evento < ultimo:
            return ahora, "DESORDENADO"
        return timestamp_evento, None

    def _registrar_timestamp_corregido(
        self,
        tipo_evento: str,
        id_evento: uuid.UUID,
        correlacion_id: uuid.UUID,
        original: datetime,
        corregido: datetime,
        motivo: str,
    ) -> None:
        payload = {
            "tipo_evento_corregido": tipo_evento,
            "id_evento_corregido": str(id_evento),
            "timestamp_original": original.isoformat(),
            "timestamp_corregido": corregido.isoformat(),
            "motivo": motivo,
        }
        self._persistir(dict(
            id_evento=uuid.uuid4(),
            fecha_evento=corregido,
            tipo_evento="TIMESTAMP_CORREGIDO",
            tipo_actor="SISTEMA",
            payload_evento=payload,
            es_payload_truncado=False,
            severidad_evento="WARNING",
            id_usuario=None,
            id_sistema="M04",
            id_referencia=str(id_evento),
            entidad_referencia="evento_auditoria_m04",
            resultado_operacion=None,
            correlacion_id=correlacion_id,
            hash_evento=_calcular_hash("TIMESTAMP_CORREGIDO", payload, corregido.isoformat()),
            codigo_error=None,
            descripcion_error=None,
            origen_dato="BACKEND",
        ))

    def _persistir(self, campos: dict, *, rechazo_controlado: bool = False) -> None:
        """RF-73 E2: N intentos, cada uno en su savepoint; si todos fallan, respaldo local.

        El savepoint aísla el intento: un fallo no deja inutilizable la sesión del
        use case (D-03) ni revierte lo que este ya escribió. Con el evento a salvo
        en el respaldo no se interrumpe el flujo (RNF-07); solo si tampoco se pudo
        respaldar se lanza 500, porque el evento se perdería.
        """
        error = None
        for intento in range(1, self._reintentos + 1):
            try:
                with self._db.begin_nested():
                    self._db.add(EventoAuditoriaM04Model(origen_registro=_ID_SISTEMA, **campos))
                    self._db.flush()
                return
            except (DataError, IntegrityError) as exc:
                errores = _campos_rechazados_bd(exc)
                if rechazo_controlado and errores:
                    raise _RechazoEventoBD(errores) from exc
                error = exc
            except Exception as exc:
                error = exc
            if error is not None:
                logger.warning(
                    "Intento %s/%s de persistir el evento de auditoría M04 %s falló: %s",
                    intento, self._reintentos, campos["tipo_evento"], error,
                )
                if intento < self._reintentos:
                    time.sleep(self._pausa * intento)

        falla = {
            "id_evento": uuid.uuid4(),
            "fecha_evento": datetime.now(timezone.utc),
            "tipo_evento": "AUDITORIA_FALLA_PERSISTENCIA",
            "tipo_actor": "SISTEMA",
            "id_sistema": _ID_SISTEMA,
            "origen_dato": "BACKEND",
            "severidad_evento": "CRITICAL",
            "resultado_operacion": "FALLIDO",
            "id_referencia": str(campos["id_evento"]),
            "entidad_referencia": "evento_auditoria_m04",
            "correlacion_id": campos["correlacion_id"],
            "codigo_error": type(error).__name__[:50],
            "descripcion_error": str(error)[:2000],
            "payload_evento": {
                "id_evento_original": str(campos["id_evento"]),
                "tipo_evento_original": campos["tipo_evento"],
                "severidad_original": campos["severidad_evento"],
                "intentos": self._reintentos,
                "destino": "RESPALDO_LOCAL",
            },
        }
        falla["hash_evento"] = _calcular_hash(
            falla["tipo_evento"], falla["payload_evento"], falla["fecha_evento"].isoformat()
        )
        # Monitoreo (E2): log CRITICAL con lo necesario para rastrear el evento.
        logger.critical(
            "AUDITORIA_FALLA_PERSISTENCIA: el evento M04 %s (%s, id %s) no se persistió tras %s intentos "
            "y va al respaldo local. Error: %s",
            campos["tipo_evento"], campos["severidad_evento"], campos["id_evento"], self._reintentos, error,
        )
        try:
            self._respaldo.guardar(_a_respaldo(campos, motivo="FALLA_PERSISTENCIA", error=error))
            self._respaldo.guardar(_a_respaldo(falla, motivo="FALLA_PERSISTENCIA", error=error))
        except Exception as exc_respaldo:
            logger.critical("Tampoco se pudo escribir el respaldo de auditoría M04: %s", exc_respaldo)
            _lanzar_fallo_persistencia(error)

    def insertar_desde_respaldo(self, evento: dict) -> bool:
        """RF-73 E8: inserta un evento del respaldo con su id y fecha originales.

        Idempotente por ``id_evento``: si una sincronización anterior alcanzó a
        guardarlo antes de caerse, no se duplica. Devuelve False en ese caso.
        """
        valores = {campo: evento.get(campo) for campo in _CAMPOS_RESPALDO}
        valores["id_evento"] = uuid.UUID(str(valores["id_evento"]))
        valores["correlacion_id"] = uuid.UUID(str(valores["correlacion_id"]))
        valores["fecha_evento"] = datetime.fromisoformat(str(valores["fecha_evento"]))
        valores["es_payload_truncado"] = bool(valores["es_payload_truncado"])
        valores["origen_registro"] = "FALLBACK"
        try:
            resultado = self._db.execute(
                pg_insert(EventoAuditoriaM04Model)
                .values(**valores)
                .on_conflict_do_nothing(index_elements=[EventoAuditoriaM04Model.id_evento])
            )
        except Exception as exc:
            _lanzar_fallo_persistencia(exc)
        return resultado.rowcount == 1

    def _registrar_invalido(
        self, tipo_evento_orig: str, payload_orig: object, errores: tuple[str, ...],
        correlacion_id: uuid.UUID, id_intento: uuid.UUID,
    ) -> ResultadoRegistroAuditoriaM04:
        # El log técnico conserva evidencia aun si el emisor revierte su transacción.
        # No se escribe SQL ni el payload recibido en el log.
        logger.error("AUDITORIA_EVENTO_INVALIDO: intento=%s correlacion=%s campos=%s",
                     id_intento, correlacion_id, ",".join(errores))
        payload = {
            "tipo_evento_original": tipo_evento_orig,
            "campos_invalidos": list(errores),
            "campos_faltantes": [c.removeprefix("payload_evento.") for c in errores if c.startswith("payload_evento.")],
            "payload_recibido": payload_orig,
            "id_intento": str(id_intento),
        }
        payload, truncado = _truncar_payload(payload, ["tipo_evento_original", "campos_invalidos", "id_intento"])
        ahora = datetime.now(timezone.utc)
        id_rechazo = uuid.uuid4()
        self._persistir(dict(
            id_evento=id_rechazo, fecha_evento=ahora,
            tipo_evento="AUDITORIA_EVENTO_INVALIDO", tipo_actor="SISTEMA",
            id_usuario=None, id_sistema=_ID_SISTEMA, origen_dato="BACKEND",
            id_referencia=str(id_intento), entidad_referencia="intento_evento_auditoria_m04",
            payload_evento=payload, es_payload_truncado=truncado, severidad_evento="ERROR",
            resultado_operacion="FALLIDO", codigo_error="AUDITORIA_EVENTO_INVALIDO",
            correlacion_id=correlacion_id,
            hash_evento=_calcular_hash("AUDITORIA_EVENTO_INVALIDO", payload, ahora.isoformat()),
        ))
        return ResultadoRegistroAuditoriaM04(
            aceptado=False, id_evento=id_rechazo, codigo="AUDITORIA_EVENTO_INVALIDO",
            campos_invalidos=errores,
        )

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
        correlacion_id: Optional[uuid.UUID] = None,
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
        if correlacion_id is not None:
            q = q.where(EventoAuditoriaM04Model.correlacion_id == correlacion_id)

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


def _a_respaldo(campos: dict, *, motivo: str, error: Optional[Exception]) -> dict:
    """Evento completo (columnas de la bitácora) más el motivo por el que se respaldó."""
    fila = {campo: campos.get(campo) for campo in _CAMPOS_RESPALDO}
    fila["fecha_evento"] = campos["fecha_evento"].isoformat()
    fila["id_evento"] = str(campos["id_evento"])
    fila["correlacion_id"] = str(campos["correlacion_id"])
    fila["modulo"] = "M04"
    fila["respaldo"] = {
        "motivo": motivo,
        "error": str(error)[:500] if error else None,
        "guardado_en": datetime.now(timezone.utc).isoformat(),
    }
    return fila


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


def _truncar_payload(payload: dict, requeridos: list[str] = ()) -> tuple[dict, bool]:
    """RF-73: payload de más de 64 KB → se conserva como claves todo lo que cabe.

    INC-M04-201-G088: antes un corte a mitad del JSON dejaba solo
    ``payload_truncado_raw`` y los campos mínimos (``tipo_modelo``, ``id_version``...)
    quedaban como texto. Ahora se conservan, en este orden, los campos mínimos del tipo
    de evento y los demás campos que quepan enteros (los escalares primero, que son la
    cabecera); lo que no cabe queda en ``payload_truncado_raw`` (inicio del JSON
    original) y sus nombres en ``campos_omitidos``.
    """
    raw = json.dumps(payload, default=str)
    if len(raw.encode()) <= _PAYLOAD_MAX_BYTES:
        return payload, False

    def tamano(d: dict) -> int:
        return len(json.dumps(d, default=str).encode())

    resultado: dict = {"payload_truncado": True}
    omitidos: list[str] = []
    orden = [k for k in requeridos if k in payload] + sorted(
        (k for k in payload if k not in requeridos),
        key=lambda k: isinstance(payload[k], (dict, list)),
    )
    reserva = 1024  # campos_omitidos + payload_truncado_raw
    for clave in orden:
        candidato = {**resultado, clave: payload[clave]}
        if clave in requeridos or tamano(candidato) <= _PAYLOAD_MAX_BYTES - reserva:
            resultado = candidato
        else:
            omitidos.append(clave)
    if omitidos:
        resultado["campos_omitidos"] = omitidos
        libre = max(0, _PAYLOAD_MAX_BYTES - tamano(resultado) - 64)
        resultado["payload_truncado_raw"] = raw.encode()[:min(libre, 500)].decode(errors="ignore")
    return resultado, True


class _RechazoEventoBD(Exception):
    def __init__(self, campos: tuple[str, ...]):
        self.campos = campos


def _campos_rechazados_bd(exc: Exception) -> tuple[str, ...]:
    """Solo rechazos del contrato conocido; una FK/caída no equivale a E1."""
    original = exc.orig
    codigo = getattr(original, "pgcode", None)
    diagnostico = getattr(original, "diag", None)
    constraint = getattr(diagnostico, "constraint_name", None)
    if codigo == "23514" and constraint == "chk_eam_actor_exclusivo":
        return ("actor",)
    if codigo == "22P02":
        # psycopg2 no expone el nombre del enum en diag: se inspecciona internamente,
        # sin devolver el mensaje ni parámetros SQL al emisor.
        mensaje = str(original)
        for enum, campo in (("enum_tipo_evento_auditoria_m04", "tipo_evento"),
                            ("enum_tipo_actor_auditoria", "tipo_actor")):
            if enum in mensaje:
                return (campo,)
    return ()
