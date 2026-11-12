# | Fecha      | Nombre          | Que se hizo                                                                 |
# |------------|-----------------|-----------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-82: script del grupo TC-M06-G01 (pytest + sandbox, rol Contador)    |
"""
TC-M06-G01 - Reconocimiento inicial por origen financiero con precio de mercado vigente (flujo principal) y
confirmación del Contador.   RF-82 (CU01).   Casos: TC-M06-001 a TC-M06-005.

Cómo se prueba (API real de M6, /finanzas):
    GET  /finanzas/reconocimientos/propuestas/{id_activo}   -> propuesta (no persiste nada)
    POST /finanzas/reconocimientos/{id_activo}              -> confirma (genera las líneas de asiento)
El activo se registra por RF-33 (POST /activos-biologicos) dentro del run; el precio RF-89 (por cabeza), los costos
de venta, la clasificación y la matriz contable de la especie se cargan por la API de M06 con el Contador.

Valores: el precio RF-89 admite 2 decimales (DTO), por eso se usa 8.000.000,00 por cabeza (individual = 1 cabeza)
y costos de venta 2 % + 3 % + 1 %: neto esperado = 8.000.000 - 480.000 = 7.520.000,0000.

Criterio del RF (RFC-018): se verifica la línea de asiento que genera M06 (hecho + sentido + cuentas de la matriz).
El RF dice «Ingreso por donación» y «Ingreso por transformación biológica»; el backend usa el mismo hecho
RECONOCIMIENTO_NACIMIENTO para NACIMIENTO y DONACION (misma cuenta de la matriz): se documenta como observación.

Cómo correrlo (desde la raíz del repo, ver comandos en la nota de entrega):
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G01/TC-M06-G01.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G01/reporte-TC-M06-G01.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

PRECIO = "8000000.00"
NETO = neto_esperado(PRECIO)                       # 7.520.000,0000
COSTOS_VENTA = q4(PRECIO) - NETO                   # 480.000,0000
COSTO_COMPRA = "2500000.0000"
CTA_NACIMIENTO = CUENTAS_MATRIZ[("RECONOCIMIENTO_NACIMIENTO", "UNICO")]     # (Activo Biológico, Ingreso por transformación biológica)
CTA_TRASLADO = CUENTAS_MATRIZ[("RECONOCIMIENTO_NACIMIENTO", "TRASLADO")]    # (Activo Biológico, Cuenta de traslado interno)
_compra: dict = {}


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


@pytest.fixture(scope="module")
def esc(env):
    return env.escenario(categoria="POR_CABEZA", precio=PRECIO)


def _propuesta_ok(env, ida, hecho=None, sentido=None, valor=None):
    p = env.propuesta(ida)
    assert p.status == 200, p
    assert p.get("es_confirmable") is True, f"la propuesta quedó bloqueada: {p.get('bloqueos')}"
    assert p.get("indicador_valoracion") == "VALOR_RAZONABLE", p
    assert dec(p.get("valor_inicial")) == NETO, f"valor neto esperado {NETO}, recibido {p.get('valor_inicial')}"
    assert dec(p.get("costos_venta")) == COSTOS_VENTA, p
    assert p.get("clasificacion") == "PRODUCCION", p
    if hecho:
        assert hechos(p) == [(hecho, sentido, dec(valor))], f"hechos propuestos: {hechos(p)}"
    # La propuesta no se contabiliza hasta que el Contador confirme.
    h = env.historial(ida)
    assert lineas_de(h) == [], f"hay asientos antes de confirmar: {lineas_de(h)}"
    assert not h.get("reconocimientos"), "hay un reconocimiento antes de confirmar"
    return p


def _confirmar_y_asiento(env, ida):
    """La propuesta no expone cuentas: el asiento de la ficha se verifica en la línea que genera la confirmación (misma matriz RF-109)."""
    r = env.confirmar(ida)
    assert r.status == 201, f"la confirmación debía responder 201: {r}"
    lineas = r.get("lineas") or []
    assert len(lineas) == 1, f"se esperaba 1 línea de asiento y hay {len(lineas)}: {lineas}"
    return lineas[0]


def test_TC_M06_001_compra_con_precio_de_mercado(env, esc):
    env.presupuesto()
    ida = env.activo(esc, origen="compra", costo=COSTO_COMPRA, soporte="Factura QA-M06-001")
    _compra["id"] = ida
    # COMPRA: la compra entra por su factura (RF-90); M06 registra la diferencia valor neto - costo.
    _propuesta_ok(env, ida, "RECONOCIMIENTO_DIFERENCIA", "GANANCIA", NETO - dec(COSTO_COMPRA))


def test_TC_M06_002_nacimiento_con_precio_costo_nulo(env, esc):
    env.presupuesto()
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    p = _propuesta_ok(env, ida, "RECONOCIMIENTO_NACIMIENTO", "UNICO", NETO)
    assert p.get("costo_adquisicion") in (None, 0, "0", "0.0000"), "NACIMIENTO no debe tener costo"
    ln = _confirmar_y_asiento(env, ida)
    assert (ln["cuenta_debito"], ln["cuenta_credito"]) == CTA_NACIMIENTO, \
        f"NACIMIENTO: débito Activo Biológico / crédito Ingreso por transformación biológica {CTA_NACIMIENTO}; el asiento fue {ln}"


def test_TC_M06_003_donacion_con_costo_y_soporte(env, esc):
    env.presupuesto()
    ida = env.activo(esc, origen="donacion", costo="1200000.0000", soporte="Acta de donación QA-M06-003")
    p = _propuesta_ok(env, ida)
    assert p.get("soporte_documental"), "la propuesta debe mostrar el soporte documental del activo"
    ln = _confirmar_y_asiento(env, ida)
    assert ln["cuenta_debito"] == CTA_NACIMIENTO[0], f"el débito debe ser Activo Biológico: {ln}"
    assert ln["cuenta_credito"] != CTA_NACIMIENTO[1], (
        "DONACION: el crédito debe ser «Ingreso por donación», distinto del «Ingreso por transformación biológica» de NACIMIENTO. "
        f"El backend propuso el hecho {ln['tipo_hecho']}/{ln['sentido']} y acreditó la misma cuenta que NACIMIENTO ({ln['cuenta_credito']}).")


@pytest.mark.parametrize("con_costo", [True, False], ids=["con_costo_900000", "sin_costo"])
def test_TC_M06_004_transferencia_interna_costo_opcional(env, esc, con_costo):
    env.presupuesto()
    kw = {"costo": "900000.0000", "soporte": "Acta de traslado QA-M06-004"} if con_costo else {"costo": None, "soporte": None}
    ida = env.activo(esc, origen="transferencia_interna", **kw)
    # El costo ausente no bloquea porque existe precio; el activo entra contra la cuenta de traslado interno.
    _propuesta_ok(env, ida)
    ln = _confirmar_y_asiento(env, ida)
    assert ln["cuenta_debito"] == CTA_NACIMIENTO[0], f"el débito debe ser Activo Biológico: {ln}"
    assert (ln["cuenta_debito"], ln["cuenta_credito"]) == CTA_TRASLADO, \
        f"TRANSFERENCIA_INTERNA: crédito a la Cuenta de traslado interno {CTA_TRASLADO}; el asiento fue {ln}"


def test_TC_M06_005_confirmacion_del_contador(env, esc):
    env.presupuesto()
    ida = _compra.get("id") or env.activo(esc, origen="compra", costo=COSTO_COMPRA, soporte="Factura QA-M06-005")
    # Ficha 005: el activo está pendiente de reconocimiento (bandeja de propuestas) hasta que el Contador confirma.
    bandeja = env.call("GET", "/finanzas/reconocimientos/propuestas", "contador")
    assert bandeja.status == 200, bandeja
    assert ida in {x.get("id_activo_biologico") for x in lista_de(bandeja.data, "propuestas")}, \
        f"antes de confirmar el activo {ida} debe estar pendiente en la bandeja de propuestas: {bandeja.text[:300]}"
    r = env.confirmar(ida)
    assert r.status == 201, f"la confirmación debía responder 201: {r}"
    assert r.get("indicador_valoracion") == "VALOR_RAZONABLE", r
    assert dec(r.get("valor_inicial")) == NETO, r
    assert str(r.get("fecha_reconocimiento"))[:10] == str(hoy()), f"fecha del reconocimiento {r.get('fecha_reconocimiento')} != hoy {hoy()}"
    lineas = r.get("lineas") or []
    assert len(lineas) == 1, f"se esperaba 1 línea de asiento y hay {len(lineas)}: {lineas}"
    ln = lineas[0]
    assert (ln["tipo_hecho"], ln["sentido"]) == ("RECONOCIMIENTO_DIFERENCIA", "GANANCIA"), ln
    assert dec(ln["valor"]) == NETO - dec(COSTO_COMPRA), f"el asiento debía ser por la propuesta: {ln}"
    clave = ("RECONOCIMIENTO_DIFERENCIA", "GANANCIA")
    if clave in esc.cuentas:
        assert ln["estado"] == "REGISTRADA", f"línea sin cuentas: {ln}"
        assert (ln["cuenta_debito"], ln["cuenta_credito"]) == esc.cuentas[clave], f"cuentas de la matriz: {ln}"
    else:
        obs("la matriz de la especie no se pudo cargar por API; no se verificaron las cuentas.")
    # El reconocimiento queda ligado al activo, al Contador y a la fecha del día; el activo sale de la bandeja.
    h = env.historial(ida)
    assert len(h.get("reconocimientos") or []) == 1, h.get("reconocimientos")
    rec = h["reconocimientos"][0]
    if "estado" in rec:
        assert rec["estado"] == "CONFIRMADO", rec
    if "id_usuario" in rec:
        assert rec["id_usuario"] == CUENTAS["ingeniero"][2], f"el reconocimiento debe quedar a nombre del Contador: {rec}"
    else:
        obs(f"El historial no expone id_usuario del reconocimiento (campos: {sorted(rec)}); el Contador queda en la auditoría.")
    assert "RECONOCIMIENTO_INICIAL" in env.tipos_auditoria(ida), "falta el evento RECONOCIMIENTO_INICIAL en RF-94"
    bandeja = env.call("GET", "/finanzas/reconocimientos/propuestas", "contador")
    assert bandeja.status == 200, bandeja
    assert ida not in {x.get("id_activo_biologico") for x in lista_de(bandeja.data, "propuestas")}, \
        "tras confirmar, el activo debe salir de PENDIENTE_RECONOCIMIENTO (bandeja de propuestas)"
    # Una segunda confirmación del mismo activo no duplica (FA-1): se prueba a fondo en TC-M06-G05.
    assert env.confirmar(ida).status == 409
