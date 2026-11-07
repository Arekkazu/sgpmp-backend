"""Lecturas en las fronteras de los umbrales de DEV - Bovino (ESCRIBE en DEV, sin sandbox).
Especie de prueba creada en DEV (Avestruz Qa, ESPECIES_GRANDES, individual). Crea umbrales propios de QA para esa especie si no existen y un fixture propio (area, animal, dispositivo, 2 sensores) para NO tocar los sensores reales de PC-BOV-001,
envia lecturas por POST /iot/telemetria con el token de servicio del broker (BROKER_SERVICE_TOKEN, leido de un
archivo local; nunca se imprime ni se guarda en los resultados), lee el resultado en historial/alertas y LIMPIA.
Uso: QA_FINCA_ID=<id finca QA> python3 fronteras_avestruz_dev.py <archivo_token_sesion> <archivo_env_broker> <salida.json> [id_area_QA_existente]
Un dispositivo (aunque este desactivado) impide desactivar su area y la API no permite moverlo ni borrarlo:
por eso se REUTILIZA un area fija de QA (pasar su id) en vez de crear una nueva en cada corrida."""
import json, sys, datetime as dt, urllib.request, urllib.error, urllib.parse, time
B = "https://api.inmero.co/api-sgpmp-dev"
TOK = open(sys.argv[1]).read().strip(); OUT = sys.argv[3]
BROKER = [l.split("=", 1)[1].strip().strip('"\'') for l in open(sys.argv[2]) if l.startswith("BROKER_SERVICE_TOKEN=")][0]
NOW = dt.datetime.now(dt.timezone.utc); HOY = NOW.date().isoformat(); SUF = NOW.strftime("%H%M%S")
import os
FINCA_PROHIBIDAS = {1, 2}  # El rosal y La florida: finca de la entrega, no se escribe ahi
FINCA = int(os.environ.get("QA_FINCA_ID", "0"))
if not FINCA or FINCA in FINCA_PROHIBIDAS:
    sys.exit("Defina QA_FINCA_ID con una finca de QA (no 1 ni 2). Abortado sin escribir nada.")
ESP = 7
INFRA_EXISTENTE = int(sys.argv[4]) if len(sys.argv) > 4 else None
R, FX, LEC = [], {}, []

