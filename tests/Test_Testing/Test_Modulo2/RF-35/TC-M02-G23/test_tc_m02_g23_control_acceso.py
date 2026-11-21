"""TC-M02-G23 — RF-35/RF-37: control de acceso y proteccion del historial inmutable.

Pruebas de seguridad (OWASP API1:BOLA, API5:Broken Function Level Authorization,
API3) contra el backend TEST desplegado. Ejecuta HTTP real via ``requests`` —
no son pruebas unitarias contra el codigo local, son regresion de caja negra
contra el mismo entorno TEST que usa la coleccion Postman hermana
(TC-M02-G23.postman_collection.json).

Las aserciones codifican el comportamiento que EXIGE el RF, no el observado
a priori: si el sistema deja de cumplirlo, pytest debe volver a fallar de
forma honesta (ver RESULTADOS/TC-M02-G23_resultado.html para la evidencia).

Requiere: pip install requests pytest (o ejecutar dentro del venv del backend,
que ya trae requests como dependencia transitiva de httpx/starlette).

Ejecutar solo este archivo:
    pytest tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G23/test_tc_m02_g23_control_acceso.py -v
"""
from __future__ import annotations

import time

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

    def test_patch_activo_de_otra_finca_debe_rechazarse(self):
        """BOLA (OWASP API1): un Productor limitado a una finca no debe poder
        actualizar un activo de otra finca. El RF pide 403; el sistema
        responde 404 (mismo criterio de aislamiento ya usado en el GET, que
        tampoco revela la existencia del recurso) — igual de valido para
        cerrar el BOLA, ver README.md."""
        resp = requests.patch(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_AJENO_B}",
            headers=_headers(self.token_productor_a),
            json={"raza": "MODIFICADO por Productor A via BOLA - pytest"},
            timeout=20,
        )
        assert resp.status_code in (403, 404), (
            "BOLA (OWASP API1): un Productor limitado a una finca pudo actualizar "
            f"un activo de otra finca. Se esperaba 403 o 404, se obtuvo "
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
    """RF-37 - historial de fases append-only.

    Usa un activo propio de esta clase (creado en setup_class), no el activo
    199 compartido con TestTCM02045BOLA/TestTCM02046FuncionRestringidaPorRol,
    para no agotar los pasos de su ciclo productivo en corridas repetidas.
    """

    ID_CICLO_PRODUCTIVA = 2

    @classmethod
    def setup_class(cls):
        cls.token_admin = _login(CORREO_ADMIN, CONTRASENA_ADMIN)
        resp = requests.post(
            f"{BASE_URL}/activos-biologicos",
            headers=_headers(cls.token_admin),
            json={
                "tipo_activo": "INDIVIDUAL",
                "id_especie": 2,
                "fecha_inicio_ciclo": "2026-01-01",
                "origen_financiero": "nacimiento",
                "id_infraestructura": 6,
                "identificador": f"QA-G23F-PY-{int(time.time() * 1000)}",
                "raza": "Trucha QA-G23 fases pytest",
                "sexo": "Macho",
                "fecha_nacimiento": "2025-01-15T00:00:00Z",
                "peso_inicial": 2.5,
            },
            timeout=20,
        )
        assert resp.status_code == 201, f"Setup del activo para fases fallo: {resp.status_code} {resp.text}"
        cls.id_activo_fases = resp.json()["id_activo_biologico"]

    def test_no_existe_endpoint_de_edicion_directa_de_fase(self):
        """Verificacion estructural: no hay ninguna ruta PATCH sobre una fase."""
        resp = requests.patch(
            f"{BASE_URL}/activos-biologicos/{self.id_activo_fases}/fases/1",
            headers=_headers(self.token_admin),
            json={"fecha_finalizacion": "2020-01-01T00:00:00Z"},
            timeout=20,
        )
        assert resp.status_code in (404, 405), (
            f"No deberia existir una ruta para editar una fase directamente, "
            f"se obtuvo {resp.status_code}. Body: {resp.text}"
        )

    def test_registrar_primera_fase(self):
        resp = requests.post(
            f"{BASE_URL}/activos-biologicos/{self.id_activo_fases}/fases",
            headers=_headers(self.token_admin),
            json={"id_ciclo_productiva": self.ID_CICLO_PRODUCTIVA, "motivo_cambio": "pytest: primera fase"},
            timeout=20,
        )
        assert resp.status_code == 201, f"RF-37: registrar la primera fase deberia funcionar: {resp.status_code} {resp.text}"
        body = resp.json()
        assert body["es_activa"] is True
        assert body["fecha_finalizacion"] is None

    def test_avanzar_segunda_fase_cierra_la_primera_de_forma_inmutable(self):
        resp = requests.post(
            f"{BASE_URL}/activos-biologicos/{self.id_activo_fases}/fases",
            headers=_headers(self.token_admin),
            json={"id_ciclo_productiva": self.ID_CICLO_PRODUCTIVA, "motivo_cambio": "pytest: segunda fase"},
            timeout=20,
        )
        assert resp.status_code == 201, f"RF-37: avanzar a la segunda fase deberia funcionar: {resp.status_code} {resp.text}"

        historial = requests.get(
            f"{BASE_URL}/activos-biologicos/{self.id_activo_fases}/fases",
            headers=_headers(self.token_admin),
            timeout=20,
        )
        assert historial.status_code == 200
        primera = next(f for f in historial.json()["fases"] if f["paso_actual"] == 1)
        assert primera["es_activa"] is False, "La primera fase deberia quedar inactiva al avanzar a la segunda."
        assert primera["fecha_finalizacion"] is not None, (
            "La primera fase deberia quedar con fecha_finalizacion fija (append-only) al cerrarse."
        )
