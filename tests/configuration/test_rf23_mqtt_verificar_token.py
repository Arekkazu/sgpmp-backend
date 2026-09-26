"""RF-23 — advertencia de arranque si MQTT_BROKER_TOKEN queda desincronizado.

`verificar_token_configurado()` es de solo lectura: nunca debe escribir en
`modulo1.credenciales_servicio`, solo loguear un warning cuando el hash del
token en el .env no coincide con el hash activo en BD.
"""
from __future__ import annotations

import hashlib
import logging

import src.shared.database  # noqa: F401  fuerza el load_dotenv() de este módulo ANTES de que
# los tests manipulen MQTT_BROKER_TOKEN -- si el primer import ocurre recién dentro de un test
# (vía `monkeypatch.setattr("src.shared.database.SessionLocal", ...)`), ese import dispara
# `load_dotenv()` y repuebla la variable justo después de haberla borrado con `delenv`.
from src.configuration.infrastructure.adapters.mqtt_http_adapter import verificar_token_configurado


class _SesionFake:
    def __init__(self, fila) -> None:
        self._fila = fila
        self.cerrada = False

    def execute(self, *args, **kwargs):  # noqa: ANN002, ANN003
        class _Resultado:
            def __init__(self, fila):
                self._fila = fila

            def first(self):
                return self._fila

        return _Resultado(self._fila)

    def close(self) -> None:
        self.cerrada = True


def test_sin_token_configurado_no_consulta_la_bd(monkeypatch) -> None:
    monkeypatch.delenv("MQTT_BROKER_TOKEN", raising=False)

    def _session_local_que_falla():  # noqa: ANN202
        raise AssertionError("no debería abrir sesión si no hay token")

    monkeypatch.setattr("src.shared.database.SessionLocal", _session_local_que_falla)

    verificar_token_configurado()  # no lanza, no llama a la BD


def test_token_coincide_con_el_hash_activo_no_advierte(monkeypatch, caplog) -> None:
    token = "token-real"
    hash_valor = hashlib.sha256(token.encode("utf-8")).hexdigest()
    monkeypatch.setenv("MQTT_BROKER_TOKEN", token)
    monkeypatch.setattr("src.shared.database.SessionLocal", lambda: _SesionFake((hash_valor,)))

    with caplog.at_level(logging.WARNING):
        verificar_token_configurado()

    assert caplog.text == ""


def test_token_desincronizado_advierte_sin_escribir(monkeypatch, caplog) -> None:
    monkeypatch.setenv("MQTT_BROKER_TOKEN", "token-viejo-en-el-env")
    monkeypatch.setattr(
        "src.shared.database.SessionLocal",
        lambda: _SesionFake(("hash-distinto-guardado-en-bd",)),
    )

    with caplog.at_level(logging.WARNING):
        verificar_token_configurado()

    assert "no coincide" in caplog.text


def test_sin_credencial_activa_advierte(monkeypatch, caplog) -> None:
    monkeypatch.setenv("MQTT_BROKER_TOKEN", "cualquier-token")
    monkeypatch.setattr("src.shared.database.SessionLocal", lambda: _SesionFake(None))

    with caplog.at_level(logging.WARNING):
        verificar_token_configurado()

    assert "no hay credencial activa" in caplog.text
