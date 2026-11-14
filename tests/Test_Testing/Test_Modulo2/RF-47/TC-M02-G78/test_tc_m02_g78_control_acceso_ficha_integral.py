"""TC-M02-G78 — RF-47: control de acceso a la ficha integral y visibilidad de
accesos directos segun rol (OWASP API5:2023 Broken Function Level Authorization).

TC-M02-131: un usuario sin permiso de lectura sobre activos_biologicos (rol
Contador) debe recibir 403 al consultar la ficha integral, sin que se exponga
ningun dato del activo.

TC-M02-132: un usuario con permisos limitados (Veterinario, solo lectura)
deberia ver la Seccion 8 (accesos directos) filtrada segun sus permisos --
pero esa seccion no existe en absoluto en la respuesta actual (ver
TC-M02-G77), asi que este sub-caso queda documentado como bloqueado por el
mismo gap, no como un fallo independiente de control de acceso.

Cuentas usadas (reactivadas de sesiones QA anteriores de RF-01, contraseña ya
documentada en tests/Test_Testing/Test_Modulo1/RF-01/):
- tc016.f87178ba.qa@sgpmp-test.com, re-rolada a Contador (id_rol=5) para esta prueba.
- tc020.qa@sgpmp-test.com, re-rolada a Veterinario (id_rol=3) desde TC-M02-G23,
  reutilizada aqui.

Ejecutar:
    pytest tests/Test_Testing/Test_Modulo2/RF-47/TC-M02-G78/test_tc_m02_g78_control_acceso_ficha_integral.py -v
"""
from __future__ import annotations

import requests

BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"

CORREO_CONTADOR = "tc016.f87178ba.qa@sgpmp-test.com"
CORREO_VETERINARIO = "tc020.qa@sgpmp-test.com"
CONTRASENA_QA_COMPARTIDA = "Abcd12#3"

# Activo accesible por cualquier rol con permiso (usado para TC-M02-131: si el
# 403 es real, ni siquiera importa si el activo existe o es accesible).
ID_ACTIVO_CUALQUIERA = 5

# Activo propio del Veterinario (Finca 40, creada para esta prueba) -- para
# TC-M02-132, donde SI se espera una lectura exitosa.
ID_ACTIVO_VETERINARIO = 222


def _login(correo: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": correo, "contrasena": CONTRASENA_QA_COMPARTIDA},
        timeout=20,
    )
    assert resp.status_code == 200, f"Login fallido para {correo}: {resp.status_code} {resp.text}"
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestTCM02131SinPermisos:
    """OWASP API5 — funcion restringida por rol: Contador no tiene ningun
    permiso sobre el recurso activos_biologicos."""

    @classmethod
    def setup_class(cls):
        cls.token_contador = _login(CORREO_CONTADOR)

    def test_ficha_integral_rechazada_con_403(self):
        resp = requests.get(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_CUALQUIERA}/ficha-integral",
            headers=_headers(self.token_contador),
            timeout=20,
        )
        assert resp.status_code == 403, (
            f"Un rol sin permiso de lectura (Contador) debe recibir 403, "
            f"se obtuvo {resp.status_code}. Body: {resp.text}"
        )

    def test_ningun_dato_del_activo_se_expone(self):
        resp = requests.get(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_CUALQUIERA}/ficha-integral",
            headers=_headers(self.token_contador),
            timeout=20,
        )
        body = resp.json()
        # La respuesta de un 403 solo debe traer el sobre de error estandar,
        # nunca campos propios del activo (identificador, especie, etc.).
        campos_prohibidos = {
            "identificador", "especie", "raza", "sexo", "peso_actual",
            "eventos_sanitarios", "indicadores", "fase_productiva_activa",
        }
        assert not campos_prohibidos.intersection(body.keys()), (
            f"La respuesta 403 no debe exponer ningun dato del activo. Campos "
            f"encontrados: {campos_prohibidos.intersection(body.keys())}"
        )
        assert body.get("error_code") == "ACCESO_DENEGADO"


class TestTCM02132AccesosDirectosPorRol:
    """Bloqueado: la Seccion 8 (accesos directos) no existe en la API actual
    (confirmado en TC-M02-G77), asi que no hay nada que filtrar por rol."""

    @classmethod
    def setup_class(cls):
        cls.token_veterinario = _login(CORREO_VETERINARIO)

    def test_veterinario_si_puede_leer_su_ficha(self):
        """Control positivo: el Veterinario (solo lectura) SI debe poder ver
        la ficha de un activo dentro de su alcance -- confirma que la cuenta
        y el permiso de lectura funcionan antes de buscar la seccion 8."""
        resp = requests.get(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_VETERINARIO}/ficha-integral",
            headers=_headers(self.token_veterinario),
            timeout=20,
        )
        assert resp.status_code == 200, (
            f"El Veterinario deberia poder leer la ficha de su propio activo: "
            f"{resp.status_code} {resp.text}"
        )

    def test_seccion_accesos_directos_no_existe_bloqueado(self):
        """No es un PASS ni un FAIL de control de acceso -- documenta que el
        sub-caso no es evaluable hoy porque la seccion que describe
        (accesos directos filtrados por rol) no existe en absoluto en la API,
        ver TC-M02-G77 (TC-M02-127) y NOTA_BLOQUEO.md de este caso."""
        resp = requests.get(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_VETERINARIO}/ficha-integral",
            headers=_headers(self.token_veterinario),
            timeout=20,
        )
        body = resp.json()
        assert "accesos_directos" not in body, (
            "Si este assert empieza a fallar, significa que la Seccion 8 ya se "
            "implemento -- en ese momento hay que reemplazar este test por la "
            "verificacion real de TC-M02-132 (accesos visibles solo segun "
            "permisos del rol), no dejarlo como bloqueado."
        )
