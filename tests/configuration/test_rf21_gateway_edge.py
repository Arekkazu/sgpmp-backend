"""RF-21 / RF-23: Gateway Edge de los dispositivos IoT (relación N:1).

El Gateway Edge (la computadora de borde del sitio) es un dispositivo de tipo
GATEWAY_EDGE; los dispositivos que atiende apuntan a él con
id_dispositivo_gateway. Desactivarlo desactiva en cascada a sus dispositivos.
Cada cambio se le avisa al broker para recalcular los permisos MQTT del Edge.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.dispositivos_iot.configurar_remotamente_use_case import (
    ConfigurarRemotamenteUseCase,
)
from src.configuration.application.use_cases.dispositivos_iot.desactivar_dispositivo_iot_use_case import (
    DesactivarDispositivoIotUseCase,
)
from src.configuration.application.use_cases.dispositivos_iot.gateway_edge_use_case import (
    AsignarGatewayEdgeUseCase,
)
from src.configuration.application.use_cases.dispositivos_iot.registrar_dispositivo_iot_use_case import (
    RegistrarDispositivoIotUseCase,
)
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.entities.tipo_dispositivo_iot import TipoDispositivoIot
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.dto.asignar_gateway_edge_dto import AsignarGatewayEdgeDTO
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.configuration.infrastructure.dto.registrar_dispositivo_iot_dto import RegistrarDispositivoIotDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError, NotFoundError, ServiceUnavailableError

USUARIO = UsuarioActual(id_usuario=4, id_token=1, id_rol=4)
GENERICO, EDGE = 1, 9
TIPOS = {
    GENERICO: TipoDispositivoIot(GENERICO, "GENERICO", 1, 60, 1, 120),
    EDGE: TipoDispositivoIot(EDGE, "GATEWAY_EDGE", 1, 1440, 1, 1440),
}
# área -> finca: las áreas 1 y 2 son de la finca 10, el área 3 de la finca 20
AREAS = {
    1: SimpleNamespace(id_finca=10, es_activo=True),
    2: SimpleNamespace(id_finca=10, es_activo=True),
    3: SimpleNamespace(id_finca=20, es_activo=True),
}


def _d(id_: int, serial: str, *, tipo=GENERICO, area=1, activo=True, gateway: Optional[int] = None):
    d = DispositivoIot.crear(
        serial=SerialDispositivo(serial),
        descripcion="d",
        id_infraestructura=area,
        id_tipo_dispositivo=tipo,
        es_activo=activo,
        id_dispositivo_gateway=gateway,
    )
    d.id_dispositivo_iot = id_
    return d


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class RepoFake:
    def __init__(self, *dispositivos: DispositivoIot) -> None:
        self.por_id = {d.id_dispositivo_iot: d for d in dispositivos}

    def obtener_por_id(self, id_, *, ids_fincas_permitidas=None):
        return self.por_id.get(id_)

    def obtener_por_serial(self, serial):
        return next((d for d in self.por_id.values() if d.serial.valor == serial), None)

    def guardar(self, d):
        d.id_dispositivo_iot = max(self.por_id, default=0) + 1
        self.por_id[d.id_dispositivo_iot] = d
        return d

    def actualizar(self, d):
        return d

    def listar_por_gateway(self, id_gateway):
        return [d for d in self.por_id.values() if d.id_dispositivo_gateway == id_gateway and d.es_activo]


class InfraRepoFake:
    def obtener_por_id(self, id_, *, ids_fincas_permitidas=None):
        return AREAS.get(id_)


class TipoRepoFake:
    def obtener_por_id(self, id_):
        return TIPOS.get(id_)


class ConfigRepoFake:
    def __init__(self, pendientes=()) -> None:
        self.pendientes = set(pendientes)

    def obtener_pendiente(self, id_):
        return object() if id_ in self.pendientes else None


class AuditoriaFake:
    def __init__(self) -> None:
        self.registros: list[dict] = []

    def registrar(self, **registro):
        self.registros.append(registro)


class BrokerFake:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sincronizadas: list[str] = []
        self.revocadas: list[str] = []

    def sincronizar_credencial(self, serial):
        if self.error:
            raise self.error
        self.sincronizadas.append(serial)

    def revocar_credencial(self, serial):
        if self.error:
            raise self.error
        self.revocadas.append(serial)


class BitacoraFake:
    def __init__(self) -> None:
        self.eventos: list[dict] = []

    def registrar(self, **evento) -> None:
        self.eventos.append(evento)


def _sitio(*extra: DispositivoIot) -> RepoFake:
    """Edge 40 (finca 10) con dos dispositivos, un Edge inactivo y otro de otra finca."""
    return RepoFake(
        _d(40, "EDGE-A", tipo=EDGE),
        _d(41, "EDGE-B", tipo=EDGE, area=2),
        _d(42, "EDGE-APAGADO", tipo=EDGE, activo=False),
        _d(43, "EDGE-OTRA-FINCA", tipo=EDGE, area=3),
        _d(1, "ESP-1", gateway=40),
        _d(2, "ESP-2", area=2, gateway=40),
        _d(3, "SUELTO"),
        *extra,
    )


# ── Registrar (RF-21) ───────────────────────────────────────────────────────

def _registrar(repo, broker, dto: dict):
    use_case = RegistrarDispositivoIotUseCase(
        DbFake(), repo, InfraRepoFake(), TipoRepoFake(), AuditoriaFake(), broker, BitacoraFake()
    )
    datos = {"serial": "ESP-NUEVO", "descripcion": "Nodo", "id_infraestructura": 2, "id_tipo_dispositivo": GENERICO}
    return use_case.execute(RegistrarDispositivoIotDTO(**{**datos, **dto}), USUARIO)


def test_registrar_un_dispositivo_vinculado_a_su_edge_le_suma_los_topics_al_edge():
    repo, broker = _sitio(), BrokerFake()

    nuevo = _registrar(repo, broker, {"id_dispositivo_gateway": 40})

    assert nuevo.id_dispositivo_gateway == 40  # otra área, misma finca: válido
    assert broker.sincronizadas == ["EDGE-A"]


@pytest.mark.parametrize(
    ("dto", "error", "codigo"),
    [
        ({"id_dispositivo_gateway": 999}, NotFoundError, "GATEWAY_EDGE_NO_ENCONTRADO"),
        ({"id_dispositivo_gateway": 3}, BusinessRuleError, "NO_ES_GATEWAY_EDGE"),
        ({"id_dispositivo_gateway": 42}, BusinessRuleError, "GATEWAY_EDGE_INACTIVO"),
        ({"id_dispositivo_gateway": 43}, BusinessRuleError, "GATEWAY_EDGE_OTRA_FINCA"),
        ({"id_dispositivo_gateway": 40, "id_tipo_dispositivo": EDGE}, BusinessRuleError, "EDGE_NO_TIENE_GATEWAY"),
    ],
)
def test_registrar_valida_el_gateway_edge(dto, error, codigo):
    repo, broker = _sitio(), BrokerFake()
    antes = len(repo.por_id)

    with pytest.raises(error) as exc:
        _registrar(repo, broker, dto)

    assert exc.value.code == codigo and exc.value.field == "id_dispositivo_gateway"
    assert len(repo.por_id) == antes and broker.sincronizadas == []


def test_registrar_un_edge_o_un_dispositivo_sin_edge_no_toca_el_broker():
    repo, broker = _sitio(), BrokerFake()
    _registrar(repo, broker, {"id_tipo_dispositivo": EDGE, "serial": "EDGE-NUEVO"})
    _registrar(repo, broker, {"serial": "OTRO-SUELTO"})
    assert broker.sincronizadas == []


# ── Asignar / cambiar / quitar el Edge (PATCH /{id}/gateway) ────────────────

def _asignar(repo, broker, id_dispositivo, id_gateway, bitacora=None):
    use_case = AsignarGatewayEdgeUseCase(
        DbFake(), repo, InfraRepoFake(), TipoRepoFake(), broker, bitacora or BitacoraFake()
    )
    return use_case.execute(id_dispositivo, AsignarGatewayEdgeDTO(id_dispositivo_gateway=id_gateway), USUARIO)


def test_cambiar_de_edge_sincroniza_el_nuevo_y_el_anterior():
    repo, broker, bitacora = _sitio(), BrokerFake(), BitacoraFake()

    d = _asignar(repo, broker, 1, 41, bitacora)

    assert d.id_dispositivo_gateway == 41
    assert broker.sincronizadas == ["EDGE-B", "EDGE-A"]
    (evento,) = bitacora.eventos
    assert evento["evento"] == "DISPOSITIVO_GATEWAY_EDGE_ASIGNADO"
    assert evento["detalle"] == {"id_gateway_anterior": 40, "id_gateway_nuevo": 41}


def test_quitar_el_edge_le_saca_los_topics_al_anterior():
    repo, broker = _sitio(), BrokerFake()
    assert _asignar(repo, broker, 1, None).id_dispositivo_gateway is None
    assert broker.sincronizadas == ["EDGE-A"]


def test_asignar_el_mismo_edge_no_hace_nada():
    repo, broker = _sitio(), BrokerFake()
    _asignar(repo, broker, 1, 40)
    assert broker.sincronizadas == []


def test_no_se_cambia_el_edge_de_un_dispositivo_inactivo():
    repo, broker = _sitio(_d(5, "APAGADO", activo=False)), BrokerFake()
    with pytest.raises(BusinessRuleError):
        _asignar(repo, broker, 5, 40)


def test_si_el_broker_no_responde_la_asignacion_se_mantiene_y_queda_rastro():
    caida = ServiceUnavailableError(code="BROKER_MQTT_NO_DISPONIBLE", message="caído")
    repo, bitacora = _sitio(), BitacoraFake()

    d = _asignar(repo, BrokerFake(error=caida), 3, 40, bitacora)

    assert d.id_dispositivo_gateway == 40
    assert [e["evento"] for e in bitacora.eventos] == [
        "DISPOSITIVO_GATEWAY_EDGE_ASIGNADO",
        "CREDENCIAL_MQTT_SINCRONIZACION_FALLIDA",
    ]


# ── Desactivar: cascada del Edge a sus dispositivos ─────────────────────────

def _desactivar(repo, broker, pendientes=()):
    db, auditoria, bitacora = DbFake(), AuditoriaFake(), BitacoraFake()
    use_case = DesactivarDispositivoIotUseCase(
        db, repo, ConfigRepoFake(pendientes), auditoria, broker, bitacora
    )
    return use_case, db, auditoria, bitacora


def test_desactivar_un_edge_desactiva_en_cascada_a_sus_dispositivos():
    repo, broker = _sitio(), BrokerFake()
    use_case, db, auditoria, _ = _desactivar(repo, broker)

    use_case.execute(40, USUARIO)

    assert not repo.por_id[40].es_activo
    assert not repo.por_id[1].es_activo and not repo.por_id[2].es_activo
    assert repo.por_id[3].es_activo  # no lo atendía
    assert repo.por_id[1].id_dispositivo_gateway == 40  # el vínculo se conserva
    assert db.commits == 1  # una sola transacción
    motivos = {r["id_dispositivo_iot"]: r["valores_nuevos"].get("motivo") for r in auditoria.registros}
    assert motivos == {40: None, 1: "gateway_edge_desactivado", 2: "gateway_edge_desactivado"}
    assert all(r["tipo_operacion"] == "DEACTIVATE" for r in auditoria.registros)
    assert broker.revocadas == ["EDGE-A", "ESP-1", "ESP-2"]


def test_una_configuracion_pendiente_en_un_dispositivo_del_edge_bloquea_todo():
    repo, broker = _sitio(), BrokerFake()
    use_case, db, auditoria, _ = _desactivar(repo, broker, pendientes={2})

    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(40, USUARIO)

    assert exc.value.code == "CONFIG_PENDIENTE_EN_DISPOSITIVOS_DEL_EDGE"
    assert "ESP-2" in exc.value.message
    assert all(d.es_activo for i, d in repo.por_id.items() if i != 42)
    assert db.commits == 0 and auditoria.registros == [] and broker.revocadas == []


def test_desactivar_un_dispositivo_del_edge_solo_lo_desactiva_a_el():
    repo, broker = _sitio(), BrokerFake()
    use_case, *_ = _desactivar(repo, broker)

    use_case.execute(1, USUARIO)

    assert not repo.por_id[1].es_activo
    assert repo.por_id[40].es_activo and repo.por_id[2].es_activo
    assert broker.revocadas == ["ESP-1"]  # el broker le quita sus topics al Edge


def test_si_el_broker_no_responde_la_cascada_igual_se_mantiene():
    caida = ServiceUnavailableError(code="BROKER_MQTT_NO_DISPONIBLE", message="caído")
    repo = _sitio()
    use_case, db, _, bitacora = _desactivar(repo, BrokerFake(error=caida))

    use_case.execute(40, USUARIO)

    assert db.commits == 1 and not repo.por_id[1].es_activo
    assert [e["exitoso"] for e in bitacora.eventos] == [False, False, False]


# ── RF-23: un Edge no se configura remotamente ──────────────────────────────

def test_configurar_remotamente_un_edge_se_rechaza():
    class MqttNoDebeLlamarse:
        def enviar_configuracion(self, *_):
            raise AssertionError("no debe publicar nada")

    use_case = ConfigurarRemotamenteUseCase(
        DbFake(), _sitio(), ConfigRepoFake(), TipoRepoFake(), MqttNoDebeLlamarse()
    )
    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(40, ConfigurarRemotamenteDTO(frecuencia_captura=10, intervalo_transmision=15), USUARIO)
    assert exc.value.code == "CONFIGURACION_NO_APLICA_A_GATEWAY_EDGE"


# ── Router ──────────────────────────────────────────────────────────────────

def test_endpoint_patch_gateway(monkeypatch: pytest.MonkeyPatch):
    from src.configuration.infrastructure.routers import dispositivo_iot_router as modulo
    from src.shared import rbac

    repo, broker = _sitio(), BrokerFake()

    class AlcanceFake:
        def __init__(self, _db):
            pass

        def listar_ids_fincas_permitidas(self, _id_usuario, _id_rol):
            return None

    monkeypatch.setattr(rbac, "tiene_permiso", lambda *_args: True)
    monkeypatch.setattr(modulo, "AlcanceFincaAdapter", AlcanceFake)
    monkeypatch.setattr(modulo, "SqlAlchemyDispositivoIotRepository", lambda _db: repo)
    monkeypatch.setattr(modulo, "SqlAlchemyInfraestructuraRepository", lambda _db: InfraRepoFake())
    monkeypatch.setattr(modulo, "SqlAlchemyTipoDispositivoIotRepository", lambda _db: TipoRepoFake())
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
        ok = client.patch("/configuracion/dispositivos-iot/3/gateway", json={"id_dispositivo_gateway": 40})
        otra_finca = client.patch("/configuracion/dispositivos-iot/3/gateway", json={"id_dispositivo_gateway": 43})

    assert ok.status_code == 200 and ok.json()["id_dispositivo_gateway"] == 40
    assert otra_finca.status_code == 422
    assert otra_finca.json()["error_code"] == "GATEWAY_EDGE_OTRA_FINCA"
    assert broker.sincronizadas == ["EDGE-A"]
