"""Script de verificación de integridad y teardown en base de datos PostgreSQL TEST (NW-13).

Verifica que ningún registro de prueba permanezca en estado activo ('es_activo = true')
y exporta los IDs desactivados a 'evidencias/ids_residuales.json'.
"""
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

NOMBRES_TEST = [
    "Oca",
    "Especie Cincuenta Caracteres Letras Puras Abcdefgh",
    "Qa",
    "Especie Cincuenta Caracteres Letras Puras Abcdefghi",
    "Trucha@QA2#",
]

try:
    conn = psycopg2.connect(DB_URL, connect_timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.current_role', 'Administrador', false);")

    ids_residuales = []
    especies_activas_indebidas = []

    for nombre in NOMBRES_TEST:
        cur.execute(
            "SELECT id_especie, nombre, es_activo FROM modulo9.especies WHERE LOWER(nombre) = LOWER(%s);",
            (nombre,),
        )
        filas = cur.fetchall()
        for id_esp, nom, activo in filas:
            ids_residuales.append({
                "id_especie": id_esp,
                "nombre": nom,
                "es_activo": activo,
            })
            if activo:
                especies_activas_indebidas.append((id_esp, nom))

    cur.close()
    conn.close()

    # Guardar IDs residuales a evidencias
    evidencias_dir = BASE_DIR / "evidencias"
    evidencias_dir.mkdir(exist_ok=True)
    ids_file = evidencias_dir / "ids_residuales.json"
    with open(ids_file, "w", encoding="utf-8") as f:
        json.dump(ids_residuales, f, indent=2, ensure_ascii=False)

    print(f"Verificación BD completada. Total registros residuales registrados: {len(ids_residuales)}")
    if especies_activas_indebidas:
        print(f"FALLA: Se encontraron {len(especies_activas_indebidas)} especies activas indebidas:", file=sys.stderr)
        for id_esp, nom in especies_activas_indebidas:
            print(f"  - ID: {id_esp}, Nombre: '{nom}'", file=sys.stderr)
        sys.exit(1)
    else:
        print("OK: Cero especies de prueba permanecen activas en base de datos.")
        sys.exit(0)

except Exception as exc:
    print(f"ERROR durante verificación en BD: {exc}", file=sys.stderr)
    sys.exit(1)
