"""DEV-08 (RF-55 Restricción 4, RF-57 E14/E15): reglas compuestas al Gateway Edge.

La regla viaja por el broker con ``origen: "regla_compuesta"`` (BRK-05,
``tipo_comando = REGLA_COMPUESTA``, ``ACK_REGLA``) y el veredicto de cada
Gateway queda por nodo. Fakes en memoria; el adaptador se prueba con
``httpx.post`` reemplazado.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from src.shared.errors import BusinessRuleError, NotFoundError
from src.telemetry.application.use_cases.reglas.consultar_sincronizacion_regla_edge_use_case import (
    ConsultarSincronizacionReglaEdgeUseCase,
)
from src.telemetry.application.use_cases.reglas.sincronizar_regla_edge_use_case import (
    MOTIVO_SIN_GATEWAY_EDGE,
    SincronizarReglaEdgeUseCase,
    payload_regla_compuesta,
)
from src.telemetry.domain.entities.alerta import ReglaAlerta
from src.telemetry.domain.entities.sincronizacion_regla_edge import (
    GatewayEdge,
    ResultadoPropagacionEdge,
    SincronizacionReglaEdge,
)
from src.telemetry.infrastructure.adapters import regla_compuesta_edge_mqtt_adapter as adaptador_mod
from src.telemetry.infrastructure.adapters.regla_compuesta_edge_mqtt_adapter import ReglaCompuestaEdgeMqttAdapter

ID_REGLA = 9
GW_1 = GatewayEdge(id_dispositivo_iot=11, serial="EDGE-001")
GW_2 = GatewayEdge(id_dispositivo_iot=12, serial="EDGE-002")


def _regla(**cambios) -> ReglaAlerta:
    datos = dict(
        id_regla_alertas=ID_REGLA, nombre="THI_ESTRES_CALORICO", tipo_sensor="TEMPERATURA",
        es_regla_compuesta=True, ventana_confirmacion_min=Decimal("5"), lectura_confirmacion_max=Decimal("3"),
        es_activa=True, version_regla=2, fecha_creacion=datetime(2026, 10, 1, tzinfo=timezone.utc),
        categoria_variable="AMBIENTAL", umbral_min=Decimal("68.5"), umbral_max=Decimal("79.0"),
        umbrales_severidad={"ALTA": 75.0, "CRITICA": 79.0}, tiene_ejecutar_edge=True, id_finca=1, id_especie=1,
    )
    datos.update(cambios)
    return ReglaAlerta(**datos)


class _ReglaRepo:
    def __init__(self, regla):
        self.regla = regla

    def obtener_por_id(self, id_regla_alertas):
        return self.regla if self.regla and self.regla.id_regla_alertas == id_regla_alertas else None


class _SincronizacionRepo:
    def __init__(self, gateways):
        self.gateways = gateways
        self.filas: dict[tuple[int, int], SincronizacionReglaEdge] = {}

    def listar_gateways_destino(self, id_regla_alertas):
        return list(self.gateways)

    def registrar_intento(self, *, id_regla_alertas, gateway, version_regla, estado_sincronizacion,
                          mensaje, fecha_intento, id_usuario):
        previa = self.filas.get((id_regla_alertas, gateway.id_dispositivo_iot))
        fila = SincronizacionReglaEdge(
            id_regla_alertas=id_regla_alertas, id_dispositivo_iot=gateway.id_dispositivo_iot,
            serial=gateway.serial, version_regla=version_regla, estado_sincronizacion=estado_sincronizacion,
            intentos_sincronizacion=(previa.intentos_sincronizacion + 1) if previa else 1,
            fecha_ultimo_intento=fecha_intento, mensaje=mensaje, id_usuario=id_usuario,
            fecha_aplicacion=fecha_intento if estado_sincronizacion == "APLICADA"
            else (previa.fecha_aplicacion if previa else None),
        )
        self.filas[(id_regla_alertas, gateway.id_dispositivo_iot)] = fila
        return fila

    def listar_por_regla(self, id_regla_alertas):
        return [f for (r, _), f in sorted(self.filas.items()) if r == id_regla_alertas]


class _EdgePort:
    def __init__(self, estados: dict[str, str]):
        self.estados = estados
        self.llamadas: list[tuple[list[str], dict]] = []

    def propagar_regla(self, seriales_gateway, payload):
        self.llamadas.append((seriales_gateway, payload))
        return {s: ResultadoPropagacionEdge(estado=self.estados[s], mensaje=f"veredicto {self.estados[s]}")
                for s in seriales_gateway}


class _Db:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def _sincronizar(regla, gateways, estados):
    repo, port, db = _SincronizacionRepo(gateways), _EdgePort(estados), _Db()
    resultado = SincronizarReglaEdgeUseCase(
        db=db, regla_repo=_ReglaRepo(regla), sincronizacion_repo=repo, edge_port=port,
    ).execute(ID_REGLA, id_usuario=4)
    return resultado, repo, port, db


# ── Contrato BRK-05 ────────────────────────────────────────────────────────

def test_payload_trae_los_campos_del_comando_regla_compuesta_del_broker():
    """Los campos de ``ReglaCompuestaCommandRequest`` (sin origen/serial, que pone el adaptador)."""
    payload = payload_regla_compuesta(_regla())
    assert set(payload) == {"id_regla_alerta", "version_regla", "es_activa", "regla"}
    assert payload["id_regla_alerta"] == ID_REGLA
    assert payload["version_regla"] == 2
    assert payload["es_activa"] is True
    assert payload["regla"]["umbral_min"] == "68.5"  # Decimal como texto, sin perder precisión
    assert payload["regla"]["umbrales_severidad"] == {"ALTA": 75.0, "CRITICA": 79.0}
    assert payload["regla"]["prevalece_sobre_regla_simple"] is True


def test_regla_desactivada_viaja_con_es_activa_false_para_que_el_edge_la_retire():
    resultado, _, port, _ = _sincronizar(_regla(es_activa=False), [GW_1], {"EDGE-001": "APLICADA"})
    assert port.llamadas[0][1]["es_activa"] is False
    assert resultado.estado == "APLICADA"


# ── Precondiciones ─────────────────────────────────────────────────────────

def test_regla_inexistente_es_404():
    with pytest.raises(NotFoundError):
        _sincronizar(None, [GW_1], {})


@pytest.mark.parametrize(
    "cambios, codigo",
    [({"es_regla_compuesta": False}, "REGLA_NO_COMPUESTA"), ({"tiene_ejecutar_edge": False}, "REGLA_SIN_EJECUCION_EDGE")],
)
def test_solo_se_propagan_reglas_compuestas_marcadas_para_el_edge(cambios, codigo):
    with pytest.raises(BusinessRuleError) as exc:
        _sincronizar(_regla(**cambios), [GW_1], {"EDGE-001": "APLICADA"})
    assert exc.value.code == codigo


# ── Estado por nodo (criterio de aceptación) ──────────────────────────────

def test_ack_regla_de_todos_los_gateway_deja_aplicada():
    resultado, repo, port, db = _sincronizar(_regla(), [GW_1, GW_2], {"EDGE-001": "APLICADA", "EDGE-002": "APLICADA"})
    assert port.llamadas[0][0] == ["EDGE-001", "EDGE-002"]
    assert resultado.estado == "APLICADA"
    assert [n.estado_sincronizacion for n in resultado.nodos] == ["APLICADA", "APLICADA"]
    assert all(n.version_regla == 2 and n.fecha_aplicacion is not None for n in resultado.nodos)
    assert db.commits == 1


def test_gateway_apagado_queda_pendiente():
    resultado, repo, _, _ = _sincronizar(_regla(), [GW_1, GW_2], {"EDGE-001": "APLICADA", "EDGE-002": "PENDIENTE"})
    assert resultado.estado == "PENDIENTE"
    estados = {n.serial: n.estado_sincronizacion for n in resultado.nodos}
    assert estados == {"EDGE-001": "APLICADA", "EDGE-002": "PENDIENTE"}
    assert repo.filas[(ID_REGLA, 12)].fecha_aplicacion is None


def test_un_gateway_sin_ack_consolida_no_conf():
    resultado, _, _, _ = _sincronizar(_regla(), [GW_1, GW_2], {"EDGE-001": "NO_CONF", "EDGE-002": "PENDIENTE"})
    assert resultado.estado == "NO_CONF"


def test_sin_broker_configurado_se_guarda_pendiente():
    resultado, _, _, _ = _sincronizar(_regla(), [GW_1], {"EDGE-001": "SIN_INTEGRACION"})
    assert resultado.nodos[0].estado_sincronizacion == "PENDIENTE"
    assert resultado.estado == "PENDIENTE"


def test_estado_desconocido_del_broker_no_confirma_nada():
    resultado, _, _, _ = _sincronizar(_regla(), [GW_1], {"EDGE-001": "RARO"})
    assert resultado.nodos[0].estado_sincronizacion == "NO_CONF"


def test_regla_sin_gateway_destino_queda_pendiente_sin_llamar_al_broker():
    resultado, _, port, db = _sincronizar(_regla(), [], {})
    assert port.llamadas == []
    assert resultado.estado == "PENDIENTE"
    assert resultado.mensaje == MOTIVO_SIN_GATEWAY_EDGE
    assert db.commits == 0


def test_reintento_actualiza_la_fila_del_nodo_y_suma_intentos():
    repo, db = _SincronizacionRepo([GW_1]), _Db()
    for estado in ("PENDIENTE", "APLICADA"):
        resultado = SincronizarReglaEdgeUseCase(
            db=db, regla_repo=_ReglaRepo(_regla()), sincronizacion_repo=repo,
            edge_port=_EdgePort({"EDGE-001": estado}),
        ).execute(ID_REGLA, id_usuario=4)
    assert len(repo.filas) == 1
    assert resultado.nodos[0].intentos_sincronizacion == 2
    assert resultado.estado == "APLICADA"


# ── Consulta ───────────────────────────────────────────────────────────────

def test_consulta_marca_pendiente_si_la_regla_cambio_despues_de_aplicarse():
    _, repo, _, _ = _sincronizar(_regla(version_regla=2), [GW_1], {"EDGE-001": "APLICADA"})
    consulta = ConsultarSincronizacionReglaEdgeUseCase(
        regla_repo=_ReglaRepo(_regla(version_regla=3)), sincronizacion_repo=repo,
    ).execute(ID_REGLA)
    assert consulta.version_regla == 3
    assert consulta.nodos[0].estado_sincronizacion == "APLICADA"
    assert consulta.estado == "PENDIENTE"
    assert "EDGE-001" in consulta.mensaje


def test_consulta_de_regla_inexistente_es_404():
    with pytest.raises(NotFoundError):
        ConsultarSincronizacionReglaEdgeUseCase(
            regla_repo=_ReglaRepo(None), sincronizacion_repo=_SincronizacionRepo([]),
        ).execute(ID_REGLA)


# ── Adaptador HTTP al broker ───────────────────────────────────────────────

class _Respuesta:
    def __init__(self, status: int, cuerpo: dict):
        self.status_code, self._cuerpo, self.text = status, cuerpo, str(cuerpo)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=httpx.Request("POST", "http://broker"), response=self)

    def json(self):
        return self._cuerpo


@pytest.fixture
def broker(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER_URL", "http://broker")
    monkeypatch.setenv("MQTT_BROKER_TOKEN", "token")
    enviados: list[dict] = []
    respuestas: dict[str, _Respuesta] = {}

    def _post(url, json, headers, timeout):
        assert url == "http://broker/v1/commands"
        assert headers == {"Authorization": "Bearer token"}
        enviados.append(json)
        respuesta = respuestas[json["serial"]]
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(adaptador_mod.httpx, "post", _post)
    return enviados, respuestas


def test_adaptador_envia_origen_regla_compuesta_y_devuelve_el_veredicto(broker):
    enviados, respuestas = broker
    respuestas["EDGE-001"] = _Respuesta(200, {"estado": "APLICADA", "mensaje": "ok", "topic": "sgpmp/EDGE-001/command"})
    respuestas["EDGE-002"] = _Respuesta(200, {"estado": "PENDIENTE", "mensaje": "desconectado", "topic": None})
    resultados = ReglaCompuestaEdgeMqttAdapter().propagar_regla(
        ["EDGE-001", "EDGE-002"], payload_regla_compuesta(_regla())
    )
    assert {e["origen"] for e in enviados} == {"regla_compuesta"}
    assert {e["serial"] for e in enviados} == {"EDGE-001", "EDGE-002"}
    assert resultados["EDGE-001"] == ResultadoPropagacionEdge("APLICADA", "ok", True)
    assert resultados["EDGE-002"].estado == "PENDIENTE"
    assert resultados["EDGE-002"].publicado is False


def test_adaptador_con_broker_caido_o_error_http_devuelve_no_conf(broker):
    _, respuestas = broker
    respuestas["EDGE-001"] = httpx.ConnectError("caido")
    respuestas["EDGE-002"] = _Respuesta(422, {"detail": "invalido"})
    resultados = ReglaCompuestaEdgeMqttAdapter().propagar_regla(["EDGE-001", "EDGE-002"], {"x": 1})
    assert resultados["EDGE-001"].estado == "NO_CONF"
    assert "ConnectError" in resultados["EDGE-001"].mensaje
    assert resultados["EDGE-002"].estado == "NO_CONF"
    assert "HTTP 422" in resultados["EDGE-002"].mensaje


def test_adaptador_sin_broker_configurado_no_intenta(monkeypatch):
    monkeypatch.delenv("MQTT_BROKER_URL", raising=False)
    monkeypatch.delenv("MQTT_BROKER_TOKEN", raising=False)
    monkeypatch.setattr(adaptador_mod.httpx, "post", lambda *a, **k: pytest.fail("no debía llamar al broker"))
    resultados = ReglaCompuestaEdgeMqttAdapter().propagar_regla(["EDGE-001"], {"x": 1})
    assert resultados["EDGE-001"].estado == "SIN_INTEGRACION"
