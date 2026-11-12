# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-82: script del grupo TC-M06-G05 (pytest + sandbox, roles)         |
# | 2026-11-08 | Daniela Castillo | M06 RF-82: G05 alineado con la ficha (021 bloqueado si no hay operación de rechazo) |
"""
TC-M06-G05 - Reconocimiento único, rechazo de la propuesta y autorización por rol (solo Contador).   RF-82 (CU01).
Casos: TC-M06-020, TC-M06-021 y TC-M06-022.

- 020: segunda confirmación del mismo activo -> rechazo (4xx) que indica que el activo ya fue reconocido; un solo reconocimiento y
  un solo asiento.
- 021: la ficha exige una operación «rechazar propuesta» (con y sin motivo). El backend no la expone (solo propuestas, confirmar y
  reversión): el script la busca en TEST y, si no existe, el caso sale BLOQUEADO «no implementado» (lo dice la ficha: no se reporta
  como defecto). No se sustituye por otra comprobación.
- 022: matriz de roles. Confirmar (POST) exige reconocimiento_inicial·Crear: solo Contador. Consultar la propuesta (GET) exige
  ·Leer, que la migración también concede a Administrador y Revisor Fiscal: el caso espera 403 para el Administrador
  (Restricción 1 / RNF-82-05 del RF); si el backend lo deja leer, esa aserción falla y es un hallazgo a documentar.
  Ingeniero de Campo se prueba cambiando temporalmente el rol de la cuenta 158 a 4 dentro del run.

Cómo correrlo (necesita QA_CONTRASENA_PRODUCTOR y QA_CONTRASENA_VETERINARIO además de admin e ingeniero):
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G05/TC-M06-G05.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G05/reporte-TC-M06-G05.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero", "productor", "veterinario"))
    yield e
    e.cerrar()


@pytest.fixture(scope="module")
def esc(env):
    return env.escenario(categoria="POR_CABEZA", precio="8000000.00")


def test_TC_M06_020_activo_ya_reconocido_rechaza_segundo_reconocimiento(env, esc):
    env.presupuesto()
    ida, r1 = env.reconocer(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-020")
    n_lineas = len(lineas_de(env.historial(ida)))
    r2 = env.confirmar(ida)
    assert 400 <= r2.status < 500, f"el segundo reconocimiento debía rechazarse y respondió {r2}"
    assert "reconocid" in (r2.text or "").lower(), f"el rechazo no indica que el activo ya fue reconocido: {r2}"
    obs(f"segundo reconocimiento: HTTP {r2.status} error_code={r2.err}")
    assert env.contar("reconocimientos_iniciales", ida, "AND estado = 'CONFIRMADO'") == 1
    assert len(lineas_de(env.historial(ida))) == n_lineas, "no debe crearse un segundo asiento"


@pytest.mark.parametrize("motivo", ["con_motivo", "sin_motivo"])
def test_TC_M06_021_contador_rechaza_la_propuesta(env, esc, motivo):
    env.presupuesto(30)
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte=f"Factura QA-M06-021-{motivo}")
    cuerpo = {"motivo_rechazo": "Rechazo por prueba QA TC-M06-021"} if motivo == "con_motivo" else {}
    encontradas = []
    for ruta in (f"/finanzas/reconocimientos/{ida}/rechazo", f"/finanzas/reconocimientos/{ida}/rechazar",
                 f"/finanzas/reconocimientos/propuestas/{ida}/rechazo", f"/finanzas/reconocimientos/propuestas/{ida}/rechazar"):
        r = env.call("POST", ruta, "contador", json=cuerpo)
        if r.status not in (404, 405):
            encontradas.append((ruta, r.status))
    if not encontradas:
        bloqueado("no implementado: TEST no expone una operación para que el Contador rechace la propuesta de reconocimiento "
                  "(solo propuesta, confirmar y reversión). Registrar 'Bloqueado - no implementado' (no se reporta como defecto).")
    no_concluyente(f"existe una ruta de rechazo en TEST {encontradas}: completar el script con su contrato.")


ROLES_NO_AUTORIZADOS = ["admin", "productor", "veterinario", "ingeniero_campo", "sin_token", "token_invalido"]
# «token_invalido» hace de «token vencido»: un token realmente vencido exige esperar su vigencia (no verificable en un run de 180 s);
# ambos deben responder 401.


def _como(env, rol, metodo, ruta, cuerpo=None):
    if rol == "ingeniero_campo":
        env.set_rol(ROL_INGENIERO)
        try:
            return env.call(metodo, ruta, "ingeniero", json=cuerpo)
        finally:
            env.set_rol(ROL_CONTADOR)
    if rol == "sin_token":
        return env.call(metodo, ruta, None, json=cuerpo)
    if rol == "token_invalido":
        return env.call(metodo, ruta, None, json=cuerpo, token=TOKEN_INVALIDO)
    return env.call(metodo, ruta, rol, json=cuerpo)


@pytest.mark.parametrize("rol", ROLES_NO_AUTORIZADOS)
def test_TC_M06_022_confirmar_y_consultar_solo_contador(env, esc, rol):
    env.presupuesto(30)
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte=f"Factura QA-M06-022-{rol}")
    esperado = (401,) if rol in ("sin_token", "token_invalido") else (403,)
    r_post = _como(env, rol, "POST", f"/finanzas/reconocimientos/{ida}", {})
    assert r_post.status in esperado, f"[{rol}] confirmar: esperado {esperado}, recibido {r_post}"
    r_get = _como(env, rol, "GET", f"/finanzas/reconocimientos/propuestas/{ida}")
    assert r_get.status in esperado, (f"[{rol}] consultar la propuesta: esperado {esperado}, recibido {r_get}. "
                                      "Si es el Administrador: el RBAC de M06 le concede reconocimiento_inicial·Leer (RF-82 dice solo Contador).")
    # La propuesta no cambia y no se crea asiento.
    env.contador()
    h = env.historial(ida)
    assert not h.get("reconocimientos") and not lineas_de(h)
    obs("el intento rechazado queda registrado: se verifica en TC-M06-G08 (auditoría).")
