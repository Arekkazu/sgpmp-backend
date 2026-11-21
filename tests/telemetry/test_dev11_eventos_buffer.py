# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-129-G27 RF-54/60/63: preservar los casos previos y actualizar el catálogo inválido tras ampliar D10. |
"""DEV-11 (D10, AIOT-DEV-03): el aviso EVENTO_BUFFER que reenvía el broker se convierte
en una alerta técnica de RF-60 y en un evento de auditoría de RF-63."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from main import app
from src.shared.database import get_db_sistema
from src.shared.errors import NotFoundError
from src.telemetry.application.use_cases.infraestructura.registrar_evento_buffer_use_case import (
    RegistrarEventoBufferUseCase,
)
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, EntidadAfectadaTipo
from src.telemetry.domain.repositories.dispositivo_port import DispositivoHeartbeatInfo
from src.telemetry.infrastructure.dto.evento_buffer_dto import RecibirEventoBufferDTO
from src.telemetry.infrastructure.routers import infraestructura_iot_router

TOKEN = "token-de-prueba"
GATEWAY = DispositivoHeartbeatInfo(id_dispositivo_iot=7, id_infraestructura=3, es_activo=True)


def _cuerpo(**extra) -> dict:
    return {
        "serial": "GW-001",
        "evento": "BUFFER_OVERFLOW",
        "porcentaje_ocupacion": 100,
        "politica_aplicada": "POLITICA_RECHAZO",
        "cantidad_datos_afectados": 12,
        "timestamp_evento": "2026-10-17T10:00:00-05:00",
        **extra,
    }


class _Alertas:
    def __init__(self, abierta=None):
        self.guardadas, self.abierta, self.dedup = [], abierta, []

    def bloquear_dispositivo(self, identificador):
        pass

    def buscar_tecnica_abierta(self, id_dispositivo_ioit, tipo_variable):
        return self.abierta

    def actualizar_deduplicacion(self, id_alerta, ultima_ocurrencia, nueva_severidad=None):
        self.dedup.append((id_alerta, ultima_ocurrencia))

    def guardar(self, alerta):
        alerta.id_alerta = 41
        self.guardadas.append(alerta)
        return alerta


def _uc(alertas=None, dispositivo=GATEWAY):
    puerto = Mock()
    puerto.obtener_por_serial.return_value = dispositivo
    auditoria = Mock()
    db = Mock()
    uc = RegistrarEventoBufferUseCase(db=db, dispositivo_port=puerto, alerta_repo=alertas or _Alertas(),
                                      auditoria_repo=auditoria)
    return uc, db, auditoria


@pytest.mark.parametrize("evento, severidad", [("BUFFER_OVERFLOW", "MODERADO"),
                                                ("BUFFER_DATA_CORRUPTION", "CRITICO")])
def test_crea_alerta_tecnica_del_gateway_y_evento_rf63(evento, severidad):
    alertas = _Alertas()
    uc, db, auditoria = _uc(alertas)

    r = uc.execute(RecibirEventoBufferDTO(**_cuerpo(evento=evento)))

    (alerta,) = alertas.guardadas
    assert (alerta.tipo_alerta, alerta.tipo_variable, alerta.severidad) == ("TECNICA", evento, severidad)
    assert (alerta.id_dispositivo_ioit, alerta.id_infraestructura, alerta.origen_evento) == (7, 3, "EDGE")
    assert alerta.fecha_evento == datetime(2026, 10, 17, 15, 0, tzinfo=timezone.utc)
    assert alerta.metadato_evento["cantidad_datos_afectados"] == 12
    assert (r.id_alerta, r.es_duplicado, r.severidad) == (41, False, severidad)
    db.commit.assert_called()

    evento_rf63 = auditoria.registrar.call_args.args[0]
    assert evento_rf63.tipo_evento == evento
    assert evento_rf63.componente_origen == ComponenteOrigen.RF54
    assert evento_rf63.entidad_afectada_tipo == EntidadAfectadaTipo.BUFFER
    assert evento_rf63.entidad_afectada_id == "7"
    assert evento_rf63.accion_detallada["id_alerta"] == 41
    assert evento_rf63.hash_integridad


def test_con_alerta_abierta_del_mismo_tipo_solo_cuenta_la_ocurrencia():
    abierta = Mock(id_alerta=9, severidad="MODERADO")
    alertas = _Alertas(abierta=abierta)
    uc, _, auditoria = _uc(alertas)

    r = uc.execute(RecibirEventoBufferDTO(**_cuerpo()))

    assert alertas.guardadas == []
    assert alertas.dedup == [(9, datetime(2026, 10, 17, 15, 0, tzinfo=timezone.utc))]
    assert (r.id_alerta, r.es_duplicado) == (9, True)
    assert auditoria.registrar.call_args.args[0].accion_detallada["es_duplicado"] is True


def test_serial_desconocido_es_404_y_no_crea_nada():
    alertas = _Alertas()
    uc, db, auditoria = _uc(alertas, dispositivo=None)
    with pytest.raises(NotFoundError) as exc:
        uc.execute(RecibirEventoBufferDTO(**_cuerpo(serial="NO-EXISTE")))
    assert exc.value.code == "DISPOSITIVO_NO_ENCONTRADO"
    assert alertas.guardadas == []
    auditoria.registrar.assert_not_called()


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("BROKER_SERVICE_TOKEN", TOKEN)
    puerto = Mock()
    puerto.obtener_por_serial.return_value = GATEWAY
    alertas = _Alertas()
    monkeypatch.setattr(infraestructura_iot_router, "DispositivoM09Adapter", lambda db: puerto)
    monkeypatch.setattr(infraestructura_iot_router, "SqlAlchemyAlertaRepository", lambda db: alertas)
    monkeypatch.setattr(infraestructura_iot_router, "SqlAlchemyBitacoraAuditoriaIotRepository", lambda db: Mock())
    app.dependency_overrides[get_db_sistema] = lambda: Mock()
    yield TestClient(app)
    app.dependency_overrides.pop(get_db_sistema, None)


def test_http_201_con_token(cliente):
    r = cliente.post("/iot/eventos-buffer", json=_cuerpo(), headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 201, r.text
    assert r.json() == {"id_alerta": 41, "es_duplicado": False,
                        "tipo_alerta_tecnica": "BUFFER_OVERFLOW", "severidad": "MODERADO"}


def test_http_401_sin_token(cliente):
    assert cliente.post("/iot/eventos-buffer", json=_cuerpo()).status_code == 401


@pytest.mark.parametrize("cambio", [{"evento": "BUFFER_EVENTO_DESCONOCIDO"}, {"porcentaje_ocupacion": 120},
                                    {"cantidad_datos_afectados": -1}])
def test_http_rechaza_sobre_invalido(cliente, cambio):
    r = cliente.post("/iot/eventos-buffer", json=_cuerpo(**cambio), headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code in (400, 422), r.text
