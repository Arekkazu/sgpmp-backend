"""TC-M02-65-G94 (#495, RF-50): el 429 dice cuándo reintentar.

El limitador ya cortaba con 429 ``LIMITE_TASA_EXCEDIDO``, pero sin cabeceras de
cuota el consumidor (M04, M06) no sabía cuándo volver a intentar. Ahora el 429
lleva ``Retry-After`` y ``RateLimit-Limit/Remaining/Reset``, calculados con la
ventana configurada, sin cambiar el límite ni la clave del contador.
"""
from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.infrastructure.routers.activo_biologico_router import (
    _LIMITE_DATOS_CONSOLIDADOS,
)
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import TooManyRequestsError
from src.shared.rate_limit import rate_limit


def test_rf50_429_informa_la_ventana_de_100_por_60_segundos() -> None:
    for _ in range(100):
        _LIMITE_DATOS_CONSOLIDADOS(request=None, identificador="modulo:modulo4-g94")

    with pytest.raises(TooManyRequestsError) as exc:
        _LIMITE_DATOS_CONSOLIDADOS(request=None, identificador="modulo:modulo4-g94")

    cabeceras = exc.value.headers
    assert cabeceras["RateLimit-Limit"] == "100"
    assert cabeceras["RateLimit-Remaining"] == "0"
    assert 1 <= int(cabeceras["Retry-After"]) <= 60
    assert cabeceras["RateLimit-Reset"] == cabeceras["Retry-After"]
    # Otro módulo conserva su propio contador (aislamiento M04/M06 intacto).
    _LIMITE_DATOS_CONSOLIDADOS(request=None, identificador="modulo:modulo6-g94")


def test_el_handler_global_envia_las_cabeceras_en_la_respuesta_http() -> None:
    app = FastAPI()
    register_error_handlers(app)
    limite = rate_limit(1, 60, alcance="test_g94_http", clave=lambda: "cliente")

    @app.get("/recurso", dependencies=[Depends(limite)])
    def recurso() -> dict:
        return {"ok": True}

    cliente = TestClient(app)
    assert cliente.get("/recurso").status_code == 200

    respuesta = cliente.get("/recurso")
    assert respuesta.status_code == 429
    assert respuesta.json()["error_code"] == "LIMITE_TASA_EXCEDIDO"
    assert 1 <= int(respuesta.headers["Retry-After"]) <= 60
    assert respuesta.headers["RateLimit-Limit"] == "1"
    assert respuesta.headers["RateLimit-Remaining"] == "0"
    assert respuesta.headers["RateLimit-Reset"] == respuesta.headers["Retry-After"]
