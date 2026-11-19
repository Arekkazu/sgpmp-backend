# | Fecha      | Nombre   | Que se hizo                                                          |
# |------------|----------|----------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: solicitud de reporte, ciclo de estados y reglas de descarga |
"""Solicitud de un reporte (RF-104) y su ciclo: EN_PROCESO → GENERADO → EXPIRADO, o FALLIDO / CANCELADO.

- El archivo queda disponible 48 h desde su generación; después se borra y la solicitud queda EXPIRADA (410).
- Solo quien lo pidió lo descarga (403 para cualquier otro), las veces que quiera dentro de las 48 h.
- En segundo plano se intenta hasta 3 veces (2 reintentos a 30 s, RNF-07) antes de marcarlo FALLIDO.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from src.shared.errors import AuthorizationError, FlowError, GoneError

EN_PROCESO, GENERADO, FALLIDO, CANCELADO, EXPIRADO = "EN_PROCESO", "GENERADO", "FALLIDO", "CANCELADO", "EXPIRADO"
PDF, EXCEL = "PDF", "EXCEL"

VIGENCIA = timedelta(hours=48)
INTENTOS_MAX = 3
ESPERA_REINTENTO = timedelta(seconds=30)
MENSAJE_FALLO = "No pudimos generar el reporte. Vuelve a intentarlo; si sigue fallando, avisa al administrador."


def sha256(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


@dataclass
class ArchivoReporte:
    numero_parte: int
    nombre_archivo: str
    tipo_contenido: str
    contenido: Optional[bytes]
    tamano_bytes: int
    checksum_sha256: str

    def integro(self) -> bool:
        """RNF-10: el contenido guardado coincide con el checksum calculado al generarlo."""
        return self.contenido is not None and sha256(self.contenido) == self.checksum_sha256


@dataclass(eq=False)
class SolicitudReporte:
    id_usuario: int
    tipo_reporte: str
    formato: str
    filtros: dict[str, Any] = field(default_factory=dict)
    zona_horaria: str = "UTC"
    id_solicitud_reporte: Optional[UUID] = None
    estado: str = EN_PROCESO
    numero_registros: Optional[int] = None
    numero_partes: int = 0
    tamano_archivo_kb: Optional[int] = None
    checksum_sha256: Optional[str] = None
    intentos: int = 0
    mensaje_error: Optional[str] = None
    fecha_solicitud: Optional[datetime] = None
    fecha_snapshot: Optional[datetime] = None
    fecha_generacion: Optional[datetime] = None
    fecha_proximo_intento: Optional[datetime] = None
    fecha_expiracion: Optional[datetime] = None
    fecha_eliminacion: Optional[datetime] = None

    def encolar(self, ahora: datetime) -> None:
        """Más de 1.000 registros: queda EN_PROCESO para el proceso en segundo plano."""
        self.estado = EN_PROCESO
        self.fecha_proximo_intento = ahora

    def registrar_generacion(self, partes: list[ArchivoReporte], numero_registros: int,
                             fecha_snapshot: datetime, ahora: datetime) -> None:
        self.estado = GENERADO
        self.numero_registros = numero_registros
        self.numero_partes = len(partes)
        self.tamano_archivo_kb = max(1, round(sum(p.tamano_bytes for p in partes) / 1024))
        # Una parte: su propio checksum; varias: el de sus checksums en orden.
        self.checksum_sha256 = (partes[0].checksum_sha256 if len(partes) == 1
                                else sha256("".join(p.checksum_sha256 for p in partes).encode()))
        self.fecha_snapshot = fecha_snapshot
        self.fecha_generacion = ahora
        self.fecha_expiracion = ahora + VIGENCIA
        self.fecha_proximo_intento = None
        self.mensaje_error = None

    def registrar_intento_fallido(self, ahora: datetime) -> bool:
        """Cuenta el intento. ``True`` si se agotaron los reintentos y la solicitud queda FALLIDA."""
        self.intentos += 1
        if self.intentos >= INTENTOS_MAX:
            self.marcar_fallida(MENSAJE_FALLO)
            return True
        self.fecha_proximo_intento = ahora + ESPERA_REINTENTO
        return False

    def marcar_fallida(self, mensaje: str) -> None:
        self.estado = FALLIDO
        self.mensaje_error = mensaje
        self.fecha_proximo_intento = None

    def cancelar(self, id_usuario: int) -> None:
        self._exigir_propietario(id_usuario)
        if self.estado != EN_PROCESO:
            raise FlowError(code="REPORTE_NO_CANCELABLE", field="estado",
                            message="Solo se puede cancelar un reporte que todavía se está generando.")
        self.estado = CANCELADO
        self.fecha_proximo_intento = None

    def expirar(self, ahora: datetime) -> None:
        self.estado = EXPIRADO
        self.fecha_eliminacion = ahora

    def vencida(self, ahora: datetime) -> bool:
        return self.estado == EXPIRADO or (
            self.estado == GENERADO and self.fecha_expiracion is not None and ahora >= self.fecha_expiracion)

    def _exigir_propietario(self, id_usuario: int) -> None:
        if self.id_usuario != id_usuario:
            raise AuthorizationError(code="REPORTE_AJENO", field="id_reporte",
                                     message="Solo quien pidió este reporte puede usarlo.")

    def exigir_descargable(self, id_usuario: int, ahora: datetime) -> None:
        """403 si es de otro usuario, 410 si ya venció, 422 si todavía no hay archivo o falló."""
        self._exigir_propietario(id_usuario)
        if self.vencida(ahora):
            raise GoneError(code="REPORTE_EXPIRADO", field="id_reporte",
                            message="El reporte ya no está disponible: los archivos se guardan 48 horas. "
                                    "Genéralo de nuevo.")
        if self.estado == EN_PROCESO:
            raise FlowError(code="REPORTE_EN_PROCESO", field="id_reporte",
                            message="El reporte todavía se está generando. Te avisaremos cuando esté listo.")
        if self.estado != GENERADO:
            raise FlowError(code="REPORTE_NO_DISPONIBLE", field="id_reporte",
                            message=self.mensaje_error or "Este reporte no se generó. Vuelve a generarlo.")
