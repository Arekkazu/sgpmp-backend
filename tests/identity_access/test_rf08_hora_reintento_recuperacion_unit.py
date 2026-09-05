"""Regresión unitaria RF-08 para la hora informada al superar el rate limit."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.identity_access.application.use_cases.contrasena import (
    solicitar_recuperacion_use_case as modulo,
)
from src.shared.errors import BusinessRuleError


IP = "203.0.113.49"
AHORA = datetime(2026, 9, 5, 15, 0, 0, tzinfo=timezone.utc)
PRIMERA_SOLICITUD = datetime(2026, 9, 5, 14, 12, 34, tzinfo=timezone.utc)


class FechaHoraFija(datetime):
    @classmethod
    def now(cls, tz=None):
        return AHORA if tz is not None else AHORA.replace(tzinfo=None)


class EventosRepoFake:
    def __init__(self) -> None:
        self.consultas_conteo = []
        self.consultas_primera = []

    def contar_solicitudes_recuperacion_por_ip(self, ip, desde):
        self.consultas_conteo.append((ip, desde))
        return modulo.MAX_SOLICITUDES_POR_HORA

    def obtener_primera_solicitud_recuperacion_por_ip(self, ip, desde):
        self.consultas_primera.append((ip, desde))
        return PRIMERA_SOLICITUD


class RepoNoDebeConsultarse:
    def obtener_por_correo(self, _correo):
        raise AssertionError("El rate limit debe detener el flujo antes de buscar al usuario")


class DbNoDebeEscribir:
    def commit(self):
        raise AssertionError("El rate limit no debe confirmar transacciones")

    def rollback(self):
        raise AssertionError("El rate limit no debe abrir una operación para revertir")


def test_informa_primera_solicitud_mas_una_hora(monkeypatch) -> None:
    monkeypatch.setattr(modulo, "datetime", FechaHoraFija)
    eventos = EventosRepoFake()
    use_case = modulo.SolicitarRecuperacionUseCase(
        usuarios_repo=RepoNoDebeConsultarse(),
        cuentas_repo=RepoNoDebeConsultarse(),
        eventos_repo=eventos,
        db=DbNoDebeEscribir(),
    )

    with pytest.raises(BusinessRuleError) as capturado:
        use_case.execute(
            SimpleNamespace(correo_electronico="persona@example.com"),
            IP,
        )

    error = capturado.value
    inicio_ventana = datetime(2026, 9, 5, 14, 0, 0, tzinfo=timezone.utc)
    assert error.code == "LIMITE_SOLICITUDES_EXCEDIDO"
    assert "15:12:34" in error.message
    assert "15:00:00" not in error.message
    assert eventos.consultas_conteo == [(IP, inicio_ventana)]
    assert eventos.consultas_primera == [(IP, inicio_ventana)]
