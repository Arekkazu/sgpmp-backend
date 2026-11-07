"""Utilidades de TC-M09-G79-v2.0 (RF-24 v2.0 / TC-M09-150-v2.0).

Laboratorio LOCAL AISLADO con PostgreSQL real y backend HTTP real. No hay dobles de
repositorio, de sesión ni de transacción: la conexión administrativa de este módulo se usa
solo para snapshots, REVOKE/GRANT y verificación SQL, nunca para sustituir al producto.

Las escrituras SQL están autorizadas únicamente dentro de la base efímera del caso. El guard
de entorno aborta antes de cualquier REVOKE/GRANT si la conexión no es inequívocamente local.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import requests

# Guard de aislamiento de carpeta: esta automatización no puede ejecutarse desde la carpeta
# histórica TC-M09-G79/.
FOLDER = "TC-M09-G79-v2.0"
if Path(__file__).resolve().parent.name != FOLDER:
    raise RuntimeError(f"Directorio no autorizado para {FOLDER}")

BASE_DIR = Path(__file__).resolve().parent
SQL_DIR = BASE_DIR / "sql"

GROUP_ID = "TC-M09-G79-v2.0"
CASO = "TC-M09-150-v2.0"
RF = "RF-24 v2.0"
CU = "CU05 — Gestionar Dispositivos IoT, Flujo D"

OBSERVACIONES_CONTROL = "QA TC-M09-150-v2.0 CONTROL"
OBSERVACIONES_OBJETIVO = "QA TC-M09-150-v2.0"

# Mensaje exigido por el FA de RF-24 v2.0. No se adapta al backend.
MENSAJE_500 = (
    "Error de integridad: No se pudo garantizar la trazabilidad de la calibración. "
    "El ajuste no ha sido aplicado; por favor, intente de nuevo."
)

# Identidad esperada del laboratorio aislado.
BD_ESPERADA = "sgpmp_g79_v2"
OWNER_ESPERADO = "sgpmp_owner"
APP_ROLE = "sgpmp_app"
COMPOSE_PROJECT = "sgpmp-g79-v2"
CONTAINER_DB = "sgpmp-g79-v2-db"
CONTAINER_BACKEND = "sgpmp-g79-v2-backend"

ACTOR_CORREO = os.environ.get("G79_ING_EMAIL", "ingeniero@pecuaria.co")
ROL_ESPERADO = "Ingeniero de Campo"

TABLA_CALIBRACIONES = "modulo9.calibraciones"
TABLA_AUDITORIA_M9 = "modulo9.auditorias_calibraciones"
TABLA_EVENTOS_M1 = "modulo1.eventos"


# --------------------------------------------------------------------------- secretos
def _secretos() -> list[str]:
    return [
        v for v in (
            os.environ.get("G79_OWNER_PASSWORD"),
            os.environ.get("G79_APP_PASSWORD"),
            os.environ.get("G79_ING_PASSWORD"),
            os.environ.get("G79_SECRET_KEY"),
        ) if v
    ]


def clean(texto: Any) -> str:
    """Redacta secretos, JWT, Bearer y contraseñas embebidas en cadenas de conexión."""
    s = str(texto)
    for secreto in set(_secretos()):
        s = s.replace(secreto, "[REDACTED]")
    s = re.sub(r"eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]*", "[JWT REDACTED]", s)
    s = re.sub(r"Bearer\s+[A-Za-z0-9_.\-]{12,}", "Bearer [REDACTED]", s)
    # postgresql://usuario:[REDACTED]@host -> la clave se redacta aunque no esté en el entorno.
    s = re.sub(r"(postgres(?:ql)?://[^:/\s]+):[^@\s]+@", r"\1:[REDACTED]@", s)
    return s


# --------------------------------------------------------------------------- evidencia
class Evidencia:
    """Escribe la evidencia del RUN ya sanitizada."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.dir = BASE_DIR / "RESULTADOS" / run_id
        self.dir.mkdir(parents=True, exist_ok=True)

    def ruta(self, nombre: str) -> Path:
        destino = self.dir / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        return destino

    def json(self, nombre: str, valor: Any) -> Path:
        destino = self.ruta(nombre)
        destino.write_text(clean(json.dumps(valor, indent=2, ensure_ascii=False, default=str)), encoding="utf-8")
        return destino

    def texto(self, nombre: str, valor: str) -> Path:
        destino = self.ruta(nombre)
        destino.write_text(clean(valor), encoding="utf-8")
        return destino


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- comandos
def run_cmd(args: list[str], timeout: int = 180) -> tuple[int, str]:
    """Ejecuta un comando y devuelve (returncode, salida combinada sanitizada)."""
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    return proc.returncode, clean((proc.stdout or "") + (proc.stderr or ""))


