"""TC-M03-G63 — RF-56 / CU-02.

Subcaso: TC-M03-125.
Matriz: rechazar HTTP plano y TLS obsoleto hacia M04; ningún paquete en claro.

Esto no valida TLS. MotorInferenciaPort.enviar_paquete(bool) no abre canal.
Ver NOTA_TECNICA_TLS.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_NOTA = Path(__file__).with_name("NOTA_TECNICA_TLS.md")

_ESCENARIOS = (
    {
        "id": "http_plano",
        "accion": "forzar envío del paquete por HTTP sin TLS hacia M04",
        "esperado": "conexión rechazada; ningún paquete transmitido en claro",
        "falta": "cliente M04 con política de canal; endpoint TLS; entorno autorizado",
    },
    {
        "id": "tls_obsoleto",
        "accion": "forzar versión TLS obsoleta hacia M04",
        "esperado": "conexión rechazada; ningún paquete transmitido",
        "falta": "configuración TLS del cliente (versión mínima acordada) y certificados de prueba",
    },
)


@pytest.mark.parametrize("escenario", _ESCENARIOS, ids=lambda s: s["id"])
def test_tc_m03_125_canal_hacia_m04(escenario: dict) -> None:
    pytest.skip(
        f"BLOQUEADO TC-M03-125 ({escenario['id']}): {escenario['accion']}. "
        f"Esperado: {escenario['esperado']}. Falta: {escenario['falta']}. "
        f"Nota técnica: {_NOTA.name} (no es evidencia TLS). "
        "Fuera de alcance: inspección del stub, testssl/sslyze, HTTP plano contra "
        "despliegue compartido, cambio de certificados."
    )
