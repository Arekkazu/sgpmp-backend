"""
TC-M01-119 (RETEST v2.0 - 2026-09-13) - Eliminar un rol sin usuarios asociados.

RF relacionado: RF-03
Incidencia original: INC-M01-03-119 (Critico) - DELETE /roles/{id} devolvia 500
para cualquier rol no protegido; el rol y sus permisos permanecian en BD.
Fix: PR #62, migracion Alembic c4a19e7d2b63 (FK permisos->roles a ON DELETE
CASCADE + trigger de proteccion corregido para retornar OLD en DELETE).

Por que esta version ya no usa el fixture "Auxiliar de Campo": el rol
sembrado original (id_rol=10) ya no existe en el ambiente TEST -- todo
indica que se elimino con exito al verificar el fix (evidencia: el id 10
esta ausente del listado y no hay rastro de un 500 en el historial). El
caso original (TC-M01-119.json) asumia ese nombre fijo como fixture y por
eso fallaba con "expected undefined to exist" al no encontrarlo, no porque
el defecto critico haya reaparecido.

Este retest sigue el mismo patron que TC-M01-114/122/123/124 (que ya
demostraron ser estables): crea su propio rol con nombre unico por
timestamp, lo elimina, y verifica que la eliminacion fue real (200, sin
rastro del rol en el listado posterior) -- sin depender de datos de
semilla fijos.

IMPORTANTE - hallazgo nuevo durante este retest, fuera del alcance de
TC-M01-119: crear un rol cuyo nombre_rol EMPIEZA exactamente con "Auxiliar
de Campo" (mayusculas y espacio exactos) devuelve HTTP 500 ERROR_INTERNO de
forma reproducible (4/4 intentos). Se documenta y reproduce por separado en
INC-M01-24-500-nombre-rol (ver RF-03/INC-M01-24-500-nombre-rol/), para no
mezclar su veredicto con el de este caso -- TC-M01-119 ya no depende de ese
nombre y no debe salir Rechazado por un defecto que no es el suyo.

Como correrlo (desde la raiz del repo backend):
    python -m pytest tests/Test_Testing/Test_Modulo1/RF-03/TC-M01-119/test_tc_m01_119_v2.py \
        -v --html=tests/Test_Testing/Test_Modulo1/RF-03/TC-M01-119/Resultados/reporte-TC-M01-119-v2.0.html \
        --self-contained-html
"""
import time

import pytest
import requests

BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
ADMIN_CORREO = "admin.dev@gmail.com"
ADMIN_CONTRASENA = "Test1234!"


@pytest.fixture(scope="module")
def token_admin():
    resp = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": ADMIN_CORREO, "contrasena": ADMIN_CONTRASENA},
        timeout=15,
    )
    assert resp.status_code == 200, f"Login fallo: {resp.status_code} {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def headers(token_admin):
    return {"Authorization": f"Bearer {token_admin}", "Content-Type": "application/json"}


class TestTCM01119RetestEliminarRol:
    def test_eliminar_rol_sin_usuarios_no_debe_fallar(self, headers):
        """Alcance real de TC-M01-119: un rol no protegido y sin usuarios
        asociados debe eliminarse con 200, sin dejar rastro en el listado."""
        nombre_rol = f"QA Retest TC119 v2.0 {int(time.time() * 1000)}"

        crear = requests.post(
            f"{BASE_URL}/roles/",
            headers=headers,
            json={
                "nombre_rol": nombre_rol,
                "descripcion": "Rol creado por el retest v2.0 de TC-M01-119",
                "permisos": [{"id_recurso": 1, "id_accion": 2}],
            },
            timeout=15,
        )
        assert crear.status_code == 201, (
            f"No se pudo crear el rol de prueba: {crear.status_code} {crear.text}"
        )
        id_rol = crear.json()["id_rol"]

        eliminar = requests.delete(f"{BASE_URL}/roles/{id_rol}", headers=headers, timeout=15)
        assert eliminar.status_code == 200, (
            f"DELETE /roles/{{id}} debia responder 200 para un rol sin usuarios "
            f"asociados (INC-M01-03-119). Respuesta real: {eliminar.status_code} "
            f"{eliminar.text}"
        )

        listado = requests.get(f"{BASE_URL}/roles/", headers=headers, timeout=15)
        assert listado.status_code == 200
        ids_presentes = {r["id_rol"] for r in listado.json()}
        assert id_rol not in ids_presentes, (
            f"El rol {id_rol} respondio 200 al eliminarlo pero sigue en el "
            f"listado -- indicaria que INC-M01-03-119 no esta corregido de "
            f"verdad (eliminacion silenciosamente ignorada)."
        )
