# | Fecha      | Nombre           | Que se hizo                                                                                        |
# |------------|------------------|----------------------------------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-84: script del grupo TC-M06-G20 (pytest + sandbox, rol Contador)                            |
# | 2026-11-08 | Daniela Castillo | G20 revisado contra ficha y RF/CU: 094 con motivo y sin sobrescritura registrada; 095 y 096 en casos |
# |            |                  | separados (sin referencia / log); 097 con el rechazo de PARAMETRIZADO probado de verdad            |
"""
TC-M06-G20 - Sobrescritura manual de costos: justificación, referencia documental y log de auditoría.   RF-84.   Casos: TC-M06-094 a TC-M06-097.

La sobrescritura se envía al confirmar el reconocimiento: POST /finanzas/reconocimientos/{id} con costos_manuales + justificacion (el DTO exige
justificación de al menos 20 caracteres cuando hay costos manuales). No existe campo de referencia documental ni campo metodo_costo_*: el DTO ignora
los campos desconocidos, no los rechaza (por eso 095 y 097c se prueban enviando lo que la ficha pide y mirando qué hace el backend).
- 094: sin justificación (vacía, espacios, ausente) se rechaza POR LA JUSTIFICACIÓN, no queda cálculo ni auditoría del ajuste y, al confirmar sin
  costos manuales, el cálculo conserva los valores de M09 (PARAMETRIZADO).
- 095a: justificación suficiente pero SIN referencia documental -> la ficha pide rechazo (RF-84 Restricción 4, CU03 FA-06).
  095b: justificación con una referencia -> se acepta.
- 096a: el cálculo usa 250.000 en comisiones (el resto sigue parametrizado) y guarda la justificación.
  096b: log de auditoría del ajuste con Contador, fecha-hora, ítem, valor original (200.000), valor manual (250.000) y justificación
  (RF-84 Salida 3, CA-3, RNF-84-03; CU03 FA-06). El tipo AJUSTE_MANUAL_COSTOS_VENTA figura en el catálogo de RF-94 pero el backend no lo emite.
- 097a/097b: «otros» sin justificación se rechaza (por la justificación) y con justificación se acepta como MANUAL.
  097c: «otros» marcado PARAMETRIZADO (metodo_costo_otros, ENUM solo MANUAL en el RF-84) debe rechazarse.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G20/TC-M06-G20.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G20/reporte-TC-M06-G20.html" --self-contained-html
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

PCT = ("0.015", "0.02", "0.005")          # transporte 150.000 + comisiones 200.000 (M09) + impuestos 50.000 sobre un bruto de 10.000.000
JUSTIF = "Ajuste manual QA TC-M06 con soporte documental: cotización No. 321 del transportador."
JUSTIF_SIN_SOPORTE = "Ajuste manual solicitado por el contador para esta venta."     # >= 20 caracteres y sin ninguna referencia a un documento


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


@pytest.fixture(scope="module")
def esc(env):
    env.nuevo_run()
    env.presupuesto(60)
    return env.escenario(categoria="POR_CABEZA", precio="10000000.00", costos=PCT)


def _nuevo(env, esc) -> int:
    return env.activo(esc, origen="nacimiento", costo=None, soporte=None)


def _rechazo_por(r, *palabras) -> bool:
    """El rechazo cuenta solo si es un 4xx y el mensaje habla del motivo que prueba el caso."""
    texto = (r.text or "").lower()
    return 400 <= r.status < 500 and any(p in texto for p in palabras)


def _eventos_ajuste(env, ida) -> list[dict]:
    """Eventos de auditoría del activo que corresponden al ajuste manual de costos de venta."""
    res = []
    for e in env.auditoria(ida):
        texto = json.dumps(e, default=str)
        if "AJUSTE" in str(e.get("tipo_evento")).upper() or (re.search(r"\b200000(\.0+)?\b", texto) and re.search(r"\b250000(\.0+)?\b", texto)):
            res.append(e)
    return res


@pytest.mark.parametrize("justificacion", ["", "     ", None], ids=["vacia", "espacios", "ausente"])
def test_TC_M06_094_sobrescritura_sin_justificacion_se_rechaza(env, esc, justificacion):
    env.presupuesto(25)
    ida = _nuevo(env, esc)
    cuerpo = {"costos_manuales": {"comisiones": "250000"}}
    if justificacion is not None:
        cuerpo["justificacion"] = justificacion
    r = env.confirmar(ida, cuerpo=cuerpo)
    if 400 <= r.status < 500 and not _rechazo_por(r, "justific"):
        no_concluyente(f"se rechazó, pero no por la justificación: {r}")
    assert _rechazo_por(r, "justific"), f"la sobrescritura sin justificación ({justificacion!r}) debía rechazarse por la justificación: {r}"
    assert env.calculo(ida) is None, "no debe registrarse el cálculo ni la sobrescritura"
    assert not _eventos_ajuste(env, ida), "no debe quedar registro de sobrescritura"
    ok = env.confirmar(ida)                                    # sin costos manuales: el cálculo conserva los valores de M09
    assert ok.status in (200, 201), ok
    c = env.calculo(ida)
    assert dec(c["costo_comisiones"]) == dec("200000") and c["metodo_costo"] == "PARAMETRIZADO", c
    assert (c.get("json_metodo_costo") or {}).get("comisiones") == "PARAMETRIZADO", c


def test_TC_M06_095a_sobrescritura_sin_referencia_documental_se_rechaza(env, esc):
    env.presupuesto(25)
    ida = _nuevo(env, esc)
    r = env.confirmar(ida, cuerpo={"costos_manuales": {"comisiones": "250000"}, "justificacion": JUSTIF_SIN_SOPORTE})
    assert 400 <= r.status < 500, (
        "la sobrescritura con justificación pero SIN referencia documental debía rechazarse (RF-84 Restricción 4, CU03 FA-06) y respondió "
        f"{r}. El backend no tiene dónde registrar una referencia: solo exige una justificación de al menos 20 caracteres.")


def test_TC_M06_095b_sobrescritura_con_una_referencia_se_acepta(env, esc):
    env.presupuesto(25)
    ida = _nuevo(env, esc)
    r = env.confirmar(ida, cuerpo={"costos_manuales": {"comisiones": "250000"}, "justificacion": JUSTIF})
    assert r.status in (200, 201), r
    c = env.calculo(ida)
    assert dec(c["costo_comisiones"]) == dec("250000") and c.get("justificacion") == JUSTIF, c
    obs("La referencia solo viaja dentro del texto de la justificación: no hay campo ni registro de referencia documental propio (H-17).")


@pytest.fixture(scope="module")
def ajuste(env, esc):
    """Una sobrescritura válida: comisiones de 200.000 (M09) a 250.000 con justificación y una referencia."""
    env.presupuesto(30)
    ida = _nuevo(env, esc)
    sim = env.simulacion(ida)
    original = (sim.get("calculo") or {}).get("costo_comisiones") if sim.status == 200 else None
    r = env.confirmar(ida, cuerpo={"costos_manuales": {"comisiones": "250000"}, "justificacion": JUSTIF})
    return {"ida": ida, "r": r, "original": original}


def test_TC_M06_096a_sobrescritura_valida_el_calculo_usa_el_valor_manual(env, ajuste):
    assert ajuste["r"].status in (200, 201), ajuste["r"]
    if ajuste["original"] is not None:
        assert dec(ajuste["original"]) == dec("200000"), f"valor original esperado de M09: 200.000 y es {ajuste['original']}"
    c = env.calculo(ajuste["ida"])
    assert dec(c["costo_comisiones"]) == dec("250000"), c
    assert dec(c["costo_transporte"]) == dec("150000") and dec(c["costo_impuestos_transaccion"]) == dec("50000"), c
    assert dec(c["valor_neto"]) == dec("9550000"), f"neto esperado 10.000.000 - (150.000 + 250.000 + 50.000) = 9.550.000 y es {c['valor_neto']}"
    assert c.get("justificacion") == JUSTIF, c
    metodos = c.get("json_metodo_costo") or {}
    assert metodos.get("comisiones") == "MANUAL" and metodos.get("transporte") == "PARAMETRIZADO" and metodos.get("impuestos") == "PARAMETRIZADO", c
    assert c["metodo_costo"] == "MIXTO", c
    assert c.get("id_usuario") is not None, f"el cálculo debe identificar al Contador (RNF-84-03): {c}"


def test_TC_M06_096b_sobrescritura_valida_deja_log_de_auditoria(env, ajuste):
    assert ajuste["r"].status in (200, 201), ajuste["r"]
    ida = ajuste["ida"]
    tipos = env.tipos_auditoria(ida)
    log = _eventos_ajuste(env, ida)
    assert log, ("no hay registro de auditoría de la sobrescritura (contador, fecha-hora, ítem=comisiones, valor_original=200.000, "
                 f"valor_manual=250.000 y justificación). Eventos del activo: {tipos}")
    texto = json.dumps(log[0], default=str)
    assert "comisiones" in texto.lower(), f"falta el ítem modificado: {texto}"
    assert re.search(r"\b200000(\.0+)?\b", texto) and re.search(r"\b250000(\.0+)?\b", texto), f"faltan valor original y valor manual: {texto}"
    assert "cotización No. 321" in texto or "cotizaci" in texto, f"falta la justificación: {texto}"
    assert log[0].get("id_usuario") is not None, f"falta el Contador: {texto}"
    assert any("fecha" in k for k in log[0]), f"falta la fecha-hora: {texto}"


def test_TC_M06_097a_otros_sin_justificacion_se_rechaza(env, esc):
    env.presupuesto(25)
    ida = _nuevo(env, esc)
    r = env.confirmar(ida, cuerpo={"costos_manuales": {"otros": "100000"}})
    if 400 <= r.status < 500 and not _rechazo_por(r, "justific"):
        no_concluyente(f"se rechazó, pero no por la justificación: {r}")
    assert _rechazo_por(r, "justific"), f"«otros» sin justificación debía rechazarse por la justificación: {r}"
    assert env.calculo(ida) is None, "no debe quedar cálculo"


def test_TC_M06_097b_otros_con_justificacion_se_acepta_como_manual(env, esc):
    env.presupuesto(25)
    ida = _nuevo(env, esc)
    r = env.confirmar(ida, cuerpo={"costos_manuales": {"otros": "100000"}, "justificacion": JUSTIF})
    assert r.status in (200, 201), r
    c = env.calculo(ida)
    assert dec(c["otros_costos_disposicion"]) == dec("100000"), c
    assert (c.get("json_metodo_costo") or {}).get("otros") == "MANUAL", c
    assert dec(c["valor_neto"]) == dec("9500000"), f"neto esperado 10.000.000 - (150.000 + 200.000 + 50.000 + 100.000) = 9.500.000 y es {c['valor_neto']}"


@pytest.mark.parametrize("forma", ["metodo_costo_otros", "costos_manuales.metodo_otros"], ids=["campo_del_RF", "dentro_de_costos_manuales"])
def test_TC_M06_097c_otros_marcado_parametrizado_se_rechaza(env, esc, forma):
    env.presupuesto(25)
    ida = _nuevo(env, esc)
    cuerpo = {"costos_manuales": {"otros": "100000"}, "justificacion": JUSTIF}
    if forma == "metodo_costo_otros":
        cuerpo["metodo_costo_otros"] = "PARAMETRIZADO"
    else:
        cuerpo["costos_manuales"]["metodo_otros"] = "PARAMETRIZADO"
    r = env.confirmar(ida, cuerpo=cuerpo)
    if 400 <= r.status < 500 and not _rechazo_por(r, "metodo", "método", "parametrizado"):
        no_concluyente(f"se rechazó, pero no por el método: {r}")
    assert _rechazo_por(r, "metodo", "método", "parametrizado"), (
        f"«otros» marcado como PARAMETRIZADO ({forma}) debía rechazarse (RF-84: metodo_costo_otros solo admite MANUAL) y respondió {r}. "
        "El backend ignora el campo sin validarlo.")
