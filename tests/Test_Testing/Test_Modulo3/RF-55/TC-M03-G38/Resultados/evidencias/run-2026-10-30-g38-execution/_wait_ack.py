"""Poll MQTT session JSON for ACK_UMBRAL after ISO timestamp. No secrets."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    session = Path(sys.argv[1])
    after = sys.argv[2]
    out = Path(sys.argv[3])
    deadline = time.monotonic() + 35
    found = None
    while time.monotonic() < deadline:
        if session.exists():
            data = json.loads(session.read_text(encoding="utf-8"))
            for ev in data.get("events") or []:
                if ev.get("kind") != "message":
                    continue
                if (ev.get("ts") or "")[:19] < after[:19]:
                    continue
                if ev.get("tipo") != "ACK_UMBRAL" and "ACK_UMBRAL" not in str(ev.get("payload") or ""):
                    continue
                if ev.get("topic", "").endswith("/status") or ev.get("tipo") == "ACK_UMBRAL":
                    found = ev
                    break
            if found:
                break
        time.sleep(0.4)
    resultado = None
    motivo = None
    if found:
        try:
            pl = json.loads(found.get("payload") or "{}")
            resultado = pl.get("resultado")
            motivo = pl.get("motivo") or pl.get("mensaje")
        except Exception:
            pass
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ack_encontrado": found is not None,
        "topic": (found or {}).get("topic"),
        "resultado": resultado,
        "motivo": motivo,
        "evento": found,
    }
    out.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ACK_ENCONTRADO", found is not None, flush=True)
    print("ACK_RESULTADO", resultado, flush=True)
    if resultado == "OK":
        print("STOP_ACK_OK", flush=True)
        return 20
    if not found:
        print("STOP_SIN_ACK", flush=True)
        return 11
    if resultado != "ERROR":
        print("STOP_ACK_NO_ERROR", flush=True)
        return 12
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
