# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-83: script del grupo TC-M06-G10 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-83: G10 con valores de la ficha (+/-300.000), evento pendiente + cierre y 8 activos con precio + 2 sin precio |
# | 2026-11-11 | Daniela Castillo | M06 RF-83 v1.2: 053 revisado (solo valor razonable sin precio ni histórico queda pendiente) y caso nuevo 053b (activo por costo) |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G10-V2.0.html |
# | 2026-11-13 | Daniela Castillo | M06 V2.0 (2.ª pasada): la base de datos pasa a ser la fuente de verdad (SQL ya funciona), expectativas alineadas con las correcciones de Desarrollo (notas de la versión 1.4.0) y las precondiciones que fallan ya no se omiten: quedan en rojo con diagnóstico |
"""
TC-M06-G10 - Medición por cierre de período (RF-87): efecto precio, prioridad del evento y activos sin precio.
RF-83 (CU02).   Casos: TC-M06-051 a TC-M06-053.

Cierre: POST /finanzas/periodos/{id}/cierre (RF-87). Mide todos los activos reconocidos del titular y cierra el período; si no se puede
ejecutar dentro del sandbox (precondiciones, tiempo) el caso queda BLOQUEADO / NO CONCLUYENTE con el motivo. Cada caso usa su propio run
(el cierre deja el período cerrado dentro del run).

- 051: dos activos de especies distintas (categoría POR_CABEZA, costos de venta en cero) con valor 10.000.000,0000; el precio de una sube a
  10.300.000 y el de la otra baja a 9.700.000; sin eventos. Se espera transformación 0,0000 y efecto precio +300.000 / -300.000.
- 052: el evento CRECIMIENTO queda PENDIENTE en la cola y se ejecuta el cierre: el cierre mide antes los eventos (RF-83: prioridad del
  evento); debe quedar una sola medición, la del evento (id_evento informado), sin segunda medición por el cierre.
- 053: 10 activos reconocidos: 8 con precio y 2 sin precio RF-89 ni histórico. «Sin precio» se logra dejando a la especie sin precio en la
  categoría que usa M09 (se cambia categoria_precio después de reconocer; no se puede borrar un precio). Prevalidación y cierre (con
  exclusiones autorizadas) deben dejar a esos 2 en la lista de pendientes, medir los 8 y no bloquear el cierre. El backend nombra la
  lista «activos_excluidos» con motivo PENDIENTE_PRECIO (el RF la llama MEDICION_PENDIENTE): se anota como observación.
  RF-83 v1.2: quedan pendientes solo los activos a valor razonable sin precio ni histórico; en el cierre no se pasan a costo (NIC 41 ¶31).
- 053b (nuevo, RF-83 v1.2): un activo valorado por costo (NIC 41 ¶30) no se mide en el cierre ni queda como pendiente de precio.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G10/TC-M06-G10.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G10/reporte-TC-M06-G10-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

SIN_COSTOS = ("0", "0", "0")


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


def _asegurar(env, segundos):
    """Cada run del sandbox dura 170 s como máximo; el cierre deja el período cerrado, así que cada caso abre su run."""
    if env.inicio is not None and env.restante() < segundos:
        env.nuevo_run()


def _periodo(env, ida, conf):
    p = (conf.get("id_periodo_contable") if hasattr(conf, "get") else None) or env.periodo(ida)
    assert p, f"no se pudo determinar el período contable del activo {ida}"
    return p


def _cerrar(env, id_periodo, autorizar=True, incluir_sin_precio=True):
    try:
        r = env.call("POST", f"/finanzas/periodos/{id_periodo}/cierre", "contador",
                     json={"autorizar_exclusiones": autorizar, "incluir_activos_sin_precio": incluir_sin_precio})
    except requests.exceptions.RequestException as exc:
        no_concluyente(f"el cierre del período no respondió a tiempo dentro del sandbox: {exc}")
    if r.status not in (200, 201, 202):
        bloqueado(f"el cierre del período {id_periodo} no se pudo ejecutar dentro del run: {r}")
    return r


def _de_cierre(env, ida):
    return [m for m in env.mediciones(ida) if m.get("origen_medicion") == "CIERRE_PERIODO"]


def _activo_a_10_millones(env, esc):
    ida, conf = env.reconocer(esc, origen="nacimiento", costo=None, soporte=None)
    env.procesar_eventos()
    return ida, conf


def test_TC_M06_051_cierre_sin_eventos_todo_es_efecto_precio(env):
    _asegurar(env, 160)
    env.presupuesto(100)
    sube = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=SIN_COSTOS)
    baja = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=SIN_COSTOS)
    a, conf = _activo_a_10_millones(env, sube)
    b, _ = _activo_a_10_millones(env, baja)
    for ida in (a, b):
        c = max(env.historial(ida)["calculos"], key=lambda x: x["id_calculo_valor_razonable"])
        assert dec(c["valor_neto"]) == dec("10000000"), f"precondición de la ficha: valor anterior 10.000.000,0000: {c}"
    env.precio(sube, "10300000.00", desde=hoy())      # RF-84 devolverá 10.300.000,0000
    env.precio(baja, "9700000.00", desde=hoy())       # RF-84 devolverá 9.700.000,0000
    id_periodo = _periodo(env, a, conf)
    _cerrar(env, id_periodo)
    for ida, esperado, signo in ((a, dec("300000"), "+"), (b, dec("-300000"), "-")):
        ms = _de_cierre(env, ida)
        assert ms, f"el cierre no creó medición para el activo {ida} (API); mediciones: {env.mediciones(ida)}"
        m = ms[-1]
        db = env.sql("SELECT origen_medicion::text AS origen, id_evento, ganancia_perdida_transformacion::text AS transf, ganancia_perdida_precio_mercado::text AS precio, "
                     f"variacion_total::text AS total FROM modulo6.mediciones_posteriores WHERE id_activo_biologico = {int(ida)}")
        assert len(db) == 1 and db[0]["origen"] == "CIERRE_PERIODO" and db[0]["id_evento"] is None, f"base de datos: una sola medición, de cierre y sin evento: {db}"
        assert dec(db[0]["transf"]) == 0 and dec(db[0]["precio"]) == esperado and dec(db[0]["total"]) == esperado, f"base de datos, efectos de la medición: {db}"
        assert len(env.mediciones(ida)) == 1 and len(ms) == 1, f"debe haber una sola medición, la del cierre: {env.mediciones(ida)}"
        assert m.get("id_periodo_contable") == id_periodo, f"la medición debe estar vinculada al período {id_periodo}: {m}"
        assert m.get("id_evento") is None, "sin evento biológico no debe haber id_evento"
        assert dec(m["valor_razonable_anterior"]) == dec("10000000"), m
        assert dec(m["ganancia_perdida_transformacion"]) == dec("0"), f"transformación debe ser 0,0000 ({signo}): {m}"
        assert dec(m["ganancia_perdida_precio_mercado"]) == esperado, f"efecto precio {signo}300.000,0000: {m}"
        assert dec(m["variacion_total"]) == esperado and dec(m["valor_razonable_actual"]) == dec("10000000") + esperado, m


def test_TC_M06_052_evento_y_cierre_el_evento_tiene_prioridad(env):
    _asegurar(env, 160)
    env.presupuesto(100)
    esc = env.escenario(categoria="PESO_KG", precio="20000.00", costos=SIN_COSTOS)
    ida, conf = env.reconocer(esc, origen="nacimiento", costo=None, soporte=None, peso_kg="400")
    env.procesar_eventos()                                           # cola vacía: solo el evento de la prueba queda pendiente
    env.pesaje(ida, "450")                                           # evento CRECIMIENTO en el mismo período, SIN procesar
    assert not env.mediciones(ida), "antes del cierre el evento sigue pendiente (aún no hay mediciones)"
    id_periodo = _periodo(env, ida, conf)
    _cerrar(env, id_periodo)                                         # el cierre procesa primero los eventos pendientes
    ms = env.mediciones(ida)
    assert ms, "ni el evento ni el cierre generaron medición"
    db = env.sql(f"SELECT origen_medicion::text AS origen, id_evento FROM modulo6.mediciones_posteriores WHERE id_activo_biologico = {int(ida)}")
    assert len(db) == 1 and db[0]["origen"] == "EVENTO" and db[0]["id_evento"], f"base de datos: una sola medición, por el evento: {db}"
    por_evento = [m for m in ms if m.get("origen_medicion") == "EVENTO"]
    assert len(por_evento) == 1 and por_evento[0].get("id_evento"), f"debe haber una medición por el evento, con id_evento: {ms}"
    assert len(ms) == 1, f"el cierre no debe registrar una segunda medición del mismo activo y valor: {ms}"
    assert not _de_cierre(env, ida), "el cierre no debe medir otra vez el activo"
    m = ms[0]
    assert dec(m["valor_razonable_anterior"]) == vn(400, "20000.00", SIN_COSTOS) and dec(m["valor_razonable_actual"]) == vn(450, "20000.00", SIN_COSTOS), m
    obs(f"evento id_evento {m['id_evento']} medido por el cierre antes de cerrar (origen EVENTO); sin medición de cierre para el activo.")


def test_TC_M06_053_activos_sin_precio_quedan_pendientes_y_el_cierre_continua(env):
    _asegurar(env, 160)
    env.presupuesto(120)
    con = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=SIN_COSTOS)
    sin = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=SIN_COSTOS)
    con_precio, sin_precio = [], []
    conf = None
    for _ in range(8):
        ida, c = env.reconocer(con, origen="nacimiento", costo=None, soporte=None)
        conf = conf or c
        con_precio.append(ida)
    for _ in range(2):
        sin_precio.append(env.reconocer(sin, origen="nacimiento", costo=None, soporte=None)[0])
    env.procesar_eventos()
    # Sin precio ni histórico: la especie pasa a usar una categoría de precio en la que nunca hubo precio.
    env.prep(env.call("PUT", f"/finanzas/configuracion/especies/{sin.id_especie}", "contador", json={
        "clasificacion": "PRODUCCION", "categoria_precio": "PESO_KG", "vida_util_meses": 60}), (200, 201), "especie sin precio en su categoría")
    env.precio(con, "10300000.00", desde=hoy())                       # los 8 con precio tienen variación
    id_periodo = _periodo(env, con_precio[0], conf)
    pre = env.call("GET", f"/finanzas/periodos/{id_periodo}/prevalidacion", "contador")
    assert pre.status == 200, pre
    lista_pre = {int(x["id_activo_biologico"]) for x in (pre.data or {}).get("activos_sin_precio", [])}
    assert set(sin_precio) <= lista_pre, f"la prevalidación debe listar los 2 activos sin precio: {lista_pre}"
    assert not (set(con_precio) & lista_pre), "ningún activo con precio debe figurar como sin precio"
    r = _cerrar(env, id_periodo, autorizar=True, incluir_sin_precio=False)
    excluidos = {int(x["id_activo_biologico"]): x for x in (r.data or {}).get("activos_excluidos", [])}
    assert set(sin_precio) <= set(excluidos), f"los 2 activos sin precio deben quedar en la lista de pendientes: {excluidos}"
    assert all(excluidos[i].get("motivo") == "PENDIENTE_PRECIO" for i in sin_precio), excluidos
    assert not (set(con_precio) & set(excluidos)), "los 8 con precio no deben quedar pendientes"
    assert r.data.get("estado") == "CERRADO", f"el cierre debe continuar y completarse: {r.data.get('estado')}"
    for ida in con_precio:
        ms = _de_cierre(env, ida)
        assert len(ms) == 1 and dec(ms[0]["ganancia_perdida_precio_mercado"]) == dec("300000"), f"activo {ida} sin medición de cierre: {ms}"
        assert env.contar("mediciones_posteriores", ida) == 1, f"base de datos: el activo {ida} con precio debe tener 1 medición"
    for ida in sin_precio:
        assert not env.mediciones(ida), f"el activo sin precio no debe medirse: {env.mediciones(ida)}"
        assert env.contar("mediciones_posteriores", ida) == 0, f"base de datos: el activo {ida} sin precio no debe tener mediciones"
    extra = len(excluidos) - len(sin_precio)
    obs(f"medidos {len(con_precio)} activos con precio; pendientes {len(sin_precio)} (motivo PENDIENTE_PRECIO); "
        f"otros excluidos del titular en TEST: {extra}; activos_procesados del cierre: {r.data.get('activos_procesados')}")
    obs("el RF llama a la lista MEDICION_PENDIENTE; la API la devuelve como activos_excluidos con motivo PENDIENTE_PRECIO (y prevalidacion.activos_sin_precio).")


def test_TC_M06_053b_activo_por_costo_no_se_mide_en_el_cierre_ni_queda_pendiente(env):
    _asegurar(env, 120)
    env.presupuesto(100)
    esc, ida = env.activo_por_costo(costos=SIN_COSTOS)
    id_periodo = _periodo(env, ida, {})
    r = _cerrar(env, id_periodo, autorizar=True, incluir_sin_precio=True)
    excluidos = {int(x["id_activo_biologico"]): x for x in (r.data or {}).get("activos_excluidos", [])}
    obs(f"cierre del período {id_periodo}: estado {r.data.get('estado')}; activo por costo excluido: {ida in excluidos} {excluidos.get(ida, '')}")
    assert not env.mediciones(ida), f"RF-83 v1.2: el activo por costo no se mide en el cierre: {env.mediciones(ida)}"
    assert env.contar("mediciones_posteriores", ida) == 0, "base de datos: el activo por costo no debe tener mediciones"
    assert ida not in excluidos, f"el activo por costo no debe quedar como pendiente de precio (no usa precio): {excluidos.get(ida)}"
    assert r.data.get("estado") == "CERRADO", f"el cierre debe completarse: {r.data.get('estado')}"
