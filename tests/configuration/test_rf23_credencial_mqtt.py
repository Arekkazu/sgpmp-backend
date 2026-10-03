"""RF-23 / TC-M09-250/251: credencial MQTT por Raspberry.

El backend no habla MQTT: valida (alcance por finca, dispositivo activo), llama
al broker por HTTPS y audita. Con dobles para el repositorio, el broker y la
bitácora.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.dispositivos_iot.credencial_mqtt_use_case import (
    ConsultarCredencialMqttUseCase,
    EmitirCredencialMqttUseCase,
    RevocarCredencialMqttUseCase,
)
from src.configuration.application.use_cases.dispositivos_iot.desactivar_dispositivo_iot_use_case import (
    DesactivarDispositivoIotUseCase,
)
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.mqtt_port import CredencialMqtt, EstadoCredencialMqtt
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.adapters import mqtt_http_adapter
from src.configuration.infrastructure.dto.emitir_credencial_mqtt_dto import EmitirCredencialMqttDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError, NotFoundError, ServiceUnavailableError

USUARIO = UsuarioActual(id_usuario=4, id_token=1, id_rol=4)


def _dispositivo(id_: int, serial: str, activo: bool = True) -> DispositivoIot:
    d = DispositivoIot.crear(
        serial=SerialDispositivo(serial),
        descripcion="d",
        id_infraestructura=1,
        id_tipo_dispositivo=1,
        es_activo=activo,
    )
    d.id_dispositivo_iot = id_
    return d


class DbFake:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass


class RepoFake:
    def __init__(self, *dispositivos: DispositivoIot) -> None:
        self.por_id = {d.id_dispositivo_iot: d for d in dispositivos}
        self.alcances: list = []

    def obtener_por_id(self, id_, *, ids_fincas_permitidas=None):
        self.alcances.append(ids_fincas_permitidas)
        return self.por_id.get(id_)

    def actualizar(self, d):
        return d


class BrokerFake:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.emitidas: list[tuple] = []
        self.revocadas: list[str] = []

    def emitir_credencial(self, serial, adicionales):
        if self.error:
            raise self.error
        self.emitidas.append((serial, adicionales))
        return CredencialMqtt(usuario=serial, password="clave-secreta-xyz", seriales=[serial, *adicionales])

    def consultar_credencial(self, serial):
        return None if serial == "SIN-CRED" else EstadoCredencialMqtt(serial, True, False, [serial])

    def revocar_credencial(self, serial):
        if self.error:
            raise self.error
        self.revocadas.append(serial)


class BitacoraFake:
    def __init__(self) -> None:
        self.eventos: list[dict] = []

    def registrar(self, **evento) -> None:
        self.eventos.append(evento)


def _emitir(repo, broker, bitacora, ids_adicionales=(), alcance=None):
    use_case = EmitirCredencialMqttUseCase(DbFake(), repo, broker, bitacora)
    dto = EmitirCredencialMqttDTO(ids_dispositivos_adicionales=list(ids_adicionales))
    return use_case.execute(1, dto, USUARIO, ids_fincas_permitidas=alcance)


def test_emitir_pide_al_broker_la_credencial_de_la_raspberry_y_sus_seriales():
    repo = RepoFake(_dispositivo(1, "RPI-1"), _dispositivo(2, "ESP-2"))
    broker, bitacora = BrokerFake(), BitacoraFake()

    credencial = _emitir(repo, broker, bitacora, ids_adicionales=[2, 1, 2], alcance=[7])

    assert broker.emitidas == [("RPI-1", ["ESP-2"])]  # principal fuera, sin repetidos
    assert credencial.password == "clave-secreta-xyz"
    assert repo.alcances == [[7], [7]]  # el alcance por finca aplica a todos
    (evento,) = bitacora.eventos
    assert evento["evento"] == "CREDENCIAL_MQTT_EMITIDA" and evento["exitoso"] is True
    assert evento["id_usuario"] == 4
    # la contraseña nunca va a la auditoría
    assert "clave-secreta-xyz" not in repr(bitacora.eventos)


@pytest.mark.parametrize(
    ("dispositivos", "adicionales", "error"),
    [
        ((), (), NotFoundError),  # no existe o fuera del alcance por finca
        ((_dispositivo(1, "RPI-1", activo=False),), (), BusinessRuleError),
        ((_dispositivo(1, "RPI-1"), _dispositivo(2, "ESP-2", activo=False)), (2,), BusinessRuleError),
        ((_dispositivo(1, "RPI-1"),), (99,), NotFoundError),
    ],
)
def test_emitir_solo_para_dispositivos_activos_y_en_alcance(dispositivos, adicionales, error):
    broker = BrokerFake()
    with pytest.raises(error):
        _emitir(RepoFake(*dispositivos), broker, BitacoraFake(), ids_adicionales=adicionales)
    assert broker.emitidas == []


def test_si_el_broker_falla_se_audita_y_se_propaga():
    caida = ServiceUnavailableError(code="BROKER_MQTT_NO_DISPONIBLE", message="caído")
    bitacora = BitacoraFake()
    with pytest.raises(ServiceUnavailableError):
        _emitir(RepoFake(_dispositivo(1, "RPI-1")), BrokerFake(error=caida), bitacora)
    (evento,) = bitacora.eventos
    assert evento["exitoso"] is False and evento["detalle"]["error"] == "BROKER_MQTT_NO_DISPONIBLE"


def test_revocar_se_permite_sobre_un_dispositivo_inactivo():
    broker, bitacora = BrokerFake(), BitacoraFake()
    use_case = RevocarCredencialMqttUseCase(DbFake(), RepoFake(_dispositivo(1, "RPI-1", activo=False)), broker, bitacora)

    use_case.execute(1, USUARIO)

    assert broker.revocadas == ["RPI-1"]
    assert bitacora.eventos[0]["evento"] == "CREDENCIAL_MQTT_REVOCADA"


def test_consultar_sin_credencial_propia_devuelve_none():
    use_case = ConsultarCredencialMqttUseCase(DbFake(), RepoFake(_dispositivo(1, "SIN-CRED")), BrokerFake())
    assert use_case.execute(1) is None


class ConfigRepoSinPendientes:
    def obtener_pendiente(self, _id):
        return None


class AuditoriaDispositivoFake:
    def registrar(self, **_kwargs):
        pass


def _desactivar(broker):
    db, bitacora = DbFake(), BitacoraFake()
    use_case = DesactivarDispositivoIotUseCase(
        db=db,
        dispositivo_repo=RepoFake(_dispositivo(1, "RPI-1")),
        config_repo=ConfigRepoSinPendientes(),
        auditoria_repo=AuditoriaDispositivoFake(),
        mqtt_port=broker,
        bitacora_credencial=bitacora,
    )
    return use_case.execute(1, USUARIO), db, bitacora


def test_desactivar_un_dispositivo_revoca_su_credencial_mqtt():
    broker = BrokerFake()
    dispositivo, db, bitacora = _desactivar(broker)

    assert not dispositivo.es_activo and db.commits == 1
    assert broker.revocadas == ["RPI-1"]
    assert bitacora.eventos[0]["detalle"]["motivo"] == "dispositivo_desactivado"


def test_si_el_broker_no_responde_la_desactivacion_igual_se_mantiene():
    caida = ServiceUnavailableError(code="BROKER_MQTT_NO_DISPONIBLE", message="caído")
    dispositivo, db, bitacora = _desactivar(BrokerFake(error=caida))

    assert not dispositivo.es_activo and db.commits == 1
    assert bitacora.eventos[0]["exitoso"] is False  # queda rastro para revocar a mano


# ── Adaptador HTTP hacia el broker ──────────────────────────────────────────

@pytest.fixture
def adaptador(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MQTT_BROKER_URL", "https://broker.test")
    monkeypatch.setenv("MQTT_BROKER_TOKEN", "tok")
    llamadas: list[tuple] = []
    respuestas: list = []

    def request(metodo, url, **kwargs):
        llamadas.append((metodo, url, kwargs.get("json"), kwargs["headers"]))
        r = respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(mqtt_http_adapter.httpx, "request", request)
    return mqtt_http_adapter.MqttHttpAdapter(), llamadas, respuestas


def test_adaptador_emite_por_https_con_el_token_de_servicio(adaptador):
    adapter, llamadas, respuestas = adaptador
    respuestas.append(httpx.Response(201, json={"usuario": "RPI-1", "password": "p", "seriales": ["RPI-1", "ESP-2"]}))

    credencial = adapter.emitir_credencial("RPI-1", ["ESP-2"])

    assert credencial == CredencialMqtt("RPI-1", "p", ["RPI-1", "ESP-2"])
    ((metodo, url, cuerpo, headers),) = llamadas
    assert (metodo, url) == ("POST", "https://broker.test/v1/devices/RPI-1/credential")
    assert cuerpo == {"seriales_adicionales": ["ESP-2"]}
    assert headers == {"Authorization": "Bearer tok"}


def test_adaptador_consultar_sin_credencial_es_none(adaptador):
    adapter, _llamadas, respuestas = adaptador
    respuestas.append(httpx.Response(404, json={"detail": "sin credencial"}))
    assert adapter.consultar_credencial("RPI-1") is None


@pytest.mark.parametrize(
    "respuesta",
    [httpx.ConnectError("caído"), httpx.Response(503, json={"detail": "x"}), httpx.Response(401, json={"detail": "x"})],
)
def test_adaptador_sin_broker_lanza_503_en_vez_de_degradar(adaptador, respuesta):
    adapter, _llamadas, respuestas = adaptador
    respuestas.append(respuesta)
    with pytest.raises(ServiceUnavailableError):
        adapter.revocar_credencial("RPI-1")


def test_adaptador_sin_configurar_lanza_503(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER_URL", "")
    with pytest.raises(ServiceUnavailableError):
        mqtt_http_adapter.MqttHttpAdapter().emitir_credencial("RPI-1", [])


# ── Router ──────────────────────────────────────────────────────────────────

def test_endpoint_emitir_responde_201_sin_cache(monkeypatch: pytest.MonkeyPatch):
    from src.configuration.infrastructure.routers import dispositivo_iot_router as modulo
    from src.shared import rbac

    repo, broker = RepoFake(_dispositivo(1, "RPI-1")), BrokerFake()

    class AlcanceFake:
        def __init__(self, _db):
            pass

        def listar_ids_fincas_permitidas(self, _id_usuario, _id_rol):
            return None

    monkeypatch.setattr(rbac, "tiene_permiso", lambda *_args: True)
    monkeypatch.setattr(modulo, "AlcanceFincaAdapter", AlcanceFake)
    monkeypatch.setattr(modulo, "SqlAlchemyDispositivoIotRepository", lambda _db: repo)
    monkeypatch.setattr(modulo, "MqttHttpAdapter", lambda: broker)
    monkeypatch.setattr(modulo, "BitacoraCredencialMqttM03Adapter", lambda _db: BitacoraFake())

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(modulo.router)
    app.dependency_overrides[get_db] = lambda: DbFake()
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=4, id_token=1, id_rol=4, id_estado_cuenta=2
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        emitida = client.post("/configuracion/dispositivos-iot/1/credencial-mqtt", json={})
        estado = client.get("/configuracion/dispositivos-iot/1/credencial-mqtt")
        revocada = client.delete("/configuracion/dispositivos-iot/1/credencial-mqtt")

    assert emitida.status_code == 201
    assert emitida.json() == {"usuario": "RPI-1", "password": "clave-secreta-xyz", "seriales": ["RPI-1"]}
    assert emitida.headers["cache-control"] == "no-store"
    assert estado.status_code == 200 and estado.json()["emitida"] is True
    assert revocada.status_code == 204
    assert broker.revocadas == ["RPI-1"]
