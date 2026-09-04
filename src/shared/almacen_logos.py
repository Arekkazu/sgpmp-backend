"""Almacenamiento de logotipos institucionales en disco (RF-26).

Existía duplicado palabra por palabra como ``_guardar_logo`` en los dos casos de uso de
identidad visual (crear y actualizar), con mensajes de error distintos para la misma
condición. Vive aquí porque la ruta que se devuelve tiene que coincidir exactamente con
la que ``main.py`` monta como estática: si los dos caminos de escritura divergen en el
formato de la ruta, uno de los dos logotipos deja de ser alcanzable por HTTP.

La ruta devuelta es **de URL** (``/uploads/logos/<archivo>``), no del sistema de
archivos: es lo que se persiste en ``modulo9.identidad_visuales.logo_path`` y lo que el
cliente concatena a la base de la API para pintar la imagen.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from src.shared.errors import ValidationError

FORMATOS_PERMITIDOS = {"image/png", "image/jpeg", "image/svg+xml"}
TAMANO_MAX = 2 * 1024 * 1024  # 2 MB, límite explícito de RF-26

# `main.py` monta DIRECTORIO_BASE bajo RUTA_PUBLICA_BASE, de modo que lo que se
# escribe en DIRECTORIO_LOGOS queda servido en RUTA_PUBLICA_LOGOS.
DIRECTORIO_BASE = "uploads"
RUTA_PUBLICA_BASE = "/uploads"
DIRECTORIO_LOGOS = f"{DIRECTORIO_BASE}/logos"
RUTA_PUBLICA_LOGOS = f"{RUTA_PUBLICA_BASE}/logos"

_EXTENSIONES = {"image/png": ".png", "image/jpeg": ".jpg", "image/svg+xml": ".svg"}


def guardar_logo(contenido: bytes, content_type: Optional[str]) -> str:
    """Valida formato y tamaño, escribe el archivo y devuelve su ruta pública.

    Los dos rechazos son los flujos alternos *Formato de imagen no compatible* y
    *archivo que excede el tamaño máximo* de RF-26.
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

    os.makedirs(DIRECTORIO_LOGOS, exist_ok=True)
    nombre = f"{uuid.uuid4()}{_EXTENSIONES[content_type]}"
    with open(os.path.join(DIRECTORIO_LOGOS, nombre), "wb") as archivo:
        archivo.write(contenido)
    return f"{RUTA_PUBLICA_LOGOS}/{nombre}"