def psql_owner(sql_file: Path | None = None, sql: str | None = None, variables: dict[str, str] | None = None) -> tuple[int, str]:
    """Ejecuta SQL como DB_OWNER dentro del contenedor del laboratorio."""
    args = ["docker", "exec", "-i", CONTAINER_DB, "psql", "-U", OWNER_ESPERADO, "-d", BD_ESPERADA, "-v", "ON_ERROR_STOP=1"]
    for clave, valor in (variables or {}).items():
        args += ["-v", f"{clave}={valor}"]
    if sql is not None:
        args += ["-c", sql]
        return run_cmd(args)
    assert sql_file is not None
    proc = subprocess.run(
        args + ["-f", "-"], input=sql_file.read_text(encoding="utf-8"),
        capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace",
    )
    return proc.returncode, clean((proc.stdout or "") + (proc.stderr or ""))


def logs_backend(desde: str | None = None) -> str:
    args = ["docker", "logs", CONTAINER_BACKEND]
    if desde:
        args += ["--since", desde]
    _, salida = run_cmd(args)
    return salida


# --------------------------------------------------------------------------- base de datos
def conexion_admin():
    """Conexión administrativa (DB_OWNER) para snapshots, REVOKE/GRANT y verificación SQL.

    No sustituye nada del producto: el POST siempre viaja por HTTP al backend real.
    """
    dsn = os.environ["G79_ADMIN_DSN"]
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    return conn


def uno(conn, sql: str, params: tuple = ()) -> Any:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        fila = cur.fetchone()
        return fila[0] if fila and len(fila) == 1 else fila


def filas(conn, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(f) for f in cur.fetchall()]


# --------------------------------------------------------------------------- safety guard
HOSTS_LOCALES = {"127.0.0.1", "localhost", "::1"}
PATRONES_PROHIBIDOS = ("inmero.co", "sslip.io", "back-sigab", "dokploy")


def safety_guard(conn) -> dict:
    """Aborta antes de cualquier escritura si el entorno no es inequívocamente local.

    Devuelve el detalle del guard para la evidencia. Lanza RuntimeError si algo no cuadra:
    en ese caso el resultado es BLOCKED / SAFETY GUARD y no se intenta "arreglar" la conexión.
    """
    dsn = os.environ.get("G79_ADMIN_DSN", "")
    api = os.environ.get("G79_API_URL", "")
    identidad = filas(conn, "SELECT current_database() AS db, current_user AS usuario, "
                            "inet_server_addr()::text AS server_addr, inet_server_port() AS server_port")[0]
    host_dsn = (re.search(r"@([^:/?]+)", dsn) or [None, ""])[1]
    host_api = (re.search(r"://([^:/?]+)", api) or [None, ""])[1]

    detalle = {
        "fecha": ahora_iso(),
        "base_de_datos": identidad["db"],
        "usuario_conexion": identidad["usuario"],
        "host_del_dsn": host_dsn,
        "host_de_la_api": host_api,
        "server_port": identidad["server_port"],
        "compose_project": COMPOSE_PROJECT,
        "contenedores": {"db": CONTAINER_DB, "backend": CONTAINER_BACKEND},
        "dsn_sanitizado": clean(dsn),
        "api_url": api,
    }

    problemas: list[str] = []
    if identidad["db"] != BD_ESPERADA:
        problemas.append(f"la base es {identidad['db']} y se esperaba {BD_ESPERADA}")
    if host_dsn not in HOSTS_LOCALES:
        problemas.append(f"el host del DSN ({host_dsn}) no es local")
    if host_api not in HOSTS_LOCALES:
        problemas.append(f"el host de la API ({host_api}) no es local")
    for patron in PATRONES_PROHIBIDOS:
        if patron in dsn.lower() or patron in api.lower():
            problemas.append(f"la conexión referencia un entorno remoto ({patron})")
    for sospechoso in ("test", "dev", "main", "prod"):
        if identidad["db"].lower() in (f"sgpmp_{sospechoso}", sospechoso):
            problemas.append(f"la base parece un entorno compartido ({identidad['db']})")

    detalle["problemas"] = problemas
    detalle["resultado"] = "PASS" if not problemas else "BLOCKED / SAFETY GUARD"
    if problemas:
        raise RuntimeError("BLOCKED / SAFETY GUARD: " + "; ".join(problemas))
    return detalle


# --------------------------------------------------------------------------- privilegios
def privilegios_app(conn) -> dict:
    fila = filas(conn, f"""
        SELECT has_table_privilege(%s, '{TABLA_CALIBRACIONES}', 'INSERT')  AS calibraciones_insert,
               has_table_privilege(%s, '{TABLA_AUDITORIA_M9}', 'INSERT')   AS audit_m9_insert,
               has_table_privilege(%s, '{TABLA_EVENTOS_M1}', 'INSERT')     AS eventos_insert
    """, (APP_ROLE, APP_ROLE, APP_ROLE))[0]
    return fila


def rol_app(conn) -> dict:
    return filas(conn, "SELECT rolname, rolsuper, rolinherit, rolbypassrls, rolcanlogin "
                       "FROM pg_roles WHERE rolname = %s", (APP_ROLE,))[0]


