# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-19 | Arekkazu | SEG-M04-01 RF-69: firma HMAC del artefacto, verificada al registrar y antes de correr en el motor |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Firma del artefacto de una versión de modelo (SEG-M04-01).

El SHA-256 que declara quien registra no prueba nada por sí solo: quien tenga la clave M2M de registro
(``RF71_INTERNAL_KEY``) podría subir cualquier archivo con su hash. La firma es un HMAC-SHA256 del SHA-256
del artefacto con ``M04_FIRMA_MODELOS_KEY``, una clave distinta que custodia Seguridad/Despliegue y que
solo tiene el proceso de entrenamiento. El backend la verifica al registrar y, contra el archivo en
disco, antes de que la versión corra en el motor (SOMBRA o ACTIVO). Sin la clave configurada no se
registra ni se activa ninguna versión.

Firmar desde el proceso de entrenamiento::

    hmac.new(clave.encode(), sha256_hex_del_artefacto.encode(), hashlib.sha256).hexdigest()
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional

VARIABLE_CLAVE = "M04_FIRMA_MODELOS_KEY"


def clave_firma() -> str:
    """Clave de firma de artefactos configurada."""
    return os.environ.get(VARIABLE_CLAVE, "")


def firmar(sha256_hex: str, clave: str) -> str:
    """Firma con HMAC-SHA256 el hash del artefacto."""
    return hmac.new(clave.encode(), sha256_hex.lower().encode(), hashlib.sha256).hexdigest()


def firma_valida(firma: Optional[str], sha256_hex: Optional[str], clave: str) -> bool:
    """Indica si la firma corresponde al hash con la clave."""
    if not (firma and sha256_hex and clave):
        return False
    return hmac.compare_digest(firma.strip().lower(), firmar(sha256_hex, clave))


def sha256_archivo(ruta: str) -> Optional[str]:
    """Calcula el SHA-256 del archivo, o ``None`` si no se puede leer."""
    try:
        with open(ruta, "rb") as archivo:
            return hashlib.file_digest(archivo, "sha256").hexdigest()
    except OSError:
        return None
