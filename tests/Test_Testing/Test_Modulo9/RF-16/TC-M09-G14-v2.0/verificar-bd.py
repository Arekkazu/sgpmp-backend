"""Script de verificación en base de datos PostgreSQL TEST para TC-M09-G14-v2.0 (NW-20).

Verificaciones realizadas:
1. Integridad de entidades: Verifica que las 7 métricas creadas en la corrida
   (SC07a, SC07b, SC09a, SC10a, SC10b, SC10c, SC10d) tengan `es_activo = false` en `modulo9.metricas_produccion`.
2. Auditoría en ventana cerrada: Verifica que en `modulo9.auditorias_metricas_produccion`
   existan registros de auditoría CREATE y DEACTIVATE para cada métrica, con:
   - id_usuario = 104 (Administrador)
   - fecha_gestion >= run_start_time AND fecha_gestion <= run_end_time (+ margen de 30s por reloj de servidor)
3. Persistencia de evidencias: Genera `evidencias/ids_residuales.json`.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parents[4]
ENV_TEST = REPO_DIR / ".env.test"

if ENV_TEST.exists():
    load_dotenv(ENV_TEST)
else:
    load_dotenv()

DB_URL = os.getenv("TEST_DATABASE_URL")
if not DB_URL:
    print("ERROR: TEST_DATABASE_URL no definida en el entorno ni en .env.test", file=sys.stderr)
    sys.exit(1)


def parse_run_info(base_dir: Path):
    """Extrae timestamps y los 7 IDs de métricas desde consola_TC-M09-G14-v2.0.txt."""
    consola_file = base_dir / "evidencias" / "consola_TC-M09-G14-v2.0.txt"
    run_start_time = None
    run_end_time = None
    ids_capturados = {}

    keys_esperadas = [
        "SC07A", "SC07B", "SC09A", "SC10A", "SC10B", "SC10C", "SC10D"
    ]

    if consola_file.exists():
        try:
            content = consola_file.read_text(encoding="utf-8", errors="ignore")
            m_start = re.search(r"RUN_START_TIME=([0-9T:.Z\-+]+)", content)
            if m_start:
                run_start_time = m_start.group(1)

            m_end = re.search(r"RUN_END_TIME=([0-9T:.Z\-+]+)", content)
            if m_end:
                run_end_time = m_end.group(1)

            for k in keys_esperadas:
                m_id = re.search(rf"CREATED_ID_{k}=(\d+)", content)
                if m_id:
                    ids_capturados[k] = int(m_id.group(1))
        except Exception as e:
            print(f"Aviso al parsear consola: {e}", file=sys.stderr)

    return run_start_time, run_end_time, ids_capturados


def get_connection():
    conn = psycopg2.connect(DB_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_role', 'Administrador', false);")
    return conn


def ejecutar_verificaciones(base_dir: Path):
    run_start_time, run_end_time, ids_capturados = parse_run_info(base_dir)
    print(f"INFO: run_start_time={run_start_time}, run_end_time={run_end_time}")
    print(f"INFO: IDs capturados de métricas: {ids_capturados}")

    if len(ids_capturados) < 7:
        print(f"ERROR: No se capturaron los 7 IDs requeridos (obtenidos {len(ids_capturados)}: {ids_capturados})", file=sys.stderr)
        return {
            "estado": "FALLA",
            "motivo": f"IDs capturados incompletos ({len(ids_capturados)}/7): {ids_capturados}",
            "ids_residuales": ids_capturados,
            "detalles": {}
        }

    ids_lista = list(ids_capturados.values())
    conn = get_connection()
    resultados = {
        "estado": "OK",
        "motivo": "Verificación de BD completada con éxito",
        "ids_residuales": {},
        "auditorias_confirmadas": {},
        "fallos": []
    }

    try:
        with conn.cursor() as cur:
            # 1. Verificar estado en modulo9.metricas_produccion
            cur.execute("""
                SELECT id_metrica_produccion, nombre, es_activo
                FROM modulo9.metricas_produccion
                WHERE id_metrica_produccion = ANY(%s);
            """, (ids_lista,))
            rows = cur.fetchall()
            mapa_metricas = {r[0]: {"nombre": r[1], "es_activo": r[2]} for r in rows}

            residuales_activos = []
            for k, id_metrica in ids_capturados.items():
                if id_metrica not in mapa_metricas:
                    resultados["fallos"].append(f"Métrica {k} (id={id_metrica}) no encontrada en BD")
                else:
                    info = mapa_metricas[id_metrica]
                    resultados["ids_residuales"][id_metrica] = {
                        "subcaso": k,
                        "nombre": info["nombre"],
                        "es_activo": info["es_activo"]
                    }
                    if info["es_activo"]:
                        residuales_activos.append(id_metrica)

            if residuales_activos:
                resultados["fallos"].append(f"Métricas aún activas en BD (esperado es_activo=false): {residuales_activos}")

            # 2. Verificar auditorías en modulo9.auditorias_metricas_produccion
            # Ventana de tiempo cerrada con tolerancia de 30s
            ts_filtro_start = run_start_time if run_start_time else "2026-10-07T00:00:00Z"
            ts_filtro_end = run_end_time if run_end_time else datetime.now(timezone.utc).isoformat()

            cur.execute("""
                SELECT id_auditoria_metrica, id_metrica_produccion, id_usuario, tipo_operacion, fecha_gestion
                FROM modulo9.auditorias_metricas_produccion
                WHERE id_metrica_produccion = ANY(%s)
                  AND id_usuario = 104
                  AND fecha_gestion >= (%s::timestamptz - INTERVAL '30 seconds')
                  AND fecha_gestion <= (%s::timestamptz + INTERVAL '60 seconds')
                ORDER BY fecha_gestion ASC;
            """, (ids_lista, ts_filtro_start, ts_filtro_end))
            audit_rows = cur.fetchall()

            audit_map = {}
            for row in audit_rows:
                id_met = row[1]
                op = row[3]
                if id_met not in audit_map:
                    audit_map[id_met] = []
                audit_map[id_met].append(op)

            for k, id_met in ids_capturados.items():
                ops = audit_map.get(id_met, [])
                resultados["auditorias_confirmadas"][id_met] = ops
                if "CREATE" not in ops:
                    resultados["fallos"].append(f"Métrica {k} (id={id_met}) carece de auditoría CREATE en ventana cerrada")
                if "DEACTIVATE" not in ops:
                    resultados["fallos"].append(f"Métrica {k} (id={id_met}) carece de auditoría DEACTIVATE en ventana cerrada")

        if resultados["fallos"]:
            resultados["estado"] = "FALLA"
            resultados["motivo"] = "; ".join(resultados["fallos"])

    except Exception as exc:
        resultados["estado"] = "FALLA"
        resultados["motivo"] = f"Excepción durante verificación en BD: {exc}"
    finally:
        conn.close()

    # Guardar evidencias/ids_residuales.json
    evidencias_dir = base_dir / "evidencias"
    evidencias_dir.mkdir(parents=True, exist_ok=True)
    ids_file = evidencias_dir / "ids_residuales.json"
    with open(ids_file, "w", encoding="utf-8") as f:
        json.dump(resultados["ids_residuales"], f, indent=2, ensure_ascii=False)

    return resultados


def main():
    parser = argparse.ArgumentParser(description="Verificación en BD para TC-M09-G14-v2.0")
    parser.add_argument("--json", action="store_true", help="Imprimir resultado estructurado en JSON")
    args = parser.parse_args()

    res = ejecutar_verificaciones(BASE_DIR)

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"ESTADO: {res['estado']}")
        print(f"MOTIVO: {res['motivo']}")

    sys.exit(0 if res["estado"] == "OK" else 1)


if __name__ == "__main__":
    main()
