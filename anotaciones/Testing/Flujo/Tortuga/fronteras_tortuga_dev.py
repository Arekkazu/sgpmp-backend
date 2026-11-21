"""Tortuga Qa (especie de prueba creada en DEV, ACUICULTURA) en DEV: lecturas en las fronteras de umbrales PROPIOS de QA para esa especie (pH y oxigeno disuelto). Paradigma POBLACIONAL (lotes con conteo).
ESCRIBE en DEV (sin sandbox) SOLO en la finca de QA indicada por QA_FINCA_ID (se niega con las fincas 1 y 2).
Fixture propio: area (Estanque), 3 lotes de 1 tortuga (un lote por sensor: un lote solo admite un sensor poblacional), un dispositivo y 3 sensores
(temperatura del agua, temperatura ambiental, humedad). Lecturas por POST /iot/telemetria con el token de servicio del broker (BROKER_SERVICE_TOKEN,
de un archivo local; no se imprime ni se guarda). Si la especie no tiene umbrales, los crea (solo para la especie de prueba, que no se usa en ninguna finca de la entrega) y los deja vigentes para el script de alertas.
Uso: QA_FINCA_ID=<id> python3 fronteras_tortuga_dev.py <token_sesion> <env_broker> <salida.json> [id_area_QA_tortuga]"""
import json, sys, os, time, datetime as dt, urllib.request, urllib.error
if int(os.environ.get("QA_FINCA_ID", "0")) in (0, 1, 2): sys.exit("Defina QA_FINCA_ID con una finca de QA (no 1 ni 2). Abortado sin escribir nada.")
FINCA = int(os.environ["QA_FINCA_ID"])
B = "https://api.inmero.co/api-sgpmp-dev"; TOK = open(sys.argv[1]).read().strip(); OUT = sys.argv[3]
BROKER = [l.split("=", 1)[1].strip().strip('"\'') for l in open(sys.argv[2]) if l.startswith("BROKER_SERVICE_TOKEN=")][0]
INFRA_EXISTENTE = int(sys.argv[4]) if len(sys.argv) > 4 else None
NOW = dt.datetime.now(dt.timezone.utc); HOY = NOW.date().isoformat(); SUF = NOW.strftime("%H%M%S"); ESP = 6
R, FX, LEC = [], {"lotes": {}}, []
def call(m, path, body=None, token=None):
    req = urllib.request.Request(B + path, method=m, data=(json.dumps(body).encode() if body is not None else None), headers={"Authorization": "Bearer " + (token or TOK), "Content-Type": "application/json"})
    try: r = urllib.request.urlopen(req, timeout=40); return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try: return e.code, json.load(e)
        except Exception: return e.code, {}
def reg(i, d, s, r, ok, det=""):
    R.append(dict(id=i, descripcion=d, status=s, error_code=r.get("error_code") if isinstance(r, dict) else None, resultado=ok, detalle=det)); print(ok, i, d, "->", s, (r.get("error_code") if isinstance(r, dict) else "") or "", det[:120])
def _crear_umbrales():
    s0, um0 = call("GET", f"/configuracion/umbrales?id_especie={ESP}"); ya = {u["id_variable_ambiental"] for u in um0.get("items", um0)}
    for idv, vmin, vmax, nivs in ((2, 5, 10, [("critico", 5, 6.5), ("normal", 6.5, 8.5), ("precaucion", 8.5, 10)]), (3, 0, 15, [("critico", 0, 5), ("precaucion", 5, 6), ("normal", 6, 15)])):
        if idv in ya: continue
        s1, r1 = call("POST", "/configuracion/umbrales", {"id_especie": ESP, "id_variable_ambiental": idv, "valor_min": vmin, "valor_max": vmax, "niveles": [{"nivel": n, "limite_inferior": a, "limite_superior": b} for n, a, b in nivs]})
        print("UMBRAL creado var", idv, "->", s1, r1.get("error_code") or r1.get("id_umbral_ambiental"), r1.get("estado_sincronizacion"))
_crear_umbrales()
s, um = call("GET", f"/configuracion/umbrales?id_especie={ESP}"); UM = {u["id_variable_ambiental"]: u for u in um.get("items", um)}
def banda(idv, v):
    u = UM[idv]; n = sorted((float(x["limite_inferior"]), float(x["limite_superior"]), x["nivel"]) for x in u["niveles"])
    if v < float(u["valor_min"]) or v > float(u["valor_max"]): return "fuera"
    h = [x[2] for x in n if x[0] <= v <= x[1]]; return h[0] if len(h) == 1 else "frontera:" + "/".join(h)
SEM = {"normal": "VERDE", "precaucion": "AMARILLO", "critico": "ROJO"}
# (nombre, categoria, id_variable, codigos de tipo_variable a probar, unidad, ref calibracion, valores)
SENS = [("QA-PH", "PH", 2, ["PH_AGUA"], "pH", 7.0, [4.99, 5.0, 6.49, 6.5, 6.51, 8.49, 8.5, 8.51, 9.99, 10.0, 10.01]),
        ("QA-O2", "OXIGENO", 3, ["OXIGENO_DISUELTO"], "mg/L", 8.0, [0.0, 4.99, 5.0, 5.01, 5.99, 6.0, 6.01, 14.99, 15.0, 15.01, 20.0, 20.5])]
