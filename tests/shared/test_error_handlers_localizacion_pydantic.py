"""INC-M02-69-G44-01 / issue #219: los errores de coerción de tipos de Pydantic
(ej. enviar `"abc"` en un campo `Decimal`) salían en inglés
("Input should be a valid decimal"), inconsistente con el resto de mensajes
de validación de dominio, que sí están en español.

De paso, se descubrió y corrige un defecto relacionado en el mismo handler:
los mensajes de los `@field_validator` propios (que sí redactan en español)
llegaban con el prefijo fijo `"Value error, "` que antepone Pydantic — nunca
reportado porque el resto del mensaje ya estaba en español y pasaba
desapercibido.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import field_validator

from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import (
    RegistrarEventoCrecimientoDTO,
)
from src.shared.base_dto import BaseDTO
from src.shared.error_handlers import register_error_handlers


class _DTOEjemplo(BaseDTO):
    valor: Decimal
    cantidad: int
    activo: bool

    @field_validator('valor')
    @classmethod
    def valor_positivo(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('El valor debe ser mayor a cero.')
        return v


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.post('/test')
    def endpoint(dto: _DTOEjemplo):
        return {'ok': True}

    return TestClient(app, raise_server_exceptions=False)


def _payload(**overrides) -> dict:
    base = {'valor': '10.5', 'cantidad': 3, 'activo': True}
    base.update(overrides)
    return base


def test_decimal_no_numerico_responde_en_espanol(client: TestClient) -> None:
    respuesta = client.post('/test', json=_payload(valor='abc'))

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo['error_code'] == 'VAL_ENTRADA'
    campo = next(f for f in cuerpo['fields'] if f['field'] == 'valor')
    assert campo['message'] == 'El valor ingresado no es un número decimal válido.'
    assert 'Input should be' not in campo['message']


def test_entero_no_numerico_responde_en_espanol(client: TestClient) -> None:
    respuesta = client.post('/test', json=_payload(cantidad='xyz'))

    campo = next(f for f in respuesta.json()['fields'] if f['field'] == 'cantidad')
    assert campo['message'] == 'El valor ingresado no es un número entero válido.'


def test_booleano_invalido_responde_en_espanol(client: TestClient) -> None:
    respuesta = client.post('/test', json=_payload(activo='tal-vez'))

    campo = next(f for f in respuesta.json()['fields'] if f['field'] == 'activo')
    assert campo['message'] == 'El valor ingresado no es un valor booleano válido (use true o false).'


def test_campo_faltante_responde_en_espanol(client: TestClient) -> None:
    respuesta = client.post('/test', json={'valor': '10.5', 'activo': True})

    campo = next(f for f in respuesta.json()['fields'] if f['field'] == 'cantidad')
    assert campo['message'] == 'Este campo es obligatorio.'


def test_validador_de_dominio_ya_no_arrastra_el_prefijo_value_error(client: TestClient) -> None:
    respuesta = client.post('/test', json=_payload(valor='-5'))

    campo = next(f for f in respuesta.json()['fields'] if f['field'] == 'valor')
    assert campo['message'] == 'El valor debe ser mayor a cero.'
    assert 'Value error' not in campo['message']


def test_tc_m02_082_valor_medicion_no_numerico_es_400_en_espanol() -> None:
    """Reproduce exactamente TC-M02-082: payload válido de RF-40 salvo por
    `valor_medicion: "abc"` contra `RegistrarEventoCrecimientoDTO`."""
    app = FastAPI()
    register_error_handlers(app)

    @app.post('/eventos/crecimiento')
    def endpoint(dto: RegistrarEventoCrecimientoDTO):
        return {'ok': True}

    client = TestClient(app, raise_server_exceptions=False)
    respuesta = client.post(
        '/eventos/crecimiento',
        json={
            'tipo_medicion': 'PESO',
            'valor_medicion': 'abc',
            'unidad_medida': 'kg',
            'fecha': '2026-09-10T08:30:00Z',
        },
    )

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo['error_code'] == 'VAL_ENTRADA'
    campo = next(f for f in cuerpo['fields'] if f['field'] == 'valor_medicion')
    assert campo['message'] == 'El valor ingresado no es un número decimal válido.'
    assert 'Input should be a valid decimal' not in campo['message']
