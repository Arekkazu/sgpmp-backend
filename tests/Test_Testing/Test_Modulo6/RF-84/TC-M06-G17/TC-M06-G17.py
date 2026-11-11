# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-84: script del grupo TC-M06-G17 (pytest + sandbox, rol Contador) |
"""
TC-M06-G17 - Valor neto en el límite (0,0001; 0; negativo) y REVISION_REQUERIDA.   RF-84 (CU03 FA-02/FA-03).   Casos: TC-M06-082 a TC-M06-086 (con subcasos b y c).

Bruto = 1.000,0000 (1 cabeza a 1.000,00). Los costos se ingresan como costos manuales en la confirmación del reconocimiento (única entrada
manual de RF-84) con la especie sin parámetros de M09.
Comportamiento del backend: un neto <= 0 NO se persiste: la confirmación responde VALOR_NETO_NO_POSITIVO (4xx) y GET /simulacion devuelve el
cálculo con estado REVISION_REQUERIDA (sin guardarlo). La ficha y RF-84 (paso 6, FA-2, CA-5) piden que el cálculo QUEDE en REVISION_REQUERIDA,
que se emita la alerta y que el Contador pueda validarlo con justificación: cada exigencia va en un caso aparte (083/083b/083c, 084/084b/084c,
085 y 086). La notificación al Contador en pantalla se prueba en Cypress (G31); aquí se verifica el registro de la alerta en la auditoría RF-94.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G17/TC-M06-G17.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G17/reporte-TC-M06-G17.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

JUSTIF = "Costos de disposición QA TC-M06 con soporte documental: cotización No. 456 del comprador."
SEV_ALERTA = ("WARNING", "ADVERTENCIA", "ALERTA", "CRITICA", "CRITICO", "CRITICAL", "ERROR")
SEV_CRITICA = ("CRITICA", "CRITICO", "CRITICAL", "ERROR", "ALTA")


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


@pytest.fixture(scope="module")
def esc(env):
    return env.escenario(categoria="POR_CABEZA", precio="1000.00", costos=None)


def _alertas(env, ida, severidades):
    """Eventos de auditoría RF-94 del activo con severidad de alerta (o de tipo ALERTA/NETO)."""
    out = []
    for e in env.auditoria(ida):
        sev = str(e.get("severidad") or e.get("severidad_evento") or "").upper()
        tipo = str(e.get("tipo_evento") or "").upper()
        if sev in severidades or "ALERTA" in tipo or "NETO" in tipo:
            out.append((tipo, sev))
    return out


@pytest.fixture(scope="module")
def cero(env):
    """Activo con costos de M09 = 100 % del bruto (neto 0): simulación y confirmación bloqueada, una sola vez."""
    env.presupuesto(30)
    e = env.escenario(categoria="POR_CABEZA", precio="1000.00", costos=("0.5", "0.4", "0.1"))
    ida = env.activo(e, origen="nacimiento", costo=None, soporte=None)
    sim = env.simulacion(ida)
    conf = env.confirmar(ida)
    return ida, sim, conf


@pytest.fixture(scope="module")
def negativo(env, esc):
    """Activo con transporte manual 1000,0001 sobre bruto 1000,0000 (neto -0,0001): confirmación bloqueada, una sola vez."""
    env.presupuesto(25)
    ida, r = env.confirmar_manual(esc, {"transporte": "1000.0001"}, JUSTIF)
    return ida, r


def test_TC_M06_082_neto_positivo_minimo_se_acepta(env, esc):
    env.presupuesto(25)
    ida, r = env.confirmar_manual(esc, {"transporte": "999.9999"}, JUSTIF)
    assert r.status in (200, 201), r
    c = env.calculo(ida)
    assert dec(c["valor_neto"]) == dec("0.0001") and c["estado"] == "CALCULADO", c
    assert not _alertas(env, ida, SEV_ALERTA), f"con neto positivo no debe haber alerta: {_alertas(env, ida, SEV_ALERTA)}"


def test_TC_M06_083_neto_cero_se_bloquea_y_se_simula_en_revision(env, cero):
    ida, s, c = cero
    assert s.status == 200 and s.get("es_valido") is True, s
    assert dec(s.get("calculo")["valor_neto"]) == 0 and s.get("calculo")["estado"] == "REVISION_REQUERIDA", s
    assert 400 <= c.status < 500 and "VALOR_NETO_NO_POSITIVO" in c.text, \
        f"la confirmación con neto 0 debe quedar bloqueada con VALOR_NETO_NO_POSITIVO: {c}"
    obs("Neto 0: el RF lo trata como alerta crítica (no preventiva): bloqueo VALOR_NETO_NO_POSITIVO; el cálculo REVISION_REQUERIDA solo existe en la simulación.")


def test_TC_M06_083b_neto_cero_genera_alerta(env, cero):
    ida, _, _ = cero
    al = _alertas(env, ida, SEV_ALERTA)
    assert al, f"con neto 0 debe quedar una alerta (preventiva o crítica) registrada para el Contador; eventos de auditoría: {env.tipos_auditoria(ida)}"


def test_TC_M06_083c_neto_cero_queda_registrado_en_revision_requerida(env, cero):
    ida, _, _ = cero
    c = env.calculo(ida)
    assert c is not None and c["estado"] == "REVISION_REQUERIDA", \
        f"el cálculo con neto 0 debe quedar registrado en REVISION_REQUERIDA hasta la validación del Contador: {c}"


def test_TC_M06_084_neto_negativo_bloquea_y_no_se_usa(env, negativo):
    ida, r = negativo
    assert 400 <= r.status < 500 and "VALOR_NETO_NO_POSITIVO" in r.text, f"se esperaba el bloqueo por neto no positivo: {r}"
    assert not lineas_de(env.historial(ida)), "el valor con neto negativo no debe usarse en el reconocimiento (sin asientos)"


def test_TC_M06_084b_neto_negativo_genera_alerta_critica(env, negativo):
    ida, _ = negativo
    al = _alertas(env, ida, SEV_CRITICA)
    assert al, f"con neto negativo debe quedar una alerta CRÍTICA registrada; eventos de auditoría: {env.tipos_auditoria(ida)}"


def test_TC_M06_084c_neto_negativo_queda_registrado_en_revision_requerida(env, negativo):
    ida, _ = negativo
    c = env.calculo(ida)
    assert c is not None and c["estado"] == "REVISION_REQUERIDA", \
        f"el cálculo con neto negativo debe quedar registrado en REVISION_REQUERIDA: {c}"


def test_TC_M06_085_validacion_explicita_de_neto_no_positivo():
    bloqueado("funcionalidad no implementada: no existe operación de RF-84 para que el Contador valide con justificación un neto <= 0 "
              "(CU03 FA-02/FA-03; RF-84 paso 6, CA-5); la API solo lo bloquea o lo simula.")


def test_TC_M06_086_validacion_sin_justificacion_de_neto_no_positivo():
    bloqueado("funcionalidad no implementada: no existe la operación de validación de un neto <= 0 (ver TC-M06-085), "
              "por lo tanto no hay rechazo de la validación sin justificación.")
