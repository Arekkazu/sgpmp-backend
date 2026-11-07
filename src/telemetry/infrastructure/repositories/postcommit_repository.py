# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-41 RF-53/57: prerequisitos y correlacion durable |
# | 2026-10-22 | Leandro | DEV-28 RF-60: reclama vision con evidencia y lock de DEV-05 |
# | 2026-10-22 | Leandro | DEV-44 RF-61: recupera avisos sin duplicar vinculacion |
# | 2026-10-22 | Leandro | DEV-47 RF-63: recupera resultados por lectura y transicion sin duplicarlos |
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: pendientes de la etapa de calidad de vision |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-12 RF-63: reintentos con espera creciente, no un FALLIDO por minuto |
# | 2026-10-31 | Claude | INC-M03-235-G16 RF-62: pendientes sin anti-join cuadrático bajo RLS |
"""RF-63 es el registro durable de etapas; no se agrega una tabla de transporte.

La conexión queda fijada a una transacción externa. Los commits de los casos de
uso existentes liberan SAVEPOINTs: los efectos y la evidencia se confirman juntos.
Los locks se conservan hasta ese commit externo, también entre casos de uso.
"""
from contextlib import contextmanager, nullcontext

from sqlalchemy import String, cast, func, literal, literal_column, select, text
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
from src.telemetry.infrastructure.models.observacion_vision_model import ObservacionVisionModel
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit


def _fuente(etapa):
    if etapa.es_vision:
        return ObservacionVisionModel.__table__, 'id_observacion_vision', 'LECTURA'
    if etapa is EtapaPostcommit.RF53_AUDITORIA:
        from src.telemetry.infrastructure.models.bitacora_ingest_model import BitacoraIngestModel
        return BitacoraIngestModel.__table__, 'id_bitacora_ingest', None
    if etapa is EtapaPostcommit.RF60_TRANSICIONES:
        from src.telemetry.infrastructure.models.historico_transicion_dispositivo_model import HistoricoTransicionDispositivoModel
        return HistoricoTransicionDispositivoModel.__table__, 'id_transaccion', None
    if etapa.es_heartbeat:
        return HeartbeatModel.__table__, 'id_heartbeat', 'HEARTBEAT'
    return TelemetriaModel.__table__, 'id_telemetria', 'LECTURA'


def _tipo(etapa, fallo=False):
    return 'POSTCOMMIT_' + etapa.value + ('_FALLIDO' if fallo else '_COMPLETADO')


def _de_la_etapa(etapa, identificador, fallo=False):
    auditoria = BitacoraAuditoriaIotModel.__table__
    return (
        auditoria.c.entidad_afectada_tipo == _fuente(etapa)[2],
        auditoria.c.entidad_afectada_id == identificador,
        auditoria.c.tipo_evento == _tipo(etapa, fallo),
    )


def _registro(etapa, identificador, fallo=False):
    return select(1).where(*_de_la_etapa(etapa, identificador, fallo)).exists()


def _con_registro(etapa, identificador, fallo=False):
    """G16 (#875): igual que ``_registro`` pero como subconsulta escalar por fila.

    Con RLS (rc.11–rc.15) las políticas de la bitácora impiden empujar la condición
    de unión dentro del escaneo protegido y PostgreSQL convertía el NOT EXISTS de
    ``pendientes`` en un anti-join por bucle anidado contra todos los COMPLETADO:
    cuadrático en el historial. Con ~100 k lecturas pasaba de 60 s, el worker lo
    cortaba a los 10 s (``statement_timeout``) y la etapa RF-62 no volvía a correr.
    La subconsulta escalar no se aplana a anti-join: es una búsqueda por índice
    (``idx_bitacora_iot_tipo_evento_entidad_afectada_id``) por lectura.
    """
    return func.coalesce(
        select(literal(True)).where(*_de_la_etapa(etapa, identificador, fallo)).limit(1).scalar_subquery(),
        False,
    )


def _listo_para_reintento(etapa, identificador, base_seg, tope_seg):
    """M3-12: la espera se duplica con cada fallo (base, 2·base, 4·base…) hasta `tope_seg`.

    Antes era fija (60 s): un error que no se arregla solo (parámetro sin
    configurar, firmware "pi-test") dejaba un FALLIDO por minuto y por fila en la
    bitácora inmutable, más de 1,39 M eventos. La fila se sigue reintentando —se
    recupera sola cuando se corrige la configuración—, pero a lo sumo una vez por
    `tope_seg`.
    """
    auditoria = BitacoraAuditoriaIotModel.__table__
    # count y max en la misma agregación: con un max() solo, Postgres lo resuelve
    # recorriendo idx_bitacora_iot_fecha hacia atrás (130 s con 2 M de eventos) en
    # vez de usar idx_bitacora_iot_tipo_evento_entidad_afectada_id. El exponente se
    # acota porque con miles de fallos previos 2^n desborda el double de Postgres.
    espera = func.least(base_seg * func.power(2, func.least(func.count() - 1, 30)), tope_seg)
    en_espera = select(
        func.max(auditoria.c.fecha_hora) > func.clock_timestamp() - espera * literal_column("interval '1 second'")
    ).where(*_de_la_etapa(etapa, identificador, fallo=True)).scalar_subquery()
    # Sin fallos previos max() es NULL: la fila está lista.
    return ~func.coalesce(en_espera, False)


