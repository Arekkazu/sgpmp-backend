# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-85: script del grupo TC-M06-G25 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-85 G25: se verifica exactamente lo que pide la ficha (error de validación 400/422 en 0 y -1; proporción exacta; 100,01 % rechazado con mensaje; valor_reduccion con 4 decimales) y cada caso abre su propio run |
# | 2026-11-08 | Daniela Castillo | M06 RF-85 G25: RF-43 (M02) define cantidad_producida como decimal(12,3), por lo que la ficha (0,0001 y 33,3333 kg) pide cantidades que el evento productivo no admite; 112 y 114 se prueban con 0,001 y 33,333 kg (el 0,0001 se envía y se documenta) |
# | 2026-11-08 | Daniela Castillo | M06 RF-85 G25: la proporción se guarda con 4 decimales, que es la precisión aprobada del sistema; 112c comprueba ese redondeo y que valor_reduccion use la proporción exacta (ya no se exige la proporción sin redondear) |
# | 2026-11-08 | Daniela Castillo | M06 RF-85 G25: decisión de QA: la cosecha mínima que M02 acepta (0,001 kg) y M06 no reconoce se mantiene como error de integración M02-M06; 112b y 112c verifican que se reconozca |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G25-V2.0.html |
# | 2026-11-13 | Daniela Castillo | M06 V2.0 (2.ª pasada): la base de datos pasa a ser la fuente de verdad (SQL ya funciona), expectativas alineadas con las correcciones de Desarrollo (notas de la versión 1.4.0) y las precondiciones que fallan ya no se omiten: quedan en rojo con diagnóstico |
"""
TC-M06-G25 - Valores límite de cantidad cosechada, proporción y precisión del reconocimiento del producto.   RF-85 (CU04).   Casos: TC-M06-112 a TC-M06-114.

Precondición común (RF-43): el evento productivo de M02 exige una fase activa de un ciclo de M09. QA no puede crear ciclos, por lo que se usa la
especie productiva sembrada de TEST (Cachama: métrica PESO en kg, ciclo 4; variables QA_ID_ESPECIE_PRODUCTIVA / _METRICA_ / _CICLO_) y se asigna la fase con
POST /activos-biologicos/{id}/fases. Si M02 responde 5xx o rechaza (defecto previo de RF-37), el caso queda BLOQUEADO. Un producto no puede registrarse
dos veces el mismo día para un activo (409): cada caso usa un activo propio. Valores con costos de venta de M09 del 2 %+3 %+1 % (6 %) salvo en 114 (sin costos).
Consumo = especie CONSUMO con categoría PESO_KG: proporción = cosechado / magnitud del activo; valor_reduccion = valor neto x proporción. Escala: activo de 1.000 kg a 20.000,00
-> 18.800.000,0000 (112 y 113) y de 100 kg a 10,00 -> 1.000,0000 sin costos (114).
Diferencia entre la ficha y el RF: la ficha pide la cantidad mínima 0,0001 (112) y 33,3333 kg (114), pero RF-43 define cantidad_producida como decimal(12,3) (tres decimales) y RF-85
define cantidad_cosechada como DECIMAL(18,4): el evento productivo solo puede traer tres decimales. Se prueba con la cantidad mínima real (0,001) y con 33,333 kg; la cantidad 0,0001
se envía antes y se documenta lo que responde RF-43.
- 112: 0 y -1 se rechazan con error de validación (400 VAL_ENTRADA o 422). La cantidad mínima positiva se acepta (112b). La proporción se guarda con 4 decimales (precisión
  aprobada del sistema; el RF no define otra): 0,001 kg sobre 1.000 kg = 0,000001 queda en 0,0000, y valor_reduccion se calcula con la proporción exacta (112c).
- 113: 999,9 kg (99,99 %): reduce casi todo el activo sin completarlo; 1.000 kg (100 %): completa (el valor en 0, el estado COSECHADO_COMPLETAMENTE y la baja de RF-45 ya
  se verifican en G24 110b, 110c y 110d y no se repiten aquí); 1.000,1 kg (100,01 %): se rechaza indicando que supera la cantidad disponible del activo.
- 114: activo de 100 kg y 1.000,0000, cosecha de 33,333 kg: importes con 4 decimales exactos (valor_reduccion = 1.000,0000 x 0,33333 = 333,3300) (114) y lo reducido más lo que
  queda en el activo suma el valor anterior (114b). La precisión real de la proporción almacenada se documenta (el RF no la define).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G25/TC-M06-G25.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G25/reporte-TC-M06-G25-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()

P_ACT = "20000.00"
NETO = vn(1000, P_ACT)                        # 18.800.000,0000
MENSAJE_SUPERA = re.compile(r"supera|excede|exced|mayor|disponible|total", re.I)


def _activo(env, kg="1000", precio=P_ACT, costos=("0.02", "0.03", "0.01")):
    esc = env.escenario_producto("CONSUMO", precio, costos=costos)
    ida = env.activo_productivo(esc, kg)
    antes = env.calculo(ida)
    assert antes and dec(antes["magnitud"]) == dec(kg), f"activo antes de la cosecha: {antes}"
    return esc, ida


def _cosecha_aceptada(env, ida, kg):
    env.prep(env.cosecha(ida, kg), (200, 201), f"evento productivo de {kg} kg")
    env.procesar_eventos()
    filas = env.producto_sql(ida)
    assert filas, f"{kg} kg debía reconocerse como producto (eventos: {env.tipos_auditoria(ida)})"
    return filas[-1]


def test_TC_M06_112_cantidad_cero_y_negativa_se_rechazan_con_error_de_validacion(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida = _activo(env)
    fallos = []
    for cantidad in ("0", "-1"):
        r = env.cosecha(ida, cantidad)
        if r.status not in (400, 422):
            fallos.append(f"cantidad {cantidad}: la ficha pide error de validación (400 VAL_ENTRADA o 422) y respondió {r}")
    assert not env.producto_sql(ida), "no debía reconocerse ningún producto con cantidad 0 o -1"
    assert not fallos, " | ".join(fallos)


_RESULTADO_COLA = {}


@pytest.fixture(scope="module")
def minimo(env):
    """Cantidad mínima positiva sobre un activo de 1.000 kg: un solo run para 112b y 112c. Primero 0,0001 (la ficha; se documenta) y luego 0,001 (la mínima de RF-43)."""
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida = _activo(env)
    r0 = env.cosecha(ida, "0.0001")
    obs(f"0,0001 kg (la ficha): el evento productivo (RF-43, decimal(12,3)) respondió HTTP {r0.status}: {(r0.text or '')[:200]}")
    env.prep(env.cosecha(ida, "0.001"), (200, 201), "evento productivo de 0,001 kg (cantidad mínima de RF-43)")
    rp = env.procesar_eventos()
    obs(f"procesamiento de la cola con la cosecha de 0,001 kg sobre 1.000 kg (proporción exacta 0,000001): HTTP {rp.status} {(rp.text or '')[:300]}")
    _RESULTADO_COLA["min"] = rp
    return ida


def test_TC_M06_112b_cantidad_minima_positiva_se_acepta(env, minimo):
    filas = env.producto_sql(minimo)
    rp = _RESULTADO_COLA.get("min")
    assert filas, (f"la cantidad mínima positiva (0,001 kg sobre 1.000 kg) debía reconocerse y no se creó el producto; resultado de la cola: "
                   f"{(rp.text or '')[:300] if rp else 'n/d'}; auditoría: {env.tipos_auditoria(minimo)}. "
                   "INC-M06-322 (corregido, #1009): la proporción 0,000001 debe guardarse con 6 decimales y nunca en 0")
    p = filas[-1]
    esperado = trunc2(NETO * dec("0.000001"))
    assert dec(p["valor_reduccion_activo"]) == esperado, f"valor_reduccion esperado {esperado} (18.800.000 x 0,000001): {p}"
    assert dec(p["cantidad_cosechada"]) == dec("0.001"), f"cantidad_cosechada debía quedar en 0,001: {p}"


def test_TC_M06_112c_proporcion_del_minimo_con_seis_decimales_y_nunca_cero(env, minimo):
    filas = env.producto_sql(minimo)
    assert filas, f"no se reconoció el producto: {env.tipos_auditoria(minimo)}"
    p = filas[-1]
    obs(f"proporcion_cosechada guardada para 0,001 de 1.000 kg: {p['proporcion_cosechada']} (exacta 0,000001); valor_reduccion {p['valor_reduccion_activo']}")
    # INC-M06-322 (corregido por Desarrollo, #1009): la proporción se guarda con 6 decimales y nunca queda en 0. Reemplaza la precisión de 4 decimales.
    assert dec(p["proporcion_cosechada"]) > 0, f"INC-M06-322: la proporción nunca debe quedar en 0: {p}"
    assert dec(p["proporcion_cosechada"]) == dec("0.000001"), f"INC-M06-322: la proporción debía guardarse con 6 decimales (0,000001): {p}"
    assert dec(p["valor_reduccion_activo"]) == trunc2(NETO * dec("0.000001")), f"valor_reduccion debía calcularse con la proporción exacta: {p}"


def test_TC_M06_113_99_99_por_ciento_reduce_casi_todo_sin_completar(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida = _activo(env)
    p = _cosecha_aceptada(env, ida, "999.9")
    assert dec(p["proporcion_cosechada"]) == dec("0.9999"), f"proporción esperada 0,9999: {p}"
    assert dec(p["valor_reduccion_activo"]) == trunc2(NETO * dec("0.9999")), f"valor_reduccion esperado {trunc2(NETO * dec('0.9999'))}: {p}"
    c = env.calculo(ida)
    assert dec(c["magnitud"]) > 0 and dec(c["valor_neto"]) > 0 and cerca(c["valor_neto"], vn("0.1", P_ACT)), (
        f"el activo debía quedar con 0,1 kg y {vn('0.1', P_ACT)} (sin completarse): {c}")


def test_TC_M06_113_100_por_ciento_se_acepta_y_completa(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida = _activo(env)
    p = _cosecha_aceptada(env, ida, "1000")
    assert dec(p["proporcion_cosechada"]) == 1, f"proporción esperada 1: {p}"
    assert dec(p["valor_reduccion_activo"]) == trunc2(NETO), f"valor_reduccion = valor total {trunc2(NETO)}: {p}"


def test_TC_M06_113_100_01_por_ciento_se_rechaza_indicando_que_supera_lo_disponible(env):
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida = _activo(env)
    r = env.cosecha(ida, "1000.1")
    if 400 <= r.status < 500:
        obs(f"1.000,1 kg rechazado al registrar el evento: HTTP {r.status} {(r.text or '')[:300]}")
        assert not env.producto_sql(ida), "no debía reconocerse ningún producto"
        assert MENSAJE_SUPERA.search(r.text or ""), f"el rechazo debía indicar que supera la cantidad disponible del activo y dice: {(r.text or '')[:200]}"
        return
    env.prep(r, (200, 201), "evento productivo de 1.000,1 kg")
    res = env.procesar_eventos()
    filas = env.producto_sql(ida)
    obs(f"1.000,1 kg aceptado al registrar el evento (HTTP {r.status}); procesamiento de la cola: HTTP {res.status} {(res.text or '')[:300]}; productos reconocidos: {len(filas)}")
    assert not filas, (f"una cosecha de 1.000,1 kg (100,01 % de un activo de 1.000 kg) debía rechazarse y se reconoció: proporción {filas[-1]['proporcion_cosechada']}, "
                       f"valor_reduccion {filas[-1]['valor_reduccion_activo']}, cantidad_cosechada {filas[-1]['cantidad_cosechada']}")


@pytest.fixture(scope="module")
def p114(env):
    """Activo de 100 kg a 10,00 (1.000,0000 sin costos) y cosecha de 33,333 kg: un solo run para 114 y 114b."""
    env.nuevo_run()
    env.presupuesto(70)
    esc, ida = _activo(env, kg="100", precio="10.00", costos=("0", "0", "0"))
    antes = env.calculo(ida)
    assert dec(antes["valor_neto"]) == dec("1000.0000"), f"valor del activo antes: {antes}"
    env.prep(env.cosecha(ida, "33.333"), (200, 201), "evento productivo de 33,333 kg")
    env.procesar_eventos()
    filas = env.producto_sql(ida)
    assert filas, f"no se reconoció el producto: {env.tipos_auditoria(ida)}"
    return filas[-1], env.calculo(ida)


def test_TC_M06_114_valor_reduccion_con_cuatro_decimales_exactos(p114):
    p, c = p114
    obs(f"proporcion_cosechada guardada: {p['proporcion_cosechada']} (exacta: 0,33333; el RF no define la precisión y se documenta); valor_reduccion {p['valor_reduccion_activo']}; "
        f"valor_producto {p['valor_producto']}; activo después: magnitud {c['magnitud']}, valor {c['valor_neto']}")
    assert dec(p["cantidad_cosechada"]) == dec("33.333"), f"cantidad_cosechada debía quedar en 33,333: {p}"
    assert dec(p["valor_reduccion_activo"]) == dec("333.3300"), (
        f"valor_reduccion esperado 333,3300 (1.000,0000 x 0,33333) y se guardó {p['valor_reduccion_activo']}: {p}")


def test_TC_M06_114b_lo_reducido_mas_lo_que_queda_suma_el_valor_anterior(p114):
    p, c = p114
    suma = dec(p["valor_reduccion_activo"]) + dec(c["valor_neto"])
    assert suma == dec("1000.0000"), (
        f"valor_reduccion {p['valor_reduccion_activo']} + valor que queda en el activo {c['valor_neto']} = {suma}; debía sumar el valor anterior 1.000,0000")
