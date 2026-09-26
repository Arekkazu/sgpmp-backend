"""INC-M09-21-G125-01 — Saneamiento de `serial` y `descripcion` en dispositivos IoT.

El pentest reportó que un payload con sintaxis de inyección SQL en `serial`
(`' OR '1'='1' -- {RUN_ID}`) y etiquetas `<script>` en `descripcion` eran
aceptados con HTTP 201, porque ni el value object ni el DTO validaban charset
(solo longitud). Verifica que ambos ahora rechazan esos payloads y siguen
aceptando valores legítimos.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.dto.registrar_dispositivo_iot_dto import RegistrarDispositivoIotDTO
from src.shared.errors import ValidationError

_PAYLOAD_SQLI = "' OR '1'='1' -- RUN123"
_PAYLOAD_SCRIPT = "<script>alert(1)</script>"


def test_serial_rechaza_sintaxis_de_inyeccion_sql() -> None:
    with pytest.raises(ValidationError) as exc:
        SerialDispositivo(_PAYLOAD_SQLI)
    assert exc.value.code == "SERIAL_FORMATO_INVALIDO"


def test_serial_acepta_formato_legitimo() -> None:
    assert SerialDispositivo("SN-2024_001").valor == "SN-2024_001"


def _dto_valido(**overrides) -> dict:
    base = dict(
        serial="SN-2024-001",
        descripcion="Sensor de temperatura ambiente",
        id_infraestructura=1,
        id_tipo_dispositivo=1,
    )
    base.update(overrides)
    return base


def test_descripcion_rechaza_etiquetas_de_script() -> None:
    with pytest.raises(PydanticValidationError):
        RegistrarDispositivoIotDTO(**_dto_valido(descripcion=_PAYLOAD_SCRIPT))


def test_descripcion_acepta_texto_legitimo() -> None:
    dto = RegistrarDispositivoIotDTO(**_dto_valido(descripcion="Sensor - exterior (invernadero A)"))
    assert dto.descripcion == "Sensor - exterior (invernadero A)"


if __name__ == "__main__":
    test_serial_rechaza_sintaxis_de_inyeccion_sql()
    test_serial_acepta_formato_legitimo()
    test_descripcion_rechaza_etiquetas_de_script()
    test_descripcion_acepta_texto_legitimo()
    print("OK")
