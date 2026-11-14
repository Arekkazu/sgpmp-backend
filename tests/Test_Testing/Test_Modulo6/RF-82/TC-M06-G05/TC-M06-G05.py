# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-82: script del grupo TC-M06-G05 (pytest + sandbox, roles)         |
# | 2026-11-08 | Daniela Castillo | M06 RF-82: G05 alineado con la ficha (021 bloqueado si no hay operación de rechazo) |
# | 2026-11-11 | Daniela Castillo | M06 RF-82: 021 ajustado a FA-4: no existe «Rechazar propuesta»; no confirmar deja el activo en PENDIENTE_CONFIRMACION sin asiento |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G05-V2.0.html |
# | 2026-11-12 | Daniela Castillo | M06 RF-82: 021 solo observa si aparece PENDIENTE_CONFIRMACION (no es exigible: la propuesta no se guarda); sigue exigiendo que no haya reconocimiento ni asiento |
# | 2026-11-13 | Daniela Castillo | M06 RF-82: 022 con Administrador con todos los permisos (líder y Análisis, 13-nov) y rol Auditor nuevo: el Administrador consulta y confirma; se agrega el Auditor (no confirma; ve el reconocimiento confirmado)
# | 2026-11-13 | Daniela Castillo | M06 RF-82: 022 Auditor exige además consultar la propuesta de reconocimiento (200, solo lectura)
"""
TC-M06-G05 - Reconocimiento único, rechazo de la propuesta y autorización por rol (solo Contador).   RF-82 (CU01).
Casos: TC-M06-020, TC-M06-021 y TC-M06-022.

- 020: segunda confirmación del mismo activo -> rechazo (4xx) que indica que el activo ya fue reconocido; un solo reconocimiento y
  un solo asiento.
- 021 (ajustado, FA-4): no existe una acción «Rechazar propuesta». Si el Contador no confirma, el activo queda en PENDIENTE_CONFIRMACION, sin reconocimiento
  confirmado y sin asiento (esperado en FA-4). Se consulta la propuesta como Contador, no se confirma, y se verifica que nada se haya registrado; solo se OBSERVA
  (no se exige) si algún campo de estado dice PENDIENTE_CONFIRMACION, y se anota si TEST expone alguna ruta de rechazo (no es exigible).
- 022: matriz de roles (V2.0, 13-nov). Productor, Veterinario, Ingeniero de campo, sin token y token inválido: confirmar (POST) y consultar la
  propuesta (GET) se rechazan (403; 401 sin sesión). El Administrador tiene TODOS los permisos (decisión del líder y de Análisis): consulta (200) y
  confirma (201). Auditor (rol nuevo): según RF-82 Postcondiciones 6 b el reconocimiento confirmado es visible para el Auditor (200); no confirma
  (403); consulta también la propuesta de reconocimiento (200, solo lectura; decisión del 13-nov, el RF no lo define). Ingeniero de Campo se prueba cambiando temporalmente el rol de la
  cuenta 158 a 4 dentro del run.

Cómo correrlo (necesita QA_CONTRASENA_PRODUCTOR, QA_CONTRASENA_VETERINARIO y QA_CONTRASENA_AUDITOR además de admin e ingeniero):
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G05/TC-M06-G05.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G05/reporte-TC-M06-G05-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero", "productor", "veterinario", "auditor"))
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
    # Solo se observa: el estado PENDIENTE_CONFIRMACION no es un campo exigible (la propuesta se calcula al vuelo y no se guarda; decisión de Análisis/líder 12-nov).
    visible = any(v.strip().upper() == "PENDIENTE_CONFIRMACION" for _, v in todos)
    obs(f"PENDIENTE_CONFIRMACION {'aparece' if visible else 'no aparece'} en algún campo de estado (solo observación); campos de estado devueltos: {todos}")
    rutas = [(ruta, env.call("POST", ruta, "contador", json={}).status) for ruta in (
        f"/finanzas/reconocimientos/{ida}/rechazo", f"/finanzas/reconocimientos/{ida}/rechazar")]
    obs(f"rutas de rechazo probadas (no exigibles): {rutas}")


ROLES_NO_AUTORIZADOS = ["productor", "veterinario", "ingeniero_campo", "sin_token", "token_invalido"]    # el Administrador ya no está: tiene todos los permisos
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
    assert r_get.status in esperado, f"[{rol}] consultar la propuesta: esperado {esperado}, recibido {r_get}"
    # La propuesta no cambia y no se crea asiento.
    env.contador()
    h = env.historial(ida)
    assert not h.get("reconocimientos") and not lineas_de(h)
    obs("el intento rechazado queda registrado: se verifica en TC-M06-G08 (auditoría).")


def test_TC_M06_022_administrador_tiene_todos_los_permisos(env, esc):
    """V2.0 (13-nov): el líder y Análisis definieron que el Administrador tiene todos los permisos: consulta la propuesta y confirma el reconocimiento."""
    env.presupuesto(30)
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-022-admin-ok")
    r_get = env.call("GET", f"/finanzas/reconocimientos/propuestas/{ida}", "admin")
    assert r_get.status == 200, f"[admin] consultar la propuesta: esperado 200 (todos los permisos), recibido {r_get}"
    r_post = env.call("POST", f"/finanzas/reconocimientos/{ida}", "admin", json={})
    assert r_post.status == 201, f"[admin] confirmar: esperado 201 (todos los permisos), recibido {r_post}"
    assert env.contar("reconocimientos_iniciales", ida, "AND estado = 'CONFIRMADO'") == 1, "debe quedar un reconocimiento confirmado"


def test_TC_M06_022_auditor_consulta_y_no_confirma(env, esc):
    """Rol Auditor (13-nov). Esperado del RF-82: no confirma (RNF-82-05, CA-2) y el reconocimiento confirmado es visible para el Auditor (Postcondiciones 6 b)."""
    env.presupuesto(40)
    env.contador()
    ida = env.activo(esc, origen="compra", costo="2500000.0000", soporte="Factura QA-M06-022-auditor")
    r_post = env.call("POST", f"/finanzas/reconocimientos/{ida}", "auditor", json={})
    assert r_post.status == 403, f"[auditor] confirmar: esperado 403, recibido {r_post}"
    fallos = []
    r_prop = env.call("GET", f"/finanzas/reconocimientos/propuestas/{ida}", "auditor")
    if r_prop.status != 200:
        fallos.append(f"consultar la propuesta de reconocimiento: esperado 200 (el Auditor consulta el reconocimiento inicial, decisión 13-nov), recibido {r_prop}")
    assert env.contar("reconocimientos_iniciales", ida) == 0, "el intento del Auditor no debe crear el reconocimiento"
    env.prep(env.confirmar(ida), (201,), "confirmar como Contador")
    r_hist = env.call("GET", f"/finanzas/activos/{ida}", "auditor")
    if r_hist.status != 200:
        fallos.append(f"consultar el reconocimiento confirmado: esperado 200 (RF-82 Postcondiciones 6 b), recibido {r_hist}")
    elif not (r_hist.data or {}).get("reconocimientos"):
        fallos.append(f"la consulta del Auditor no trae el reconocimiento: {r_hist}")
    assert not fallos, "[auditor] " + " | ".join(fallos)
