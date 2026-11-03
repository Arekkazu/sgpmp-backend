"""Capacidad por area productiva - Cerdo (Porcino) en DEV. Paradigma POBLACIONAL: el animal es un LOTE con conteo.
ESCRIBE en DEV (sin sandbox) SOLO en la finca de QA indicada por QA_FINCA_ID (se niega con las fincas 1 y 2).
Densidad Porcino en DEV = 1.0 ind/m2. Area de 10.5 m2 -> capacidad floor(10.5) = 10.
Limpieza: baja del lote completo (cantidad_afectada omitida) y desactivar el area.
Uso: QA_FINCA_ID=<id> python3 capacidad_cerdo_dev.py <archivo_token_sesion> <salida.json>"""
import json, sys, os, math, datetime as dt, urllib.request, urllib.error
if int(os.environ.get("QA_FINCA_ID", "0")) in (0, 1, 2): sys.exit("Defina QA_FINCA_ID con una finca de QA (no 1 ni 2). Abortado sin escribir nada.")
FINCA = int(os.environ["QA_FINCA_ID"])
B = "https://api.inmero.co/api-sgpmp-dev"; TOK = open(sys.argv[1]).read().strip(); OUT = sys.argv[2]
HOY = dt.datetime.now(dt.timezone.utc).date().isoformat()  # fecha UTC como el servidor (la local puede ir un dia atras)
SUF = dt.datetime.now().strftime("%H%M%S")
ESP_CERDO, ESP_BOV, DENS, SUP = 4, 2, 1.0, 10.5
R, CR = [], {"infra": None, "infra_extra": None, "lotes": []}
def call(m, path, body=None):
    req = urllib.request.Request(B + path, method=m, data=(json.dumps(body).encode() if body is not None else None), headers={"Authorization": "Bearer " + TOK, "Content-Type": "application/json"})
    try: r = urllib.request.urlopen(req, timeout=40); return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try: return e.code, json.load(e)
        except Exception: return e.code, {}
def paso(i, d, esp, s, r, ok, extra=""):
    ec = r.get("error_code") if isinstance(r, dict) else None
    R.append(dict(id=i, descripcion=d, esperado=esp, status=s, error_code=ec, resultado="PASA" if ok else "FALLA", detalle=extra)); print("PASA " if ok else "FALLA", i, d, "->", s, ec or "", extra[:110])
def lote(n, infra, ident=None):
    return {"tipo_activo": "POBLACIONAL", "id_especie": ESP_CERDO, "fecha_inicio_ciclo": HOY, "origen_financiero": "compra", "costo_adquisicion": 1, "soporte_documental": "FACTURA-QA-FLUJO",
            "id_infraestructura": infra, "cantidad_inicial": n, "peso_promedio_inicial": 25.0, **({"identificador": ident} if ident else {})}
def area(nombre, sup, esp, modelo="MODELO_PORCINOS", tipo="Corral"):
    return {"nombre_infraestructura": nombre, "tipo_area": tipo, "superficie": sup, "finca_id": FINCA, "descripcion_infraestructura": "QA flujo cerdo - capacidad", "especies": esp, "especie_id": esp[0], "tipo_modelo_asignado": modelo, "nivel_criticidad": "BAJA"}
def actualiz(infra, sup):
    _, g = call("GET", f"/configuracion/infraestructuras/{infra}"); b = area(f"QA-FLUJO-CERDO-CAP-{SUF}", sup, [ESP_CERDO]); b.pop("finca_id")
    if g.get("fecha_actualizacion"): b["fecha_actualizacion"] = g["fecha_actualizacion"]
    return call("PATCH", f"/configuracion/infraestructuras/{infra}", b)
