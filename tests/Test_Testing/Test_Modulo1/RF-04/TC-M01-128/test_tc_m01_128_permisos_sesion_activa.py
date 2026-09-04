"""
TC-M01-128 - Verificar la aplicacion de un cambio de permisos en una sesion
activa.

RF relacionado: RF-04
Categoria: Integracion / Seguridad

Criterio de aceptacion (RF-04, Restricciones):
    "Los cambios realizados en permisos deben reflejarse inmediatamente en
    las sesiones activas del sistema, aplicandose en la siguiente
    solicitud realizada por el usuario" -- sin requerir cierre de sesion.

IMPORTANTE - sustitucion de la cuenta de prueba:
La ficha original usa a "Diana Paola Rincon" (diana.rincon.qa3@sgpmp-test.com).
Se confirmo via API (busqueda por nombre/correo, sin resultados bajo qa3 ni
qa4) que esa cuenta YA NO EXISTE: fue eliminada legitimamente por
TC-M01-139 ("Eliminar una cuenta y verificar su caracter irreversible"),
ya Aprobado -- es el resultado correcto y esperado de esa prueba, no un
error. Como una cuenta ELIMINADA es terminal por diseno (RF-06), no se
puede reutilizar.

Tampoco se pudo usar ingeniero@pecuaria.co (otra cuenta ya validada en
esta sesion): su contrasena compartida ya habia cambiado por otras
pruebas del equipo corriendo en paralelo ("Intento 2 de 5" al iniciar
sesion) -- reintentar mas contrasenas hubiera arriesgado bloquear esa
cuenta compartida.

Se intento tambien REGISTRAR y ACTIVAR una cuenta desechable nueva via
API (POST /usuarios/ + POST /usuarios/{id}/gestionar {"accion_cuenta":
"activar"}, el mismo mecanismo administrativo que ya valido TC-M01-135).
Esa ruta quedo bloqueada: el registro ahora responde 400 CAPTCHA_INVALIDO
con cualquier valor de captcha_token que no sea una respuesta real de
Google (se confirmo en google_recaptcha_adapter.py que llama de verdad a
https://www.google.com/recaptcha/api/siteverify) -- una mejora real
frente al hallazgo previo de INC-M01-10-11 (que en su momento encontro
que se aceptaba cualquier token), pero que impide generar cuentas nuevas
por este camino sin resolver un captcha real.

Este script en su lugar usa una cuenta de prueba EXISTENTE y dedicada,
provista directamente por el equipo el 2026-09-03 (gestor.granja.test@
pecuaria.co, rol no administrador, contrasena vigente confirmada) --
sin registrar ni activar nada nuevo.

Por que 100% via API (sin conexion directa a BD): el puerto de PostgreSQL
(5448) no respondia al momento de escribir este script (timeout de red).
El mecanismo se puede demostrar igual de bien por API:
GET /sesiones/me/permisos no requiere ningun permiso RBAC especifico
(solo requiere estar autenticado), asi que refleja en vivo los permisos
efectivos del usuario en cada llamada -- perfecto para capturar el
"antes" y el "despues" sin volver a iniciar sesion.

Este test:
1. Inicia sesion como Administrador.
2. Inicia sesion con la cuenta de prueba existente (gestor.granja.test@
   pecuaria.co) -- UNA sola vez; el token se reutiliza sin renovarlo en
   todo el resto del test.
3. Como Administrador, elige un permiso cualquiera que el rol de esa
   cuenta tenga activo ahora mismo (no depende de un recurso fijo como
   "activos", que ademas no existe en el catalogo de este modulo).
4. Con el token ORIGINAL del usuario de prueba, confirma que ese permiso
   aparece en GET /sesiones/me/permisos ("antes").
5. Como Administrador, retira ese permiso del rol.
6. Con el MISMO token original (sin volver a iniciar sesion), confirma
   que el permiso ya NO aparece en GET /sesiones/me/permisos ("despues")
   -- evidencia de que el cambio se aplico a la sesion activa.
7. Restaura el permiso al final (finally), para no dejar el rol
   Productor permanentemente incompleto (afecta a todos los usuarios de
   ese rol, no solo al de esta prueba).

Requisitos:
    pip install pytest pytest-html requests

Como correrlo:
    pytest test_tc_m01_128_permisos_sesion_activa.py -v \
        --html=reporte-TC-M01-128.html --self-contained-html
"""
import os

import pytest
import requests

BASE_URL = os.getenv(
    "BASE_URL",
    "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test",
)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@pecuaria.co")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Test1234!")

# Cuenta de prueba existente y dedicada (no administradora), provista por
# el equipo el 2026-09-03. No es descartable ni se registra/activa nada:
# ya existe y su contrasena esta vigente.
USUARIO_PRUEBA_EMAIL = os.getenv("USUARIO_PRUEBA_EMAIL", "gestor.granja.test@pecuaria.co")
USUARIO_PRUEBA_PASSWORD = os.getenv("USUARIO_PRUEBA_PASSWORD", "Test1234!")


def _login(correo: str, contrasena: str) -> dict:
    resp = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": correo, "contrasena": contrasena},
        timeout=15,
    )
    assert resp.status_code == 200, (
        f"No se pudo iniciar sesion como {correo}: {resp.status_code} {resp.text}"
    )
    return resp.json()


