# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-14 | Arekkazu | INC-M06-363-G27 / INC-M06-365-G21 RF-84/85: cosecha retomada con el precio y costos por región, en PostgreSQL real |
# | 2026-11-15 | Arekkazu | INC-M06-365-G21 RF-84: región agrupada («Huila - Tolima») por cada departamento |
"""Contra PostgreSQL real, dentro de una sola transacción como el sandbox de QA (``db_session`` usa SAVEPOINT).

- INC-M06-363-G27 (TC-M06-120c/120d): la cosecha pendiente por falta de precio se reconoce al registrar el precio,
  manual justificado o de mercado. Antes el precio quedaba con la misma hora (``now()``) que el último intento y la
  cola no la retomaba.
- INC-M06-365-G21 (TC-M06-098): los costos de venta se buscan por la región (departamento de la finca) del activo,
  con el GENERAL de respaldo, sin distinguir mayúsculas ni tildes.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from src.financial_valuation.application.use_cases.precios.registrar_precio_use_case import SolicitudPrecio
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY,
    _activo,
    _configurar,
    _finca,
    _matriz,
    _pesaje,
    _precio,
    contador,
    m06,
)


def _cosecha(db, id_activo: int, id_metrica: int, cantidad: str) -> int:
    id_evento = uuid.uuid4().int % (10**8) + 10**8
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("""INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha)
                       VALUES (:e, :a, now())"""), {"e": id_evento, "a": id_activo})
    db.execute(text("""INSERT INTO modulo2.eventos_productivos (id_evento, cantidad, id_metrica_produccion, id_ciclo_productivo)
                       VALUES (:e, :c, :m, 1)"""), {"e": id_evento, "c": D(cantidad), "m": id_metrica})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return id_evento


def _resultado(db, id_evento: int) -> tuple[str, str]:
    return tuple(db.execute(text("SELECT resultado, detalle FROM modulo6.procesamientos_eventos_m02 WHERE id_evento = :e"),
                            {"e": id_evento}).one())


@pytest.mark.parametrize("fuente", ["ESTIMADA", "MERCADO_ACTIVO"])
def test_la_cosecha_pendiente_se_reconoce_al_registrar_el_precio(db_session, m06, contador, fuente):
    uid, especie = contador["id_usuario"], 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie, clasificacion="PRODUCCION")
    _matriz(m06, uid)
    m06.guardar_asignacion().execute("PRODUCTO_AGRICOLA", "UNICO", None, None, "1435", "4255", uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("3000000"))
    _pesaje(db_session, activo, "450", -timedelta(minutes=10))
    _precio(m06, uid, especie, "9500", HOY - timedelta(days=10))
    m06.confirmar_reconocimiento().execute(activo, uid)
    id_metrica = db_session.execute(text("""
        INSERT INTO modulo9.metricas_produccion (nombre, unidad_medida, tipo_medicion, tiene_estado, id_especie)
        VALUES (:n, 'L', 'VOLUMEN', false, :e) RETURNING id_metrica_produccion"""),
        {"n": f"Leche {uuid.uuid4().hex[:6]}", "e": especie}).scalar_one()
    cosecha = _cosecha(db_session, activo, id_metrica, "200")

    m06.procesar_eventos().execute()
    resultado, detalle = _resultado(db_session, cosecha)
    assert resultado == "MEDICION_PENDIENTE" and "Falta un precio de mercado del producto" in detalle, detalle

    m06.registrar_precio().execute(SolicitudPrecio(
        id_especie=especie, categoria="PRODUCTO", precio_unitario=D("3500"), fecha_vigencia=HOY - timedelta(days=1),
        fuente=fuente, evidencia_documental="Cotización de la cooperativa lechera",
        id_metrica_produccion=id_metrica, confirmar_desviacion=True,
        justificacion_estimacion=("Precio estimado con el promedio de las tres últimas liquidaciones de la "
                                  "cooperativa lechera de la zona") if fuente == "ESTIMADA" else None), uid)
    m06.procesar_eventos().execute()

    assert _resultado(db_session, cosecha)[0] == "PROCESADO"
    producto = db_session.execute(text("""SELECT precio_mercado_producto, valor_producto FROM
        modulo6.reconocimientos_productos_agricolas WHERE id_evento_productivo = :e"""), {"e": cosecha}).one()
    assert producto.precio_mercado_producto == D("3500")
    assert producto.valor_producto == D("665000.00")  # 200 L × 3.500 − 5 % de transporte
    assert db_session.execute(text("""SELECT count(*) FROM modulo6.lineas_asiento_nic41
        WHERE tabla_origen = 'reconocimientos_productos_agricolas' AND id_origen = (SELECT id_reconocimiento_producto_agricola
        FROM modulo6.reconocimientos_productos_agricolas WHERE id_evento_productivo = :e)"""), {"e": cosecha}).scalar() == 1
    assert cosecha not in {c["id_evento"] for c in m06.eventos.cosechas_pendientes()}

    m06.procesar_eventos().execute()  # reprocesar no duplica el reconocimiento
    assert db_session.execute(text("""SELECT count(*) FROM modulo6.reconocimientos_productos_agricolas
                                      WHERE id_evento_productivo = :e"""), {"e": cosecha}).scalar() == 1


def test_costos_de_venta_por_region_con_general_de_respaldo(db_session, m06, contador):
    uid, especie = contador["id_usuario"], 2
    m06.guardar_costos_venta().execute(especie, D("0.05"), D("0"), D("0"), uid)
    m06.guardar_costos_venta().execute(especie, D("0.03"), D("0"), D("0"), uid, "Córdoba")

    assert m06.config.costos_venta_vigentes(especie, " cordoba ").pct_transporte == D("0.03")
    assert m06.config.costos_venta_vigentes(especie, "Huila").pct_transporte == D("0.05")
    assert m06.config.costos_venta_vigentes(especie, None).pct_transporte == D("0.05")

    # Otra grafía de la misma región reemplaza al vigente: nunca quedan dos para la misma especie y región.
    m06.guardar_costos_venta().execute(especie, D("0.02"), D("0"), D("0"), uid, "CORDOBA")
    assert m06.config.costos_venta_vigentes(especie, "Córdoba").pct_transporte == D("0.02")
    assert db_session.execute(text("""SELECT count(*) FROM modulo6.parametros_costos_venta WHERE id_especie = :e
        AND es_activo AND region <> 'GENERAL'"""), {"e": especie}).scalar() == 1

    # Región agrupada, como las que tiene TEST: vale para cada departamento que nombra; la exacta le gana.
    m06.guardar_costos_venta().execute(especie, D("0.04"), D("0"), D("0"), uid, "Huila - Tolima")
    assert m06.config.costos_venta_vigentes(especie, "Tolima").pct_transporte == D("0.04")
    assert m06.config.costos_venta_vigentes(especie, "huila").pct_transporte == D("0.04")
    m06.guardar_costos_venta().execute(especie, D("0.01"), D("0"), D("0"), uid, "Huila")
    assert m06.config.costos_venta_vigentes(especie, "Huila").pct_transporte == D("0.01")
    assert m06.config.costos_venta_vigentes(especie, "Tolima").pct_transporte == D("0.04")


def test_el_calculo_usa_los_costos_de_la_region_de_la_finca(db_session, m06, contador):
    uid, especie = contador["id_usuario"], 2
    finca = _finca(db_session, uid)
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("""UPDATE modulo9.fincas SET ubicacion = '{"departamento": "Córdoba", "municipio": "Montería"}'
                               WHERE id_finca = :f"""), {"f": finca})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    _configurar(m06, uid, especie)  # GENERAL al 5 %
    m06.guardar_costos_venta().execute(especie, D("0.03"), D("0"), D("0"), uid, "cordoba")
    _matriz(m06, uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("3000000"))
    _pesaje(db_session, activo, "450", -timedelta(minutes=10))
    _precio(m06, uid, especie, "9500", HOY - timedelta(days=10))

    assert m06.activos.obtener(activo).region == "Córdoba"
    m06.confirmar_reconocimiento().execute(activo, uid)
    calculo = m06.valoraciones.ultimo_calculo(activo)
    assert calculo.costo_transporte == (calculo.valor_razonable_bruto * D("0.03")).quantize(D("0.0001"))
