# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-84: script del grupo TC-M06-G16 (pytest + sandbox, rol Contador) |
"""
TC-M06-G16 - Cálculo del valor razonable menos costos de venta: parametrizado, manual y mixto.   RF-84 (CU03).   Casos: TC-M06-078 a TC-M06-081 (078b y 079b: tipo_costo=VENTA y referencia documental).

RF-84 no tiene un endpoint propio de cálculo con entradas: el cálculo se persiste al CONFIRMAR el reconocimiento (POST /finanzas/reconocimientos/{id},
con costos_manuales y justificacion) y se lee en GET /finanzas/activos/{id} (calculos). Bruto = 10.000.000,0000 (1 cabeza POR_CABEZA a 10.000.000,00).
Costos de M09 (PUT costos-venta): transporte 1,5 %, comisiones 2 %, impuestos 0,5 % -> 150.000 / 200.000 / 50.000. «otros» siempre es manual.
El método por componente queda en json_metodo_costo y el global en metodo_costo (PARAMETRIZADO / MANUAL / MIXTO). tipo_costo=VENTA no es un campo
del cálculo (obs).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G16/TC-M06-G16.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G16/reporte-TC-M06-G16.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

BRUTO = Decimal("10000000.0000")
JUSTIF = "Ajuste manual QA TC-M06 con soporte documental: cotización de transporte No. 123 del proveedor."
PCT = ("0.015", "0.02", "0.005")


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


def _metodos(c):
    m = c.get("json_metodo_costo") or {}
    return {k: m.get(k) for k in ("transporte", "comisiones", "impuestos", "otros")}


def _componentes(c):
    return tuple(dec(c[k]) for k in ("costo_transporte", "costo_comisiones", "costo_impuestos_transaccion", "otros_costos_disposicion"))


def _confirmar(env, esc, manuales, justif):
    ida, r = env.confirmar_manual(esc, manuales, justif)
    assert r.status in (200, 201), r
    c = env.calculo(ida)
    assert c is not None and dec(c["valor_razonable_bruto"]) == BRUTO, c
    c["_id_activo"] = ida
    return c


def test_TC_M06_078_calculo_parametrizado_con_otros_manual(env):
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=PCT)
    c = _confirmar(env, esc, {"otros": "100000"}, JUSTIF)
    assert _componentes(c) == (dec("150000"), dec("200000"), dec("50000"), dec("100000")), c
    assert dec(c["valor_neto"]) == dec("9500000.0000"), c
    assert _metodos(c) == {"transporte": "PARAMETRIZADO", "comisiones": "PARAMETRIZADO", "impuestos": "PARAMETRIZADO", "otros": "MANUAL"}, c
    assert c["metodo_costo"] == "MIXTO", c


def test_TC_M06_079_calculo_totalmente_manual(env):
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=None)       # especie sin parámetros en M09
    manuales = {"transporte": "120000", "comisiones": "180000", "impuestos": "40000", "otros": "60000"}
    c = _confirmar(env, esc, manuales, JUSTIF)
    assert dec(c["valor_neto"]) == dec("9600000.0000"), c
    assert c["metodo_costo"] == "MANUAL" and set(_metodos(c).values()) == {"MANUAL"}, c
    assert c.get("justificacion") == JUSTIF, "la justificación debe quedar guardada junto al cálculo"


def _claves(c):
    """Todas las claves del cálculo (incluye las del json del método) en minúscula."""
    ks = {str(k).lower() for k in c}
    ks |= {str(k).lower() for k in (c.get("json_metodo_costo") or {})}
    return ks


def test_TC_M06_078b_tipo_costo_venta_en_cada_componente(env):
    """Ficha 078 y RF-84 (entradas, Restricción 6, paso 7): cada costo del cálculo queda clasificado con tipo_costo = VENTA."""
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=PCT)
    c = _confirmar(env, esc, {"otros": "100000"}, JUSTIF)
    plano = {**(c.get("json_metodo_costo") or {}), **c}
    tipos = {k: v for k, v in plano.items() if str(k).lower().startswith("tipo_costo")}
    if not tipos:
        bloqueado("funcionalidad no implementada: el cálculo no guarda ni devuelve tipo_costo = VENTA por componente "
                  f"(RF-84 Restricción 6; ficha 078). Claves del cálculo: {sorted(c)}")
    assert all(str(v).upper() == "VENTA" for v in tipos.values()) and len(tipos) >= 4, tipos


def test_TC_M06_079b_referencia_documental_como_dato_propio(env):
    """Ficha 079 y RF-84 Restricción 4: la referencia documental de los costos manuales queda registrada junto al cálculo."""
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=None)
    manuales = {"transporte": "120000", "comisiones": "180000", "impuestos": "40000", "otros": "60000"}
    c = _confirmar(env, esc, manuales, JUSTIF)
    refs = [k for k in _claves(c) if "referencia" in k or "soporte" in k or "documental" in k]
    if not refs:
        bloqueado("funcionalidad no implementada: no existe un dato de referencia documental del costo manual; solo hay "
                  f"'justificacion' (texto libre, mín. 20 caracteres). Claves del cálculo: {sorted(c)}")


def test_TC_M06_080_metodos_mixtos_por_componente(env):
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=PCT)
    c = _confirmar(env, esc, {"comisiones": "250000", "otros": "60000"}, JUSTIF)
    assert _metodos(c) == {"transporte": "PARAMETRIZADO", "comisiones": "MANUAL", "impuestos": "PARAMETRIZADO", "otros": "MANUAL"}, c
    assert _componentes(c) == (dec("150000"), dec("250000"), dec("50000"), dec("60000")), c
    assert dec(c["valor_neto"]) == BRUTO - dec("510000"), "el neto debe usar los valores efectivamente aplicados"
    assert c["metodo_costo"] == "MIXTO"


def test_TC_M06_081_costos_en_cero_el_neto_es_el_bruto(env):
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=PCT)
    cero = {"transporte": "0", "comisiones": "0", "impuestos": "0", "otros": "0"}
    c = _confirmar(env, esc, cero, JUSTIF)
    assert dec(c["valor_neto"]) == BRUTO and c["estado"] == "CALCULADO", c
    assert _componentes(c) == (0, 0, 0, 0), c
    alertas = [e for e in env.auditoria(c["_id_activo"]) if str(e.get("severidad") or e.get("severidad_evento") or "").upper()
               in ("WARNING", "ADVERTENCIA", "ALERTA", "CRITICA", "CRITICO", "CRITICAL", "ERROR")]
    assert not alertas, f"con costos en 0,0000 y neto positivo no debe haber alerta: {alertas}"
    obs("Con los cuatro costos manuales en 0,0000 el sistema acepta el cálculo (sin exigir al menos un costo) y no emite alerta.")
