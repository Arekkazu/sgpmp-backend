# | Fecha      | Nombre   | Que se hizo                                                                     |
# |------------|----------|---------------------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104..107: consultas de reportes, RLS de solicitudes, RF-105 y endpoints  |
"""Integración M08 RF-104 a RF-107 contra PostgreSQL con la migración ``a7c3e91f5b20``.

- Las consultas de los 18 reportes y del historial corren y devuelven lo sembrado.
- Las solicitudes de reporte solo las ve su dueño (RLS) y ``obtener`` las encuentra para responder 403.
- RF-105: escalamiento a CRÍTICA, auditoría de cada notificación y preferencias de canal.
- Endpoints: 403 por rol, 422 por período abierto, generación, descarga solo del dueño y catálogo de errores.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.reporting.domain.reportes.solicitud import EN_PROCESO, SolicitudReporte
from src.reporting.infrastructure.repositories.fuente_reportes_repository import SqlAlchemyFuenteReportesRepository
from src.reporting.infrastructure.repositories.solicitud_reporte_repository import SqlAlchemySolicitudReporteRepository
from src.shared.database import declarar_identidad

pytestmark = pytest.mark.integration

FINCA, AREA, ESPECIE, ANIMAL, LOTE, DISPOSITIVO, SENSOR = 8101, 8101, 8101, 8101, 8102, 8101, 8101
NIT = "901999888"


def _sembrar(db: Session) -> dict[str, date]:
    hoy = date.today()
    db.execute(text("SET LOCAL session_replication_role = replica"))
    sql = f"""
    INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
        VALUES (1, 'ACTIVO'), (6, 'BAJA') ON CONFLICT DO NOTHING;
    INSERT INTO modulo9.fincas (id_finca, nombre, razon_social, numero_id_tributaria, dv, es_activo, tipo_id_tributaria,
        ubicacion, tamano_h, fecha_creacion, fecha_actualizacion)
        VALUES ({FINCA}, 'Finca Integración', 'Agro Integración SAS', '{NIT}', '3', true, 'NIT', '{{}}', 5, now(), now());
    INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca, es_activo, tipo, superficie)
        VALUES ({AREA}, 'Galpón I', {FINCA}, true, 'GALPON', 50);
    INSERT INTO modulo9.especies (id_especie, nombre, es_activo, fecha_creacion) VALUES ({ESPECIE}, 'Especie I', true, now());
    INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie, identificador, id_infraestructura, tipo,
        fecha_inicio_ciclo, id_estado, atributos_dinamicos, id_usuario, fecha_creacion, origen_financiero)
    SELECT {ANIMAL}, {ESPECIE}, 'BOV-I', {AREA}, 'INDIVIDUAL'::modulo2.enum_activo_biologico_tipo, current_date - 200, 1,
           '{{"sinigan":"CO-I"}}'::jsonb, 1, now(), o FROM (SELECT enumlabel::modulo2.enum_activo_biologico_origen_financiero o
           FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
           WHERE t.typname = 'enum_activo_biologico_origen_financiero' LIMIT 1) x
    UNION ALL
    SELECT {LOTE}, {ESPECIE}, 'LOTE-I', {AREA}, 'POBLACIONAL'::modulo2.enum_activo_biologico_tipo, current_date - 100, 6,
           '{{}}'::jsonb, 1, now(), o FROM (SELECT enumlabel::modulo2.enum_activo_biologico_origen_financiero o
           FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
           WHERE t.typname = 'enum_activo_biologico_origen_financiero' LIMIT 1) x;
    INSERT INTO modulo2.detalles_activos_biologicos_poblacionales (id_activo_biologico, cantidad_inicial, cantidad_actual)
        VALUES ({LOTE}, 50, 40);
    INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha, descripcion, id_usuario) VALUES
        (81001, {LOTE}, now() - interval '3 days', 'Muerte', 1), (81002, {ANIMAL}, now() - interval '2 days', 'Pesaje', 1);
    INSERT INTO modulo2.eventos_bajas (id_evento, cantidad_afectada, detalles, tipo) VALUES (81001, 10, NULL, 'muerte');
    INSERT INTO modulo2.eventos_crecimeinto (id_evento, tipo_medicion, valor_medicion, unidad_medida)
        VALUES (81002, 'PESO', 320, 'kg');
    INSERT INTO modulo5.registros_medicamentos (id_activo_biologico, nombre_medicamento, descripcion_clinica, unidad_dosis,
        cantidad, fecha_aplicacion, costo_unitario_medicamento, costo_total_medicamento, via_aplicacion, estado_registro,
        periodo_retiro_dias, fecha_fin_retiro, id_usuario, fecha_registro)
        VALUES ({ANIMAL}, 'Ivermectina', 'Desparasitación', 'ml', 5, current_date - 3, 8000, 40000, 'SC', 'VALIDADO', 28,
                current_date + 25, 1, now());
    INSERT INTO modulo6.periodos_contables (id_periodo_contable, tipo_cierre, fecha_inicio, fecha_fin, estado,
        numero_id_tributaria, fecha_creacion, id_usuario) VALUES
        (8101, 'MENSUAL', date_trunc('month', current_date - interval '2 month')::date,
         (date_trunc('month', current_date - interval '1 month') - interval '1 day')::date, 'CERRADO', '{NIT}', now(), 1),
        (8102, 'MENSUAL', date_trunc('month', current_date - interval '1 month')::date,
         (date_trunc('month', current_date) - interval '1 day')::date, 'CERRADO', '{NIT}', now(), 1),
        (8103, 'MENSUAL', date_trunc('month', current_date)::date,
         (date_trunc('month', current_date) + interval '1 month - 1 day')::date, 'ABIERTO', '{NIT}', now(), 1);
    INSERT INTO modulo6.calculos_valor_razonable (id_activo_biologico, id_precio_mercado, metodo_costo,
        valor_razonable_bruto, costo_transporte, valor_neto, estado, fecha_calculo, id_periodo_contable, id_usuario)
        VALUES ({ANIMAL}, 1, 'PARAMETRIZADO', 1700000, 61000, 1639000, 'CALCULADO',
                date_trunc('month', current_date) - interval '3 day', 8102, 1);
    INSERT INTO modulo9.dispositivos_iot (id_dispositivo_iot, serial, descripcion, es_activo, fecha_creacion,
        id_infraestructura, id_tipo_dispositivo) VALUES ({DISPOSITIVO}, 'SN-I', 'Sensor', true, now() - interval '60 days', {AREA}, 1);
    INSERT INTO modulo9.sensores (id_sensores, id_dispositivo_iot, es_activo, nombre, categoria)
        VALUES ({SENSOR}, {DISPOSITIVO}, true, 'Temp I', 'TEMPERATURA');
    INSERT INTO modulo3.estados_dispositivos_iot (id_dispositivo_iot, estado_actual, fecha_ultimo_contacto,
        fecha_ultima_actualizacion) VALUES ({DISPOSITIVO}, 'SIN_SEÑAL', now() - interval '30 hours', now());
    """
    for sentencia in (s.strip() for s in sql.split(";")):
        if sentencia:
            db.execute(text(sentencia))
    db.execute(text("SET LOCAL session_replication_role = origin"))
    db.flush()
    return {"hoy": hoy}


# --- Consultas ---------------------------------------------------------------------------------

def test_consultas_de_reportes_devuelven_lo_sembrado(db_session: Session):
    _sembrar(db_session)
    f = SqlAlchemyFuenteReportesRepository(db_session)
    hoy, ahora = date.today(), datetime.now(timezone.utc)
    inventario = f.inventario(fincas=[FINCA], inicio=hoy - timedelta(days=30), fin=hoy, hasta=ahora, especie=None,
                              estado=None)
    assert {i["identificador"]: i["sinigan"] for i in inventario} == {"BOV-I": "CO-I", "LOTE-I": None}
    assert next(i for i in inventario if i["identificador"] == "BOV-I")["peso_kg"] == 320
    assert f.inventario(fincas=[FINCA], inicio=hoy - timedelta(days=30), fin=hoy, hasta=ahora, especie=None,
                        estado="MUERTO")[0]["identificador"] == "LOTE-I"
    salidas = f.salidas(fincas=[FINCA], desde=ahora - timedelta(days=30), hasta=ahora, especie=None)
    assert salidas[0]["tipo"] == "MUERTE" and salidas[0]["motivo"] is None
    valoracion = f.valoracion_periodo(id_periodo=8102, fincas=[FINCA])
    assert valoracion[0]["valor_razonable"] == 1639000 and valoracion[0]["metodo"] == "VALOR_RAZONABLE"
    assert f.retiros_vigentes(fincas=[FINCA], hoy=hoy, especie=None, activo=None)[0]["medicamento"] == "Ivermectina"
    dispositivos = f.dispositivos(fincas=[FINCA], corte=ahora, es_hoy=True, infraestructura=None)
    assert dispositivos[0]["estado"] == "SIN_SEÑAL"
    assert f.ubicar("activo", ANIMAL)["id_finca"] == FINCA and f.ubicar("sensor", SENSOR)["id_finca"] == FINCA
    periodo = f.periodo(8103)
    assert periodo["estado"] == "ABIERTO" and periodo["nit"] == NIT
    assert f.fincas_de_titular(NIT, None) == [FINCA]
    assert f.valor_portafolio(fincas=[FINCA], fin=periodo["fecha_inicio"] - timedelta(days=1))[0]["valor"] == 1639000
    assert f.parametro("ventana_correspondencia_horas") == 12
    # El resto de consultas corren sin error con el esquema real.
    f.costos(fincas=[FINCA], inicio=None, fin=hoy, especie=None, tipo=None)
    f.produccion(fincas=[FINCA], desde=None, hasta=ahora, especie=None, activo=None)
    f.variacion_periodos(base=8102, comparacion=8101, fincas=[FINCA])
    f.exportaciones(8102)
    f.eventos_sanitarios(fincas=[FINCA], desde=None, hasta=ahora, especie=None, activo=None)
    f.predicciones_activas(fincas=[FINCA], especie=None, activo=None, desde=None)
    f.calibraciones(fincas=[FINCA], desde=ahora - timedelta(days=365), hasta=ahora, sensor=None, infraestructura=None)
    f.alertas_sensores(fincas=[FINCA], desde=ahora - timedelta(days=30), hasta=ahora, infraestructura=None)
    f.inferencias(activo=ANIMAL, desde=ahora - timedelta(days=30), hasta=ahora)
    f.retroalimentaciones(activo=ANIMAL, desde=ahora - timedelta(days=30), hasta=ahora)


# --- RLS de solicitudes ------------------------------------------------------------------------

def test_cada_usuario_ve_solo_sus_reportes(db_session: Session, crear_usuario_db):
    a, b = crear_usuario_db(id_rol=5), crear_usuario_db(id_rol=5)
    repo = SqlAlchemySolicitudReporteRepository(db_session)
    db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
    declarar_identidad(db_session, a["id_usuario"], "Contador")
    db_session.connection().execute(text("SELECT set_config('app.current_user_id', :u, true), "
                                         "set_config('app.current_role', 'Contador', true)"),
                                    {"u": str(a["id_usuario"])})
    from uuid import uuid4
    s = SolicitudReporte(id_usuario=a["id_usuario"], tipo_reporte="REPORTE_VALORACION_NIC41", formato="PDF",
                         id_solicitud_reporte=uuid4())
    s.encolar(datetime.now(timezone.utc))
    repo.guardar(s)
    assert [r.id_solicitud_reporte for r in repo.listar_por_usuario(a["id_usuario"], 10)] == [s.id_solicitud_reporte]
    db_session.connection().execute(text("SELECT set_config('app.current_user_id', :u, true)"),
                                    {"u": str(b["id_usuario"])})
    assert repo.listar_por_usuario(a["id_usuario"], 10) == []
    db_session.execute(text("RESET ROLE"))
    encontrada = repo.obtener(s.id_solicitud_reporte)
    assert encontrada is not None and encontrada.estado == EN_PROCESO


# --- RF-105 ------------------------------------------------------------------------------------

def test_escalamiento_auditoria_y_preferencias(db_session: Session, crear_usuario_db):
    from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
    from src.identity_access.infrastructure.repositories.notificacion_repository import (
        SqlAlchemyNotificacionRepository,
    )
    _sembrar(db_session)
    vet = crear_usuario_db(id_rol=3)
    repo = SqlAlchemyNotificacionRepository(db_session)

    def aviso(nivel: str) -> int:
        id_evento = SqlAlchemyEventoRepository(db_session).registrar(
            tipo_evento=32, exitoso=True, id_usuario=vet["id_usuario"], detalle={"titulo": "Fiebre"}, modulo="MODULO3")
        return repo.registrar(id_evento=id_evento, id_usuario=vet["id_usuario"], id_canal=2, mensaje="Fiebre",
                              estado="en_cola", nivel=nivel, id_activo_biologico=ANIMAL)

    for _ in range(3):
        aviso("CRITICA")
    escalada = aviso("ADVERTENCIA")
    nivel = db_session.execute(text("SELECT nivel::text FROM modulo1.notificaciones WHERE id_notificacion = :n"),
                               {"n": escalada}).scalar()
    assert nivel == "CRITICA"
    auditadas = db_session.execute(text("""
        SELECT count(*) FROM modulo1.eventos WHERE tipo_evento = 46 AND id_usuario = :u
          AND detalle->>'accion' = 'CREADA'"""), {"u": vet["id_usuario"]}).scalar()
    assert auditadas == 4
    notificacion = repo.obtener_interna(escalada, vet["id_usuario"])
    notificacion.marcar_como_leida(datetime.now(timezone.utc))
    repo.guardar(notificacion)
    assert db_session.execute(text("""SELECT count(*) FROM modulo1.eventos WHERE tipo_evento = 46
        AND detalle->>'accion' = 'LEIDA' AND (detalle->>'id_notificacion')::int = :n"""), {"n": escalada}).scalar() == 1

    assert repo.canal_habilitado(vet["id_usuario"], "ADVERTENCIA", "PUSH") is True
    repo.guardar_preferencias(vet["id_usuario"], {("ADVERTENCIA", "PUSH"): False})
    assert repo.canal_habilitado(vet["id_usuario"], "ADVERTENCIA", "PUSH") is False
    assert repo.ventana_agrupacion_minutos() == 5


# --- Endpoints ---------------------------------------------------------------------------------

@pytest.fixture
def cliente_m08(integration_app: FastAPI, client: TestClient, db_session: Session, monkeypatch):
    """El cliente de integración con los routers de M08; la instantánea y los avisos usan la transacción de la
    prueba (en producción abren su propia sesión)."""
    from src.configuration.infrastructure.routers import mensajes_error_router
    from src.reporting.infrastructure.adapters import avisos_reportes_m01_adapter  # noqa: F401
    from src.reporting.infrastructure.routers import reportes_router
    from src.shared.database import declarar_identidad_sistema

    @contextmanager
    def instantanea(id_usuario, zona):
        yield SqlAlchemyFuenteReportesRepository(db_session)

    def sesion_fondo() -> Session:
        sesion = Session(bind=db_session.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint")
        declarar_identidad_sistema(sesion)
        return sesion

    monkeypatch.setattr(reportes_router, "abrir_instantanea", instantanea)
    monkeypatch.setattr(reportes_router, "sesion_sistema", sesion_fondo)
    if not any(getattr(r, "path", "") == "/reportes" for r in integration_app.routes):
        integration_app.include_router(reportes_router.router)
        integration_app.include_router(mensajes_error_router.router)
    return client


def _asignar_finca(db: Session, id_usuario: int) -> None:
    db.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca, es_activo, fecha_creacion) "
                    "VALUES (:u, :f, true, now())"), {"u": id_usuario, "f": FINCA})
    db.flush()


def test_reportes_por_rol_periodo_y_descarga(cliente_m08: TestClient, db_session: Session, crear_usuario_db,
                                             crear_auth_headers):
    _sembrar(db_session)
    contador, productor, otro = crear_usuario_db(id_rol=5), crear_usuario_db(id_rol=2), crear_usuario_db(id_rol=5)
    for u in (contador, productor, otro):
        _asignar_finca(db_session, u["id_usuario"])
    h_cont, h_prod, h_otro = (crear_auth_headers(u) for u in (contador, productor, otro))

    catalogo = {r["tipo_reporte"] for r in cliente_m08.get("/reportes/catalogo", headers=h_cont).json()}
    assert "REPORTE_VALORACION_NIC41" in catalogo and "REPORTE_TELEMETRIA" not in catalogo
    assert "REPORTE_EJECUTIVO_CONSOLIDADO" in {
        r["tipo_reporte"] for r in cliente_m08.get("/reportes/catalogo", headers=h_prod).json()}

    nic41 = {"tipo_reporte": "REPORTE_VALORACION_NIC41", "formato": "PDF", "filtros": {"periodo_contable": 8102}}
    assert cliente_m08.post("/reportes", json=nic41, headers=h_prod).status_code == 403
    abierto = cliente_m08.post("/reportes", json={**nic41, "filtros": {"periodo_contable": 8103}}, headers=h_cont)
    assert abierto.status_code == 422 and abierto.json()["error_code"] == "PERIODO_NO_CERRADO"
    faltante = cliente_m08.post("/reportes", json={**nic41, "filtros": {}}, headers=h_cont)
    assert faltante.status_code == 400

    previa = cliente_m08.post("/reportes/vista-previa", json={"tipo_reporte": nic41["tipo_reporte"],
                                                              "filtros": nic41["filtros"]}, headers=h_cont)
    assert previa.status_code == 200 and previa.json()["numero_registros"] == 1
    assert {"dato": "Exportación contable", "valor": "Exportación pendiente"} in previa.json()["encabezado"]

    creado = cliente_m08.post("/reportes", json=nic41, headers=h_cont)
    assert creado.status_code == 201, creado.text
    reporte = creado.json()
    assert reporte["estado"] == "GENERADO" and len(reporte["partes"]) == 1
    url = f"/reportes/{reporte['id_reporte']}/partes/1/descarga"
    descarga = cliente_m08.get(url, headers=h_cont)
    assert descarga.status_code == 200 and descarga.content.startswith(b"%PDF")
    assert cliente_m08.get(url, headers=h_otro).status_code == 403
    db_session.execute(text("UPDATE modulo8.solicitudes_reportes SET fecha_expiracion = now() - interval '1 minute' "
                            "WHERE id_solicitud_reporte = :i"), {"i": reporte["id_reporte"]})
    assert cliente_m08.get(url, headers=h_cont).status_code == 410
    auditoria = db_session.execute(text("""SELECT detalle FROM modulo1.eventos WHERE tipo_evento = 43
        AND detalle->>'id_reporte' = :i"""), {"i": reporte["id_reporte"]}).scalar()
    assert auditoria["checksum"] == reporte["checksum_sha256"] and auditoria["filtros_aplicados"] == nic41["filtros"]


def test_catalogo_de_errores_solo_lo_edita_el_administrador(cliente_m08: TestClient, crear_usuario_db,
                                                            crear_auth_headers):
    admin, productor = crear_usuario_db(id_rol=1), crear_usuario_db(id_rol=2)
    h_admin, h_prod = crear_auth_headers(admin), crear_auth_headers(productor)
    cuerpo = {"idioma": "es-CO", "mensaje": "La especie elegida no está activa.", "texto_accion": "Configurar especies",
              "ruta_accion": "configuracion"}
    assert cliente_m08.put("/configuracion/mensajes-error/ESPECIE_INACTIVA", json=cuerpo,
                           headers=h_prod).status_code == 403
    guardado = cliente_m08.put("/configuracion/mensajes-error/ESPECIE_INACTIVA", json=cuerpo,
                               headers=h_admin)
    assert guardado.status_code == 200 and guardado.json()["ruta_accion"] == "configuracion"
    externo = cliente_m08.put("/configuracion/mensajes-error/ESPECIE_INACTIVA",
                              json={**cuerpo, "ruta_accion": "https://otro.example.com"}, headers=h_admin)
    assert externo.status_code == 400
    claves = {m["clave"] for m in cliente_m08.get("/configuracion/mensajes-error?idioma=es-CO",
                                                  headers=h_prod).json()}
    assert {"ESPECIE_INACTIVA", "ERROR_NO_CATALOGADO"} <= claves
