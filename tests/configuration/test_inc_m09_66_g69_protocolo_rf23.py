"""INC-M09-66-G69 (#492, RF-23): un campo fuera de la ficha ya no se ignora.

`protocolo=LoRaWAN` y `protocolo=PROTOCOLO_INEXISTENTE` respondían 202 igual
que sin el campo: Pydantic descartaba en silencio cualquier clave desconocida.
RF-23 solo define `frecuencia_captura` e `intervalo_transmision` (más el estado
del dispositivo, que tiene su propio endpoint); LoRaWAN es la red entre el
dispositivo y su gateway, el backend solo publica por MQTT. Un campo ajeno
ahora es 400 y señala el campo.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.shared.error_handlers import register_error_handlers


@pytest.fixture
def cliente() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/configurar", status_code=202)
    def configurar(dto: ConfigurarRemotamenteDTO) -> dict:
        return dto.model_dump()

    return TestClient(app)


@pytest.mark.parametrize("protocolo", ["LoRaWAN", "PROTOCOLO_INEXISTENTE"])
def test_protocolo_no_definido_en_rf23_responde_400(cliente: TestClient, protocolo: str) -> None:
    respuesta = cliente.post(
        "/configurar",
        json={"frecuencia_captura": 5, "intervalo_transmision": 10, "protocolo": protocolo},
    )

    assert respuesta.status_code == 400
    campos = {f["field"]: f["message"] for f in respuesta.json()["fields"]}
    assert campos["protocolo"] == "Este campo no está permitido en esta solicitud."


def test_solo_los_parametros_de_rf23_siguen_aceptandose(cliente: TestClient) -> None:
    respuesta = cliente.post("/configurar", json={"frecuencia_captura": 5, "intervalo_transmision": 10})

    assert respuesta.status_code == 202
    assert respuesta.json() == {"frecuencia_captura": 5, "intervalo_transmision": 10}
