"""RF-101 5.9: /token limita los intentos antes de comparar el secreto con bcrypt."""
from types import SimpleNamespace

import pytest

from src.accounting_integration.application.use_cases.canal import emitir_token_canal_use_case as modulo
from src.accounting_integration.application.use_cases.canal.emitir_token_canal_use_case import EmitirTokenCanalUseCase
from src.shared.errors import AuthenticationError, TooManyRequestsError
from src.shared.rate_limit import registrar_llamada


class _Clientes:
    def __init__(self):
        self.consultas = 0

    def obtener_por_identificador(self, client_id):
        self.consultas += 1
        return SimpleNamespace(id_cliente_externo=1)

    def credencial_activa(self, id_cliente):
        return SimpleNamespace(hash_secreto="$2b$12$" + "x" * 53)


def _caso(clientes, eventos):
    return EmitirTokenCanalUseCase(clientes, SimpleNamespace(), lambda *a: ("t", 60), registrar_llamada, eventos.append)


def test_por_ip_corta_antes_de_bcrypt_y_sin_auditar(monkeypatch):
    comparaciones = []
    monkeypatch.setattr(modulo.secreto_cliente, "coincide", lambda *a: comparaciones.append(a) or False)
    clientes, eventos = _Clientes(), []
    caso = _caso(clientes, eventos)
    for _ in range(modulo.INTENTOS_TOKEN_POR_IP):
        with pytest.raises(AuthenticationError):
            caso.execute("cliente-prueba-ip", "malo", "a@b.co", "203.0.113.7")
    with pytest.raises(TooManyRequestsError) as exc:
        caso.execute("cliente-prueba-ip", "malo", "a@b.co", "203.0.113.7")
    assert "Retry-After" in exc.value.headers
    assert len(comparaciones) == modulo.INTENTOS_TOKEN_POR_IP
    assert clientes.consultas == modulo.INTENTOS_TOKEN_POR_IP
    assert len(eventos) == modulo.INTENTOS_TOKEN_POR_IP


def test_por_client_id_aunque_cambie_la_ip(monkeypatch):
    monkeypatch.setattr(modulo.secreto_cliente, "coincide", lambda *a: False)
    caso = _caso(_Clientes(), [])
    for i in range(modulo.INTENTOS_TOKEN_POR_CLIENT_ID):
        with pytest.raises(AuthenticationError):
            caso.execute("cliente-prueba-distribuido", "malo", "a@b.co", f"198.51.100.{i}")
    with pytest.raises(TooManyRequestsError):
        caso.execute("cliente-prueba-distribuido", "malo", "a@b.co", "198.51.100.250")
