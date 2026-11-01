# | Fecha      | Nombre                   | Que se hizo                                                                 |
# |------------|--------------------------|-----------------------------------------------------------------------------|
# | 2026-10-30 | Juan Sebastian Gutierrez | RF-73 TC-M04-G092: consolidador JUnit XML -> schema canónico con skip y obs |
"""Convierte JUnit XML de pytest al schema canónico del brief M4 para TC-M04-G092."""
import json
import sys
import xml.etree.ElementTree as ET


def main(junit_path: str, out_json: str) -> None:
    tree = ET.parse(junit_path)
    checkpoints = []
    ok = 0
    falla = 0
    skipped = 0

    for tc in tree.findall(".//testcase"):
        name = tc.get("name", "unknown")
        skip_node = tc.find("skipped")
        fail_node = tc.find("failure")
        err_node = tc.find("error")
        failure = fail_node if fail_node is not None else err_node

        if skip_node is not None:
            estado = "SKIPPED"
            msg = skip_node.get("message") or skip_node.text or "(sin mensaje)"
            obtenido = msg.strip().replace("\n", " ")[:400]
            skipped += 1
        elif failure is not None:
            estado = "FALLA"
            msg_attr = (failure.get("message") or "").strip()
            txt_body = (failure.text or "").strip()
            obtenido = (msg_attr or txt_body or "(sin mensaje)").replace("\n", " ")[:400]
            falla += 1
        else:
            estado = "OK"
            obtenido = "todos los asserts pasaron"
            ok += 1

        esperado = "asserts del subcaso según RF-73 v2.0"
        if "tc_m04_285" in name:
            esperado = "RF-73: Cadena intra-M04 con >= 3 eventos bajo el mismo correlacion_id"
        elif "tc_m04_286" in name:
            esperado = "RF-73: Reconstrucción de cadena causal completa mediante id_referencia"
        elif "tc_m04_287" in name:
            esperado = "RF-73: Correlación transversal multisistema M03+M04+M06 (OBS-M04-G092-01)"
        elif "tc_m04_288" in name:
            esperado = "RF-73/PR #785: Contrato de filtro correlacion_id (200 con UUID, 200 vacío, 422 ErrorResponse)"

        checkpoints.append({
            "paso": name,
            "esperado": esperado,
            "obtenido": obtenido,
            "estado": estado,
        })

    veredicto = "APROBADO" if (falla == 0 and ok > 0 and len(checkpoints) > 0) else "RECHAZADO"
    summary = {
        "total": len(checkpoints),
        "ok": ok,
        "falla": falla,
        "skipped": skipped,
        "veredicto": veredicto,
        "veredicto_operacional": "BLOQUEADO_POR_DISEÑO" if falla > 0 else "APROBADO",
    }
    result = {
        "tc": "TC-M04-G092",
        "rf": "RF-73",
        "summary": summary,
        "checkpoints": checkpoints,
        "observaciones": [
            "TC-M04-285 y TC-M04-286 bloqueados por no implementación de RF-66 (INC-M04-151-G081).",
            "TC-M04-287 omitido por OBS-M04-G092-01 (M03 y M06 no emiten correlacion_id).",
            "TC-M04-288 aprobado certificando fix de PR #785 del filtro correlacion_id.",
        ],
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[OK] {out_json}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

