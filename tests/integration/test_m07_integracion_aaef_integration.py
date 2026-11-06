# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-95..102 / RF-AE01: integración AAEF de punta a punta contra PostgreSQL |
"""M07 de punta a punta contra Postgres real (migración 94b14a6931d6).

M06 real (reconocimiento, factura de proveedor repartida entre dos activos, cierre del período) →
administración de M07 (cliente AgroFusion con su secreto, anexo, contrato 3.0) → lo que hace
AgroFusion (pide el token con client_id/client_secret/email y consulta el documento AAEF con Bearer)
→ rechazos de RF-AE01 y auditoría inmutable de RF-102."""
from __future__ import annotations

import hashlib
import os
from collections.abc import Generator
from datetime import timedelta
from decimal import Decimal as D

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.accounting_integration.domain.services.esquema_agrofusion import AccountingConsultResponse
from src.financial_valuation.application.use_cases.costos.registrar_costo_use_case import SolicitudCosto
from tests.integration.conftest import JWT_SECRET_INTEGRACION, _importar_modelos_identity_access
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401  (m06 es fixture)
    HOY,
    NIT,
    _activo,
    _configurar,
    _finca,
    _matriz,
    _pesaje,
    _precio,
    m06,
)

pytestmark = pytest.mark.integration

SECRETO = "secreto-de-prueba-agrofusion-0001"
URL = f"/integracion/aaef/productores/{NIT}"


@pytest.fixture
def cliente_http(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    _importar_modelos_identity_access()
    from src.accounting_integration.infrastructure import factoria
    from src.accounting_integration.infrastructure.routers.m07_router import router as m07_router
    from src.identity_access.infrastructure.routers.agrofusion_integration_router import router as m2m_router
    from src.identity_access.infrastructure.routers.usuarios_routers import router as usuarios_router
    from src.shared import jwt as jwt_module
    from src.shared import rate_limit
    from src.shared.database import declarar_identidad_sistema, get_db
    from src.shared.error_handlers import register_error_handlers

    def sesion_aparte() -> Session:
        sesion = Session(bind=db_session.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint")
        declarar_identidad_sistema(sesion)
        return sesion

    rol_app = os.getenv("TEST_ROL_APP")  # con sgpmp_app los requests quedan sujetos a RLS, como en TEST

    def override_get_db():
        db_session.info.clear()
        if rol_app:
            db_session.execute(text(f'SET LOCAL ROLE "{rol_app}"'))
        try:
            yield db_session
        finally:
            if rol_app:
                db_session.execute(text("RESET ROLE"))

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(factoria, "sesion_sistema", sesion_aparte)
    rate_limit._llamadas.clear()
    app = FastAPI()
    register_error_handlers(app)
    for router in (m07_router, m2m_router, usuarios_router):
        app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False, client=("203.0.113.10", 50000)) as cliente:
        yield cliente


def _sembrar_m06_cerrado(db: Session, m06, uid: int) -> tuple[dict, int]:
    """Titular con un período cerrado que tiene una factura de proveedor repartida en dos activos."""
    especie = 2
    finca = _finca(db, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    m06.guardar_asignacion().execute("CONSUMO_INSUMO", "UNICO", None, "VETERINARIO", "5135", "1405", uid)
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=5))
    activos = []
    for _ in range(2):
        activo = _activo(db, finca, uid, especie=especie, origen="nacimiento", costo=None)
        _pesaje(db, activo, "100", -timedelta(minutes=1))
        m06.confirmar_reconocimiento().execute(activo, uid)
        activos.append(activo)
    m06.registrar_costo().execute(SolicitudCosto(
        subtipo_costo="VETERINARIO", origen_costo="SERVICIO_TERCERO", monto_costo=D("100.01"), fecha_costo=HOY,
        activos_reparto=activos, tercero_nit="800555111", tercero_dv="1", tercero_razon_social="Veterinaria SAS",
        factura_prefijo="FE", factura_numero="88231", fecha_factura=HOY, fecha_vencimiento_factura=HOY + timedelta(days=30)), uid)
    periodo = m06.periodos.que_contiene(NIT, HOY)
    assert m06.cierre().execute(periodo.id_periodo_contable, uid)["estado"] == "CERRADO"
    return {"desde": periodo.fecha_inicio.isoformat(), "hasta": periodo.fecha_fin.isoformat()}, finca


