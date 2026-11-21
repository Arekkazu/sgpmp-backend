# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-13 | Arekkazu | QA-M06 CU13 H-01/H-02 C3 RF-94: precios en la bitácora del período y autor por nombre |
"""QA M06 (13-11): un precio registrado por otro Contador aparece en la bitácora del período de un titular
(CU13 H-01), firmado con su nombre y no con «Usuario sin nombre registrado» (C3), y se puede elegir en el
filtro por usuario (CU13 H-02). La consulta corre como ``sgpmp_app`` para que la RLS sea la de producción:
el Contador no puede leer ``modulo1.usuarios`` de otras personas."""
from __future__ import annotations

import calendar
from datetime import date

import pytest
from sqlalchemy import text

from src.shared.database import declarar_identidad
from tests.integration.test_m06_flujo_nic41_integration import HOY, _finca, _precio, contador, m06  # noqa: F401

pytestmark = pytest.mark.integration

NIT_QA = "900987654"  # DV DIAN = 7


def _periodo(m06, id_usuario: int, anio: int, mes: int):
    fin = date(anio, mes, calendar.monthrange(anio, mes)[1])
    return m06.periodos.crear(NIT_QA, "MENSUAL", date(anio, mes, 1), fin, id_usuario)


def test_precio_de_otro_contador_en_la_bitacora_del_periodo_con_su_nombre(db_session, m06, contador, crear_usuario_db):
    autora = crear_usuario_db(id_rol=5, estado=2, nombre="Autora", apellidos="Del Precio")
    _finca(db_session, contador["id_usuario"], nit=NIT_QA, dv="7")
    periodo = _periodo(m06, contador["id_usuario"], HOY.year, HOY.month)
    precio = _precio(m06, autora["id_usuario"], 2, "9100", HOY)

    declarar_identidad(db_session, contador["id_usuario"], "Contador")
    db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
    try:
        assert db_session.execute(text(
            "SELECT count(*) FROM modulo1.usuarios WHERE id_usuario = :u"), {"u": autora["id_usuario"]}).scalar_one() == 0
        consulta = m06.consultar_auditoria()
        bitacora = consulta.execute({"id_periodo_contable": periodo.id_periodo_contable,
                                     "tipo_evento": ["PRECIO_REGISTRADO"]}, 1, 500, True)
        actores = consulta.actores(periodo.id_periodo_contable)
    finally:
        db_session.execute(text("RESET ROLE"))

    [evento] = [e for e in bitacora["eventos"] if e["monto_afectado"] == 9100 and e["fecha_hora"].date() == HOY]
    assert evento["actor"] == "Autora Del Precio"
    assert {"id_usuario": autora["id_usuario"], "nombre": "Autora Del Precio"} in actores
    assert precio["estado"] == "ACTIVO"


def test_precio_fuera_de_las_fechas_del_periodo_no_entra_en_su_bitacora(db_session, m06, contador):
    _finca(db_session, contador["id_usuario"], nit=NIT_QA, dv="7")
    periodo = _periodo(m06, contador["id_usuario"], HOY.year - 1, HOY.month)
    _precio(m06, contador["id_usuario"], 2, "9200", HOY)

    bitacora = m06.consultar_auditoria().execute({"id_periodo_contable": periodo.id_periodo_contable,
                                                  "tipo_evento": ["PRECIO_REGISTRADO"]}, 1, 500, True)

    assert bitacora["eventos"] == []
