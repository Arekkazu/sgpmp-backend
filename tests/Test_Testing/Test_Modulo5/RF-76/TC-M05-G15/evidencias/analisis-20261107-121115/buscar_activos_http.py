# | Fecha      | Nombre                   | Que se hizo                                               |
# |------------|--------------------------|-----------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G15 FASE 1: busqueda HTTP de activos viables       |
import os
import uuid
import requests
from dotenv import dotenv_values

env = dotenv_values(".env.test")
BASE_URL = env["TEST_BASE_URL"].rstrip("/")
ADMIN_EMAIL = env["TEST_ADMIN_EMAIL"]
ADMIN_PASSWORD = env["TEST_ADMIN_PASSWORD"]
SANDBOX_SECRET = env["TEST_SANDBOX_SECRET"]

EXCLUIDOS = (930, 900, 901, 825)

run_id = f"diag-http-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": SANDBOX_SECRET, "X-Zona-Horaria": "America/Bogota"})
r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD}, timeout=45)
s.headers["Authorization"] = f"Bearer {r.json()['token']}"

try:
    # 1. Estados 2, 4, 5, 6
    for st_id, st_name in [(2, "INACTIVO"), (4, "AISLADO"), (5, "CERRADO"), (6, "BAJA")]:
        resp = s.get(f"{BASE_URL}/activos-biologicos?id_estado={st_id}&page_size=10")
        registros = resp.json().get("registros", []) if resp.status_code == 200 else []
        validos = [x for x in registros if x.get("id_activo_biologico") not in EXCLUIDOS]
        print(f"\n--- Estado {st_name} ({st_id}): total={resp.json().get('total_registros')} ---")
        for v in validos[:5]:
            print(f"ID={v['id_activo_biologico']} | Tipo={v['tipo']} | Estado={v['nombre_estado']}({v['id_estado']})")

    # 2. Poblacionales activos
    resp_pob = s.get(f"{BASE_URL}/activos-biologicos?tipo=POBLACIONAL&page_size=50")
    regs_pob = resp_pob.json().get("registros", []) if resp_pob.status_code == 200 else []
    print(f"\n--- POBLACIONALES: total={resp_pob.json().get('total_registros')} ---")
    for p in regs_pob:
        aid = p["id_activo_biologico"]
        if aid in EXCLUIDOS:
            continue
        # Consultar detalle del activo
        det_r = s.get(f"{BASE_URL}/activos-biologicos/{aid}")
        det = det_r.json() if det_r.status_code == 200 else {}
        dp = det.get("detalle_poblacional") or {}
        cant = dp.get("cantidad_actual")
        # Consultar fases
        fases_r = s.get(f"{BASE_URL}/activos-biologicos/{aid}/fases")
        fases = fases_r.json().get("fases", []) if fases_r.status_code == 200 else []
        activas = [f for f in fases if f.get("es_activa")]
        print(f"POBLACIONAL ID={aid} | Estado={p.get('nombre_estado')}({p.get('id_estado')}) | cant_actual={cant} | FasesActivas={len(activas)}")

finally:
    s.delete(f"{BASE_URL}/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": SANDBOX_SECRET}, timeout=45)
    s.close()

