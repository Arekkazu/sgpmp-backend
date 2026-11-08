# | Fecha      | Nombre                   | Que se hizo                                               |
# |------------|--------------------------|-----------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G15 FASE 1: script exploratorio T2 inventario TEST |
"""
Script exploratorio para T2 (TC-M05-G15):
Busca activos viables en TEST via /test-control/query para los escenarios a-h.
Excluye 930, 900, 901, 825.
"""
import os
import sys
import uuid
import json
import requests
from pathlib import Path
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[7]
ENV_PATH = REPO_ROOT / ".env.test"
ENV = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}

def get_env(k: str) -> str:
    v = os.environ.get(k) or ENV.get(k)
    if not v:
        raise RuntimeError(f"Falta variable de entorno: {k}")
    return v

BASE_URL = get_env("TEST_BASE_URL").rstrip("/")
ADMIN_EMAIL = get_env("TEST_ADMIN_EMAIL")
ADMIN_PASSWORD = get_env("TEST_ADMIN_PASSWORD")
SANDBOX_SECRET = get_env("TEST_SANDBOX_SECRET")

EXCLUIDOS = (930, 900, 901, 825)

def run_query(session: requests.Session, sql: str) -> list[dict]:
    r = session.post(f"{BASE_URL}/test-control/query", json={"query": sql}, timeout=45)
    if r.status_code != 200:
        print(f"[ERROR query {r.status_code}]: {r.text[:200]}")
        return []
    return r.json().get("data", [])

