from __future__ import annotations

import hashlib
import json
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
        tipo_evento: str,
        resultado: TipoResultado,
        componente_origen: ComponenteOrigen,
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
    ) -> None:
        try:
            clasificacion, retencion = clasificar_componente(componente_origen)
            ahora = datetime.now(timezone.utc)

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

            self.auditoria_repo.registrar(evento)
            self.db.commit()
        except Exception:
            self.db.rollback()
