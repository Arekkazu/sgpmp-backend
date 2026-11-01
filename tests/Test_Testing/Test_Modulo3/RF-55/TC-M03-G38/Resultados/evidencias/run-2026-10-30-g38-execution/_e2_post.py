"""E2: un POST a broker TEST. Token solo por stdin. Nunca se imprime ni se escribe."""
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
PAYLOAD_PATH = HERE / "payload_e2.json"
HTTP_OUT = HERE / "http_e2_response.json"


def _cargar_payload() -> dict:
    body = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    if body.get("origen") != "umbral":
        raise SystemExit("STOP_ORIGEN")
    if body.get("serial") != SERIAL:
        raise SystemExit("STOP_SERIAL")
    if body.get("id_umbral_ambiental") != 65:
        raise SystemExit("STOP_ID")
    if body.get("variable") != "Humedad Relativa":
        raise SystemExit("STOP_VARIABLE")
    return body


def comprobar() -> int:
    body = _cargar_payload()
    print("MODO comprobar (sin POST, sin token)", flush=True)
    print("BROKER_TEST", URL, flush=True)
    print("METODO POST /v1/commands", flush=True)
    print("SERIAL", body["serial"], flush=True)
    print("ID_UMBRAL", body["id_umbral_ambiental"], flush=True)
    print("VARIABLE", body["variable"], flush=True)
    print("VERSION_COMANDO", body.get("version"), flush=True)
    print("PAYLOAD", PAYLOAD_PATH.name, flush=True)
    return 0


def enviar() -> int:
    token = sys.stdin.readline().rstrip("\n\r")
    if not token:
        print("STOP_SIN_TOKEN", flush=True)
        return 2
    body = _cargar_payload()
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    token = None
    ctx = ssl.create_default_context()
    http: dict = {"url": URL, "method": "POST", "payload_file": PAYLOAD_PATH.name}
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
    HTTP_OUT.write_text(json.dumps(http, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("HTTP_STATUS", http.get("status"), flush=True)
    body_obj = http.get("body")
    if isinstance(body_obj, dict):
        print("HTTP_ESTADO", body_obj.get("estado"), flush=True)
        print("HTTP_MENSAJE", str(body_obj.get("mensaje", ""))[:300], flush=True)
        print("HTTP_TOPIC", body_obj.get("topic"), flush=True)
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    modo = sys.argv[1] if len(sys.argv) > 1 else "comprobar"
    if modo == "comprobar":
        return comprobar()
    if modo == "enviar":
        return enviar()
    print("USO: comprobar | enviar", flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
