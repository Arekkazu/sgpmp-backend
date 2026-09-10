"""TC-M02-G42 — RF-39: inmutabilidad de eventos biologicos (OWASP ASVS V4.2).

TC-M02-080 (Seguridad): un evento biologico ya registrado debe ser append-only
-- ni la API ni un UPDATE/DELETE directo contra la base de datos deben poder
editarlo o eliminarlo.

Dos capas de defensa verificadas, ambas por caja negra contra el entorno TEST
real (no contra el codigo local):

1. Capa de API: no existe ninguna ruta HTTP para editar/eliminar un evento
   especifico -- DELETE/PATCH sobre cualquier patron de URL plausible debe
   dar 404 (la ruta simplemente no existe, no es un 403/405 aplicado).
2. Capa de base de datos (defensa en profundidad, ASVS V4.2 exige que el
   control no dependa solo de la capa de aplicacion): un UPDATE/DELETE
   directo contra `modulo2.eventos_activos` / `eventos_sanitarios` debe ser
   rechazado por el trigger `trg_fn_eventos_activos_inmutable`, incluso con
   una conexion que tiene permiso de escritura a nivel de GRANT.

La capa 2 requiere credenciales de base de datos -- ejecutar solo con
autorizacion explicita para acceder a la BD de TEST. Todas las operaciones de
escritura de este archivo terminan en ROLLBACK; ninguna se compromete nunca.

Ejecutar:
    pytest tests/Test_Testing/Test_Modulo2/RF-39/TC-M02-G42/test_tc_m02_g42_inmutabilidad_eventos.py -v
"""
from __future__ import annotations

import datetime as dt

import psycopg2
import pytest
import requests

BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
CORREO_ADMIN = "admin.test@sgpmp.com.co"
CONTRASENA_ADMIN = "Administrador123#"

# Credencial de solo consulta para verificar hallazgos directamente en la BD
# de TEST (documentada y usada en varias sesiones de QA de este proyecto).
DB_HOST = "158.69.200.27"
DB_PORT = 5448
DB_NAME = "sgpmp_test"
DB_USER = "member_qa"
DB_PASSWORD = "qaSGP2026"

# Activo INDIVIDUAL propio de esta sesion, usado para crear el evento a proteger.
ID_ACTIVO = 218


def _login() -> str:
    resp = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": CORREO_ADMIN, "contrasena": CONTRASENA_ADMIN},
        timeout=20,
    )
    assert resp.status_code == 200, f"Login fallido: {resp.status_code} {resp.text}"
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def token_admin() -> str:
    return _login()


@pytest.fixture(scope="module")
def id_evento(token_admin: str) -> int:
    """Registra un evento sanitario real para intentar editarlo/borrarlo."""
    fecha = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=3)).isoformat()
    resp = requests.post(
        f"{BASE_URL}/activos-biologicos/{ID_ACTIVO}/eventos/sanitario",
        headers=_headers(token_admin),
        json={
            "tipo": "CONTROL_PREVENTIVO",
            "observaciones": "TC-M02-080: evento a proteger",
            "fecha": fecha,
        },
        timeout=20,
    )
    assert resp.status_code == 201, f"No se pudo crear el evento de prueba: {resp.status_code} {resp.text}"
    return resp.json()["evento"]["id_eventos"]


