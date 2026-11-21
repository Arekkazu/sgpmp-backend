"""Script de restauracion de fincas originales del Veterinario (id 97).
Ejecutado fuera de sandbox con credenciales de Administrador (login nuevo).
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

# 2. Login Admin NUEVO
s = requests.Session()
r_login = s.post(f"{base_url}/sesiones/", json={"correo_electronico": admin_email, "contrasena": admin_pass})
assert r_login.status_code == 200, f"Error en login admin: {r_login.status_code}"
token = r_login.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

# 3. Leer lista original registrada
reg_path = Path("tests/Test_Testing/Test_Modulo5/RF-76/TC-M05-G19/evidencias/registro_asignacion_fincas.json")
if reg_path.exists():
    reg_data = json.loads(reg_path.read_text(encoding="utf-8"))
    fincas_originales = reg_data.get("fincas_antes", [84, 184])
else:
    fincas_originales = [84, 184]

hora_inicio = datetime.now(timezone.utc).isoformat()
print(f"[RESTAURAR] Hora inicio: {hora_inicio}")
print(f"[RESTAURAR] Restaurando lista original exacta: {sorted(fincas_originales)}")

# 4. PUT /usuarios/97/fincas con lista original exacta
r_put = s.put(f"{base_url}/usuarios/97/fincas", headers=headers, json={"ids_fincas": sorted(fincas_originales)})
print(f"[RESTAURAR] PUT status: {r_put.status_code}, response: {r_put.text}")
assert r_put.status_code == 200, f"Error en PUT restauracion: {r_put.status_code} {r_put.text}"

# 5. Verificacion por lectura con Veterinario (/usuarios/me)
s_vet = requests.Session()
r_vlogin = s_vet.post(f"{base_url}/sesiones/", json={"correo_electronico": env["TEST_VET_EMAIL"], "contrasena": env["TEST_VET_PASSWORD"]})
assert r_vlogin.status_code == 200
v_token = r_vlogin.json()["token"]
r_me = s_vet.get(f"{base_url}/usuarios/me", headers={"Authorization": f"Bearer {v_token}"})
assert r_me.status_code == 200
fincas_actuales = [f["id_finca"] for f in r_me.json().get("fincas", [])]
hora_fin = datetime.now(timezone.utc).isoformat()

print(f"[RESTAURAR] Hora fin: {hora_fin}")
print(f"[RESTAURAR] Lista VERIFICADA fincas usuario 97: {sorted(fincas_actuales)}")
assert sorted(fincas_actuales) == sorted(fincas_originales), (
    f"ERROR: Fincas restauradas {sorted(fincas_actuales)} no coinciden con originales {sorted(fincas_originales)}"
)

# Guardar registro para informe
registro_restauracion = {
    "operacion": "RESTAURACION_FINAL",
    "hora_inicio": hora_inicio,
    "hora_fin": hora_fin,
    "fincas_originales": sorted(fincas_originales),
    "fincas_restauradas": sorted(fincas_actuales),
    "coincide": True,
}
Path("tests/Test_Testing/Test_Modulo5/RF-76/TC-M05-G19/evidencias/registro_restauracion_fincas.json").write_text(
    json.dumps(registro_restauracion, indent=2), encoding="utf-8"
)
print("[RESTAURAR] Exito total en restauracion de fincas")
