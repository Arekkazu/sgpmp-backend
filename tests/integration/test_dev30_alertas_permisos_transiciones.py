# | Fecha      | Nombre  | Que se hizo                                          |
# |------------|---------|------------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-30 RF-57: prueba RBAC y persistencia PostgreSQL   |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DEV-49: el fallo inducido pasa a la auditoria (historial por trigger) |
"""HTTP, JWT, RBAC, repositorios y triggers reales en PostgreSQL exclusivo.

Si existe el recurso DB-08, la fixture configura explícitamente D/alertas
dentro de la transacción de cada prueba. Si falta, los escenarios que lo
requieren se omiten; nunca se crea un recurso para aparentar su despliegue.
"""
from __future__ import annotations

import importlib
import pkgutil
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import alerta_router

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos_dev30():
    for paquete in (
        "src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
        "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models",
    ):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + "."):
            importlib.import_module(item.name)


@pytest.fixture
def escenario(db_session, crear_usuario_db, crear_auth_headers, monkeypatch):
    from src.shared import jwt as jwt_module

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    recurso = db_session.execute(text(
        "SELECT id_recurso FROM modulo1.recursos WHERE nombre_recurso='alertas'"
    )).scalar_one_or_none()
    roles = dict(db_session.execute(text(
        "SELECT nombre_rol,id_rol FROM modulo1.roles WHERE nombre_rol IN ('Productor','Veterinario','Administrador')"
    )).all())
    assert set(roles) == {"Productor", "Veterinario", "Administrador"}
    # Un rol adicional demuestra que no se decide por el id o nombre del rol.
    roles["Personalizado"] = db_session.execute(text(
        "INSERT INTO modulo1.roles(nombre_rol,es_protegido) VALUES (:nombre,false) RETURNING id_rol"
    ), {"nombre": "DEV30 " + uuid4().hex[:12]}).scalar_one()
    for nombre, rol in roles.items():
        permisos = [(32, 3, True)]
        if recurso is not None:
            permisos.append((recurso, 4, nombre != "Productor"))
        for recurso_id, accion, activo in permisos:
            db_session.execute(text("""
                INSERT INTO modulo1.permisos(nombre,id_rol,id_recurso,id_accion,es_activo)
                VALUES (:nombre,:rol,:recurso,:accion,:activo)
                ON CONFLICT(id_rol,id_recurso,id_accion)
                DO UPDATE SET es_activo=EXCLUDED.es_activo
            """), {"nombre": "DEV30 " + uuid4().hex[:12], "rol": rol,
                  "recurso": recurso_id, "accion": accion, "activo": activo})
    usuarios = {nombre: crear_usuario_db(id_rol=rol) for nombre, rol in roles.items()}
    headers = {nombre: crear_auth_headers(usuario) for nombre, usuario in usuarios.items()}
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, db_session, headers, roles, recurso


def _crear_alerta(db, estado="ACTIVA"):
    id_alerta = db.execute(text("""
        INSERT INTO modulo3.alertas(tipo_alerta,severidad,estado_alerta,origen_evento,
            tipo_variable,fecha_evento,fecha_generacion)
        VALUES ('FALLO_AMBIENTAL','LEVE',:estado,'EDGE','TEMPERATURA_AMBIENTAL',now(),now())
        RETURNING id_alerta
    """), {"estado": estado}).scalar_one()
    db.commit()
    return id_alerta


def _registros(db, id_alerta):
    alerta = db.execute(text("SELECT to_jsonb(a) FROM modulo3.alertas a WHERE id_alerta=:id"), {"id": id_alerta}).scalar_one()
    historico = db.execute(text("""
        SELECT to_jsonb(h) FROM modulo3.historico_estados_alertas h
        WHERE id_alerta=:id ORDER BY id_historico_estado_alerta
    """), {"id": id_alerta}).scalars().all()
    return alerta, historico


def _patch(escenario, id_alerta, estado, rol="Productor"):
    return escenario[0].patch(
        f"/iot/alertas/{id_alerta}/estado", headers=escenario[2][rol],
        json={"nuevo_estado": estado, "motivo": "Revisión DEV-30"},
    )


def _requiere_db08(escenario):
    if escenario[4] is None:
        pytest.skip("DB-08 pendiente: no existe el recurso 'alertas' del contrato documentado.")


def test_productor_u_sin_d_recibe_403_sin_persistencia(escenario):
    db = escenario[1]
    id_alerta = _crear_alerta(db)
    previo = _registros(db, id_alerta)
    respuesta = _patch(escenario, id_alerta, "descartada")
    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"
    assert _registros(db, id_alerta) == previo