def _preparar_m07(cli: TestClient, admin: dict, contador: dict) -> int:
    """Lo que hace el Administrador (y el Contador) antes de la primera consulta de AgroFusion."""
    r = cli.post("/integracion/clientes", headers=admin, json={
        "codigo": "AGROFUSION", "nombre": "AgroFusion", "identificador_publico": "agrofusion",
        "fecha_vencimiento": (HOY + timedelta(days=365)).isoformat(), "client_secret": SECRETO,
        "canales": [{"canal": "IDENTIDAD_M2M"}, {"canal": "CONSULTA_AAEF", "limite_por_minuto": 30}]})
    assert r.status_code == 201, r.text
    assert r.json()["client_secret"] == SECRETO and "hash" not in r.text
    id_cliente = r.json()["id_cliente_externo"]
    r = cli.post("/integracion/anexos", headers=admin, json={
        "codigo_anexo": "AAEF-ANEXO-3.0", "version_anexo": "3.0", "ruta_documento": "docs/integracion/anexo_aaef_v3.0.md",
        "sha256_documento": hashlib.sha256(b"anexo").hexdigest()})
    assert r.status_code == 201, r.text
    id_anexo = r.json()["id_mapeo_anexo_aaef"]
    assert cli.post(f"/integracion/anexos/{id_anexo}/revision", headers=admin).status_code == 403  # solo el Contador
    r = cli.post(f"/integracion/anexos/{id_anexo}/revision", headers=contador)
    assert r.status_code == 200 and r.json()["estado"] == "EN_REVISION", r.text
    r = cli.post("/integracion/contratos", headers=admin, json={
        "contrato_version": "3.0", "tipo_cambio": "MAJOR", "fecha_vigencia": HOY.isoformat(),
        "id_mapeo_anexo_aaef": id_anexo, "mapeadores": ["COMPRAS"]})
    assert r.status_code == 201 and r.json()["estado"] == "PENDIENTE", r.text
    id_contrato = r.json()["id_version_contrato_aaef"]
    apagado = cli.post("/integracion/contratos", headers=admin, json={  # el 06 sigue apagado (SIGCON no lo recibe)
        "contrato_version": "3.1", "tipo_cambio": "MINOR", "fecha_vigencia": HOY.isoformat(),
        "id_mapeo_anexo_aaef": id_anexo, "mapeadores": ["COMPRAS", "COMPROBANTE_NIC41"]})
    assert (apagado.status_code, apagado.json()["error_code"]) == (422, "MAPPER_NO_DISPONIBLE")
    r = cli.post(f"/integracion/contratos/{id_contrato}/activar", headers=admin)
    assert r.status_code == 200 and r.json()["estado"] == "ACTIVO", r.text
    return id_cliente


def _token(cli: TestClient, correo: str, secreto: str = SECRETO):
    return cli.post("/integraciones/agrofusion/token",
                    json={"client_id": "agrofusion", "client_secret": secreto, "email": correo})


