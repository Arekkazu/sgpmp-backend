# | 2026-11-20 | Juan Sebastian Gutierrez | Convierte el staging de una corrida de TC-M08-G018 (trazas + checkpoints) al JSON propio (formato Cypress del manual 2.1). No ejecuta nada contra TEST. |
# Uso: python convertir_json_g018.py <carpeta run-...> <reintento>
import hashlib, json, os, re, sys

run, reintento = sys.argv[1], int(sys.argv[2])
suf = f"_reintento{reintento}" if reintento > 0 else ""
tc = "TC-M08-G018"
ESPERADOS = ["CP-01", "CP-02", "CP-04", "CP-05", "CP-06a", "CP-06b", "CP-07a", "CP-07b", "CP-08", "CP-09a", "CP-09b", "CP-10", "CP-11"]
CASO = {cp: ("TC-M08-059" if cp == "CP-11" else "TC-M08-047") for cp in ESPERADOS}

def leer(n):
    return open(os.path.join(run, n), encoding="utf-8-sig").read()

def campos(linea):
    p = linea.split("|")
    # tipo|id|esperado=...|obtenido=... (puede contener |)|estado=...|req=...
    return {"tipo": p[0], "id": p[1], "esperado": p[2].removeprefix("esperado="),
            "obtenido": "|".join(p[3:-2]).removeprefix("obtenido="),
            "estado": p[-2].removeprefix("estado="), "req": p[-1].removeprefix("req=")}

trazas = [l for l in leer(f"trazas_{tc}{suf}.txt").splitlines() if l.strip()]
nombres = {}
for l in leer(f"checkpoints_{tc}{suf}.txt").splitlines():
    m = re.match(r"^(OK|FALLA)\s+\|\s+(CP-\S+)\s+(.*?)\s+\|\| esperado: ", l)
    if m:
        nombres[m.group(2)] = (m.group(1), m.group(3))

cps, obs, pre = [], [], []
for l in trazas:
    if l.startswith("CP|"):
        c = campos(l)
        estado_newman, nombre = nombres[c["id"]]
        if estado_newman != c["estado"]:
            sys.exit(f"INCOHERENTE: {c['id']} trazas={c['estado']} checkpoints={estado_newman}")
        fuente = re.findall(r"\(([^()]*)\)\s*$", nombre)
        cps.append({"paso": f"{c['id']} {nombre}", "caso": CASO[c["id"]], "esperado": c["esperado"],
                    "fuente": fuente[0] if fuente else "", "obtenido": c["obtenido"], "estado": c["estado"],
                    "x_request_id": c["req"]})
    elif l.startswith("OBS|"):
        c = campos(l)
        obs.append({"id": c["id"], "obtenido": c["obtenido"], "x_request_id": c["req"]})
    elif l.startswith(("PRE|", "ABORT|", "RETIRADO|", "CIERRE|")):
        pre.append(l)

ids = [c["paso"].split(" ")[0] for c in cps]
if ids != ESPERADOS:
    sys.exit(f"CHECKPOINTS DISTINTOS DEL DISENO: {ids}")
if any(l.startswith(("ABORT|", "RETIRADO|")) for l in pre):
    sys.exit("La corrida tiene ABORT o RETIRADO: no se genera JSON")
cierre = [l for l in pre if l.startswith("CIERRE|")]
resumen = leer(f"resumen_{tc}{suf}.txt")
run_id = re.search(r"run_id: (\S+)", resumen).group(1)
ok = sum(c["estado"] == "OK" for c in cps); falla = sum(c["estado"] == "FALLA" for c in cps)
sha = lambda n: hashlib.sha256(open(os.path.join(run, n), "rb").read()).hexdigest().upper()
doc = {
    "tc": tc, "reintento": reintento,
    "summary": {"total": len(cps), "ok": ok, "falla": falla, "veredicto": "Rechazado" if falla else "Aprobado"},
    "checkpoints": cps,
    "observaciones": obs,
    "retirados": [],
    "runs": [{"run_id": run_id, "rollback": cierre[0] if cierre else "no encontrado"}],
    "precondiciones": [l for l in pre if l.startswith("PRE|")],
    "origen": {"herramienta": "Newman + htmlextra; JSON derivado del mismo staging con convertir_json_g018.py",
               "sha256": {n: sha(n) for n in (f"trazas_{tc}{suf}.txt", f"checkpoints_{tc}{suf}.txt",
                                              f"resumen_{tc}{suf}.txt", f"resultado_{tc}{suf}.html")}},
}
salida = os.path.join(run, f"resultado_{tc}{suf}.json")
if os.path.exists(salida):
    sys.exit(f"ya existe {salida}")
with open(salida, "w", encoding="utf-8", newline="\r\n") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"{salida}: total={len(cps)} ok={ok} falla={falla} observaciones={len(obs)}")
