"""RF-26 / INC-M09-26-G86 — Fallo de almacenamiento de logotipo tipado.

Verifica (sin BD):
- un fallo del sistema de archivos al escribir el logotipo sale como
  ``InfrastructureError`` 500 con el mensaje del flujo alterno de RF-26, no
  como un 500 genérico sin información;
- formato no permitido y tamaño excedido siguen rechazándose con 400;
- el contenido real del archivo se valida (no solo el Content-Type
  declarado) y las imágenes se redimensionan a ``DIMENSION_MAX``;
- un SVG con `<script>` se rechaza.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from src.shared.almacen_logos import DIMENSION_MAX, guardar_logo
from src.shared.errors import InfrastructureError, ValidationError


def _png_bytes(size: tuple[int, int] = (10, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, (255, 0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_fallo_de_escritura_se_traduce_a_error_de_almacenamiento(monkeypatch, tmp_path) -> None:
    def _open_que_falla(*args, **kwargs):  # noqa: ANN002, ANN003
        raise OSError("No space left on device")

    monkeypatch.setattr("builtins.open", _open_que_falla)

    with pytest.raises(InfrastructureError) as excinfo:
        guardar_logo(_png_bytes(), "image/png")

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


def test_contenido_que_no_es_una_imagen_real_se_rechaza_aunque_el_content_type_diga_png() -> None:
    with pytest.raises(ValidationError) as excinfo:
        guardar_logo(b"<?php system($_GET['c']); ?>", "image/png")
    assert excinfo.value.code == "FORMATO_IMAGEN_NO_PERMITIDO"


def test_svg_con_script_se_rechaza() -> None:
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    with pytest.raises(ValidationError) as excinfo:
        guardar_logo(svg, "image/svg+xml")
    assert excinfo.value.code == "FORMATO_IMAGEN_NO_PERMITIDO"


def test_svg_valido_se_acepta(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("src.shared.almacen_logos.DIRECTORIO_LOGOS", str(tmp_path / "logos"))

    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="5"/></svg>'
    ruta = guardar_logo(svg, "image/svg+xml")

    assert ruta.endswith(".svg")


def test_logo_valido_escribe_y_devuelve_ruta_publica(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("src.shared.almacen_logos.DIRECTORIO_LOGOS", str(tmp_path / "uploads" / "logos"))
    monkeypatch.setattr("src.shared.almacen_logos.RUTA_PUBLICA_LOGOS", "/uploads/logos")

    ruta = guardar_logo(_png_bytes(), "image/png")

    assert ruta.startswith("/uploads/logos/")
    assert ruta.endswith(".png")
    assert (tmp_path / "uploads" / "logos" / ruta.rsplit("/", 1)[1]).exists()


def test_imagen_mas_grande_que_el_maximo_se_redimensiona(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("src.shared.almacen_logos.DIRECTORIO_LOGOS", str(tmp_path / "logos"))

    ruta = guardar_logo(_png_bytes((DIMENSION_MAX * 3, 100)), "image/png")

    archivo = tmp_path / "logos" / ruta.rsplit("/", 1)[1]
    with Image.open(archivo) as guardada:
        assert max(guardada.size) == DIMENSION_MAX
