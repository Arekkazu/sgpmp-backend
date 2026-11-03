"""Pollo (Pollo De Engorde) en DEV: lecturas de un sensor de una especie SIN umbrales configurados (Pollo de engorde no tiene ninguno en DEV).
ESCRIBE en DEV (sin sandbox) SOLO en la finca de QA indicada por QA_FINCA_ID (se niega con las fincas 1 y 2).
Fixture propio: area, lote POBLACIONAL, dispositivo y 3 sensores (temperatura ambiental, humedad, amoniaco). Lecturas por
POST /iot/telemetria con el token de servicio del broker (BROKER_SERVICE_TOKEN, de un archivo local; no se imprime ni se guarda).
NO crea umbrales: documenta como se comporta el sistema sin ellos (semaforo, calidad, alertas).
Uso: QA_FINCA_ID=<id> python3 sin_umbral_pollo_dev.py <token_sesion> <env_broker> <salida.json> [id_area_QA_porcino]"""
import json, sys, os, time, datetime as dt, urllib.request, urllib.error
if int(os.environ.get("QA_FINCA_ID", "0")) in (0, 1, 2): sys.exit("Defina QA_FINCA_ID con una finca de QA (no 1 ni 2). Abortado sin escribir nada.")
FINCA = int(os.environ["QA_FINCA_ID"])
B = "https://api.inmero.co/api-sgpmp-dev"; TOK = open(sys.argv[1]).read().strip(); OUT = sys.argv[3]
BROKER = [l.split("=", 1)[1].strip().strip('"\'') for l in open(sys.argv[2]) if l.startswith("BROKER_SERVICE_TOKEN=")][0]
INFRA_EXISTENTE = int(sys.argv[4]) if len(sys.argv) > 4 else None
NOW = dt.datetime.now(dt.timezone.utc); HOY = NOW.date().isoformat(); SUF = NOW.strftime("%H%M%S"); ESP = 5
R, FX, LEC = [], {}, []
def call(m, path, body=None, token=None):
    req = urllib.request.Request(B + path, method=m, data=(json.dumps(body).encode() if body is not None else None), headers={"Authorization": "Bearer " + (token or TOK), "Content-Type": "application/json"})
    try: r = urllib.request.urlopen(req, timeout=40); return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try: return e.code, json.load(e)
        except Exception: return e.code, {}
def reg(i, d, s, r, ok, det=""):
    R.append(dict(id=i, descripcion=d, status=s, error_code=r.get("error_code") if isinstance(r, dict) else None, resultado=ok, detalle=det)); print(ok, i, d, "->", s, (r.get("error_code") if isinstance(r, dict) else "") or "", det[:130])
s, um = call("GET", f"/configuracion/umbrales?id_especie={ESP}"); n_um = len(um.get("items", um))
reg("U0", "Precondicion: Pollo de engorde no tiene umbrales", s, um, "OK" if n_um == 0 else "FALLA", f"{n_um} umbrales")
if n_um: sys.exit("Pollo de engorde ya tiene umbrales: esta prueba ya no aplica")
SENS = [("QA-TEMP-AMB", "TEMPERATURA", "TEMPERATURA_AMBIENTAL", "°C", 25.0, [24.0, 35.0, 99.9, 100.0, 100.5, -50.0, -50.5]),
        ("QA-HR", "HUMEDAD", "HUMEDAD_RELATIVA", "%", 60.0, [60.0, 95.0, 100.0, 100.5, 0.0, -0.5]),
        ("QA-NH3", "AMONIACO", "NH3", "ppm", 5.0, [10.0, 40.0, 499.9, 500.0, 500.5, 0.0, -0.5])]
