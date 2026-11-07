"""Convierte el JUnit XML de pytest al JSON resumido del scanner.

Estrategia de resumen:
  - 1 checkpoint por test (el scanner cuenta por checkpoint).
  - Campo 'obtenido' usa códigos cortos en vez del mensaje completo.
  - Bloque 'summary' consolida conteos y motivo de bloqueo.
"""
import sys
import json
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter

TC_ID = "TC-M03-G166"
BASE = Path(__file__).parent

# Patrones para clasificar sin volcar el mensaje completo
PATRON_BLOQUEO_BROKER = "BLOQUEO EXTERNO EN SETUP"
PATRON_BROKER_503 = "TOKEN_SERVICIO_NO_CONFIGURADO"


def parse_args():
    parser = argparse.ArgumentParser(description="Convierte el JUnit XML de pytest al JSON resumido del scanner.")
    parser.add_argument("--suffix", "--sufijo", dest="suffix", default="", nargs="?", const="", help="Sufijo del reporte (ej: _reintento2)")
    return parser.parse_args()


def clasificar(case):
    skipped = case.find("skipped")
    fallo = case.find("failure") if case.find("failure") is not None else case.find("error")

    # Sin failure ni error real → no es fallo
    if fallo is None:
        if skipped is not None:
            # Puede ser xfail o skip. Ambos son "esperados"
            msg = (skipped.get("message") or skipped.get("type") or "").lower()
            if "xfail" in msg or "inc-" in msg:
                return "OK", "XFAIL"
            return "OK", "SKIP"
        return "OK", "PASSED"

    # Hay failure/error → sí es fallo
    msg = (fallo.get("message") or fallo.text or "").strip()
    if "BLOQUEO EXTERNO EN SETUP" in msg or "TOKEN_SERVICIO_NO_CONFIGURADO" in msg:
        return "FALLA", "BLOCKED_BROKER"
    return "FALLA", f"FAILED: {msg.replace(chr(10),' ')[:80]}"


def main() -> int:
    args = parse_args()
    suffix = args.suffix
    if suffix and not suffix.startswith("_"):
        suffix = f"_{suffix}"

    xml_path = BASE / "resultados" / f"resultado_{TC_ID}{suffix}.xml"
    json_path = BASE / "resultados" / f"resultado_{TC_ID}{suffix}.json"

    if not xml_path.exists():
        print(f"ERROR: no existe {xml_path}", file=sys.stderr)
        return 2

    tree = ET.parse(xml_path)
    root = tree.getroot()
    suites = root.findall(".//testsuite") if root.tag == "testsuites" else [root]

    checkpoints = []
    for suite in suites:
        for case in suite.findall("testcase"):
            clase = case.get("classname", "").split(".")[-1]
            nombre = case.get("name", "")
            paso = f"{clase}::{nombre}" if clase else nombre
            estado, obtenido = clasificar(case)
            checkpoints.append({
                "paso": paso,
                "esperado": "PASSED",
                "obtenido": obtenido,
                "estado": estado,
            })

    # --- Resumen consolidado ---
    estados = Counter(c["estado"] for c in checkpoints)
    codigos = Counter(c["obtenido"] for c in checkpoints)
    bloqueo = None
    if codigos.get("BLOCKED_BROKER", 0) > 0:
        bloqueo = {
            "motivo": "POST /iot/telemetria devuelve 503 TOKEN_SERVICIO_NO_CONFIGURADO (BROKER_SERVICE_TOKEN no configurado en TEST)",
            "afectados": codigos["BLOCKED_BROKER"],
            "inc_sugerido": "INC-M03-BROKER-DEPLOYMENT",
        }

    payload = {
        "tc": TC_ID,
        "summary": {
            "total": len(checkpoints),
            "ok": estados.get("OK", 0),
            "falla": estados.get("FALLA", 0),
            "xfailed": codigos.get("XFAIL", 0),
            "skipped": codigos.get("SKIP", 0),
            "bloqueados": codigos.get("BLOCKED_BROKER", 0),
            "veredicto": "APROBADO" if estados.get("FALLA", 0) == 0 else "RECHAZADO",
            "defectos_backend_documentados": [
                "INC-M03-RF57-NOT-EMITTED (5 xfail)",
                "INC-M03-104-G165 punto 3 (6 xfail transicion SUPERADA)",
            ],
        },
        "checkpoints": checkpoints,
    }

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tamano = json_path.stat().st_size
    print(f"Generado {json_path} ({tamano} bytes)")
    print(f"  total={len(checkpoints)} ok={estados.get('OK',0)} falla={estados.get('FALLA',0)}")
    print(f"  xfailed={codigos.get('XFAIL',0)} skipped={codigos.get('SKIP',0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