class SqlAlchemyPostcommitRepository:
    def __init__(self, db, transaccion):
        self.db = db
        self.transaccion = transaccion

    def pendientes(self, etapa, limite, reintento_seg, reintento_max_seg=None):
        tabla, columna, _ = _fuente(etapa)
        identificador = cast(tabla.c[columna], String)
        consulta = select(tabla.c[columna]).where(
            ~_con_registro(etapa, identificador),
            _listo_para_reintento(etapa, identificador, reintento_seg, reintento_max_seg or reintento_seg),
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
        if etapa is EtapaPostcommit.VISION_DETECCION:
            consulta = consulta.where(tabla.c.fecha_inicio_ventana.is_not(None))
        if etapa is EtapaPostcommit.VISION_CALIDAD:
            # Las históricas ya traen su evaluación (8c4e2a6f1b93): no se reevalúan.
            consulta = consulta.where(tabla.c.fecha_evaluacion_calidad.is_(None))
        if etapa is EtapaPostcommit.RF61_AVISOS:
            from src.telemetry.infrastructure.models.vinculacion_lectura_model import VinculacionLecturaModel
            v=VinculacionLecturaModel.__table__
            consulta=consulta.where(select(1).where(v.c.id_telemetria==tabla.c.id_telemetria,
                v.c.fecha_fin_vinculacion.is_(None),
                (v.c.causa=='CONFIGURACION_INCOMPLETA')|v.c.estado_vinculacion.in_(['AMBIGUA','PENDIENTE_REVISION'])).exists())
        for requisito in etapa.requisitos:
            consulta = consulta.where(_con_registro(requisito, identificador))
        return list(self.db.execute(consulta.order_by(tabla.c[columna]).limit(limite)).scalars())

    def reclamar(self, etapa, identificador):
        tabla, columna, _ = _fuente(etapa)
        fila = self.db.execute(select(tabla.c.id_dispositivo_iot).where(
            tabla.c[columna] == identificador).with_for_update(skip_locked=True)).first()
        if fila is None:
            return False
        # Serializa también distintas filas del mismo dispositivo, sin I/O externo.
        if fila[0] is not None and not self.db.execute(text('SELECT pg_try_advisory_xact_lock(3505, :id)'), {'id': fila[0]}).scalar_one():
            return False
        # Una nueva sentencia/snapshot tras el lock evita duplicados si otro
        # proceso acaba de confirmar la evidencia que faltaba al hacer la selección.
        if self.db.execute(select(_registro(etapa, str(identificador)))).scalar_one():
            return False
        for requisito in etapa.requisitos:
            if not self.db.execute(select(_registro(requisito, str(identificador)))).scalar_one():
                return False
        return True

    def registrar(self, etapa, identificador, error=None, *, detalle=None):
        if etapa in (EtapaPostcommit.RF53_LECTURAS, EtapaPostcommit.RF53_AUDITORIA):
            componente = ComponenteOrigen.RF53
        elif etapa is EtapaPostcommit.VISION_CALIDAD:
            componente = ComponenteOrigen.RF62
        elif etapa.es_heartbeat or etapa.es_vision or etapa is EtapaPostcommit.RF60_TRANSICIONES:
            componente = ComponenteOrigen.RF60
        elif etapa is EtapaPostcommit.RF61_AVISOS:
            componente = ComponenteOrigen.RF61
        else:
            componente = ComponenteOrigen(etapa.value)
        clasificacion, retencion = clasificar_componente(componente)
        evento = EventoAuditoriaIot(
            id_evento=None, tipo_evento=_tipo(etapa, error is not None),
            fecha_hora=self.db.execute(text('SELECT clock_timestamp()')).scalar_one(),
            resultado=TipoResultado.FALLIDO if error else TipoResultado.EXITOSO,
            descripcion='Etapa postcommit pendiente de reintento.' if error else 'Etapa postcommit completada.',
            entidad_afectada_tipo=EntidadAfectadaTipo(_fuente(etapa)[2]) if _fuente(etapa)[2] else None,
            entidad_afectada_id=str(identificador),
            accion_detallada={'etapa': etapa.value, 'fuente': _fuente(etapa)[0].name,
                'id_origen': identificador, 'error': error,
                **({'resultado_etapa': detalle} if detalle is not None else {})},
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
