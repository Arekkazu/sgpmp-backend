"""RF-23 / TC-M09-250/251: credencial MQTT del Gateway Edge.

El backend no habla MQTT: valida (alcance por finca, dispositivo activo, que no
dependa de un Edge), llama al broker por HTTPS y audita. Con dobles para el
repositorio, el broker y la bitácora.
"""
from __future__ import annotations

from typing import Optional

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.dispositivos_iot.credencial_mqtt_use_case import (
    ConsultarCredencialMqttUseCase,
    EmitirCredencialMqttUseCase,
    RevocarCredencialMqttUseCase,
)
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.mqtt_port import CredencialMqtt, EstadoCredencialMqtt
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.adapters import mqtt_http_adapter
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError, NotFoundError, ServiceUnavailableError

USUARIO = UsuarioActual(id_usuario=4, id_token=1, id_rol=4)


def _dispositivo(
    id_: int, serial: str, activo: bool = True, gateway: Optional[int] = None
) -> DispositivoIot:
    d = DispositivoIot.crear(
        serial=SerialDispositivo(serial),
        descripcion="d",
        id_infraestructura=1,
        id_tipo_dispositivo=1,
        es_activo=activo,
        id_dispositivo_gateway=gateway,
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


class BrokerFake:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.emitidas: list[str] = []
        self.revocadas: list[str] = []

    def emitir_credencial(self, serial):
        if self.error:
            raise self.error
        self.emitidas.append(serial)
        return CredencialMqtt(usuario=serial, password="clave-secreta-xyz", seriales=[serial, "ESP-2"])

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


def _emitir(repo, broker, bitacora, alcance=None):
    return EmitirCredencialMqttUseCase(DbFake(), repo, broker, bitacora).execute(
        1, USUARIO, ids_fincas_permitidas=alcance
    )


def test_emitir_pide_al_broker_la_credencial_del_edge():
    repo, broker, bitacora = RepoFake(_dispositivo(1, "EDGE-1")), BrokerFake(), BitacoraFake()

    credencial = _emitir(repo, broker, bitacora, alcance=[7])

    # los seriales que atiende los saca el broker de modulo9, no los manda el backend
    assert broker.emitidas == ["EDGE-1"]
    assert credencial.seriales == ["EDGE-1", "ESP-2"]
    assert repo.alcances == [[7]]
    (evento,) = bitacora.eventos
    assert evento["evento"] == "CREDENCIAL_MQTT_EMITIDA" and evento["exitoso"] is True
    assert evento["detalle"] == {"seriales": ["EDGE-1", "ESP-2"]}
    assert "clave-secreta-xyz" not in repr(bitacora.eventos)  # nunca a la auditoría


@pytest.mark.parametrize(
    ("dispositivos", "error", "codigo"),
    [
        ((), NotFoundError, "DISPOSITIVO_NO_ENCONTRADO"),  # o fuera del alcance por finca
        ((_dispositivo(1, "EDGE-1", activo=False),), BusinessRuleError, "DISPOSITIVO_INACTIVO"),
        # se comunica por su Edge: la credencial es la del Edge
        ((_dispositivo(1, "ESP-2", gateway=40),), BusinessRuleError, "DISPOSITIVO_DEPENDE_DE_GATEWAY_EDGE"),
    ],
)
def test_emitir_solo_para_quien_se_conecta_al_broker(dispositivos, error, codigo):
    broker = BrokerFake()
    with pytest.raises(error) as exc:
        _emitir(RepoFake(*dispositivos), broker, BitacoraFake())
    assert exc.value.code == codigo
    assert broker.emitidas == []


def test_si_el_broker_falla_se_audita_y_se_propaga():
    caida = ServiceUnavailableError(code="BROKER_MQTT_NO_DISPONIBLE", message="caído")
    bitacora = BitacoraFake()
    with pytest.raises(ServiceUnavailableError):
        _emitir(RepoFake(_dispositivo(1, "EDGE-1")), BrokerFake(error=caida), bitacora)
    (evento,) = bitacora.eventos
    assert evento["exitoso"] is False and evento["detalle"]["error"] == "BROKER_MQTT_NO_DISPONIBLE"


def test_revocar_se_permite_sobre_un_dispositivo_inactivo():
    broker, bitacora = BrokerFake(), BitacoraFake()
    repo = RepoFake(_dispositivo(1, "EDGE-1", activo=False))

    RevocarCredencialMqttUseCase(DbFake(), repo, broker, bitacora).execute(1, USUARIO)

    assert broker.revocadas == ["EDGE-1"]
    assert bitacora.eventos[0]["evento"] == "CREDENCIAL_MQTT_REVOCADA"


def test_consultar_sin_credencial_propia_devuelve_none():
    use_case = ConsultarCredencialMqttUseCase(DbFake(), RepoFake(_dispositivo(1, "SIN-CRED")), BrokerFake())
    assert use_case.execute(1) is None


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
    respuestas.append(httpx.Response(201, json={"usuario": "EDGE-1", "password": "p", "seriales": ["EDGE-1"]}))

    assert adapter.emitir_credencial("EDGE-1") == CredencialMqtt("EDGE-1", "p", ["EDGE-1"])
    ((metodo, url, cuerpo, headers),) = llamadas
    assert (metodo, url, cuerpo) == ("POST", "https://broker.test/v1/devices/EDGE-1/credential", None)
    assert headers == {"Authorization": "Bearer tok"}


@pytest.mark.parametrize("codigo", [204, 404])  # 404: el Edge todavía no tiene credencial
def test_adaptador_sincroniza_sin_rotar(adaptador, codigo):
    adapter, llamadas, respuestas = adaptador
    respuestas.append(httpx.Response(codigo, json={"detail": "x"}) if codigo == 404 else httpx.Response(204))

    adapter.sincronizar_credencial("EDGE-1")

    ((metodo, url, _cuerpo, _headers),) = llamadas
    assert (metodo, url) == ("POST", "https://broker.test/v1/devices/EDGE-1/credential/sync")


def test_adaptador_consultar_sin_credencial_es_none(adaptador):
    adapter, _llamadas, respuestas = adaptador
    respuestas.append(httpx.Response(404, json={"detail": "sin credencial"}))
    assert adapter.consultar_credencial("EDGE-1") is None


@pytest.mark.parametrize(
    "respuesta",
    [httpx.ConnectError("caído"), httpx.Response(503, json={"detail": "x"}), httpx.Response(401, json={"detail": "x"})],
)
def test_adaptador_sin_broker_lanza_503_en_vez_de_degradar(adaptador, respuesta):
    adapter, _llamadas, respuestas = adaptador
    respuestas.append(respuesta)
    with pytest.raises(ServiceUnavailableError):
        adapter.revocar_credencial("EDGE-1")


def test_adaptador_sin_configurar_lanza_503(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER_URL", "")
    with pytest.raises(ServiceUnavailableError):
        mqtt_http_adapter.MqttHttpAdapter().emitir_credencial("EDGE-1")


# ── Router ──────────────────────────────────────────────────────────────────

def test_endpoint_emitir_responde_201_sin_cache(monkeypatch: pytest.MonkeyPatch):
    from src.configuration.infrastructure.routers import dispositivo_iot_router as modulo
    from src.shared import rbac

    repo, broker = RepoFake(_dispositivo(1, "EDGE-1")), BrokerFake()

    class AlcanceFake:
        def __init__(self, _db):
            pass

        def listar_ids_fincas_permitidas(self, _id_usuario, _id_rol):
            return None

    monkeypatch.setattr(rbac, "tiene_permiso", lambda *_args: True)
    monkeypatch.setattr(modulo, "AlcanceFincaAdapter", AlcanceFake)
    monkeypatch.setattr(modulo, "SqlAlchemyDispositivoIotRepository", lambda _db: repo)
    monkeypatch.setattr(modulo, "MqttHttpAdapter", lambda: broker)
    monkeypatch.setattr(modulo, "BitacoraIotM03Adapter", lambda _db: BitacoraFake())

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(modulo.router)
    app.dependency_overrides[get_db] = lambda: DbFake()
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=4, id_token=1, id_rol=4, id_estado_cuenta=2
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        emitida = client.post("/configuracion/dispositivos-iot/1/credencial-mqtt")
        estado = client.get("/configuracion/dispositivos-iot/1/credencial-mqtt")
        revocada = client.delete("/configuracion/dispositivos-iot/1/credencial-mqtt")

    assert emitida.status_code == 201
    assert emitida.json() == {
        "usuario": "EDGE-1",
        "password": "clave-secreta-xyz",
        "seriales": ["EDGE-1", "ESP-2"],
    }
    assert emitida.headers["cache-control"] == "no-store"
    assert estado.status_code == 200 and estado.json()["emitida"] is True
    assert revocada.status_code == 204
    assert broker.revocadas == ["EDGE-1"]
