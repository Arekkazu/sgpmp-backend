"""Cachama (Cachama Blanca) en DEV: lecturas en las fronteras de los umbrales vigentes. Paradigma POBLACIONAL (lotes con conteo).
ESCRIBE en DEV (sin sandbox) SOLO en la finca de QA indicada por QA_FINCA_ID (se niega con las fincas 1 y 2).
Fixture propio: area (Estanque), 3 lotes de 1 pez (un lote por sensor: un lote solo admite un sensor poblacional), un dispositivo y 3 sensores
(temperatura del agua, temperatura ambiental, humedad). Lecturas por POST /iot/telemetria con el token de servicio del broker (BROKER_SERVICE_TOKEN,
de un archivo local; no se imprime ni se guarda). Los umbrales se leen en vivo de DEV (no se crean ni modifican).
Uso: QA_FINCA_ID=<id> python3 fronteras_cachama_dev.py <token_sesion> <env_broker> <salida.json> [id_area_QA_cachama]"""
import json, sys, os, time, datetime as dt, urllib.request, urllib.error
if int(os.environ.get("QA_FINCA_ID", "0")) in (0, 1, 2): sys.exit("Defina QA_FINCA_ID con una finca de QA (no 1 ni 2). Abortado sin escribir nada.")
FINCA = int(os.environ["QA_FINCA_ID"])
B = "https://api.inmero.co/api-sgpmp-dev"; TOK = open(sys.argv[1]).read().strip(); OUT = sys.argv[3]
BROKER = [l.split("=", 1)[1].strip().strip('"\'') for l in open(sys.argv[2]) if l.startswith("BROKER_SERVICE_TOKEN=")][0]
INFRA_EXISTENTE = int(sys.argv[4]) if len(sys.argv) > 4 else None
NOW = dt.datetime.now(dt.timezone.utc); HOY = NOW.date().isoformat(); SUF = NOW.strftime("%H%M%S"); ESP = 1
R, FX, LEC = [], {"lotes": {}}, []
def call(m, path, body=None, token=None):
    req = urllib.request.Request(B + path, method=m, data=(json.dumps(body).encode() if body is not None else None), headers={"Authorization": "Bearer " + (token or TOK), "Content-Type": "application/json"})
    try: r = urllib.request.urlopen(req, timeout=40); return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try: return e.code, json.load(e)
        except Exception: return e.code, {}
def reg(i, d, s, r, ok, det=""):
    R.append(dict(id=i, descripcion=d, status=s, error_code=r.get("error_code") if isinstance(r, dict) else None, resultado=ok, detalle=det)); print(ok, i, d, "->", s, (r.get("error_code") if isinstance(r, dict) else "") or "", det[:120])
s, um = call("GET", f"/configuracion/umbrales?id_especie={ESP}"); UM = {u["id_variable_ambiental"]: u for u in um.get("items", um)}
def banda(idv, v):
    u = UM[idv]; n = sorted((float(x["limite_inferior"]), float(x["limite_superior"]), x["nivel"]) for x in u["niveles"])
    if v < float(u["valor_min"]) or v > float(u["valor_max"]): return "fuera"
    h = [x[2] for x in n if x[0] <= v <= x[1]]; return h[0] if len(h) == 1 else "frontera:" + "/".join(h)
SEM = {"normal": "VERDE", "precaucion": "AMARILLO", "critico": "ROJO"}
# (nombre, categoria, id_variable, codigos de tipo_variable a probar, unidad, ref calibracion, valores)
SENS = [("QA-TEMP-AGUA", "TEMPERATURA", 1, ["TEMPERATURA_AGUA", "Temperatura del agua"], "°C", 27.0, [23.99, 24.0, 29.99, 30.0, 30.01, 31.99, 32.0, 32.01, 33.99, 34.0, 34.01]),
        ("QA-TEMP-AMB", "TEMPERATURA", 9, ["TEMPERATURA_AMBIENTAL"], "°C", 25.0, [17.99, 18.0, 31.99, 32.0, 32.01, 34.99, 35.0, 35.01, 39.99, 40.0, 40.01]),
        ("QA-HR", "HUMEDAD", 10, ["HUMEDAD_RELATIVA"], "%", 60.0, [39.99, 40.0, 69.99, 70.0, 70.01, 79.99, 80.0, 80.01, 99.99, 100.0, 100.01])]
