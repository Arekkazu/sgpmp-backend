# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74..81: flujo completo contra Postgres |
"""M05 de punta a punta contra Postgres real (TestClient + triggers + migración bf404c6f1018).

Cubre lo que los fakes no pueden: el ledger y el acumulado que llevan los
triggers, la dedup corregida, la compensación de anulaciones, los códigos HTTP
del RF, la entrega a M06, la exportación con vencimiento y el cierre de ciclo.
"""
from __future__ import annotations

import random
import string
import uuid
from collections.abc import Generator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.fechas import hoy_colombia

pytestmark = pytest.mark.integration

HOY = hoy_colombia()


def _id() -> int:
    return uuid.uuid4().int % (10**9)


def _nombre(prefijo: str) -> str:
    return prefijo + " " + "".join(random.choices(string.ascii_letters, k=10))


@pytest.fixture(autouse=True)
def _catalogos(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    db_session.execute(text(
        "INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre) VALUES "
        "(1,'ACTIVO'),(2,'INACTIVO'),(3,'EN_TRATAMIENTO'),(4,'AISLADO'),(5,'CERRADO'),(6,'BAJA') "
        "ON CONFLICT (id_estado_activo_biologico) DO NOTHING"
    ))
    db_session.flush()
    # Los avisos por correo de RF-76 no deben intentar SMTP en la prueba.
    monkeypatch.setattr(
        "src.supplies.infrastructure.adapters.notificacion_medicamento_email_adapter.send_email",
        lambda **_: None,
    )


def _escenario(db: Session, id_usuario: int, *, con_fase: bool = True) -> dict:
    """Finca + infraestructura + activo INDIVIDUAL ACTIVO (+ fase abierta) + alimento del catálogo."""
    sid = _id()
    db.execute(text("SET LOCAL app.usuario_id = :uid"), {"uid": id_usuario})
    db.execute(text(
        "INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, "
        "es_activo) VALUES (:id, :n, '{}', 10, now(), now(), true)"), {"id": sid, "n": _nombre("Finca Suministros")})
    db.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"),
               {"u": id_usuario, "f": sid})
    db.execute(text(
        "INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca, superficie, es_activo, tipo) "
        "VALUES (:id, :n, :id, 100, true, 'Corral')"), {"id": sid, "n": _nombre("Corral Suministros")})
    id_activo = _id()
    db.execute(text(
        "INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie, identificador, id_infraestructura, "
        "tipo, fecha_inicio_ciclo, id_estado, descripcion, origen_financiero, costo_adquisicion, atributos_dinamicos, "
        "id_usuario, fecha_creacion, soporte_documental, detalles_procedencia) VALUES (:id, 2, :ident, :infra, "
        "'INDIVIDUAL', current_date - 30, 1, 'Integración M05', 'compra', 100, '{}', :u, now() - interval '31 days', "
        "'doc', '')"),
        {"id": id_activo, "ident": f"M05-{id_activo}", "infra": sid, "u": id_usuario})
    id_fase = None
    if con_fase:
        id_fase, id_cpb = _id(), _id()
        # La base de pruebas no trae ciclos biológicos: la fila puente se siembra sin su FK.
        db.execute(text("SET LOCAL session_replication_role = replica"))
        db.execute(text(
            "INSERT INTO modulo9.ciclos_productivos_biologicos (id_ciclos_productivo_biologico, id_ciclo_biologico, "
            "id_ciclo_productivo) VALUES (:id, 1, 1)"), {"id": id_cpb})
        db.execute(text(
            "INSERT INTO modulo2.gestiones_fases (id_gestion_fases, id_activo_biologico, id_ciclo_productiva, "
            "fecha_inicio, es_activa, id_usuario, id_ciclos_productivo_biologico) "
            "VALUES (:id, :a, 1, now() - interval '30 days', true, :u, :cpb)"),
            {"id": id_fase, "a": id_activo, "u": id_usuario, "cpb": id_cpb})
        db.execute(text("SET LOCAL session_replication_role = origin"))
    id_alimento = db.execute(text(
        "INSERT INTO modulo5.tipos_alimentos (nombre, costo_unitario, unidad_medida, estado) "
        "VALUES (:n, 1000, 'kg', 'ACTIVO') RETURNING id_tipo_elemento"), {"n": _nombre("Concentrado")}).scalar_one()
    db.flush()
    return {"activo": id_activo, "fase": id_fase, "alimento": id_alimento, "finca": sid}


