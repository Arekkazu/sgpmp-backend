# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-84: script del grupo TC-M06-G19 (pytest + sandbox, rol Contador) |
"""
TC-M06-G19 - Tipificación de costos: tipo_costo VENTA y exclusión de MANTENIMIENTO.   RF-84 (CU03 FA-04) y RF-90.   Casos: TC-M06-091 a TC-M06-093.

La clasificación del costo (tipo_costo del RF-84) es `naturaleza_costo` de RF-90 en POST /finanzas/costos: MANTENIMIENTO / INVERSION / VENTA, DERIVADA del
subtipo (RF-90: «derivada del catálogo según subtipo_costo, o declarada por el Contador si OTRO»); con subtipo OTRO sin naturaleza el costo queda
PENDIENTE_CLASIFICACION (RF-90 FA-3). El cálculo del valor neto (RF-84) no recibe costos de M05 ni guarda tipo_costo (H-16 de G16).
- 091: ficha dice «sin tipo_costo se rechaza»; RF-90 dice que se deriva del subtipo -> se prueba lo que dice RF-90 (091a derivada VENTA,
  091b OTRO sin naturaleza queda PENDIENTE_CLASIFICACION sin tocar el neto, 091c VENTA explícito se acepta). La diferencia con la ficha se documenta.
- 092: costo MANTENIMIENTO de 80.000 (mano de obra propia; M05 no se puede simular desde QA): el neto sigue en 9.500.000, el costo queda como gasto
  del período (línea de asiento). 092b: un MANTENIMIENTO no se puede registrar como VENTA (RF-84 CA-7, RF-90 FA-2). La notificación al Contador
  se emite en una sesión aparte tras el commit: no verificable en el sandbox (se revisa en Cypress, G31).
- 093: clasificaciones inválidas ('OTRO', 'FINANCIERO') se rechazan con 4xx y no cambian el neto ni crean costo.
Todo el grupo comparte un activo reconocido en un solo run; cada caso usa montos distintos para no confundir sus registros.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G19/TC-M06-G19.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G19/reporte-TC-M06-G19.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

PCT = ("0.02", "0.02", "0.01")            # 2 % + 2 % + 1 % = 5 % del bruto (500.000): neto = 9.500.000,0000
JUSTIF = "Costo de QA TC-M06 clasificado por el Contador con soporte documental."


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


@pytest.fixture(scope="module")
def ida(env):
    env.nuevo_run()
    env.presupuesto(60)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=PCT)
    a, _ = env.reconocer(esc, origen="nacimiento", costo=None, soporte=None)
    return a


def _costo(ida, monto, subtipo="MANO_OBRA", **extra):
    return {"subtipo_costo": subtipo, "origen_costo": "MANO_OBRA_PROPIA", "monto_costo": monto,
            "fecha_costo": str(hoy()), "id_activo_biologico": ida, **extra}


def _post(env, ida, monto, **kw):
    return env.call("POST", "/finanzas/costos", "contador", json=_costo(ida, monto, **kw))


def _neto(env, ida):
    s = env.simulacion(ida)
    assert s.status == 200, s
    return dec(s.get("calculo")["valor_neto"])


def _registro(r):
    regs = (r.data or {}).get("registros") or []
    return regs[0] if regs else {}


def test_TC_M06_091a_tipo_costo_ausente_o_nulo_se_deriva_del_subtipo(env, ida):
    antes = _neto(env, ida)
    for nombre, extra in (("ausente", {}), ("null", {"naturaleza_costo": None})):
        r = _post(env, ida, "70001.0000" if nombre == "ausente" else "70002.0000", subtipo="TRANSPORTE", justificacion=JUSTIF, **extra)
        assert r.status in (200, 201), f"costo de TRANSPORTE con naturaleza {nombre}: se esperaba el registro con naturaleza derivada y respondió {r}"
        reg = _registro(r)
        assert reg.get("naturaleza_costo") == "VENTA" and reg.get("estado") == "REGISTRADO", (nombre, reg)
    assert _neto(env, ida) == antes, "el costo de VENTA registrado no debe cambiar el cálculo del neto"
    obs("La ficha pide rechazar el costo sin tipo; RF-90 dice que la naturaleza se deriva del subtipo (TRANSPORTE = VENTA): diferencia de la ficha.")


def test_TC_M06_091b_subtipo_otro_sin_naturaleza_queda_pendiente_de_clasificacion(env, ida):
    antes = _neto(env, ida)
    for nombre, extra in (("ausente", {}), ("null", {"naturaleza_costo": None})):
        r = _post(env, ida, "70011.0000" if nombre == "ausente" else "70012.0000", subtipo="OTRO", justificacion=JUSTIF, **extra)
        assert r.status in (200, 201), f"costo OTRO con naturaleza {nombre}: RF-90 FA-3 lo deja PENDIENTE_CLASIFICACION y respondió {r}"
        assert _registro(r).get("estado") == "PENDIENTE_CLASIFICACION" and not _registro(r).get("naturaleza_costo"), _registro(r)
    assert _neto(env, ida) == antes, "un costo sin clasificar no debe entrar en el neto"


def test_TC_M06_091c_venta_explicita_se_acepta(env, ida):
    r = _post(env, ida, "70021.0000", subtipo="TRANSPORTE", naturaleza_costo="VENTA", justificacion=JUSTIF)
    assert r.status in (200, 201), r
    assert _registro(r).get("naturaleza_costo") == "VENTA", _registro(r)


def test_TC_M06_092_mantenimiento_no_se_resta_y_queda_como_gasto(env, ida):
    antes = _neto(env, ida)
    assert antes == dec("9500000.0000"), f"base del caso: neto esperado 9.500.000,0000 y es {antes}"
    r = _post(env, ida, "80000.0000")
    assert r.status in (200, 201), f"no se pudo registrar el costo de MANTENIMIENTO: {r}"
    reg = _registro(r)
    assert reg.get("naturaleza_costo") == "MANTENIMIENTO", reg
    assert _neto(env, ida) == dec("9500000.0000"), "el costo de mantenimiento no debe restarse del valor neto"
    lista = env.call("GET", "/finanzas/costos", "contador", params={"id_activo_biologico": ida})
    assert lista.status == 200, lista
    registros = lista_de(lista.data, "costos", "registros")
    assert any(dec(c.get("monto_costo")) == dec("80000") and c.get("naturaleza_costo") == "MANTENIMIENTO" for c in registros), registros
    lineas = env.sql("SELECT tipo_hecho::text AS tipo_hecho, valor FROM modulo6.lineas_asiento_nic41 "
                     f"WHERE id_activo_biologico = {int(ida)} AND NOT es_reverso AND valor = 80000")
    assert lineas, "el costo de mantenimiento debe registrarse como gasto del período (línea de asiento)"
    obs("Notificación al Contador por el gasto/reclasificación: se emite en una sesión aparte tras el commit (no verificable en el sandbox; Cypress G31).")


def test_TC_M06_092b_mantenimiento_no_se_reclasifica_como_venta(env, ida):
    n = len(lista_de(env.call("GET", "/finanzas/costos", "contador", params={"id_activo_biologico": ida}).data, "costos", "registros"))
    r = _post(env, ida, "70031.0000", naturaleza_costo="VENTA", justificacion=JUSTIF)
    assert 400 <= r.status < 500, f"un costo de MANTENIMIENTO no puede incluirse como VENTA (RF-84 CA-7): respondió {r}"
    n2 = len(lista_de(env.call("GET", "/finanzas/costos", "contador", params={"id_activo_biologico": ida}).data, "costos", "registros"))
    assert n2 == n, "el costo rechazado no debe quedar registrado"


@pytest.mark.parametrize("clasificacion", ["OTRO", "FINANCIERO"])
def test_TC_M06_093_clasificacion_invalida_se_rechaza(env, ida, clasificacion):
    antes = _neto(env, ida)
    n = len(lista_de(env.call("GET", "/finanzas/costos", "contador", params={"id_activo_biologico": ida}).data, "costos", "registros"))
    r = _post(env, ida, "70041.0000" if clasificacion == "OTRO" else "70042.0000", naturaleza_costo=clasificacion)
    assert 400 <= r.status < 500, f"naturaleza_costo {clasificacion} debía rechazarse con 4xx y respondió {r}"
    assert _neto(env, ida) == antes, "el costo inválido no debe afectar el neto"
    n2 = len(lista_de(env.call("GET", "/finanzas/costos", "contador", params={"id_activo_biologico": ida}).data, "costos", "registros"))
    assert n2 == n, "el costo con clasificación inválida no debe quedar registrado"