try:
    for k in (1, 9, 10): reg("U0", f"Umbral vigente de la variable {k}", 200, {}, "OK" if k in UM else "FALLA", json.dumps([(n['nivel'], n['limite_inferior'], n['limite_superior']) for n in UM[k]['niveles']]) + f" sync={UM[k].get('estado_sincronizacion')}" if k in UM else "no existe")
    if INFRA_EXISTENTE: FX["infra"] = INFRA_EXISTENTE; FX["area_reutilizada"] = True; reg("F1", "Reutilizar area QA de Cachama", 200, {}, "OK", f"id={INFRA_EXISTENTE}")
    else:
        s, r = call("POST", "/configuracion/infraestructuras", {"nombre_infraestructura": f"QA-FLUJO-CACHAMA-LECT-{SUF}", "tipo_area": "Estanque", "superficie": 2.05, "finca_id": FINCA, "descripcion_infraestructura": "QA flujo cachama - lecturas en fronteras", "especies": [ESP], "especie_id": ESP, "tipo_modelo_asignado": "MODELO_ACUICULTURA", "nivel_criticidad": "BAJA"})
        FX["infra"] = r.get("id_infraestructura"); reg("F1", "Crear area QA de Cachama", s, r, "OK" if s == 201 else "FALLA", f"id={FX['infra']}")
    serial = f"QA-CACHAMA-LECT-{SUF}"
    s, r = call("POST", "/configuracion/dispositivos-iot", {"serial": serial, "descripcion": "QA flujo cachama - dispositivo", "id_infraestructura": FX["infra"], "id_tipo_dispositivo": 1, "es_activo": True}); FX["disp"] = r.get("id_dispositivo_iot"); FX["serial"] = serial; reg("F3", "Registrar dispositivo QA", s, r, "OK" if s == 201 else "FALLA", f"id={FX['disp']}")
    SID = {}
    for nom, cat, idv, codes, unidad, ref, vals in SENS:
        s, r = call("POST", "/activos-biologicos", {"tipo_activo": "POBLACIONAL", "id_especie": ESP, "fecha_inicio_ciclo": HOY, "origen_financiero": "compra", "costo_adquisicion": 1, "soporte_documental": "FACTURA-QA-FLUJO", "id_infraestructura": FX["infra"], "cantidad_inicial": 1, "peso_promedio_inicial": 0.05})
        lote = r.get("id_activo_biologico"); FX["lotes"][nom] = lote; reg("F2", f"Lote de 1 pez para {nom}", s, r, "OK" if s == 201 else "FALLA", f"id={lote}")
        s, r = call("POST", f"/configuracion/dispositivos-iot/{FX['disp']}/sensores", {"nombre": f"{nom}-{SUF}", "categoria": cat}); sid = r.get("id_sensores"); SID[nom] = sid; reg("F4", f"Sensor {nom}", s, r, "OK" if s == 201 else "FALLA", f"id={sid}")
        s, r = call("PUT", f"/configuracion/sensores/{sid}/especies-compatibles", {"ids_especies": [ESP]}); reg("F5", f"Especie compatible de {nom}", s, r, "OK" if s == 200 else "FALLA")
        s, r = call("POST", f"/configuracion/sensores/{sid}/asociar", {"id_dispositivo_iot": FX["disp"], "id_infraestructura": FX["infra"], "punto_instalacion": "QA"}); reg("F6", f"Asociar {nom} al area", s, r, "OK" if s in (200, 201) else "FALLA")
        s, r = call("POST", f"/configuracion/sensores/{sid}/calibrar", {"id_dispositivo_iot": FX["disp"], "id_infraestructura": FX["infra"], "valor_referencia": ref, "ganancia": 1.0, "offset": 0.0, "fecha_calibracion": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "observaciones": "QA: sin correccion", "modo_calibracion": "SENSOR"}); reg("F7", f"Calibrar {nom}", s, r, "OK" if s in (200, 201) else "FALLA", json.dumps(r, ensure_ascii=False)[:100])
        s, r = call("POST", f"/activos-biologicos/{lote}/sensores", {"tipo_activo": "LOTE", "tipo_asociacion": "POBLACIONAL", "dispositivo_iot_id": FX["disp"], "sensor_id": sid, "id_infraestructura": FX["infra"], "motivo": "QA flujo cachama"}); reg("F8", f"Asociar {nom} a su lote", s, r, "OK" if s in (200, 201) else "FALLA", json.dumps(r, ensure_ascii=False)[:100])
    FX["sensores"] = SID
    time.sleep(4)
    codigo_ok = {}
    for nom, cat, idv, codes, unidad, ref, vals in SENS:
        for v in vals:
            ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            intentos = [codigo_ok[nom]] if nom in codigo_ok else codes
            for code in intentos:
                body = {"device_id": FX["disp"], "sensor_id": SID[nom], "tipo_variable": code, "valor": v, "unidad": unidad, "timestamp_captura": ts, "serial": serial, "origen": "TIEMPO_REAL"}
                if idv == 1: body["id_variable"] = idv
                s, r = call("POST", "/iot/telemetria", body, token=BROKER)
                if s in (200, 201): codigo_ok[nom] = code; break
            LEC.append(dict(sensor=nom, id_variable=idv, tipo_variable=code, valor=v, http=s, error_code=r.get("error_code"), message=(r.get("message") or "")[:100]))
            print("lectura", nom, v, "->", s, r.get("estado_calidad") or r.get("error_code") or "", ("[" + code + "]") if idv == 1 else ""); time.sleep(0.35)
    FX["codigo_variable_usado"] = codigo_ok
    time.sleep(8)
    for nom, sid in SID.items():
        idv = [x[2] for x in SENS if x[0] == nom][0]; its = []; p = 1
        while True:
            s, d = call("GET", f"/iot/monitoreo/historial?fecha_inicio={HOY}&fecha_fin={HOY}&sensor_id={sid}&por_pagina=100&pagina={p}&orden=asc"); its += d.get("items", [])
            if p >= d.get("paginas_totales", 1) or not d.get("items"): break
            p += 1
        por = {round(float(i["valor"]), 4): i for i in its}
        for l in [x for x in LEC if x["sensor"] == nom]:
            i = por.get(round(l["valor"], 4)); b = banda(idv, l["valor"])
            if l["http"] not in (200, 201): l["verificacion"] = dict(esperado=b, resultado="INFO" if b == "fuera" or b.startswith("frontera") else "FALLA", observado=f"rechazada {l['http']} {l['error_code']}"); continue
            if not i: l["verificacion"] = dict(esperado=b, observado="NO PERSISTIDA", resultado="FALLA"); continue
            obs = i["estado_semaforo_historico"]; cal = i["estado_calidad"]
            if b.startswith("frontera"): res, esp_t = "INFO", f"frontera {b[9:]}"
            elif b == "fuera": res, esp_t = "INFO", "fuera de [min,max]"
            else: res, esp_t = ("PASA" if SEM[b] == obs and cal == "LECTURA_VALIDA" else "FALLA"), f"{b} -> {SEM[b]}"
            l["verificacion"] = dict(esperado=esp_t, semaforo=obs, estado_calidad=cal, id_alerta=i.get("id_alerta"), id_umbral=i.get("id_umbral_ambiental"), valor_ajustado=i.get("valor_ajustado"), tipo_activo=i.get("tipo_activo"), resultado=res)
        FX.setdefault("alertas", {})[nom] = [dict(id=a["id_alerta"], severidad=a["severidad"], estado=a["estado_alerta"], valor=a["valor"]) for a in call("GET", f"/iot/alertas?id_sensor={sid}")[1].get("items", [])]