@pytest.fixture
def cliente(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.biological_assets.infrastructure.routers.activo_biologico_router import router as activos
    from src.identity_access.infrastructure.routers.usuarios_routers import router as _usuarios  # noqa: F401
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers
    from src.supplies.infrastructure.routers.consumo_alimento_router import router as consumos
    from src.supplies.infrastructure.routers.costeo_suministros_router import router as costeo
    from src.supplies.infrastructure.routers.historial_suministros_router import router as historial
    from src.supplies.infrastructure.routers.medicamento_router import router as medicamentos
    from src.supplies.infrastructure.routers.reporte_gastos_router import router as reportes

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    for r in (activos, consumos, costeo, historial, medicamentos, reportes):
        app.include_router(r)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("m05-integracion", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin(crear_usuario_db, crear_auth_headers):
    usuario = crear_usuario_db(id_rol=1, estado=2)
    return usuario, crear_auth_headers(usuario)


def _escalar(db: Session, sql: str, **params):
    return db.execute(text(sql), params).scalar()


def _consumo(cliente, headers, esc, hora: str, fecha: date = HOY, cantidad: str = "10"):
    return cliente.post("/suministros/consumo-alimentos", headers=headers, json={
        "id_activo_biologico": esc["activo"], "id_tipo_alimento": esc["alimento"], "fecha_consumo": fecha.isoformat(),
        "hora_suministro": hora, "cantidad_alimento": cantidad, "costo_unitario": "1500",
    })


def test_consumo_ledger_dedup_y_eventos(cliente, db_session, admin):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])

    r1 = _consumo(cliente, headers, esc, "08:00")
    r2 = _consumo(cliente, headers, esc, "16:00")  # misma ración, otra hora: RF-75 R12 (antes chocaba en el ledger)
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    assert Decimal(r1.json()["costo_total"]) == Decimal("15000")  # RF-75 paso 8: cantidad × costo_unitario

    assert _escalar(db_session, "SELECT count(*) FROM modulo5.registro_suministro WHERE id_activo_biologico=:a",
                    a=esc["activo"]) == 2
    assert _escalar(db_session, "SELECT acumulado_total_ciclo FROM modulo5.acumulado_ciclo WHERE id_gestion_fases=:f",
                    f=esc["fase"]) == Decimal("30000")
    assert _escalar(db_session, "SELECT count(*) FROM modulo5.outbox_provisiones_m06 WHERE id_gestion_fases=:f "
                    "AND modalidad='INCREMENTAL'", f=esc["fase"]) == 2
    assert _escalar(db_session, "SELECT count(*) FROM modulo5.auditorias_suministros WHERE id_activo_biologico=:a "
                    "AND tipo_operacion='ACUMULADO_ACTUALIZADO'", a=esc["activo"]) == 2

    anterior = _consumo(cliente, headers, esc, "07:00")  # CA-10: solo suministros posteriores al último
    assert anterior.status_code == 409, anterior.text
    assert anterior.json()["error_code"] == "CONSUMO_DUPLICADO"

    futuro = _consumo(cliente, headers, esc, "09:00", fecha=HOY + timedelta(days=1))
    assert futuro.status_code == 400 and futuro.json()["error_code"] == "FECHA_FUTURA"
    cero = _consumo(cliente, headers, esc, "17:00", cantidad="0")
    assert cero.status_code == 400
    assert "mayor a cero kilogramos" in cero.text


def test_anular_consumo_compensa_ledger_y_edicion_405(cliente, db_session, admin):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])
    id_consumo = _consumo(cliente, headers, esc, "08:00").json()["id_consumo_alimeto"]

    assert cliente.put(f"/suministros/consumo-alimentos/{id_consumo}", headers=headers).status_code == 405

    corta = cliente.post(f"/suministros/consumo-alimentos/{id_consumo}/anulacion", headers=headers,
                         json={"justificacion_anulacion": "error"})
    assert corta.status_code == 400
    r = cliente.post(f"/suministros/consumo-alimentos/{id_consumo}/anulacion", headers=headers,
                     json={"justificacion_anulacion": "Se registró en el activo equivocado por error"})
    assert r.status_code == 200, r.text
    assert _escalar(db_session, "SELECT acumulado_total_ciclo FROM modulo5.acumulado_ciclo WHERE id_gestion_fases=:f",
                    f=esc["fase"]) == Decimal("0")
    assert _escalar(db_session, "SELECT sum(costo_registro) FROM modulo5.registro_suministro "
                    "WHERE id_activo_biologico=:a", a=esc["activo"]) == Decimal("0")
    otra = cliente.post(f"/suministros/consumo-alimentos/{id_consumo}/anulacion", headers=headers,
                        json={"justificacion_anulacion": "Se registró en el activo equivocado por error"})
    assert otra.status_code == 409


