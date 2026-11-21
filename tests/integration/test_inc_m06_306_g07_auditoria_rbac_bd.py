# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-08 | destroyerban | INC-M06-306-G07 RF-82: el 403 de M06 deja un evento en auditorias_financieras |
"""INC-M06-306-G07 contra Postgres real: el intento de un rol sin permiso sobre M06 responde 403 y deja
un ``ACCESO_NO_AUTORIZADO`` en ``modulo6.auditorias_financieras`` con su hash calculado por el trigger.

Los ids de la URL no existen a propósito: van en el payload y no en las columnas con FK."""
from __future__ import annotations

import pytest
from sqlalchemy import text

ROL_SIN_PERMISO = 2  # Productor: la matriz de c4d81e6f2a95 no le da U sobre reconocimiento_inicial


@pytest.fixture(scope="module", autouse=True)
def _router_m06(integration_app):
    from src.financial_valuation.infrastructure.routers.m06_router import router

    integration_app.include_router(router)


def _contar(db) -> int:
    return db.execute(text("SELECT count(*) FROM modulo6.auditorias_financieras")).scalar_one()


@pytest.mark.parametrize("ruta, cuerpo", [
    ("/finanzas/reconocimientos/999999/reversion", {"motivo": "Reversión de prueba de integración"}),
    ("/finanzas/reconocimientos/999999", {}),
    ("/finanzas/periodos/999999/cierre", {}),
])
def test_rol_sin_permiso_recibe_403_y_queda_auditado(client, db_session, crear_usuario_db, crear_auth_headers,
                                                     ruta, cuerpo) -> None:
    usuario = crear_usuario_db(id_rol=ROL_SIN_PERMISO)
    antes = _contar(db_session)

    respuesta = client.post(ruta, json=cuerpo, headers=crear_auth_headers(usuario))

    assert respuesta.status_code == 403
    assert _contar(db_session) == antes + 1
    evento = db_session.execute(text("""
        SELECT tipo_evento::text AS tipo_evento, severidad::text AS severidad, tipo_actor::text AS tipo_actor,
               id_usuario, id_activo_biologico, datos_nuevos, hash_integridad
        FROM modulo6.auditorias_financieras ORDER BY id_auditoria_financiera DESC LIMIT 1""")).mappings().one()
    assert evento["tipo_evento"] == "ACCESO_NO_AUTORIZADO"
    assert evento["severidad"] == "WARNING"
    assert evento["tipo_actor"] == "USUARIO"
    assert evento["id_usuario"] == usuario["id_usuario"]
    assert evento["id_activo_biologico"] is None
    assert evento["datos_nuevos"]["error_code"] == "ACCESO_DENEGADO"
    assert evento["datos_nuevos"]["ruta"].startswith("/finanzas/")
    assert len(evento["hash_integridad"]) == 64 and evento["hash_integridad"] != "0" * 64


def test_sin_token_es_401_y_no_se_audita(client, db_session) -> None:
    antes = _contar(db_session)
    assert client.post("/finanzas/reconocimientos/999999/reversion", json={}).status_code == 401
    assert _contar(db_session) == antes