def test_agrofusion_consulta_el_documento_aaef_de_punta_a_punta(
    db_session, m06, cliente_http, crear_usuario_db, crear_auth_headers,
):
    contador = crear_usuario_db(id_rol=5, estado=2)
    admin = crear_usuario_db(id_rol=1, estado=2)
    rango, _ = _sembrar_m06_cerrado(db_session, m06, contador["id_usuario"])
    web_contador = crear_auth_headers(contador)
    admin_web = crear_auth_headers(admin)
    id_cliente = _preparar_m07(cliente_http, admin_web, web_contador)

    # GET_AUTHORIZATION: token de canal que no cierra la sesión web del Contador (RFC-019 D-19.4).
    r = _token(cliente_http, contador["correo"])
    assert r.status_code == 200, r.text
    canal = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert 300 <= r.json()["expires_in"] <= 3600
    assert cliente_http.get("/usuarios/me", headers=web_contador).status_code == 200
    assert cliente_http.get("/usuarios/me", headers=canal).status_code == 401  # el token de canal no opera la web

    # RF-AE01: AgroFusion consulta el período cerrado.
    r = cliente_http.get(URL, params=rango, headers=canal)
    assert r.status_code == 200, r.text
    assert r.headers["X-Version-Contrato-AAEF"] == "3.0" and r.headers["X-Request-Id"]
    documento = AccountingConsultResponse.model_validate(r.json())  # lo que AgroFusion valida (sin 502)
    assert documento.metadata.SourceSystem.SystemNIT == NIT and documento.metadata.StandardVersion == "1.0"
    [factura] = documento.invoices  # la factura repartida es un solo 02 (SIGCON rechaza números repetidos)
    assert (factura.Header.Type.Code, factura.Header.Prefix, factura.Header.Serial) == ("02", "FE", "88231")
    assert [ln.accounting_account for ln in factura.Lines] == [["5135"], ["5135"]]
    assert factura.Totals.Subtotal == factura.Totals.TotalPayment == 100.01 and documento.transactions == []
    segunda = cliente_http.get(URL, params=rango, headers=canal)
    assert segunda.headers["X-Content-SHA256"] == r.headers["X-Content-SHA256"]  # mismo rango cerrado, mismo hash
    assert segunda.json()["metadata"]["ExchangeId"] != r.json()["metadata"]["ExchangeId"]

    # Rechazos de RF-AE01.
    assert cliente_http.get(URL, params=rango).json()["error_code"] == "NO_AUTENTICADO"
    assert cliente_http.get(URL, params={**rango, "client_secret": "x"}, headers=canal).json()["error_code"] == "CREDENCIALES_EN_URL"
    assert cliente_http.get(URL, params={**rango, "desde": "2026/10/01"}, headers=canal).json()["error_code"] == "PARAMETROS_INVALIDOS"
    desalineado = cliente_http.get(URL, params={**rango, "desde": (HOY.replace(day=1) + timedelta(days=3)).isoformat()}, headers=canal)
    assert (desalineado.status_code, desalineado.json()["error_code"]) == (422, "RANGO_NO_ALINEADO")
    assert rango["desde"] in desalineado.json()["message"]
    siguiente_fin = (HOY.replace(day=28) + timedelta(days=40)).replace(day=1) - timedelta(days=1)
    abierto = cliente_http.get(URL, params={**rango, "hasta": siguiente_fin.isoformat()}, headers=canal)
    assert (abierto.status_code, abierto.json()["error_code"]) == (422, "PERIODO_NO_CERRADO")
    assert cliente_http.get(URL, params=rango, headers={**canal, "Accept-Version": "9.9"}).status_code == 404
    assert cliente_http.get("/integracion/aaef/productores/111222333", params=rango, headers=canal).status_code == 404
    assert _token(cliente_http, contador["correo"], "otro-secreto-incorrecto-00").status_code == 401

    # RF-95 5.3 d: una finca más del titular sin asignar al Contador → 403.
    otro = crear_usuario_db(id_rol=5, estado=2)
    _finca(db_session, otro["id_usuario"])
    r = cliente_http.get(URL, params=rango, headers=canal)
    assert (r.status_code, r.json()["error_code"]) == (403, "ALCANCE_INSUFICIENTE")

    # RF-101 5.4: suspender corta el token vigente en la siguiente solicitud.
    assert cliente_http.post(f"/integracion/clientes/{id_cliente}/suspender", headers=admin_web,
                             json={"motivo": "Prueba de suspensión"}).status_code == 200
    r = cliente_http.get(URL, params=rango, headers=canal)
    assert (r.status_code, r.json()["error_code"]) == (403, "CLIENTE_NO_AUTORIZADO")

    # RF-102: todo quedó auditado, íntegro y sin secretos; la tabla es inmutable.
    r = cliente_http.get("/integracion/auditoria", headers=admin_web, params={"tamano": 100})
    assert r.status_code == 200
    tipos = {e["tipo_evento"] for e in r.json()["items"]}
    assert {"PAQUETE_AAEF_CONSULTADO", "SOLICITUD_RECHAZADA", "CREDENCIALES_EN_URL", "TOKEN_CANAL_EMITIDO",
            "TOKEN_CANAL_RECHAZADO", "CLIENTE_REGISTRADO", "CLIENTE_SUSPENDIDO", "CONTRATO_ACTIVADO"} <= tipos
    assert all(e["integridad"] == "INTEGRO" for e in r.json()["items"])
    assert SECRETO not in r.text and canal["Authorization"][7:] not in r.text
    assert cliente_http.get("/integracion/auditoria", headers=web_contador).status_code == 403
    assert cliente_http.delete("/integracion/auditoria", headers=admin_web).status_code == 405
    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(text("UPDATE modulo7.eventos_integracion SET codigo_http = 1"))


