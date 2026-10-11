"""INC-M01-12-107: la IP del cliente sale de `request.client` (resuelta por
uvicorn con FORWARDED_ALLOW_IPS), no del X-Forwarded-For que mande el cliente."""
from starlette.requests import Request

from src.shared.middlewares import _get_client_ip


def _request(client, xff=None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "client": client, "headers": headers})


def test_ignora_x_forwarded_for_falsificado() -> None:
    assert _get_client_ip(_request(("200.1.2.3", 5000), xff="6.6.6.6")) == "200.1.2.3"


def test_sin_cliente_devuelve_none() -> None:
    assert _get_client_ip(_request(None)) is None