@pytest.mark.parametrize("rol", ["Veterinario", "Administrador", "Personalizado"])
def test_d_explicito_permite_descarte_y_persistencia(escenario, rol):
    _requiere_db08(escenario)
    id_alerta = _crear_alerta(escenario[1])
    respuesta = _patch(escenario, id_alerta, "DESCARTADA", rol)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado_alerta"] == "DESCARTADA"
    alerta, historial = _registros(escenario[1], id_alerta)
    assert alerta["estado_alerta"] == "DESCARTADA"
    assert historial and all(h["estado_nuevo"] == "DESCARTADA" for h in historial)


@pytest.mark.parametrize("estado_origen,destino", [
    ("ACTIVA", "CERRADA"), ("ACTIVA", "VENCIDA"),
    ("EN_ATENCION", "VENCIDA"), ("VENCIDA", "EN_ATENCION"),
    ("VENCIDA", "RESUELTA"), ("VENCIDA", "DESCARTADA"),
])
def test_transicion_invalida_no_modifica_filas(escenario, estado_origen, destino):
    if destino == "DESCARTADA":
        _requiere_db08(escenario)
    db = escenario[1]
    id_alerta = _crear_alerta(db, estado_origen)
    previo = _registros(db, id_alerta)
    respuesta = _patch(escenario, id_alerta, destino, "Veterinario")
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["error_code"] == "TRANSICION_INVALIDA"
    assert _registros(db, id_alerta) == previo
    eventos = db.execute(text("""
        SELECT resultado,accion_detallada FROM modulo3.bitacora_auditoria_iot
        WHERE entidad_afectada_tipo='ALERTA' AND entidad_afectada_id=:id
          AND tipo_evento='TRANSICION_ALERTA_RECHAZADA'
    """), {"id": str(id_alerta)}).all()
    assert len(eventos) == 1
    assert eventos[0][0] == "RECHAZADO"
    assert eventos[0][1] == {"error_code": "TRANSICION_INVALIDA", "estado_solicitado": destino}


@pytest.mark.parametrize("origen,destino", [("ACTIVA", "EN_ATENCION"), ("EN_ATENCION", "RESUELTA")])
def test_transicion_valida_con_u_se_conserva(escenario, origen, destino):
    id_alerta = _crear_alerta(escenario[1], origen)
    respuesta = _patch(escenario, id_alerta, destino)
    assert respuesta.status_code == 200, respuesta.text
    assert _registros(escenario[1], id_alerta)[0]["estado_alerta"] == destino


def test_permiso_d_inactivo_no_autoriza(escenario):
    _requiere_db08(escenario)
    db = escenario[1]
    db.execute(text("""
        UPDATE modulo1.permisos SET es_activo=false
        WHERE id_rol=:rol AND id_recurso=:recurso AND id_accion=4
    """), {"rol": escenario[3]["Veterinario"], "recurso": escenario[4]})
    id_alerta = _crear_alerta(db)
    previo = _registros(db, id_alerta)
    respuesta = _patch(escenario, id_alerta, "DESCARTADA", "Veterinario")
    assert respuesta.status_code == 403, respuesta.text
    assert _registros(db, id_alerta) == previo


def test_d_sin_u_no_omite_control_general(escenario):
    _requiere_db08(escenario)
    db = escenario[1]
    db.execute(text("""
        UPDATE modulo1.permisos SET es_activo=false
        WHERE id_rol=:rol AND id_recurso=32 AND id_accion=3
    """), {"rol": escenario[3]["Personalizado"]})
    id_alerta = _crear_alerta(db)
    previo = _registros(db, id_alerta)
    respuesta = _patch(escenario, id_alerta, "DESCARTADA", "Personalizado")
    assert respuesta.status_code == 403, respuesta.text
    assert _registros(db, id_alerta) == previo


def test_sin_token_no_autoriza(escenario):
    id_alerta = _crear_alerta(escenario[1])
    respuesta = escenario[0].patch(f"/iot/alertas/{id_alerta}/estado", json={"nuevo_estado": "DESCARTADA"})
    assert respuesta.status_code == 401
    assert _registros(escenario[1], id_alerta)[0]["estado_alerta"] == "ACTIVA"


def test_fallo_de_historial_revierte_estado_en_postgresql(escenario, monkeypatch):
    # DEV-49: el historial lo escribe el trigger en la misma sentencia del UPDATE.
    # Se induce el fallo en la auditoría de DEV-47, que va en la misma transacción
    # después del cambio de estado: el estado y el historial tienen que revertirse.
    from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository

    def fallar(*args, **kwargs):
        raise RuntimeError("Fallo de persistencia inducido por la prueba")

    id_alerta = _crear_alerta(escenario[1])
    previo = _registros(escenario[1], id_alerta)
    monkeypatch.setattr(SqlAlchemyAlertaRepository, "_auditar", fallar)
    respuesta = _patch(escenario, id_alerta, "EN_ATENCION")
    assert respuesta.status_code == 500  # Fallo inesperado, no una regla de negocio.
    assert _registros(escenario[1], id_alerta) == previo
