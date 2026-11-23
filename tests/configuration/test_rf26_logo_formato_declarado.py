"""RF-26: al subir el logo, Pillow solo usa el decodificador del formato declarado."""
import io

import pytest
from PIL import Image

from src.shared import almacen_logos
from src.shared.errors import UnsupportedMediaTypeError


def _imagen(formato: str) -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (8, 8), "green").save(salida, format=formato)
    return salida.getvalue()


@pytest.mark.parametrize("formato", ["BMP", "TGA", "GIF", "TIFF"])
def test_otro_formato_declarado_como_png_no_se_decodifica(formato, monkeypatch):
    llamadas = []
    original = Image.open

    def espia(fp, mode="r", formats=None):
        llamadas.append(formats)
        return original(fp, mode, formats)

    monkeypatch.setattr(almacen_logos.Image, "open", espia)
    with pytest.raises(UnsupportedMediaTypeError) as exc:
        almacen_logos._validar_y_redimensionar_raster(_imagen(formato), "image/png")
    assert exc.value.code == "FORMATO_IMAGEN_NO_PERMITIDO"
    assert llamadas and all(f == ["PNG"] for f in llamadas)


def test_png_y_jpeg_validos_siguen_pasando():
    for formato, tipo in (("PNG", "image/png"), ("JPEG", "image/jpeg")):
        resultado = almacen_logos._validar_y_redimensionar_raster(_imagen(formato), tipo)
        assert Image.open(io.BytesIO(resultado)).format == formato
