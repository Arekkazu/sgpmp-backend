# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M03-136-G02 RF-53: checksum verificado contra el contenido |
"""RF-53 Fase 1 (#850): una lectura alterada con el checksum original se rechaza."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import (
    IngerirTelemetriaBatchDTO,
    IngerirTelemetriaDTO,
    checksum_lectura,
)

# Mismo cálculo que la colección TC-M03-G02 (JSON.stringify con claves ordenadas, CryptoJS.SHA256).
LECTURA = ('{"device_id":720,"sensor_id":1052,"tipo_variable":"TEMPERATURA_AMBIENTAL","valor":25.0,'
           '"unidad":"°C","timestamp_captura":"2026-10-29T15:00:00.000Z","serial":"SER-720","origen":"TIEMPO_REAL"}')
CHECKSUM_JS = "96788b49d793a581f06abe6690decb628a61fa95d8b582048e4f4ee33696dcc5"


def _lectura(**cambios):
    return json.loads(LECTURA) | {"checksum": CHECKSUM_JS} | cambios


def test_checksum_coincide_con_el_de_javascript():
    assert checksum_lectura(json.loads(LECTURA)) == CHECKSUM_JS
    assert IngerirTelemetriaDTO.model_validate(_lectura()).valor == 25
    assert IngerirTelemetriaDTO.model_validate(_lectura(checksum=CHECKSUM_JS.upper()))


@pytest.mark.parametrize("cambios", [dict(valor=26.0), dict(sensor_id=1053), dict(checksum="abc"), dict(checksum=123)])
def test_lectura_alterada_se_rechaza(cambios):
    with pytest.raises(ValidationError) as exc:
        IngerirTelemetriaDTO.model_validate(_lectura(**cambios))
    assert "checksum" in str(exc.value)


def test_sin_checksum_no_se_verifica():
    assert IngerirTelemetriaDTO.model_validate(json.loads(LECTURA) | {"valor": 26.0}).valor == 26


def test_lote_rechaza_el_registro_alterado():
    with pytest.raises(ValidationError) as exc:
        IngerirTelemetriaBatchDTO.model_validate({"registros": [_lectura(), _lectura(valor=26.0)]})
    assert exc.value.errors()[0]["loc"][:2] == ("registros", 1)
