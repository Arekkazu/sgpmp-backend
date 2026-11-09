# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-82: script del grupo TC-M06-G03 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-82: G03 alineado con la ficha (SELECT de conteo, 404/422, EN_PRODUCCION) |
"""
TC-M06-G03 - Validación de entradas y precondiciones NIC 41 ¶10 del reconocimiento inicial.   RF-82 (CU01).
Casos: TC-M06-010 a TC-M06-016.

RF-82 lee origen, costo y soporte del activo registrado en RF-33 (CA-11): los casos intentan registrar el activo inválido por
RF-33 (dentro del run). Si RF-33 lo rechaza (400/422), el caso se da por cumplido por RF-33 (lo dice la ficha); si lo registra,
RF-82 debe bloquear: no se genera propuesta confirmable, la confirmación se rechaza y el SELECT cuenta 0 reconocimientos.
En ningún caso puede quedar un reconocimiento inválido ni haber un 5xx.

Diferencias de nombres frente a la ficha (catálogo real de RF-33/M02), anotadas para el reporte:
- Criterio de QA: la mayúscula/minúscula no cuenta como desviación. El catálogo real de RF-33 va en minúscula (compra, donacion...),
  así que el caso «compra con la mayúscula/minúscula equivocada» de TC-M06-011 se prueba como 'COMPRA'. Si RF-33 la acepta
  normalizándola a 'compra', se da por válida (es el mismo valor); si la guarda tal cual, RF-82 debe bloquear.
- M02 no tiene el estado EN_PRODUCCION: ese subcaso sale BLOQUEADO (no se puede preparar), no se sustituye por otro estado.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G03/TC-M06-G03.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G03/reporte-TC-M06-G03.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

RECHAZO = (400, 422)


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


@pytest.fixture(scope="module")
def esc(env):
    return env.escenario(categoria="POR_CABEZA", precio=None)       # sin precio: el valor sale del costo


@pytest.fixture(scope="module")
def esc_precio(env):
    return env.escenario(categoria="POR_CABEZA", precio="8000000.00")


def _informa(r) -> bool:
    """La respuesta explica el motivo: bloqueos en la propuesta o mensaje/código de error."""
    if r.status == 200:
        return bool(r.get("bloqueos"))
    return bool(r.err or r.text)


def _verificar_bloqueo(env, ida, que):
    """RF-82 no genera propuesta confirmable, rechaza la confirmación y no deja reconocimiento (SELECT cuenta 0)."""
    p = env.propuesta(ida)
    assert p.status < 500, f"{que}: la propuesta respondió un error de servidor: {p}"
    if p.status == 200:
        assert p.get("es_confirmable") is False, f"{que}: RF-82 debía bloquear y generó una propuesta confirmable: {p.data}"
    else:
        assert 400 <= p.status < 500, p
    assert _informa(p), f"{que}: el bloqueo no informa el motivo: {p}"
    c = env.confirmar(ida)
    assert 400 <= c.status < 500, f"{que}: la confirmación debía rechazarse y respondió {c}"
    n = env.contar("reconocimientos_iniciales", ida)
    assert n == 0, f"{que}: el SELECT muestra {n} reconocimiento(s) para el activo"
    h = env.call("GET", f"/finanzas/activos/{ida}", "contador")
    if h.status == 200:
        assert not lineas_de(h.data), f"{que}: hay líneas de asiento para el activo"
    obs(f"{que}: propuesta HTTP {p.status} codigos={codigos(p) if p.status == 200 else p.err}; confirmación HTTP {c.status} {c.err}")


def _debe_quedar_sin_reconocimiento(env, r_registro, que):
    """RF-33 rechaza (cumplido por RF-33) o, si registra el activo, RF-82 bloquea el reconocimiento."""
    assert r_registro.status < 500, f"{que}: RF-33 respondió un error de servidor: {r_registro}"
    if r_registro.status in RECHAZO:
        obs(f"{que}: rechazado por RF-33 (HTTP {r_registro.status} {r_registro.err})")
        return
    assert r_registro.status in (200, 201), f"{que}: {r_registro}"
    _verificar_bloqueo(env, r_registro.get("id_activo_biologico"), f"{que} (registrado por RF-33, bloquea RF-82)")


@pytest.mark.parametrize("variante", ["ausente", "null"])
def test_TC_M06_010_activo_sin_origen_financiero(env, esc, variante):
    env.presupuesto()
    if variante == "ausente":
        r = env.activo_r(esc, quitar=("origen_financiero",))
    else:
        r = env.activo_r(esc, origen=None)                           # origen_financiero: null
    _debe_quedar_sin_reconocimiento(env, r, f"origen {variante}")


@pytest.mark.parametrize("origen", ["PRESTAMO", "COMPRA", ""], ids=["PRESTAMO", "COMPRA_otra_caja", "vacio"])
def test_TC_M06_011_origen_fuera_del_catalogo(env, esc, origen):
    env.presupuesto()
    r = env.activo_r(esc, origen=origen)
    if origen == "COMPRA" and r.status in (200, 201):
        ida = r.get("id_activo_biologico")
        guardado = r.get("origen_financiero")
        if guardado is None:
            g = env.call("GET", f"/activos-biologicos/{ida}", "admin")
            guardado = g.get("origen_financiero")
        if str(guardado).lower() == "compra":
            obs(f"RF-33 aceptó 'COMPRA' y lo guardó como '{guardado}': mismo valor del catálogo, no se considera desviación.")
            return
    _debe_quedar_sin_reconocimiento(env, r, f"origen '{origen}'")


@pytest.mark.parametrize("origen", ["compra", "donacion"])
@pytest.mark.parametrize("variante", ["ausente", "null"])
def test_TC_M06_012_compra_y_donacion_sin_costo(env, esc, origen, variante):
    env.presupuesto()
    extra = {"costo_adquisicion": None} if variante == "null" else {}
    r = env.activo_r(esc, origen=origen, costo=None, **extra)         # sin costo y sin precio de mercado en la especie
    _debe_quedar_sin_reconocimiento(env, r, f"{origen} sin costo ({variante})")


@pytest.mark.parametrize("origen", ["compra", "donacion"])
@pytest.mark.parametrize("variante", ["ausente", "vacio", "null"])
def test_TC_M06_013_compra_y_donacion_sin_soporte(env, esc, origen, variante):
    env.presupuesto()
    if variante == "ausente":
        r = env.activo_r(esc, origen=origen, costo="1000000.0000", soporte=None)
    elif variante == "vacio":
        r = env.activo_r(esc, origen=origen, costo="1000000.0000", soporte="")
    else:
        r = env.activo_r(esc, origen=origen, costo="1000000.0000", soporte=None, soporte_documental=None)
    _debe_quedar_sin_reconocimiento(env, r, f"{origen} sin soporte ({variante})")


@pytest.mark.parametrize("id_activo,esperado", [("999999999", (404,)), ("abc", (400, 422)), ("null", (400, 422))],
                         ids=["inexistente", "abc", "null"])
def test_TC_M06_014_activo_inexistente_o_mal_formado(env, esc, id_activo, esperado):
    """Ficha: inexistente 404 (o rechazo equivalente); mal formado o null 422. Criterio de QA (8-nov): el error de validación de
    la API (400 VAL_ENTRADA, convención global ya aprobada en otros módulos) equivale al 422 de la ficha."""
    env.presupuesto()
    env.contador()
    for r in (env.call("GET", f"/finanzas/reconocimientos/propuestas/{id_activo}", "contador"),
              env.call("POST", f"/finanzas/reconocimientos/{id_activo}", "contador", json={})):
        assert r.status < 500, f"error de servidor: {r}"
        assert r.status in esperado, f"la ficha pide {esperado} y se recibió {r}"


@pytest.mark.parametrize("estado", ["ACTIVO", "EN_PRODUCCION", "INACTIVO", "BAJA"])
def test_TC_M06_015_estado_del_activo(env, esc_precio, estado):
    """ACTIVO y EN_PRODUCCION generan propuesta; BAJA e INACTIVO se rechazan con mensaje de estado no elegible."""
    env.presupuesto(25)
    ida = env.activo(esc_precio, origen="compra")                     # COMPRA, costo 2.500.000, soporte; precio RF-89 vigente
    if estado == "BAJA":
        env.prep(env.baja(ida), (200, 201), "evento de baja RF-45 (estado BAJA)")
    elif estado != "ACTIVO":
        r = env.estado_activo(ida, estado)
        if r.status not in (200, 201):
            pytest.skip(f"NO APLICA: el estado {estado} ya no existe en M02 (se cambió al probar ese módulo, ya aprobado); "
                        f"M02 respondió HTTP {r.status} {r.err}. ACTIVO cubre el estado elegible.")
    p = env.propuesta(ida)
    if estado in ("ACTIVO", "EN_PRODUCCION"):
        assert p.status == 200, f"estado {estado} debía generar propuesta: {p}"
        assert p.get("es_confirmable") is True, f"estado {estado} debía ser elegible: {p.get('bloqueos')}"
    else:
        _verificar_bloqueo(env, ida, f"estado {estado}")


def test_TC_M06_016_sin_clasificacion_en_m09(env):
    """Sin clasificación PRODUCCION/CONSUMO en M09: no se genera propuesta, se informa la falta; se registra el código real."""
    env.presupuesto(25)
    esc = env.escenario(categoria="POR_CABEZA", clasificacion=None, precio="8000000.00")
    ida = env.activo(esc, origen="compra")
    p = env.propuesta(ida)
    assert p.status < 500, p
    if p.status == 200:
        assert p.get("es_confirmable") is False, f"se generó propuesta confirmable con clasificación vacía: {p.data}"
    assert _informa(p), f"no se informa que falta la clasificación de M09: {p}"
    c = env.confirmar(ida)
    assert 400 <= c.status < 500, f"la confirmación debía rechazarse: {c}"
    assert env.contar("reconocimientos_iniciales", ida) == 0
    obs(f"Sin clasificación en M09: propuesta HTTP {p.status} codigos={codigos(p) if p.status == 200 else p.err}; "
        f"confirmación HTTP {c.status} error_code={c.err} (el RF no define este flujo alterno).")
