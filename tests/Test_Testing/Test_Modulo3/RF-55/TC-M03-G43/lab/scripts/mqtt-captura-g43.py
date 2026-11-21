"""Suscriptor de evidencia G43: evento y command. No publica."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("mqtt-captura.jsonl")


def main() -> int:
    host = os.environ["MQTT_HOST"]
    port = int(os.environ["MQTT_PORT"])
    user = os.environ["MQTT_USERNAME"]
    password = os.environ["MQTT_PASSWORD"]
    prefix = os.environ.get("MQTT_TOPIC_PREFIX", "sgpmp")
    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id="g43-lab-sniffer",
        clean_session=True,
    )
    client.username_pw_set(user, password)
    received: list[dict] = []

    def on_message(_c, _u, msg: mqtt.MQTTMessage) -> None:
        try:
            cuerpo = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            cuerpo = {"_raw": msg.payload.decode("utf-8", "replace")}
        fila = {"ts": time.time(), "topic": msg.topic, "payload": cuerpo}
        received.append(fila)
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False, default=str) + "\n")

    client.on_message = on_message
    client.connect(host, port, keepalive=30)
    client.subscribe([(f"{prefix}/+/evento", 1), (f"{prefix}/+/command", 1)])
    client.loop_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
