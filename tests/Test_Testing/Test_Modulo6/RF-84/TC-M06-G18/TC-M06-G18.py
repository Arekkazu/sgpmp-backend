# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-84: script del grupo TC-M06-G18 (pytest + sandbox, rol Contador) |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G18-V2.0.html |
# | 2026-11-13 | Daniela Castillo | M06 V2.0 (2.ª pasada): la base de datos pasa a ser la fuente de verdad (SQL ya funciona), expectativas alineadas con las correcciones de Desarrollo (notas de la versión 1.4.0) y las precondiciones que fallan ya no se omiten: quedan en rojo con diagnóstico |
"""
TC-M06-G18 - Rangos y precisión de las entradas del cálculo: costos, valor bruto y DECIMAL(18,4).   RF-84.   Casos: TC-M06-087 a TC-M06-090 (con subcasos 089b, 090a y 090b).

El bruto no es una entrada directa: es magnitud x precio (RF-89, 2 decimales, máx. 12 dígitos). Adaptaciones:
- 088: bruto inválido -> precio 0, -0,01, ausente y 'abc' en POST /finanzas/precios (RF-89 alimenta el bruto).
- 089: bruto de 4 decimales = 123,45 kg x 10.000,01 = 1.234.501,2345; costos manuales 0,0001+0,0002+0,0003+0,0004 -> neto 1.234.501,2335.
  Entrada con 5 decimales (100,00005): se documenta si rechaza o redondea.
- 090: el bruto no se puede ingresar directo. El mayor precio que acepta RF-89 es 99.999.999,99 (la tabla es NUMERIC(10,2); el DTO dice 12 dígitos pero
  9.999.999.999,99 responde 400 VALOR_FUERA_DE_RANGO). Un individuo no pasa de 9.999,99 kg y un lote POR_CABEZA está limitado por la capacidad del área
  (25.000 individuos), así que el máximo se forma con un lote POBLACIONAL por PESO_KG (bruto = cantidad x peso promedio x precio):
  1.000 cabezas x 1.000 kg x 99.999.999,99 = 99.999.999.990.000,00 (< 1e14) y 1.001 cabezas x 1.000 kg x 99.999.999,99 = 1.001.000 kg x 99.999.999,99 = 100.099.999.989.990,00 (>= 1e14, desborda NUMERIC(18,4)). Si M02 limita el peso promedio el caso queda NO VERIFICABLE;
  un 5xx sería el hallazgo a reportar.

Criterio de códigos: la ficha pide «error de validación» -> 400 (VAL_ENTRADA, que equivale al 422 de la ficha) o 422; cualquier otro código es desviación.
El 5xx nunca es aceptable. Los 5 decimales (089b) siguen el criterio de H-03: aceptar y redondear sin avisar es error.
El .json de esta carpeta (087 y 088) no se usa: este pytest cubre los cuatro casos; no hay tiempos que medir.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G18/TC-M06-G18.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G18/reporte-TC-M06-G18-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

JUSTIF = "Ajuste manual QA TC-M06 con soporte documental: cotización No. 789 del proveedor."


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


def _validacion(r) -> bool:
    return r.status in (400, 422)


def test_TC_M06_087_costos_negativos_se_rechazan(env):
    env.nuevo_run()          # run propio: cada caso dispone de sus 170 s
    env.presupuesto(40)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=("0.02", "0.03", "0.01"))
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    for comp in ("transporte", "comisiones", "impuestos", "otros"):
        r = env.confirmar(ida, cuerpo={"costos_manuales": {comp: "-0.01"}, "justificacion": JUSTIF})
        assert _validacion(r), f"costo negativo en {comp} debía rechazarse con error de validación (400/422) y respondió {r}"
    assert env.calculo(ida) is None, "no debe calcularse con costos negativos"
    assert env.contar("calculos_valor_razonable", ida) == 0, "base de datos: no debe existir cálculo con costos negativos"


def test_TC_M06_087b_costo_cero_se_acepta_en_cada_componente(env):
    """Ficha 087: «0 (acepta) por componente»: un activo por componente (la confirmación solo puede hacerse una vez por activo)."""
    env.nuevo_run()          # run propio: cada caso dispone de sus 170 s
    env.presupuesto(60)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=("0.02", "0.03", "0.01"))
    for comp in ("transporte", "comisiones", "impuestos", "otros"):
        ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
        r = env.confirmar(ida, cuerpo={"costos_manuales": {comp: "0"}, "justificacion": JUSTIF})
        assert r.status in (200, 201), f"el costo 0,0000 en {comp} debe aceptarse: {r}"
        c = env.calculo(ida)
        clave = {"transporte": "costo_transporte", "comisiones": "costo_comisiones", "impuestos": "costo_impuestos_transaccion",
                 "otros": "otros_costos_disposicion"}[comp]
        assert c is not None and dec(c[clave]) == 0, c
        env.comparar_calculo_bd(ida, c)


def test_TC_M06_088_valor_bruto_invalido_via_precio(env):
    env.nuevo_run()          # run propio: cada caso dispone de sus 170 s
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio=None)
    base = {"id_especie": esc.id_especie, "categoria": "POR_CABEZA", "fecha_vigencia": str(hoy() - timedelta(days=1)),
            "fuente": "MERCADO_ACTIVO", "evidencia_documental": "Boletín QA", "confirmar_desviacion": True}
    for nombre, extra in (("cero", {"precio_unitario": "0"}), ("negativo", {"precio_unitario": "-0.01"}),
                          ("ausente", {}), ("no numérico", {"precio_unitario": "abc"})):
        r = env.call("POST", "/finanzas/precios", "contador", json={**base, **extra})
        assert _validacion(r), f"precio {nombre} debía rechazarse con error de validación (400/422) y respondió {r}"
    n = uno(env.sql(f"SELECT count(*) AS n FROM modulo6.precios_mercado WHERE id_especie = {int(esc.id_especie)}"))
    assert int(n) == 0, "ninguna petición inválida debe registrar un precio"


def test_TC_M06_089_precision_de_cuatro_decimales(env):
    env.nuevo_run()          # run propio: cada caso dispone de sus 170 s
    env.presupuesto(50)
    esc = env.escenario(categoria="PESO_KG", precio="10000.01", costos=None)
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None, peso_kg="123.45")
    manuales = {"transporte": "0.0001", "comisiones": "0.0002", "impuestos": "0.0003", "otros": "0.0004"}
    r = env.confirmar(ida, cuerpo={"costos_manuales": manuales, "justificacion": JUSTIF})
    assert r.status in (200, 201), r
    c = env.calculo(ida)
    assert dec(c["valor_razonable_bruto"]) == dec("1234501.2345") and dec(c["valor_neto"]) == dec("1234501.2335"), c
    bd = env.comparar_calculo_bd(ida, c)
    assert dec(bd["valor_razonable_bruto"]) == dec("1234501.2345") and dec(bd["valor_neto"]) == dec("1234501.2335"), f"base de datos: {bd}"


def test_TC_M06_089b_entrada_con_cinco_decimales(env):
    """Ficha 089: con 5 decimales «se rechaza o redondea con regla explícita documentada». Aceptar y redondear sin avisar es error (H-03)."""
    env.nuevo_run()          # run propio: cada caso dispone de sus 170 s
    env.presupuesto(30)
    esc = env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=None)
    ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None)
    r = env.confirmar(ida, cuerpo={"costos_manuales": {"transporte": "100.00005"}, "justificacion": JUSTIF})
    assert r.status < 500, f"5 decimales no debe producir error de servidor: {r}"
    # INC-M06-303 (corregido por Desarrollo, #990): más de 4 decimales se rechaza con 400 (ya no se acepta ni se redondea).
    assert _validacion(r), (f"INC-M06-303: 100.00005 (5 decimales) debía rechazarse con 400/422 y respondió {r}; "
                            f"cálculo guardado: {env.calculo(ida)}")
    assert env.calculo(ida) is None and env.contar("calculos_valor_razonable", ida) == 0, "el rechazo no debe dejar cálculo guardado (API ni base)"


CEROS = {"costos_manuales": {"transporte": "0", "comisiones": "0", "impuestos": "0", "otros": "0"}, "justificacion": JUSTIF}
PRECIO_MAX = "99999999.99"


def _lote(env, esc, cabezas: int, kg_promedio: str):
    """Lote POBLACIONAL con fase activa y pesaje (M06 mide por kilogramo solo con un pesaje registrado). Devuelve (id_activo, respuesta del paso que falló o None)."""
    a = env.activo_r(esc, origen="nacimiento", costo=None, soporte=None, tipo="POBLACIONAL", cantidad=cabezas, peso_promedio="1")
    if a.status not in (200, 201):
        return None, a
    ida = a.get("id_activo_biologico")
    f = env.asignar_fase(ida)
    if f.status not in (200, 201):
        return ida, f
    p = env.call("POST", f"/activos-biologicos/{ida}/eventos/crecimiento", "admin", json={
        "tipo_medicion": "PESO", "valor_medicion": kg_promedio, "unidad_medida": "kg", "nuevo_peso_promedio": kg_promedio,
        "cantidad_medida": cabezas, "tipo_agregacion": "PROMEDIO"})
    return ida, (p if p.status not in (200, 201) else None)


def test_TC_M06_090a_valor_cercano_al_maximo_se_acepta(env):
    """Bruto 1.000 cabezas x 1.000 kg x 99.999.999,99 = 99.999.999.990.000,0000 (< 1e14; el mayor precio de RF-89)."""
    env.nuevo_run()
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio=PRECIO_MAX, costos=None)
    ida, falla = _lote(env, esc, 1000, "1000")
    if falla is not None:
        no_verificable(f"M02 no admite el lote de 1.000 cabezas de 1.000 kg necesario para acercarse al máximo: {falla}")
    r = env.confirmar(ida, cuerpo=CEROS)
    assert r.status in (200, 201), f"el valor cercano al máximo debía aceptarse: {r}"
    assert dec(env.calculo(ida)["valor_razonable_bruto"]) == dec("99999999990000.0000")
    assert dec(env.calculo_bd(ida)["valor_razonable_bruto"]) == dec("99999999990000.0000"), "base de datos: el bruto cercano al máximo debe guardarse completo"


def test_TC_M06_090b_valor_que_desborda_se_rechaza_sin_5xx(env):
    """Bruto 1.001 cabezas x 1.000 kg x 99.999.999,99 = 100.099.999.989.990,00 >= 1e14: desborda NUMERIC(18,4)."""
    env.nuevo_run()
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio=PRECIO_MAX, costos=None)
    ida, falla = _lote(env, esc, 1001, "1000")
    if falla is not None:
        obs(f"M02 rechaza el lote de 1.001 cabezas de 1.000 kg o su pesaje (HTTP {falla.status}) antes de llegar a M06.")
        no_verificable("no se puede formar un bruto >= 1e14 porque M02 limita el peso o la cantidad del lote.")
    r = env.confirmar(ida, cuerpo=CEROS)
    assert r.err not in ("SIN_MAGNITUD", "SIN_PRECIO"), f"el rechazo no es por desborde sino por falta de datos del activo: {r}"
    assert _validacion(r), f"el valor que desborda DECIMAL(18,4) debe rechazarse con error de validación (400/422), sin 5xx, y respondió {r}"
    assert env.calculo(ida) is None, "no debe quedar un cálculo con el valor desbordado"
    assert env.contar("calculos_valor_razonable", ida) == 0, "base de datos: no debe quedar cálculo con el valor desbordado"
