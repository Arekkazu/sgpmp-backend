# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M03-147-G191 RF-63 CA-13: registra eventos incompletos sin rechazarlos |
# | 2026-11-19 | Arekkazu | SEG-M03-01 RF-63: el evento que no se pudo guardar se reintenta y su pérdida queda en ERROR |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso para registrar eventos en la bitácora de auditoría IoT (RF-63)."""
from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.telemetry.domain.entities.evento_auditoria_iot import (
    ClasificacionRegistro,
    ComponenteOrigen,
    EntidadAfectadaTipo,
    EventoAuditoriaIot,
    SeveridadLog,
    TipoResultado,
    clasificar_componente,
)
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository

logger = logging.getLogger(__name__)

# tipo_evento es NOT NULL: un evento recibido sin tipo se guarda con este valor.
TIPO_EVENTO_NO_INFORMADO = 'TIPO_EVENTO_NO_INFORMADO'

# SEG-M03-01: eventos que no se pudieron guardar; se reintentan tras el siguiente registro exitoso.
# ponytail: vive en la memoria del proceso (se pierde al reiniciar y cada worker tiene la suya); el
# evento completo queda además en el log ERROR. Pasar a un respaldo durable como M02 si hace falta.
_PENDIENTES: deque[tuple[EventoAuditoriaIot, int]] = deque(maxlen=1000)
_MAX_INTENTOS = 3


def _calcular_hash(evento: EventoAuditoriaIot) -> str:
    """SHA-256 sobre campos del evento (excepto hash e id_evento)."""
    payload = {
        'tipo_evento': evento.tipo_evento,
        'fecha_hora': evento.fecha_hora.isoformat(),
        'resultado': evento.resultado.value if isinstance(evento.resultado, TipoResultado) else evento.resultado,
        'modulo': evento.modulo,
        'id_usuario': evento.id_usuario,
        'nombre_usuario': evento.nombre_usuario,
        'descripcion': evento.descripcion,
        'entidad_afectada_tipo': evento.entidad_afectada_tipo.value if isinstance(evento.entidad_afectada_tipo, EntidadAfectadaTipo) else evento.entidad_afectada_tipo,
        'entidad_afectada_id': evento.entidad_afectada_id,
        'severidad_log': evento.severidad_log.value if isinstance(evento.severidad_log, SeveridadLog) else evento.severidad_log,
        'componente_origen': evento.componente_origen.value if isinstance(evento.componente_origen, ComponenteOrigen) else evento.componente_origen,
        'accion_detallada': evento.accion_detallada,
    }
    contenido = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(contenido.encode('utf-8')).hexdigest()


class RegistrarEventoAuditoriaIotUseCase:
    """RF-63: Registra un evento de auditoría IoT con hash SHA-256 y clasificación NIC41/TECNICO.
    Operación best-effort: los errores internos no se propagan para no bloquear el flujo principal.
    """

    def __init__(self, db: Session, auditoria_repo: BitacoraAuditoriaIotRepository) -> None:
        self.db = db
        self.auditoria_repo = auditoria_repo

    def execute(
        self,
        tipo_evento: Optional[str],
        resultado: TipoResultado,
        componente_origen: Optional[ComponenteOrigen],
        severidad_log: SeveridadLog = SeveridadLog.INFO,
        descripcion: Optional[str] = None,
        entidad_afectada_tipo: Optional[EntidadAfectadaTipo] = None,
        entidad_afectada_id: Optional[str] = None,
        accion_detallada: Optional[dict] = None,
        id_usuario: Optional[int] = None,
        nombre_usuario: Optional[str] = None,
        id_sesion: Optional[UUID] = None,
        direccion_ip: Optional[str] = None,
        registro_incompleto: bool = False,
        fecha_evento: Optional[datetime] = None,
    ) -> None:
        """``fecha_evento`` es el instante en que ocurrió el evento (por omisión, ahora).

        RF-63 CA-13 / E3: si falta ``tipo_evento`` o el RF emisor el evento se
        registra igual, con ``registro_incompleto=true`` y los campos faltantes en
        ``accion_detallada.campos_faltantes``.
        """
        try:
            faltantes = [campo for campo, valor in (
                ('tipo_evento', tipo_evento), ('rf_origen', componente_origen)) if not valor]
            if faltantes:
                registro_incompleto = True
                accion_detallada = {**(accion_detallada or {}), 'campos_faltantes': faltantes}
                tipo_evento = tipo_evento or TIPO_EVENTO_NO_INFORMADO
            clasificacion, retencion = clasificar_componente(componente_origen)
            ahora = fecha_evento or datetime.now(timezone.utc)

            evento = EventoAuditoriaIot(
                id_evento=None,
                tipo_evento=tipo_evento,
                fecha_hora=ahora,
                resultado=resultado,
                modulo='M03',
                id_usuario=id_usuario,
                nombre_usuario=nombre_usuario,
                descripcion=descripcion,
                accion_detallada=accion_detallada,
                entidad_afectada_tipo=entidad_afectada_tipo,
                entidad_afectada_id=entidad_afectada_id,
                severidad_log=severidad_log,
                hash_integridad='',
                clasificacion_registro=clasificacion,
                retencion_aplicable=retencion,
                registro_incompleto=registro_incompleto,
                componente_origen=componente_origen,
            )
            evento.hash_integridad = _calcular_hash(evento)

        except Exception:
            logger.exception('RF-63: no se pudo armar el evento de auditoría (tipo=%s).', tipo_evento)
            return
        if self._guardar(evento):
            self._reintentar_pendientes()
        else:
            self._encolar(evento, 1)

    def _guardar(self, evento: EventoAuditoriaIot) -> bool:
        """Guarda y confirma; ``False`` si falla (la transacción queda revertida)."""
        try:
            # El adaptador best-effort devuelve el evento sin ID si falla: no confirmar ni aparentar éxito.
            if self.auditoria_repo.registrar(evento).id_evento is None:
                raise RuntimeError('el repositorio no devolvió id_evento')
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False

    def _reintentar_pendientes(self) -> None:
        for _ in range(len(_PENDIENTES)):
            evento, intentos = _PENDIENTES.popleft()
            if not self._guardar(evento):
                self._encolar(evento, intentos + 1)
                return  # la bitácora volvió a fallar: los demás esperan al siguiente registro

    @staticmethod
    def _encolar(evento: EventoAuditoriaIot, intentos: int) -> None:
        if intentos > _MAX_INTENTOS:
            logger.error('RF-63: evento de auditoría descartado tras %s intentos: %s', _MAX_INTENTOS, evento)
            return
        if len(_PENDIENTES) == _PENDIENTES.maxlen:
            logger.error('RF-63: cola de reintentos llena, se descarta el evento más antiguo: %s', _PENDIENTES[0][0])
        _PENDIENTES.append((evento, intentos))
        logger.error('RF-63: no se pudo registrar el evento de auditoría (tipo=%s, intento %s); queda para reintento: %s',
                     evento.tipo_evento, intentos, evento)
