"""RF-63 es el registro durable de etapas; no se agrega una tabla de transporte.

La conexión queda fijada a una transacción externa. Los commits de los casos de
uso existentes liberan SAVEPOINTs: los efectos y la evidencia se confirman juntos.
Los locks se conservan hasta ese commit externo, también entre casos de uso.
"""
from contextlib import contextmanager, nullcontext

from sqlalchemy import String, cast, func, literal_column, select, text
from sqlalchemy.orm import Session
from sqlalchemy.engine import Connection

from src.shared.database import declarar_identidad_sistema
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen, EntidadAfectadaTipo, EventoAuditoriaIot, SeveridadLog,
    TipoResultado, clasificar_componente,
)
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.models.bitacora_auditoria_iot_model import BitacoraAuditoriaIotModel
from src.telemetry.infrastructure.models.heartbeat_model import HeartbeatModel
from src.telemetry.infrastructure.models.telemetria_model import TelemetriaModel
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit


def _fuente(etapa):
    if etapa.es_heartbeat:
        return HeartbeatModel.__table__, 'id_heartbeat', 'HEARTBEAT'
    return TelemetriaModel.__table__, 'id_telemetria', 'LECTURA'


def _tipo(etapa, fallo=False):
    return 'POSTCOMMIT_' + etapa.value + ('_FALLIDO' if fallo else '_COMPLETADO')


def _registro(etapa, identificador, fallo=False, espera=None):
    auditoria = BitacoraAuditoriaIotModel.__table__
    consulta = select(1).where(
        auditoria.c.entidad_afectada_tipo == _fuente(etapa)[2],
        auditoria.c.entidad_afectada_id == identificador,
        auditoria.c.tipo_evento == _tipo(etapa, fallo),
    )
    if espera is not None:
        consulta = consulta.where(auditoria.c.fecha_hora >
            func.clock_timestamp() - espera * literal_column("interval '1 second'"))
    return consulta.exists()


class SqlAlchemyPostcommitRepository:
    def __init__(self, db, transaccion):
        self.db = db
        self.transaccion = transaccion

    def pendientes(self, etapa, limite, reintento_seg):
        tabla, columna, _ = _fuente(etapa)
        identificador = cast(tabla.c[columna], String)
        consulta = select(tabla.c[columna]).where(
            ~_registro(etapa, identificador),
            ~_registro(etapa, identificador, fallo=True, espera=reintento_seg),
        )
        campo = {
            EtapaPostcommit.HEARTBEAT_SENSORES: 'json_sensores_operativos',
            EtapaPostcommit.HEARTBEAT_TEMPERATURA: 'temperatura_dispositivo',
            EtapaPostcommit.HEARTBEAT_FIRMWARE: 'version_firmware',
        }.get(etapa)
        if campo:
            consulta = consulta.where(tabla.c[campo].is_not(None))
            if etapa is EtapaPostcommit.HEARTBEAT_SENSORES:
                consulta = consulta.where(func.jsonb_typeof(tabla.c[campo]) != 'null')
        if etapa.requisito:
            consulta = consulta.where(_registro(etapa.requisito, identificador))
        return list(self.db.execute(consulta.order_by(tabla.c[columna]).limit(limite)).scalars())

    def reclamar(self, etapa, identificador):
        tabla, columna, _ = _fuente(etapa)
        fila = self.db.execute(select(tabla.c.id_dispositivo_iot).where(
            tabla.c[columna] == identificador).with_for_update(skip_locked=True)).first()
        if fila is None:
            return False
        # Serializa también distintas filas del mismo dispositivo, sin I/O externo.
        if not self.db.execute(text('SELECT pg_try_advisory_xact_lock(3505, :id)'), {'id': fila[0]}).scalar_one():
            return False
        # Una nueva sentencia/snapshot tras el lock evita duplicados si otro
        # proceso acaba de confirmar la evidencia que faltaba al hacer la selección.
        if self.db.execute(select(_registro(etapa, str(identificador)))).scalar_one():
            return False
        if etapa.requisito:
            return self.db.execute(select(_registro(etapa.requisito, str(identificador)))).scalar_one()
        return True

    def registrar(self, etapa, identificador, error=None):
        componente = ComponenteOrigen.RF60 if etapa.es_heartbeat else ComponenteOrigen(etapa.value)
        clasificacion, retencion = clasificar_componente(componente)
        evento = EventoAuditoriaIot(
            id_evento=None, tipo_evento=_tipo(etapa, error is not None),
            fecha_hora=self.db.execute(text('SELECT clock_timestamp()')).scalar_one(),
            resultado=TipoResultado.FALLIDO if error else TipoResultado.EXITOSO,
            descripcion='Etapa postcommit pendiente de reintento.' if error else 'Etapa postcommit completada.',
            entidad_afectada_tipo=EntidadAfectadaTipo(_fuente(etapa)[2]),
            entidad_afectada_id=str(identificador),
            accion_detallada={'etapa': etapa.value, 'fuente': _fuente(etapa)[0].name, 'id_origen': identificador, 'error': error},
            componente_origen=componente, clasificacion_registro=clasificacion,
            retencion_aplicable=retencion, severidad_log=SeveridadLog.WARNING if error else SeveridadLog.INFO,
        )
        evento.hash_integridad = _calcular_hash(evento)
        persistido = SqlAlchemyBitacoraAuditoriaIotRepository(self.db).registrar(evento)
        if persistido.id_evento is None:
            # El repositorio RF-63 es best-effort para otros consumidores; aquí la
            # evidencia es obligatoria para confirmar los efectos de la etapa.
            raise RuntimeError('No se confirmó la evidencia RF-63 de postcommit.')

    def confirmar(self):
        self.db.commit()
        self.transaccion.commit()


@contextmanager
def unidad_postcommit(engine, identidad=True):
    contexto = nullcontext(engine) if isinstance(engine, Connection) else engine.connect()
    with contexto as conexion:
        transaccion = conexion.begin_nested() if conexion.in_transaction() else conexion.begin()
        with Session(bind=conexion, join_transaction_mode='create_savepoint', expire_on_commit=False) as db:
            if identidad:
                declarar_identidad_sistema(db)
            try:
                db.execute(text("SELECT set_config('statement_timeout', '10000', true), set_config('lock_timeout', '2000', true)"))
                yield SqlAlchemyPostcommitRepository(db, transaccion)
            finally:
                db.close()
                if transaccion.is_active:
                    transaccion.rollback()
