"""F8 - Ciclo de vida de alertas (RF-57), avestruz en DEV. ESCRIBE en DEV (sin sandbox).
Crea un fixture propio en el area fija de QA (se pasa su id), genera DOS alertas criticas nuevas (una por sensor) y
recorre el ciclo de inmediato: una alerta VENCE ~5 min despues de generada si nadie la atiende, y VENCIDA es terminal.
Alerta A: ACTIVA->EN_ATENCION->RESUELTA + transiciones invalidas. Alerta B: ACTIVA->DESCARTADA.
El token de servicio del broker (BROKER_SERVICE_TOKEN) se lee de un archivo local y no se imprime ni se guarda.
Uso: QA_FINCA_ID=<id finca QA> python3 alertas_ciclo_avestruz_dev.py <token_sesion> <env_broker> <salida.json> <id_area_QA>"""
import json, sys, time, datetime as dt, urllib.request, urllib.error
B = "https://api.inmero.co/api-sgpmp-dev"; TOK = open(sys.argv[1]).read().strip(); OUT = sys.argv[3]; INFRA = int(sys.argv[4])
BROKER = [l.split("=", 1)[1].strip().strip('"\'') for l in open(sys.argv[2]) if l.startswith("BROKER_SERVICE_TOKEN=")][0]
NOW = dt.datetime.now(dt.timezone.utc); HOY = NOW.date().isoformat(); SUF = NOW.strftime("%H%M%S"); ESP = 7
R, FX = [], {}
import os
if int(os.environ.get('QA_FINCA_ID', '0')) in (0, 1, 2): sys.exit('Defina QA_FINCA_ID con una finca de QA (no 1 ni 2). Abortado sin escribir nada.')
def call(m, path, body=None, token=None):
    req = urllib.request.Request(B + path, method=m, data=(json.dumps(body).encode() if body is not None else None), headers={"Authorization": "Bearer " + (token or TOK), "Content-Type": "application/json"})
    try: r = urllib.request.urlopen(req, timeout=40); return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try: return e.code, json.load(e)
        except Exception: return e.code, {}
def estado(i): return call("GET", f"/iot/alertas/{i}")[1]
def paso(i, desc, esp, aid, body, ok_fn, antes=None):
    s, r = call("PATCH", f"/iot/alertas/{aid}/estado", body); d = estado(aid)
    ok = ok_fn(s, r, d)
    R.append(dict(id=i, descripcion=desc, esperado=esp, status=s, error_code=r.get("error_code"), estado_resultante=d.get("estado_alerta"), fecha_atencion=d.get("fecha_atencion"), fecha_resolucion=d.get("fecha_resolucion"), motivo_descarte=d.get("motivo_descarte"), resultado="PASA" if ok else "FALLA"))
    print("PASA " if ok else "FALLA", i, desc, "->", s, r.get("error_code") or "", "| estado:", d.get("estado_alerta"))