def test_rf78_codigos_del_rf_y_correccion_aditiva(cliente, db_session, admin):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])
    base = {"id_activo_biologico": esc["activo"], "tipo_suministro": "SERVICIO_VETERINARIO", "cantidad": "2",
            "unidad_medida": "servicio", "precio_unitario": "50000", "fecha_aplicacion": HOY.isoformat(),
            "justificacion_precio": "Factura del veterinario sin precio de referencia"}

    def post(**cambios):
        return cliente.post("/suministros/costeo-directo", headers=headers,
                            json={**base, "id_idempotencia": str(uuid.uuid4()), **cambios})

    assert post(tipo_suministro="VACUNA").status_code == 422          # E4
    assert post(justificacion_precio=None).status_code == 422         # E2
    assert post(fecha_aplicacion=(HOY + timedelta(days=2)).isoformat()).status_code == 422  # E3
    sin_ciclo = _escenario(db_session, usuario["id_usuario"], con_fase=False)
    assert post(id_activo_biologico=sin_ciclo["activo"]).status_code == 409  # E1

    idem = str(uuid.uuid4())
    ok = cliente.post("/suministros/costeo-directo", headers=headers, json={**base, "id_idempotencia": idem})
    assert ok.status_code == 200 and ok.json()["estado"] == "REGISTRADO", ok.text
    repetido = cliente.post("/suministros/costeo-directo", headers=headers, json={**base, "id_idempotencia": idem})
    assert repetido.status_code == 200 and repetido.json()["estado"] == "YA_PROCESADO"
    duplicado = post()
    assert duplicado.status_code == 409  # E6

    id_original = ok.json()["id_registro_suministro"]
    assert cliente.post(f"/suministros/costeo-directo/{uuid.uuid4()}/correccion", headers=headers, json={
        "id_idempotencia": str(uuid.uuid4()), "cantidad": "1", "precio_unitario": "-1000",
        "justificacion_precio": "Ajuste por descuento posterior en factura", "motivo_correccion": "Descuento aplicado por el proveedor",
    }).status_code == 422  # E7
    for precio in ("-10000", "-5000"):
        c = cliente.post(f"/suministros/costeo-directo/{id_original}/correccion", headers=headers, json={
            "id_idempotencia": str(uuid.uuid4()), "cantidad": "1", "precio_unitario": precio,
            "justificacion_precio": "Ajuste por descuento posterior en factura",
            "motivo_correccion": "Descuento aplicado por el proveedor",
        })
        assert c.status_code == 200, c.text
    # R12: 100.000 − 10.000 − 5.000 (con reemplazo habría quedado en −15.000 + 100.000 − 100.000…)
    assert _escalar(db_session, "SELECT acumulado_total_ciclo FROM modulo5.acumulado_ciclo WHERE id_gestion_fases=:f",
                    f=esc["fase"]) == Decimal("85000")

    hist = cliente.get("/suministros/historial", headers=headers, params={
        "id_activo_biologico": esc["activo"], "tipo_suministro_filtro": "SERVICIO_VETERINARIO"})
    assert hist.status_code == 200, hist.text
    assert {i["tipo_suministro"] for i in hist.json()["items"]} == {"SERVICIO_VETERINARIO"}
    assert Decimal(hist.json()["resumen"]["monto_total_filtrado"]) == Decimal("85000")


def test_entrega_a_m06_idempotente(cliente, db_session, admin):
    from src.financial_valuation.application.use_cases.provision_costos.recibir_provision_costos_use_case import (
        RecibirProvisionCostosUseCase,
    )
    from src.financial_valuation.domain.entities.recepcion_provision import RecepcionProvision
    from src.financial_valuation.infrastructure.repositories.recepcion_provision_repository import (
        SqlAlchemyRecepcionProvisionRepository,
    )
    from src.supplies.infrastructure.factories.provision_nic41_factory import build_despachar_provisiones_m06_use_case

    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])
    _consumo(cliente, headers, esc, "08:00")

    def sesion_anidada() -> Session:
        return Session(bind=db_session.connection(), join_transaction_mode="create_savepoint")

    despachador = build_despachar_provisiones_m06_use_case(db_session)
    despachador.m06_port.session_factory = sesion_anidada
    assert despachador.ejecutar() >= 1
    assert _escalar(db_session, "SELECT estado FROM modulo5.outbox_provisiones_m06 WHERE id_gestion_fases=:f",
                    f=esc["fase"]) == "ENTREGADO"
    id_evento = _escalar(db_session, "SELECT id_evento_provision FROM modulo6.recepciones_provisiones_m05 "
                         "WHERE id_gestion_fases=:f", f=esc["fase"])
    assert id_evento is not None

    contenido = _escalar(db_session, "SELECT json_contenido FROM modulo6.recepciones_provisiones_m05 "
                         "WHERE id_evento_provision=:e", e=id_evento)
    ack = RecibirProvisionCostosUseCase(db_session, SqlAlchemyRecepcionProvisionRepository(db_session)).execute(
        RecepcionProvision(id_evento_provision=id_evento, modalidad="INCREMENTAL", schema_version="1.0",
                           id_activo_biologico=esc["activo"], id_gestion_fases=esc["fase"], contenido=contenido)
    )
    assert ack.duplicado is True  # R10 / CA-10
    assert _escalar(db_session, "SELECT count(*) FROM modulo6.recepciones_provisiones_m05 WHERE id_gestion_fases=:f",
                    f=esc["fase"]) == 1


