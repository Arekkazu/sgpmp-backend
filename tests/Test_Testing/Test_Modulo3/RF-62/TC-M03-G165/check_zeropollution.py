import requests
import json

admin_token = requests.post("https://api.inmero.co/api-sgpmp-test/sesiones/", json={"email": "admin@sgpmp.com", "clave": "Admin123*"}).json()["access_token"]
run_res = requests.post("https://api.inmero.co/api-sgpmp-test/test-control/runs", headers={"Authorization": f"Bearer {admin_token}"}).json()
run_id = run_res["run_id"]
headers = {"Authorization": f"Bearer {admin_token}", "X-Test-Run-Id": run_id}

c_tel = requests.post("https://api.inmero.co/api-sgpmp-test/test-control/query", headers=headers, json={"query": "SELECT COUNT(id) as c FROM modulo3.telemetrias;"}).json()["rows"][0]["c"]
c_cal = requests.post("https://api.inmero.co/api-sgpmp-test/test-control/query", headers=headers, json={"query": "SELECT COUNT(id) as c FROM modulo3.telemetria_calidad;"}).json()["rows"][0]["c"]
c_bit = requests.post("https://api.inmero.co/api-sgpmp-test/test-control/query", headers=headers, json={"query": "SELECT COUNT(id) as c FROM modulo3.bitacora_auditoria_iot;"}).json()["rows"][0]["c"]

requests.delete(f"https://api.inmero.co/api-sgpmp-test/test-control/runs/{run_id}", headers={"Authorization": f"Bearer {admin_token}"})

with open("tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G165/baseline_g165.json") as f:
    base = json.load(f)

print(f"BASELINE: {base}")
print(f"POST-RUN: telemetrias={c_tel}, calidad={c_cal}, bitacora={c_bit}")
diff = (c_tel - base["telemetrias"]) + (c_cal - base["telemetria_calidad"]) + (c_bit - base["bitacora_auditoria_iot"])
print(f"DIFF: {diff}")
