"""DEV-10 (M09·RF-20, D-06): el tipo_modelo_asignado de un área va a sus Gateway Edge.

Al crear un área con modelo o cambiar su ``tipo_modelo_asignado``, se envía a
los Gateway Edge del área con ``origen: "tipo_modelo"`` (BRK-05) y el resultado
de cada Gateway queda en la bitácora IoT. Fakes en memoria; el adaptador se
prueba con ``httpx.post`` reemplazado.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from src.configuration.application.use_cases.infraestructuras.editar_infraestructura_use_case import (
    EditarInfraestructuraUseCase,
)
from src.configuration.application.use_cases.infraestructuras.propagar_tipo_modelo_edge import (
    EVENTO_PROPAGACION_TIPO_MODELO,
    PropagadorTipoModeloEdge,
    payload_tipo_modelo,
)
from src.configuration.application.use_cases.infraestructuras.registrar_infraestructura_use_case import (
    RegistrarInfraestructuraUseCase,
)
from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.repositories.destino_edge_repository import GatewayEdgeDestino
from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt
from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.superficie import Superficie
from src.configuration.infrastructure.adapters import edge_sincronizacion_mqtt_adapter as adaptador_mod
from src.configuration.infrastructure.adapters.edge_sincronizacion_mqtt_adapter import EdgeSincronizacionMqttAdapter
from src.configuration.infrastructure.dto.editar_infraestructura_dto import EditarInfraestructuraDTO
from src.configuration.infrastructure.dto.registrar_infraestructura_dto import RegistrarInfraestructuraDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual

USUARIO = UsuarioActual(id_usuario=7, id_token=1, id_rol=1, id_estado_cuenta=2)
GW_1 = GatewayEdgeDestino(id_dispositivo_iot=38, serial="EDGE-001")
GW_2 = GatewayEdgeDestino(id_dispositivo_iot=39, serial="EDGE-002")


def _area(tipo_modelo="MODELO_AVES") -> Infraestructura:
    return Infraestructura(
        id_infraestructura=10, nombre=NombreInfraestructura("Galpón 1"), tipo="Galpón",
        superficie=Superficie(Decimal("120")), id_finca=1, es_activo=True,
        fecha_actualizacion=datetime(2026, 10, 1, tzinfo=timezone.utc),
        id_especie=1, tipo_modelo_asignado=tipo_modelo,
    )


class _Destinos:
    def __init__(self, gateways): self.gateways = gateways
    def listar_gateways_por_infraestructura(self, _id): return list(self.gateways)


class _Edge:
    def __init__(self, estados):
        self.estados = estados
        self.llamadas = []

    def propagar_tipo_modelo(self, seriales, payload):
        self.llamadas.append((seriales, payload))
        return {s: ResultadoEnvioMqtt(estado=self.estados[s], mensaje=f"broker {self.estados[s]}",
                                      publicado=self.estados[s] == "APLICADA") for s in seriales}


class _Bitacora:
    def __init__(self): self.eventos = []
    def registrar_propagacion_tipo_modelo(self, **kw): self.eventos.append(kw)


def _propagador(gateways, estados):
    edge, bitacora = _Edge(estados), _Bitacora()
    return PropagadorTipoModeloEdge(destino_repo=_Destinos(gateways), edge_port=edge, bitacora=bitacora), edge, bitacora


# ── Paso de propagación ────────────────────────────────────────────────────

def test_payload_trae_los_campos_del_comando_tipo_modelo_del_broker():
    assert payload_tipo_modelo(_area("MODELO_PORCINOS")) == {
        "id_infraestructura": 10, "tipo_modelo_asignado": "MODELO_PORCINOS",
    }


def test_registra_en_la_bitacora_el_resultado_de_cada_gateway():
    propagador, edge, bitacora = _propagador([GW_1, GW_2], {"EDGE-001": "APLICADA", "EDGE-002": "PENDIENTE"})
    propagador.propagar(_area("MODELO_ACUICULTURA"), id_usuario=7)
    assert edge.llamadas[0][0] == ["EDGE-001", "EDGE-002"]
    assert [(e["serial"], e["estado"]) for e in bitacora.eventos] == [("EDGE-001", "APLICADA"), ("EDGE-002", "PENDIENTE")]
    evento = bitacora.eventos[0]
    assert evento["evento"] == EVENTO_PROPAGACION_TIPO_MODELO
    assert (evento["id_dispositivo_iot"], evento["id_infraestructura"], evento["id_usuario"]) == (38, 10, 7)
    assert evento["detalle"]["tipo_modelo_asignado"] == "MODELO_ACUICULTURA"
    assert evento["detalle"]["ack_tipo_modelo"] is True
    assert bitacora.eventos[1]["detalle"]["ack_tipo_modelo"] is False


def test_area_sin_gateway_no_llama_al_broker_ni_registra():
    propagador, edge, bitacora = _propagador([], {})
    propagador.propagar(_area(), id_usuario=7)
    assert edge.llamadas == [] and bitacora.eventos == []


def test_area_sin_modelo_no_se_envia():
    propagador, edge, bitacora = _propagador([GW_1], {"EDGE-001": "APLICADA"})
    propagador.propagar(_area(None), id_usuario=7)
    assert edge.llamadas == [] and bitacora.eventos == []


# ── Crear y editar área ───────────────────────────────────────────────────

class _Espia:
    def __init__(self): self.areas = []
    def propagar(self, infra, id_usuario): self.areas.append((infra.tipo_modelo_asignado, id_usuario))


class _InfraRepo:
    def __init__(self, infra=None): self.infra = infra
    def obtener_por_id(self, _id, **_): return self.infra

    def guardar(self, infra):
        infra.id_infraestructura = 10
        return infra

    def actualizar(self, infra): return infra


class _Db:
    def __init__(self): self.commits = 0
    def commit(self): self.commits += 1
    def rollback(self): pass


class _Auditoria:
    def registrar(self, **_kw): pass


class _Especies:
    def obtener_por_id(self, id_especie):
        return SimpleNamespace(id_especie=id_especie, nombre="Gallina", es_activo=True, tipo_modelo="MODELO_AVES")


class _Fincas:
    def obtener_por_id(self, _id, **_): return SimpleNamespace(es_activo=True, id_finca=1)


class _TiposArea:
    def obtener_por_nombre(self, nombre): return SimpleNamespace(nombre=nombre, es_activo=True)


class _Dependencias:
    def contar_activos_de_otra_especie(self, _id, _especie): return (0, None)


def test_crear_area_con_modelo_lo_propaga_despues_del_commit():
    espia, db = _Espia(), _Db()
    RegistrarInfraestructuraUseCase(
        db=db, infra_repo=_InfraRepo(), finca_repo=_Fincas(), tipo_area_repo=_TiposArea(),
        auditoria_repo=_Auditoria(), especie_repo=_Especies(), propagador_tipo_modelo=espia,
    ).execute(RegistrarInfraestructuraDTO(
        nombre_infraestructura="Galpón 1", tipo_area="Galpón", superficie=Decimal("120"),
        finca_id=1, especie_id=1, tipo_modelo_asignado="MODELO_AVES",
    ), USUARIO)
    assert db.commits == 1
    assert espia.areas == [("MODELO_AVES", 7)]


def _editar(area, tipo_modelo, nombre="Galpón 1"):
    espia = _Espia()
    EditarInfraestructuraUseCase(
        db=_Db(), infra_repo=_InfraRepo(area), finca_repo=_Fincas(), tipo_area_repo=_TiposArea(),
        auditoria_repo=_Auditoria(), especie_repo=_Especies(), dependency_port=_Dependencias(),
        propagador_tipo_modelo=espia,
    ).execute(10, EditarInfraestructuraDTO(
        nombre_infraestructura=nombre, tipo_area="Galpón", superficie=Decimal("120"),
        especie_id=1, tipo_modelo_asignado=tipo_modelo, fecha_actualizacion=area.fecha_actualizacion,
    ), USUARIO)
    return espia


def test_cambiar_el_modelo_del_area_lo_propaga():
    assert _editar(_area(None), "MODELO_AVES").areas == [("MODELO_AVES", 7)]


def test_editar_el_area_sin_cambiar_el_modelo_no_reinicia_el_nodo():
    assert _editar(_area("MODELO_AVES"), "MODELO_AVES", nombre="Galpón Norte").areas == []


# ── Adaptador HTTP al broker ───────────────────────────────────────────────

class _Respuesta:
    def __init__(self, status, cuerpo):
        self.status_code, self._cuerpo, self.text = status, cuerpo, str(cuerpo)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=httpx.Request("POST", "http://broker"), response=self)

    def json(self): return self._cuerpo


def test_adaptador_envia_origen_tipo_modelo_y_el_de_umbral_no_cambia(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER_URL", "http://broker")
    monkeypatch.setenv("MQTT_BROKER_TOKEN", "token")
    enviados = []

    def _post(url, json, headers, timeout):
        enviados.append(json)
        if json["serial"] == "EDGE-CAIDO":
            raise httpx.ConnectError("caido")
        return _Respuesta(200, {"estado": "APLICADA", "mensaje": "ok", "topic": "t"})

    monkeypatch.setattr(adaptador_mod.httpx, "post", _post)
    adaptador = EdgeSincronizacionMqttAdapter()
    resultados = adaptador.propagar_tipo_modelo(["EDGE-001", "EDGE-CAIDO"], payload_tipo_modelo(_area()))
    assert enviados[0]["origen"] == "tipo_modelo" and enviados[0]["tipo_modelo_asignado"] == "MODELO_AVES"
    assert resultados["EDGE-001"].estado == "APLICADA"
    assert resultados["EDGE-CAIDO"].estado == "NO_CONF"
    assert resultados["EDGE-CAIDO"].mensaje.startswith("El broker MQTT no propagó el tipo_modelo_asignado.")

    enviados.clear()
    caido = adaptador.propagar_umbral(["EDGE-CAIDO"], {"id_umbral_ambiental": 1})
    assert enviados[0]["origen"] == "umbral"
    assert caido["EDGE-CAIDO"].mensaje.startswith("El broker MQTT no propagó el umbral.")


def test_adaptador_sin_broker_configurado_no_intenta(monkeypatch):
    monkeypatch.delenv("MQTT_BROKER_URL", raising=False)
    monkeypatch.delenv("MQTT_BROKER_TOKEN", raising=False)
    monkeypatch.setattr(adaptador_mod.httpx, "post", lambda *a, **k: pytest.fail("no debía llamar al broker"))
    resultado = EdgeSincronizacionMqttAdapter().propagar_tipo_modelo(["EDGE-001"], {})["EDGE-001"]
    assert resultado.estado == "SIN_INTEGRACION"
    assert "tipo_modelo_asignado" in resultado.mensaje
