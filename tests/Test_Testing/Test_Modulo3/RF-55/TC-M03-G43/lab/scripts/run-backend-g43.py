"""Arranque uvicorn del backend SGPMP real, acotado al laboratorio G43."""
from __future__ import annotations

import os
import sys

def _ok() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if "sgpmp_g43_test" not in url or "5439" not in url:
        raise SystemExit("ABORT: DATABASE_URL no es sgpmp_g43_test:5439")
    if "/sgpmp?" in url or url.endswith("/sgpmp") or "sgpmp_pr14_test" in url:
        raise SystemExit("ABORT: DATABASE_URL apunta a una base prohibida")
    if not os.environ.get("BROKER_SERVICE_TOKEN"):
        raise SystemExit("ABORT: falta BROKER_SERVICE_TOKEN de laboratorio")


if __name__ == "__main__":
    _ok()
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.environ.get("BACKEND_BIND", "127.0.0.1"),
        port=int(os.environ.get("BACKEND_PORT", "18043")),
        reload=False,
        log_level="info",
    )
