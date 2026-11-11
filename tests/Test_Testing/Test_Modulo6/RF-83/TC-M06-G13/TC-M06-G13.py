# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-83: script del grupo TC-M06-G13 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | M06 RF-83: G13 con resultado por baja, clasificación, cuentas y exclusión del cierre |
"""
TC-M06-G13 - Baja del activo en la medición posterior: venta, pérdida y exclusión posterior.   RF-83 (FA-3, CA-9, RFC-018).   Casos: TC-M06-061 a TC-M06-064.

Lo que pide el RF (FA-3 + RFC-018): el evento BAJA no invoca RF-84; la variación final = valor_baja - último valor razonable; si la baja es por venta
se considera resultado por baja y si es por deterioro o pérdida se clasifica como pérdida por transformación biológica; además se emite a RF-86 el
hecho BAJA_ACTIVO por el valor en libros (débito costo de venta / pérdida por baja, crédito activo biológico); en una venta SGPMP no registra
ingreso ni cuenta por cobrar; el historial queda cerrado.
Lo que existe en el backend: el hecho BAJA_ACTIVO por el valor en libros (UNICO para venta y sacrificio, PERDIDA para el resto). El evento de baja de M02
no trae valor_baja (solo tipo_baja, fecha_baja, motivo_baja y cantidad_afectada) y M06 no registra el resultado por baja ni la variación clasificada:
esas partes se prueban y, si no existen, el caso queda BLOQUEADO como funcionalidad no implementada (se reporta como error).
Activo de 400 kg a 20.000,00 por kg con costos 2/3/1 %: valor en libros 7.520.000,0000 (la ficha usa 10.000.000 como escala).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G13/TC-M06-G13.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G13/reporte-TC-M06-G13.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

P = "20000.00"
LIBROS = vn(400, P)
_ESC: dict = {}


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


def _esc(env, segundos=70):
    """Escenario del run vigente; si queda poco tiempo se abre otro run (un run dura 170 s) y se crea otro escenario."""
    if env.inicio is not None and env.restante() < segundos:
        env.nuevo_run()
    if _ESC.get("run") != env.run_id:
        _ESC["esc"] = env.escenario(categoria="PESO_KG", precio=P)
        _ESC["run"] = env.run_id
    return _ESC["esc"]


def _dar_de_baja(env, tipo):
    esc = _esc(env)
    env.presupuesto(40)
    ida = env.base_medible(esc, "400")
    calculos = len(env.historial(ida)["calculos"])
    env.prep(env.baja(ida, tipo), (200, 201), f"evento de baja ({tipo})")
    assert env.procesar_eventos().status == 200
    return esc, ida, calculos


def _lineas(env, ida, tipo_hecho=None):
    extra = f" AND tipo_hecho::text = '{tipo_hecho}'" if tipo_hecho else ""
    return env.sql("SELECT tipo_hecho::text AS tipo_hecho, sentido::text AS sentido, valor, cuenta_debito, cuenta_credito "
                   f"FROM modulo6.lineas_asiento_nic41 WHERE id_activo_biologico = {int(ida)} AND NOT es_reverso{extra} ORDER BY id_linea_asiento_nic41")


def _variaciones(env, ida):
    return env.sql("SELECT tipo::text AS tipo, monto_variacion::text AS monto FROM modulo6.variaciones_valor_razonable "
                   f"WHERE id_activo_biologico = {int(ida)}")


def test_TC_M06_061a_baja_por_venta_emite_baja_activo_por_el_valor_en_libros(env):
    esc, ida, calculos = _dar_de_baja(env, "venta")
    lineas = _lineas(env, ida, "BAJA_ACTIVO")
    assert len(lineas) == 1, f"debía existir un hecho BAJA_ACTIVO: {lineas}"
    assert dec(lineas[0]["valor"]) == trunc2(LIBROS), f"BAJA_ACTIVO debe ser por el valor en libros {LIBROS}: {lineas[0]}"
    assert lineas[0]["sentido"] == "UNICO", lineas[0]
    esperado = CUENTAS_MATRIZ[("BAJA_ACTIVO", "UNICO")]
    assert (lineas[0]["cuenta_debito"], lineas[0]["cuenta_credito"]) == esperado, f"débito costo de venta / crédito activo biológico: {lineas[0]}"
    assert not env.mediciones(ida), "RF-83 no invoca RF-84 en la baja: no debe crearse medición"
    assert len(env.historial(ida)["calculos"]) == calculos, "la baja no debe calcular un nuevo valor razonable (RF-84)"


def test_TC_M06_061b_resultado_por_baja_variacion_valor_baja_menos_anterior(env):
    esc, ida, _ = _dar_de_baja(env, "venta")
    variaciones = _variaciones(env, ida)
    if not variaciones:
        bloqueado("funcionalidad no implementada: RF-83 FA-3 / CA-9 piden registrar la variación final (valor_baja - último valor razonable) como "
                  "resultado por baja. El evento de baja de M02 no trae valor_baja (solo tipo_baja, fecha_baja, motivo_baja, cantidad_afectada) y M06 "
                  f"solo emite BAJA_ACTIVO por el valor en libros; no hay variación registrada del activo ({variaciones}).")
    assert any("BAJA" in v["tipo"] for v in variaciones), f"debe registrarse el resultado por baja: {variaciones}"


def test_TC_M06_062_baja_por_venta_no_registra_ingreso_ni_cuenta_por_cobrar(env):
    esc, ida, _ = _dar_de_baja(env, "venta")
    todas = _lineas(env, ida)
    nuevas = [(f["tipo_hecho"], f["sentido"]) for f in todas if f["tipo_hecho"] != "RECONOCIMIENTO_NACIMIENTO"]
    assert nuevas == [("BAJA_ACTIVO", "UNICO")], f"solo debe existir el hecho BAJA_ACTIVO tras el reconocimiento: {todas}"
    assert not [f for f in todas if "INGRESO" in f["tipo_hecho"].upper() or "COBRAR" in f["tipo_hecho"].upper()], todas


@pytest.mark.parametrize("tipo", ["muerte", "perdida"])
def test_TC_M06_063a_baja_por_perdida_emite_baja_activo_perdida(env, tipo):
    esc, ida, _ = _dar_de_baja(env, tipo)
    lineas = _lineas(env, ida, "BAJA_ACTIVO")
    assert len(lineas) == 1 and lineas[0]["sentido"] == "PERDIDA", lineas
    assert dec(lineas[0]["valor"]) == trunc2(LIBROS), lineas[0]
    esperado = CUENTAS_MATRIZ[("BAJA_ACTIVO", "PERDIDA")]
    assert (lineas[0]["cuenta_debito"], lineas[0]["cuenta_credito"]) == esperado, lineas[0]
    assert not env.mediciones(ida)


def test_TC_M06_063b_la_variacion_de_la_baja_se_clasifica_como_perdida_por_transformacion(env):
    esc, ida, _ = _dar_de_baja(env, "muerte")
    variaciones = _variaciones(env, ida)
    esperado = dec(-LIBROS)
    if not variaciones:
        bloqueado("funcionalidad no implementada: RF-83 FA-3 (deterioro o pérdida) pide registrar la variación final (0 - último valor razonable = "
                  f"{esperado}) clasificada como pérdida por transformación biológica; M06 solo emite BAJA_ACTIVO PERDIDA por el valor en libros y no "
                  "registra variación ni medición final del activo.")
    assert any(v["tipo"] == "PERDIDA_TRANSFORMACION_BIOLOGICA" and dec(v["monto"]) == esperado for v in variaciones), variaciones


def test_TC_M06_064a_crecimiento_sobre_activo_dado_de_baja_no_crea_medicion(env):
    esc, ida, _ = _dar_de_baja(env, "perdida")
    n_lineas = len(_lineas(env, ida, "BAJA_ACTIVO"))
    r = env.call("POST", f"/activos-biologicos/{ida}/eventos/crecimiento", "admin", json={
        "tipo_medicion": "PESO", "valor_medicion": "500", "unidad_medida": "kg"})
    assert r.status < 500, f"error de servidor: {r}"
    env.procesar_eventos()
    assert not env.mediciones(ida), "no debe crearse ninguna medición para un activo dado de baja"
    assert len(_lineas(env, ida, "BAJA_ACTIVO")) == n_lineas, "no debe emitirse otro BAJA_ACTIVO ni reabrirse el historial"
    obs(f"evento de crecimiento sobre el activo en BAJA: M02 respondió {r.status} ({r.err}).")


def test_TC_M06_064b_el_cierre_no_mide_el_activo_dado_de_baja(env):
    esc, ida, _ = _dar_de_baja(env, "perdida")
    env.presupuesto(45)
    env.precio(esc, "21000.00", desde=hoy())                       # un cambio de precio que sí mediría un activo vigente
    periodo = env.periodo(ida)
    if not periodo:
        no_verificable("no se pudo determinar el período contable del activo.")
    try:
        r = env.call("POST", f"/finanzas/periodos/{periodo}/cierre", "contador",
                     json={"autorizar_exclusiones": True, "incluir_activos_sin_precio": True})
    except requests.exceptions.RequestException as exc:
        no_concluyente(f"el cierre no respondió a tiempo dentro del sandbox: {exc}")
    if r.status not in (200, 201, 202):
        bloqueado(f"el cierre del período {periodo} no se pudo ejecutar dentro del run: {r}")
    assert not env.mediciones(ida), f"el activo dado de baja debe quedar excluido del cierre: {env.mediciones(ida)}"
    ids = {int(x["id_activo_biologico"]) for x in (r.data or {}).get("activos_excluidos", [])}
    obs(f"cierre completado; activo en baja medido: no; excluido por pendiente de precio: {ida in ids}")
