# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-13 | Leandro | TC-M06-G52 RF-91: comprobar auditoría vinculada, ausencia y recuperación de la fuente. |
"""Regresión de #1104 con las bitácoras y cadenas persistidas en PostgreSQL."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.financial_valuation.domain.entities.contabilidad import LineaAsiento
from src.financial_valuation.infrastructure.routers.m06_router import router
from tests.integration.test_inc_m03_104_g165_motor_calidad import equipo_g165, insertar_serie
from tests.integration.test_inc_m06_281_g68_valor_libros_cero import _evento_sanitario
from tests.integration.test_m06_flujo_nic41_integration import (
    HOY, NIT, _activo, _auditar_pesaje, _configurar, _finca, _matriz, _pesaje, contador, m06,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def rutas_m06(integration_app):
    if not any(getattr(ruta, "path", None) == "/finanzas/lineas/{id_linea}/cadena" for ruta in integration_app.routes):
        integration_app.include_router(router)


@pytest.fixture
def linea_manual(request, db_session, m06, contador):
    usuario = contador["id_usuario"]
    finca = _finca(db_session, usuario)
    _matriz(m06, usuario)
    activo = _activo(db_session, finca, usuario, especie=2, origen="compra", costo=Decimal("1000"))
    evento = _pesaje(db_session, activo, "40")
    periodo = m06.contabilizador.periodo_para(NIT, HOY, usuario).id_periodo_contable
    linea = m06.contabilizador.asentar(LineaAsiento(
        tipo_hecho="BAJA_ACTIVO", sentido="UNICO", valor=Decimal("1000"), fecha_hecho=HOY,
        id_periodo_contable=periodo, id_activo_biologico=activo, id_especie=2, id_finca=finca,
        numero_id_tributaria=NIT, tabla_origen="procesamientos_eventos_m02", id_origen=evento,
        tipo_evidencia=getattr(request, "param", "REGISTRO_MANUAL"), id_usuario=usuario,
    ), usuario)
    return activo, evento, periodo, linea.id_linea_asiento_nic41


def test_solo_la_auditoria_del_evento_verifica_la_linea(
    client, crear_auth_headers, db_session, m06, contador, linea_manual,
):
    usuario = contador["id_usuario"]
    headers = crear_auth_headers(contador)
    activo, evento, periodo, linea = linea_manual
    otro_evento = _pesaje(db_session, activo, "41")
    _auditar_pesaje(db_session, activo, otro_evento, usuario)
    m06.asientos.cambiar_trazabilidad(linea, "VERIFICADO")

    ruta_verificacion = f"/finanzas/periodos/{periodo}/trazabilidad"
    ruta_cadena = f"/finanzas/lineas/{linea}/cadena"
    verificacion = client.post(ruta_verificacion, headers=headers)
    assert verificacion.status_code == 200, verificacion.text
    respuesta = verificacion.json()
    assert respuesta["verificadas"] == 0
    assert respuesta["pendientes"][0]["faltantes"] == ["auditoria_m02"]
    cadena = client.get(ruta_cadena, headers=headers)
    assert cadena.status_code == 200, cadena.text
    assert cadena.json()["estado_trazabilidad"] == "PENDIENTE_TRAZABILIDAD"

    auditoria = _auditar_pesaje(db_session, activo, evento, usuario)
    verificacion = client.post(ruta_verificacion, headers=headers)
    assert verificacion.status_code == 200, verificacion.text
    assert verificacion.json() == {"verificadas": 1, "pendientes": []}
    detalle = client.get(ruta_cadena, headers=headers)
    assert detalle.status_code == 200, detalle.text
    cadena = detalle.json()
    assert cadena["estado_trazabilidad"] == "VERIFICADO"
    assert cadena["eslabones"]["auditoria_m02"] is True
    assert cadena["eslabones"]["ids"]["id_auditoria_m02"] == auditoria


def test_error_sql_en_la_fuente_deja_verificacion_pendiente(
    db_session, m06, contador, linea_manual, monkeypatch,
):
    from src.financial_valuation.infrastructure.repositories import trazabilidad_repository

    usuario = contador["id_usuario"]
    activo, evento, periodo, linea = linea_manual
    _auditar_pesaje(db_session, activo, evento, usuario)
    consulta = trazabilidad_repository.fila

    def falla_temporalmente(db, sql, parametros):
        if "FROM modulo2.bitacora_auditoria_m02" in sql:
            db.execute(text("SELECT modulo2.fn_fuente_g52_indisponible()"))
        return consulta(db, sql, parametros)

    with monkeypatch.context() as cambios:
        cambios.setattr(trazabilidad_repository, "fila", falla_temporalmente)
        respuesta = m06.verificar_trazabilidad().execute(periodo, usuario)

    assert respuesta["pendientes"][0]["faltantes"] == ["auditoria_m02"]
    cadena = m06.trazabilidad.cadena(linea)
    assert cadena["estado_trazabilidad"] == "VERIFICACION_PENDIENTE"
    assert cadena["estado_verificacion"] == "PENDIENTE"
    assert cadena["eslabones"]["fuentes_no_disponibles"] == ["auditoria_m02"]
    assert db_session.execute(text("""
        SELECT datos_nuevos->>'resultado' FROM modulo6.auditorias_financieras
         WHERE tipo_evento = 'CADENA_TRAZABILIDAD_VERIFICADA' AND id_referencia = :l
    """), {"l": linea}).scalar_one() == "FUENTE_NO_DISPONIBLE"
    assert m06.verificar_trazabilidad().execute(periodo, usuario) == {"verificadas": 1, "pendientes": []}


@pytest.mark.parametrize("linea_manual", ["IOT_DIRECTO"], indirect=True)
def test_iot_exige_auditoria_de_una_lectura_apta_del_activo(
    db_session, m06, contador, linea_manual, equipo_g165,
):
    activo, evento, periodo, linea = linea_manual
    usuario = contador["id_usuario"]
    sensor = equipo_g165["sensor"]
    dispositivo = equipo_g165["dispositivo"]
    lectura_apta = insertar_serie(db_session, equipo_g165, [22], 21, gap=1)
    lectura_no_apta = db_session.execute(text("""
        SELECT id_telemetria FROM modulo3.telemetrias WHERE id_sensor = :s AND valor_crudo = 22
    """), {"s": sensor}).scalar_one()
    db_session.execute(text("""
        INSERT INTO modulo2.asociaciones_activos_sensores
            (id_sensor, id_usuario, fecha_inicio, id_activo_biologico, tipo, tipo_activo, dispositivo_iot_id)
        VALUES (:s, :u, now() - interval '3 minutes', :a, 'directa', 'INDIVIDUAL', :d)
    """), {"s": sensor, "u": contador["id_usuario"], "a": activo, "d": dispositivo})
    db_session.execute(text("""
        INSERT INTO modulo3.telemetria_calidad
            (id_telemetria, id_sensor, indice_calidad, clasificacion_calidad, apto_para_nic41)
        VALUES (:apta, :s, 100, 'APTO', true), (:no_apta, :s, 0, 'NO_APTO', false)
    """), {"apta": lectura_apta, "no_apta": lectura_no_apta, "s": sensor})
    _auditar_pesaje(db_session, activo, evento, usuario)

    def auditar_lectura(lectura):
        return db_session.execute(text("""
            INSERT INTO modulo3.bitacora_auditoria_iot
                (tipo_evento, resultado, fecha_hora, entidad_afectada_tipo, entidad_afectada_id, hash_integridad)
            VALUES ('EVALUACION_CALIDAD_COMPLETADA', 'EXITOSO', now(), 'CALIDAD_DATO', :l, repeat('a', 64))
            RETURNING id_evento
        """), {"l": str(lectura)}).scalar_one()

    auditar_lectura(lectura_no_apta)
    resultado = m06.verificar_trazabilidad().execute(periodo, usuario)
    assert resultado["pendientes"][0]["faltantes"] == ["auditoria_m03"]
    assert m06.trazabilidad.cadena(linea)["eslabones"]["ids"]["ids_lectura_iot"] == [lectura_apta]

    auditoria = auditar_lectura(lectura_apta)
    assert m06.verificar_trazabilidad().execute(periodo, usuario) == {"verificadas": 1, "pendientes": []}
    eslabones = m06.trazabilidad.cadena(linea)["eslabones"]
    assert eslabones["ids"]["id_auditoria_m03"] == str(auditoria)
    assert eslabones["ids"]["id_lectura_auditada"] == lectura_apta

    id_finca = db_session.execute(text("""
        SELECT id_finca FROM modulo6.lineas_asiento_nic41 WHERE id_linea_asiento_nic41 = :l
    """), {"l": linea}).scalar_one()
    otro_activo = _activo(
        db_session, id_finca, contador["id_usuario"], especie=2, origen="compra", costo=Decimal("1000"),
    )
    db_session.execute(text("""
        INSERT INTO modulo3.vinculaciones_lecturas
            (id_telemetria, modelo_manejo, id_activo_biologico, id_infraestructura,
             fecha_inicio_vinculacion, mecanismo_vinculacion, estado_vinculacion, fecha_creacion)
        VALUES (:l, 'INDIVIDUAL', :a, :f, now(), 'MANUAL', 'CONFIRMADA', now())
    """), {"l": lectura_apta, "a": otro_activo, "f": id_finca})
    resultado = m06.verificar_trazabilidad().execute(periodo, usuario)
    assert resultado["pendientes"][0]["faltantes"] == ["lecturas_nic41", "auditoria_m03"]


def test_rf73_corresponde_al_activo_y_a_la_fecha_del_evento(db_session, m06, contador):
    usuario = contador["id_usuario"]
    finca = _finca(db_session, usuario)
    _configurar(m06, usuario, especie=3, vida=24)
    activo = _activo(db_session, finca, usuario, especie=3, origen="compra", costo=Decimal("10000000"))
    _pesaje(db_session, activo, "30")
    m06.confirmar_reconocimiento().execute(activo, usuario)
    evento = _evento_sanitario(db_session, activo)
    m06.registrar_deterioro().execute(
        activo, evento, Decimal("1000000"), "Pérdida de capacidad productiva documentada", usuario,
    )
    [linea] = [ln for ln in m06.asientos.del_activo(activo) if ln.tipo_evidencia == "EVENTO_SANITARIO"]
    fecha = db_session.execute(text(
        "SELECT fecha FROM modulo2.eventos_activos WHERE id_eventos = :e"
    ), {"e": evento}).scalar_one()

    def auditar_inferencia(id_activo, instante):
        return db_session.execute(text("""
            INSERT INTO modulo4.eventos_auditoria_m04
                (tipo_evento, fecha_evento, tipo_actor, id_sistema, id_referencia, entidad_referencia,
                 payload_evento, resultado_operacion, hash_evento)
            VALUES ('INFERENCIA_EJECUTADA', :fecha, 'SISTEMA', 'M04', :inferencia, 'resultado_inferencia',
                    jsonb_build_object('activo_biologico_id', CAST(:activo AS integer)), 'EXITOSO', repeat('a', 64))
            RETURNING id_evento
        """), {"fecha": instante, "inferencia": str(uuid4()), "activo": id_activo}).scalar_one()

    auditar_inferencia(activo + 1, fecha)
    auditar_inferencia(activo, fecha - timedelta(days=1))
    resultado = m06.verificar_trazabilidad().execute(linea.id_periodo_contable, usuario)
    [pendiente] = [p for p in resultado["pendientes"] if p["id_linea"] == linea.id_linea_asiento_nic41]
    assert pendiente["faltantes"] == ["auditoria_m04"]

    auditoria = auditar_inferencia(activo, fecha)
    m06.verificar_trazabilidad().execute(linea.id_periodo_contable, usuario)
    cadena = m06.trazabilidad.cadena(linea.id_linea_asiento_nic41)
    assert cadena["estado_trazabilidad"] == "VERIFICADO"
    assert cadena["eslabones"]["ids"]["id_auditoria_m04"] == str(auditoria)
    assert cadena["eslabones"]["ids"]["id_evento_sanitario"] == evento
