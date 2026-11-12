# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-83: script del grupo TC-M06-G11 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-83: G11 con 20 mediciones aleatorias (varios runs), +-0,0001 y valor máximo DECIMAL(18,4) |
"""
TC-M06-G11 - Separación de efectos (transformación y precio) y valores límite de la variación.   RF-83 (CU02).   Casos: TC-M06-054 a TC-M06-057.

Fórmula del RF (pasos 4-6): pre_evento_ajustado = valor con la magnitud ANTERIOR y el precio NUEVO; precio = pre_ajustado - anterior;
transformación = actual - pre_ajustado; precio + transformación = actual - anterior (exacto, RNF-83-05).

- 054: la ficha usa anterior 10.000.000 / pre-ajustado 10.400.000 / actual 10.900.000. Con precios de 2 decimales y pesos de 2 decimales
  no existe una combinación que dé exactamente esos tres valores (la razón 109/104 obliga a un factor 13 que no divide a 10^n). Se usa
  anterior 10.000.000 y pre-ajustado 10.400.000 (precio +4 %: 20.000 -> 20.800, 500 kg) y actual 10.920.000 (525 kg): precio 400.000,
  transformación 520.000, suma 920.000. Costos de venta en cero.
- 055: 20 mediciones aleatorias (semilla fija 20261107) repartidas en varios runs del sandbox (cada run dura 170 s; cada caso abre su run porque la especie de peso es compartida); se leen las columnas de
  variación por SELECT antes de cerrar cada run.
- 056: variación 0: el backend no registra medición y deja MEDICION_SIN_VARIACION; la ficha permite documentar ese comportamiento.
- 057: +0,0001 y -0,0001 (precio 0,01 y diferencia de 0,01 kg) deben registrarse exactos; valor máximo 99.999.999.999.999,9999 =
  9.999.999,99 kg x 10.000.000,01 por kg (producto exacto, costos en cero).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G11/TC-M06-G11.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G11/reporte-TC-M06-G11.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

P = "20000.00"
SIN_COSTOS = ("0", "0", "0")


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


def _nuevo(env):
    """Cada caso abre su propio run: las categorías de peso comparten la especie sembrada (4) y un precio registrado en un caso
    seguiría vigente en el siguiente si compartieran run (el precio más reciente de la especie manda)."""
    if env.inicio is not None:
        env.nuevo_run()


def _filas(env, ida):
    """Columnas de variación de las mediciones del activo, leídas por SELECT (texto exacto, orden de creación)."""
    return env.sql("SELECT valor_razonable_anterior::text AS anterior, valor_razonable_actual::text AS actual, "
                   "ganancia_perdida_precio_mercado::text AS precio, ganancia_perdida_transformacion::text AS transf, "
                   "variacion_total::text AS total FROM modulo6.mediciones_posteriores "
                   f"WHERE id_activo_biologico = {int(ida)} ORDER BY id_medicion_posterior")


def _suma_exacta(f):
    return dec(f["precio"]) + dec(f["transf"]) == dec(f["actual"]) - dec(f["anterior"]) == dec(f["total"])


def test_TC_M06_054_separacion_de_efectos_con_evento_y_cambio_de_precio(env):
    _nuevo(env)
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio=P, costos=SIN_COSTOS)
    ida = env.base_medible(esc, "500")                              # anterior 10.000.000,0000
    assert env.medir(esc, ida, "20800.00", "525").status == 200     # pre-ajustado 500 kg x 20.800 = 10.400.000; actual 525 x 20.800
    fs = _filas(env, ida)
    if not fs:
        no_verificable("no se generó medición.")
    f = fs[-1]
    assert dec(f["anterior"]) == dec("10000000"), f
    assert dec(f["actual"]) == dec("10920000"), f
    assert dec(f["precio"]) == dec("400000"), f"efecto precio = pre-ajustado (10.400.000) - anterior (10.000.000): {f}"
    assert dec(f["transf"]) == dec("520000"), f"transformación = actual (10.920.000) - pre-ajustado (10.400.000): {f}"
    assert _suma_exacta(f) and dec(f["total"]) == dec("920000"), f
    obs("valores de la ficha no construibles exactamente (precio y peso de 2 decimales): se usó actual 10.920.000 en lugar de 10.900.000.")


def test_TC_M06_055_suma_exacta_en_un_lote_de_20_mediciones_aleatorias(env):
    azar = random.Random(20261107)
    reunidas: list[dict] = []                       # columnas de variación de todas las mediciones
    entradas: list[tuple] = []                      # (kg anterior, precio nuevo, kg nuevo, valor anterior) de cada medición
    iteraciones = vueltas = 0
    while len(reunidas) < 20 and iteraciones < 40 and vueltas < 6:
        vueltas += 1
        _nuevo(env)
        env.presupuesto(80)
        esc = env.escenario(categoria="PESO_KG", precio=P)
        ida = env.base_medible(esc, "400")
        kg_ant, vn_ant = 400, vn(400, P)
        propias: list[tuple] = []
        while len(reunidas) + len(propias) < 20 and env.restante() > 28:
            iteraciones += 1
            precio = f"{azar.randint(15000, 26000)}.{azar.randint(0, 99):02d}"
            kg = azar.randint(300, 600)
            while kg == kg_ant:
                kg = azar.randint(300, 600)
            env.medir(esc, ida, precio, str(kg))
            actual = vn(kg, precio)
            propias.append((kg_ant, precio, kg, vn_ant, actual))
            kg_ant, vn_ant = kg, actual
        fs = _filas(env, ida)                       # se leen antes de que el run se cierre
        assert len(fs) == len(propias), f"cada paso debe dejar una medición: {len(fs)} filas para {len(propias)} pasos"
        reunidas += fs
        entradas += propias
    assert len(reunidas) == 20, f"se esperaban 20 mediciones y se reunieron {len(reunidas)}"
    for f, (kg_ant, precio, kg, vn_ant, vn_act) in zip(reunidas, entradas):
        assert _suma_exacta(f), f"la suma de efectos no es exacta (diferencia distinta de 0,0000): {f}"
        pr, tr = efectos(vn_ant, vn_act, kg_ant, precio)
        assert cerca(f["precio"], pr) and cerca(f["transf"], tr), f"efectos esperados precio {pr}, transformación {tr}: {f}"
    obs(f"20 mediciones aleatorias (positivas y negativas) verificadas en {iteraciones} pasos; positivas: "
        f"{sum(1 for f in reunidas if dec(f['total']) > 0)}, negativas: {sum(1 for f in reunidas if dec(f['total']) < 0)}.")


def test_TC_M06_056_variacion_cero(env):
    _nuevo(env)
    env.presupuesto(50)
    esc = env.escenario(categoria="PESO_KG", precio=P)
    ida = env.base_medible(esc, "400")
    assert env.medir(esc, ida, None, "400").status == 200       # mismo peso y mismo precio: actual = anterior
    tipos = env.tipos_auditoria(ida)
    fs = _filas(env, ida)
    assert "MEDICION_PENDIENTE" not in tipos, f"una variación 0 no debe generar alerta de pendiente: {tipos}"
    if fs:
        assert dec(fs[-1]["precio"]) == 0 and dec(fs[-1]["transf"]) == 0 and dec(fs[-1]["total"]) == 0, fs[-1]
        obs("variación 0,0000: la medición se registró con ambos efectos y la variación en 0,0000.")
    else:
        assert "MEDICION_SIN_VARIACION" in tipos, "si no se registra la medición debe quedar al menos el evento MEDICION_SIN_VARIACION"
        obs("variación 0,0000: no se crea medición; queda el evento MEDICION_SIN_VARIACION, sin alerta ni error (la ficha permite documentarlo).")


@pytest.mark.parametrize("kg_final,signo", [("400.01", 1), ("399.99", -1)], ids=["mas_0_0001", "menos_0_0001"])
def test_TC_M06_057_variacion_minima_de_0_0001(env, kg_final, signo):
    _nuevo(env)
    env.presupuesto(50)
    esc = env.escenario(categoria="PESO_KG", precio="0.01", costos=SIN_COSTOS)       # 0,01 por kg: 0,01 kg = 0,0001
    ida = env.base_medible(esc, "400")                                               # valor 4,0000
    assert env.medir(esc, ida, None, kg_final).status == 200
    fs = _filas(env, ida)
    ultimo = max(env.historial(ida)["calculos"], key=lambda c: c["id_calculo_valor_razonable"])
    obs(f"{kg_final} kg a 0,01: mediciones registradas {len(fs)}; valor vigente del activo {ultimo['valor_neto']} "
        f"(el esperado era {dec('4') + dec('0.0001') * signo}); eventos {env.tipos_auditoria(ida)}")
    assert fs, ("la variación de 0,0001 no se registró: no hay medición y el valor vigente del activo quedó en el anterior. "
                "La ficha (RF-83 CA-1/CA-6, DECIMAL(18,4)) espera el registro exacto.")
    f = fs[-1]
    assert dec(f["total"]) == dec("0.0001") * signo and _suma_exacta(f), f
    assert dec(f["actual"]) == dec("4") + dec("0.0001") * signo, f


def test_TC_M06_057_valor_maximo_decimal_18_4(env):
    _nuevo(env)
    env.presupuesto(60)
    esc = env.escenario(categoria="PESO_KG", precio="10000000.01", costos=SIN_COSTOS)
    ida = env.base_medible(esc, "1")                                                 # valor 10.000.000,0100
    assert env.medir(esc, ida, None, "9999999.99").status == 200                     # 9.999.999,99 x 10.000.000,01
    fs = _filas(env, ida)
    if not fs:
        no_verificable(f"no se generó medición para el valor máximo; eventos {env.tipos_auditoria(ida)}")
    f = fs[-1]
    assert dec(f["actual"]) == dec("99999999999999.9999"), f"el valor máximo debe aceptarse sin desbordamiento: {f}"
    assert _suma_exacta(f), f"la suma de efectos debe seguir siendo exacta: {f}"
