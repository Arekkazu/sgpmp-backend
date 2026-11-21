"""Arranque del Gateway real en Windows con SelectorEventLoop (lab G43)."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

url = os.environ.get("DATABASE_URL", "")
if "sgpmp_g43_test" not in url or "5439" not in url:
    raise SystemExit("ABORT gateway: DATABASE_URL no es sgpmp_g43_test:5439")
if os.environ.get("MQTT_HOST") not in {"127.0.0.1", "localhost"} or os.environ.get("MQTT_PORT") != "1884":
    raise SystemExit("ABORT gateway: MQTT no es 127.0.0.1:1884")
if "127.0.0.1:18043" not in os.environ.get("BACKEND_URL", ""):
    raise SystemExit("ABORT gateway: BACKEND_URL no es el backend G43")

broker = Path(__file__).resolve().parents[8] / "_consultas" / "BROKER-MQTT-SGPMP"
sys.path.insert(0, str(broker))
os.chdir(broker)

import uvicorn  # noqa: E402


async def _serve() -> None:
    config = uvicorn.Config(
        "app.main:app",
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "18044")),
        reload=False,
        loop="none",
        http="h11",
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(_serve())
