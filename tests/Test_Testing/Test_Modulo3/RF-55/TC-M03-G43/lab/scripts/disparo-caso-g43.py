"""Un disparo del agente real: FakeLoraSource + evaluar_simple + MqttLink.

No publica command. Serial G43-LAB-001. Umbral fixture 90043.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[8] / ".worktrees" / "sgpmp-rf55-validation" / "raspberry"
# lab/scripts -> lab -> TC-M03-G43 -> RF-55 -> Test_Modulo3 -> Test_Testing -> tests -> sgpmp-backend -> integrador
INTEGRADOR = Path(__file__).resolve().parents[8]
FW = INTEGRADOR / ".worktrees" / "sgpmp-rf55-validation" / "raspberry"
sys.path.insert(0, str(FW))

from edge_agent.agent import Agent  # noqa: E402
from edge_agent.buffer import Buffer  # noqa: E402
from edge_agent.config import FakeVariable, Settings  # noqa: E402
from edge_agent.config_store import ConfigStore, DeviceConfig, Umbral, UmbralStore  # noqa: E402
from edge_agent.historial import Historial  # noqa: E402
from edge_agent.mqtt_client import Connected, Event, MqttLink  # noqa: E402
from edge_agent.reglas.store import ReglaStore  # noqa: E402
from edge_agent.sources import FakeLoraSource  # noqa: E402
import queue  # noqa: E402

SERIAL = "G43-LAB-001"
VARIABLE = "temperatura_ambiente"
UNIDAD = "C"
NIVELES = (
    {"nivel": "normal", "limite_inferior": 18.0, "limite_superior": 24.0},
    {"nivel": "precaucion", "limite_inferior": 24.0, "limite_superior": 28.0},
    {"nivel": "critico", "limite_inferior": 28.0, "limite_superior": 32.0},
)


def umbral_g43() -> Umbral:
    return Umbral(
        id_umbral_ambiental=90043,
        version="fixture-g43-lab",
        variable=VARIABLE,
        unidad=UNIDAD,
        valor_min=18.0,
        valor_max=32.0,
        niveles=NIVELES,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--valor", type=float, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    state = args.state_dir
    state.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        mqtt_host=os.environ.get("EDGE_MQTT_HOST", "127.0.0.1"),
        mqtt_port=int(os.environ.get("EDGE_MQTT_PORT", "1884")),
        mqtt_username=os.environ["EDGE_MQTT_USERNAME"],
        mqtt_password=os.environ["EDGE_MQTT_PASSWORD"],
        mqtt_client_id=f"edge-{SERIAL}-{int(args.valor * 10)}",
        mqtt_ca_cert=None,
        mqtt_keepalive_s=30,
        topic_prefix="sgpmp",
        topic_telemetry="telemetry",
        topic_heartbeat="heartbeat",
        topic_status="status",
        topic_command="command",
        serials=(SERIAL,),
        heartbeat_interval_s=300,
        default_frecuencia_captura_min=60,
        default_intervalo_transmision_min=60,
        buffer_path=state / "buffer.db",
        buffer_max_rows=100,
        state_path=state / "config.json",
        source="fake",
        fake_variables=(FakeVariable(VARIABLE, UNIDAD, args.valor, args.valor),),
        topic_evento="evento",
    )
    events: queue.Queue[Event] = queue.Queue()
    link = MqttLink(settings, events)
    umbrales = UmbralStore(state / "umbrales.json")
    umbrales.set(umbral_g43())
    historial = Historial(state / "historial.db", 1000)
    agent = Agent(
        settings,
        link,
        ConfigStore(settings.state_path, DeviceConfig(60, 60)),
        Buffer(settings.buffer_path, 100),
        FakeLoraSource(settings.fake_variables),
        umbrales=umbrales,
        reglas=ReglaStore(state / "reglas.json"),
        historial=historial,
        reloj_sincronizado=lambda: True,
    )
    link.start()
    conectado = False
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            ev = events.get(timeout=0.5)
        except queue.Empty:
            continue
        agent.handle_event(ev, time.time())
        if isinstance(ev, Connected):
            conectado = True
            break
    if not conectado:
        link.stop()
        args.out.write_text(json.dumps({"ok": False, "error": "sin conexion MQTT"}, indent=2), encoding="utf-8")
        return 2
    ahora = time.time()
    agent.tick(ahora)
    # esperar PUBACK / procesar cola
    fin = time.time() + 8
    while time.time() < fin:
        try:
            ev = events.get(timeout=0.3)
        except queue.Empty:
            continue
        agent.handle_event(ev, time.time())
    filas = historial.recientes() if historial else []
    payload = {
        "ok": True,
        "valor": args.valor,
        "serial": SERIAL,
        "historial": filas[:5],
        "conectado": True,
    }
    args.out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    link.stop()
    historial.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
