"""Convierte JUnit XML de pytest al schema canónico del brief M4."""
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

        # Poblar "esperado" con un literal mínimo para no dejarlo vacío
        esperado = "asserts del subcaso según RF-73 v2.0"
        if "tc_m04_273" in name:
            esperado = "RF-73: por_pagina default 50, len(items)=min(50,total)"
        elif "tc_m04_274" in name:
            esperado = "RF-73: por_pagina=200, len(items)=min(200,total)"
        elif "tc_m04_275" in name:
            esperado = "RF-73: por_pagina=201 debe rechazar (422 o 400 según OpenAPI)"

        checkpoints.append({
            "paso": name,
            "esperado": esperado,
            "obtenido": obtenido,
            "estado": estado,
        })

    veredicto = "APROBADO" if falla == 0 and len(checkpoints) > 0 else "RECHAZADO"
    summary = {"total": len(checkpoints), "ok": ok, "falla": falla,
               "veredicto": veredicto}
    result = {"tc": "TC-M04-G089", "summary": summary,
              "checkpoints": checkpoints}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[OK] {out_json}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
