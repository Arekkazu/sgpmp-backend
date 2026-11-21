# | Fecha      | Nombre         | Que se hizo                                                         |
# |------------|----------------|---------------------------------------------------------------------|
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-302-G01 RF-82: la donación acredita su propia cuenta        |
"""INC-M06-302-G01 (#989): la donación se asienta con ``RECONOCIMIENTO_DONACION``, no con el nacimiento.

Antes, al confirmar el reconocimiento de un activo donado, la línea salía como
``RECONOCIMIENTO_NACIMIENTO / UNICO`` y acreditaba la cuenta de nacimientos (4251 aquí). Con un
hecho propio, la matriz le asigna «Ingreso por donación» (4255 aquí)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

import pytest

from src.financial_valuation.application.services.propuesta_reconocimiento import ProponedorReconocimiento
from tests.integration.test_m06_flujo_nic41_integration import (
    HOY, _activo, _configurar, _finca, _matriz, _pesaje, _precio, contador, m06,  # noqa: F401 (fixtures)
)

pytestmark = pytest.mark.integration


def test_hechos_de_la_donacion_y_del_nacimiento_son_distintos():
    assert ProponedorReconocimiento._hechos_valor_razonable("donacion", D("100"), None) == [
        ("RECONOCIMIENTO_DONACION", "UNICO", D("100"))]
    assert ProponedorReconocimiento._hechos_valor_razonable("nacimiento", D("100"), None) == [
        ("RECONOCIMIENTO_NACIMIENTO", "UNICO", D("100"))]


def test_confirmar_donacion_acredita_la_cuenta_de_ingreso_por_donacion(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    m06.guardar_asignacion().execute("RECONOCIMIENTO_DONACION", "UNICO", None, None, "1586", "4255", uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="donacion", costo=D("1000000"))
    _pesaje(db_session, activo, "400", -timedelta(minutes=5))
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=10))

    propuesta = m06.propuestas().de_activo(activo, uid)
    assert [h["tipo_hecho"] for h in propuesta["hechos"]] == ["RECONOCIMIENTO_DONACION"]

    reconocido = m06.confirmar_reconocimiento().execute(activo, uid)
    assert [(ln["cuenta_debito"], ln["cuenta_credito"], ln["estado"]) for ln in reconocido["lineas"]] == [
        ("1586", "4255", "REGISTRADA")]
    [linea] = m06.asientos.del_activo(activo)
    assert (linea.tipo_hecho, linea.sentido) == ("RECONOCIMIENTO_DONACION", "UNICO")
