"""[INC-M09-70-G29][RF-17] Observabilidad de la sincronización de umbrales con el Edge (#532).

- Cada propagación deja un evento ``PROPAGACION_UMBRAL_EDGE`` en la bitácora IoT
  (RF-63) con el Gateway, si el broker publicó, si hubo ``ACK_UMBRAL``, la causa
  y la duración. Se registra también cuando RF-17 responde 500.
- Un ``NO_CONF`` del adaptador lleva la causa concreta (HTTP del broker, error
  de red), no solo "No se pudo contactar al broker".
- ``tiempo_sin_contacto`` del estado IoT se calcula al responder.
"""
from __future__ import annotations

import datetime

import httpx
import pytest

from src.configuration.application.use_cases.umbrales.sincronizar_umbral_edge import (
    EVENTO_PROPAGACION_UMBRAL,
    MOTIVO_SIN_GATEWAY_EDGE,
)
from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt
from src.configuration.infrastructure.adapters import bitacora_iot_m03_adapter, edge_sincronizacion_mqtt_adapter
from src.configuration.infrastructure.adapters.bitacora_iot_m03_adapter import BitacoraIotM03Adapter
from src.configuration.infrastructure.adapters.edge_sincronizacion_mqtt_adapter import EdgeSincronizacionMqttAdapter
from src.shared.errors import InfrastructureError
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
    EntidadAfectadaTipo,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.infrastructure.schema.estado_dispositivo_iot_schema import EstadoDispositivoIoTSchema
from tests.configuration.test_inc_m09_104_g29_sincronizacion_edge_umbrales import (
    APLICADA,
    NO_CONF,
    PENDIENTE,
    BitacoraFake,
    DbFake,
    EdgePortFake,
    UmbralRepoFake,
    _RespuestaFalsa,
    _editar,
    _registrar,
    _umbral_existente,
)


class TestTrazabilidadPropagacion:
    def test_aplicada_registra_gateway_ack_version_y_duracion(self) -> None:
        bitacora = BitacoraFake()
        aplicada = ResultadoEnvioMqtt(estado='APLICADA', mensaje='El dispositivo confirmó.', publicado=True)

        _registrar(EdgePortFake(**{'EDGE-1': aplicada}), bitacora=bitacora)

        (evento,) = bitacora.propagaciones
        assert evento['evento'] == EVENTO_PROPAGACION_UMBRAL
        assert (evento['id_umbral_ambiental'], evento['id_usuario']) == (1, 1)
        assert (evento['estado'], evento['fallo']) == ('APLICADA', False)
        detalle = evento['detalle']
        assert detalle['variable'] == 'Temperatura'
        assert isinstance(detalle['duracion_ms'], int)
        assert detalle['gateways'] == [
            {
                'serial': 'EDGE-1',
                'estado': 'APLICADA',
                'publicado': True,
                'ack_umbral': True,
                'mensaje': 'El dispositivo confirmó.',
            }
        ]

    def test_no_conf_queda_registrado_antes_del_500(self) -> None:
        bitacora = BitacoraFake()

        with pytest.raises(InfrastructureError):
            _registrar(
                EdgePortFake(**{'EDGE-1': APLICADA, 'EDGE-2': NO_CONF}),
                seriales=('EDGE-1', 'EDGE-2'),
                bitacora=bitacora,
            )

        (evento,) = bitacora.propagaciones
        assert (evento['estado'], evento['fallo']) == ('NO_CONF', True)
        assert evento['detalle']['motivo'] == 'EDGE-2: Sin ACK a tiempo.'
        assert [(g['serial'], g['ack_umbral']) for g in evento['detalle']['gateways']] == [
            ('EDGE-1', True),
            ('EDGE-2', False),
        ]

    def test_edge_desconectado_en_la_edicion_queda_registrado(self) -> None:
        """TC-M09-63: la edición B queda PENDIENTE, sin ACK, y la bitácora lo muestra."""
        bitacora = BitacoraFake()

        with pytest.raises(InfrastructureError):
            _editar(EdgePortFake(**{'EDGE-1': PENDIENTE}), UmbralRepoFake(existente=_umbral_existente()), bitacora=bitacora)

        (evento,) = bitacora.propagaciones
        assert (evento['estado'], evento['fallo']) == ('PENDIENTE', True)
        assert evento['detalle']['version'] is not None
        assert evento['detalle']['gateways'][0]['ack_umbral'] is False

    def test_sin_gateway_registra_el_intento_sin_fallo(self) -> None:
        bitacora = BitacoraFake()

        _registrar(EdgePortFake(), seriales=(), bitacora=bitacora)

        (evento,) = bitacora.propagaciones
        assert (evento['estado'], evento['fallo']) == ('PENDIENTE', False)
        assert evento['detalle']['gateways'] == []
        assert evento['detalle']['motivo'] == MOTIVO_SIN_GATEWAY_EDGE

    def test_si_no_se_pudo_persistir_el_estado_no_registra(self) -> None:
        class RepoQueFalla(UmbralRepoFake):
            def actualizar_estado_sincronizacion(self, umbral):
                raise RuntimeError('BD caída')

        bitacora = BitacoraFake()
        db = DbFake()

        with pytest.raises(RuntimeError):
            _registrar(EdgePortFake(**{'EDGE-1': APLICADA}), umbral_repo=RepoQueFalla(), db=db, bitacora=bitacora)

        assert bitacora.propagaciones == []
        assert db.rollbacks == 1


