# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: evidencia obligatoria sin commits implicitos |
"""Construcción única de evidencia; la transacción pertenece al llamador."""
from datetime import datetime, timezone

from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
from src.telemetry.domain.entities.evento_auditoria_iot import (
    EventoAuditoriaIot, SeveridadLog, TipoResultado, clasificar_componente,
)


def registrar_evidencia(repo, tipo, componente, *, entidad=None, identificador=None,
                       detalle=None, usuario=None, resultado=TipoResultado.EXITOSO,
                       severidad=SeveridadLog.INFO, fecha=None, descripcion=None):
    clasificacion, retencion = clasificar_componente(componente)
    evento = EventoAuditoriaIot(
        id_evento=None, tipo_evento=tipo, fecha_hora=fecha or datetime.now(timezone.utc),
        resultado=resultado, componente_origen=componente,
        entidad_afectada_tipo=entidad,
        entidad_afectada_id=str(identificador) if identificador is not None else None,
        accion_detallada=detalle, id_usuario=usuario, descripcion=descripcion,
        severidad_log=severidad, clasificacion_registro=clasificacion,
        retencion_aplicable=retencion,
    )
    evento.hash_integridad = _calcular_hash(evento)
    persistido = repo.registrar(evento)
    if persistido.id_evento is None:
        raise RuntimeError('No se confirmó la evidencia obligatoria RF-63.')
    return persistido
