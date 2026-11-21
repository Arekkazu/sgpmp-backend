# | Fecha      | Nombre         | Que se hizo                                                          |
# |------------|----------------|----------------------------------------------------------------------|
# | 2026-11-12 | LuisfNarvaez01 | INC-M06-359-G79 RF-93: excluir_activos en el SQL de líneas y costos   |
"""INC-M06-359-G79 (#1084): el filtro ``excluir_activos`` saca al activo de las líneas y de los costos
del período en PostgreSQL, y el estado guardado lo resta y lo lista con sus montos."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

import pytest

from src.financial_valuation.application.use_cases.costos.registrar_costo_use_case import SolicitudCosto
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY, NIT, _activo, _configurar, _finca, _matriz, _pesaje, _precio, contador, m06,
)

pytestmark = pytest.mark.integration


def test_activo_excluido_sale_de_lineas_costos_y_estado(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    activos = []
    for _ in range(2):
        a = _activo(db_session, finca, uid, especie=especie, origen="nacimiento", costo=None)
        _pesaje(db_session, a, "400", -timedelta(minutes=5))
        activos.append(a)
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=10))
    for a in activos:
        m06.confirmar_reconocimiento().execute(a, uid)
    m06.registrar_costo().execute(SolicitudCosto(
        subtipo_costo="VETERINARIO", origen_costo="SERVICIO_TERCERO", monto_costo=D("50000"), fecha_costo=HOY,
        id_activo_biologico=activos[1], naturaleza_costo="MANTENIMIENTO", tercero_nit="900111222", tercero_dv="1",
        tercero_razon_social="Veterinaria de Prueba", factura_prefijo="FV", factura_numero="77",
        fecha_factura=HOY, fecha_vencimiento_factura=HOY + timedelta(days=30)), uid)
    periodo = m06.periodos.que_contiene(NIT, HOY).id_periodo_contable
    excluido = activos[1]

    lineas = m06.reportes.movimientos(periodo, {"excluir_activos": [excluido]})
    assert lineas and excluido not in {ln["id_activo_biologico"] for ln in lineas}
    assert excluido not in {c["id_activo_biologico"] for c in m06.costos.del_periodo(periodo, {"excluir_activos": [excluido]})}
    assert excluido in {c["id_activo_biologico"] for c in m06.costos.del_periodo(periodo, {})}

    completo = m06.constructor_estado.calcular(periodo, {})
    guardado = m06.constructor_estado.guardar(periodo, {}, uid, [{"id_activo_biologico": excluido, "motivo": "PENDIENTE_PRECIO"}])
    [listado] = guardado["activos_excluidos_cierre"]
    neto_excluido = D(listado["montos_excluidos"]["resultado_neto"])
    assert neto_excluido != 0
    assert guardado["resultado_neto"] == completo["resultado_neto"] - neto_excluido
