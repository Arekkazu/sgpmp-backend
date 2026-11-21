# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-12 | Arekkazu | Lote M05/M06 11-12 RF-82 v1.1 (INC-M06-304-G05): el Administrador opera todo el módulo financiero |
"""RF-82 v1.1 propuesto (INC-M06-304-G05), migración 810b1e4eb4f9: el Administrador recibía 403 al
confirmar o revertir el reconocimiento. Ahora tiene cada permiso que pide el router de M06, leído del
propio router para que un endpoint nuevo no lo deje por fuera.

Los ids de la URL no existen a propósito: sin permiso sería 403; con permiso llega al caso de uso."""
from __future__ import annotations

import inspect
import re

import pytest
from sqlalchemy import text

ADMINISTRADOR = 1


@pytest.fixture(scope="module", autouse=True)
def _router_m06(integration_app):
    from src.financial_valuation.infrastructure.routers.m06_router import router

    integration_app.include_router(router)


def _pares_del_router() -> set[tuple[str, str]]:
    from src.financial_valuation.infrastructure.routers import m06_router

    fuente = inspect.getsource(m06_router)
    pares = set(re.findall(r'\("(\w+)",\s*([CRUDE])\)', fuente))  # permiso("x", R) y require_alguno_m06([("x", R)])
    assert len(pares) > 20, "no se reconocieron los permisos del router"
    return pares


def test_el_administrador_tiene_cada_permiso_del_router(db_session) -> None:
    activos = set(db_session.execute(text("""
        SELECT rec.nombre_recurso, a.codigo FROM modulo1.permisos p
        JOIN modulo1.roles r ON r.id_rol = p.id_rol
        JOIN modulo1.recursos rec ON rec.id_recurso = p.id_recurso
        JOIN modulo1.acciones a ON a.id_accion = p.id_accion
        WHERE r.nombre_rol = 'Administrador' AND p.es_activo""")).all())
    assert _pares_del_router() - activos == set()


@pytest.mark.parametrize("ruta, cuerpo", [
    ("/finanzas/reconocimientos/999999", {}),
    ("/finanzas/reconocimientos/999999/reversion", {"motivo": "Reversión de prueba de integración"}),
    ("/finanzas/periodos/999999/cierre", {}),
])
def test_el_administrador_confirma_revierte_y_cierra_sin_403(client, crear_usuario_db, crear_auth_headers,
                                                              ruta, cuerpo) -> None:
    respuesta = client.post(ruta, json=cuerpo, headers=crear_auth_headers(crear_usuario_db(id_rol=ADMINISTRADOR)))
    assert respuesta.status_code != 403, respuesta.text
