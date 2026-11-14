# | Fecha      | Nombre                   | Que se hizo                                                              |
# |------------|--------------------------|--------------------------------------------------------------------------|
# | 2026-10-30 | Juan Sebastian Gutierrez | RF-73 TC-M04-G092: Pytest honesto (285/286 fail, 287 skip OBS, 288 fix) |
"""
TC-M04-G092 — Trazabilidad end-to-end con correlacion_id en GET /prediccion/auditoria (httpx).
Subcasos:
  - TC-M04-285: Trazabilidad intra-M04 (inferencia -> alerta -> retroalimentacion, >= 3 eventos)
  - TC-M04-286: Cadena causal completa enlazada por id_referencia
  - TC-M04-287: Correlacion transversal multisistema M03 + M04 + M06 (OBS-M04-G092-01)
  - TC-M04-288: Contract test del filtro correlacion_id (PR #785 / commit b440932a)

Reglas arquitecturales:
  - P1'=B: httpx.Client contra $env:BACKEND o $env:TEST_BASE_URL (backend desplegado).
  - P2=A: 1 login + consultas + teardown por test. DEF-04 respetado.
  - L13/L18: Asserts estrictos y honestos. Fallas legitimas se asertan como falla (sin enmascarar).
  - L17: HTTP directo con Bearer JWT, sin queries SQL directas afectadas por RLS.
  - D1=B: Formato ErrorResponse (HTTP 422, VAL_ENTRADA, fields), no detail[] nativo de FastAPI.
"""
import collections
import os
import uuid

import httpx
import pytest


BASE_URL = (os.environ.get("BACKEND") or os.environ.get("TEST_BASE_URL", "https://www.api.inmero.co/api-sgpmp-test")).rstrip("/")
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "administador.dev@gmail.com")
SANDBOX_SECRET = os.environ["TEST_SANDBOX_SECRET"]


def _new_run_id() -> str:
    return f"pytest-g092-{uuid.uuid4()}"


def _sandbox_headers(run_id: str) -> dict:
    return {
        "X-Test-Run-Id": run_id,
        "X-Sandbox-Secret": SANDBOX_SECRET,
    }


def _login(client: httpx.Client, run_id: str) -> str:
    r = client.post(
        "/sesiones/",
        headers=_sandbox_headers(run_id),
        json={
            "correo_electronico": ADMIN_EMAIL,
            "contrasena": os.environ["TEST_ADMIN_PASSWORD"],
        },
    )
    assert r.status_code == 200, (
        f"Login {r.status_code}: {r.text[:300]}"
    )
    body = r.json()
    assert "token" in body, f"Sin token: {list(body.keys())}"
    return body["token"]


def _auth(token: str, run_id: str) -> dict:
    h = _sandbox_headers(run_id)
    h["Authorization"] = f"Bearer {token}"
    return h


def _teardown(client: httpx.Client, run_id: str) -> None:
    r = client.delete(
        f"/test-control/runs/{run_id}",
        headers={"X-Sandbox-Secret": SANDBOX_SECRET},
    )
    assert r.status_code == 200, (
        f"Teardown {r.status_code}: {r.text[:300]}"
    )


@pytest.fixture
def client():
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as c:
        yield c


def test_tc_m04_285_trazabilidad_intra_m04(client):
    """
    TC-M04-285: Trazabilidad dentro de M04 (inferencia -> alerta -> retroalimentacion).
    Valida la existencia de al menos una cadena con >= 3 eventos compartiendo el mismo correlacion_id.
    Bloqueador confirmado: RF-66 (Motor Inferencia) no implementado en TEST -> INC-M04-151-G081.
    """
    run_id = _new_run_id()
    try:
        token = _login(client, run_id)
        r = client.get(
            "/prediccion/auditoria",
            headers=_auth(token, run_id),
            params={"por_pagina": 200},
        )
        assert r.status_code == 200, f"GET: {r.status_code}: {r.text[:300]}"
        body = r.json()
        items = body.get("items", [])

        # Contar eventos por correlacion_id
        counts = collections.Counter(
            item.get("correlacion_id")
            for item in items
            if item.get("correlacion_id")
        )
        cadenas_completas = [cid for cid, count in counts.items() if count >= 3]

        assert len(cadenas_completas) > 0, (
            "RF-66 no implementado: 0 cadenas con >= 3 eventos en TEST. Ver INC-M04-151-G081."
        )
    finally:
        _teardown(client, run_id)


def test_tc_m04_286_cadena_causal_id_referencia(client):
    """
    TC-M04-286: Cadena causal completa RF-56 -> RF-66 -> RF-57 -> RF-72 vinculada con id_referencia.
    Valida encadenamiento causal entre eventos de prediccion.
    Bloqueador confirmado: Productores y enlaces causales no implementados -> INC-M04-151-G081.
    """
    run_id = _new_run_id()
    try:
        token = _login(client, run_id)
        r = client.get(
            "/prediccion/auditoria",
            headers=_auth(token, run_id),
            params={"por_pagina": 200},
        )
        assert r.status_code == 200, f"GET: {r.status_code}: {r.text[:300]}"
        body = r.json()
        items = body.get("items", [])

        # Buscar eventos que tengan id_referencia apuntando a otro evento de la coleccion
        ids_presentes = {item.get("id") for item in items if item.get("id")}
        enlaces_causales = [
            item for item in items
            if item.get("id_referencia") and item.get("id_referencia") in ids_presentes
        ]

        assert len(enlaces_causales) > 0, (
            "Cadena causal no disponible: productores no implementados. Ver INC-M04-151-G081."
        )
    finally:
        _teardown(client, run_id)


