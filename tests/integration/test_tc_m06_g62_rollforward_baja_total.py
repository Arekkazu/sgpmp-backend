# | Fecha      | Nombre         | Que se hizo                                                           |
# |------------|----------------|-----------------------------------------------------------------------|
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G62 RF-92: la baja total deja el cierre en 0 y la conciliación cuadra |
"""TC-M06-G62 (#1107), RF-92 ¶50 / CA-4: inicio + movimientos ± variaciones = cierre por activo (±0,01).

La baja total no deja un cálculo nuevo; el informe tomaba como valor al cierre el último cálculo, de antes
de la baja, y a la vez restaba la baja: el activo quedaba descuadrado por todo su valor."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY, NIT, _activo, _configurar, _finca, _id, _matriz, _pesaje, _precio, contador, m06,
)

pytestmark = pytest.mark.integration


def _baja(db, id_activo: int, tipo: str) -> None:
    id_evento = _id()
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha) VALUES (:e, :a, now())"),
               {"e": id_evento, "a": id_activo})
    db.execute(text("""INSERT INTO modulo2.eventos_bajas (id_evento, cantidad_afectada, tipo)
                       VALUES (:e, 1, CAST(:t AS modulo2.enum_evento_bajas_tipo))"""), {"e": id_evento, "t": tipo})
    db.execute(text("SET LOCAL session_replication_role = origin"))


def test_baja_total_deja_el_cierre_en_cero_y_la_conciliacion_cuadra(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("3000000"))
    _pesaje(db_session, activo, "400", -timedelta(minutes=5))
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=10))
    m06.confirmar_reconocimiento().execute(activo, uid)  # VN 3.040.000 = compra 3.000.000 + diferencia 40.000

    _baja(db_session, activo, "muerte")
    assert m06.procesar_eventos().execute().get("PROCESADO") == 1
    periodo = m06.periodos.que_contiene(NIT, HOY).id_periodo_contable

    [datos] = [a for a in m06.reportes.datos_revelaciones(periodo)["activos"] if a["id_activo_biologico"] == activo]
    assert datos["valor_cierre"] == 0
    informe = m06.constructor_informe.construir(periodo, {"declaracion_sin_novedad": True})
    [fila] = [r for r in informe["contenido"]["parr_50_conciliacion"] if r["id_activo_biologico"] == activo]
    calculado = (fila["valor_inicio"] + fila["compras"] + fila["nacimientos_y_otros_ingresos"]
                 + fila["transformacion_biologica"] + fila["precio_mercado"] - fila["cosechas"] - fila["bajas"]
                 - fila["depreciacion_y_deterioro"])
    assert fila["bajas"] == D("3040000") and fila["valor_cierre"] == 0
    assert abs(calculado - fila["valor_cierre"]) <= D("0.01")
    assert not [a for a in informe["alertas_consistencia"] if a.get("id_activo_biologico") == activo]
