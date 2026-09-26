"""
INC-M01-24-500-nombre-rol - Reproduccion.

Descubierto el 2026-09-13 al retestear TC-M01-119 (ver
../TC-M01-119/test_tc_m01_119_v2.py). No es el alcance de TC-M01-119; se
documenta y reproduce aparte para no mezclar su veredicto con el de ese caso.

Defecto: POST /roles/ devuelve HTTP 500 ERROR_INTERNO (en vez de 201 o un
4xx controlado) cuando `nombre_rol` EMPIEZA exactamente con la cadena
"Auxiliar de Campo" (mayusculas y un solo espacio, tal como el sistema lo
usaba). Reproducible 4/4 veces contra el ambiente TEST el 2026-09-13.

Contexto: el rol semilla original id_rol=10, nombre "Auxiliar de Campo",
fue el fixture de INC-M01-03-119 (DELETE /roles/{id} -> 500). Ese id ya no
existe en TEST -- todo indica que se elimino con exito al verificar el fix
de INC-M01-03-119 (ver TC-M01-119 v2.0, que confirma que DELETE ya
funciona). Este hallazgo nuevo sugiere que algo quedo mal manejado despues
de esa eliminacion (constraint, indice o trigger que compara el nombre de
forma exacta contra un registro de auditoria/historico), pero eso es
hipotesis de QA -- Desarrollo debe confirmar la causa raiz real.

Evidencia de aislamiento (variantes probadas manualmente el 2026-09-13):
    "Auxiliar de Campo <sufijo>"    -> 500  (prefijo exacto)
    "Auxiliar de Campo"             -> 500  (nombre exacto)
    "auxiliar de campo"             -> 201  (minusculas)
    "AUXILIAR DE CAMPO"             -> 201  (mayusculas)
    "Auxiliar de Camp"              -> 201  (un caracter menos)
    "Auxiliar  de Campo"            -> 201  (doble espacio)
    "xAuxiliar de Campo"            -> 201  (con prefijo extra, ya no es
                                              prefijo exacto de la cadena)
    "Auxiliar" / "Campo"            -> 201  (por separado)

Como correrlo (desde la raiz del repo backend):
    python -m pytest tests/Test_Testing/Test_Modulo1/RF-03/INC-M01-24-500-nombre-rol/repro_defecto_nombre_auxiliar_de_campo.py \
        -v --html=tests/Test_Testing/Test_Modulo1/RF-03/INC-M01-24-500-nombre-rol/Resultados/reporte-v2.0.html \
        --self-contained-html

Este test se espera que FALLE mientras el defecto siga presente -- es la
evidencia formal del hallazgo, no una verificacion de exito.
"""
import time

import pytest
import requests

BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
ADMIN_CORREO = "admin.dev@gmail.com"
ADMIN_CONTRASENA = "Test1234!"


@pytest.fixture(scope="module")
def headers():
    resp = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": ADMIN_CORREO, "contrasena": ADMIN_CONTRASENA},
        timeout=15,
    )
    assert resp.status_code == 200, f"Login fallo: {resp.status_code} {resp.text}"
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _crear_rol(headers, nombre_rol):
    return requests.post(
        f"{BASE_URL}/roles/",
        headers=headers,
        json={
            "nombre_rol": nombre_rol,
            "descripcion": "Reproduccion INC-M01-24-500-nombre-rol",
            "permisos": [{"id_recurso": 1, "id_accion": 2}],
        },
        timeout=15,
    )


class TestINCM0124NombreAuxiliarDeCampo:
    def test_prefijo_exacto_auxiliar_de_campo_no_debe_dar_500(self, headers):
        nombre_rol = f"Auxiliar de Campo repro {int(time.time() * 1000)}"
        resp = _crear_rol(headers, nombre_rol)
        if resp.status_code == 201:
            requests.delete(
                f"{BASE_URL}/roles/{resp.json()['id_rol']}", headers=headers, timeout=15
            )
        assert resp.status_code != 500, (
            "DEFECTO REPRODUCIDO: nombre_rol con prefijo exacto 'Auxiliar de "
            f"Campo' -> HTTP 500. Cuerpo: {resp.text}"
        )

    def test_variantes_de_caja_y_espaciado_si_funcionan(self, headers):
        """Control: confirma que el defecto es especifico del prefijo exacto,
        no de la palabra en general -- variantes cercanas SI funcionan."""
        variantes = [
            f"auxiliar de campo repro {int(time.time() * 1000)}",
            f"AUXILIAR DE CAMPO REPRO {int(time.time() * 1000)}",
            f"Auxiliar  de Campo repro {int(time.time() * 1000)}",  # doble espacio
        ]
        creados = []
        try:
            for nombre in variantes:
                resp = _crear_rol(headers, nombre)
                assert resp.status_code == 201, (
                    f"Se esperaba 201 para la variante {nombre!r} (control de "
                    f"aislamiento), se obtuvo {resp.status_code}: {resp.text}"
                )
                creados.append(resp.json()["id_rol"])
        finally:
            for id_rol in creados:
                requests.delete(f"{BASE_URL}/roles/{id_rol}", headers=headers, timeout=15)