def test_rotar_el_secreto_invalida_el_anterior_de_inmediato(
    db_session, cliente_http, crear_usuario_db, crear_auth_headers,
):
    contador = crear_usuario_db(id_rol=5, estado=2)
    admin = crear_auth_headers(crear_usuario_db(id_rol=1, estado=2))
    id_cliente = cliente_http.post("/integracion/clientes", headers=admin, json={
        "codigo": "AGROFUSION", "nombre": "AgroFusion", "identificador_publico": "agrofusion",
        "fecha_vencimiento": (HOY + timedelta(days=30)).isoformat(), "canales": [{"canal": "CONSULTA_AAEF"}]}).json()["id_cliente_externo"]
    r = cliente_http.post(f"/integracion/clientes/{id_cliente}/rotar", headers=admin,
                          json={"motivo": "Rotación programada", "fecha_vencimiento": (HOY + timedelta(days=90)).isoformat()})
    nuevo = r.json()["client_secret"]
    assert len(nuevo) >= 40
    assert _token(cliente_http, contador["correo"], nuevo).status_code == 200
    revocar = cliente_http.post(f"/integracion/clientes/{id_cliente}/revocar", headers=admin, json={"motivo": "Fin del convenio"})
    assert revocar.json()["estado"] == "REVOCADO"
    assert cliente_http.post(f"/integracion/clientes/{id_cliente}/reactivar", headers=admin, json={}).status_code == 409
    assert _token(cliente_http, contador["correo"], nuevo).status_code == 403


