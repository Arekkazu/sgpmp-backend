"""TC-M02-G23 — RF-35/RF-37: control de acceso y proteccion del historial inmutable.

Pruebas de seguridad (OWASP API1:BOLA, API5:Broken Function Level Authorization,
API3) contra el backend TEST desplegado. Ejecuta HTTP real via ``requests`` —
no son pruebas unitarias contra el codigo local, son regresion de caja negra
contra el mismo entorno TEST que usa la coleccion Postman hermana
(TC-M02-G23.postman_collection.json).

Las aserciones codifican el comportamiento que EXIGE el RF, no el observado,
a proposito: mientras el gap exista, pytest debe reportar FAIL de forma
honesta (ver RESULTADOS/TC-M02-G23_resultado.md para el detalle de por que
fallan y evidencia completa).

Requiere: pip install requests pytest (o ejecutar dentro del venv del backend,
que ya trae requests como dependencia transitiva de httpx/starlette).

Ejecutar solo este archivo:
    pytest tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G23/test_tc_m02_g23_control_acceso.py -v
"""
from __future__ import annotations

import requests

BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"

CORREO_ADMIN = "admin.test@sgpmp.com.co"
CONTRASENA_ADMIN = "Administrador123#"

# Cuenta QA reactivada para esta prueba (ver README.md): Productor con permiso
# de escritura sobre activos_biologicos, limitado a la Finca 36 (QA G23 Finca
# Alfa), creada especificamente para este caso.
CORREO_PRODUCTOR_A = "tc015b.qa@sgpmp-test.com"

# Cuenta QA reactivada y re-rolada a Veterinario para esta prueba: tiene
# permiso de lectura pero NO de escritura sobre activos_biologicos.
CORREO_VETERINARIO = "tc020.qa@sgpmp-test.com"

CONTRASENA_QA_COMPARTIDA = "Abcd12#3"

# Activo propio del Productor A (Finca 36 / QA-G23-Estanque-A).
ID_ACTIVO_PROPIO_A = 199

# Activo "victima" controlado en una finca ajena (Finca 37 / QA-G23-Estanque-B,
# propiedad del admin) — usado para el BOLA de TC-M02-045. Es un activo propio
# de esta suite de pruebas, no pertenece a un usuario real; se puede modificar
# y restaurar libremente sin afectar a nadie mas.
ID_ACTIVO_AJENO_B = 200
RAZA_ORIGINAL_AJENO = "Camaron victima finca B"


def _login(correo: str, contrasena: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": correo, "contrasena": contrasena},
        timeout=20,
    )
    assert resp.status_code == 200, f"Login fallido para {correo}: {resp.status_code} {resp.text}"
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


class TestTCM02045BOLA:
    """OWASP API1:2023 — Broken Object Level Authorization."""

    @classmethod
    def setup_class(cls):
        cls.token_admin = _login(CORREO_ADMIN, CONTRASENA_ADMIN)
        cls.token_productor_a = _login(CORREO_PRODUCTOR_A, CONTRASENA_QA_COMPARTIDA)

    @classmethod
    def teardown_class(cls):
        # Deja el activo victima en su estado original, sin importar el
        # resultado de la prueba (incluida la explotacion exitosa del BOLA).
        requests.patch(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_AJENO_B}",
            headers=_headers(cls.token_admin),
            json={"raza": RAZA_ORIGINAL_AJENO},
            timeout=20,
        )

    def test_control_positivo_productor_edita_su_propio_activo(self):
        resp = requests.patch(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_PROPIO_A}",
            headers=_headers(self.token_productor_a),
            json={"raza": "Camaron propio - pytest control positivo"},
            timeout=20,
        )
        assert resp.status_code == 200, (
            "El Productor A deberia poder editar su propio activo (control positivo, "
            f"no es el BOLA que se esta probando): {resp.status_code} {resp.text}"
        )

    def test_get_activo_de_otra_finca_no_lo_revela(self):
        resp = requests.get(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_AJENO_B}",
            headers=_headers(self.token_productor_a),
            timeout=20,
        )
        assert resp.status_code == 404, (
            "GET si aplica el alcance por finca (RF-25) correctamente: "
            f"se esperaba 404, se obtuvo {resp.status_code} {resp.text}"
        )

    def test_patch_activo_de_otra_finca_debe_rechazarse_con_403(self):
        """BOLA critico: RF-35 exige 403. Confirmado en vivo que responde 200."""
        resp = requests.patch(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_AJENO_B}",
            headers=_headers(self.token_productor_a),
            json={"raza": "MODIFICADO por Productor A via BOLA - pytest"},
            timeout=20,
        )
        assert resp.status_code == 403, (
            "BOLA confirmado (OWASP API1): un Productor limitado a una finca puede "
            f"actualizar un activo de otra finca. Se esperaba 403, se obtuvo "
            f"{resp.status_code}. Body: {resp.text}"
        )

    def test_activo_ajeno_no_debio_cambiar(self):
        """Verifica el efecto de negocio, independiente del codigo HTTP anterior."""
        resp = requests.get(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_AJENO_B}",
            headers=_headers(self.token_admin),
            timeout=20,
        )
        assert resp.status_code == 200
        raza_actual = resp.json()["detalle_individual"]["raza"]
        assert raza_actual == RAZA_ORIGINAL_AJENO, (
            f"El activo ajeno fue modificado por un usuario sin permiso sobre esa finca. "
            f"raza actual: {raza_actual!r}, esperada: {RAZA_ORIGINAL_AJENO!r}."
        )


