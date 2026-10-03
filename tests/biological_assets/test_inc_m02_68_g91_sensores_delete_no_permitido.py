"""INC-M02-68-G91 / TC-M02-G91 (TC-M02-222): confirma que agregar el `GET`
de consulta (issue #218) no habilita `DELETE` sobre las mismas rutas — el
historial de asociaciones sensor-activo sigue siendo append-only
(Restricción 8 del RF-49). El reporte de QA acepta `404` o `405` para este
caso (`pm.expect([404, 405]).to.include(pm.response.code)`); esta rama solo
tiene registrados GET/POST/PATCH, así que Starlette responde `405` para
ambas rutas.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router_module.router)
    return TestClient(app, raise_server_exceptions=False)


def test_delete_sobre_asociacion_puntual_no_esta_permitido() -> None:
    respuesta = _client().delete('/activos-biologicos/19/sensores/17')

    assert respuesta.status_code in (404, 405)


def test_delete_sobre_ruta_base_no_esta_permitido() -> None:
    respuesta = _client().delete('/activos-biologicos/19/sensores')

    assert respuesta.status_code in (404, 405)


def test_get_nuevo_no_afecta_el_metodo_patch_existente() -> None:
    """El GET nuevo comparte prefijo con PATCH .../sensores/{id_asociacion};
    confirma que agregar uno no desregistra el otro."""
    metodos_por_ruta: dict[str, set[str]] = {}
    for route in router_module.router.routes:
        if 'sensores' in getattr(route, 'path', ''):
            metodos_por_ruta.setdefault(route.path, set()).update(route.methods)

    assert metodos_por_ruta['/activos-biologicos/{id_activo}/sensores'] == {'GET', 'POST'}
    assert metodos_por_ruta['/activos-biologicos/{id_activo}/sensores/{id_asociacion}'] == {'PATCH'}
