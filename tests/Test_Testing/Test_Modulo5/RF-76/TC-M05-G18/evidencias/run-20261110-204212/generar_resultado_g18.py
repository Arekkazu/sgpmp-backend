"""Genera resultado_TC-M05-G18.json a partir de junit_TC-M05-G18.xml y trazas_tc_m05_g18.json."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET


def generar_resultado(run_dir: Path) -> dict:
    """Construye y valida el resumen oficial JSON a partir del JUnit XML y las trazas."""
    junit_path = run_dir / "junit_TC-M05-G18.xml"
    trazas_path = run_dir / "trazas_tc_m05_g18.json"
    out_path = run_dir / "resultado_TC-M05-G18.json"

    tree = ET.parse(junit_path)
    root = tree.getroot()
    testcases = root.findall(".//testcase")
    trazas = json.loads(trazas_path.read_text(encoding="utf-8"))

    if len(testcases) != len(trazas):
        raise ValueError(
            f"Incoherencia entre JUnit ({len(testcases)}) y trazas ({len(trazas)})."
        )

    checkpoints: list[dict[str, str]] = []
    ok_count = 0
    falla_count = 0

    for testcase, traza in zip(testcases, trazas):
        xml_fallo = testcase.find("failure") is not None or testcase.find("error") is not None
        xml_estado = "FALLA" if xml_fallo else "OK"
        traza_estado = traza["estado"]
        if xml_estado != traza_estado:
            raise ValueError(
                f"Estado divergente en {traza['test']}: XML={xml_estado} vs traza={traza_estado}"
            )

        if traza_estado == "OK":
            ok_count += 1
        else:
            falla_count += 1

        checkpoints.append(
            {
                "paso": (
                    f"{traza['test']} (plano {traza['caso_plano']} / orig {traza['caso_original']}) "
                    f"- {testcase.attrib['name']}"
                ),
                "esperado": traza["esperado"],
                "obtenido": traza["obtenido"],
                "estado": traza_estado,
            }
        )

    veredicto = "Aprobado" if falla_count == 0 and len(checkpoints) > 0 else "Rechazado"
    payload = {
        "tc": "TC-M05-G18",
        "summary": {
            "total": len(checkpoints),
            "ok": ok_count,
            "falla": falla_count,
            "veredicto": veredicto,
        },
        "checkpoints": checkpoints,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    resultado = generar_resultado(Path(__file__).resolve().parent)
    print(json.dumps(resultado["summary"], ensure_ascii=False))