def test_tc_m04_287_correlacion_transversal_multisistema(client):
    """
    TC-M04-287: Correlacion transversal M03 + M04 + M06 (IoT -> IA -> Contabilidad).
    Requiere que modulo3.bitacora_auditoria_iot y modulo6.auditorias_financieras
    propaguen y emitan correlacion_id.
    Estado: OBS-M04-G092-01 (Ambiguedad documentada en la ficha; esquemas de M03 y M06
    no incluyen columna correlacion_id).
    """
    pytest.skip(
        "OBS-M04-G092-01: M03/M06 no emiten correlacion_id. "
        "Requiere alineacion de esquema. NO es defecto del fix #785."
    )


def test_tc_m04_288_filtro_correlacion_id_contrato(client):
    """
    TC-M04-288: Contract test del filtro correlacion_id en GET /prediccion/auditoria.
    Verifica de manera exhaustiva el fix de PR #785 (commit b440932a):
      a) Filtro por UUID existente -> HTTP 200, items pertenecen exclusivamente a ese UUID.
      b) Filtro por UUID inexistente -> HTTP 200, items vacios, total = 0.
      c) Filtro por UUID malformado -> HTTP 422, ErrorResponse con VAL_ENTRADA y fields.
      d) Sin filtro -> HTTP 200, retorna eventos con correlacion_id variados.
    """
    run_id = _new_run_id()
    try:
        token = _login(client, run_id)
        auth_headers = _auth(token, run_id)

        # 1. Obtener un correlacion_id existente en TEST
        r_base = client.get(
            "/prediccion/auditoria",
            headers=auth_headers,
            params={"por_pagina": 10},
        )
        assert r_base.status_code == 200, f"Error consulta base: {r_base.text[:300]}"
        base_items = r_base.json().get("items", [])
        assert len(base_items) >= 2, "Se requieren al menos 2 eventos para verificar filtros"

        sample_cid = base_items[0].get("correlacion_id")
        assert sample_cid is not None, "El evento de auditoria no posee correlacion_id"
        # Validar formato UUID
        uuid.UUID(str(sample_cid))

        # a) Filtro con UUID existente
        r_filtro = client.get(
            "/prediccion/auditoria",
            headers=auth_headers,
            params={"correlacion_id": sample_cid},
        )
        assert r_filtro.status_code == 200, f"Filtro existente status {r_filtro.status_code}"
        body_filtro = r_filtro.json()
        assert len(body_filtro["items"]) >= 1, "Filtro no retorno el registro esperado"
        for it in body_filtro["items"]:
            assert it["correlacion_id"] == sample_cid, (
                f"Item con correlacion_id inesperado: {it['correlacion_id']} != {sample_cid}"
            )

        # b) Filtro con UUID inexistente
        nil_uuid = "00000000-0000-0000-0000-000000000000"
        r_inexistente = client.get(
            "/prediccion/auditoria",
            headers=auth_headers,
            params={"correlacion_id": nil_uuid},
        )
        assert r_inexistente.status_code == 200, f"Filtro inexistente status {r_inexistente.status_code}"
        body_inexistente = r_inexistente.json()
        assert body_inexistente["items"] == [], (
            f"Esperado items=[], obtenido {body_inexistente['items']}"
        )
        assert body_inexistente["total"] == 0, (
            f"Esperado total=0, obtenido {body_inexistente['total']}"
        )

        # c) Filtro con UUID malformado -> HTTP 422 ErrorResponse
        r_malformado = client.get(
            "/prediccion/auditoria",
            headers=auth_headers,
            params={"correlacion_id": "uuid-invalido-123"},
        )
        assert r_malformado.status_code == 422, (
            f"Esperado 422 para UUID malformado, obtenido {r_malformado.status_code}: {r_malformado.text}"
        )
        body_err = r_malformado.json()
        assert body_err.get("error_code") == "VAL_ENTRADA", (
            f"Esperado error_code='VAL_ENTRADA', obtenido {body_err.get('error_code')}"
        )
        assert "message" in body_err and body_err["message"], (
            f"Falta mensaje en ErrorResponse: {body_err}"
        )
        assert "fields" in body_err and isinstance(body_err["fields"], list), (
            f"Falta fields lista en ErrorResponse: {body_err}"
        )
        assert any(f.get("field") == "correlacion_id" for f in body_err["fields"]), (
            f"fields no contiene parametro correlacion_id: {body_err['fields']}"
        )
        assert "detail" not in body_err, (
            "ErrorResponse no debe contener detail[] nativo de FastAPI"
        )

        # d) Sin filtro de correlacion_id: registros con diversidad de correlacion_id
        r_unfiltered = client.get(
            "/prediccion/auditoria",
            headers=auth_headers,
            params={"por_pagina": 10},
        )
        assert r_unfiltered.status_code == 200
        unfiltered_items = r_unfiltered.json().get("items", [])
        cids = {it.get("correlacion_id") for it in unfiltered_items if it.get("correlacion_id")}
        assert len(cids) >= 2, (
            f"Se esperaban al menos 2 correlacion_id distintos sin filtro, obtenidos: {len(cids)}"
        )
    finally:
        _teardown(client, run_id)