class TestTCM02046FuncionRestringidaPorRol:
    """OWASP API5:2023 — Broken Function Level Authorization."""

    @classmethod
    def setup_class(cls):
        cls.token_veterinario = _login(CORREO_VETERINARIO, CONTRASENA_QA_COMPARTIDA)

    def test_rol_sin_permiso_escritura_no_puede_actualizar(self):
        resp = requests.patch(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_PROPIO_A}",
            headers=_headers(self.token_veterinario),
            json={"raza": "Intento de veterinario sin permiso - pytest"},
            timeout=20,
        )
        assert resp.status_code == 403, (
            f"Un rol sin permiso de escritura (Veterinario) debe recibir 403, "
            f"se obtuvo {resp.status_code}. Body: {resp.text}"
        )
        assert resp.json().get("error_code") == "ACCESO_DENEGADO"


class TestTCM02047HistorialFasesInmutable:
    """RF-37 — historial de fases append-only.

    BLOQUEADO: no se pudo construir la precondicion literal ("existe una fase
    ya cerrada") porque POST /fases esta roto para cualquier activo — ver
    NOTA_BLOQUEO.md para la causa raiz exacta (falta un argumento en una
    llamada de cambiar_fase_use_case.py). Se deja el test que reproduce el
    bloqueo (xfail, no skip: si el bug se corrige, este test debe empezar a
    fallar y avisar que hay que completar TC-M02-047 de verdad) y el test
    estructural que SI se puede verificar sin esa precondicion.
    """

    @classmethod
    def setup_class(cls):
        cls.token_admin = _login(CORREO_ADMIN, CONTRASENA_ADMIN)

    def test_no_existe_endpoint_de_edicion_directa_de_fase(self):
        """Verificacion estructural: no hay ninguna ruta PATCH sobre una fase.

        No depende de la precondicion bloqueada — confirma que el historial es
        append-only por ausencia de endpoint, incluso sin poder crear fases.
        """
        resp = requests.patch(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_PROPIO_A}/fases/1",
            headers=_headers(self.token_admin),
            json={"fecha_finalizacion": "2020-01-01T00:00:00Z"},
            timeout=20,
        )
        assert resp.status_code in (404, 405), (
            f"No deberia existir una ruta para editar una fase directamente, "
            f"se obtuvo {resp.status_code}. Body: {resp.text}"
        )

    def test_precondicion_bloqueada_cambiar_fase_falla_para_cualquier_activo(self):
        """Documenta el bloqueo — ver NOTA_BLOQUEO.md.

        Esta asercion espera el ESTADO ACTUAL (roto). El dia que alguien
        corrija cambiar_fase_use_case.py, este test empezara a fallar aqui,
        lo cual es la senal correcta de que hay que reemplazarlo por el
        TC-M02-047 completo (avanzar 2 fases y verificar inmutabilidad de la
        primera).
        """
        resp = requests.post(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_PROPIO_A}/fases",
            headers=_headers(self.token_admin),
            json={"id_ciclo_productiva": 2, "motivo_cambio": "pytest: probe bloqueo RF-37"},
            timeout=20,
        )
        assert resp.status_code == 500, (
            "Este assert documenta un bloqueo conocido (ver NOTA_BLOQUEO.md). "
            f"Si esto ya no da 500 (obtenido: {resp.status_code}), el bug de "
            "cambiar_fase_use_case.py fue corregido: reemplazar este test por "
            "el TC-M02-047 completo (crear 2 fases y verificar inmutabilidad "
            "de la primera)."
        )