def _permisos_efectivos(token: str) -> list[dict]:
    """Consulta los permisos EFECTIVOS del usuario autenticado por este
    token, en vivo -- no requiere ningun permiso RBAC particular, solo
    estar autenticado."""
    resp = requests.get(
        f"{BASE_URL}/sesiones/me/permisos",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert resp.status_code == 200, (
        f"No se pudo consultar los permisos efectivos: {resp.status_code} {resp.text}"
    )
    return resp.json()["permisos"]


@pytest.fixture(scope="module")
def admin_token() -> str:
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)["token"]


@pytest.fixture(scope="module")
def usuario_prueba(admin_token) -> dict:
    """Inicia sesion con la cuenta de prueba EXISTENTE (no registra ni
    activa nada nuevo). Devuelve su token (obtenido UNA sola vez, sin
    renovarlo en el resto del test) + su id_rol."""
    login_resp = _login(USUARIO_PRUEBA_EMAIL, USUARIO_PRUEBA_PASSWORD)
    token = login_resp["token"]

    resp = requests.get(
        f"{BASE_URL}/usuarios/admin",
        params={"correo": USUARIO_PRUEBA_EMAIL},
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert resp.status_code == 200 and resp.json()["total"] >= 1, (
        f"No se encontro la cuenta de prueba {USUARIO_PRUEBA_EMAIL}: "
        f"{resp.status_code} {resp.text}"
    )
    nombre_rol = resp.json()["items"][0]["nombre_rol"]

    roles_resp = requests.get(
        f"{BASE_URL}/roles/",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert roles_resp.status_code == 200, (
        f"No se pudo listar roles: {roles_resp.status_code} {roles_resp.text}"
    )
    rol = next(
        (r for r in roles_resp.json() if r["nombre_rol"] == nombre_rol), None
    )
    assert rol is not None, f"No se encontro el rol '{nombre_rol}' en GET /roles/"

    return {
        "token": token,
        "id_rol": rol["id_rol"],
        "nombre_rol": nombre_rol,
        "correo": USUARIO_PRUEBA_EMAIL,
    }


@pytest.fixture(scope="module")
def permiso_objetivo(admin_token, usuario_prueba) -> dict:
    """Cualquier permiso activo del rol del usuario de prueba: no
    necesitamos que sea 'activos:eliminar' en particular (ese recurso no
    existe en el catalogo de este modulo) -- el mecanismo a probar es el
    mismo sin importar cual permiso se retire."""
    resp = requests.get(
        f"{BASE_URL}/roles/{usuario_prueba['id_rol']}/permisos",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert resp.status_code == 200, (
        f"No se pudieron listar los permisos del rol: {resp.status_code} {resp.text}"
    )
    activos = [p for p in resp.json() if p["es_activo"]]
    assert len(activos) >= 2, (
        f"El rol '{usuario_prueba['nombre_rol']}' tiene {len(activos)} permisos "
        f"activos; se necesitan al menos 2 para poder retirar uno sin dejar el "
        f"rol sin permisos (RF-03 exige minimo 1)."
    )
    return activos[0]


class TestTCM01128PermisosSesionActiva:
    """Suite de pruebas para TC-M01-128."""

    def test_el_permiso_desaparece_de_la_sesion_activa_sin_relogin(
        self, admin_token, usuario_prueba, permiso_objetivo
    ):
        token_usuario = usuario_prueba["token"]  # el MISMO token en todo el test
        clave_objetivo = (permiso_objetivo["id_recurso"], permiso_objetivo["id_accion"])

        # --- ANTES: el permiso aparece en la sesion activa ---
        permisos_antes = _permisos_efectivos(token_usuario)
        claves_antes = {(p["id_recurso"], p["id_accion"]) for p in permisos_antes}
        assert clave_objetivo in claves_antes, (
            f"Precondicion fallida: el permiso {clave_objetivo} no aparece "
            f"todavia en la sesion activa antes de retirarlo."
        )

        excepcion_durante_retiro = None
        try:
            # --- Administrador retira el permiso ---
            retiro = requests.delete(
                f"{BASE_URL}/roles/{usuario_prueba['id_rol']}/permisos/"
                f"{permiso_objetivo['id_permiso']}",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=15,
            )
            assert retiro.status_code == 200, (
                f"No se pudo retirar el permiso: {retiro.status_code} {retiro.text}"
            )

            # --- DESPUES: MISMO token, sin volver a iniciar sesion ---
            permisos_despues = _permisos_efectivos(token_usuario)
            claves_despues = {
                (p["id_recurso"], p["id_accion"]) for p in permisos_despues
            }

            assert clave_objetivo not in claves_despues, (
                f"RF-04 exige que un cambio de permisos se aplique de inmediato "
                f"a las sesiones activas, sin requerir cierre de sesion. El "
                f"permiso {clave_objetivo} SIGUE apareciendo en la sesion activa "
                f"del usuario tras retirarlo -- el cambio no se propago."
            )
        except Exception as exc:
            excepcion_durante_retiro = exc
        finally:
            # --- Restaurar el permiso, pase lo que pase ---
            restaurar = requests.post(
                f"{BASE_URL}/roles/{usuario_prueba['id_rol']}/permisos",
                json={
                    "id_recurso": permiso_objetivo["id_recurso"],
                    "id_accion": permiso_objetivo["id_accion"],
                },
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=15,
            )
            assert restaurar.status_code in (200, 201, 409), (
                f"CRITICO: no se pudo restaurar el permiso {clave_objetivo} en "
                f"el rol '{usuario_prueba['nombre_rol']}': {restaurar.status_code} "
                f"{restaurar.text}"
            )

        if excepcion_durante_retiro is not None:
            raise excepcion_durante_retiro
