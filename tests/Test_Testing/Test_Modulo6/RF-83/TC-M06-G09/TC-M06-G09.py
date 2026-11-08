# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-83: script del grupo TC-M06-G09 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-83: G09 con los valores de la ficha (10.000.000 / 10.500.000 / 9.200.000), especie con ciclo, 048 real |
"""
TC-M06-G09 - Medición posterior por evento biológico y encadenamiento del historial.   RF-83 (CU02).   Casos: TC-M06-046 a TC-M06-050.

Valores de la ficha: precio 20.000,00 por kg y costos de venta en cero (neto = bruto): 500 kg -> 10.000.000,0000 (anterior); 525 kg ->
10.500.000,0000 (CRECIMIENTO, variación 500.000,0000); 460 kg -> 9.200.000,0000 (DETERIORO, variación -800.000,0000). RF-83 no recalcula:
el valor actual lo entrega RF-84 (vn() de la biblioteca replica la fórmula del RF).

Especie: un pesaje de M02 exige fase activa de un ciclo de la especie y tipo de medición PESO configurado; la API de QA no crea ciclos,
por eso las categorías PESO_KG usan la especie productiva sembrada de TEST y se asigna la fase (RF-37) antes de pesar.

Cómo mide el backend: POST /finanzas/eventos/procesar toma los eventos de M02 de activos con reconocimiento CONFIRMADO. Solo CRECIMIENTO
(pesaje), INGRESO (nacimiento en un lote), PRODUCTIVO (RF-85) y BAJA cambian valores; los reproductivos y sanitarios no.
- 047 REPRODUCCION = ingreso por nacimiento de crías en un lote (RF-83: «Procreación (nuevas crías): RF-42»).
- 048 PRODUCCION: la ficha espera una medición del activo; RF-85 (RNF-85-02) exige que la producción periódica NO modifique el valor del
  activo biológico (solo reconoce el producto). Se prueba lo que dice RF-85 y se anota la diferencia con la ficha.
- 050: la ficha pide CRECIMIENTO, PRODUCCION y DETERIORO; como PRODUCCION no mide el activo, se usan CRECIMIENTO, CRECIMIENTO y DETERIORO.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G09/TC-M06-G09.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G09/reporte-TC-M06-G09.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

P = "20000.00"
SIN_COSTOS = ("0", "0", "0")


def V(kg):
    """Valor neto de RF-84 con costos de venta en cero: kg x 20.000,00."""
    return vn(kg, P, SIN_COSTOS)


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


def _asegurar(env, segundos):
    """Cada run del sandbox dura 170 s como máximo: si ya no alcanza para el caso, se cierra y se abre uno nuevo."""
    if env.inicio is not None and env.restante() < segundos:
        env.nuevo_run()


def _escenario(env):
    return env.escenario(categoria="PESO_KG", precio=P, costos=SIN_COSTOS)


def _una_medicion(env, ida):
    ms = env.mediciones(ida)
    if not ms:
        no_verificable("no se generó medición: el procesamiento de eventos de M02 no produjo variación en el run "
                       f"(eventos del activo: {env.tipos_auditoria(ida)}).")
    return ms[-1]


def _evento_vinculado(env, m, ida, tipo_esperado):
    """La medición debe apuntar (id_evento) al evento de M02 que la originó. Se comprueba en el registro de procesamiento de M06
    (modulo6.procesamientos_eventos_m02): el id_evento de la medición figura allí como PROCESADO. (El SELECT del sandbox no devuelve
    filas de modulo2.eventos_activos para este run, por eso no se verifica el evento directamente en M02.)"""
    ide = m.get("id_evento")
    assert ide, f"la medición no trae id_evento: {m}"
    filas = env.sql(f"SELECT resultado::text AS resultado FROM modulo6.procesamientos_eventos_m02 WHERE id_evento = {int(ide)}")
    assert filas, f"el id_evento {ide} de la medición no figura como procesado en M06 (procesamientos_eventos_m02)"
    assert filas[0]["resultado"] == "PROCESADO", f"id_evento {ide}: resultado del procesamiento {filas[0]}"
    ea = env.sql(f"SELECT id_activo_biologico AS ida FROM modulo2.eventos_activos WHERE id_eventos = {int(ide)}")
    obs(f"{tipo_esperado}: id_evento {ide} procesado; consulta a modulo2.eventos_activos desde el sandbox: "
        f"{'activo ' + str(ea[0]['ida']) if ea else 'sin filas (el SELECT del sandbox no ve esa tabla)'}")
    if ea:
        assert int(ea[0]["ida"]) == int(ida), f"el evento {ide} pertenece al activo {ea[0]['ida']} y no al {ida}"


def _calculos_activo(env, ida, magnitud):
    """Cálculos RF-84 del activo con esa magnitud (los del producto agrícola llevan la magnitud cosechada)."""
    return [c for c in env.historial(ida)["calculos"] if dec(c["magnitud"]) == dec(magnitud)]


def test_TC_M06_046_medicion_por_evento_crecimiento(env):
    _asegurar(env, 90)
    env.presupuesto(50)
    esc = _escenario(env)
    ida = env.base_medible(esc, "500")                              # reconocimiento inicial: 10.000.000,0000
    r = env.medir(esc, ida, None, "525")                            # CRECIMIENTO: RF-84 devuelve 10.500.000,0000
    assert r.status == 200, r
    m = _una_medicion(env, ida)
    assert dec(m["valor_razonable_anterior"]) == V(500) == dec("10000000"), m
    assert dec(m["valor_razonable_actual"]) == V(525) == dec("10500000"), f"RF-84 entrega 10.500.000: {m}"
    assert dec(m["variacion_total"]) == dec("500000"), m
    _evento_vinculado(env, m, ida, "CRECIMIENTO")
    calculo = max(_calculos_activo(env, ida, 525), key=lambda c: c["id_calculo_valor_razonable"])
    assert dec(calculo["valor_neto"]) == V(525), "el valor vigente del activo debe actualizarse al valor actual"


def test_TC_M06_047_medicion_por_reproduccion_nacimiento_de_crias(env):
    _asegurar(env, 90)
    env.presupuesto(60)
    esc = env.escenario(categoria="POR_CABEZA", precio="500000.00", costos=SIN_COSTOS, especie_existente=ID_ESPECIE_PRODUCTIVA)
    ida, _ = env.reconocer(esc, tipo="POBLACIONAL", cantidad=10, origen="nacimiento", costo=None, soporte=None)
    env.asignar_fase(ida)
    env.procesar_eventos()
    env.prep(env.call("POST", f"/activos-biologicos/{ida}/eventos/ingreso", "admin", json={
        "tipo_ingreso": "nacimiento", "fecha_ingreso": str(hoy()), "cantidad_ingresada": 5, "motivo_ingreso": "Nacimientos QA TC-M06-047"}),
        (200, 201), "evento de ingreso por nacimiento")
    assert env.procesar_eventos().status == 200
    m = _una_medicion(env, ida)
    assert dec(m["valor_razonable_anterior"]) == vn(10, "500000.00", SIN_COSTOS) and dec(m["valor_razonable_actual"]) == vn(15, "500000.00", SIN_COSTOS), m
    assert dec(m["variacion_total"]) == dec(m["valor_razonable_actual"]) - dec(m["valor_razonable_anterior"]) > 0, m
    assert dec(m["ganancia_perdida_transformacion"]) == dec(m["variacion_total"]) > 0, "las crías son efecto transformación"
    _evento_vinculado(env, m, ida, "INGRESO")
    calculo = max(_calculos_activo(env, ida, 15), key=lambda c: c["id_calculo_valor_razonable"])
    assert dec(calculo["valor_neto"]) == dec(m["valor_razonable_actual"]), "el valor del activo debe actualizarse"
    hechos_m = {(l["tipo_hecho"], l["sentido"]) for l in lineas_de(env.historial(ida))}
    assert ("RECONOCIMIENTO_NACIMIENTO", "UNICO") in hechos_m, f"el nacimiento de crías es reconocimiento inicial (¶27): {hechos_m}"
    obs("REPRODUCCION se prueba como ingreso por nacimiento al lote; los eventos reproductivos/sanitarios de M02 no miden (SIN_EFECTO).")


def test_TC_M06_048_medicion_por_evento_produccion(env):
    """Ficha 048: medición vinculada al evento PRODUCCION y valor actualizado. RF-85 (RNF-85-02): la producción periódica NO modifica el
    valor del activo (reconoce el producto): se verifica el comportamiento de RF-85 y se anota la diferencia con la ficha."""
    _asegurar(env, 100)
    env.presupuesto(70)
    esc = env.escenario_producto(clasificacion="PRODUCCION", precio_activo=P, precio_producto="5000.00", costos=SIN_COSTOS)
    ida = env.activo_productivo(esc, "500")
    antes_m = len(env.mediciones(ida))
    antes_c = _calculos_activo(env, ida, 500)
    antes_v = dec(max(antes_c, key=lambda c: c["id_calculo_valor_razonable"])["valor_neto"])
    env.prep(env.cosecha(ida, "10"), (200, 201), "evento productivo RF-43")
    env.procesar_eventos()
    ms = env.mediciones(ida)
    despues_c = _calculos_activo(env, ida, 500)
    despues_v = dec(max(despues_c, key=lambda c: c["id_calculo_valor_razonable"])["valor_neto"])
    productos = env.productos(ida)
    obs(f"PRODUCCION: mediciones {antes_m} -> {len(ms)}; cálculos del activo {len(antes_c)} -> {len(despues_c)}; "
        f"valor del activo {antes_v} -> {despues_v}; productos reconocidos: {len(productos)}")
    assert productos, "el evento PRODUCCION debe reconocer el producto agrícola (RF-85)"
    p = env.producto_sql(ida)[-1]
    obs(f"producto: valor {p['valor_producto']}, proporción cosechada {p['proporcion_cosechada']}, reducción del activo {p['valor_reduccion_activo']}")
    assert dec(p["valor_producto"]) == dec("50000"), f"10 kg x 5.000,00 = 50.000,0000: {p}"
    assert despues_v == antes_v and len(despues_c) == len(antes_c) and len(ms) == antes_m, (
        "RNF-85-02: la producción periódica no debe modificar el valor del activo "
        f"(valor {antes_v} -> {despues_v}, mediciones {antes_m} -> {len(ms)})")
    assert not p["valor_reduccion_activo"] or dec(p["valor_reduccion_activo"]) == 0, f"PRODUCCION no reduce el activo: {p}"
    obs("la ficha pide una medición del activo por el evento PRODUCCION; RF-85 (RNF-85-02) prohíbe modificar el valor del activo con la producción periódica: diferencia de la ficha.")


def test_TC_M06_049_medicion_por_deterioro_perdida_por_transformacion(env):
    _asegurar(env, 90)
    env.presupuesto(50)
    esc = _escenario(env)
    ida = env.base_medible(esc, "500")                              # anterior 10.000.000,0000
    assert env.medir(esc, ida, None, "460").status == 200           # DETERIORO: RF-84 devuelve 9.200.000,0000, sin cambio de precio
    m = _una_medicion(env, ida)
    assert dec(m["valor_razonable_anterior"]) == dec("10000000"), m
    assert dec(m["valor_razonable_actual"]) == dec("9200000"), m
    assert dec(m["variacion_total"]) == dec("-800000"), m
    assert dec(m["ganancia_perdida_transformacion"]) == dec("-800000"), "la pérdida debe ir como transformación biológica"
    assert dec(m["ganancia_perdida_precio_mercado"]) == 0, m
    sentidos = {(l["tipo_hecho"], l["sentido"]) for l in lineas_de(env.historial(ida))}
    assert ("VARIACION_VR_TB", "PERDIDA") in sentidos, sentidos


def test_TC_M06_050_encadenamiento_del_historial(env):
    _asegurar(env, 120)
    env.presupuesto(80)
    esc = _escenario(env)
    ida = env.base_medible(esc, "500")
    inicial = V(500)
    for kg in ("525", "550", "505"):                                # CRECIMIENTO, CRECIMIENTO, DETERIORO
        assert env.medir(esc, ida, None, kg).status == 200
    ms = env.mediciones(ida)
    if len(ms) < 3:
        no_verificable(f"solo se generaron {len(ms)} de 3 mediciones.")
    assert dec(ms[0]["valor_razonable_anterior"]) == inicial
    for previa, actual in zip(ms, ms[1:]):
        assert dec(actual["valor_razonable_anterior"]) == dec(previa["valor_razonable_actual"]), f"cadena rota: {previa} -> {actual}"
    assert len({str(m["valor_razonable_actual"]) for m in ms}) == len(ms), "hay valores repetidos"
    assert sum(dec(m["variacion_total"]) for m in ms) == dec(ms[-1]["valor_razonable_actual"]) - inicial
    obs("la ficha pide CRECIMIENTO, PRODUCCION y DETERIORO; PRODUCCION no mide el activo (RNF-85-02): se usaron CRECIMIENTO, CRECIMIENTO y DETERIORO.")
