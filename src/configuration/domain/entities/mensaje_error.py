# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-107 RNF-03: mensaje de error en lenguaje natural por clave |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Entrada del catálogo de mensajes de error (RF-107 RNF-03), configurable por el Administrador en M09.

La clave es la del error que devuelve el backend (``PERIODO_NO_CERRADO``) o una del front (``SIN_CONEXION``); el
front muestra este texto en vez del que trae la respuesta y, si hay ruta, un botón de acción correctiva. La ruta es
siempre interna (relativa al front): nunca una URL externa."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.shared.errors import ValidationError

IDIOMAS = ("es-CO", "en-US")
_CLAVE = re.compile(r"^[A-Z0-9_]{2,80}$")
_RUTA = re.compile(r"^[a-z0-9][a-z0-9/_-]{0,199}$")


@dataclass
class MensajeError:
    """Mensaje de error personalizado por clave e idioma."""
    clave: str
    idioma: str
    mensaje: str
    texto_accion: Optional[str] = None
    ruta_accion: Optional[str] = None
    es_activo: bool = True
    id_usuario: Optional[int] = None
    fecha_actualizacion: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.mensaje = (self.mensaje or "").strip()
        self.texto_accion = (self.texto_accion or "").strip() or None
        self.ruta_accion = (self.ruta_accion or "").strip().strip("/") or None
        if not _CLAVE.match(self.clave or ""):
            raise ValidationError(code="VAL_ENTRADA", field="clave",
                                  message="La clave solo admite mayúsculas, números y guion bajo (2 a 80).")
        if self.idioma not in IDIOMAS:
            raise ValidationError(code="VAL_ENTRADA", field="idioma", message="El idioma debe ser es-CO o en-US.")
        if not 5 <= len(self.mensaje) <= 500:
            raise ValidationError(code="VAL_ENTRADA", field="mensaje",
                                  message="El mensaje debe tener entre 5 y 500 caracteres.")
        if (self.texto_accion is None) != (self.ruta_accion is None):
            raise ValidationError(code="VAL_ENTRADA", field="ruta_accion",
                                  message="El botón de acción necesita su texto y la pantalla a la que lleva.")
        if self.texto_accion and len(self.texto_accion) > 80:
            raise ValidationError(code="VAL_ENTRADA", field="texto_accion",
                                  message="El texto del botón admite hasta 80 caracteres.")
        if self.ruta_accion and not _RUTA.match(self.ruta_accion):
            raise ValidationError(code="VAL_ENTRADA", field="ruta_accion",
                                  message="La pantalla del botón debe ser una ruta del sistema, por ejemplo "
                                          "«finanzas» o «configuracion/especies».")
