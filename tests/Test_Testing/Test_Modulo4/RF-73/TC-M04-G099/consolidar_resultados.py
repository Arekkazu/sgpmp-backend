# | Fecha      | Nombre                   | Que se hizo                                                                 |
# |------------|--------------------------|-----------------------------------------------------------------------------|
# | 2026-10-25 | HulkyZeus                | RF-73 TC-M04-G099: consolidador inicial JUnit XML -> schema canónico        |
# | 2026-10-30 | Juan Sebastian Gutierrez | RF-73 TC-M04-G099: D5 mapeo subcasos 305a/b/c y veredicto honesto sin_datos |
"""Convierte JUnit XML de pytest al schema canónico del brief M4 para TC-M04-G099."""
import json
import sys
import xml.etree.ElementTree as ET


def main(junit_path: str, out_json: str) -> None:
    tree = ET.parse(junit_path)
    checkpoints = []
    ok = 0
    falla = 0
    for tc in tree.findall(".//testcase"):
        name = tc.get("name", "unknown")
        # FIX OBS-M04-G086-03 (ElementTree truthiness):
        # Un Element sin hijos es falsy, por lo que "a or b" perdía el failure.
        fail_node = tc.find("failure")
        err_node = tc.find("error")
        failure = fail_node if fail_node is not None else err_node

        if failure is not None:
            estado = "FALLA"
            msg_attr = (failure.get("message") or "").strip()
            txt_body = (failure.text or "").strip()
            obtenido = (msg_attr or txt_body or "(sin mensaje)").replace("\n", " ")[:400]
            falla += 1
        else:
            estado = "OK"
            obtenido = "todos los asserts pasaron"
            ok += 1

        # Poblar "esperado" con el mapeo del subcaso
        esperado = "asserts del subcaso según RF-73 v2.0"
        if "305a" in name:
            esperado = "RF-73 E7 (Caso A): corrección de timestamp futuro (> 60s) a hora servidor y emisión de TIMESTAMP_CORREGIDO (WARNING, motivo=FUTURO)"
        elif "305b" in name:
            esperado = "RF-73 E7 (Caso B): corrección de timestamp desordenado a hora servidor y emisión de TIMESTAMP_CORREGIDO (WARNING, motivo=DESORDENADO)"
        elif "305c" in name:
            esperado = "RF-73 E7 (Caso C): persistencia con hora del servidor sin TIMESTAMP_CORREGIDO al omitir timestamp_evento"
        elif "tc_m04_056" in name or "305" in name:
            esperado = "RF-73 E7: corrección de timestamp futuro/desordenado + TIMESTAMP_CORREGIDO"

        checkpoints.append({
            "paso": name,
            "esperado": esperado,
            "obtenido": obtenido,
            "estado": estado,
        })

    # D5: Veredicto honesto
    if len(checkpoints) == 0:
        veredicto = "sin_datos"
    elif falla > 0:
        veredicto = "RECHAZADO"
    elif ok > 0 and falla == 0:
        veredicto = "APROBADO"
    else:
        veredicto = "RECHAZADO"

    summary = {
        "total": len(checkpoints),
        "ok": ok,
        "falla": falla,
        "veredicto": veredicto,
    }
    result = {
        "tc": "TC-M04-G099",
        "rf": "RF-73",
        "summary": summary,
        "checkpoints": checkpoints,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[OK] {out_json}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
