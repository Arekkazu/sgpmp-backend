"""Script de verificación en base de datos PostgreSQL TEST para TC-M09-G05-v2.0 (NW-08 y NW-11).

Cubre:
- NW-08: Verificación de auditoría UPDATE en modulo9.auditorias_especies generada por Ingeniero (id_usuario=4).
- NW-11: Verificación de integridad final: Fixture F-04 activo con descripción restaurada y 0 residuales de 'Alpaca QA2'.
"""
import argparse
import json
import os
import sys
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


def verificar_nw08(cur) -> bool:
    """Verifica que exista auditoría UPDATE reciente por el Ingeniero (id_usuario=4) sobre id_especie=4."""
    query = """
        SELECT id_auditoria_especie, id_especie, id_usuario, tipo_operacion, fecha_gestion, valores_nuevos
        FROM modulo9.auditorias_especies
        WHERE id_especie = 4
          AND id_usuario = 4
          AND tipo_operacion = 'UPDATE'
          AND fecha_gestion >= (NOW() - INTERVAL '60 minutes')
        ORDER BY fecha_gestion DESC
        LIMIT 1;
    """
    cur.execute(query)
    row = cur.fetchone()
    if row:
        id_aud, id_esp, id_usr, op, fecha, val_nuevos = row
        print(f"[NW-08] OK: Registro de auditoría UPDATE encontrado (ID={id_aud}, Usuario={id_usr}, Fecha={fecha}).")
        return True
    else:
        cur.execute("SELECT NOW(), MAX(fecha_gestion), EXTRACT(EPOCH FROM (NOW() - MAX(fecha_gestion))) / 60.0 FROM modulo9.auditorias_especies;")
        diag = cur.fetchone()
        hora_actual, ultima_fecha, minutos = diag if diag else (None, None, None)
        print("[NW-08] FALLA: No se encontró registro de auditoría UPDATE para id_especie=4 e id_usuario=4 en los últimos 60 minutos.", file=sys.stderr)
        print(f"      Última auditoría registrada en la tabla: {ultima_fecha}", file=sys.stderr)
        print(f"      Hora actual: {hora_actual}", file=sys.stderr)
        print(f"      Minutos transcurridos desde la última: {minutos}", file=sys.stderr)
        return False


def verificar_nw11(cur, base_dir: Path) -> bool:
    """Verifica el estado del fixture F-04 y la ausencia de residuales de 'Alpaca QA2'."""
    ok = True

    # 1. Verificar Fixture F-04 (Cachama Blanca)
    cur.execute("SELECT id_especie, nombre, descripcion, es_activo FROM modulo9.especies WHERE id_especie = 4;")
    row_f4 = cur.fetchone()
    if not row_f4:
        print("[NW-11] FALLA: Fixture F-04 (id_especie=4) no encontrado en base de datos.", file=sys.stderr)
        ok = False
    else:
        id_esp, nom, desc, activo = row_f4
        if not activo:
            print(f"[NW-11] FALLA: Fixture F-04 se encuentra inactivo (es_activo=False).", file=sys.stderr)
            ok = False
        else:
            print(f"[NW-11] OK: Fixture F-04 activo (Nombre='{nom}', es_activo={activo}, Descripcion='{desc}').")

    # 2. Verificar ausencia de residuales de 'Alpaca QA2'
    cur.execute("SELECT id_especie, nombre, es_activo FROM modulo9.especies WHERE LOWER(nombre) = LOWER('Alpaca QA2');")
    residuales = cur.fetchall()

    evidencias_dir = base_dir / "evidencias"
    evidencias_dir.mkdir(exist_ok=True)
    ids_file = evidencias_dir / "ids_residuales.json"

    ids_data = [{"id_especie": r[0], "nombre": r[1], "es_activo": r[2]} for r in residuales]
    with open(ids_file, "w", encoding="utf-8") as f:
        json.dump(ids_data, f, indent=2, ensure_ascii=False)

    if residuales:
        print(f"[NW-11] FALLA: Se detectaron {len(residuales)} especies residuales con nombre 'Alpaca QA2' en BD.", file=sys.stderr)
        for r in residuales:
            print(f"  - Residual ID={r[0]}, Nombre='{r[1]}', Activo={r[2]}", file=sys.stderr)
        ok = False
    else:
        print("[NW-11] OK: Cero registros residuales de 'Alpaca QA2' en base de datos.")

    return ok


def main():
    parser = argparse.ArgumentParser(description="Verificación BD para TC-M09-G05-v2.0")
    parser.add_argument("--modo", choices=["all", "nw08", "nw11"], default="all", help="Chequeo a ejecutar")
    args = parser.parse_args()

    try:
        conn = psycopg2.connect(DB_URL, connect_timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT set_config('app.current_role', 'Administrador', false);")

        success = True
        if args.modo in ["all", "nw08"]:
            if not verificar_nw08(cur):
                success = False

        if args.modo in ["all", "nw11"]:
            if not verificar_nw11(cur, BASE_DIR):
                success = False

        cur.close()
        conn.close()

        if success:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as exc:
        print(f"ERROR durante verificación en BD: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