def test_medicamento_e11_y_cierre_bloqueado_por_retiro(cliente, db_session, admin):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])

    def aplicar(hora: str):
        return cliente.post("/suministros/medicamentos", headers=headers, json={
            "id_activo_biologico": esc["activo"], "nombre_medicamento": "Oxitetraciclina",
            "fecha_aplicacion": HOY.isoformat(), "hora_aplicacion": hora, "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": "5", "unidad_dosis": "ml", "periodo_retiro_dias": 10,
            "motivo_aplicacion": "Tratamiento de infección respiratoria", "costo_unitario": "2000",
            "nombre_veterinario": "Dra. Prueba",
        })

    primero = aplicar("08:00")
    assert primero.status_code == 201, primero.text
    segundo = aplicar("14:00")
    assert segundo.status_code == 200, segundo.text  # E11
    assert segundo.json()["tratamientos_activos"] == 2
    assert "tratamientos activos" in segundo.json()["mensaje"]

    cierre = cliente.post(f"/activos-biologicos/{esc['activo']}/cierre", headers=headers,
                          json={"fecha_cierre": HOY.isoformat(), "motivo_cierre": "venta"})
    assert cierre.status_code == 409, cierre.text
    assert cierre.json()["error_code"] == "TRATAMIENTO_ACTIVO"


def test_cierre_de_ciclo_consolida_calcula_ca_y_reporta(cliente, db_session, admin):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])
    assert _consumo(cliente, headers, esc, "08:00").status_code == 201

    cierre = cliente.post(f"/activos-biologicos/{esc['activo']}/cierre", headers=headers,
                          json={"fecha_cierre": HOY.isoformat(), "motivo_cierre": "venta"})
    assert cierre.status_code == 200, cierre.text

    assert _escalar(db_session, "SELECT monto_provision FROM modulo5.provision_nic41 WHERE id_gestion_fases=:f",
                    f=esc["fase"]) == Decimal("15000")
    assert _escalar(db_session, "SELECT estado FROM modulo5.acumulado_ciclo WHERE id_gestion_fases=:f",
                    f=esc["fase"]) == "CONSOLIDADO"
    assert _escalar(db_session, "SELECT count(*) FROM modulo5.outbox_provisiones_m06 WHERE id_gestion_fases=:f "
                    "AND modalidad='CONSOLIDADO'", f=esc["fase"]) == 1
    assert _escalar(db_session, "SELECT count(*) FROM modulo5.resultado_ica WHERE id_activo_biologico=:a "
                    "AND periodo_evaluacion='POR_CICLO'", a=esc["activo"]) == 1
    assert _escalar(db_session, "SELECT count(*) FROM modulo5.reporte_gastos_acumulados "
                    "WHERE id_activo_biologico=:a", a=esc["activo"]) == 1


def test_reporte_gastos_exporta_pdf_y_vence(cliente, db_session, admin, crear_usuario_db, crear_auth_headers):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])
    _consumo(cliente, headers, esc, "08:00")

    r = cliente.post("/suministros/reportes-gastos", headers=headers, json={
        "fecha_inicio_reporte": (HOY - timedelta(days=10)).isoformat(), "fecha_fin_reporte": HOY.isoformat(),
        "activo_biologico_id": esc["activo"], "formato_exportacion": "PDF",
    })
    assert r.status_code == 200, r.text
    archivo = r.json()["archivo"]
    descarga = cliente.get(archivo["url_descarga"], headers=headers)
    assert descarga.status_code == 200
    assert descarga.content.startswith(b"%PDF")

    otro = crear_usuario_db(id_rol=1, estado=2)
    assert cliente.get(archivo["url_descarga"], headers=crear_auth_headers(otro)).status_code == 403

    db_session.execute(text(
        "UPDATE modulo5.archivos_exportacion_suministros SET fecha_generacion = now() - interval '2 days', "
        "fecha_expiracion = now() - interval '1 day' WHERE id_archivo_exportacion_suministro = :id"),
        {"id": archivo["id_archivo"]})
    db_session.flush()
    assert cliente.get(archivo["url_descarga"], headers=headers).status_code == 410  # E6d

    invertido = cliente.post("/suministros/reportes-gastos", headers=headers, json={
        "fecha_inicio_reporte": HOY.isoformat(), "fecha_fin_reporte": (HOY - timedelta(days=5)).isoformat(),
        "activo_biologico_id": esc["activo"],
    })
    assert invertido.status_code == 400  # E2
