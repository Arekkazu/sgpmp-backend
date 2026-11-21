# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-82: script del grupo TC-M06-G02 (pytest + sandbox, rol Contador) |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G02-V2.0.html |
# | 2026-11-12 | Daniela Castillo | M06 INC-302: 007 verifica además el hecho propio RECONOCIMIENTO_DONACION y las cuentas del par de donación de la matriz |
"""
TC-M06-G02 - Reconocimiento inicial SIN precio de mercado: valoración por costo (RF-88) o bloqueo del reconocimiento.
RF-82 (CU01).   Casos: TC-M06-006 a TC-M06-009.

Qué hace el backend (ProponedorReconocimiento): sin precio RF-89 y con costo documentado aplica el modelo de costo (NIC 41 ¶30)
con indicador VALORACION_POR_COSTO y advertencia; sin precio ni costo bloquea con RECONOCIMIENTO_BLOQUEADO_SIN_VALOR y, al
intentar confirmar, deja el evento RECONOCIMIENTO_BLOQUEADO_SIN_VALOR (WARNING) en RF-94. El modelo de costo exige la vida útil
de la especie (se carga con la configuración de M09 del escenario).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G02/TC-M06-G02.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G02/reporte-TC-M06-G02-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


@pytest.fixture(scope="module")
def esc(env):
    # Especie SIN precio RF-89, con clasificación, vida útil y costos de venta cargados.
    return env.escenario(categoria="POR_CABEZA", precio=None, vida_util=60)


def _por_costo(env, ida, valor, hecho=None, sentido=None):
    p = env.propuesta(ida)
    assert p.status == 200, p
    assert p.get("es_confirmable") is True, f"no debía bloquearse: {p.get('bloqueos')}"
    assert p.get("indicador_valoracion") == "VALORACION_POR_COSTO", p
    assert dec(p.get("valor_inicial")) == dec(valor), f"valor por costo esperado {valor}, recibido {p.get('valor_inicial')}"
    assert p.get("advertencias"), "falta la alerta de nivel ADVERTENCIA por valoración por costo"
    if hecho:
        assert hechos(p) == [(hecho, sentido, dec(valor))], hechos(p)
    return p


def test_TC_M06_006_compra_sin_precio_valoracion_por_costo(env, esc):
    env.presupuesto()
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-006")
    _por_costo(env, ida, "2500000.0000")
    r = env.confirmar(ida)
    assert r.status == 201, r
    assert r.get("indicador_valoracion") == "VALORACION_POR_COSTO", r
    ev = [e for e in env.auditoria(ida, "RECONOCIMIENTO_INICIAL")]
    assert ev and ev[0].get("severidad") == "WARNING", f"la valoración por costo debe auditarse con severidad WARNING: {ev}"


def test_TC_M06_007_donacion_sin_precio_valoracion_por_costo(env, esc):
    env.presupuesto()
    ida = env.activo(esc, origen="donacion", costo="1200000.0000", soporte="Acta de donación QA-M06-007")
    _por_costo(env, ida, "1200000.0000")
    r = env.confirmar(ida)
    assert r.status == 201, r
    lineas = r.get("lineas") or []
    assert len(lineas) == 1, f"se esperaba 1 línea de asiento y hay {len(lineas)}: {lineas}"
    ln = lineas[0]
    nac = CUENTAS_MATRIZ[("RECONOCIMIENTO_NACIMIENTO", "UNICO")]
    assert ln["cuenta_debito"] == nac[0], f"el débito debe ser Activo Biológico: {ln}"
    assert ln["cuenta_credito"] != nac[1], (
        "DONACION: el crédito del asiento debe ser «Ingreso por donación», distinto del «Ingreso por transformación biológica» de NACIMIENTO. "
        f"El backend usó el hecho {ln['tipo_hecho']}/{ln['sentido']} y acreditó la misma cuenta que NACIMIENTO ({ln['cuenta_credito']}).")
    assert (ln["tipo_hecho"], ln["sentido"]) == ("RECONOCIMIENTO_DONACION", "UNICO"), f"la donación debe usar su propio hecho: {ln}"
    assert (ln["cuenta_debito"], ln["cuenta_credito"]) == CUENTAS_MATRIZ[("RECONOCIMIENTO_DONACION", "UNICO")], (
        f"las cuentas debían ser las del par de donación de la matriz (estado {ln.get('estado')}): {ln}")


@pytest.mark.parametrize("origen,costo,soporte", [
    ("nacimiento", None, None),
    ("transferencia_interna", None, None),
], ids=["008_nacimiento", "009_transferencia_sin_costo"])
def test_TC_M06_008_009_sin_valor_se_bloquea(env, esc, origen, costo, soporte):
    env.presupuesto()
    ida = env.activo(esc, origen=origen, costo=costo, soporte=soporte)
    p = env.propuesta(ida)
    assert p.status == 200, p
    assert p.get("es_confirmable") is False, "sin precio ni costo no debe poder confirmarse"
    assert "RECONOCIMIENTO_BLOQUEADO_SIN_VALOR" in codigos(p), f"bloqueos: {p.get('bloqueos')}"
    # Al intentar confirmar: rechazo, sin reconocimiento ni asiento, el activo sigue pendiente.
    r = env.confirmar(ida)
    assert 400 <= r.status < 500, f"la confirmación debía rechazarse: {r}"
    assert r.err == "RECONOCIMIENTO_BLOQUEADO_SIN_VALOR", r
    h = env.historial(ida)
    assert not h.get("reconocimientos") and not lineas_de(h), "no debe existir reconocimiento ni asiento"
    assert env.propuesta(ida).get("es_confirmable") is False
    bandeja = env.call("GET", "/finanzas/reconocimientos/propuestas", "contador")
    assert bandeja.status == 200, bandeja
    assert ida in {x.get("id_activo_biologico") for x in lista_de(bandeja.data, "propuestas")}, \
        "el activo debe seguir PENDIENTE_RECONOCIMIENTO (en la bandeja de propuestas) tras el bloqueo"
    # RF-94 registra el bloqueo (WARNING) aunque la operación no prospere.
    ev = env.auditoria(ida, "RECONOCIMIENTO_BLOQUEADO_SIN_VALOR")
    assert ev, "RF-94 no registró RECONOCIMIENTO_BLOQUEADO_SIN_VALOR"
    assert ev[0].get("severidad") == "WARNING", ev[0]
