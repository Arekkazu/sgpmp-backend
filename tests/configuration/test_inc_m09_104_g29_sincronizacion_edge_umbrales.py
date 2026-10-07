"""[INC-M09-104-G29][RF-17] TC-M09-62/TC-M09-63 — propagación real de umbrales al Nodo Edge.

La creación/edición de un umbral ambiental se propaga, después del commit, a
cada Gateway Edge de las áreas activas de su especie
(``modulo9.fn_seriales_gateway_edge_por_especie``) por el broker MQTT
(``POST /v1/commands`` con ``origen: "umbral"``, que espera el ``ACK_UMBRAL``
del Edge). El resultado de cada Gateway se consolida en un único
``estado_sincronizacion`` del umbral, que se persiste antes de responder:

- todos APLICADA → APLICADA + ``fecha_ultima_sincronizacion`` (201/200);
- alguno NO_CONF → NO_CONF y HTTP 500 ``FALLO_SINCRONIZACION_EDGE`` (RF-17);
- alguno PENDIENTE (Edge desconectado) o especie sin Gateway → PENDIENTE
  (201/200, TC-M09-58-G22 / #459: no es un fallo).

QA V4 rechazó la versión anterior porque los endpoints inyectaban
``EdgeSincronizacionStubAdapter`` (siempre PENDIENTE, sin transporte); el stub
ya no existe.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from src.configuration.application.use_cases.umbrales.editar_umbral_use_case import EditarUmbralUseCase
from src.configuration.application.use_cases.umbrales.registrar_umbral_use_case import RegistrarUmbralUseCase
from src.configuration.application.use_cases.umbrales.sincronizar_umbral_edge import (
    MOTIVO_SIN_GATEWAY_EDGE,
    consolidar_resultados,
)
from src.configuration.domain.entities.umbral_ambiental import MOTIVO_CAMBIOS_SIN_PROPAGAR, UmbralAmbiental
from src.configuration.domain.entities.variable_ambiental import VariableAmbiental
from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt
from src.configuration.infrastructure.adapters import edge_sincronizacion_mqtt_adapter
from src.configuration.infrastructure.adapters.edge_sincronizacion_mqtt_adapter import EdgeSincronizacionMqttAdapter
from src.configuration.infrastructure.dto.editar_umbral_dto import EditarUmbralDTO
from src.configuration.infrastructure.dto.nivel_dto import NivelDTO
from src.configuration.infrastructure.dto.registrar_umbral_dto import RegistrarUmbralDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import InfrastructureError

APLICADA = ResultadoEnvioMqtt(estado='APLICADA', mensaje='El dispositivo confirmó.')
PENDIENTE = ResultadoEnvioMqtt(estado='PENDIENTE', mensaje='EDGE no está conectado al broker.')
NO_CONF = ResultadoEnvioMqtt(estado='NO_CONF', mensaje='Sin ACK a tiempo.')


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class UmbralRepoFake:
    def __init__(self, existente: UmbralAmbiental | None = None) -> None:
        self.existente = existente
        self.guardado: UmbralAmbiental | None = None
        self.actualizado: UmbralAmbiental | None = None
        self.estado_tras_actualizar: str | None = None
        self.estados_sincronizacion_persistidos: list[UmbralAmbiental] = []

    def obtener_por_especie_y_variable(self, id_especie, id_variable_ambiental):
        return None

    def obtener_por_id(self, id_umbral_ambiental, **_):
        return self.existente

    def guardar(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        umbral.id_umbral_ambiental = 1
        self.guardado = umbral
        return umbral

    def actualizar(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        self.actualizado = umbral
        self.estado_tras_actualizar = umbral.estado_sincronizacion
        return umbral

    def actualizar_estado_sincronizacion(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        self.estados_sincronizacion_persistidos.append(umbral)
        return umbral


class DestinoRepoFake:
    def __init__(self, seriales: list[str]) -> None:
        self.seriales = seriales
        self.especies_consultadas: list[int] = []

    def listar_seriales_gateway_por_especie(self, id_especie: int) -> list[str]:
        self.especies_consultadas.append(id_especie)
        return list(self.seriales)


class EdgePortFake:
    def __init__(self, **resultado_por_serial: ResultadoEnvioMqtt) -> None:
        self.resultado_por_serial = resultado_por_serial
        self.llamadas: list[tuple[list[str], dict]] = []

    def propagar_umbral(self, seriales_gateway, payload):
        self.llamadas.append((list(seriales_gateway), payload))
        return {s: self.resultado_por_serial[s] for s in seriales_gateway}


class AuditoriaRepoFake:
    def registrar(self, **kwargs) -> None:
        pass


class EspecieRepoFake:
    def obtener_por_id(self, _id, **_):
        return SimpleNamespace(es_activo=True)


class VariableRepoFake:
    def obtener_por_id(self, id_variable_ambiental, **_):
        return VariableAmbiental(
            id_variable_ambiental=id_variable_ambiental,
            nombre='Temperatura',
            unidad='°C',
            valor_fisico_min=Decimal('-10'),
            valor_fisico_max=Decimal('50'),
            es_activo=True,
        )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


def _niveles_dto() -> list[NivelDTO]:
    return [
        NivelDTO(nivel='normal', limite_inferior=Decimal('20'), limite_superior=Decimal('30')),
        NivelDTO(nivel='precaucion', limite_inferior=Decimal('30'), limite_superior=Decimal('35')),
        NivelDTO(nivel='critico', limite_inferior=Decimal('35'), limite_superior=Decimal('40')),
    ]


def _registrar_dto() -> RegistrarUmbralDTO:
    return RegistrarUmbralDTO(
        id_especie=1,
        id_variable_ambiental=1,
        valor_min=Decimal('20'),
        valor_max=Decimal('40'),
        niveles=_niveles_dto(),
    )


def _editar_dto() -> EditarUmbralDTO:
    return EditarUmbralDTO(
        valor_min=Decimal('15'),
        valor_max=Decimal('45'),
        niveles=[
            NivelDTO(nivel='normal', limite_inferior=Decimal('15'), limite_superior=Decimal('25')),
            NivelDTO(nivel='precaucion', limite_inferior=Decimal('25'), limite_superior=Decimal('35')),
            NivelDTO(nivel='critico', limite_inferior=Decimal('35'), limite_superior=Decimal('45')),
        ],
        fecha_actualizacion=None,
    )


def _umbral_existente() -> UmbralAmbiental:
    from src.configuration.domain.entities.nivel_alerta_ambiental import NivelAlertaAmbiental
    from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta

    return UmbralAmbiental(
        id_umbral_ambiental=1,
        id_especie=1,
        id_variable_ambiental=1,
        unidad_medida='°C',
        valor_min=Decimal('20'),
        valor_max=Decimal('40'),
        es_activo=True,
        niveles=[
            NivelAlertaAmbiental(nivel=NivelAlerta.normal, limite_inferior=Decimal('20'), limite_superior=Decimal('30')),
            NivelAlertaAmbiental(nivel=NivelAlerta.precaucion, limite_inferior=Decimal('30'), limite_superior=Decimal('35')),
            NivelAlertaAmbiental(nivel=NivelAlerta.critico, limite_inferior=Decimal('35'), limite_superior=Decimal('40')),
        ],
        fecha_actualizacion=None,
    )


def _registrar(edge_port, *, seriales=('EDGE-1',), umbral_repo=None, db=None):
    uc = RegistrarUmbralUseCase(
        db=db or DbFake(),
        umbral_repo=umbral_repo or UmbralRepoFake(),
        especie_repo=EspecieRepoFake(),
        variable_repo=VariableRepoFake(),
        auditoria_repo=AuditoriaRepoFake(),
        destino_repo=DestinoRepoFake(list(seriales)),
        edge_port=edge_port,
    )
    return uc.execute(_registrar_dto(), _usuario())


def _editar(edge_port, repo, *, seriales=('EDGE-1',)):
    uc = EditarUmbralUseCase(
        db=DbFake(),
        umbral_repo=repo,
        variable_repo=VariableRepoFake(),
        auditoria_repo=AuditoriaRepoFake(),
        destino_repo=DestinoRepoFake(list(seriales)),
        edge_port=edge_port,
    )
    return uc.execute(1, _editar_dto(), _usuario())


class TestRegistrarUmbralPropagacionEdge:
    def test_envia_a_cada_gateway_de_la_especie_el_payload_del_contrato(self) -> None:
        edge_port = EdgePortFake(**{'EDGE-1': APLICADA, 'EDGE-2': APLICADA})

        _registrar(edge_port, seriales=('EDGE-1', 'EDGE-2'))

        ((seriales, payload),) = edge_port.llamadas
        assert seriales == ['EDGE-1', 'EDGE-2']
        assert payload == {
            'id_umbral_ambiental': 1,
            'version': None,
            'variable': 'Temperatura',
            'unidad': '°C',
            'valor_min': '20',
            'valor_max': '40',
            'niveles': [
                {'nivel': 'normal', 'limite_inferior': '20', 'limite_superior': '30'},
                {'nivel': 'precaucion', 'limite_inferior': '30', 'limite_superior': '35'},
                {'nivel': 'critico', 'limite_inferior': '35', 'limite_superior': '40'},
            ],
        }

    def test_todos_los_gateway_confirman_aplicada_con_fecha(self) -> None:
        resultado = _registrar(EdgePortFake(**{'EDGE-1': APLICADA, 'EDGE-2': APLICADA}), seriales=('EDGE-1', 'EDGE-2'))

        assert resultado.estado_sincronizacion == 'APLICADA'
        assert resultado.fecha_ultima_sincronizacion is not None
        assert resultado.motivo_fallo_sincronizacion is None

    def test_edge_desconectado_queda_pendiente_sin_500(self) -> None:
        """TC-M09-63: el Edge apagado no es un error; conserva su configuración anterior."""
        repo = UmbralRepoFake()

        resultado = _registrar(EdgePortFake(**{'EDGE-1': PENDIENTE}), umbral_repo=repo)

        assert resultado.estado_sincronizacion == 'PENDIENTE'
        assert 'EDGE-1' in resultado.motivo_fallo_sincronizacion
        assert repo.estados_sincronizacion_persistidos[0].estado_sincronizacion == 'PENDIENTE'

    def test_especie_sin_gateway_queda_pendiente_con_motivo(self) -> None:
        edge_port = EdgePortFake()

        resultado = _registrar(edge_port, seriales=())

        assert resultado.estado_sincronizacion == 'PENDIENTE'
        assert resultado.motivo_fallo_sincronizacion == MOTIVO_SIN_GATEWAY_EDGE

    def test_un_gateway_sin_ack_produce_500_tras_persistir(self) -> None:
        """RF-17: si algún Edge no confirma, el umbral y su NO_CONF ya quedaron
        guardados (dos commits) y la respuesta es 500."""
        repo = UmbralRepoFake()
        db = DbFake()

        with pytest.raises(InfrastructureError) as exc_info:
            _registrar(
                EdgePortFake(**{'EDGE-1': APLICADA, 'EDGE-2': NO_CONF}),
                seriales=('EDGE-1', 'EDGE-2'),
                umbral_repo=repo,
                db=db,
            )

        assert exc_info.value.code == 'FALLO_SINCRONIZACION_EDGE'
        persistido = repo.estados_sincronizacion_persistidos[0]
        assert persistido.estado_sincronizacion == 'NO_CONF'
        assert 'EDGE-2: Sin ACK a tiempo.' in persistido.motivo_fallo_sincronizacion
        assert repo.guardado is not None
        assert db.commits == 2 and db.rollbacks == 0

    def test_estado_desconocido_se_trata_como_fallo(self) -> None:
        with pytest.raises(InfrastructureError):
            _registrar(EdgePortFake(**{'EDGE-1': ResultadoEnvioMqtt(estado='RARO', mensaje='?')}))


class TestEditarUmbralPropagacionEdge:
    def test_reenvia_el_umbral_editado_con_su_version(self) -> None:
        repo = UmbralRepoFake(existente=_umbral_existente())
        edge_port = EdgePortFake(**{'EDGE-1': APLICADA})

        resultado = _editar(edge_port, repo)

        ((_, payload),) = edge_port.llamadas
        assert payload['valor_min'] == '15'
        assert payload['version'] == repo.actualizado.fecha_actualizacion.isoformat()
        assert resultado.estado_sincronizacion == 'APLICADA'

    def test_la_edicion_se_guarda_pendiente_antes_de_propagar(self) -> None:
        """Si la propagación no alcanza a persistir su resultado, el umbral no
        debe quedar con el APLICADA de la versión anterior."""
        existente = _umbral_existente()
        existente.marcar_sincronizado(datetime.datetime.now(datetime.timezone.utc))
        repo = UmbralRepoFake(existente=existente)

        _editar(EdgePortFake(**{'EDGE-1': APLICADA}), repo)

        assert repo.estado_tras_actualizar == 'PENDIENTE'

    def test_editar_con_fallo_real_de_propagacion_responde_500_tras_persistir(self) -> None:
        repo = UmbralRepoFake(existente=_umbral_existente())

        with pytest.raises(InfrastructureError) as exc_info:
            _editar(EdgePortFake(**{'EDGE-1': NO_CONF}), repo)

        assert exc_info.value.code == 'FALLO_SINCRONIZACION_EDGE'
        assert repo.estados_sincronizacion_persistidos[0].estado_sincronizacion == 'NO_CONF'


class TestConsolidarResultados:
    def test_no_conf_prevalece_sobre_pendiente(self) -> None:
        resultado = consolidar_resultados({'A': PENDIENTE, 'B': NO_CONF, 'C': APLICADA})

        assert resultado.estado == 'NO_CONF'
        assert resultado.mensaje == 'B: Sin ACK a tiempo.'

    def test_pendiente_si_ninguno_fallo_y_alguno_no_esta_conectado(self) -> None:
        assert consolidar_resultados({'A': APLICADA, 'B': PENDIENTE}).estado == 'PENDIENTE'

    def test_sin_destinos_es_pendiente(self) -> None:
        assert consolidar_resultados({}).estado == 'PENDIENTE'


class _RespuestaFalsa:
    def __init__(self, cuerpo: dict, status: int = 200) -> None:
        self._cuerpo = cuerpo
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError('error', request=httpx.Request('POST', 'http://b'), response=None)

    def json(self) -> dict:
        return self._cuerpo


class TestEdgeSincronizacionMqttAdapter:
    @pytest.fixture(autouse=True)
    def _broker_configurado(self, monkeypatch):
        monkeypatch.setenv('MQTT_BROKER_URL', 'http://broker')
        monkeypatch.setenv('MQTT_BROKER_TOKEN', 'tok')

    def test_llama_al_broker_con_origen_umbral_por_cada_gateway(self, monkeypatch) -> None:
        llamadas: list[dict] = []

        def post(url, json, headers, timeout):
            llamadas.append({'url': url, 'json': json, 'auth': headers['Authorization']})
            return _RespuestaFalsa({'estado': 'APLICADA', 'mensaje': 'ok', 'serial': json['serial']})

        monkeypatch.setattr(edge_sincronizacion_mqtt_adapter.httpx, 'post', post)

        resultados = EdgeSincronizacionMqttAdapter().propagar_umbral(['EDGE-1', 'EDGE-2'], {'variable': 'Temperatura'})

        assert {s: r.estado for s, r in resultados.items()} == {'EDGE-1': 'APLICADA', 'EDGE-2': 'APLICADA'}
        assert sorted(c['json']['serial'] for c in llamadas) == ['EDGE-1', 'EDGE-2']
        assert all(c['url'] == 'http://broker/v1/commands' for c in llamadas)
        assert all(c['json']['origen'] == 'umbral' and c['json']['variable'] == 'Temperatura' for c in llamadas)
        assert all(c['auth'] == 'Bearer tok' for c in llamadas)

    def test_devuelve_el_veredicto_del_broker(self, monkeypatch) -> None:
        monkeypatch.setattr(
            edge_sincronizacion_mqtt_adapter.httpx,
            'post',
            lambda *a, **k: _RespuestaFalsa({'estado': 'PENDIENTE', 'mensaje': 'EDGE-1 no está conectado'}),
        )

        (resultado,) = EdgeSincronizacionMqttAdapter().propagar_umbral(['EDGE-1'], {}).values()

        assert resultado.estado == 'PENDIENTE'

    @pytest.mark.parametrize(
        'falla',
        [httpx.ConnectError('caído'), httpx.ReadTimeout('lento')],
        ids=['broker-caido', 'timeout'],
    )
    def test_broker_inalcanzable_es_no_conf_no_pendiente(self, monkeypatch, falla) -> None:
        """A diferencia de RF-23: se intentó y falló -> el 500 de RF-17 no debe ocultarse."""
        def post(*a, **k):
            raise falla

        monkeypatch.setattr(edge_sincronizacion_mqtt_adapter.httpx, 'post', post)

        (resultado,) = EdgeSincronizacionMqttAdapter().propagar_umbral(['EDGE-1'], {}).values()

        assert resultado.estado == 'NO_CONF'

    def test_error_http_del_broker_es_no_conf(self, monkeypatch) -> None:
        monkeypatch.setattr(
            edge_sincronizacion_mqtt_adapter.httpx, 'post', lambda *a, **k: _RespuestaFalsa({}, status=404)
        )

        (resultado,) = EdgeSincronizacionMqttAdapter().propagar_umbral(['EDGE-1'], {}).values()

        assert resultado.estado == 'NO_CONF'

    def test_sin_integracion_configurada_queda_pendiente_sin_llamar(self, monkeypatch) -> None:
        monkeypatch.setenv('MQTT_BROKER_URL', '')

        def post(*a, **k):
            raise AssertionError('no debe llamar al broker')

        monkeypatch.setattr(edge_sincronizacion_mqtt_adapter.httpx, 'post', post)

        resultados = EdgeSincronizacionMqttAdapter().propagar_umbral(['EDGE-1'], {})

        assert resultados['EDGE-1'].estado == 'PENDIENTE'

    def test_sin_gateway_no_llama(self) -> None:
        assert EdgeSincronizacionMqttAdapter().propagar_umbral([], {}) == {}


class TestEntidadUmbralAmbiental:
    def test_marcar_sincronizado_limpia_el_motivo_de_fallo(self) -> None:
        umbral = _umbral_existente()
        umbral.marcar_fallo_sincronizacion('fallo previo')

        ahora = datetime.datetime.now(datetime.timezone.utc)
        umbral.marcar_sincronizado(ahora)

        assert umbral.estado_sincronizacion == 'APLICADA'
        assert umbral.fecha_ultima_sincronizacion == ahora
        assert umbral.motivo_fallo_sincronizacion is None

    def test_marcar_fallo_sincronizacion_guarda_el_motivo(self) -> None:
        umbral = _umbral_existente()

        umbral.marcar_fallo_sincronizacion('sin ACK a tiempo')

        assert umbral.estado_sincronizacion == 'NO_CONF'
        assert umbral.motivo_fallo_sincronizacion == 'sin ACK a tiempo'

    def test_actualizar_deja_pendiente_y_conserva_la_ultima_sincronizacion(self) -> None:
        umbral = _umbral_existente()
        antes = datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc)
        umbral.marcar_sincronizado(antes)

        umbral.actualizar(
            valor_min=Decimal('10'),
            valor_max=Decimal('45'),
            niveles=umbral.niveles,
            id_usuario=1,
            ts_ahora=datetime.datetime.now(datetime.timezone.utc),
        )

        assert umbral.estado_sincronizacion == 'PENDIENTE'
        assert umbral.motivo_fallo_sincronizacion == MOTIVO_CAMBIOS_SIN_PROPAGAR
        assert umbral.fecha_ultima_sincronizacion == antes

    def test_estado_por_defecto_de_un_umbral_nuevo_es_pendiente(self) -> None:
        umbral = UmbralAmbiental.crear(
            id_especie=1,
            id_variable_ambiental=1,
            unidad_medida='°C',
            valor_min=Decimal('20'),
            valor_max=Decimal('40'),
            niveles=[],
            id_usuario=1,
        )

        assert umbral.estado_sincronizacion == 'PENDIENTE'