def owners_tablas(conn) -> list[dict]:
    return filas(conn, """
        SELECT schemaname, tablename, tableowner
        FROM pg_tables
        WHERE (schemaname, tablename) IN (('modulo9','calibraciones'),
                                          ('modulo9','auditorias_calibraciones'),
                                          ('modulo1','eventos'))
        ORDER BY schemaname, tablename
    """)


def grants_auditoria(conn) -> list[dict]:
    return filas(conn, """
        SELECT grantee, table_schema, table_name, privilege_type
        FROM information_schema.role_table_grants
        WHERE grantee = %s AND table_schema IN ('modulo1','modulo9')
          AND table_name IN ('eventos','auditorias_calibraciones')
        ORDER BY table_schema, table_name, privilege_type
    """, (APP_ROLE,))


# --------------------------------------------------------------------------- calibraciones
def count_calibraciones(conn, id_sensor: int) -> int:
    return int(uno(conn, f"SELECT count(*) FROM {TABLA_CALIBRACIONES} WHERE id_sensor = %s", (id_sensor,)))


def rows_calibraciones(conn, id_sensor: int) -> list[dict]:
    return filas(conn, f"""
        SELECT id_calibracion, id_dispositivo_iot, id_sensor, valor_referencia,
               fecha_calibracion, id_usuario, observaciones, ganancia, offset_calibracion
        FROM {TABLA_CALIBRACIONES} WHERE id_sensor = %s ORDER BY id_calibracion
    """, (id_sensor,))


def auditorias_de(conn, id_calibracion: int) -> list[dict]:
    return filas(conn, f"""
        SELECT id_auditoria_calibracion, id_calibracion, id_usuario, tipo_operacion, fecha_gestion
        FROM {TABLA_AUDITORIA_M9} WHERE id_calibracion = %s ORDER BY id_auditoria_calibracion
    """, (id_calibracion,))


def auditorias_huerfanas(conn) -> list[dict]:
    """Auditoría de calibración cuya calibración no existe: señal de persistencia parcial."""
    return filas(conn, f"""
        SELECT a.id_auditoria_calibracion, a.id_calibracion, a.id_usuario, a.fecha_gestion
        FROM {TABLA_AUDITORIA_M9} a
        LEFT JOIN {TABLA_CALIBRACIONES} c ON c.id_calibracion = a.id_calibracion
        WHERE c.id_calibracion IS NULL
        ORDER BY a.id_auditoria_calibracion
    """)


def eventos_desde(conn, desde_iso: str) -> list[dict]:
    return filas(conn, f"""
        SELECT id_evento, id_usuario, fecha_evento
        FROM {TABLA_EVENTOS_M1}
        WHERE fecha_evento >= %s::timestamptz
        ORDER BY id_evento
    """, (desde_iso,))


# --------------------------------------------------------------------------- API real
class ApiCliente:
    """Cliente del backend HTTP real. El token vive solo en memoria."""

    def __init__(self) -> None:
        self.base = os.environ["G79_API_URL"].rstrip("/")
        self._token: str | None = None

    def health(self) -> int:
        return requests.get(f"{self.base}/health", timeout=20).status_code

    def openapi(self) -> dict:
        r = requests.get(f"{self.base}/openapi.json", timeout=30)
        r.raise_for_status()
        return r.json()

    def login(self, correo: str, password: str) -> dict:
        r = requests.post(
            f"{self.base}/sesiones/",
            json={"correo_electronico": correo, "contrasena": password},
            timeout=30,
        )
        cuerpo = r.json() if r.content else {}
        if r.status_code == 200 and cuerpo.get("token"):
            self._token = cuerpo["token"]
        # Nunca se devuelve el token hacia la evidencia.
        return {"status": r.status_code, "tiene_token": bool(cuerpo.get("token")),
                "error_code": cuerpo.get("error_code")}

    @property
    def autenticado(self) -> bool:
        return self._token is not None

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def get(self, ruta: str) -> tuple[int, Any]:
        r = requests.get(f"{self.base}{ruta}", headers=self._headers(), timeout=30)
        return r.status_code, (r.json() if r.content else None)

    def calibrar(self, id_sensor: int, body: dict) -> tuple[int, Any]:
        """Único método de escritura funcional. Se invoca como máximo dos veces por RUN:
        una para el control positivo y una para el POST objetivo. No reintenta nunca."""
        r = requests.post(
            f"{self.base}/configuracion/sensores/{id_sensor}/calibrar",
            headers=self._headers(), data=json.dumps(body), timeout=60,
        )
        return r.status_code, (r.json() if r.content else None)


def cuerpo_calibracion(id_dispositivo: int, id_area: int, valor: str, observaciones: str) -> dict:
    """Body del caso. modo_calibracion=SENSOR se envía aunque el schema no lo declare."""
    return {
        "modo_calibracion": "SENSOR",
        "id_dispositivo_iot": id_dispositivo,
        "id_infraestructura": id_area,
        "valor_referencia": float(valor),
        "observaciones": observaciones,
        "fecha_calibracion": ahora_iso(),
    }
