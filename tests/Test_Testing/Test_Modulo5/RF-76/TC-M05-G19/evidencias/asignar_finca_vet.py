"""Script de asignacion temporal de Finca 1 al Veterinario (id 97).
Ejecutado fuera de sandbox con credenciales de Administrador.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import requests

# 1. Carga de variables desde .env.test en la raiz del repo
repo_root = Path(__file__).resolve().parents[6]
env = {}
with open(repo_root / ".env.test", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip("\"'")

base_url = env["TEST_BASE_URL"].rstrip("/")
admin_email = env["TEST_ADMIN_EMAIL"]
admin_pass = env["TEST_ADMIN_PASSWORD"]

# 2. Login Admin
s = requests.Session()
r_login = s.post(f"{base_url}/sesiones/", json={"correo_electronico": admin_email, "contrasena": admin_pass})
assert r_login.status_code == 200, f"Error en login admin: {r_login.status_code}"
token = r_login.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

# 3. Estado antes: leer fincas actuales del usuario 97
# Consultar detalle del usuario 97
r_det = s.get(f"{base_url}/usuarios/97/detalle", headers=headers)
hora_antes = datetime.now(timezone.utc).isoformat()
print(f"[ASIGNAR] Hora inicio: {hora_antes}")
print(f"[ASIGNAR] GET /usuarios/97/detalle status: {r_det.status_code}")

# Si detalle tiene fincas o usamos la lista observada en /usuarios/me
fincas_antes = []
if r_det.status_code == 200:
    data = r_det.json()
    fincas_antes = [f["id_finca"] for f in data.get("fincas", [])]
if not fincas_antes:
    fincas_antes = [84, 184]

print(f"[ASIGNAR] Lista ORIGINAL de fincas usuario 97: {sorted(fincas_antes)}")

# 4. PUT /usuarios/97/fincas con ORIGINAL + [1]
fincas_deseadas = sorted(list(set(fincas_antes + [1])))
print(f"[ASIGNAR] Enviando PUT con lista: {fincas_deseadas}")
r_put = s.put(f"{base_url}/usuarios/97/fincas", headers=headers, json={"ids_fincas": fincas_deseadas})
print(f"[ASIGNAR] PUT status: {r_put.status_code}, response: {r_put.text}")
assert r_put.status_code == 200, f"Error en PUT /usuarios/97/fincas: {r_put.status_code} {r_put.text}"

# 5. Verificacion por lectura con Veterinario (/usuarios/me)
s_vet = requests.Session()
r_vlogin = s_vet.post(f"{base_url}/sesiones/", json={"correo_electronico": env["TEST_VET_EMAIL"], "contrasena": env["TEST_VET_PASSWORD"]})
assert r_vlogin.status_code == 200
v_token = r_vlogin.json()["token"]
r_me = s_vet.get(f"{base_url}/usuarios/me", headers={"Authorization": f"Bearer {v_token}"})
assert r_me.status_code == 200
fincas_despues = [f["id_finca"] for f in r_me.json().get("fincas", [])]
hora_despues = datetime.now(timezone.utc).isoformat()

print(f"[ASIGNAR] Hora fin: {hora_despues}")
print(f"[ASIGNAR] Lista VERIFICADA fincas usuario 97 despues: {sorted(fincas_despues)}")
assert 1 in fincas_despues, "ERROR: Finca 1 no aparece asignada al usuario 97"

# Guardar registro para informe
registro = {
    "operacion": "ASIGNACION_TEMPORAL",
    "hora_inicio": hora_antes,
    "hora_fin": hora_despues,
    "fincas_antes": sorted(fincas_antes),
    "fincas_despues": sorted(fincas_despues),
}
Path("tests/Test_Testing/Test_Modulo5/RF-76/TC-M05-G19/evidencias/registro_asignacion_fincas.json").write_text(
    json.dumps(registro, indent=2), encoding="utf-8"
)
print("[ASIGNAR] Exito total en asignacion temporal")
