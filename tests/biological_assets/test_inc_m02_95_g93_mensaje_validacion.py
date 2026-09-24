"""INC-M02-95-G93: las respuestas 400 no exponen internals de Pydantic."""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers


class DbFake:
    pass


def _usuario() -> UsuarioActual:
    return UsuarioActual(
        id_usuario=7,
        id_token=1,
        id_rol=1,
        id_estado_cuenta=2,
    )


@pytest.fixture
def cliente() -> Generator[TestClient, None, None]:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_module.router)
    app.dependency_overrides[get_db] = lambda: DbFake()
    app.dependency_overrides[get_current_user] = _usuario

    rutas_objetivo = {
        '/activos-biologicos',
        '/activos-biologicos/auditoria',
        '/activos-biologicos/{id_activo}/historial',
        '/activos-biologicos/{id_activo}/indicadores',
        '/activos-biologicos/{id_activo}/datos-consolidados',
    }
    for ruta in app.routes:
        if getattr(ruta, 'path', None) not in rutas_objetivo:
            continue
        for dependencia in ruta.dependant.dependencies:
            if dependencia.call not in {get_db, get_current_user}:
                app.dependency_overrides[dependencia.call] = lambda: None

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


_DETALLES_TECNICOS_PROHIBIDOS = (
    'datosconsolidadosdto',
    'listaractivosdto',
    'consultarbitacoradto',
    'consultarhistorialdto',
    'consultarindicadoresdto',
    'validation error',
    'type=value_error',
    'input_value',
    'pydantic.dev',
)


def _assert_400_sanitizado(respuesta, mensaje: str) -> None:
    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo['error_code'] == 'PARAMETROS_INVALIDOS'
    assert cuerpo['message'] == mensaje
    assert cuerpo['fields'] == []
    texto = respuesta.text.lower()
    for detalle in _DETALLES_TECNICOS_PROHIBIDOS:
        assert detalle not in texto


def test_tc_m02_156_a_rango_invertido_expone_solo_mensaje_funcional(
    cliente: TestClient,
) -> None:
    respuesta = cliente.get(
        '/activos-biologicos/1/datos-consolidados',
        params={'fecha_inicio': '2026-09-10', 'fecha_fin': '2026-09-09'},
    )

    _assert_400_sanitizado(
        respuesta,
        'La fecha de inicio (2026-09-10) no puede ser posterior '
        'a la fecha de fin (2026-09-09).',
    )


def test_fecha_futura_conserva_regla_sin_exponer_pydantic(cliente: TestClient) -> None:
    respuesta = cliente.get(
        '/activos-biologicos/1/datos-consolidados',
        params={'fecha_inicio': '2099-01-01'},
    )

    _assert_400_sanitizado(
        respuesta,
        'La fecha de inicio (2099-01-01) no puede ser una fecha futura: '
        'los datos consolidados son sobre eventos ya ocurridos.',
    )


def test_tipo_dato_invalido_conserva_mensaje_del_dominio(cliente: TestClient) -> None:
    respuesta = cliente.get(
        '/activos-biologicos/1/datos-consolidados',
        params={'tipo_dato': 'interno'},
    )

    _assert_400_sanitizado(
        respuesta,
        'Tipo de dato inválido. Valores permitidos: estado, eventos, fases, metricas, todos.',
    )


def test_fecha_malformada_usa_contrato_estable(cliente: TestClient) -> None:
    respuesta = cliente.get(
        '/activos-biologicos/1/datos-consolidados',
        params={'fecha_inicio': '2026-13-40'},
    )

    _assert_400_sanitizado(
        respuesta,
        'Formato de fecha inválido. Use el formato YYYY-MM-DD.',
    )
    assert 'isoformat' not in respuesta.text.lower()


@pytest.mark.parametrize(
    ('ruta', 'parametros'),
    [
        (
            '/activos-biologicos/1/historial',
            {'fecha_inicio': '2026-09-10', 'fecha_fin': '2026-09-09'},
        ),
        (
            '/activos-biologicos/1/indicadores',
            {'fecha_inicio': '2026-09-10', 'fecha_fin': '2026-09-09'},
        ),
    ],
)
def test_rutas_vecinas_no_conservan_el_mismo_escape(
    cliente: TestClient,
    ruta: str,
    parametros: dict[str, str],
) -> None:
    respuesta = cliente.get(ruta, params=parametros)

    _assert_400_sanitizado(
        respuesta,
        'La fecha de inicio (2026-09-10) no puede ser posterior '
        'a la fecha de fin (2026-09-09).',
    )


def test_bitacora_no_expone_el_value_error_de_datetime(cliente: TestClient) -> None:
    respuesta = cliente.get(
        '/activos-biologicos/auditoria',
        params={'fecha_inicio': 'fecha-invalida'},
    )

    _assert_400_sanitizado(
        respuesta,
        'Formato de fecha y hora inválido. Use el formato ISO 8601.',
    )
    assert 'isoformat' not in respuesta.text.lower()


def test_listado_no_expone_el_validation_error_del_dto(cliente: TestClient) -> None:
    respuesta = cliente.get(
        '/activos-biologicos',
        params={'tipo': 'ave'},
    )

    _assert_400_sanitizado(
        respuesta,
        'Tipo inválido. Valores permitidos: INDIVIDUAL, POBLACIONAL.',
    )
