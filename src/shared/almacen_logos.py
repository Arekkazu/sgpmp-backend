"""Almacenamiento de logotipos institucionales en disco (RF-26).

Existía duplicado palabra por palabra como ``_guardar_logo`` en los dos casos de uso de
identidad visual (crear y actualizar), con mensajes de error distintos para la misma
condición. Vive aquí porque la ruta que se devuelve tiene que coincidir exactamente con
la que ``main.py`` monta como estática: si los dos caminos de escritura divergen en el
formato de la ruta, uno de los dos logotipos deja de ser alcanzable por HTTP.

La ruta devuelta es **de URL** (``/uploads/logos/<archivo>``), no del sistema de
archivos: es lo que se persiste en ``modulo9.identidad_visuales.logo_path`` y lo que el
cliente concatena a la base de la API para pintar la imagen.

``LOGOS_STORAGE_PATH`` sigue el mismo patrón que ``MODELOS_STORAGE_PATH``
(``registrar_version_modelo_use_case.py``): sin definir cae a ``/tmp/sgpmp_logos``. En
Dokploy/producción el contenedor corre como ``appuser`` y ``/app`` (WORKDIR) es propiedad
de root, así que un directorio relativo tipo ``uploads/logos`` nunca se puede crear ahí —
y como además no vive en el volumen persistente, un redeploy lo borra igual si funcionara.
Se configura para que apunte al volumen ``sgpmp_modelos`` ya provisionado
(``/app/storage/modelos/logos``, ver ``docker-compose.yml``), sin pedir un volumen nuevo.
"""
from __future__ import annotations

import io
import os
import re
import uuid
from typing import Optional
from xml.etree import ElementTree

from PIL import Image, UnidentifiedImageError

from src.shared.errors import InfrastructureError, ValidationError

FORMATOS_PERMITIDOS = {"image/png", "image/jpeg", "image/svg+xml"}
TAMANO_MAX = 2 * 1024 * 1024  # 2 MB, límite explícito de RF-26

# Lado más largo tras redimensionar. El sidebar pinta el logo en un marco fijo
# (`.ds-sidebar__logo-mark`, `object-fit: contain`) así que no hace falta más
# resolución que esa — subir un PNG de 6000x6000 no debe quedar guardado tal cual.
DIMENSION_MAX = 512

RUTA_PUBLICA_LOGOS = "/uploads/logos"
DIRECTORIO_LOGOS = os.environ.get("LOGOS_STORAGE_PATH", "/tmp/sgpmp_logos")

_EXTENSIONES = {"image/png": ".png", "image/jpeg": ".jpg", "image/svg+xml": ".svg"}
_FORMATOS_PIL = {"image/png": "PNG", "image/jpeg": "JPEG"}

# Rechazo simple de SVG con contenido ejecutable (RF-26 pide imagen, no vector con
# script embebido). No es un sanitizador completo — cubre los vectores de XSS
# habituales sin sumar una dependencia nueva solo para esto.
_SVG_PATRON_PELIGROSO = re.compile(r"<script|javascript:|on\w+\s*=", re.IGNORECASE)


