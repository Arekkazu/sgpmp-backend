# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: URL del motor IA en cualquier dominio y ventana del activo |
# | 2026-10-31 | Arekkazu | RF-17/RF-66 C3: el paquete lleva los rangos RF-17 de la especie   |
"""RF-66 / IA-1 v1: la URL del motor es una URL base en cualquier dominio, cada paquete viaja
con la ventana de su activo y la cola de reenvío usa el motor real cuando hay URL."""
from __future__ import annotations

import json
import ssl
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.domain.repositories.ventana_inferencia_port import VentanaActivo
from src.telemetry.infrastructure.adapters import motor_inferencia_http_adapter as http
from src.telemetry.infrastructure.workers import reenvio_inferencia_worker as worker


@pytest.mark.parametrize(("configurada", "efectiva"), [
    ("https://api.inmero.co/model-ia-test", "https://api.inmero.co/model-ia-test/v1/paquetes"),
    ("https://motor.arekkazu.top/", "https://motor.arekkazu.top/v1/paquetes"),
    ("https://spi.sgpmp.co:8443/ia", "https://spi.sgpmp.co:8443/ia/v1/paquetes"),
    ("https://10-0-0-5.sslip.io", "https://10-0-0-5.sslip.io/v1/paquetes"),
    (" https://api.inmero.co/model-ia/v1/paquetes ", "https://api.inmero.co/model-ia/v1/paquetes"),
    ("https://api.inmero.co/model-ia/v1/paquetes/", "https://api.inmero.co/model-ia/v1/paquetes"),
])
def test_url_base_en_cualquier_dominio(configurada, efectiva):
    assert http.url_paquetes(configurada) == efectiva


def test_desde_entorno_usa_la_url_base(monkeypatch):
    monkeypatch.setenv("IOT_INFERENCIA_M04_URL", "https://motor.arekkazu.top")
    monkeypatch.delenv("IOT_INFERENCIA_CA_FILE", raising=False)
    monkeypatch.delenv("IOT_INFERENCIA_TLS_MIN", raising=False)
    assert http.motor_inferencia_http_desde_entorno().url == "https://motor.arekkazu.top/v1/paquetes"


def test_url_sin_dominio_no_se_usa(monkeypatch):
    monkeypatch.setenv("IOT_INFERENCIA_M04_URL", "https:///v1/paquetes")
    assert http.motor_inferencia_http_desde_entorno() is None


def _paquete(id_paquete: int, sensor: int = 7) -> PaqueteInferencia:
    return PaqueteInferencia(id_sensor=sensor, id_dispositivo_iot=3, id_evento_edge_computing=11,
                             tipo_variable="TEMP_CORPORAL", valor_numerico=Decimal("39.8"),
                             estado_calidad="VALIDO", fecha_envio=datetime.now(timezone.utc),
                             estado_paquete="PENDIENTE", intento_envios=0, contexto_incompleto=False,
                             id_paquetes_inferencia=id_paquete)


def test_cada_paquete_lleva_el_activo_y_su_ventana():
    lecturas = [{"timestamp": "2026-10-30T10:00:00+00:00", "variable": "frecuencia_cardiaca",
                 "valor": 71.0, "apto_para_ia": True}]
    ventanas = Mock()
    rangos = {"temperatura_corporal": {"sano": [38.0, 39.5], "plausible": [35.0, 43.0]}}
    ventanas.ventanas.return_value = {1: VentanaActivo(885, lecturas, rangos), 2: VentanaActivo(None, [])}
    cliente = http.MotorInferenciaHttpAdapter("https://motor.arekkazu.top/v1/paquetes",
                                              ssl.create_default_context(), ventanas=ventanas)
    cuerpos = json.loads(json.dumps(cliente._cuerpos([_paquete(1), _paquete(2, sensor=9)]), default=str))
    assert (cuerpos[0]["id_activo_biologico"], cuerpos[0]["lecturas"]) == (885, lecturas)
    assert cuerpos[0]["rangos_especie"] == rangos
    # Sin umbral RF-17 no se manda el campo: el motor usa sus valores propios.
    assert (cuerpos[1]["id_activo_biologico"], cuerpos[1]["lecturas"]) == (None, [])
    assert "rangos_especie" not in cuerpos[1]
    assert cuerpos[0]["tipo_variable"] == "TEMP_CORPORAL"  # el paquete de RF-56 no cambia


def test_sin_puerto_de_ventanas_el_cuerpo_es_el_de_siempre():
    cliente = http.MotorInferenciaHttpAdapter("https://m04.interno/v1/paquetes", ssl.create_default_context())
    (cuerpo,) = cliente._cuerpos([_paquete(1)])
    assert "lecturas" not in cuerpo and "id_activo_biologico" not in cuerpo


@pytest.mark.parametrize(("url", "tipo_esperado"), [
    ("https://motor.arekkazu.top", "MotorInferenciaHttpAdapter"),
    ("", "MotorInferenciaStubAdapter"),
])
def test_la_cola_de_reenvio_usa_el_motor_real_si_hay_url(monkeypatch, url, tipo_esperado):
    monkeypatch.setenv("IOT_INFERENCIA_M04_URL", url)
    monkeypatch.delenv("IOT_INFERENCIA_CA_FILE", raising=False)
    monkeypatch.setattr(worker, "sesion_sistema", Mock)
    caso = Mock()
    monkeypatch.setattr(worker, "DrenarPaquetesPendientesUseCase", caso)
    worker.drenar_una_vez()
    assert type(caso.call_args.kwargs["motor_inferencia_port"]).__name__ == tipo_esperado
