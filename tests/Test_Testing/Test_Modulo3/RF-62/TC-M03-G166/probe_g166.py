# probe_g166.py - FASE FINAL: seed SQL directo + evaluacion (sin broker MQTT)
# No depende de POST /iot/telemetria (bloqueado por TOKEN_SERVICIO_NO_CONFIGURADO)
import os, sys, uuid, json, time, requests
from datetime import datetime, timezone, timedelta
from decimal import Decimal

BASE   = "https://www.api.inmero.co/api-sgpmp-test"
SECRET = "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff"
EMAIL  = "administador.dev@gmail.com"
PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD")
if not PASSWORD:
    sys.exit("Falta TEST_ADMIN_PASSWORD en el entorno")

SENSOR_ID       = 2      # fallback confirmado: solo 1 lectura de 2024
ID_VARIABLE     = 9      # TEMPERATURA_AMBIENTAL (catalogo I3P-1)
ID_DISPOSITIVO  = 1      # device de sensor 2
UNIDAD          = "\u00b0C"   # °C
CATEGORIA       = "AMBIENTAL"

RUN_ID  = f"probe-g166-{uuid.uuid4().hex[:12]}"
HDRS    = {"X-Test-Run-Id": RUN_ID, "X-Sandbox-Secret": SECRET}
TOKEN   = None

def h(extra=None):
    base = {**HDRS}
    if TOKEN:
        base["Authorization"] = f"Bearer {TOKEN}"
    if extra:
        base.update(extra)
    return base

def show(label, r, trunc=1500):
    dur_ms = int(r.elapsed.total_seconds() * 1000)
    print(f"\n--- {label} ---")
    print(f"HTTP {r.status_code} ({dur_ms} ms)")
    try:
        print(json.dumps(r.json(), indent=2, default=str)[:trunc])
    except Exception:
        print(r.text[:trunc])
    return r

def query(sql, timeout=60):
    return requests.post(f"{BASE}/test-control/query", headers=h(),
                         json={"query": sql}, timeout=timeout)