try:
    s, r = call("POST", "/activos-biologicos", {"tipo_activo": "INDIVIDUAL", "id_especie": ESP, "fecha_inicio_ciclo": HOY, "origen_financiero": "compra", "costo_adquisicion": 1, "soporte_documental": "FACTURA-QA-FLUJO", "id_infraestructura": INFRA, "identificador": f"QA-AVE-ALR-{SUF}", "raza": "Africano", "sexo": "Hembra", "fecha_nacimiento": "2023-03-01", "peso_inicial": 100})
    FX["activo"] = r.get("id_activo_biologico"); print("animal", s, FX["activo"])
    serial = f"QA-AVE-ALR-{SUF}"
    s, r = call("POST", "/configuracion/dispositivos-iot", {"serial": serial, "descripcion": "QA flujo avestruz - alertas", "id_infraestructura": INFRA, "id_tipo_dispositivo": 1, "es_activo": True}); FX["disp"] = r.get("id_dispositivo_iot"); print("dispositivo", s, FX["disp"])
    SENS = {}
    for nom, cat, tv, unidad, ref, val in (("QA-TEMP-CORP", "TEMPERATURA", "TEMP_CORPORAL", "°C", 38.5, 41.5), ("QA-FC", None, "FRECUENCIA_CARDIACA", "bpm", 77.0, 160.0)):
        b = {"nombre": f"{nom}-{SUF}"}; 
        if cat: b["categoria"] = cat
        s, r = call("POST", f"/configuracion/dispositivos-iot/{FX['disp']}/sensores", b); sid = r.get("id_sensores"); SENS[nom] = dict(id=sid, tv=tv, unidad=unidad, val=val)
        call("PUT", f"/configuracion/sensores/{sid}/especies-compatibles", {"ids_especies": [ESP]})
        call("POST", f"/configuracion/sensores/{sid}/asociar", {"id_dispositivo_iot": FX["disp"], "id_infraestructura": INFRA, "punto_instalacion": "QA"})
        call("POST", f"/configuracion/sensores/{sid}/calibrar", {"id_dispositivo_iot": FX["disp"], "id_infraestructura": INFRA, "valor_referencia": ref, "ganancia": 1.0, "offset": 0.0, "fecha_calibracion": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "observaciones": "QA", "modo_calibracion": "SENSOR"})
        s, r = call("POST", f"/activos-biologicos/{FX['activo']}/sensores", {"tipo_activo": "INDIVIDUAL", "tipo_asociacion": "DIRECTA", "dispositivo_iot_id": FX["disp"], "sensor_id": sid, "id_infraestructura": INFRA, "motivo": "QA"}); print("sensor", nom, sid, "asociado", s)
    time.sleep(4)
    ALR = {}
    for nom, sn in SENS.items():
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        s, r = call("POST", "/iot/telemetria", {"device_id": FX["disp"], "sensor_id": sn["id"], "tipo_variable": sn["tv"], "valor": sn["val"], "unidad": sn["unidad"], "timestamp_captura": ts, "serial": serial, "origen": "TIEMPO_REAL"}, token=BROKER)
        print("lectura", nom, sn["val"], s, r.get("estado_calidad") or r.get("error_code"))
    time.sleep(8)
    for nom, sn in SENS.items():
        its = call("GET", f"/iot/alertas?id_sensor={sn['id']}")[1].get("items", [])
        ALR[nom] = its[0]["id_alerta"] if its else None
    A, Bq = ALR["QA-TEMP-CORP"], ALR["QA-FC"]; print("alertas A/B:", A, Bq)
    a0, b0 = estado(A), estado(Bq)
    R.append(dict(id="E0", descripcion="Alertas generadas por las lecturas criticas", alerta_A=A, estado_A=a0.get("estado_alerta"), severidad_A=a0.get("severidad"), tipo_A=a0.get("tipo_alerta"), alerta_B=Bq, estado_B=b0.get("estado_alerta"), severidad_B=b0.get("severidad"), tipo_B=b0.get("tipo_alerta"),
                  resultado="PASA" if a0.get("estado_alerta") == "ACTIVA" and b0.get("estado_alerta") == "ACTIVA" and a0.get("severidad") == "CRITICO" else "FALLA"))
    if not (a0.get("estado_alerta") == "ACTIVA" and b0.get("estado_alerta") == "ACTIVA"): raise SystemExit("precondicion: las alertas no estan ACTIVAS; no se recorre el ciclo")
    paso("L1", "ACTIVA -> CERRADA (estado que no existe)", "422 TRANSICION_INVALIDA, sigue ACTIVA", A, {"nuevo_estado": "CERRADA", "motivo": "QA"}, lambda s, r, d: s == 422 and r.get("error_code") == "TRANSICION_INVALIDA" and d["estado_alerta"] == "ACTIVA")
    paso("L2", "ACTIVA -> EN_ATENCION", "200, fecha_atencion informada", A, {"nuevo_estado": "EN_ATENCION", "motivo": "QA ciclo de vida"}, lambda s, r, d: s == 200 and d["estado_alerta"] == "EN_ATENCION" and d["fecha_atencion"])
    paso("L3", "EN_ATENCION -> RESUELTA", "200, fecha_resolucion informada", A, {"nuevo_estado": "RESUELTA", "motivo": "QA ciclo de vida"}, lambda s, r, d: s == 200 and d["estado_alerta"] == "RESUELTA" and d["fecha_resolucion"])
    paso("L4", "RESUELTA -> ACTIVA (retroceso)", "rechazo 4xx, sigue RESUELTA", A, {"nuevo_estado": "ACTIVA", "motivo": "QA"}, lambda s, r, d: 400 <= s < 500 and d["estado_alerta"] == "RESUELTA")
    paso("L5", "RESUELTA -> EN_ATENCION", "rechazo 4xx, sigue RESUELTA", A, {"nuevo_estado": "EN_ATENCION", "motivo": "QA"}, lambda s, r, d: 400 <= s < 500 and d["estado_alerta"] == "RESUELTA")
    paso("L6", "Motivo de 501 caracteres", "400/422 (maximo 500), sin cambio", Bq, {"nuevo_estado": "DESCARTADA", "motivo": "x" * 501}, lambda s, r, d: s in (400, 422) and d["estado_alerta"] == "ACTIVA")
    paso("L7", "ACTIVA -> DESCARTADA con motivo", "200, motivo_descarte informado", Bq, {"nuevo_estado": "DESCARTADA", "motivo": "QA: falsa alarma de prueba"}, lambda s, r, d: s == 200 and d["estado_alerta"] == "DESCARTADA" and d["motivo_descarte"])
    paso("L8", "DESCARTADA -> ACTIVA (retroceso)", "rechazo 4xx, sigue DESCARTADA", Bq, {"nuevo_estado": "ACTIVA", "motivo": "QA"}, lambda s, r, d: 400 <= s < 500 and d["estado_alerta"] == "DESCARTADA")
    paso("L9", "Estado inexistente", "400/422", Bq, {"nuevo_estado": "INVENTADO", "motivo": "QA"}, lambda s, r, d: s in (400, 422))
    FX["alertas"] = ALR
finally:
    if FX.get("activo"):
        for a in call("GET", f"/activos-biologicos/{FX['activo']}/sensores")[1].get("asociaciones", []):
            call("PATCH", f"/activos-biologicos/{FX['activo']}/sensores/{a['id_asociacion_activo_sensor']}", {"estado_nuevo": "INACTIVA", "motivo": "QA limpieza"})
        s, r = call("POST", f"/activos-biologicos/{FX['activo']}/eventos/baja", {"tipo_baja": "perdida", "fecha_baja": HOY, "motivo_baja": "QA limpieza flujo avestruz (datos de prueba)"}); print("LIMPIEZA baja animal", s)
    if FX.get("disp"):
        s, r = call("PATCH", f"/configuracion/dispositivos-iot/{FX['disp']}/desactivar"); print("LIMPIEZA desactivar dispositivo", s)
    json.dump({"ejecutado": dt.datetime.now().isoformat(timespec="seconds"), "ambiente": B, "area_QA": INFRA, "fixture": FX, "pasos": R}, open(OUT, "w"), ensure_ascii=False, indent=1)
