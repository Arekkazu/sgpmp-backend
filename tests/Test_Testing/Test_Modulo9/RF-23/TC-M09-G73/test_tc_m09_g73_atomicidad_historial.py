"""
TC-M09-G73 (RF-23, G73-02) - Atomicidad ante fallo del historial.

Ficha: "Requiere inyeccion de fallo en el historial y un cliente MQTT para
confirmar que no se publica ningun mensaje." Esperado: 500 con rollback y
ningun mensaje en el broker.

Por que local (mocks, no broker/DB real): el unico fallo "del historial"
que este endpoint puede sufrir es que `config_repo.guardar()` (el INSERT de
`ConfiguracionRemota`, que ES el registro de historial) lance una excepcion
de BD -- no hay forma de inyectar eso de forma controlada contra el backend
real en TEST sin herramientas de las que no disponemos (acceso a logs/DB).
Mismo patron que `tests/configuration/test_rf23_alcance_finca.py` (TC-M09-G71):
spies/fakes en vez de SqlAlchemy real, monkeypatch de RBAC y del adaptador
MQTT. El "cliente MQTT" de la ficha se verifica como un spy que levanta
AssertionError si llega a invocarse `enviar_configuracion` -- si el fallo de
BD SI publicara algo, este test lo detectaria.

Fuente de la garantia de atomicidad (leida en el codigo, no supuesta):
`configurar_remotamente_use_case.py::ConfigurarRemotamenteUseCase.execute()`
-- el `try: self.config_repo.guardar(config); self.db.commit() / except:
self.db.rollback(); raise` ocurre ANTES de la linea
`self.mqtt_port.enviar_configuracion(...)` (comentario en el propio codigo:
"POST-commit: intento de envio MQTT"). Si `guardar()` lanza, la funcion
nunca llega a esa linea.

Como correrlo:
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"  # stub fcntl en Windows
    python -m pytest tests/Test_Testing/Test_Modulo9/RF-23/TC-M09-G73/test_tc_m09_g73_atomicidad_historial.py -v \
        --html=resultados/resultado_TC-M09-G73_reintento1.html --self-contained-html
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.dispositivos_iot.configurar_remotamente_use_case import (
    ConfigurarRemotamenteUseCase,
)
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers

USUARIO_ADMIN = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)


class _FalloHistorial(Exception):
    """Simula una excepcion de BD real (IntegrityError/DataError/etc.) al
    guardar el registro de historial de configuracion."""


class DbSpy:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class DispositivoRepoFake:
    """Dispositivo SENSOR activo valido -- llega sin problemas hasta el paso
    de guardar el historial."""

    def obtener_por_id(self, _id, *, ids_fincas_permitidas=None):
        dispositivo = type(
            "DispositivoFake",
            (),
            {
                "es_activo": True,
                "id_tipo_dispositivo": 3,
                "serial": type("SerialFake", (), {"valor": "QA-G73-ATOMICIDAD"})(),
            },
        )()
        return dispositivo


class TipoRepoFake:
    def obtener_por_id(self, _id):
        tipo = type("TipoFake", (), {"verificar_rango": staticmethod(lambda f, i: None)})()
        return tipo


class ConfigRepoFalloHistorial:
    """El 'fallo en el historial' pedido por la ficha: guardar() explota."""

    def __init__(self) -> None:
        self.intentos_guardar = 0
        self.actualizaciones = 0

    def obtener_pendiente(self, _id):
        return None

    def guardar(self, _config):
        self.intentos_guardar += 1
        raise _FalloHistorial("Fallo simulado de BD al registrar el historial de configuracion")

    def actualizar(self, _config):
        self.actualizaciones += 1
        raise AssertionError("No debe llegar a actualizar: guardar() ya debio fallar antes")


class MqttSpyNuncaDebeLlamarse:
    """El 'cliente MQTT' de la ficha: si el use case publica algo tras un
    fallo de historial, este spy lo delata."""

    def __init__(self) -> None:
        self.llamadas = []

    def enviar_configuracion(self, serial, payload):
        self.llamadas.append((serial, payload))
        raise AssertionError(
            f"Violacion de atomicidad: se intento publicar en el broker "
            f"(serial={serial!r}, payload={payload!r}) a pesar de que el "
            f"historial fallo y debio hacerse rollback."
        )


class TestTCM09G73AtomicidadHistorial:
    """TC-M09-G73 / G73-02: fallo del historial -> 500 + rollback + 0 publicaciones MQTT."""

    def test_use_case_directo_rollback_y_sin_publicar(self):
        db = DbSpy()
        config_repo = ConfigRepoFalloHistorial()
        mqtt_spy = MqttSpyNuncaDebeLlamarse()
        use_case = ConfigurarRemotamenteUseCase(
            db=db,
            dispositivo_repo=DispositivoRepoFake(),
            config_repo=config_repo,
            tipo_repo=TipoRepoFake(),
            mqtt_port=mqtt_spy,
        )
        dto = ConfigurarRemotamenteDTO(frecuencia_captura=10, intervalo_transmision=15)

        with pytest.raises(_FalloHistorial):
            use_case.execute(42, dto, USUARIO_ADMIN, ids_fincas_permitidas=None)

        assert config_repo.intentos_guardar == 1, "guardar() debio intentarse exactamente una vez"
        assert config_repo.actualizaciones == 0, "no debio llegar al paso de actualizar"
        assert db.rollbacks == 1, "RF-23 exige rollback ante fallo del historial"
        assert db.commits == 0, "no debio quedar ningun commit parcial"
        assert mqtt_spy.llamadas == [], (
            "Atomicidad violada: el adaptador MQTT fue invocado pese al fallo del historial "
            f"(llamadas={mqtt_spy.llamadas!r})"
        )

    def test_endpoint_responde_500_sin_publicar(self, monkeypatch: pytest.MonkeyPatch):
        from src.configuration.infrastructure.routers import dispositivo_iot_router as modulo
        from src.shared import rbac

        db = DbSpy()
        config_repo = ConfigRepoFalloHistorial()
        mqtt_spy = MqttSpyNuncaDebeLlamarse()

        monkeypatch.setattr(rbac, "tiene_permiso", lambda *_args: True)
        monkeypatch.setattr(modulo, "SqlAlchemyDispositivoIotRepository", lambda _db: DispositivoRepoFake())
        monkeypatch.setattr(modulo, "SqlAlchemyConfiguracionRemotaRepository", lambda _db: config_repo)
        monkeypatch.setattr(modulo, "SqlAlchemyTipoDispositivoIotRepository", lambda _db: TipoRepoFake())
        monkeypatch.setattr(modulo, "MqttHttpAdapter", lambda: mqtt_spy)
        monkeypatch.setattr(
            modulo,
            "AlcanceFincaAdapter",
            lambda _db: type(
                "AlcanceFake", (), {"listar_ids_fincas_permitidas": staticmethod(lambda *_a: None)}
            )(),
        )

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(modulo.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: USUARIO_ADMIN

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/configuracion/dispositivos-iot/42/configurar",
                json={"frecuencia_captura": 10, "intervalo_transmision": 15},
            )

        assert response.status_code == 500, (
            f"RF-23/G73 exige 500 ante fallo del historial; respondio "
            f"{response.status_code}. Cuerpo: {response.text}"
        )
        assert response.json().get("error_code") == "ERROR_INTERNO"
        assert db.rollbacks == 1
        assert db.commits == 0
        assert mqtt_spy.llamadas == [], (
            "Atomicidad violada a nivel endpoint: se publico en el broker pese al 500"
        )
