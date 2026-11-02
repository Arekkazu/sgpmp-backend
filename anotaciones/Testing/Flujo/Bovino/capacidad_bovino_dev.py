"""Capacidad por area productiva - Bovino en DEV (ESCRIBE en DEV, sin sandbox).
Crea un area pequena de prueba y cargas de animales, comprueba capacidad = floor(densidad x superficie)
(densidad Bovino en DEV = 0.1) y al final LIMPIA (cierra activos y desactiva el area).
Uso: QA_FINCA_ID=<id finca QA> python3 capacidad_bovino_dev.py <archivo_token_sesion> <salida.json>
No usa ni imprime el BROKER_TOKEN (esta prueba no lo necesita)."""
import json, sys, math, datetime as dt, urllib.request, urllib.error
B = "https://api.inmero.co/api-sgpmp-dev"
TOK = open(sys.argv[1]).read().strip(); OUT = sys.argv[2]
HOY = dt.date.today().isoformat()
SUF = dt.datetime.now().strftime("%H%M%S")
import os
FINCA_PROHIBIDAS = {1, 2}  # El rosal y La florida: finca de la entrega, no se escribe ahi
FINCA = int(os.environ.get("QA_FINCA_ID", "0"))
if not FINCA or FINCA in FINCA_PROHIBIDAS:
    sys.exit("Defina QA_FINCA_ID con una finca de QA (no 1 ni 2). Abortado sin escribir nada.")
ESP_BOV, ESP_TER, DENS = 2, 3, 0.1
R, CREADOS = [], {"infra": None, "activos": []}

