# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: evidencia obligatoria en la transaccion de vinculacion |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo y función |
"""Evidencia de auditoría obligatoria en la transacción de vinculación (RF-61).

Registra el evento dentro de la misma transacción y falla si la evidencia no se
confirma, para no dejar vinculaciones sin rastro.
"""
from datetime import datetime, timezone
from src.telemetry.domain.entities.evento_auditoria_iot import (
    EventoAuditoriaIot,ComponenteOrigen,EntidadAfectadaTipo,TipoResultado,clasificar_componente,
)
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash


def registrar_evidencia(repo,tipo,identificador,detalle,id_usuario=None,*,entidad=EntidadAfectadaTipo.VINCULACION):
    """Registra la evidencia RF-61 y verifica que quede confirmada.

    Args:
        repo: Repositorio de bitácora de auditoría IoT.
        tipo: Tipo de evento de auditoría.
        identificador: Id de la entidad afectada.
        detalle: Acción detallada del evento.
        id_usuario: Usuario responsable, si aplica.
        entidad: Tipo de entidad afectada (por defecto, vinculación).

    Raises:
        RuntimeError: Si la evidencia no se confirma.
    """
    clasificacion,retencion=clasificar_componente(ComponenteOrigen.RF61)
    evento=EventoAuditoriaIot(id_evento=None,tipo_evento=tipo,fecha_hora=datetime.now(timezone.utc),
        resultado=TipoResultado.EXITOSO,componente_origen=ComponenteOrigen.RF61,
        entidad_afectada_tipo=entidad,entidad_afectada_id=str(identificador),
        clasificacion_registro=clasificacion,retencion_aplicable=retencion,
        accion_detallada=detalle,id_usuario=id_usuario)
    evento.hash_integridad=_calcular_hash(evento)
    if repo.registrar(evento).id_evento is None:
        raise RuntimeError('No se confirmo la evidencia RF-61.')
