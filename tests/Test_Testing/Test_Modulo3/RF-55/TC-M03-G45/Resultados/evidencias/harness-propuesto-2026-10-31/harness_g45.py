"""Harness temporal G45 / TC-M03-081: Agent real, almacenamiento aislado, sin MQTT.

No toca systemd ni /var/lib/sgpmp-edge. FakeLink solo captura publicaciones
en memoria (no hay broker). FuenteFija solo inyecta Reading; no reimplementa
lecturas_invalidas ni evaluar_lote.

Uso (cuando se autorice la ejecución local, no en la Pi de servicio):

    python harness_g45.py

Requiere el firmware en PYTHONPATH (worktree raspberry/).
"""
from __future__ import annotations

import json
import logging
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FIRMWARE = Path(__file__).resolve().parents[9] / ".worktrees" / "sgpmp-rf55-validation" / "raspberry"
if not (FIRMWARE / "edge_agent").is_dir():
    # integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G45/Resultados/evidencias/harness-...
    FIRMWARE = Path(r"c:\Users\ll529\OneDrive\Documentos\integrador\.worktrees\sgpmp-rf55-validation\raspberry")
sys.path.insert(0, str(FIRMWARE))

from edge_agent.agent import Agent, _es_finito  # noqa: E402
from edge_agent.buffer import Buffer  # noqa: E402
from edge_agent.config import Settings  # noqa: E402
from edge_agent.config_store import ConfigStore, DeviceConfig, Umbral, UmbralStore  # noqa: E402
from edge_agent.historial import Historial  # noqa: E402
from edge_agent.reglas.evaluador import lecturas_invalidas  # noqa: E402
from edge_agent.reglas.store import ReglaStore  # noqa: E402
from edge_agent.sources import Reading  # noqa: E402

SERIAL = "QA-G45-HARNESS"
T0 = 1_750_000_000.0
HERE = Path(__file__).resolve().parent


class FakeLink:
    """Doble de transporte MQTT: no conecta. No contiene lógica RF-55."""

    def __init__(self) -> None:
        self.connected = True
        self.published: list[tuple[str, dict]] = []
        self._mid = 1

    def publish(self, topic: str, payload: bytes, qos: int = 1) -> int | None:
        self.published.append((topic, json.loads(payload)))
        mid = self._mid
        self._mid += 1
        return mid


class FuenteFija:
    """DataSource que entrega un lote y se agota. No valida valores."""

    def __init__(self, lecturas: list[Reading]) -> None:
        self._lecturas = lecturas

    def read(self, serial: str, now: datetime) -> list[Reading]:
        out, self._lecturas = self._lecturas, []
        return out

    def is_alive(self, serial: str, now: datetime, max_silence_s: float) -> bool:
        return True

    def status(self, serial: str) -> dict:
        return {}

    def apply_config(self, serial: str, config: object) -> None:
        pass


def _valor(valor: Any) -> Any:
    if isinstance(valor, int | float) and not isinstance(valor, bool):
        return float(valor)
    return valor


def _reading(item: dict, ahora: float) -> Reading:
    return Reading(
        serial=SERIAL,
        variable=item["variable"],
        valor_crudo=_valor(item["valor"]),
        unidad=item.get("unidad", ""),
        timestamp_captura=datetime.fromtimestamp(ahora, UTC),
    )


def _settings(tmp: Path) -> Settings:
    return Settings(
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="qa-g45",
        mqtt_password="unused-local-only",
        mqtt_client_id="edge-qa-g45",
        mqtt_ca_cert=None,
        mqtt_keepalive_s=60,
        topic_prefix="sgpmp",
        topic_telemetry="telemetry",
        topic_heartbeat="heartbeat",
        topic_status="status",
        topic_command="command",
        serials=(SERIAL,),
        heartbeat_interval_s=300,
        default_frecuencia_captura_min=1,
        default_intervalo_transmision_min=1,
        buffer_path=tmp / "buffer.db",
        buffer_max_rows=1000,
        state_path=tmp / "config.json",
        source="fake",
        fake_variables=(),
        firmware_version="qa-g45-harness",
    )