finally:
    def L(desc, s, r): R.append(dict(id="LIMPIEZA", descripcion=desc, status=s, error_code=r.get("error_code"), resultado="OK" if s in (200, 201, 204) else "REVISAR")); print("LIMPIEZA", desc, s, r.get("error_code") or "")
    for nom, lote in FX["lotes"].items():
        if not lote: continue
        for a in call("GET", f"/activos-biologicos/{lote}/sensores")[1].get("asociaciones", []):
            s2, r2 = call("PATCH", f"/activos-biologicos/{lote}/sensores/{a['id_asociacion_activo_sensor']}", {"estado_nuevo": "INACTIVA", "motivo": "QA limpieza"}); L("desactivar asociacion sensor-lote", s2, r2)
        s, r = call("POST", f"/activos-biologicos/{lote}/eventos/baja", {"tipo_baja": "perdida", "fecha_baja": HOY, "motivo_baja": "QA limpieza flujo cachama (datos de prueba)"}); L("baja del lote", s, r)
    if FX.get("disp"): s, r = call("PATCH", f"/configuracion/dispositivos-iot/{FX['disp']}/desactivar"); L("desactivar dispositivo", s, r)
    json.dump({"ejecutado": dt.datetime.now().isoformat(timespec="seconds"), "ambiente": B, "finca": FINCA, "umbrales_dev": {str(k): {"min": v["valor_min"], "max": v["valor_max"], "niveles": [(n["nivel"], n["limite_inferior"], n["limite_superior"]) for n in v["niveles"]], "sync": v.get("estado_sincronizacion")} for k, v in UM.items()}, "fixture": FX, "pasos": R, "lecturas": LEC}, open(OUT, "w"), ensure_ascii=False, indent=1)
