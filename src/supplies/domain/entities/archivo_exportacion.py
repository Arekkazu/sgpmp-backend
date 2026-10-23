# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77/RF-81: archivo exportado y vigencia |
"""Entidad ``ArchivoExportacion`` (RF-77 24 h, RF-81 72 h).

Un archivo PDF/CSV/EXCEL ya generado, disponible para su dueño hasta
``fecha_expiracion``. Vencido, su contenido se purga y la descarga responde 410.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from src.shared.errors import AuthorizationError, GoneError

VIGENCIA = {"RF77": timedelta(hours=24), "RF81": timedelta(hours=72)}
TIPOS_CONTENIDO = {
    "PDF": "application/pdf",
    "CSV": "text/csv",
    "EXCEL": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@dataclass(eq=False)
class ArchivoExportacion:
    origen: str
    formato: str
    nombre_archivo: str
    contenido: Optional[bytes]
    total_registros: int
    id_usuario: int
    fecha_generacion: datetime
    fecha_expiracion: datetime
    id_referencia: Optional[int] = None
    id_archivo: Optional[UUID] = None
    fecha_eliminacion: Optional[datetime] = None

    @classmethod
    def nuevo(cls, *, origen: str, formato: str, nombre_archivo: str, contenido: bytes,
              total_registros: int, id_usuario: int, ahora: datetime,
              id_referencia: Optional[int] = None) -> "ArchivoExportacion":
        return cls(
            origen=origen, formato=formato, nombre_archivo=nombre_archivo, contenido=contenido,
            total_registros=total_registros, id_usuario=id_usuario, fecha_generacion=ahora,
            fecha_expiracion=ahora + VIGENCIA[origen], id_referencia=id_referencia,
        )

    @property
    def tipo_contenido(self) -> str:
        return TIPOS_CONTENIDO[self.formato]

    @property
    def tamano_bytes(self) -> int:
        return len(self.contenido or b"")

    def contenido_para(self, id_usuario: int, ahora: datetime) -> bytes:
        """Contenido descargable por su dueño; 403 si es de otro usuario, 410 si venció."""
        if id_usuario != self.id_usuario:
            raise AuthorizationError(
                code="ARCHIVO_DE_OTRO_USUARIO",
                message="El archivo solicitado pertenece a otro usuario.",
            )
        if self.contenido is None or ahora >= self.fecha_expiracion:
            horas = int(VIGENCIA[self.origen].total_seconds() // 3600)
            accion = (
                "Genere el reporte nuevamente para obtener una nueva descarga." if self.origen == "RF77"
                else "Solicite una nueva exportación."
            )
            raise GoneError(
                code="ARCHIVO_EXPIRADO",
                message=(
                    "El archivo solicitado ya no está disponible. Los archivos exportados tienen una vigencia de "
                    f"{horas} horas. {accion}"
                ),
            )
        return self.contenido