def _cargar_umbral(store: UmbralStore, spec: dict) -> None:
    store.set(
        Umbral(
            id_umbral_ambiental=spec["id_umbral_ambiental"],
            version=spec.get("version"),
            variable=spec["variable"],
            unidad=spec["unidad"],
            valor_min=spec["valor_min"],
            valor_max=spec["valor_max"],
            niveles=tuple(spec["niveles"]),
        )
    )


def correr_escenario(spec: dict, umbral_t: dict, tmp: Path) -> dict:
    lecturas = [_reading(x, T0) for x in spec["lecturas"]]
    invalidas = lecturas_invalidas(lecturas, {})
    settings = _settings(tmp)
    link = FakeLink()
    buffer = Buffer(settings.buffer_path, settings.buffer_max_rows)
    historial = Historial(settings.historial_path, settings.historial_max_filas)
    umbrales = UmbralStore(tmp / "umbrales.json")
    _cargar_umbral(umbrales, umbral_t)
    reglas = ReglaStore(tmp / "reglas.json")
    store = ConfigStore(
        settings.state_path,
        DeviceConfig(settings.default_frecuencia_captura_min, settings.default_intervalo_transmision_min),
    )
    agent = Agent(
        settings,
        link,
        store,
        buffer,
        FuenteFija(lecturas),
        umbrales=umbrales,
        reglas=reglas,
        historial=historial,
        reloj_sincronizado=lambda: True,
        clock=lambda: T0,
    )
    log = logging.getLogger("edge_agent")
    with _CaptureLog(log) as warnings:
        agent.tick(T0)
        agent.tick(T0 + 15 * 60)

    filas = historial.recientes()
    eventos = [p for t, p in link.published if t.endswith("/evento")]
    telemetria = [p for t, p in link.published if t.endswith("/telemetry")]
    buffer.close()
    historial.close()
    return {
        "id": spec["id"],
        "entrada": spec["lecturas"],
        "validacion": [
            {
                "variable": r.variable,
                "valor": None if r.valor_crudo is None else (r.valor_crudo if isinstance(r.valor_crudo, bool | str) else r.valor_crudo),
                "es_finito": _es_finito(r.valor_crudo),
                "invalida": True,
                "motivo": motivo,
            }
            for r, motivo in invalidas
        ],
        "lecturas_es_finito": [
            {"variable": r.variable, "valor_repr": repr(r.valor_crudo), "es_finito": _es_finito(r.valor_crudo)}
            for r in lecturas
        ],
        "historial": [
            {
                "clasificacion": f["clasificacion"],
                "severidad": f.get("severidad"),
                "ruta": f.get("ruta"),
                "estado": f.get("estado"),
                "variables": f.get("variables"),
                "detalle": f.get("detalle"),
            }
            for f in filas
        ],
        "eventos": [
            {
                "clasificacion_rf55": e.get("clasificacion_rf55"),
                "severidad": e.get("severidad"),
                "regla_aplicada": (e.get("metadata_edge") or {}).get("regla_aplicada"),
                "variable": (e.get("metadata_edge") or {}).get("variable"),
            }
            for e in eventos
        ],
        "telemetria": [{"variable": t.get("variable"), "valor_crudo": t.get("valor_crudo")} for t in telemetria],
        "warnings_rf55": [w for w in warnings if "descartada para RF-55" in w],
        "paths": {
            "tmp": str(tmp),
            "historial": str(settings.historial_path),
            "buffer": str(settings.buffer_path),
        },
    }


class _CaptureLog:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.lines: list[str] = []

    def __enter__(self) -> list[str]:
        self._handler = logging.Handler()
        recs = self.lines

        class H(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                recs.append(record.getMessage())

        self._h = H()
        self.logger.addHandler(self._h)
        self.logger.setLevel(logging.WARNING)
        return self.lines

    def __exit__(self, *args: object) -> None:
        self.logger.removeHandler(self._h)


def main() -> int:
    casos = json.loads((HERE / "escenarios_p1_p4.json").read_text(encoding="utf-8"))
    umbral = casos["umbral_temperatura_casos_rf55"]
    informes = []
    with tempfile.TemporaryDirectory(prefix="g45-harness-") as raw:
        root = Path(raw)
        for spec in casos["escenarios"]:
            informes.append(correr_escenario(spec, umbral, root / spec["id"]))
    out = HERE / "resultado_local.json"
    out.write_text(json.dumps(informes, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"escrito {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