def guardar_logo(contenido: bytes, content_type: Optional[str]) -> str:
    """Valida formato, tamaño y contenido real, redimensiona si aplica, escribe el
    archivo y devuelve su ruta pública.

    Los dos rechazos por Content-Type/tamaño son los flujos alternos *Formato de
    imagen no compatible* y *archivo que excede el tamaño máximo* de RF-26. El
    Content-Type declarado por el cliente es solo la puerta de entrada: el contenido
    se valida de verdad abriendo los bytes con Pillow (o, para SVG, parseándolo).
    """
    if content_type not in FORMATOS_PERMITIDOS:
        raise ValidationError(
            code="FORMATO_IMAGEN_NO_PERMITIDO",
            message=(
                f"Archivo no admitido. El logotipo debe estar en formato PNG, JPEG o SVG. "
                f"Tipo recibido: '{content_type}'."
            ),
            field="logo",
        )
    if len(contenido) > TAMANO_MAX:
        raise ValidationError(
            code="TAMANO_IMAGEN_EXCEDIDO",
            message=(
                f"El archivo de imagen supera el límite de 2 MB "
                f"({len(contenido) / (1024 * 1024):.1f} MB recibidos)."
            ),
            field="logo",
        )

    if content_type == "image/svg+xml":
        contenido = _validar_svg(contenido)
    else:
        contenido = _validar_y_redimensionar_raster(contenido, content_type)

    nombre = f"{uuid.uuid4()}{_EXTENSIONES[content_type]}"
    try:
        os.makedirs(DIRECTORIO_LOGOS, exist_ok=True)
        with open(os.path.join(DIRECTORIO_LOGOS, nombre), "wb") as archivo:
            archivo.write(contenido)
    except OSError as exc:
        # FA "Fallo en la persistencia del archivo (Storage Error)" de RF-26. Sin
        # este try/except, un fallo del sistema de archivos (contenedor efímero,
        # disco lleno, permisos) salía como 500 genérico "Ocurrió un error interno"
        # sin información, y sin distinguir este caso del resto de 500 (INC-M09-26-G86).
        raise InfrastructureError(
            code="ERROR_ALMACENAMIENTO",
            message=(
                "Error de almacenamiento: No se pudo guardar el logotipo debido a un "
                "fallo en el servidor de archivos. La configuración anterior no ha "
                "sido modificada."
            ),
            original_error=exc,
        )
    return f"{RUTA_PUBLICA_LOGOS}/{nombre}"


def _validar_y_redimensionar_raster(contenido: bytes, content_type: str) -> bytes:
    """Abre el archivo como imagen real (rechaza cualquier cosa que no lo sea,
    aunque el Content-Type declarado diga lo contrario) y lo reduce a
    ``DIMENSION_MAX``. Volver a codificar los píxeles de paso también descarta
    cualquier payload escondido en metadatos o en un polyglot PNG/JPEG."""
    try:
        imagen = Image.open(io.BytesIO(contenido))
        imagen.verify()
        # `verify()` deja el objeto inutilizable para leer píxeles; se reabre.
        imagen = Image.open(io.BytesIO(contenido))
        formato_real = imagen.format
        imagen.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError(
            code="FORMATO_IMAGEN_NO_PERMITIDO",
            message="El archivo no es una imagen válida.",
            field="logo",
        )

    if formato_real != _FORMATOS_PIL[content_type]:
        raise ValidationError(
            code="FORMATO_IMAGEN_NO_PERMITIDO",
            message="El contenido del archivo no coincide con el formato declarado.",
            field="logo",
        )

    imagen.thumbnail((DIMENSION_MAX, DIMENSION_MAX), Image.Resampling.LANCZOS)
    if content_type == "image/jpeg" and imagen.mode in ("RGBA", "P"):
        imagen = imagen.convert("RGB")

    salida = io.BytesIO()
    imagen.save(salida, format=_FORMATOS_PIL[content_type])
    return salida.getvalue()


def _validar_svg(contenido: bytes) -> bytes:
    texto = contenido.decode("utf-8", errors="ignore")
    if _SVG_PATRON_PELIGROSO.search(texto):
        raise ValidationError(
            code="FORMATO_IMAGEN_NO_PERMITIDO",
            message="El SVG contiene contenido no permitido.",
            field="logo",
        )
    try:
        raiz = ElementTree.fromstring(contenido)
    except ElementTree.ParseError:
        raise ValidationError(
            code="FORMATO_IMAGEN_NO_PERMITIDO",
            message="El archivo no es un SVG válido.",
            field="logo",
        )
    if not raiz.tag.endswith("svg"):
        raise ValidationError(
            code="FORMATO_IMAGEN_NO_PERMITIDO",
            message="El archivo no es un SVG válido.",
            field="logo",
        )
    return contenido