def call(m, path, body=None, token=None):
    req = urllib.request.Request(B + path, method=m, data=(json.dumps(body).encode() if body is not None else None),
        headers={"Authorization": "Bearer " + (token or TOK), "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=40); return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try: return e.code, json.load(e)
        except Exception: return e.code, {"raw": "no-json"}
def reg(i, desc, st, r, ok, det=""):
    R.append(dict(id=i, descripcion=desc, status=st, error_code=r.get("error_code") if isinstance(r, dict) else None, resultado=ok, detalle=det))
    print(ok, i, desc, "->", st, (r.get("error_code") if isinstance(r, dict) else "") or "", det[:140])

# Umbrales DEV (se leen en vivo, no se asumen)
def _crear_umbrales():
    s0, um0 = call("GET", f"/configuracion/umbrales?id_especie={ESP}"); ya = {u["id_variable_ambiental"] for u in um0.get("items", um0)}
    for idv, vmin, vmax, nivs in ((13, 37, 43, [("normal", 37, 39.8), ("precaucion", 39.8, 40.5), ("critico", 40.5, 43)]), (14, 30, 180, [("normal", 30, 100), ("precaucion", 100, 140), ("critico", 140, 180)])):
        if idv in ya: continue
        s1, r1 = call("POST", "/configuracion/umbrales", {"id_especie": ESP, "id_variable_ambiental": idv, "valor_min": vmin, "valor_max": vmax, "niveles": [{"nivel": n, "limite_inferior": a, "limite_superior": b} for n, a, b in nivs]})
        print("UMBRAL creado var", idv, "->", s1, r1.get("error_code") or r1.get("id_umbral_ambiental"), r1.get("estado_sincronizacion"))
_crear_umbrales()
s, um = call("GET", f"/configuracion/umbrales?id_especie={ESP}"); um = um.get("items", um)
UM = {u["id_variable_ambiental"]: u for u in um}
def banda(idv, v):
    u = UM[idv]; n = sorted((float(x["limite_inferior"]), float(x["limite_superior"]), x["nivel"]) for x in u["niveles"])
    if v < float(u["valor_min"]) or v > float(u["valor_max"]): return "fuera"
    h = [x[2] for x in n if x[0] <= v <= x[1]]; return h[0] if len(h) == 1 else "frontera:" + "/".join(h)
SEM = {"normal": "VERDE", "precaucion": "AMARILLO", "critico": "ROJO"}

try:
    # F1 area
    if INFRA_EXISTENTE:
        FX["infra"] = INFRA_EXISTENTE; FX["area_reutilizada"] = True; reg("F1", "Reutilizar area fija de QA", 200, {}, "OK", f"id={INFRA_EXISTENTE}")
    else:
      s, r = call("POST", "/configuracion/infraestructuras", {"nombre_infraestructura": f"QA-FLUJO-AVESTRUZ-LECT-{SUF}", "tipo_area": "Potrero", "superficie": 155, "finca_id": FINCA,
        "descripcion_infraestructura": "QA flujo avestruz - lecturas en fronteras (se desactiva al terminar)", "especies": [ESP], "especie_id": ESP, "tipo_modelo_asignado": "MODELO_ESPECIES_GRANDES", "nivel_criticidad": "BAJA"})
      FX["infra"] = r.get("id_infraestructura"); reg("F1", "Crear area QA", s, r, "OK" if s == 201 else "FALLA", f"id={FX['infra']}")
    # F2 animal
    s, r = call("POST", "/activos-biologicos", {"tipo_activo": "INDIVIDUAL", "id_especie": ESP, "fecha_inicio_ciclo": HOY, "origen_financiero": "compra", "costo_adquisicion": 1, "soporte_documental": "FACTURA-QA-FLUJO",
        "id_infraestructura": FX["infra"], "identificador": f"QA-AVE-LECT-{SUF}", "raza": "Africano", "sexo": "Hembra", "fecha_nacimiento": "2023-03-01", "peso_inicial": 100})
    FX["activo"] = r.get("id_activo_biologico"); reg("F2", "Crear animal QA", s, r, "OK" if s == 201 else "FALLA", f"id={FX['activo']}")
    # F3 dispositivo
    s, r = call("POST", "/configuracion/dispositivos-iot", {"serial": f"QA-AVE-LECT-{SUF}", "descripcion": "QA flujo avestruz - dispositivo de prueba", "id_infraestructura": FX["infra"], "id_tipo_dispositivo": 1, "es_activo": True})
    FX["disp"] = r.get("id_dispositivo_iot"); FX["serial"] = f"QA-AVE-LECT-{SUF}"; reg("F3", "Registrar dispositivo QA (tipo GENERICO)", s, r, "OK" if s == 201 else "FALLA", f"id={FX['disp']}")
    # F4 sensores
    SENS = {}
    for nom, cat, tv, idv, unidad, ref in (("QA-TEMP-CORP", "TEMPERATURA", "TEMP_CORPORAL", 13, "°C", 38.5), ("QA-FC", None, "FRECUENCIA_CARDIACA", 14, "bpm", 77.0)):
        body = {"nombre": f"{nom}-{SUF}"}; 
        if cat: body["categoria"] = cat
        s, r = call("POST", f"/configuracion/dispositivos-iot/{FX['disp']}/sensores", body)
        sid = r.get("id_sensores") or r.get("id_sensor"); SENS[nom] = dict(id=sid, tv=tv, idv=idv, unidad=unidad, ref=ref)
        reg("F4", f"Registrar sensor {nom}", s, r, "OK" if s == 201 else "FALLA", f"id={sid} resp={json.dumps(r, ensure_ascii=False)[:100]}")
        s, r = call("PUT", f"/configuracion/sensores/{sid}/especies-compatibles", {"ids_especies": [ESP]})
        reg("F5", f"Especies compatibles de {nom}", s, r, "OK" if s in (200, 201) else "REVISAR", json.dumps(r, ensure_ascii=False)[:120])
        s, r = call("POST", f"/configuracion/sensores/{sid}/asociar", {"id_dispositivo_iot": FX["disp"], "id_infraestructura": FX["infra"], "punto_instalacion": "QA"})
        reg("F6", f"Asociar {nom} al area", s, r, "OK" if s in (200, 201) else "FALLA", json.dumps(r, ensure_ascii=False)[:120])
        s, r = call("POST", f"/configuracion/sensores/{sid}/calibrar", {"id_dispositivo_iot": FX["disp"], "id_infraestructura": FX["infra"], "valor_referencia": ref, "ganancia": 1.0, "offset": 0.0, "fecha_calibracion": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "observaciones": "QA flujo: sin correccion", "modo_calibracion": "SENSOR"})
        reg("F7", f"Calibrar {nom} (ganancia 1, offset 0)", s, r, "OK" if s in (200, 201) else "FALLA", json.dumps(r, ensure_ascii=False)[:120])
        s, r = call("POST", f"/activos-biologicos/{FX['activo']}/sensores", {"tipo_activo": "INDIVIDUAL", "tipo_asociacion": "DIRECTA", "dispositivo_iot_id": FX["disp"], "sensor_id": sid, "id_infraestructura": FX["infra"], "motivo": "QA flujo avestruz"})
        reg("F8", f"Asociar {nom} al animal", s, r, "OK" if s in (200, 201) else "FALLA", json.dumps(r, ensure_ascii=False)[:120])
    FX["sensores"] = SENS
    if not all(v["id"] for v in SENS.values()) or not FX.get("activo"): raise SystemExit("fixture incompleto, no se envian lecturas")
    time.sleep(4)  # que la captura sea posterior a la fecha de asociacion/calibracion
    # Lecturas
    VAL = {"QA-TEMP-CORP": [36.99, 37.00, 39.79, 39.80, 39.81, 40.49, 40.50, 40.51, 42.99, 43.00, 43.01],
           "QA-FC": [29.99, 30, 99.99, 100, 100.01, 139.99, 140, 140.01, 179.99, 180, 180.01]}
    k = 0
    for nom, vals in VAL.items():
        sn = SENS[nom]
        for v in vals:
            k += 1
            ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            body = {"device_id": FX["disp"], "sensor_id": sn["id"], "tipo_variable": sn["tv"], "valor": v, "unidad": sn["unidad"], "timestamp_captura": ts, "serial": FX["serial"], "origen": "TIEMPO_REAL"}
            s, r = call("POST", "/iot/telemetria", body, token=BROKER)
            LEC.append(dict(sensor=nom, valor=v, ts=ts, http=s, error_code=r.get("error_code"), respuesta={kk: r.get(kk) for kk in ("id_telemetria", "estado_calidad", "estado", "message") if kk in r}))
            print("lectura", nom, v, "->", s, r.get("error_code") or r.get("estado_calidad") or "")
            time.sleep(0.4)
    time.sleep(8)
    # Lectura de resultado
    for nom, sn in SENS.items():
        its = []; p = 1
        while True:
            s, d = call("GET", f"/iot/monitoreo/historial?fecha_inicio={HOY}&fecha_fin={HOY}&sensor_id={sn['id']}&por_pagina=100&pagina={p}&orden=asc&incluir_alertas=true")
            its += d.get("items", [])
            if p >= d.get("paginas_totales", 1) or not d.get("items"): break
            p += 1
        por_valor = {float(i["valor"]): i for i in its}
        als = call("GET", f"/iot/alertas?id_sensor={sn['id']}&por_pagina=100")[1].get("items", [])
        for l in [x for x in LEC if x["sensor"] == nom]:
            i = por_valor.get(float(l["valor"])); b = banda(sn["idv"], float(l["valor"]))
            esp = "fuera" if b == "fuera" else b
            if not i:
                l["verificacion"] = dict(esperado=esp, observado="NO PERSISTIDA", resultado="INFO" if b in ("fuera",) or b.startswith("frontera") else "FALLA"); continue
            obs = i["estado_semaforo_historico"]; cal = i["estado_calidad"]
            if b.startswith("frontera"):
                res = "INFO"; esp_t = f"frontera {b[9:]} (inclusividad no definida)"
            elif b == "fuera":
                res = "INFO"; esp_t = "fuera de [min,max]"
            else:
                res = "PASA" if SEM[b] == obs and cal == "LECTURA_VALIDA" else "FALLA"; esp_t = f"{b} -> {SEM[b]}"
            l["verificacion"] = dict(esperado=esp_t, semaforo=obs, estado_calidad=cal, id_alerta=i.get("id_alerta"), valor_ajustado=i.get("valor_ajustado"), resultado=res)
        FX.setdefault("alertas", {})[nom] = [dict(id=a["id_alerta"], severidad=a["severidad"], estado=a["estado_alerta"], valor=a["valor"], nivel=(a.get("metadato_evento") or {}).get("nivel_umbral")) for a in als]
finally:
    # limpieza (adaptativa); pasos y resultado se anotan
    def L(desc, s, r): R.append(dict(id="LIMPIEZA", descripcion=desc, status=s, error_code=r.get("error_code"), resultado="OK" if s in (200, 201, 204) else "REVISAR", detalle=(r.get("message") or "")[:100])); print("LIMPIEZA", desc, s, r.get("error_code") or "")
    if FX.get("activo"):
        s, r = call("GET", f"/activos-biologicos/{FX['activo']}/sensores")
        for a in r.get("asociaciones", []):
            s2, r2 = call("PATCH", f"/activos-biologicos/{FX['activo']}/sensores/{a['id_asociacion_activo_sensor']}", {"estado_nuevo": "INACTIVA", "motivo": "QA limpieza"}); L("desactivar asociacion sensor-animal", s2, r2)
        s, r = call("POST", f"/activos-biologicos/{FX['activo']}/eventos/baja", {"tipo_baja": "perdida", "fecha_baja": HOY, "motivo_baja": "QA limpieza flujo avestruz (datos de prueba)"}); L("baja del animal", s, r)
    if FX.get("disp"):
        s, r = call("PATCH", f"/configuracion/dispositivos-iot/{FX['disp']}/desactivar"); L("desactivar dispositivo", s, r)
    if FX.get("infra") and not FX.get("area_reutilizada"):
        s, r = call("PATCH", f"/configuracion/infraestructuras/{FX['infra']}/desactivar"); L("desactivar area (puede fallar por el dispositivo)", s, r)
    json.dump({"ejecutado": dt.datetime.now().isoformat(timespec="seconds"), "ambiente": B, "fixture": FX, "umbrales_dev": {str(k): {"min": v["valor_min"], "max": v["valor_max"], "niveles": [(n["nivel"], n["limite_inferior"], n["limite_superior"]) for n in v["niveles"]]} for k, v in UM.items()}, "pasos": R, "lecturas": LEC}, open(OUT, "w"), ensure_ascii=False, indent=1)
