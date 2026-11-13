# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-82: script del grupo TC-M06-G05 (pytest + sandbox, roles)         |
# | 2026-11-08 | Daniela Castillo | M06 RF-82: G05 alineado con la ficha (021 bloqueado si no hay operación de rechazo) |
# | 2026-11-11 | Daniela Castillo | M06 RF-82: 021 ajustado a FA-4: no existe «Rechazar propuesta»; no confirmar deja el activo en PENDIENTE_CONFIRMACION sin asiento |
"""
TC-M06-G05 - Reconocimiento único, rechazo de la propuesta y autorización por rol (solo Contador).   RF-82 (CU01).
Casos: TC-M06-020, TC-M06-021 y TC-M06-022.

- 020: segunda confirmación del mismo activo -> rechazo (4xx) que indica que el activo ya fue reconocido; un solo reconocimiento y
  un solo asiento.
- 021 (ajustado, FA-4): no existe una acción «Rechazar propuesta». Si el Contador no confirma, el activo queda en PENDIENTE_CONFIRMACION, sin reconocimiento
  confirmado y sin asiento (esperado en FA-4). Se consulta la propuesta como Contador, no se confirma, y se verifica que nada se haya registrado y que el
  estado siga pendiente de confirmación; se anota si TEST expone alguna ruta de rechazo (no es exigible).
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


def test_TC_M06_021_sin_confirmar_el_activo_queda_pendiente_de_confirmacion_sin_asiento(env, esc):
    env.presupuesto(40)
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-021")
    prop = env.propuesta(ida)
    assert prop.status == 200, f"el Contador debe poder consultar la propuesta: {prop}"
    # El Contador la revisa y no la confirma (no hay acción de rechazo): no debe quedar nada registrado.
    h = env.historial(ida)
    assert not h.get("reconocimientos") and not lineas_de(h), f"sin confirmar no debe existir reconocimiento ni asiento: {h.get('reconocimientos')} / {lineas_de(h)}"
    assert env.contar("reconocimientos_iniciales", ida, "AND estado = 'CONFIRMADO'") == 0, "no debe existir un reconocimiento confirmado"
    m02 = env.call("GET", f"/activos-biologicos/{ida}", "admin")
    obs(f"estado del activo en M02: {(m02.data or {}).get('nombre_estado') if isinstance(m02.data, dict) else m02.status}; propuesta: {prop.text[:200]}")

    def _estados(o, ruta=""):
        """Todos los campos cuyo nombre contiene «estado» y traen un texto (en la propuesta, en M02 y en el historial)."""
        if isinstance(o, dict):
            for k, v in o.items():
                if "estado" in str(k).lower() and isinstance(v, str):
                    yield f"{ruta}{k}", v
                yield from _estados(v, f"{ruta}{k}.")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from _estados(v, f"{ruta}{i}.")
    campos = {"propuesta": list(_estados(prop.data, "propuesta.")), "m02": list(_estados(m02.data, "m02.")), "historial": list(_estados(h, "historial."))}
    todos = [c for lista in campos.values() for c in lista]
    assert any(v.strip().upper() == "PENDIENTE_CONFIRMACION" for _, v in todos), (
        "FA-4: el activo debe quedar en estado PENDIENTE_CONFIRMACION (campo de estado con ese valor exacto) mientras el Contador no confirma; "
        f"campos de estado devueltos: {todos}")
    rutas = [(ruta, env.call("POST", ruta, "contador", json={}).status) for ruta in (
        f"/finanzas/reconocimientos/{ida}/rechazo", f"/finanzas/reconocimientos/{ida}/rechazar")]
    obs(f"rutas de rechazo probadas (no exigibles): {rutas}")


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