def call(m, path, body=None):
    req = urllib.request.Request(B + path, method=m, data=(json.dumps(body).encode() if body is not None else None),
                                 headers={"Authorization": "Bearer " + TOK, "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=40); return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try: return e.code, json.load(e)
        except Exception: return e.code, {"raw": "no-json"}

def paso(i, desc, esperado, status, resp, ok, extra=""):
    ec = resp.get("error_code") if isinstance(resp, dict) else None
    R.append(dict(id=i, descripcion=desc, esperado=esperado, status=status, error_code=ec, resultado="PASA" if ok else "FALLA", detalle=extra))
    print(("PASA " if ok else "FALLA"), i, desc, "->", status, ec or "", extra)

def activo(n, ident, infra):
    return {"tipo_activo": "INDIVIDUAL", "id_especie": ESP_BOV, "fecha_inicio_ciclo": HOY, "origen_financiero": "compra",
            "costo_adquisicion": 1, "soporte_documental": "FACTURA-QA-FLUJO", "id_infraestructura": infra, "identificador": ident, "raza": "Brahman",
            "sexo": "Hembra", "fecha_nacimiento": "2023-03-01", "peso_inicial": 450}

def area(nombre, sup, especies, modelo="MODELO_ESPECIES_GRANDES"):
    return {"nombre_infraestructura": nombre, "tipo_area": "Potrero", "superficie": sup, "finca_id": FINCA,
            "descripcion_infraestructura": "QA flujo bovino - capacidad (se desactiva al terminar)",
            "especies": especies, "especie_id": especies[0], "tipo_modelo_asignado": modelo, "nivel_criticidad": "BAJA"}

try:
    cap = lambda s: math.floor(round(DENS * s, 9))
    # C1 crear area 35 m2 -> capacidad floor(3.5)=3
    s, r = call("POST", "/configuracion/infraestructuras", area(f"QA-FLUJO-BOVINO-CAP-{SUF}", 35, [ESP_BOV]))
    ok = s == 201
    infra = r.get("id_infraestructura") if ok else None; CREADOS["infra"] = infra
    paso("C1", "Crear area de 35 m2 con Bovino (densidad 0.1)", "201, capacidad_maxima=3 (floor(3.5))", s, r, ok and r.get("capacidad_maxima") == 3, f"capacidad_maxima={r.get('capacidad_maxima')} id={infra}")
    if not infra: raise SystemExit("sin area, se detiene")
    # C2..C4 cargar 2 y 3 animales (limite exacto)
    for n in (1, 2, 3):
        s, r = call("POST", "/activos-biologicos", activo(n, f"QA-BOV-CAP-{SUF}-{n}", infra))
        ida = r.get("id_activo_biologico") if s == 201 else None
        if ida: CREADOS["activos"].append(ida)
        paso(f"C{n+1}", f"Registrar animal {n} de 3 (capacidad 3)" + (" - LIMITE EXACTO" if n == 3 else ""), "201", s, r, s == 201, f"id_activo={ida}")
    # C5 el 4to supera
    s, r = call("POST", "/activos-biologicos", activo(4, f"QA-BOV-CAP-{SUF}-4", infra))
    if s == 201 and r.get("id_activo_biologico"): CREADOS["activos"].append(r["id_activo_biologico"])
    paso("C5", "Registrar animal 4 (un animal sobre el limite)", "422 CAPACIDAD_EXCEDIDA", s, r, s == 422 and r.get("error_code") == "CAPACIDAD_EXCEDIDA", (r.get("message") or "")[:120])
    # C6 identificador duplicado
    s, r = call("POST", "/activos-biologicos", activo(1, f"QA-BOV-CAP-{SUF}-1", infra))
    if s == 201 and r.get("id_activo_biologico"): CREADOS["activos"].append(r["id_activo_biologico"])
    paso("C6", "Identificador duplicado", "409/422 por identificador repetido (no por otro motivo)", s, r, s in (409, 422) and "SOPORTE" not in str(r.get("error_code")) and "identificador" in json.dumps(r, ensure_ascii=False).lower(), (r.get("message") or "")[:120])
    # C7 area llena: lectura de capacidad
    s, r = call("GET", f"/configuracion/infraestructuras/{infra}")
    paso("C7", "Leer area: capacidad_maxima sigue 3", "capacidad_maxima=3", s, r, s == 200 and r.get("capacidad_maxima") == 3, f"capacidad_maxima={r.get('capacidad_maxima')}")
    # C8 reducir superficie a 30 m2 -> capacidad 3, con 3 alojados debe aceptarse (limite)
    ed = area(f"QA-FLUJO-BOVINO-CAP-{SUF}", 30, [ESP_BOV]); [ed.pop(k) for k in ("finca_id",)]
    _, g = call("GET", f"/configuracion/infraestructuras/{infra}")
    if g.get("fecha_actualizacion"): ed["fecha_actualizacion"] = g["fecha_actualizacion"]
    s, r = call("PATCH", f"/configuracion/infraestructuras/{infra}", ed)
    paso("C8", "Reducir superficie a 30 m2 (capacidad 3) con 3 animales", "200 (limite)", s, r, s == 200, f"capacidad_maxima={r.get('capacidad_maxima')}")
    # C9 reducir a 29.99 -> capacidad 2 con 3 alojados
    ed["superficie"] = 29.99
    _, g = call("GET", f"/configuracion/infraestructuras/{infra}")
    if g.get("fecha_actualizacion"): ed["fecha_actualizacion"] = g["fecha_actualizacion"]
    s, r = call("PATCH", f"/configuracion/infraestructuras/{infra}", ed)
    paso("C9", "Reducir superficie a 29.99 m2 (capacidad 2) con 3 animales", "422 CAPACIDAD_EXCEDIDA", s, r, s == 422 and r.get("error_code") == "CAPACIDAD_EXCEDIDA", (r.get("message") or "")[:120])
    s, r = call("GET", f"/configuracion/infraestructuras/{infra}")
    paso("C10", "La superficie no cambio tras el rechazo", "superficie=30.00", s, r, str(r.get("superficie")) in ("30", "30.0", "30.00"), f"superficie={r.get('superficie')}")
    # C11 negativo transversal: Bovino + Ternero (grupos distintos)
    s, r = call("POST", "/configuracion/infraestructuras", area(f"QA-FLUJO-BOVINO-MIX-{SUF}", 35, [ESP_BOV, ESP_TER]))
    if s == 201 and r.get("id_infraestructura"): CREADOS["infra_extra"] = r["id_infraestructura"]
    paso("C11", "Area con Bovino + Ternero (ESPECIES_GRANDES + ESPECIES_MEDIANAS)", "422 GRUPOS_MANEJO_INCOMPATIBLES", s, r, s == 422 and r.get("error_code") == "GRUPOS_MANEJO_INCOMPATIBLES", (r.get("message") or "")[:120])
finally:
    # limpieza: dar de baja los activos y desactivar las areas
    for ida in CREADOS["activos"]:
        s, r = call("POST", f"/activos-biologicos/{ida}/eventos/baja", {"tipo_baja": "perdida", "fecha_baja": HOY, "motivo_baja": "QA limpieza flujo bovino (datos de prueba)"})
        R.append(dict(id=f"L-activo-{ida}", descripcion="Limpieza: baja del activo (el cierre de ciclo da SIN_FASE_ACTIVA)", status=s, error_code=r.get("error_code"), resultado="OK" if s in (200, 201) else "REVISAR", detalle=(r.get("message") or "")[:100]))
        print("LIMPIEZA activo", ida, s, r.get("error_code") or "")
    for k in ("infra", "infra_extra"):
        if CREADOS.get(k):
            s, r = call("PATCH", f"/configuracion/infraestructuras/{CREADOS[k]}/desactivar")
            R.append(dict(id=f"L-{k}-{CREADOS[k]}", descripcion="Limpieza: desactivar area", status=s, error_code=r.get("error_code"), resultado="OK" if s in (200, 204) else "REVISAR", detalle=(r.get("message") or "")[:100]))
            print("LIMPIEZA area", CREADOS[k], s, r.get("error_code") or "")
    json.dump({"ejecutado": dt.datetime.now().isoformat(timespec="seconds"), "ambiente": B, "creados": CREADOS, "pasos": R}, open(OUT, "w"), ensure_ascii=False, indent=1)