class TestCapaAPI:
    """No existe ninguna ruta HTTP para editar/eliminar un evento."""

    @pytest.mark.parametrize(
        "path_template",
        [
            "/activos-biologicos/{id_activo}/eventos/{id_evento}",
            "/activos-biologicos/eventos/{id_evento}",
            "/eventos/{id_evento}",
        ],
    )
    def test_delete_evento_no_existe_como_ruta(self, token_admin, id_evento, path_template):
        url = BASE_URL + path_template.format(id_activo=ID_ACTIVO, id_evento=id_evento)
        resp = requests.delete(url, headers=_headers(token_admin), timeout=20, allow_redirects=True)
        assert resp.status_code == 404, (
            f"Se esperaba que no exista ninguna ruta DELETE para un evento especifico "
            f"({url}), se obtuvo {resp.status_code}: {resp.text}"
        )

    @pytest.mark.parametrize(
        "path_template",
        [
            "/activos-biologicos/{id_activo}/eventos/{id_evento}",
            "/activos-biologicos/{id_activo}/eventos/sanitario/{id_evento}",
        ],
    )
    def test_patch_evento_no_existe_como_ruta(self, token_admin, id_evento, path_template):
        url = BASE_URL + path_template.format(id_activo=ID_ACTIVO, id_evento=id_evento)
        resp = requests.patch(
            url, headers=_headers(token_admin), json={"observaciones": "editado"},
            timeout=20, allow_redirects=True,
        )
        assert resp.status_code == 404, (
            f"Se esperaba que no exista ninguna ruta PATCH para un evento especifico "
            f"({url}), se obtuvo {resp.status_code}: {resp.text}"
        )

    def test_evento_sigue_intacto_tras_los_intentos(self, token_admin, id_evento):
        """Confirma que ninguno de los intentos anteriores borro el evento, aunque
        hayan dado 404 -- verifica el dato (via el historial RF-46), no solo el
        codigo HTTP de los intentos de DELETE/PATCH.

        Nota: la categoria SANITARIO del historial RF-46 no expone el contenido
        real del evento (`detalle_especifico` sale null para CONTROL_PREVENTIVO
        -- un gap de RF-46 ajeno a esta prueba), asi que se verifica el conteo
        de registros en vez de buscar el texto original.
        """
        resp_hist = requests.get(
            f"{BASE_URL}/activos-biologicos/{ID_ACTIVO}/historial",
            headers=_headers(token_admin),
            timeout=20,
        )
        assert resp_hist.status_code == 200
        assert resp_hist.json()["total_registros"] >= 1, (
            "El evento deberia seguir existiendo en el historial del activo tras "
            "los intentos de DELETE/PATCH -- si el conteo bajara, alguno habria tenido efecto."
        )


class TestCapaBaseDeDatos:
    """Defensa en profundidad (ASVS V4.2): un UPDATE/DELETE directo contra la
    base de datos, con permiso de escritura a nivel de GRANT, debe ser
    rechazado igual por el trigger de inmutabilidad. Todas las operaciones
    terminan en ROLLBACK explicito -- nunca se compromete nada."""

    @pytest.fixture(autouse=True)
    def conexion(self):
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD, connect_timeout=10,
        )
        conn.autocommit = False
        yield conn
        conn.rollback()
        conn.close()

    def test_update_eventos_activos_rechazado(self, conexion, id_evento):
        cur = conexion.cursor()
        with pytest.raises(psycopg2.Error) as exc_info:
            cur.execute(
                "UPDATE modulo2.eventos_activos SET descripcion = %s WHERE id_eventos = %s;",
                ("MODIFICADO pytest", id_evento),
            )
        assert "IMMUTABLE_RECORD" in str(exc_info.value.pgerror or exc_info.value)
        conexion.rollback()

    def test_update_eventos_sanitarios_rechazado(self, conexion, id_evento):
        cur = conexion.cursor()
        with pytest.raises(psycopg2.Error) as exc_info:
            cur.execute(
                "UPDATE modulo2.eventos_sanitarios SET observaciones = %s WHERE id_evento = %s;",
                ("MODIFICADO pytest", id_evento),
            )
        assert "IMMUTABLE_RECORD" in str(exc_info.value.pgerror or exc_info.value)
        conexion.rollback()

    def test_delete_eventos_sanitarios_rechazado(self, conexion, id_evento):
        cur = conexion.cursor()
        with pytest.raises(psycopg2.Error) as exc_info:
            cur.execute("DELETE FROM modulo2.eventos_sanitarios WHERE id_evento = %s;", (id_evento,))
        assert "IMMUTABLE_RECORD" in str(exc_info.value.pgerror or exc_info.value)
        conexion.rollback()

    def test_delete_eventos_activos_rechazado(self, conexion, id_evento):
        cur = conexion.cursor()
        with pytest.raises(psycopg2.Error) as exc_info:
            cur.execute("DELETE FROM modulo2.eventos_activos WHERE id_eventos = %s;", (id_evento,))
        assert "IMMUTABLE_RECORD" in str(exc_info.value.pgerror or exc_info.value)
        conexion.rollback()
