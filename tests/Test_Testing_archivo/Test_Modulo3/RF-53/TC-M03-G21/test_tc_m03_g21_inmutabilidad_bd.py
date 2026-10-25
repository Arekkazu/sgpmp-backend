"""
TC-M03-G21 - Proteccion del historial de telemetria contra modificacion y eliminacion (verificacion en BD).

RF relacionado: RF-53 (CU01). Caso: TC-M03-073 (ASVS V8), sub-caso (b): intento directo contra la BD.

Criterio de la ficha: UPDATE y DELETE sobre un registro ya persistido quedan bloqueados incluso con
privilegios elevados o acceso directo a BD; el registro conserva su valor, timestamp e id originales y el
intento queda auditado.

Como se verifica:
1. Se ejecuta con Newman TC-M03-G21.postman_collection.json (misma carpeta), que crea una lectura propia,
   prueba la via API (073a y 074) y exporta su id en el environment (g21_*).
2. Contra la BD de TEST, con el usuario QA (que tiene privilegio UPDATE/DELETE sobre la tabla, asi que lo
   que se mide es la proteccion propia del dato y no un simple "permiso denegado"):
   - UPDATE y DELETE sobre esa lectura deben fallar por el bloqueo de inmutabilidad.
   - El bypass de triggers con session_replication_role = replica debe estar prohibido.
   - Ningun rol de prueba puede deshabilitar los triggers ni truncar la tabla (se comprueba en el catalogo,
     sin ejecutar ninguna sentencia destructiva).
   - Tras los intentos, el registro sigue identico.

SEGURIDAD DE LA PRUEBA: cada sentencia de escritura se ejecuta dentro de una transaccion explicita que SIEMPRE
termina en ROLLBACK, y solo sobre la lectura creada por la propia coleccion. Aunque el bloqueo no existiera,
la BD compartida de TEST no queda modificada.

Sobre "el intento queda auditado": el trigger de inmutabilidad (modulo3.fn_telemetrias_inmutable) aborta con
RAISE EXCEPTION, que revierte todo lo hecho en la transaccion; cualquier registro de auditoria en tabla dentro de
esa transaccion se pierde. Solo quedaria en el log del servidor (log_statement / pgaudit), que el usuario QA no
puede consultar; el test correspondiente lo reporta como SKIP con esa razon.

Requisitos: newman en el PATH y acceso de red a TEST (API y Postgres 5448).
Variables opcionales: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-53/TC-M03-G21 -v \
        --html=reporte-TC-M03-G21.html --self-contained-html
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import psycopg2
import psycopg2.errors
import pytest

DB_HOST = os.getenv("DB_HOST", "158.69.200.27")
DB_PORT = os.getenv("DB_PORT", "5448")
DB_USER = os.getenv("DB_USER", "member_qa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "qaSGP2026")
DB_NAME = os.getenv("DB_NAME", "sgpmp_test")

_COLECCION = Path(__file__).parent / "TC-M03-G21.postman_collection.json"


@pytest.fixture(scope="module")
def lectura(tmp_path_factory) -> dict:
    newman = shutil.which("newman")
    if newman is None:
        pytest.skip("newman no esta instalado en el PATH")
    salida = tmp_path_factory.mktemp("g21") / "environment.json"
    proceso = subprocess.run(
        [newman, "run", str(_COLECCION), "--export-environment", str(salida), "-r", "cli"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if not salida.exists():
        pytest.fail(f"Newman no exporto el environment:\n{proceso.stdout[-3000:]}\n{proceso.stderr[-2000:]}")
    env = {v["key"]: v["value"] for v in json.loads(salida.read_text(encoding="utf-8"))["values"]}
    if not env.get("g21_id_telemetria", "").isdigit():
        pytest.fail(f"La coleccion no registro la lectura de prueba; salida de Newman:\n{proceso.stdout[-3000:]}")
    return {
        "id": int(env["g21_id_telemetria"]),
        "valor": Decimal(env["g21_valor_original"]),
        "ts": datetime.fromisoformat(env["g21_ts_original"].replace("Z", "+00:00")),
    }


@pytest.fixture
def conexion():
    con = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME)
    con.autocommit = False  # cada prueba trabaja en una transaccion que se revierte
    try:
        yield con
    finally:
        con.rollback()
        con.close()


def _intentar(conexion, sql: str, params: tuple):
    """Ejecuta una sentencia de escritura y SIEMPRE revierte. Devuelve (filas_afectadas, error)."""
    try:
        with conexion.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount, None
    except psycopg2.Error as exc:
        return 0, exc
    finally:
        conexion.rollback()


def _leer(conexion, id_telemetria):
    with conexion.cursor() as cur:
        cur.execute(
            "SELECT id_telemetria, valor_crudo, timestamp_captura FROM modulo3.telemetrias WHERE id_telemetria = %s",
            (id_telemetria,),
        )
        fila = cur.fetchone()
    conexion.rollback()
    return fila


def test_tc_m03_073b_update_directo_en_bd_bloqueado(lectura, conexion):
    filas, error = _intentar(
        conexion,
        "UPDATE modulo3.telemetrias SET valor_crudo = 999, timestamp_captura = timestamp_captura - interval '1 day' "
        "WHERE id_telemetria = %s",
        (lectura["id"],),
    )
    assert error is not None, f"El UPDATE directo se ejecuto ({filas} fila(s) afectadas antes del rollback de la prueba)"
    assert "INMUTABILIDAD" in str(error) or error.pgcode == "P0002", f"Bloqueado por otra causa: {error}"


def test_tc_m03_073b_delete_directo_en_bd_bloqueado(lectura, conexion):
    filas, error = _intentar(conexion, "DELETE FROM modulo3.telemetrias WHERE id_telemetria = %s", (lectura["id"],))
    assert error is not None, f"El DELETE directo se ejecuto ({filas} fila(s) afectadas antes del rollback de la prueba)"
    assert "INMUTABILIDAD" in str(error) or error.pgcode == "P0002", f"Bloqueado por otra causa: {error}"


def test_tc_m03_073b_no_se_puede_saltar_el_trigger_con_replication_role(lectura, conexion):
    """Con session_replication_role = replica los triggers ENABLE (origin) no se disparan."""
    try:
        with conexion.cursor() as cur:
            cur.execute("SET LOCAL session_replication_role = replica")
            cur.execute(
                "UPDATE modulo3.telemetrias SET valor_crudo = 999 WHERE id_telemetria = %s", (lectura["id"],)
            )
            afectadas = cur.rowcount
    except psycopg2.Error as exc:
        assert isinstance(exc, psycopg2.errors.InsufficientPrivilege) or "INMUTABILIDAD" in str(exc), (
            f"Rechazado por una causa inesperada: {exc}"
        )
        return
    finally:
        conexion.rollback()
    pytest.fail(f"El rol {DB_USER} salto los triggers con session_replication_role y modifico {afectadas} fila(s)")


def test_tc_m03_073b_ningun_rol_de_prueba_puede_desactivar_la_proteccion(conexion):
    """Catalogo (sin ejecutar nada): no ser superusuario ni dueno de la tabla, sin TRUNCATE, triggers activos."""
    with conexion.cursor() as cur:
        cur.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        es_super = cur.fetchone()[0]
        cur.execute("SELECT pg_has_role(current_user, tableowner, 'MEMBER') FROM pg_tables "
                    "WHERE schemaname = 'modulo3' AND tablename = 'telemetrias'")
        es_dueno = cur.fetchone()[0]
        cur.execute("SELECT has_table_privilege('modulo3.telemetrias', 'TRUNCATE')")
        puede_truncar = cur.fetchone()[0]
        cur.execute("SELECT tgname, tgenabled FROM pg_trigger WHERE tgrelid = 'modulo3.telemetrias'::regclass "
                    "AND tgname IN ('trg_rf53_02_no_update', 'trg_rf53_03_no_delete')")
        triggers = dict(cur.fetchall())
    conexion.rollback()
    assert not es_super, f"{DB_USER} es superusuario: puede deshabilitar triggers"
    assert not es_dueno, f"{DB_USER} es (o hereda) el dueno de la tabla: puede deshabilitar triggers"
    assert not puede_truncar, "TRUNCATE no dispara triggers por fila y borraria el historial"
    assert triggers == {"trg_rf53_02_no_update": "O", "trg_rf53_03_no_delete": "O"}, (
        f"Triggers de inmutabilidad ausentes o deshabilitados: {triggers}"
    )


def test_tc_m03_073b_registro_intacto_tras_los_intentos(lectura, conexion):
    fila = _leer(conexion, lectura["id"])
    assert fila is not None, "La lectura desaparecio"
    id_tel, valor, ts = fila
    assert id_tel == lectura["id"]
    assert valor == lectura["valor"]
    assert ts == lectura["ts"]


def test_tc_m03_073b_intento_auditado():
    pytest.skip(
        "No verificable con el usuario QA: el trigger de inmutabilidad aborta con RAISE EXCEPTION (revierte "
        "cualquier registro en tabla de la misma transaccion) y el log del servidor/pgaudit no es accesible. "
        "Pedir a Desarrollo/DBA la evidencia del intento en el log de PostgreSQL."
    )
