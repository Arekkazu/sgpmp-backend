"""Un POST umbral al broker TEST. Token solo stdin. Payloads e2/e3/e5 sin modificarlos."""
from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://sgpmp-brokertest-zyytic-0f1138-149-130-169-209.sslip.io/v1/commands"
SERIAL = "RASPBERRY3B-TEST"
HERE = Path(__file__).resolve().parent
PERMITIDOS = {
    "e2": HERE / "payload_e2.json",
    "e3": HERE / "payload_e3.json",
    "e5": HERE / "payload_e5.json",
}


def _cargar(escenario: str) -> tuple[dict, Path]:
    path = PERMITIDOS[escenario]
    body = json.loads(path.read_text(encoding="utf-8"))
    if body.get("origen") != "umbral":
        raise SystemExit("STOP_ORIGEN")
    if body.get("serial") != SERIAL:
        raise SystemExit("STOP_SERIAL")
    if body.get("id_umbral_ambiental") != 65:
        raise SystemExit("STOP_ID")
    if body.get("variable") != "Humedad Relativa":
        raise SystemExit("STOP_VARIABLE")
    return body, path


def comprobar(escenario: str) -> int:
    body, path = _cargar(escenario)
    print("MODO comprobar (sin POST)", escenario, flush=True)
    print("BROKER_TEST", URL, flush=True)
    print("METODO POST /v1/commands", flush=True)
    print("SERIAL", body["serial"], flush=True)
    print("PAYLOAD", path.name, flush=True)
    print("VERSION_COMANDO", body.get("version"), flush=True)
    return 0


def enviar(escenario: str) -> int:
    token = sys.stdin.readline().rstrip("\n\r")
    if not token:
        print("STOP_SIN_TOKEN", flush=True)
        return 2
    body, path = _cargar(escenario)
    out = HERE / f"http_{escenario}_response.json"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    token = None
    ctx = ssl.create_default_context()
    http: dict = {"url": URL, "method": "POST", "escenario": escenario, "payload_file": path.name}
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
            raw = resp.read()
            http["status"] = resp.status
            try:
                http["body"] = json.loads(raw.decode("utf-8") or "null")
            except ValueError:
                http["body_raw"] = raw.decode("utf-8", "replace")[:2000]
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        http["status"] = exc.code
        try:
            http["body"] = json.loads(raw.decode("utf-8") or "null")
        except ValueError:
            http["body_raw"] = raw.decode("utf-8", "replace")[:2000]
    except Exception as exc:
        http["status"] = -1
        http["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    http["parada_aplicada"] = False
    body_obj = http.get("body")
    if isinstance(body_obj, dict) and body_obj.get("estado") == "APLICADA":
        http["parada_aplicada"] = True
    out.write_text(json.dumps(http, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("HTTP_STATUS", http.get("status"), flush=True)
    if isinstance(body_obj, dict):
        print("HTTP_ESTADO", body_obj.get("estado"), flush=True)
        print("HTTP_MENSAJE", str(body_obj.get("mensaje", ""))[:300], flush=True)
    st = http.get("status")
    if st in (401, 403):
        print("STOP_AUTH", flush=True)
        return 21
    if http["parada_aplicada"]:
        print("STOP_APLICADA", flush=True)
        return 20
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 3:
        print("USO: comprobar|enviar e2|e3|e5", flush=True)
        return 2
    modo, escenario = sys.argv[1], sys.argv[2].lower()
    if escenario not in PERMITIDOS:
        print("STOP_ESCENARIO", flush=True)
        return 2
    if modo == "comprobar":
        return comprobar(escenario)
    if modo == "enviar":
        return enviar(escenario)
    print("USO: comprobar|enviar e2|e3|e5", flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