def main():
    run_id = f"diag-t2-{uuid.uuid4()}"
    s = requests.Session()
    s.headers.update({
        "X-Test-Run-Id": run_id,
        "X-Sandbox-Secret": SANDBOX_SECRET,
        "X-Zona-Horaria": "America/Bogota",
    })

    print(f"Iniciando exploracion T2 bajo run_id={run_id}...")
    try:
        # 1. Login
        login_resp = s.post(f"{BASE_URL}/sesiones/", json={
            "correo_electronico": ADMIN_EMAIL,
            "contrasena": ADMIN_PASSWORD,
        }, timeout=45)
        if login_resp.status_code != 200:
            print(f"[FAIL] Login status={login_resp.status_code}")
            return
        token = login_resp.json().get("token")
        s.headers["Authorization"] = f"Bearer {token}"
        print("[OK] Login admin exitoso.")

        # 2. Catalogo de estados
        estados = run_query(s, "SELECT id_estado_activo_biologico, nombre FROM modulo2.estados_activos_biologicos ORDER BY id_estado_activo_biologico")
        print("\n--- Catalogo de Estados (modulo2.estados_activos_biologicos) ---")
        for e in estados:
            print(f"ID={e.get('id_estado_activo_biologico')} | Nombre={e.get('nombre')}")

        excl_str = ",".join(str(x) for x in EXCLUIDOS)
        
        # a) INACTIVO (id_estado = 2)
        inactivos = run_query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo, ab.id_estado, est.nombre AS nombre_estado,
                   ab.fecha_inicio_ciclo,
                   (SELECT COUNT(*) FROM modulo2.gestiones_fases gf WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE) AS fases_activas
            FROM modulo2.activos_biologicos ab
            JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = ab.id_estado
            WHERE ab.id_estado = 2 AND ab.id_activo_biologico NOT IN ({excl_str})
            ORDER BY ab.id_activo_biologico
            LIMIT 10
        """)
        print(f"\n--- a) Activos INACTIVOS (id_estado=2) encontrados: {len(inactivos)} ---")
        for a in inactivos:
            print(f"ID={a['id_activo_biologico']} | Tipo={a['tipo']} | Estado={a['nombre_estado']}({a['id_estado']}) | FasesActivas={a['fases_activas']}")

        # b) CERRADO (id_estado = 5)
        cerrados = run_query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo, ab.id_estado, est.nombre AS nombre_estado,
                   ab.fecha_inicio_ciclo,
                   (SELECT COUNT(*) FROM modulo2.gestiones_fases gf WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE) AS fases_activas
            FROM modulo2.activos_biologicos ab
            JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = ab.id_estado
            WHERE ab.id_estado = 5 AND ab.id_activo_biologico NOT IN ({excl_str})
            ORDER BY ab.id_activo_biologico
            LIMIT 10
        """)
        print(f"\n--- b) Activos CERRADOS (id_estado=5) encontrados: {len(cerrados)} ---")
        for a in cerrados:
            print(f"ID={a['id_activo_biologico']} | Tipo={a['tipo']} | Estado={a['nombre_estado']}({a['id_estado']}) | FasesActivas={a['fases_activas']}")

        # c) BAJA (id_estado = 6)
        bajas = run_query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo, ab.id_estado, est.nombre AS nombre_estado,
                   ab.fecha_inicio_ciclo,
                   (SELECT COUNT(*) FROM modulo2.gestiones_fases gf WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE) AS fases_activas
            FROM modulo2.activos_biologicos ab
            JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = ab.id_estado
            WHERE ab.id_estado = 6 AND ab.id_activo_biologico NOT IN ({excl_str})
            ORDER BY ab.id_activo_biologico
            LIMIT 10
        """)
        print(f"\n--- c) Activos BAJA (id_estado=6) encontrados: {len(bajas)} ---")
        for a in bajas:
            print(f"ID={a['id_activo_biologico']} | Tipo={a['tipo']} | Estado={a['nombre_estado']}({a['id_estado']}) | FasesActivas={a['fases_activas']}")

        # d) ACTIVO sin ciclo abierto (id_estado = 1, fases_activas = 0)
        sin_ciclo = run_query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo, ab.id_estado, est.nombre AS nombre_estado,
                   ab.fecha_inicio_ciclo,
                   (SELECT COUNT(*) FROM modulo2.gestiones_fases gf WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE) AS fases_activas
            FROM modulo2.activos_biologicos ab
            JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = ab.id_estado
            WHERE ab.id_estado = 1 AND ab.id_activo_biologico NOT IN ({excl_str})
              AND NOT EXISTS (
                  SELECT 1 FROM modulo2.gestiones_fases gf
                  WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE
              )
            ORDER BY ab.id_activo_biologico
            LIMIT 10
        """)
        print(f"\n--- d) Activos ACTIVO (id_estado=1) SIN ciclo abierto encontrados: {len(sin_ciclo)} ---")
        for a in sin_ciclo:
            print(f"ID={a['id_activo_biologico']} | Tipo={a['tipo']} | Estado={a['nombre_estado']}({a['id_estado']}) | FasesActivas={a['fases_activas']}")

        # e & f) POBLACIONAL ACTIVO con ciclo abierto y cantidad_actual = 0 o NULL
        poblacionales = run_query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo, ab.id_estado, est.nombre AS nombre_estado,
                   dp.cantidad_actual, dp.cantidad_inicial,
                   (SELECT COUNT(*) FROM modulo2.gestiones_fases gf WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE) AS fases_activas
            FROM modulo2.activos_biologicos ab
            JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = ab.id_estado
            LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp ON dp.id_activo_biologico = ab.id_activo_biologico
            WHERE ab.tipo = 'POBLACIONAL' AND ab.id_activo_biologico NOT IN ({excl_str})
            ORDER BY ab.id_activo_biologico
            LIMIT 25
        """)
        print(f"\n--- e/f) Activos POBLACIONALES encontrados: {len(poblacionales)} ---")
        for a in poblacionales:
            print(f"ID={a['id_activo_biologico']} | Tipo={a['tipo']} | Estado={a['nombre_estado']}({a['id_estado']}) | cant_actual={a['cantidad_actual']} | FasesActivas={a['fases_activas']}")

        # g) Id inexistente: verificar 999999999
        inexistente = run_query(s, "SELECT COUNT(*) as c FROM modulo2.activos_biologicos WHERE id_activo_biologico = 999999999")
        print(f"\n--- g) ID 999999999 conteo en BD: {inexistente} ---")

        # h) AISLADO (id_estado = 4)
        aislados = run_query(s, f"""
            SELECT ab.id_activo_biologico, ab.tipo, ab.id_estado, est.nombre AS nombre_estado,
                   (SELECT COUNT(*) FROM modulo2.gestiones_fases gf WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE) AS fases_activas
            FROM modulo2.activos_biologicos ab
            JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = ab.id_estado
            WHERE ab.id_estado = 4 AND ab.id_activo_biologico NOT IN ({excl_str})
            ORDER BY ab.id_activo_biologico
            LIMIT 10
        """)
        print(f"\n--- h) Activos AISLADOS (id_estado=4) encontrados: {len(aislados)} ---")
        for a in aislados:
            print(f"ID={a['id_activo_biologico']} | Tipo={a['tipo']} | Estado={a['nombre_estado']}({a['id_estado']}) | FasesActivas={a['fases_activas']}")

    finally:
        # Teardown
        del_resp = s.delete(f"{BASE_URL}/test-control/runs/{run_id}", headers={
            "X-Sandbox-Secret": SANDBOX_SECRET
        }, timeout=45)
        print(f"\nTeardown sandbox: status={del_resp.status_code}, body={del_resp.text[:100]}")
        s.close()

if __name__ == "__main__":
    main()