try:
    for k in (2, 3): reg("U0", f"Umbral vigente de la variable {k}", 200, {}, "OK" if k in UM else "FALLA", json.dumps([(n['nivel'], n['limite_inferior'], n['limite_superior']) for n in UM[k]['niveles']]) + f" sync={UM[k].get('estado_sincronizacion')}" if k in UM else "no existe")
    if INFRA_EXISTENTE: FX["infra"] = INFRA_EXISTENTE; FX["area_reutilizada"] = True; reg("F1", "Reutilizar area QA de Tortuga", 200, {}, "OK", f"id={INFRA_EXISTENTE}")
    else:
        s, r = call("POST", "/configuracion/infraestructuras", {"nombre_infraestructura": f"QA-FLUJO-TORTUGA-LECT-{SUF}", "tipo_area": "Estanque", "superficie": 5.05, "finca_id": FINCA, "descripcion_infraestructura": "QA flujo tortuga - lecturas en fronteras", "especies": [ESP], "especie_id": ESP, "tipo_modelo_asignado": "MODELO_ACUICULTURA", "nivel_criticidad": "BAJA"})
        FX["infra"] = r.get("id_infraestructura"); reg("F1", "Crear area QA de Tortuga", s, r, "OK" if s == 201 else "FALLA", f"id={FX['infra']}")
    serial = f"QA-TORTUGA-LECT-{SUF}"
    s, r = call("POST", "/configuracion/dispositivos-iot", {"serial": serial, "descripcion": "QA flujo tortuga - dispositivo", "id_infraestructura": FX["infra"], "id_tipo_dispositivo": 1, "es_activo": True}); FX["disp"] = r.get("id_dispositivo_iot"); FX["serial"] = serial; reg("F3", "Registrar dispositivo QA", s, r, "OK" if s == 201 else "FALLA", f"id={FX['disp']}")
    SID = {}
    for nom, cat, idv, codes, unidad, ref, vals in SENS:
        s, r = call("POST", "/activos-biologicos", {"tipo_activo": "POBLACIONAL", "id_especie": ESP, "fecha_inicio_ciclo": HOY, "origen_financiero": "compra", "costo_adquisicion": 1, "soporte_documental": "FACTURA-QA-FLUJO", "id_infraestructura": FX["infra"], "cantidad_inicial": 1, "peso_promedio_inicial": 0.5})
        lote = r.get("id_activo_biologico"); FX["lotes"][nom] = lote; reg("F2", f"Lote de 1 tortuga para {nom}", s, r, "OK" if s == 201 else "FALLA", f"id={lote}")
        s, r = call("POST", f"/configuracion/dispositivos-iot/{FX['disp']}/sensores", {"nombre": f"{nom}-{SUF}", "categoria": cat}); sid = r.get("id_sensores"); SID[nom] = sid; reg("F4", f"Sensor {nom}", s, r, "OK" if s == 201 else "FALLA", f"id={sid}")
        s, r = call("PUT", f"/configuracion/sensores/{sid}/especies-compatibles", {"ids_especies": [ESP]}); reg("F5", f"Especie compatible de {nom}", s, r, "OK" if s == 200 else "FALLA")
        s, r = call("POST", f"/configuracion/sensores/{sid}/asociar", {"id_dispositivo_iot": FX["disp"], "id_infraestructura": FX["infra"], "punto_instalacion": "QA"}); reg("F6", f"Asociar {nom} al area", s, r, "OK" if s in (200, 201) else "FALLA")
        s, r = call("POST", f"/configuracion/sensores/{sid}/calibrar", {"id_dispositivo_iot": FX["disp"], "id_infraestructura": FX["infra"], "valor_referencia": ref, "ganancia": 1.0, "offset": 0.0, "fecha_calibracion": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "observaciones": "QA: sin correccion", "modo_calibracion": "SENSOR"}); reg("F7", f"Calibrar {nom}", s, r, "OK" if s in (200, 201) else "FALLA", json.dumps(r, ensure_ascii=False)[:100])
        s, r = call("POST", f"/activos-biologicos/{lote}/sensores", {"tipo_activo": "LOTE", "tipo_asociacion": "POBLACIONAL", "dispositivo_iot_id": FX["disp"], "sensor_id": sid, "id_infraestructura": FX["infra"], "motivo": "QA flujo tortuga"}); reg("F8", f"Asociar {nom} a su lote", s, r, "OK" if s in (200, 201) else "FALLA", json.dumps(r, ensure_ascii=False)[:100])
    FX["sensores"] = SID
    time.sleep(4)
    codigo_ok = {}
    for nom, cat, idv, codes, unidad, ref, vals in SENS:
        for v in vals:
            ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            intentos = [codigo_ok[nom]] if nom in codigo_ok else codes
            for code in intentos:
                body = {"device_id": FX["disp"], "sensor_id": SID[nom], "tipo_variable": code, "valor": v, "unidad": unidad, "timestamp_captura": ts, "serial": serial, "origen": "TIEMPO_REAL"}
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
        s, r = call("POST", f"/activos-biologicos/{lote}/eventos/baja", {"tipo_baja": "perdida", "fecha_baja": HOY, "motivo_baja": "QA limpieza flujo tortuga (datos de prueba)"}); L("baja del lote", s, r)
    if FX.get("disp"): s, r = call("PATCH", f"/configuracion/dispositivos-iot/{FX['disp']}/desactivar"); L("desactivar dispositivo", s, r)
    json.dump({"ejecutado": dt.datetime.now().isoformat(timespec="seconds"), "ambiente": B, "finca": FINCA, "umbrales_dev": {str(k): {"min": v["valor_min"], "max": v["valor_max"], "niveles": [(n["nivel"], n["limite_inferior"], n["limite_superior"]) for n in v["niveles"]], "sync": v.get("estado_sincronizacion")} for k, v in UM.items()}, "fixture": FX, "pasos": R, "lecturas": LEC}, open(OUT, "w"), ensure_ascii=False, indent=1)