try:
    if INFRA_EXISTENTE: FX["infra"] = INFRA_EXISTENTE; FX["area_reutilizada"] = True; reg("F1", "Reutilizar area QA de Pollo de engorde", 200, {}, "OK", f"id={INFRA_EXISTENTE}")
    else:
        s, r = call("POST", "/configuracion/infraestructuras", {"nombre_infraestructura": f"QA-FLUJO-POLLO-LECT-{SUF}", "tipo_area": "Galpón", "superficie": 10.5, "finca_id": FINCA, "descripcion_infraestructura": "QA flujo pollo - lecturas sin umbral", "especies": [ESP], "especie_id": ESP, "tipo_modelo_asignado": "MODELO_AVES", "nivel_criticidad": "BAJA"})
        FX["infra"] = r.get("id_infraestructura"); reg("F1", "Crear area QA de Pollo de engorde", s, r, "OK" if s == 201 else "FALLA", f"id={FX['infra']}")
    s, r = call("POST", "/activos-biologicos", {"tipo_activo": "POBLACIONAL", "id_especie": ESP, "fecha_inicio_ciclo": HOY, "origen_financiero": "compra", "costo_adquisicion": 1, "soporte_documental": "FACTURA-QA-FLUJO", "id_infraestructura": FX["infra"], "cantidad_inicial": 5, "peso_promedio_inicial": 1.5})
    FX["lote"] = r.get("id_activo_biologico"); reg("F2", "Crear lote de 5 pollos", s, r, "OK" if s == 201 else "FALLA", f"id={FX['lote']}")
    serial = f"QA-POLLO-LECT-{SUF}"
    s, r = call("POST", "/configuracion/dispositivos-iot", {"serial": serial, "descripcion": "QA flujo pollo - dispositivo", "id_infraestructura": FX["infra"], "id_tipo_dispositivo": 1, "es_activo": True}); FX["disp"] = r.get("id_dispositivo_iot"); FX["serial"] = serial; reg("F3", "Registrar dispositivo QA", s, r, "OK" if s == 201 else "FALLA", f"id={FX['disp']}")
    for nom, cat, tv, unidad, ref, vals in SENS:
        s, r = call("POST", f"/configuracion/dispositivos-iot/{FX['disp']}/sensores", {"nombre": f"{nom}-{SUF}", "categoria": cat}); sid = r.get("id_sensores"); FX.setdefault("sensores", {})[nom] = sid
        reg("F4", f"Sensor {nom} ({cat})", s, r, "OK" if s == 201 else "FALLA", f"id={sid}")
        s, r = call("PUT", f"/configuracion/sensores/{sid}/especies-compatibles", {"ids_especies": [ESP]}); reg("F5", f"Especie compatible de {nom}", s, r, "OK" if s == 200 else "FALLA", json.dumps(r, ensure_ascii=False)[:100])
        s, r = call("POST", f"/configuracion/sensores/{sid}/asociar", {"id_dispositivo_iot": FX["disp"], "id_infraestructura": FX["infra"], "punto_instalacion": "QA"}); reg("F6", f"Asociar {nom} al area", s, r, "OK" if s in (200, 201) else "FALLA", json.dumps(r, ensure_ascii=False)[:100])
        s, r = call("POST", f"/configuracion/sensores/{sid}/calibrar", {"id_dispositivo_iot": FX["disp"], "id_infraestructura": FX["infra"], "valor_referencia": ref, "ganancia": 1.0, "offset": 0.0, "fecha_calibracion": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "observaciones": "QA: sin correccion", "modo_calibracion": "SENSOR"}); reg("F7", f"Calibrar {nom}", s, r, "OK" if s in (200, 201) else "FALLA", json.dumps(r, ensure_ascii=False)[:100])
        s, r = call("POST", f"/activos-biologicos/{FX['lote']}/sensores", {"tipo_activo": "LOTE", "tipo_asociacion": "POBLACIONAL", "dispositivo_iot_id": FX["disp"], "sensor_id": sid, "id_infraestructura": FX["infra"], "motivo": "QA flujo pollo"}); reg("F8", f"Asociar {nom} al lote", s, r, "OK" if s in (200, 201) else "FALLA", json.dumps(r, ensure_ascii=False)[:120])
    time.sleep(4)
    for nom, cat, tv, unidad, ref, vals in SENS:
        for v in vals:
            ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            s, r = call("POST", "/iot/telemetria", {"device_id": FX["disp"], "sensor_id": FX["sensores"][nom], "tipo_variable": tv, "valor": v, "unidad": unidad, "timestamp_captura": ts, "serial": serial, "origen": "TIEMPO_REAL"}, token=BROKER)
            LEC.append(dict(sensor=nom, tipo_variable=tv, valor=v, http=s, error_code=r.get("error_code"), estado_calidad_respuesta=r.get("estado_calidad"), message=(r.get("message") or "")[:100]))
            print("lectura", nom, v, "->", s, r.get("estado_calidad") or r.get("error_code") or ""); time.sleep(0.4)
    time.sleep(8)
    for nom, sid in FX["sensores"].items():
        its = []; p = 1
        while True:
            s, d = call("GET", f"/iot/monitoreo/historial?fecha_inicio={HOY}&fecha_fin={HOY}&sensor_id={sid}&por_pagina=100&pagina={p}&orden=asc"); its += d.get("items", [])
            if p >= d.get("paginas_totales", 1) or not d.get("items"): break
            p += 1
        por = {float(i["valor"]): i for i in its}
        for l in [x for x in LEC if x["sensor"] == nom]:
            i = por.get(float(l["valor"]))
            l["historial"] = None if not i else dict(estado_calidad=i["estado_calidad"], semaforo=i["estado_semaforo_historico"], id_alerta=i.get("id_alerta"), id_umbral=i.get("id_umbral_ambiental"), valor_ajustado=i.get("valor_ajustado"), tipo_activo=i.get("tipo_activo"), especie=i.get("especie"))
        FX.setdefault("alertas", {})[nom] = [a["id_alerta"] for a in call("GET", f"/iot/alertas?id_sensor={sid}")[1].get("items", [])]
    s, d = call("GET", f"/iot/monitoreo/dashboard/{FX['infra']}")
    FX["dashboard"] = dict(estado_general=(d.get("resumen_unidades") or [{}])[0].get("estado_general"), sensores=[dict(n=x["nombre_sensor"], sem=x["estado_semaforo"], sin_umbral=x.get("sin_umbral"), valor=x["ultimo_valor"], calidad=x["estado_calidad"]) for x in d.get("sensores", [])])
