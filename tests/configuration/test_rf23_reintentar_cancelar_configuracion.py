"""RF-23: reintentar o cancelar una configuración remota PENDIENTE o NO_CONF.

Lo que vale la pena fijar: solo se reintenta la configuración más reciente
(una NO_CONF vieja pisaría en el dispositivo la nueva), una ya resuelta no se
toca, y cancelar no exige el dispositivo activo porque es lo que destraba
desactivarlo.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.dispositivos_iot.configurar_remotamente_use_case import (
    EVENTO_CANCELADA,
    EVENTO_REINTENTADA,
    CancelarConfiguracionUseCase,
    ReintentarConfiguracionUseCase,
)
from src.configuration.domain.entities.configuracion_remota import ConfiguracionRemota
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError

USUARIO = UsuarioActual(id_usuario=4, id_token=1, id_rol=4)


def _dispositivo(activo: bool = True) -> DispositivoIot:
    d = DispositivoIot.crear(
        serial=SerialDispositivo("ESP-1"),
        descripcion="d",
        id_infraestructura=1,
        id_tipo_dispositivo=1,
        es_activo=activo,
    )
    d.id_dispositivo_iot = 1
    return d


def _config(id_: int, estado: str, id_dispositivo: int = 1) -> ConfiguracionRemota:
    return ConfiguracionRemota(
        id_configuracion_remota=id_,
        id_dispositivo_iot=id_dispositivo,
        frecuencia_captura=15,
        intervalo_transmision=15,
        estado=estado,
        id_usuario=4,
    )


class DbFake:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass


class DispositivoRepoFake:
    def __init__(self, dispositivo: DispositivoIot) -> None:
        self.dispositivo = dispositivo

    def obtener_por_id(self, id_, *, ids_fincas_permitidas=None):
        return self.dispositivo if id_ == self.dispositivo.id_dispositivo_iot else None


class ConfigRepoFake:
    def __init__(self, *configs: ConfiguracionRemota) -> None:
        self.por_id = {c.id_configuracion_remota: c for c in configs}
        self.actualizadas: list[str] = []

    def obtener_por_id(self, id_):
        return self.por_id.get(id_)

    def listar_por_dispositivo(self, id_dispositivo):
        return sorted(
            (c for c in self.por_id.values() if c.id_dispositivo_iot == id_dispositivo),
            key=lambda c: c.id_configuracion_remota,
            reverse=True,
        )

    def actualizar(self, config):
        self.actualizadas.append(config.estado)
        return config


class BrokerFake:
    def __init__(self, estado: str) -> None:
        self.estado = estado
        self.envios: list[tuple[str, dict]] = []

    def enviar_configuracion(self, serial, payload):
        self.envios.append((serial, payload))
        return ResultadoEnvioMqtt(estado=self.estado, mensaje=f"broker: {self.estado}")


class BitacoraFake:
    def __init__(self) -> None:
        self.eventos: list[dict] = []

    def registrar(self, **evento) -> None:
        self.eventos.append(evento)


def _reintentar(repo, broker, bitacora=None, dispositivo=None, id_config=10):
    return ReintentarConfiguracionUseCase(
        DbFake(), DispositivoRepoFake(dispositivo or _dispositivo()), repo, broker, bitacora or BitacoraFake()
    ).execute(1, id_config, USUARIO)


def _cancelar(repo, bitacora=None, dispositivo=None, id_config=10):
    return CancelarConfiguracionUseCase(
        DbFake(), DispositivoRepoFake(dispositivo or _dispositivo()), repo, bitacora or BitacoraFake()
    ).execute(1, id_config, USUARIO)


def test_reintentar_una_pendiente_que_ahora_llega_queda_aplicada_y_se_audita():
    repo, broker, bitacora = ConfigRepoFake(_config(10, "PENDIENTE")), BrokerFake("APLICADA"), BitacoraFake()

    config, mensaje = _reintentar(repo, broker, bitacora)

    assert broker.envios == [("ESP-1", {"frecuencia_captura": 15, "intervalo_transmision": 15})]
    assert config.estado == "APLICADA" and config.fecha_aplicacion is not None
    assert repo.actualizadas == ["APLICADA"]
    assert mensaje == "broker: APLICADA"
    assert bitacora.eventos[0]["evento"] == EVENTO_REINTENTADA
    assert bitacora.eventos[0]["exitoso"] is True


def test_reintentar_una_no_conf_con_el_dispositivo_offline_la_deja_pendiente():
    repo = ConfigRepoFake(_config(10, "NO_CONF"))

    config, _ = _reintentar(repo, BrokerFake("PENDIENTE"))

    assert config.estado == "PENDIENTE"
    assert repo.actualizadas == ["PENDIENTE"]


def test_reintentar_sin_cambio_de_estado_no_escribe():
    repo = ConfigRepoFake(_config(10, "PENDIENTE"))

    config, _ = _reintentar(repo, BrokerFake("PENDIENTE"))

    assert config.estado == "PENDIENTE"
    assert repo.actualizadas == []


def test_no_se_reintenta_una_configuracion_que_ya_tiene_otra_mas_reciente():
    repo, broker = ConfigRepoFake(_config(10, "NO_CONF"), _config(11, "APLICADA")), BrokerFake("APLICADA")

    with pytest.raises(ConflictError) as exc:
        _reintentar(repo, broker)

    assert exc.value.code == "CONFIGURACION_REEMPLAZADA"
    assert broker.envios == []


@pytest.mark.parametrize("estado", ["APLICADA", "CANCELADA"])
def test_una_configuracion_resuelta_no_se_reintenta_ni_se_cancela(estado):
    repo, broker = ConfigRepoFake(_config(10, estado)), BrokerFake("APLICADA")

    with pytest.raises(ConflictError) as reintento:
        _reintentar(repo, broker)
    with pytest.raises(ConflictError) as cancelacion:
        _cancelar(repo)

    assert reintento.value.code == cancelacion.value.code == "CONFIGURACION_YA_RESUELTA"
    assert broker.envios == [] and repo.actualizadas == []


def test_una_configuracion_de_otro_dispositivo_es_404():
    repo = ConfigRepoFake(_config(10, "PENDIENTE", id_dispositivo=2))

    with pytest.raises(NotFoundError) as exc:
        _cancelar(repo)

    assert exc.value.code == "CONFIGURACION_NO_ENCONTRADA"


def test_cancelar_funciona_con_el_dispositivo_inactivo_y_reintentar_no():
    inactivo = _dispositivo(activo=False)
    repo, bitacora = ConfigRepoFake(_config(10, "PENDIENTE")), BitacoraFake()

    with pytest.raises(BusinessRuleError) as exc:
        _reintentar(repo, BrokerFake("APLICADA"), dispositivo=inactivo)
    config = _cancelar(repo, bitacora, dispositivo=inactivo)

    assert exc.value.code == "DISPOSITIVO_INACTIVO"
    assert config.estado == "CANCELADA"
    assert bitacora.eventos == [
        {
            "evento": EVENTO_CANCELADA,
            "exitoso": True,
            "id_dispositivo_iot": 1,
            "serial": "ESP-1",
            "id_usuario": 4,
            "detalle": {"id_configuracion_remota": 10, "estado_anterior": "PENDIENTE"},
        }
    ]


@pytest.mark.parametrize(("estado_broker", "codigo_http"), [("APLICADA", 200), ("PENDIENTE", 202), ("NO_CONF", 504)])
def test_endpoints_reintentar_y_cancelar(monkeypatch: pytest.MonkeyPatch, estado_broker, codigo_http):
    from src.configuration.infrastructure.routers import dispositivo_iot_router as modulo
    from src.shared import rbac

    repo = ConfigRepoFake(_config(10, "NO_CONF"), _config(9, "PENDIENTE"))

    class AlcanceFake:
        def __init__(self, _db):
            pass

        def listar_ids_fincas_permitidas(self, _id_usuario, _id_rol):
            return None

    monkeypatch.setattr(rbac, "tiene_permiso", lambda *_args: True)
    monkeypatch.setattr(modulo, "AlcanceFincaAdapter", AlcanceFake)
    monkeypatch.setattr(modulo, "SqlAlchemyDispositivoIotRepository", lambda _db: DispositivoRepoFake(_dispositivo()))
    monkeypatch.setattr(modulo, "SqlAlchemyConfiguracionRemotaRepository", lambda _db: repo)
    monkeypatch.setattr(modulo, "MqttHttpAdapter", lambda: BrokerFake(estado_broker))
    monkeypatch.setattr(modulo, "BitacoraIotM03Adapter", lambda _db: BitacoraFake())

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(modulo.router)
    app.dependency_overrides[get_db] = lambda: DbFake()
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=4, id_token=1, id_rol=4, id_estado_cuenta=2
    )

    base = "/configuracion/dispositivos-iot/1/configuraciones"
    with TestClient(app, raise_server_exceptions=False) as client:
        reintento = client.post(f"{base}/10/reintentar")
        cancelada = client.patch(f"{base}/9/cancelar")

    assert reintento.status_code == codigo_http
    assert cancelada.status_code == 200
    assert cancelada.json()["estado"] == "CANCELADA"
