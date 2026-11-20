# | Fecha      | Nombre      | Que se hizo |
# |------------|-------------|-------------|
# | 2026-11-17 | Laura López | TC-M07-G058: sondas SQL readonly (Docker local) + diagnóstico estructural RF-102. |
"""Ejecuta consultas SQL de solo lectura para TC-M07-G058.

Prioridad:
  1) Docker ``infra-db-1`` BD ``sgpmp`` (solo SELECT / catálogo).
  2) Si la tabla ``modulo7.eventos_integracion`` no existe localmente
     (migración RF-102 no aplicada), documenta la ausencia y NO crea objetos.

No usa credenciales en archivos. No DML/DDL sobre BD compartida TEST.

    python tests/Test_Testing/Test_Modulo7/RF-102/TC-M07-G058/ejecutar_sql_tc_m07_g58.py
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADO = CARPETA / "Resultado"
SQL_FILE = CARPETA / "consultas_sql_TC-M07-G058.sql"
OUT_TXT = RESULTADO / "resultado_consultas_sql_TC-M07-G058.txt"
OUT_JSON = RESULTADO / "diagnostico_sql_TC-M07-G058.json"

CONTAINER = "infra-db-1"
DB_NAME = "sgpmp"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def docker_ok() -> bool:
    p = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER],
        capture_output=True, text=True,
    )
    return p.stdout.strip() == "true"


def psql(sql: str, db: str = DB_NAME) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=0"],
        input=sql.encode("utf-8"),
        capture_output=True,
    )


def main() -> int:
    RESULTADO.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    diag: dict = {
        "fecha_utc": ahora(),
        "contenedor": CONTAINER,
        "base": DB_NAME,
        "solo_lectura": True,
        "sql_fuente": SQL_FILE.name,
        "pasos": [],
        "viable": False,
    }

    if not docker_ok():
        diag["motivo"] = f"Contenedor {CONTAINER} no disponible"
        OUT_JSON.write_text(json.dumps(diag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        OUT_TXT.write_text(diag["motivo"] + "\n", encoding="utf-8")
        print(json.dumps(diag, ensure_ascii=False, indent=2))
        return 2

    # Probe table existence first
    probe = psql(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='modulo7' AND table_name='eventos_integracion') AS existe;"
    )
    out = (probe.stdout or b"").decode("utf-8", "replace")
    err = (probe.stderr or b"").decode("utf-8", "replace")
    log.append("=== PROBE eventos_integracion ===\n" + out + err)
    existe = "t" in out.split() or "| t" in out or "existe \n-----\n t" in out.replace(" ", "")
    # robust parse
    existe = " t\n" in out or out.strip().endswith("t") or "\nt\n" in out
    diag["pasos"].append({"paso": "probe_tabla", "ok": probe.returncode == 0, "existe_eventos_integracion": existe, "stdout": out[-500:]})

    # Catalog search always
    catalog = psql("""
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'modulo7'
  AND (
    table_name ILIKE '%evento%integr%'
    OR table_name ILIKE '%archiv%'
    OR table_name ILIKE '%reten%'
    OR table_name ILIKE '%histor%'
    OR table_name ILIKE '%rf102%'
  )
ORDER BY 1, 2;
""")
    cat_out = (catalog.stdout or b"").decode("utf-8", "replace")
    log.append("=== CATALOGO modulo7 relevante ===\n" + cat_out)
    diag["catalogo_modulo7"] = cat_out

    # pg_cron
    cron = psql("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='pg_cron') AS tiene_pg_cron;")
    cron_out = (cron.stdout or b"").decode("utf-8", "replace")
    log.append("=== pg_cron ===\n" + cron_out)
    diag["pg_cron"] = cron_out
    tiene_cron = "\nt\n" in cron_out or cron_out.strip().endswith("t")

    jobs = None
    if tiene_cron:
        jobs_r = psql(
            "SELECT jobid::text, schedule, command FROM cron.job "
            "WHERE command ILIKE '%modulo7%' OR command ILIKE '%eventos_integracion%' "
            "OR command ILIKE '%archiv%' OR command ILIKE '%reten%';"
        )
        jobs = (jobs_r.stdout or b"").decode("utf-8", "replace")
        log.append("=== cron.job filtrado ===\n" + jobs)
    diag["cron_jobs_filtrados"] = jobs
    diag["tiene_pg_cron"] = tiene_cron

    # M01 archive contrast (not RF-102)
    m01 = psql("""
SELECT 'modulo1.eventos_archivados' AS objeto,
       EXISTS(SELECT 1 FROM information_schema.tables
              WHERE table_schema='modulo1' AND table_name='eventos_archivados') AS existe;
""")
    m01_out = (m01.stdout or b"").decode("utf-8", "replace")
    log.append("=== contraste M01 eventos_archivados (NO es RF-102) ===\n" + m01_out)
    diag["contraste_m01_eventos_archivados"] = m01_out

    stats = None
    if existe:
        full = psql(SQL_FILE.read_text(encoding="utf-8"))
        full_out = (full.stdout or b"").decode("utf-8", "replace")
        full_err = (full.stderr or b"").decode("utf-8", "replace")
        log.append("=== CONSULTAS COMPLETAS ===\n" + full_out + "\n" + full_err)
        stats_r = psql("""
SELECT count(*)::int AS total,
       count(*) FILTER (WHERE hash_integridad IS NOT NULL AND hash_integridad ~ '^[0-9a-f]{64}$')::int AS con_hash,
       min(fecha_evento)::text AS min_fecha,
       max(fecha_evento)::text AS max_fecha,
       count(*) FILTER (WHERE fecha_evento <= (now() - INTERVAL '5 years'))::int AS ge_5y,
       count(*) FILTER (
         WHERE tipo_evento::text IN ('PAQUETE_AAEF_CONSULTADO','VISTA_AAEF_GENERADA','CONTRATO_ACTIVADO')
           AND fecha_evento <= (now() - INTERVAL '10 years')
       )::int AS aaef_ge_10y
FROM modulo7.eventos_integracion;
""")
        stats = (stats_r.stdout or b"").decode("utf-8", "replace")
        log.append("=== STATS ===\n" + stats)
        diag["stats_raw"] = stats
    else:
        log.append(
            "\n[INFO] modulo7.eventos_integracion NO existe en Docker local sgpmp. "
            "La migración RF-102 (94b14a6931d6) no está aplicada en esta BD. "
            "Las estadísticas de retención/hash en vivo se obtienen vía API TEST "
            "(ejecutar_tc_m07_g58.py). No se creó ni migró nada.\n"
        )
        diag["nota"] = (
            "Tabla ausente en Docker local. Evidencia estructural: migración 94b14a6931d6 "
            "y código src/accounting_integration. Datos vivos: API TEST."
        )

    # Functions search even without table
    funcs = psql("""
SELECT n.nspname, p.proname
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='modulo7'
  AND (p.proname ILIKE '%archiv%' OR p.proname ILIKE '%reten%' OR p.proname ILIKE '%evento%integr%')
ORDER BY 1,2;
""")
    funcs_out = (funcs.stdout or b"").decode("utf-8", "replace")
    log.append("=== funciones modulo7 ===\n" + funcs_out)
    diag["funciones_modulo7"] = funcs_out

    diag["viable"] = True
    diag["existe_eventos_integracion_local"] = existe
    OUT_TXT.write_text("\n".join(log), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(diag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "viable": True,
        "existe_eventos_integracion_local": existe,
        "tiene_pg_cron": tiene_cron,
        "salida": str(OUT_TXT),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