finally:
    def L(desc, s, r): R.append(dict(id="LIMPIEZA", descripcion=desc, status=s, error_code=r.get("error_code"), resultado="OK" if s in (200, 201, 204) else "REVISAR")); print("LIMPIEZA", desc, s, r.get("error_code") or "")
    if FX.get("lote"):
        for a in call("GET", f"/activos-biologicos/{FX['lote']}/sensores")[1].get("asociaciones", []):
            s2, r2 = call("PATCH", f"/activos-biologicos/{FX['lote']}/sensores/{a['id_asociacion_activo_sensor']}", {"estado_nuevo": "INACTIVA", "motivo": "QA limpieza"}); L("desactivar asociacion sensor-lote", s2, r2)
        s, r = call("POST", f"/activos-biologicos/{FX['lote']}/eventos/baja", {"tipo_baja": "perdida", "fecha_baja": HOY, "motivo_baja": "QA limpieza flujo pollo (datos de prueba)"}); L("baja del lote", s, r)
    if FX.get("disp"): s, r = call("PATCH", f"/configuracion/dispositivos-iot/{FX['disp']}/desactivar"); L("desactivar dispositivo", s, r)
    json.dump({"ejecutado": dt.datetime.now().isoformat(timespec="seconds"), "ambiente": B, "finca": FINCA, "fixture": FX, "pasos": R, "lecturas": LEC}, open(OUT, "w"), ensure_ascii=False, indent=1)
