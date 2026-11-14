# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-13 | Arekkazu | INC-M06-061B-G57 RF-91/92 (RFC-027): 403 al Revisor Fiscal por estado, 404 si no existe |
# | 2026-11-13 | Arekkazu | INC-M06 RF-92/93 (RFC-027): 403 también en las descargas y en el estado de resultados no aprobado; la cadena usa una línea con trazabilidad completa (#1115) |
"""INC-M06-061B-G57 / RFC-027 (RF-91 y RF-92 v1.2, CA-10), con la RLS de la API (``TEST_ROL_APP``).

El Revisor Fiscal solo lee la cadena de períodos CERRADOS y los informes APROBADOS o ARCHIVADOS. Antes
la RLS los ocultaba y respondía 404 como si no existieran; ahora es 403, y 404 solo si el id no existe.
El Contador no tiene restricción de estado."""
from __future__ import annotations

import pytest

from tests.integration.test_inc_m06_lote_2026_11_10 import _reconocido
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    _auditar_pesaje, _pesaje, contador, m06,
)

pytestmark = pytest.mark.integration
REVISOR_FISCAL = 8
INEXISTENTE = 999999999


@pytest.fixture(scope="module", autouse=True)
def _router_m06(integration_app):
    from src.financial_valuation.infrastructure.routers.m06_router import router

    integration_app.include_router(router)


def test_revisor_fiscal_recibe_403_por_estado_y_404_si_no_existe(client, db_session, m06, contador, crear_usuario_db,
                                                                 crear_auth_headers):
    uid = contador["id_usuario"]
    _, activo, periodo = _reconocido(db_session, m06, uid)
    p = periodo.id_periodo_contable
    # RF-91 (#1115): solo entra al cierre la línea con su cadena completa; la variación del pesaje auditado.
    _auditar_pesaje(db_session, activo, _pesaje(db_session, activo, "420"), uid)
    m06.procesar_eventos().execute()
    linea = next(ln.id_linea_asiento_nic41 for ln in m06.asientos.del_periodo(p) if ln.tipo_hecho == "VARIACION_VR_TB")
    revisor = crear_auth_headers(crear_usuario_db(id_rol=REVISOR_FISCAL, estado=2))

    abierta = client.get(f"/finanzas/lineas/{linea}/cadena", headers=revisor)
    assert abierta.status_code == 403, abierta.text
    assert abierta.json()["error_code"] == "ACCESO_DENEGADO" and "períodos cerrados" in abierta.json()["message"]
    assert client.get(f"/finanzas/lineas/{INEXISTENTE}/cadena", headers=revisor).status_code == 404
    assert client.get(f"/finanzas/revelaciones/{INEXISTENTE}", headers=revisor).status_code == 404

    m06.cierre().execute(p, uid, autorizar_exclusiones=True)
    [informe] = m06.reportes.listar_informes(p)
    assert informe["estado"] == "BORRADOR"

    assert client.get(f"/finanzas/lineas/{linea}/cadena", headers=revisor).status_code == 200
    borrador = client.get(f"/finanzas/revelaciones/{informe['id_informe']}", headers=revisor)
    assert borrador.status_code == 403 and "aprobados o archivados" in borrador.json()["message"]
    assert client.get(f"/finanzas/periodos/{p}/revelaciones", headers=revisor).json() == []

    m06.informe_revelaciones().resolver(informe["id_informe"], True, None, uid)
    assert client.get(f"/finanzas/revelaciones/{informe['id_informe']}", headers=revisor).status_code == 200
    assert [i["estado"] for i in client.get(f"/finanzas/periodos/{p}/revelaciones", headers=revisor).json()] == ["APROBADO"]


def test_revisor_fiscal_recibe_403_en_descargas_y_estado_de_resultados_no_aprobado(
        client, db_session, m06, contador, crear_usuario_db, crear_auth_headers):
    """QA 13-11: GET /finanzas/revelaciones/41 (BORRADOR) daba 404 al Revisor Fiscal; las descargas y el estado de
    resultados GENERADO tenían el mismo 404. El Contador sigue recibiendo 422 al descargar lo no aprobado."""
    uid = contador["id_usuario"]
    _, _, periodo = _reconocido(db_session, m06, uid)
    p = periodo.id_periodo_contable
    m06.cierre().execute(p, uid, autorizar_exclusiones=True)
    [informe] = m06.reportes.listar_informes(p)
    [estado] = m06.reportes.listar_estados(p)
    assert (informe["estado"], estado["estado"]) == ("BORRADOR", "GENERADO")
    revisor = crear_auth_headers(crear_usuario_db(id_rol=REVISOR_FISCAL, estado=2))

    for url, texto in ((f"/finanzas/revelaciones/{informe['id_informe']}/descarga", "aprobados o archivados"),
                       (f"/finanzas/estados-resultados/{estado['id_estado']}", "estados de resultados aprobados"),
                       (f"/finanzas/estados-resultados/{estado['id_estado']}/descarga", "estados de resultados aprobados")):
        r = client.get(url, headers=revisor)
        assert r.status_code == 403, (url, r.text)
        assert r.json()["error_code"] == "ACCESO_DENEGADO" and texto in r.json()["message"]
    for url in (f"/finanzas/revelaciones/{INEXISTENTE}/descarga", f"/finanzas/estados-resultados/{INEXISTENTE}",
                f"/finanzas/estados-resultados/{INEXISTENTE}/descarga"):
        assert client.get(url, headers=revisor).status_code == 404, url
    assert client.get(f"/finanzas/revelaciones/{informe['id_informe']}/descarga",
                      headers=crear_auth_headers(contador)).status_code == 422
