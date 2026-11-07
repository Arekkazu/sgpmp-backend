# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: enlaza fuentes confirmadas al worker existente |
"""Proyecciones auditables, sin copiar payloads ni modificar las fuentes."""
from datetime import timezone
from sqlalchemy import select

from src.telemetry.application.use_cases.auditoria.evidencia_iot import registrar_evidencia
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen as C, EntidadAfectadaTipo as E, TipoResultado as R, SeveridadLog as S,
)
from src.telemetry.infrastructure.models.bitacora_ingest_model import BitacoraIngestModel
from src.telemetry.infrastructure.models.telemetria_model import TelemetriaModel
from src.telemetry.infrastructure.models.heartbeat_model import HeartbeatModel
from src.telemetry.infrastructure.models.historico_transicion_dispositivo_model import HistoricoTransicionDispositivoModel
from src.telemetry.infrastructure.models.bitacora_auditoria_iot_model import BitacoraAuditoriaIotModel
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository


def _lectura_auditada(db, identificador):
    tabla = BitacoraAuditoriaIotModel
    return db.execute(select(tabla.id_evento).where(
        tabla.tipo_evento == 'TELEMETRIA_VALIDADA', tabla.componente_origen == 'RF53',
        tabla.entidad_afectada_tipo == 'LECTURA',
        tabla.entidad_afectada_id == str(identificador),
    ).limit(1)).first() is not None


def auditar_lectura(db, identificador):
    # Recupera también lecturas confirmadas si el log SQL best-effort faltó.
    if _lectura_auditada(db, identificador):
        return
    fila = db.get(TelemetriaModel, identificador)
    registrar_evidencia(SqlAlchemyBitacoraAuditoriaIotRepository(db), 'TELEMETRIA_VALIDADA', C.RF53,
        entidad=E.LECTURA, identificador=identificador,
        fecha=fila.timestamp_procesamiento.astimezone(timezone.utc),
        resultado=R.EXITOSO if fila.estado_calidad == 'LECTURA_VALIDA' else R.ADVERTENCIA,
        detalle={'fuente': 'telemetrias', 'id_origen': identificador,
                 'id_dispositivo_iot': fila.id_dispositivo_iot, 'id_sensor': fila.id_sensor,
                 'id_variable': fila.id_variable, 'estado_calidad': fila.estado_calidad,
                 'timestamp_captura': fila.timestamp_captura.isoformat()})


def auditar_ingesta(db, identificador):
    fila = db.get(BitacoraIngestModel, identificador)
    estado = fila.estado_calidad
    tipos = {'ERROR_DUPLICADO': 'DUPLICADO_DETECTADO',
             'ERROR_AUTENTICACION': 'ERROR_AUTENTICACION_DISPOSITIVO',
             'ERROR_ESTRUCTURA': 'ERROR_ESTRUCTURA_MENSAJE',
             'ERROR_PERSISTENCIA': 'FALLA_PERSISTENCIA'}
    aceptada = fila.id_telemetria is not None and estado in (
        'LECTURA_VALIDA', 'FUERA_DE_RANGO', 'ERROR_CALIBRACION')
    if aceptada:
        auditar_lectura(db, fila.id_telemetria)
        return
    tipo = 'TELEMETRIA_VALIDADA' if aceptada else tipos.get(estado, 'TELEMETRIA_RECHAZADA')
    registrar_evidencia(SqlAlchemyBitacoraAuditoriaIotRepository(db), tipo, C.RF53,
        entidad=E.LECTURA if fila.id_telemetria is not None else None,
        identificador=fila.id_telemetria, fecha=fila.fecha_evento.astimezone(timezone.utc),
        resultado=R.EXITOSO if aceptada else R.RECHAZADO,
        severidad=S.INFO if estado == 'LECTURA_VALIDA' else S.WARNING,
        detalle={'fuente': 'bitacora_ingest', 'id_origen': identificador,
                 'id_dispositivo_iot': fila.id_dispositivo_iot, 'id_sensor': fila.id_sensor,
                 'estado_calidad': estado, 'fecha_evento': fila.fecha_evento.isoformat()})


def auditar_heartbeat(db, identificador):
    fila = db.get(HeartbeatModel, identificador)
    registrar_evidencia(SqlAlchemyBitacoraAuditoriaIotRepository(db), 'HEARTBEAT_RECIBIDO', C.RF60,
        entidad=E.HEARTBEAT, identificador=identificador,
        fecha=fila.fecha_recepcion.astimezone(timezone.utc),
        detalle={'id_dispositivo_iot': fila.id_dispositivo_iot})


def auditar_transicion(db, identificador):
    fila = db.get(HistoricoTransicionDispositivoModel, identificador)
    # Dos triggers existentes pueden materializar la misma transición con now().
    # Se preservan ambas fuentes, pero solo una evidencia de la transición real.
    clave = {'id_dispositivo_iot': fila.id_dispositivo_iot,
             'estado_anterior': fila.estado_anterior, 'estado_nuevo': fila.estado_nuevo,
             'fecha_transicion': fila.fecha_transicion.astimezone(timezone.utc).isoformat()}
    tabla = BitacoraAuditoriaIotModel
    if db.execute(select(tabla.id_evento).where(
        tabla.componente_origen == 'RF60', tabla.accion_detallada['transicion'] == clave
    ).limit(1)).first():
        return
    tipo = {'SIN_SEÑAL': 'DISPOSITIVO_SIN_SEÑAL', 'INACTIVO': 'DISPOSITIVO_INACTIVO',
            'EN_MANTENIMIENTO': 'MANTENIMIENTO_INICIADO'}.get(fila.estado_nuevo, 'ESTADO_CAMBIADO')
    if fila.estado_nuevo == 'ACTIVO':
        tipo = 'MANTENIMIENTO_COMPLETADO' if fila.estado_anterior == 'EN_MANTENIMIENTO' else 'DISPOSITIVO_RECONECTADO'
    registrar_evidencia(SqlAlchemyBitacoraAuditoriaIotRepository(db), tipo, C.RF60,
        entidad=E.DISPOSITIVO, identificador=fila.id_dispositivo_iot,
        usuario=fila.id_usuairo_responsable, fecha=fila.fecha_transicion.astimezone(timezone.utc),
        detalle={'transicion': clave, 'id_historico': identificador,
                 'causa_primaria': fila.causa_primaria})
