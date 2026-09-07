"""RF-26 / INC-M09-26-G86 — Fallo de almacenamiento de logotipo tipado.

Verifica (sin BD):
- un fallo del sistema de archivos al escribir el logotipo sale como
  ``InfrastructureError`` 500 con el mensaje del flujo alterno de RF-26, no
  como un 500 genérico sin información;
- formato no permitido y tamaño excedido siguen rechazándose con 400.
"""
from __future__ import annotations

import pytest

from src.shared.almacen_logos import guardar_logo
from src.shared.errors import InfrastructureError, ValidationError


def test_fallo_de_escritura_se_traduce_a_error_de_almacenamiento(monkeypatch, tmp_path) -> None:
    # Fuerza que el directorio de logos se resuelva dentro de un tmp_path de solo
    # lectura simulada: hacemos que open() falle con OSError.
    def _open_que_falla(*args, **kwargs):  # noqa: ANN002, ANN003
        raise OSError("No space left on device")

    monkeypatch.setattr("builtins.open", _open_que_falla)

    with pytest.raises(InfrastructureError) as excinfo:
        guardar_logo(b"\x89PNG\r\n\x1a\n", "image/png")

    assert excinfo.value.code == "ERROR_ALMACENAMIENTO"
    assert "No se pudo guardar el logotipo" in excinfo.value.message


def test_formato_no_permitido_se_rechaza_con_400() -> None:
    with pytest.raises(ValidationError) as excinfo:
        guardar_logo(b"GIF89a", "image/gif")
    assert excinfo.value.code == "FORMATO_IMAGEN_NO_PERMITIDO"


def test_tamano_excedido_se_rechaza_con_400() -> None:
    with pytest.raises(ValidationError) as excinfo:
        guardar_logo(b"\x00" * (2 * 1024 * 1024 + 1), "image/png")
    assert excinfo.value.code == "TAMANO_IMAGEN_EXCEDIDO"


def test_logo_valido_escribe_y_devuelve_ruta_publica(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("src.shared.almacen_logos.DIRECTORIO_LOGOS", str(tmp_path / "uploads" / "logos"))
    monkeypatch.setattr("src.shared.almacen_logos.RUTA_PUBLICA_LOGOS", "/uploads/logos")

    ruta = guardar_logo(b"\x89PNG\r\n\x1a\ncontenido", "image/png")

    assert ruta.startswith("/uploads/logos/")
    assert ruta.endswith(".png")
    assert (tmp_path / "uploads" / "logos" / ruta.rsplit("/", 1)[1]).exists()
