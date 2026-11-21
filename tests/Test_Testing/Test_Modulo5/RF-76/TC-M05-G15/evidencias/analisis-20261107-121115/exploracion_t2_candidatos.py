# | Fecha      | Nombre                   | Que se hizo                                               |
# |------------|--------------------------|-----------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G15 FASE 1: busqueda exhaustiva de activos T2      |
import os
import uuid
import json
import requests
from pathlib import Path
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[7]
ENV_PATH = REPO_ROOT / ".env.test"
ENV = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}

def get_env(k: str) -> str:
    return os.environ.get(k) or ENV.get(k) or ""

BASE_URL = get_env("TEST_BASE_URL").rstrip("/")
ADMIN_EMAIL = get_env("TEST_ADMIN_EMAIL")
ADMIN_PASSWORD = get_env("TEST_ADMIN_PASSWORD")
SANDBOX_SECRET = get_env("TEST_SANDBOX_SECRET")

EXCLUIDOS = (930, 900, 901, 825)
excl_str = ",".join(str(x) for x in EXCLUIDOS)

def query(s, sql):
    r = s.post(f"{BASE_URL}/test-control/query", json={"query": sql}, timeout=45)
    if r.status_code != 200:
        print(f"Error {r.status_code}: {r.text[:200]}")
        return []
    return r.json().get("data", [])

def main():
    run_id = f"diag-t2-cand-{uuid.uuid4()}"
    s = requests.Session()
    s.headers.update({
        "X-Test-Run-Id": run_id,
        "X-Sandbox-Secret": SANDBOX_SECRET,
        "X-Zona-Horaria": "America/Bogota",
    })
    try:
        r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD}, timeout=45)
        if r.status_code != 200:
            print("Login failed")
            return
        s.headers["Authorization"] = f"Bearer {r.json()['token']}"

        # a) INACTIVOS (id_estado = 2)
        print("\n--- a) Activos INACTIVOS (id_estado = 2) ---")
        res_a = query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo::text AS tipo, ab.id_estado, ab.fecha_inicio_ciclo
            FROM modulo2.activos_biologicos ab
            WHERE ab.id_estado = 2 AND ab.id_activo_biologico NOT IN ({excl_str})
            ORDER BY ab.id_activo_biologico LIMIT 5
        """)
        for row in res_a:
            print(row)

        # b) CERRADOS (id_estado = 5)
        print("\n--- b) Activos CERRADOS (id_estado = 5) ---")
        res_b = query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo::text AS tipo, ab.id_estado, ab.fecha_inicio_ciclo
            FROM modulo2.activos_biologicos ab
            WHERE ab.id_estado = 5 AND ab.id_activo_biologico NOT IN ({excl_str})
            ORDER BY ab.id_activo_biologico LIMIT 5
        """)
        for row in res_b:
            print(row)

        # c) BAJA (id_estado = 6)
        print("\n--- c) Activos BAJA (id_estado = 6) ---")
        res_c = query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo::text AS tipo, ab.id_estado, ab.fecha_inicio_ciclo
            FROM modulo2.activos_biologicos ab
            WHERE ab.id_estado = 6 AND ab.id_activo_biologico NOT IN ({excl_str})
            ORDER BY ab.id_activo_biologico LIMIT 5
        """)
        for row in res_c:
            print(row)

        # d) ACTIVO sin ciclo abierto (id_estado = 1, sin fase activa)
        print("\n--- d) Activos ACTIVO (id_estado = 1) sin ciclo abierto ---")
        res_d = query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo::text AS tipo, ab.id_estado, ab.fecha_inicio_ciclo
            FROM modulo2.activos_biologicos ab
            WHERE ab.id_estado = 1 AND ab.id_activo_biologico NOT IN ({excl_str})
              AND NOT EXISTS (
                  SELECT 1 FROM modulo2.gestiones_fases gf
                  WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE
              )
            ORDER BY ab.id_activo_biologico LIMIT 5
        """)
        for row in res_d:
            print(row)

        # e & f) POBLACIONALES
        print("\n--- e/f) Activos POBLACIONALES con cantidad_actual y ciclo abierto ---")
        res_ef = query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo::text AS tipo, ab.id_estado,
                   dp.cantidad_actual, dp.cantidad_inicial,
                   (SELECT COUNT(*) FROM modulo2.gestiones_fases gf WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE) AS fases_activas
            FROM modulo2.activos_biologicos ab
            LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp ON dp.id_activo_biologico = ab.id_activo_biologico
            WHERE ab.tipo::text = 'POBLACIONAL' AND ab.id_activo_biologico NOT IN ({excl_str})
            ORDER BY ab.id_activo_biologico LIMIT 20
        """)
        for row in res_ef:
            print(row)

        # Buscar especificamente si hay POBLACIONAL con cantidad_actual = 0 o NULL
        print("\n--- e) POBLACIONAL con cantidad_actual = 0 ---")
        res_e0 = query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo::text AS tipo, ab.id_estado, dp.cantidad_actual,
                   (SELECT COUNT(*) FROM modulo2.gestiones_fases gf WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE) AS fases_activas
            FROM modulo2.activos_biologicos ab
            LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp ON dp.id_activo_biologico = ab.id_activo_biologico
            WHERE ab.tipo::text = 'POBLACIONAL' AND dp.cantidad_actual = 0 AND ab.id_activo_biologico NOT IN ({excl_str})
        """)
        print("cantidad_actual = 0:", res_e0)

        print("\n--- f) POBLACIONAL con cantidad_actual IS NULL ---")
        res_enull = query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo::text AS tipo, ab.id_estado, dp.cantidad_actual,
                   (SELECT COUNT(*) FROM modulo2.gestiones_fases gf WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE) AS fases_activas
            FROM modulo2.activos_biologicos ab
            LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp ON dp.id_activo_biologico = ab.id_activo_biologico
            WHERE ab.tipo::text = 'POBLACIONAL' AND dp.cantidad_actual IS NULL AND ab.id_activo_biologico NOT IN ({excl_str})
        """)
        print("cantidad_actual IS NULL:", res_enull)

        # h) AISLADOS (id_estado = 4)
        print("\n--- h) Activos AISLADOS (id_estado = 4) ---")
        res_h = query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo::text AS tipo, ab.id_estado, ab.fecha_inicio_ciclo
            FROM modulo2.activos_biologicos ab
            WHERE ab.id_estado = 4 AND ab.id_activo_biologico NOT IN ({excl_str})
            ORDER BY ab.id_activo_biologico LIMIT 5
        """)
        for row in res_h:
            print(row)

    finally:
        s.delete(f"{BASE_URL}/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": SANDBOX_SECRET}, timeout=45)
        s.close()

if __name__ == "__main__":
    main()

