# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-82: script del grupo TC-M06-G04 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-82: G04 alineado con la ficha (5xx falla, redondeo sin aviso falla, fecha con precio) |
"""
TC-M06-G04 - Valores límite del reconocimiento inicial: costo de adquisición, precisión decimal y fecha del reconocimiento.
RF-82 (CU01).   Casos: TC-M06-017, TC-M06-018 y TC-M06-019.

El costo entra por RF-33 (POST /activos-biologicos, dentro del run) y la especie NO tiene precio RF-89, de modo que el valor
reconocido sale del costo (VALORACION_POR_COSTO). El valor exacto se verifica con SELECT en modulo6.reconocimientos_iniciales
(la respuesta JSON de FastAPI puede redondear los Decimal grandes a float: si difiere, queda como observación).
El backend no recibe la fecha del reconocimiento (la calcula el servidor): como la ficha dice «si la API admite fecha explícita»,
el caso 019 prueba SIN fecha (debe ser la del día del servidor, con SELECT) y envía además «fecha_reconocimiento» de ayer, hoy y
mañana: si la API la admite, ayer y mañana deben rechazarse y hoy aceptarse; si la ignora, queda documentado que no la admite.
Un 5xx en cualquier caso es FALLIDO (no es un rechazo controlado).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G04/TC-M06-G04.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G04/reporte-TC-M06-G04.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys
from datetime import timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


@pytest.fixture(scope="module")
def esc(env):
    return env.escenario(categoria="POR_CABEZA", precio=None, vida_util=60)


@pytest.fixture(scope="module")
def esc_precio(env):
    return env.escenario(categoria="POR_CABEZA", precio="8000000.00", vida_util=60)


def _valor_guardado(env, ida):
    # ::text para leer el NUMERIC exacto: /test-control/query devuelve los números como float y perdería los 4 decimales.
    return uno(env.sql(f"SELECT valor_razonable_neto_inicial::text FROM modulo6.reconocimientos_iniciales "
                       f"WHERE id_activo_biologico = {ida} AND estado = 'CONFIRMADO'"))


LIMITES = [
    ("-0.01", False), ("0", False), ("0.0001", True), ("0.01", True),
    ("99999999999999.9999", True), ("100000000000000.0000", False),
]


@pytest.mark.parametrize("costo,acepta", LIMITES, ids=[c for c, _ in LIMITES])
def test_TC_M06_017_costo_en_los_limites(env, esc, costo, acepta):
    env.presupuesto(30)
    r = env.activo_r(esc, origen="compra", costo=costo, soporte="Factura QA-M06-017")
    if not acepta:
        assert r.status not in (200, 201), f"RF-33 no debía registrar el costo {costo}: {r}"
        assert r.status < 500, f"RF-33 respondió un error de servidor con el costo {costo} en lugar de rechazarlo: {r}"
        return
    assert r.status in (200, 201), f"el costo {costo} debía aceptarse: {r}"
    ida = r.get("id_activo_biologico")
    c = env.confirmar(ida)
    assert c.status == 201, f"con costo {costo} el reconocimiento por costo debía confirmarse: {c}"
    assert c.get("indicador_valoracion") == "VALORACION_POR_COSTO", c
    guardado = _valor_guardado(env, ida)
    assert dec(guardado) == dec(costo), f"valor guardado {guardado} != costo {costo}"
    if dec(c.get("valor_inicial")) != dec(costo):
        obs(f"la respuesta JSON devolvió {c.get('valor_inicial')} para el costo {costo} (pérdida de precisión de float en la API); en BD quedó {guardado}.")


@pytest.mark.parametrize("costo", ["1000.0001", "1000.00005"], ids=["4_decimales", "5_decimales"])
def test_TC_M06_018_costo_con_mas_de_cuatro_decimales(env, esc, costo):
    env.presupuesto(30)
    r = env.activo_r(esc, origen="compra", costo=costo, soporte="Factura QA-M06-018")
    assert r.status < 500, f"RF-33 respondió un error de servidor: {r}"
    if costo == "1000.0001":
        assert r.status in (200, 201), f"4 decimales debía aceptarse: {r}"
        ida = r.get("id_activo_biologico")
        assert env.confirmar(ida).status == 201
        assert dec(_valor_guardado(env, ida)) == dec("1000.0001")
        return
    if r.status in (400, 422):
        obs(f"5 decimales: RF-33 lo rechaza (HTTP {r.status} {r.err}).")
        return
    assert r.status in (200, 201), r
    ida = r.get("id_activo_biologico")
    g = env.call("GET", f"/activos-biologicos/{ida}", "admin")
    guardado_activo = g.get("costo_adquisicion")
    if guardado_activo is None and isinstance(g.data, dict) and isinstance(g.data.get("data"), dict):
        guardado_activo = g.data["data"].get("costo_adquisicion")
    c = env.confirmar(ida)
    assert c.status == 201, f"el activo con costo de 5 decimales se registró pero el reconocimiento respondió {c}"
    guardado_rec = _valor_guardado(env, ida)
    obs(f"5 decimales: RF-33 aceptó 1000.00005; costo guardado {guardado_activo}, valor reconocido guardado {guardado_rec}.")
    if dec(guardado_rec) == dec("1000.00005") and (guardado_activo is None or dec(guardado_activo) == dec("1000.00005")):
        return                                                       # se conservó el valor informado
    texto = (r.text + " " + c.text).lower()
    # Solo cuenta un aviso que hable del redondeo; la clave genérica «advertencias» (p. ej. valoración por costo) no basta.
    avisa = any(k in texto for k in ("redonde", "aproxim", "ajustad", "truncad", "decimales"))
    obs(f"respuesta de RF-33: {r.text[:400]}")
    obs(f"respuesta de la confirmación: {c.text[:400]}")
    assert avisa, (f"se persistió un valor distinto del informado (1000.00005 -> costo {guardado_activo}, "
                   f"valor reconocido {guardado_rec}) sin avisar al usuario: {r.text[:200]}")


def test_TC_M06_019_fecha_del_reconocimiento_es_la_del_dia(env, esc_precio):
    esc = esc_precio                                                 # ficha: COMPRA con precio de mercado vigente
    env.presupuesto(40)
    # Hoy (sin fecha explícita): la fecha registrada es la del servidor (zona America/Bogota).
    hoy_ida = env.activo(esc, origen="compra", costo="1500000.0000", soporte="Factura QA-M06-019")
    c = env.confirmar(hoy_ida)
    assert c.status == 201, c
    assert str(c.get("fecha_reconocimiento"))[:10] == str(hoy()), c
    fecha_bd = uno(env.sql(f"SELECT fecha_reconocimiento FROM modulo6.reconocimientos_iniciales WHERE id_activo_biologico = {hoy_ida}"))
    assert str(fecha_bd)[:10] == str(hoy()), f"fecha en BD {fecha_bd}"
    # Con fecha explícita: ayer y mañana se rechazan y hoy se acepta (si la API la ignora, se documenta que no la admite).
    for etiqueta, dia in (("ayer", hoy() - timedelta(days=1)), ("hoy", hoy()), ("manana", hoy() + timedelta(days=1))):
        ida = env.activo(esc, origen="compra", costo="1500000.0000", soporte=f"Factura QA-M06-019-{etiqueta}")
        r = env.confirmar(ida, cuerpo={"fecha_reconocimiento": str(dia)})
        assert r.status < 500, r
        if etiqueta != "hoy" and 400 <= r.status < 500:
            continue                                                 # ayer/mañana rechazados, como pide la ficha
        assert r.status == 201, f"con fecha explícita {etiqueta} ({dia}) se esperaba {'201 (aceptada)' if etiqueta == 'hoy' else 'rechazo'} y respondió {r}"
        assert str(r.get("fecha_reconocimiento"))[:10] == str(hoy()), f"con fecha {etiqueta} se registró {r.get('fecha_reconocimiento')}"
        obs(f"la API ignoró fecha_reconocimiento={dia}; quedó la fecha del día.")