cap = math.floor(round(DENS * SUP, 9))
try:
    s, r = call("POST", "/configuracion/infraestructuras", area(f"QA-FLUJO-CERDO-CAP-{SUF}", SUP, [ESP_CERDO])); infra = r.get("id_infraestructura") if s == 201 else None; CR["infra"] = infra
    paso("P1", f"Crear area de {SUP} m2 con Porcino (densidad {DENS})", f"201, capacidad_maxima={cap}", s, r, s == 201 and r.get("capacidad_maxima") == cap, f"capacidad_maxima={r.get('capacidad_maxima')} id={infra}")
    if not infra: raise SystemExit("sin area")
    s, r = call("POST", "/activos-biologicos", lote(cap + 1, infra)); 
    if s == 201: CR["lotes"].append(r.get("id_activo_biologico"))
    paso("P2", f"Un lote de {cap+1} cerdos en area vacia (uno sobre el limite)", "422 CAPACIDAD_EXCEDIDA", s, r, s == 422 and r.get("error_code") == "CAPACIDAD_EXCEDIDA", (r.get("message") or "")[:100])
    s, r = call("POST", "/activos-biologicos", lote(cap - 1, infra)); a = r.get("id_activo_biologico") if s == 201 else None
    if a: CR["lotes"].append(a)
    paso("P3", f"Lote de {cap-1} cerdos (un animal bajo el limite)", "201", s, r, s == 201, f"id_activo={a}")
    s, r = call("POST", "/activos-biologicos", lote(1, infra)); a = r.get("id_activo_biologico") if s == 201 else None
    if a: CR["lotes"].append(a)
    paso("P4", f"Segundo lote de 1 cerdo (total {cap}: limite exacto)", "201", s, r, s == 201, f"id_activo={a}")
    s, r = call("POST", "/activos-biologicos", lote(1, infra)); 
    if s == 201: CR["lotes"].append(r.get("id_activo_biologico"))
    paso("P5", f"Tercer lote de 1 cerdo (total {cap+1})", "422 CAPACIDAD_EXCEDIDA", s, r, s == 422 and r.get("error_code") == "CAPACIDAD_EXCEDIDA", (r.get("message") or "")[:100])
    s, r = call("GET", f"/configuracion/infraestructuras/{infra}")
    paso("P6", "Leer area: capacidad_maxima", f"{cap}", s, r, s == 200 and r.get("capacidad_maxima") == cap, f"capacidad_maxima={r.get('capacidad_maxima')}")
    s, r = actualiz(infra, float(cap))
    paso("P7", f"Reducir superficie a {cap}.0 m2 con {cap} cerdos (capacidad {cap})", "200 (limite)", s, r, s == 200, f"capacidad_maxima={r.get('capacidad_maxima')}")
    s, r = actualiz(infra, cap - 0.01)
    paso("P8", f"Reducir superficie a {cap-0.01} m2 (capacidad {cap-1}) con {cap} cerdos", "422 CAPACIDAD_EXCEDIDA", s, r, s == 422 and r.get("error_code") == "CAPACIDAD_EXCEDIDA", (r.get("message") or "")[:100])
    s, r = call("GET", f"/configuracion/infraestructuras/{infra}")
    paso("P9", "La superficie no cambio tras el rechazo", f"{cap}.00", s, r, str(r.get("superficie")) in (f"{cap}", f"{cap}.0", f"{cap}.00"), f"superficie={r.get('superficie')}")
    s, r = call("POST", "/configuracion/infraestructuras", area(f"QA-FLUJO-CERDO-MIX-{SUF}", SUP, [ESP_CERDO, ESP_BOV]))
    if s == 201: CR["infra_extra"] = r.get("id_infraestructura")
    paso("P10", "Area con Porcino + Bovino (PORCINOS + ESPECIES_GRANDES)", "422 GRUPOS_MANEJO_INCOMPATIBLES", s, r, s == 422 and r.get("error_code") == "GRUPOS_MANEJO_INCOMPATIBLES", (r.get("message") or "")[:100])
finally:
    for ida in CR["lotes"]:
        s, r = call("POST", f"/activos-biologicos/{ida}/eventos/baja", {"tipo_baja": "perdida", "fecha_baja": HOY, "motivo_baja": "QA limpieza flujo cerdo (datos de prueba)"})
        R.append(dict(id=f"L-lote-{ida}", descripcion="Limpieza: baja del lote completo", status=s, error_code=r.get("error_code"), resultado="OK" if s in (200, 201) else "REVISAR")); print("LIMPIEZA lote", ida, s, r.get("error_code") or "")
    for k in ("infra", "infra_extra"):
        if CR.get(k):
            s, r = call("PATCH", f"/configuracion/infraestructuras/{CR[k]}/desactivar"); R.append(dict(id=f"L-{k}-{CR[k]}", descripcion="Limpieza: desactivar area", status=s, error_code=r.get("error_code"), resultado="OK" if s in (200, 204) else "REVISAR")); print("LIMPIEZA area", CR[k], s, r.get("error_code") or "")
    json.dump({"ejecutado": dt.datetime.now().isoformat(timespec="seconds"), "ambiente": B, "finca": FINCA, "creados": CR, "pasos": R}, open(OUT, "w"), ensure_ascii=False, indent=1)
