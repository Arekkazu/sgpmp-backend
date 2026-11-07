"""Monitor MQTT v5. No publish. Stop when STOP file exists or timeout."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

OUT = Path(sys.argv[1])
STOP = Path(sys.argv[2])
TIMEOUT = float(sys.argv[3]) if len(sys.argv) > 3 else 120.0
TOPICS = ["sgpmp/RASPBERRY3B-TEST/#", "sgpmp/QA-M03-272-A-088894/#"]


def rc_int(c):
    if c is None:
        return -1
    if hasattr(c, "value"):
        try:
            return int(c.value)
        except Exception:
            pass
    try:
        return int(c)
    except Exception:
        return -1


def main() -> int:
    events = []
    connected = {"rc": None}
    granted = []

    def dump():
        OUT.write_text(
            json.dumps(
                {
                    "connect_rc": connected["rc"],
                    "subacks": granted,
                    "events": events,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def on_connect(c, u, f, rc, p=None):
        connected["rc"] = rc_int(rc)
        events.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": "connect",
                "rc": connected["rc"],
                "reason": str(rc),
            }
        )
        dump()
        if connected["rc"] == 0:
            for t in TOPICS:
                _, mid = c.subscribe(t, 1)
                events.append(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "kind": "subscribe_sent",
                        "topic": t,
                        "mid": mid,
                    }
                )

    def on_sub(c, u, mid, rcs, p=None):
        g = [rc_int(x) for x in rcs]
        granted.append({"mid": mid, "granted": g, "reasons": [str(x) for x in rcs]})
        events.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": "suback",
                "mid": mid,
                "granted": g,
                "reasons": [str(x) for x in rcs],
            }
        )
        dump()
        if len(granted) >= 2 and all(x["granted"] == [1] for x in granted):
            print("SUBACK_READY", flush=True)

    def on_msg(c, u, m):
        pl = m.payload.decode("utf-8", "replace")[:4000]
        tipo = ""
        try:
            d = json.loads(pl)
            tipo = d.get("tipo_mensaje") or ""
        except Exception:
            pass
        events.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": "message",
                "topic": m.topic,
                "tipo": tipo,
                "payload": pl,
            }
        )
        dump()
        print("MSG", m.topic, tipo, flush=True)

    cl = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"qa-g38-e2-mon-{int(time.time())}",
        protocol=mqtt.MQTTv5,
    )
    cl.username_pw_set(os.environ["MQTT_USERNAME"].strip(), os.environ["MQTT_PASSWORD"])
    cl.on_connect = on_connect
    cl.on_subscribe = on_sub
    cl.on_message = on_msg
    cl.reconnect_delay_set(3600, 3600)
    cl.connect(os.environ["MQTT_HOST"].strip(), int(os.environ["MQTT_HOST_PORT"]), 30)
    cl.loop_start()
    t0 = time.monotonic()
    while time.monotonic() - t0 < TIMEOUT:
        if STOP.exists():
            break
        time.sleep(0.2)
    cl.loop_stop()
    cl.disconnect()
    dump()
    print("MONITOR_END", connected["rc"], "msgs", sum(1 for e in events if e["kind"] == "message"), flush=True)
    return 0 if connected["rc"] == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
