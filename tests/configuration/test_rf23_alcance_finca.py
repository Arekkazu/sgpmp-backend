"""RF-23 / TC-M09-G71: alcance por finca en configuración remota."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.dispositivos_iot.configurar_remotamente_use_case import (
    ConfigurarRemotamenteUseCase,
    ConsultarConfiguracionesUseCase,
)
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dependencies import get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import NotFoundError


USUARIO_INGENIERO = UsuarioActual(id_usuario=4, id_token=1, id_rol=4)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass


class DispositivoFueraDeAlcanceRepoFake:
    def __init__(self) -> None:
        self.alcance_recibido = None

    def obtener_por_id(self, _id, *, ids_fincas_permitidas=None):
        self.alcance_recibido = ids_fincas_permitidas
        return None


class ConfigRepoSpy:
    def __init__(self) -> None:
        self.guardados = 0
        self.consultas = 0

    def obtener_pendiente(self, _id):
        raise AssertionError("No debe consultar pendientes fuera del alcance")

    def guardar(self, _config):
        self.guardados += 1
        raise AssertionError("No debe persistir una configuración fuera del alcance")

    def actualizar(self, _config):
        raise AssertionError("No debe actualizar una configuración fuera del alcance")

    def listar_por_dispositivo(self, _id):
        self.consultas += 1
        raise AssertionError("No debe exponer el historial fuera del alcance")


class TipoRepoSpy:
    def obtener_por_id(self, _id):
        raise AssertionError("No debe consultar el tipo fuera del alcance")


class MqttSpy:
    def enviar_configuracion(self, _serial, _payload):
        raise AssertionError("No debe emitir MQTT fuera del alcance")


def test_configurar_dispositivo_fuera_de_alcance_responde_404_sin_efectos():
    db = DbFake()
    dispositivo_repo = DispositivoFueraDeAlcanceRepoFake()
    config_repo = ConfigRepoSpy()
    use_case = ConfigurarRemotamenteUseCase(
        db=db,
        dispositivo_repo=dispositivo_repo,
        config_repo=config_repo,
        tipo_repo=TipoRepoSpy(),
        mqtt_port=MqttSpy(),
    )

    with pytest.raises(NotFoundError) as exc:
        use_case.execute(
            17,
            ConfigurarRemotamenteDTO(
                frecuencia_captura=10,
                intervalo_transmision=15,
            ),
            USUARIO_INGENIERO,
            ids_fincas_permitidas=[],
        )

    assert exc.value.status_code == 404
    assert exc.value.code == "DISPOSITIVO_NO_ENCONTRADO"
    assert dispositivo_repo.alcance_recibido == []
    assert config_repo.guardados == 0
    assert db.commits == 0


def test_historial_fuera_de_alcance_responde_404_sin_consultar_configuraciones():
    dispositivo_repo = DispositivoFueraDeAlcanceRepoFake()
    config_repo = ConfigRepoSpy()
    use_case = ConsultarConfiguracionesUseCase(
        db=DbFake(),
        config_repo=config_repo,
        dispositivo_repo=dispositivo_repo,
    )

    with pytest.raises(NotFoundError) as exc:
        use_case.listar_por_dispositivo(17, ids_fincas_permitidas=[])

    assert exc.value.status_code == 404
    assert exc.value.code == "DISPOSITIVO_NO_ENCONTRADO"
    assert dispositivo_repo.alcance_recibido == []
    assert config_repo.consultas == 0


def test_endpoints_propagan_alcance_y_responden_404(
    monkeypatch: pytest.MonkeyPatch,
):
    from src.configuration.infrastructure.routers import dispositivo_iot_router as modulo
    from src.shared import rbac

    db = DbFake()
    dispositivo_repo = DispositivoFueraDeAlcanceRepoFake()
    config_repo = ConfigRepoSpy()

    class AlcanceSinFincasFake:
        def __init__(self, _db):
            pass

        def listar_ids_fincas_permitidas(self, id_usuario, id_rol):
            assert (id_usuario, id_rol) == (4, 4)
            return []

    monkeypatch.setattr(rbac, "tiene_permiso", lambda *_args: True)
    monkeypatch.setattr(modulo, "AlcanceFincaAdapter", AlcanceSinFincasFake)
    monkeypatch.setattr(
        modulo,
        "SqlAlchemyDispositivoIotRepository",
        lambda _db: dispositivo_repo,
    )
    monkeypatch.setattr(
        modulo,
        "SqlAlchemyConfiguracionRemotaRepository",
        lambda _db: config_repo,
    )
    monkeypatch.setattr(modulo, "SqlAlchemyTipoDispositivoIotRepository", lambda _db: TipoRepoSpy())
    monkeypatch.setattr(modulo, "MqttHttpAdapter", MqttSpy)

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(modulo.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=4,
        id_token=1,
        id_rol=4,
        id_estado_cuenta=2,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        post_response = client.post(
            "/configuracion/dispositivos-iot/17/configurar",
            json={"frecuencia_captura": 10, "intervalo_transmision": 15},
        )
        history_response = client.get(
            "/configuracion/dispositivos-iot/17/configuraciones"
        )

    assert post_response.status_code == 404
    assert post_response.json()["error_code"] == "DISPOSITIVO_NO_ENCONTRADO"
    assert history_response.status_code == 404
    assert history_response.json()["error_code"] == "DISPOSITIVO_NO_ENCONTRADO"
    assert dispositivo_repo.alcance_recibido == []
    assert config_repo.guardados == 0
    assert config_repo.consultas == 0
