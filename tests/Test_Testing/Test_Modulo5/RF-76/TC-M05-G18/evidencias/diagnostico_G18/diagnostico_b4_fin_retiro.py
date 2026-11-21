"""Diagnostico B4 (TC-M05-G18): prueba aislada de NotificacionMedicamentoEmailAdapter (sin BD ni SMTP)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[7]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.supplies.infrastructure.adapters.notificacion_medicamento_email_adapter as adapter_mod
from src.supplies.infrastructure.adapters.notificacion_medicamento_email_adapter import (
    NotificacionMedicamentoEmailAdapter,
)

ACTIVO_ID = 853
VET_USER_ID = 301
PRODUCTOR_CORREO = "productor.g18@finca.example"
VET_CORREO = "veterinario.g18@finca.example"


class _FakeResult:
    def __init__(self, row: Optional[Any]) -> None:
        self._row = row

    def fetchone(self) -> Optional[Any]:
        return self._row


class _FakeSessionSinBD:
    """Sesion falsa con las mismas respuestas SQL usadas en TC-M05-G18."""

    def execute(self, stmt: Any, _params: Optional[dict[str, Any]] = None) -> _FakeResult:
        sql = str(stmt)
        if "modulo2.activos_biologicos" in sql:
            return _FakeResult(
                SimpleNamespace(nombre="Carlos", apellidos="Productor", correo_electronico=PRODUCTOR_CORREO)
            )
        if "modulo1.usuarios" in sql:
            return _FakeResult(
                SimpleNamespace(nombre="Dra. Ana", apellidos="Veterinaria", correo_electronico=VET_CORREO)
            )
        return _FakeResult(None)


def main() -> None:
    enviados_fin: list[dict[str, str]] = []
    enviados_inicio: list[dict[str, str]] = []
    bucket_actual = enviados_fin

    def _fake_send_email(*, to: str, subject: str, html_body: str) -> None:
        bucket_actual.append({"to": to, "subject": subject, "len_html": str(len(html_body))})

    orig_send = adapter_mod.send_email
    adapter_mod.send_email = _fake_send_email
    try:
        adapter = NotificacionMedicamentoEmailAdapter(_FakeSessionSinBD())  # type: ignore[arg-type]

        bucket_actual = enviados_fin
        adapter.notificar_fin_retiro(id_activo=ACTIVO_ID, fecha_fin_retiro=date(2026, 11, 10))

        bucket_actual = enviados_inicio
        adapter.notificar_inicio_retiro(
            id_activo=ACTIVO_ID,
            id_usuario_veterinario=VET_USER_ID,
            nombre_medicamento="Oxitetraciclina-20",
            fecha_fin_retiro=date(2026, 11, 14),
        )
    finally:
        adapter_mod.send_email = orig_send

    print(f"notificar_fin_retiro destinatarios={[x['to'] for x in enviados_fin]} detalle={enviados_fin}")
    print(f"notificar_inicio_retiro destinatarios={[x['to'] for x in enviados_inicio]} detalle={enviados_inicio}")


if __name__ == "__main__":
    main()
