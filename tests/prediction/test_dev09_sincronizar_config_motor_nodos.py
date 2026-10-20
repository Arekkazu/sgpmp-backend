"""DEV-09 (RF-65 E7/E8/E10): la configuración del motor se sincroniza con sus nodos Edge.

Al guardar, se envía a cada nodo con ``origen: "config_motor"`` (BRK-05,
``CONFIG_MOTOR_IA``) y ``modulo4.sincronizacion_nodos_edge`` refleja la
respuesta del broker. El router traduce el resultado a 201/200, 202 o 409.
Fakes en memoria; el router se prueba con dependencias reemplazadas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.prediction.application.use_cases.motor_ia.configurar_motor_use_case import (
    ConfigurarMotorUseCase,
    payload_config_motor,
)
from src.prediction.application.use_cases.motor_ia.consultar_sincronizacion_motor_use_case import (
    ConsultarSincronizacionMotorUseCase,
)
from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA
from src.prediction.domain.entities.sincronizacion_nodo_edge import (
    NodoEdge,
    ResultadoEnvioConfigMotor,
    SincronizacionNodoEdge,
)
from src.prediction.infrastructure.adapters import config_motor_edge_mqtt_adapter as adaptador_mod
from src.prediction.infrastructure.adapters.config_motor_edge_mqtt_adapter import ConfigMotorEdgeMqttAdapter
from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO
from src.shared.errors import BusinessRuleError, NotFoundError

TIPO = "MODELO_ESPECIES_GRANDES"
NODO_1 = NodoEdge(id_dispositivo_iot=38, serial="EDGE-001")
NODO_2 = NodoEdge(id_dispositivo_iot=39, serial="EDGE-002")


def _existente(config_version: int = 3) -> ConfiguracionMotorIA:
    entidad = ConfiguracionMotorIA.crear(
        tipo_modelo=TIPO, umbral_riesgo_alto=Decimal("0.7"), umbral_alerta_critica=Decimal("0.8"),
        ventana_temporal_min=10, modo_ejecucion="EDGE", w_factor_sanitario=Decimal("0.5"),
        w_factor_ambiental=Decimal("0.3"), w_factor_densidad=Decimal("0.2"), id_usuario_responsable=1,
    )
    entidad.id_configuracion_motor = 4
    entidad.config_version = config_version
    entidad.fecha_creacion = datetime(2026, 10, 1, tzinfo=timezone.utc)
    return entidad


class _ConfigRepo:
    def __init__(self, existente=None):
        self.existente = existente

    def obtener_por_tipo(self, _tipo): return self.existente

    def guardar(self, entidad):
        entidad.id_configuracion_motor = 4
        entidad.fecha_creacion = datetime(2026, 10, 1, tzinfo=timezone.utc)
        return entidad

    def actualizar(self, entidad): return entidad


class _Auditoria:
    def registrar(self, **_kw): pass


class _Versiones:
    def obtener_llave(self, _id): return None


class _Nodos:
    def __init__(self, nodos): self.nodos = nodos
    def listar_nodos_activos(self, _tipo): return list(self.nodos)


class _SincronizacionRepo:
    def __init__(self):
        self.filas: dict[tuple[int, str], SincronizacionNodoEdge] = {}

    def registrar_intento(self, *, nodo, tipo_modelo, config_version_servidor, config_version_nodo,
                          estado_sincronizacion, motivo_fallo, fecha_intento):
        previa = self.filas.get((nodo.id_dispositivo_iot, tipo_modelo))
        fila = SincronizacionNodoEdge(
            id_dispositivo_iot=nodo.id_dispositivo_iot, serial=nodo.serial, tipo_modelo=tipo_modelo,
            config_version_servidor=config_version_servidor, estado_sincronizacion=estado_sincronizacion,
            intentos_sincronizacion=(previa.intentos_sincronizacion if previa else 0) + 1,
            config_version_nodo=config_version_nodo, fecha_ultimo_intento=fecha_intento,
            fecha_aplicacion=fecha_intento if estado_sincronizacion == "APLICADA"
            else (previa.fecha_aplicacion if previa else None),
            motivo_fallo=motivo_fallo,
        )
        self.filas[(nodo.id_dispositivo_iot, tipo_modelo)] = fila
        return fila

    def listar_por_tipo_modelo(self, tipo_modelo):
        return [f for (_, t), f in sorted(self.filas.items()) if t == tipo_modelo]


class _Broker:
    """serial -> (estado, config_version que informa el nodo)."""

    def __init__(self, veredictos):
        self.veredictos = veredictos
        self.llamadas = []

    def propagar_config(self, seriales, payload):
        self.llamadas.append((seriales, payload))
        return {s: ResultadoEnvioConfigMotor(estado=self.veredictos[s][0], mensaje=f"broker {self.veredictos[s][0]}",
                                             config_version=self.veredictos[s][1]) for s in seriales}


class _Db:
    def commit(self): pass
    def rollback(self): pass


def _dto(**cambios) -> ConfigurarMotorDTO:
    datos = dict(tipo_modelo=TIPO, modo_ejecucion="EDGE", ventana_temporal_min=10,
                 umbral_riesgo_alto=Decimal("0.7"), umbral_alerta_critica=Decimal("0.8"))
    datos.update(cambios)
    return ConfigurarMotorDTO(**datos)


def _configurar(nodos, veredictos, existente=None, dto=None):
    repo, broker = _SincronizacionRepo(), _Broker(veredictos)
    resultado = ConfigurarMotorUseCase(
        db=_Db(), repo=_ConfigRepo(existente), auditoria_repo=_Auditoria(), version_port=_Versiones(),
        nodo_edge_port=_Nodos(nodos), sincronizacion_repo=repo, config_edge_port=broker,
    ).execute(dto or _dto(), id_usuario=1)
    return resultado, repo, broker


# ── Tabla del ticket: respuesta del broker -> estado_sincronizacion ────────

@pytest.mark.parametrize(
    "estado_broker, version_nodo, esperado",
    [
        ("APLICADA", 4, "APLICADA"),        # mismo config_version
        ("APLICADA", 3, "DESINCRONIZADO"),  # E10: otro config_version
        ("APLICADA", None, "APLICADA"),     # el ACK no trajo versión: confirmó la enviada
        ("PENDIENTE", None, "PENDIENTE"),   # E7: nodo apagado
        ("NO_CONF", None, "FALLIDA"),       # E8: sin ACK
        ("SIN_INTEGRACION", None, "PENDIENTE"),
        ("RARO", None, "FALLIDA"),
    ],
)
def test_respuesta_del_broker_se_traduce_al_estado_de_la_fila(estado_broker, version_nodo, esperado):
    assert ResultadoEnvioConfigMotor(estado_broker, "m", version_nodo).estado_sincronizacion(4) == esperado


def test_payload_trae_los_campos_del_comando_config_motor_del_broker():
    payload = payload_config_motor(_existente(config_version=7))
    assert set(payload) == {"tipo_modelo", "config_version", "configuracion"}
    assert payload["config_version"] == 7
    assert payload["configuracion"]["modo_ejecucion"] == "EDGE"


# ── Caso de uso ────────────────────────────────────────────────────────────

def test_actualizar_envia_la_config_version_nueva_y_la_fila_queda_aplicada():
    resultado, repo, broker = _configurar([NODO_1], {"EDGE-001": ("APLICADA", 4)}, existente=_existente(3))
    seriales, payload = broker.llamadas[0]
    assert seriales == ["EDGE-001"] and payload["config_version"] == 4
    fila = repo.filas[(38, TIPO)]
    assert (fila.estado_sincronizacion, fila.config_version_servidor, fila.config_version_nodo) == ("APLICADA", 4, 4)
    assert fila.fecha_aplicacion is not None and fila.motivo_fallo is None
    assert resultado.sincronizacion.estado == "APLICADA"
    assert not resultado.sincronizacion.hay_sin_confirmar and not resultado.sincronizacion.hay_desincronizados


def test_nodo_apagado_deja_la_fila_pendiente_y_la_configuracion_guardada():
    resultado, repo, _ = _configurar([NODO_1], {"EDGE-001": ("PENDIENTE", None)})
    assert resultado.es_nueva and resultado.entidad.id_configuracion_motor == 4
    assert repo.filas[(38, TIPO)].estado_sincronizacion == "PENDIENTE"
    assert repo.filas[(38, TIPO)].motivo_fallo == "broker PENDIENTE"
    assert resultado.sincronizacion.hay_sin_confirmar


def test_nodo_con_otra_version_queda_desincronizado_con_el_motivo():
    resultado, repo, _ = _configurar([NODO_1, NODO_2], {"EDGE-001": ("APLICADA", 9), "EDGE-002": ("APLICADA", 1)})
    assert resultado.sincronizacion.estado == "DESINCRONIZADO"
    assert resultado.sincronizacion.hay_desincronizados
    assert "config_version 9" in repo.filas[(38, TIPO)].motivo_fallo
    assert repo.filas[(39, TIPO)].estado_sincronizacion == "APLICADA"


def test_modo_edge_sin_nodos_se_decide_con_datos_reales():
    with pytest.raises(BusinessRuleError) as exc:
        _configurar([], {})
    assert exc.value.code == "MODO_EDGE_SIN_NODOS"


def test_modo_servidor_sin_nodos_guarda_sin_llamar_al_broker():
    resultado, _, broker = _configurar([], {}, dto=_dto(modo_ejecucion="SERVIDOR"))
    assert broker.llamadas == []
    assert resultado.sincronizacion.nodos == [] and resultado.sincronizacion.estado == "APLICADA"


def test_modo_servidor_con_nodos_tambien_les_avisa():
    """Los nodos deben saber que la inferencia pasó al servidor."""
    _, _, broker = _configurar([NODO_1], {"EDGE-001": ("APLICADA", 1)}, dto=_dto(modo_ejecucion="SERVIDOR"))
    assert broker.llamadas[0][1]["configuracion"]["modo_ejecucion"] == "SERVIDOR"


def test_reintento_actualiza_la_misma_fila_y_suma_intentos():
    repo = _SincronizacionRepo()
    for veredicto in (("PENDIENTE", None), ("APLICADA", 1)):
        ConfigurarMotorUseCase(
            db=_Db(), repo=_ConfigRepo(), auditoria_repo=_Auditoria(), version_port=_Versiones(),
            nodo_edge_port=_Nodos([NODO_1]), sincronizacion_repo=repo,
            config_edge_port=_Broker({"EDGE-001": veredicto}),
        ).execute(_dto(), id_usuario=1)
    assert len(repo.filas) == 1
    assert repo.filas[(38, TIPO)].intentos_sincronizacion == 2
    assert repo.filas[(38, TIPO)].estado_sincronizacion == "APLICADA"


# ── Consulta ───────────────────────────────────────────────────────────────

def test_consulta_marca_pendiente_un_nodo_con_una_version_anterior():
    _, repo, _ = _configurar([NODO_1], {"EDGE-001": ("APLICADA", 1)})
    consulta = ConsultarSincronizacionMotorUseCase(
        repo=_ConfigRepo(_existente(config_version=2)), sincronizacion_repo=repo,
    ).execute(TIPO)
    assert consulta.nodos[0].estado_sincronizacion == "APLICADA"
    assert consulta.estado == "PENDIENTE"
    assert "EDGE-001" in consulta.mensaje


def test_consulta_sin_configuracion_es_404():
    with pytest.raises(NotFoundError) as exc:
        ConsultarSincronizacionMotorUseCase(repo=_ConfigRepo(None), sincronizacion_repo=_SincronizacionRepo()).execute(TIPO)
    assert exc.value.code == "CONFIGURACION_MOTOR_NO_ENCONTRADA"


# ── Router: código HTTP según la sincronización ───────────────────────────

@pytest.fixture
def cliente(monkeypatch):
    from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
    from src.prediction.infrastructure.routers import motor_ia_router as router_mod
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    estado = {"veredictos": {}, "existente": None}
    monkeypatch.setattr(router_mod, "SqlAlchemyConfiguracionMotorIARepository", lambda db: _ConfigRepo(estado["existente"]))
    monkeypatch.setattr(router_mod, "SqlAlchemyEventoAuditoriaM04Repository", lambda db: _Auditoria())
    monkeypatch.setattr(router_mod, "VersionModeloAdapter", lambda db: _Versiones())
    monkeypatch.setattr(router_mod, "NodoEdgeM09Adapter", lambda db: _Nodos([NODO_1]))
    monkeypatch.setattr(router_mod, "SqlAlchemySincronizacionNodoEdgeRepository", lambda db: _SincronizacionRepo())
    monkeypatch.setattr(router_mod, "ConfigMotorEdgeMqttAdapter", lambda: _Broker(estado["veredictos"]))

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db] = lambda: _Db()
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
    for ruta in router_mod.router.routes:
        for dependencia in ruta.dependencies:
            app.dependency_overrides[dependencia.dependency] = lambda: None
    return TestClient(app), estado


_BODY = {"tipo_modelo": TIPO, "modo_ejecucion": "EDGE", "ventana_temporal_min": 10,
         "umbral_riesgo_alto": "0.7", "umbral_alerta_critica": "0.8"}


@pytest.mark.parametrize(
    "veredicto, existente, http, estado",
    [
        (("APLICADA", 1), None, 201, "APLICADA"),
        (("APLICADA", 4), 3, 200, "APLICADA"),
        (("APLICADA", 1), 3, 409, "DESINCRONIZADO"),  # E10
        (("PENDIENTE", None), None, 202, "PENDIENTE"),  # E7 — criterio de aceptación
        (("NO_CONF", None), None, 202, "FALLIDA"),      # E8
    ],
)
def test_post_motor_ia_responde_segun_la_sincronizacion(cliente, veredicto, existente, http, estado):
    client, ctx = cliente
    ctx["veredictos"] = {"EDGE-001": veredicto}
    ctx["existente"] = _existente(existente) if existente else None
    r = client.post("/prediccion/motor-ia", json=_BODY)
    assert r.status_code == http, r.text
    cuerpo = r.json()
    assert cuerpo["tipo_modelo"] == TIPO  # la configuración quedó guardada en todos los casos
    assert cuerpo["sincronizacion"]["nodos"][0]["estado_sincronizacion"] == estado


# ── Adaptador HTTP al broker ───────────────────────────────────────────────

class _Respuesta:
    def __init__(self, status, cuerpo):
        self.status_code, self._cuerpo, self.text = status, cuerpo, str(cuerpo)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=httpx.Request("POST", "http://broker"), response=self)

    def json(self): return self._cuerpo


def test_adaptador_envia_origen_config_motor_y_lee_el_config_version_del_ack(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER_URL", "http://broker")
    monkeypatch.setenv("MQTT_BROKER_TOKEN", "token")
    enviados = []

    def _post(url, json, headers, timeout):
        enviados.append(json)
        return {
            "EDGE-001": _Respuesta(200, {"estado": "APLICADA", "mensaje": "ok", "topic": "t", "config_version": 4}),
            "EDGE-002": _Respuesta(200, {"estado": "APLICADA", "mensaje": "ok", "topic": "t", "config_version": True}),
            "EDGE-003": _Respuesta(503, {"detail": "MQTT"}),
        }[json["serial"]]

    monkeypatch.setattr(adaptador_mod.httpx, "post", _post)
    resultados = ConfigMotorEdgeMqttAdapter().propagar_config(["EDGE-001", "EDGE-002", "EDGE-003"], {"config_version": 4})
    assert {e["origen"] for e in enviados} == {"config_motor"}
    assert resultados["EDGE-001"].config_version == 4
    assert resultados["EDGE-002"].config_version is None  # un booleano no es una versión
    assert resultados["EDGE-003"].estado == "NO_CONF" and "HTTP 503" in resultados["EDGE-003"].mensaje


def test_adaptador_sin_broker_configurado_no_intenta(monkeypatch):
    monkeypatch.delenv("MQTT_BROKER_URL", raising=False)
    monkeypatch.delenv("MQTT_BROKER_TOKEN", raising=False)
    monkeypatch.setattr(adaptador_mod.httpx, "post", lambda *a, **k: pytest.fail("no debía llamar al broker"))
    assert ConfigMotorEdgeMqttAdapter().propagar_config(["EDGE-001"], {})["EDGE-001"].estado == "SIN_INTEGRACION"