def test_agrofusion_sincroniza_usuarios_como_lo_hace_su_backend(
    db_session, cliente_http, crear_usuario_db, crear_auth_headers,
):
    """Mismo orden y forma que ``agrofusion-backendauth/users_service``: GET_USER (404 = crear), CREATE_USER
    con apellidos separados, roles como lista y género con su catálogo, ACTIVATE_ACCOUNT con el token,
    CHANGE_USER_STATUS y UPDATE_USER con el id de SGPMP en ``{user_id}``."""
    admin = crear_usuario_db(id_rol=1, estado=2)
    cliente_http.post("/integracion/clientes", headers=crear_auth_headers(admin), json={
        "codigo": "AGROFUSION", "nombre": "AgroFusion", "identificador_publico": "agrofusion",
        "fecha_vencimiento": (HOY + timedelta(days=30)).isoformat(), "client_secret": SECRETO,
        "canales": [{"canal": "IDENTIDAD_M2M"}]})
    r = _token(cliente_http, admin["correo"])
    canal = {"Authorization": f"Bearer {r.json()['access_token']}"}
    from jose import jwt as jose_jwt
    assert jose_jwt.get_unverified_claims(r.json()["access_token"])["rol"] == [1]  # AgroFusion lo lee como lista

    # Catálogos que AgroFusion llama sin token.
    # AgroFusion pasa estas listas sin plantilla y su frontend lee id/name y role_id/role_name.
    assert [x["id"] for x in cliente_http.get("/integraciones/agrofusion/tipos-documento").json()] == [1, 2, 3]
    roles = cliente_http.get("/integraciones/agrofusion/roles").json()
    id_contador = next(x["role_id"] for x in roles if x["role_name"] == "Contador")
    id_productor = next(x["role_id"] for x in roles if x["role_name"] == "Productor")

    correo = f"af-{_letras_minusculas()}@example.com"
    assert cliente_http.get(f"/integraciones/agrofusion/usuarios/{correo}", headers=canal).status_code == 404
    r = cliente_http.post("/integraciones/agrofusion/usuarios", headers=canal, json={  # tal como lo arma AgroFusion
        "email": correo, "name": "Laura", "first_last_name": "Gómez", "second_last_name": "Ruiz",
        "type_document_id": "1", "document_number": str(_numero()), "birthday": "1990-05-10",
        "gender_id": "2", "roles": [id_productor], "password": "Inicial2026*Segura", "date_issuance_document": "2010-01-01"})
    assert r.status_code == 201, r.text
    assert (r.json()["apellidos"], r.json()["genero"], r.json()["id_rol"]) == ("Gómez Ruiz", "F", id_productor)
    token = r.json()["activation_token"]
    for _ in range(2):  # RFC-019 D-19.6: ACTIVATE_ACCOUNT llega después y responde 200 idempotente
        activacion = cliente_http.get(f"/usuarios/activar/{token}")
        assert (activacion.status_code, activacion.json()["message"]) == (200, "La cuenta ya está activa.")
    assert cliente_http.get(f"/usuarios/activar/m2m-{'x' * 43}").status_code == 400

    usuario = cliente_http.get(f"/integraciones/agrofusion/usuarios/{correo}", headers=canal).json()
    assert usuario["roles"] == [id_productor] and usuario["genero_id"] == 2 and usuario["id_estado_cuenta"] == 2
    assert (usuario["type_document_id"], usuario["first_last_name"]) == (1, "Gómez Ruiz")
    assert None not in usuario.values()  # la plantilla de AgroFusion convertiría un nulo en «None»
    user_id = usuario["user_id"]

    for estado, esperado in ((2, 3), (1, 2), (1, 2)):  # inactivo, activo y activo otra vez (no es error)
        r = cliente_http.patch(f"/integraciones/agrofusion/usuarios/{user_id}/estado", headers=canal, json={"user_id": str(user_id), "new_status": str(estado)})
        assert r.status_code == 200, r.text
        assert cliente_http.get(f"/integraciones/agrofusion/usuarios/{correo}", headers=canal).json()["id_estado_cuenta"] == esperado

    r = cliente_http.put(f"/integraciones/agrofusion/usuarios/{user_id}", headers=canal, json={
        "name": "Laura Marcela", "first_last_name": "Gómez", "second_last_name": "Ruiz", "telefono": "3001234567",
        "roles": [id_contador], "gender_id": "1", "document_number": "999", "type_document_id": "1"})  # documento y género se ignoran
    assert r.status_code == 200, r.text
    assert (r.json()["nombre"], r.json()["telefono"], r.json()["id_rol"], r.json()["genero"]) == ("Laura Marcela", "3001234567", id_contador, "F")
    assert cliente_http.put(f"/integraciones/agrofusion/usuarios/{user_id}", headers=canal,
                            json={"roles": [987654]}).json()["error_code"] == "ROL_NO_ENCONTRADO"
    assert cliente_http.patch("/integraciones/agrofusion/usuarios/987654321/estado", headers=canal,
                              json={"nuevo_estado": 2}).status_code == 404


def _letras_minusculas() -> str:
    import random
    import string
    return "".join(random.choices(string.ascii_lowercase, k=10))


def _numero() -> int:
    import random
    return random.randint(10_000_000, 99_999_999)