def main():
    global TOKEN
    print(f"RUN_ID = {RUN_ID}")
    print(f"BASE   = {BASE}")

    # 1. Health
    show("GET /health", requests.get(f"{BASE}/health", headers=HDRS, timeout=15))

    # 2. Login (UN solo POST /sesiones/)
    r = requests.post(f"{BASE}/sesiones/", headers=HDRS, json={
        "correo_electronico": EMAIL, "contrasena": PASSWORD,
    }, timeout=30)
    show("POST /sesiones/", r, trunc=300)
    if r.status_code != 200:
        print("!! Login fallo"); return
    TOKEN = r.json().get("token") or r.json().get("access_token")
    print(f"TOKEN len={len(TOKEN or '')}")

    # 3. Preflight: contar lecturas previas sensor 2
    r_prev = query(f"SELECT COUNT(*) AS n FROM modulo3.telemetrias WHERE id_sensor = {SENSOR_ID}")
    show("preflight count", r_prev, trunc=500)

    # 4. Generar 41 lecturas (20 distintas + 21 identicas)
    base_ts  = datetime.now(timezone.utc) - timedelta(minutes=70)
    ts_proc  = datetime.now(timezone.utc).isoformat()
    base_val = Decimal("25.40")

    values_lines = []
    for i in range(41):
        if i < 20:
            valor = base_val + Decimal(f"{(i-10)*0.01}")
        else:
            valor = base_val
        ts = (base_ts + timedelta(minutes=10*i)).isoformat()
        values_lines.append(
            f"({SENSOR_ID}, {ID_VARIABLE}, {ID_DISPOSITIVO}, "
            f"{valor}, {valor}, "
            f"'{ts}'::timestamptz, '{ts_proc}'::timestamptz, "
            f"'TIEMPO_REAL', 'LECTURA_VALIDA', true, "
            f"'{{}}'::jsonb, '{CATEGORIA}', '{UNIDAD}', "
            f"'v1-sandbox', '{{\"ganancia\":\"1\",\"offset\":\"0\"}}'::jsonb, "
            f"false, 10, 'CRUDO')"
        )
    values_sql = ",\n".join(values_lines)

    # 5. INSERT via CTE (compatible con wrapper SELECT * FROM (...))
    sql_insert = f"""
WITH ins AS (
  INSERT INTO modulo3.telemetrias
    (id_sensor, id_variable, id_dispositivo_iot, valor_crudo, valor_ajustado,
     timestamp_captura, timestamp_procesamiento, origen, estado_calidad,
     calibrado, metadatos, categoria_variable, unidad_medida,
     version_calibracion, parametros_calibracion, valor_agregado,
     frecuencia_muestreo_min, tipo_dato)
  VALUES
{values_sql}
  RETURNING id_telemetria, timestamp_captura
)
SELECT id_telemetria, timestamp_captura FROM ins
ORDER BY timestamp_captura DESC LIMIT 5
"""

    print("\n--- INSERT 41 lecturas ---")
    t0 = time.time()
    r_ins = query(sql_insert, timeout=90)
    print(f"duracion: {int((time.time()-t0)*1000)} ms")
    show("INSERT resultado", r_ins, trunc=2000)

    id_ultima = None
    if r_ins.status_code == 200:
        data = r_ins.json().get("data", [])
        if data:
            id_ultima = data[0]["id_telemetria"]
            print(f"id_ultima (mas reciente) = {id_ultima}")

    if not id_ultima:
        print("\n!! INSERT fallo o no devolvio id. Detener.")
        return

    # 6. Verificar cuantas filas hay ahora para sensor 2 + variable 9
    r_cnt = query(
        f"SELECT COUNT(*) AS n FROM modulo3.telemetrias "
        f"WHERE id_sensor = {SENSOR_ID} AND id_variable = {ID_VARIABLE}")
    show("count post-insert", r_cnt, trunc=500)

    # 7. POST evaluar
    print(f"\n=== POST /iot/calidad/{id_ultima}/evaluar ===")
    r_eval = requests.post(f"{BASE}/iot/calidad/{id_ultima}/evaluar",
                           headers=h(), timeout=90)
    show("POST evaluar", r_eval, trunc=3000)

    # 8. GET verificacion
    if r_eval.status_code in (200, 201):
        print(f"\n=== GET /iot/calidad/{id_ultima} ===")
        r_ver = requests.get(f"{BASE}/iot/calidad/{id_ultima}",
                             headers=h(), timeout=30)
        show("GET calidad", r_ver, trunc=3000)

        print("\n--- VEREDICTO CONTRACTUAL ---")
        print("  Esperado para R=21 (consecutivas 25.40 al final):")
        print("    clasificacion_calidad = NO_APTO")
        print("    indice_calidad        = 10")
        print("    apto_para_ia          = False")
        print("    apto_para_nic41       = False")
        print("    sensor_congelado.severidad = CRITICO")
        print("    sensor_congelado.activo = True")
        try:
            d = r_ver.json()
            print("\n  Obtenido:")
            for k in ("clasificacion_calidad", "indice_calidad",
                      "apto_para_ia", "apto_para_nic41"):
                print(f"    {k:22s} = {d.get(k)}")
            flags = d.get("flags") or {}
            sc = flags.get("sensor_congelado") or {}
            print(f"    sensor_congelado      = {sc}")
        except Exception as e:
            print(f"  No se pudo parsear: {e}")

        # 9. Invariante: una sola VIGENTE
        r_vig = query(
            f"SELECT COUNT(*) AS n FROM modulo3.telemetria_calidad "
            f"WHERE id_telemetria = {id_ultima} "
            f"AND estado_evaluacion = 'VIGENTE'")
        show("VIGENTE count", r_vig, trunc=500)

if __name__ == "__main__":
    try:
        main()
    finally:
        print(f"\n=== TEARDOWN: DELETE /test-control/runs/{RUN_ID} ===")
        try:
            r = requests.delete(f"{BASE}/test-control/runs/{RUN_ID}",
                                headers={"X-Sandbox-Secret": SECRET}, timeout=30)
            print(f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            print(f"ERROR teardown: {e}")
