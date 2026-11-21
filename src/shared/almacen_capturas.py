# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-53/RF-66: últimas capturas de cada cámara en disco            |
"""Capturas de las cámaras de visión: el último cuadro de cada ventana con las cajas que detectó
el nodo (JPEG). Solo para mostrar en Predicción qué está viendo el modelo.

Se guardan en disco, no en la BD, y solo las ``MAX_POR_CAMARA`` más recientes de cada cámara (con
ventanas de 20 s, unos 5 minutos): una persona que pase frente a la cámara no queda guardada más
allá de eso. ``CAPTURAS_STORAGE_PATH`` sigue el patrón de ``LOGOS_STORAGE_PATH``: sin definir cae a
``/tmp/sgpmp_capturas``, y perderlas en un redeploy no importa porque se renuevan cada ventana.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

from src.shared.errors import ValidationError

DIRECTORIO = Path(os.environ.get("CAPTURAS_STORAGE_PATH", "/tmp/sgpmp_capturas"))
MAX_POR_CAMARA = 15
MAX_BYTES = 500_000
MAX_LADO = 1920
#: Una inferencia guarda el fin de su ventana con la precisión de la BD; la captura, con la del nodo.
TOLERANCIA = timedelta(seconds=1)


@dataclass(frozen=True)
class Captura:
    id_dispositivo_iot: int
    fecha: datetime
    n_individuos: Optional[int]
    jpeg: bytes


def guardar_captura(id_dispositivo_iot: int, fecha: datetime, n_individuos: Optional[int], jpeg: bytes) -> None:
    """Valida que sea un JPEG razonable, lo guarda y deja solo las más recientes de la cámara."""
    if len(jpeg) > MAX_BYTES:
        raise ValidationError(code="CAPTURA_DEMASIADO_GRANDE",
                              message=f"La captura supera {MAX_BYTES // 1000} KB.", field="imagen_jpeg_base64")
    try:
        with Image.open(io.BytesIO(jpeg)) as img:
            formato, (ancho, alto) = img.format, img.size
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        formato, ancho, alto = None, 0, 0
    if formato != "JPEG" or not (0 < ancho <= MAX_LADO and 0 < alto <= MAX_LADO):
        raise ValidationError(code="CAPTURA_INVALIDA", message="La captura debe ser un JPEG de hasta "
                              f"{MAX_LADO} px por lado.", field="imagen_jpeg_base64")
    carpeta = DIRECTORIO / str(id_dispositivo_iot)
    carpeta.mkdir(parents=True, exist_ok=True)
    ms = round(fecha.astimezone(timezone.utc).timestamp() * 1000)
    destino = carpeta / f"{ms}_{n_individuos if n_individuos is not None else 'x'}.jpg"
    temporal = destino.with_suffix(".tmp")
    temporal.write_bytes(jpeg)
    os.replace(temporal, destino)  # quien lee nunca ve un archivo a medio escribir
    for viejo in sorted(carpeta.glob("*.jpg"), key=_ms, reverse=True)[MAX_POR_CAMARA:]:
        viejo.unlink(missing_ok=True)


def buscar_captura(ids_camaras: list[int], fecha: Optional[datetime] = None) -> Optional[Captura]:
    """La más reciente de esas cámaras o, con ``fecha``, la de esa ventana (None si ya se descartó)."""
    candidatas = [(id_, ruta) for id_ in ids_camaras for ruta in (DIRECTORIO / str(id_)).glob("*.jpg")]
    if fecha is not None:
        objetivo = fecha.astimezone(timezone.utc).timestamp() * 1000
        limite = TOLERANCIA.total_seconds() * 1000
        candidatas = [(id_, r) for id_, r in candidatas if abs(_ms(r) - objetivo) <= limite]
    if not candidatas:
        return None
    id_camara, ruta = max(candidatas, key=lambda c: _ms(c[1]))
    n = ruta.stem.split("_")[1]
    try:
        jpeg = ruta.read_bytes()
    except FileNotFoundError:  # se descartó justo después de listarla
        return None
    return Captura(id_camara, datetime.fromtimestamp(_ms(ruta) / 1000, timezone.utc),
                   int(n) if n.isdigit() else None, jpeg)


def _ms(ruta: Path) -> int:
    return int(ruta.stem.split("_")[0])
