# | Fecha      | Nombre                   | Que se hizo                                               |
# |------------|--------------------------|-----------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G15 FASE 1: prueba escenario 462 cantidad NULL     |
import requests, uuid, time
from datetime import datetime, timezone, timedelta
from dotenv import dotenv_values

env = dotenv_values(".env.test")
BASE_URL = env["TEST_BASE_URL"].rstrip("/")
ADMIN_EMAIL = env["TEST_ADMIN_EMAIL"]
ADMIN_PASSWORD = env["TEST_ADMIN_PASSWORD"]
SANDBOX_SECRET = env["TEST_SANDBOX_SECRET"]

ZONA_BOGOTA = timezone(timedelta(hours=-5))
hoy_bogota = datetime.now(ZONA_BOGOTA).date().isoformat()

run_id = f"tc-m05-g15-t4-pob462-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({
    "X-Test-Run-Id": run_id,
    "X-Sandbox-Secret": SANDBOX_SECRET,
    "X-Zona-Horaria": "America/Bogota",
})

print(f"=== Probando Escenario 7: POBLACIONAL cantidad NULL [Activo 462] ===")
try:
    r_login = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD}, timeout=45)
    s.headers["Authorization"] = f"Bearer {r_login.json()['token']}"
    
    # 1. Abrir fase en 462
    r_fase = s.post(f"{BASE_URL}/activos-biologicos/462/fases", json={
        "id_ciclo_productiva": 4,
        "motivo_cambio": "TC-M05-G15: apertura fase sandbox para probar POBLACIONAL cantidad NULL",
    })
    print(f"Apertura fase 462: HTTP {r_fase.status_code}")
    assert r_fase.status_code == 201

    # 2. Conteo base medicamentos
    r_conteo = s.get(f"{BASE_URL}/suministros/medicamentos?id_activo_biologico=462")
    c_base = r_conteo.json().get("total")
    print(f"Conteo base 462: {c_base}")

    # 3. POST /suministros/medicamentos
    payload = {
        "id_activo_biologico": 462,
        "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": hoy_bogota,
        "hora_aplicacion": "10:30",
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": 100,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": "Tratamiento de infección respiratoria",
        "costo_unitario": 500,
        "nombre_veterinario": "Dr. Pérez",
    }
    r_post = s.post(f"{BASE_URL}/suministros/medicamentos", json=payload)
    print(f"[RESPUESTA POST 462] HTTP {r_post.status_code}")
    print(f"Body: {r_post.json()}")

    # 4. Conteo en sandbox
    r_conteo_sb = s.get(f"{BASE_URL}/suministros/medicamentos?id_activo_biologico=462")
    print(f"Conteo en sandbox: {r_conteo_sb.json().get('total')} (base: {c_base})")

finally:
    del_r = s.delete(f"{BASE_URL}/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": SANDBOX_SECRET})
    print(f"Teardown: HTTP {del_r.status_code}")
    s.close()