class TestCausaDelNoConf:
    @pytest.fixture(autouse=True)
    def _broker_configurado(self, monkeypatch):
        monkeypatch.setenv('MQTT_BROKER_URL', 'http://broker')
        monkeypatch.setenv('MQTT_BROKER_TOKEN', 'tok')

    def _propagar(self, monkeypatch, post) -> ResultadoEnvioMqtt:
        monkeypatch.setattr(edge_sincronizacion_mqtt_adapter.httpx, 'post', post)
        (resultado,) = EdgeSincronizacionMqttAdapter().propagar_umbral(['EDGE-1'], {}).values()
        return resultado

    def test_broker_que_rechaza_el_comando_muestra_status_y_detalle(self, monkeypatch) -> None:
        """El NO_CONF de TEST (2026-10-08): el broker sin #24 respondía 422 al origen "umbral"."""
        detalle = {'detail': [{'loc': ['body', 'origen'], 'msg': "Input should be 'configuracion'"}]}

        resultado = self._propagar(monkeypatch, lambda *a, **k: _RespuestaFalsa(detalle, status=422))

        assert resultado.estado == 'NO_CONF'
        assert resultado.publicado is False
        assert 'HTTP 422' in resultado.mensaje
        assert "Input should be 'configuracion'" in resultado.mensaje

    def test_broker_inalcanzable_nombra_el_error_de_red(self, monkeypatch) -> None:
        def post(*a, **k):
            raise httpx.ConnectError('caído')

        resultado = self._propagar(monkeypatch, post)

        assert resultado.estado == 'NO_CONF'
        assert 'ConnectError' in resultado.mensaje

    def test_respuesta_sin_estado_es_respuesta_invalida(self, monkeypatch) -> None:
        resultado = self._propagar(monkeypatch, lambda *a, **k: _RespuestaFalsa({'mensaje': 'x'}))

        assert resultado.estado == 'NO_CONF'
        assert 'respuesta inválida del broker (KeyError)' in resultado.mensaje

    @pytest.mark.parametrize(
        ('cuerpo', 'publicado'),
        [
            ({'estado': 'NO_CONF', 'mensaje': 'sin ACK', 'topic': 'sgpmp/EDGE-1/command'}, True),
            ({'estado': 'PENDIENTE', 'mensaje': 'EDGE-1 no está conectado', 'topic': None}, False),
        ],
        ids=['publicado-sin-ack', 'no-publicado'],
    )
    def test_publicado_sale_del_topic_que_devuelve_el_broker(self, monkeypatch, cuerpo, publicado) -> None:
        resultado = self._propagar(monkeypatch, lambda *a, **k: _RespuestaFalsa(cuerpo))

        assert resultado.publicado is publicado


class TestBitacoraIotM03Adapter:
    @pytest.mark.parametrize(
        ('estado', 'fallo', 'resultado', 'severidad'),
        [
            ('APLICADA', False, TipoResultado.EXITOSO, SeveridadLog.INFO),
            ('NO_CONF', True, TipoResultado.FALLIDO, SeveridadLog.ERROR),
            ('PENDIENTE', False, TipoResultado.ADVERTENCIA, SeveridadLog.WARNING),
        ],
    )
    def test_evento_sobre_el_umbral_consultable_por_su_id(self, monkeypatch, estado, fallo, resultado, severidad) -> None:
        eventos = []

        class RepoFake:
            def __init__(self, db) -> None:
                pass

            def registrar(self, evento) -> None:
                eventos.append(evento)

        monkeypatch.setattr(bitacora_iot_m03_adapter, 'SqlAlchemyBitacoraAuditoriaIotRepository', RepoFake)

        BitacoraIotM03Adapter(DbFake()).registrar_propagacion_umbral(
            evento=EVENTO_PROPAGACION_UMBRAL,
            id_umbral_ambiental=64,
            id_usuario=1,
            estado=estado,
            fallo=fallo,
            detalle={'gateways': []},
        )

        (evento,) = eventos
        assert evento.tipo_evento == 'PROPAGACION_UMBRAL_EDGE'
        assert (evento.resultado, evento.severidad_log) == (resultado, severidad)
        assert evento.entidad_afectada_tipo == EntidadAfectadaTipo.UMBRAL
        assert evento.entidad_afectada_id == '64'
        assert evento.componente_origen == ComponenteOrigen.RF17
        assert evento.accion_detallada == {'id_umbral_ambiental': 64, 'estado': estado, 'gateways': []}
        assert evento.hash_integridad


class TestTiempoSinContactoEnVivo:
    def _estado(self, fecha_ultimo_contacto, tiempo_guardado) -> EstadoDispositivoIoTSchema:
        return EstadoDispositivoIoTSchema(
            id_estado_dispositivo_iot=1,
            id_dispositivo_iot=138,
            estado_actual='SIN_SEÑAL',
            fecha_ultimo_contacto=fecha_ultimo_contacto,
            tiempo_sin_contacto=tiempo_guardado,
            fecha_ultima_actualizacion=datetime.datetime.now(datetime.timezone.utc),
        )

    def test_se_calcula_desde_el_ultimo_contacto_y_no_desde_la_columna(self) -> None:
        hace_diez_min = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)

        estado = self._estado(hace_diez_min, tiempo_guardado=354)

        assert 600 <= estado.tiempo_sin_contacto <= 605

    def test_sin_contacto_previo_conserva_el_valor(self) -> None:
        assert self._estado(None, tiempo_guardado=None).tiempo_sin_contacto is None
