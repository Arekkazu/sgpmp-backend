# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-81: PDF/Excel, 202 > 10.000, firma     |
"""Caso de uso: exportar el historial de suministros a PDF o Excel (RF-81 Fase 6).

- ≤ 10.000 registros: archivo síncrono (≤ 10 s).
- > 10.000: se encola un trabajo EXPORTACION y se responde 202 con
  ``id_exportacion`` (E3); máximo 3 exportaciones asíncronas en curso por
  usuario (E6, 429). El worker genera el archivo, lo deja disponible 72 h y
  avisa al usuario.

El archivo trae encabezado del activo, todos los campos de cada registro,
subtotales por tipo de suministro y por ciclo, y firma (SHA-256 de las filas)
con el timestamp del sistema. Registra ``EXPORTACION_HISTORIAL_GENERADA`` en la
bitácora de M05 (RF-80) sin bloquear la respuesta si la auditoría falla.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy.orm import Session

from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError
from src.supplies.application.use_cases.exportacion.generador_archivos import (
    Documento,
    generar_excel,
    generar_pdf,
)
from src.supplies.domain.entities.historial_suministro import FiltrosHistorialSuministro, LineaHistorialSuministro
from src.supplies.domain.entities.trabajo_historial_suministro import TrabajoHistorialSuministro
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.alcance_activo_port import AlcanceActivoPort
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.configuracion_batch_historial_repository import (
    ConfiguracionBatchHistorialRepository,
)
from src.supplies.domain.repositories.historial_suministro_read_port import HistorialSuministroReadPort
from src.supplies.domain.value_objects.historial_suministro_enums import TipoTrabajoHistorial

logger = logging.getLogger(__name__)

FORMATOS = {"PDF": ".pdf", "EXCEL": ".xlsx"}
_COLUMNAS = [
    "id_registro_suministro",
    "tipo_suministro",
    "tipo_operacion",
    "descripcion",
    "fecha_aplicacion",
    "cantidad",
    "unidad_medida",
    "precio_unitario",
    "costo_registro",
    "origen_precio",
    "nombre_activo",
    "especie",
    "nombre_ciclo",
    "estado_ciclo",
    "observacion",
]


def _fila(l: LineaHistorialSuministro) -> list:
    return [
        l.id_registro_suministro, l.tipo_suministro, l.tipo_operacion, l.descripcion,
        l.fecha_aplicacion.isoformat(), l.cantidad, l.unidad_medida, l.precio_unitario, l.costo_registro,
        l.origen_precio, l.nombre_activo, l.especie, l.nombre_ciclo, l.estado_ciclo, l.observacion,
    ]


@dataclass(frozen=True)
class ArchivoHistorial:
    contenido: bytes
    nombre_archivo: str
    formato: str
    total_registros: int


class ExportarHistorialSincronoUseCase:
    def __init__(
        self,
        historial_port: HistorialSuministroReadPort,
        alcance_port: AlcanceActivoPort,
        activo_port: ActivoConsultaPort,
        config_repo: ConfiguracionBatchHistorialRepository,
        db: Session,
        auditoria_port: AuditoriaSuministroPort,
        solicitar: Optional[object] = None,
    ) -> None:
        self.historial_port = historial_port
        self.alcance_port = alcance_port
        self.activo_port = activo_port
        self.config_repo = config_repo
        self.db = db
        self.auditoria_port = auditoria_port
        self.solicitar = solicitar

    def execute(
        self, filtros: FiltrosHistorialSuministro, formato: str, *, id_usuario: int, id_rol: int
    ) -> Union[ArchivoHistorial, TrabajoHistorialSuministro]:
        ids_permitidos = self._validar(filtros, formato, id_usuario, id_rol)
        config = self.config_repo.obtener()
        resultado = self.historial_port.consultar(
            replace(filtros, pagina=1, registros_por_pagina=config.umbral_exportacion_async), ids_permitidos
        )
        if resultado.total_registros_filtrados > config.umbral_exportacion_async:
            return self.solicitar.execute(
                TipoTrabajoHistorial.EXPORTACION.value, filtros, id_usuario, id_rol, formato_exportacion=formato
            )
        return self._archivo(filtros, formato, resultado, id_usuario)

    def exportar_forzado(
        self, filtros: FiltrosHistorialSuministro, formato: str, *, id_usuario: int, id_rol: int
    ) -> ArchivoHistorial:
        """Worker del motor async (trabajo EXPORTACION): todo el volumen, sin umbral síncrono."""
        ids_permitidos = self._validar(filtros, formato, id_usuario, id_rol)
        resultado = self.historial_port.consultar(
            replace(filtros, pagina=1, registros_por_pagina=5_000_000), ids_permitidos
        )
        return self._archivo(filtros, formato, resultado, id_usuario)

    # ── Auxiliares ───────────────────────────────────────────────────────────
    def _validar(self, filtros: FiltrosHistorialSuministro, formato: str, id_usuario: int, id_rol: int):
        if formato not in FORMATOS:
            raise BusinessRuleError(
                code="FORMATO_EXPORTACION_INVALIDO",
                message="El formato de exportación del historial debe ser PDF o EXCEL.",
                field="formato_exportacion",
            )
        activo = self.activo_port.obtener(filtros.id_activo_biologico)
        if activo is None:
            raise NotFoundError(
                code="ACTIVO_NO_ENCONTRADO",
                message=f"El activo biológico {filtros.id_activo_biologico} no existe.",
                field="id_activo_biologico",
            )
        ids_permitidos = self.alcance_port.listar_ids_activos_permitidos(id_usuario, id_rol)
        if ids_permitidos is not None and filtros.id_activo_biologico not in ids_permitidos:
            raise AuthorizationError(
                code="ACCESO_DENEGADO",
                message=(
                    f"No tiene permisos para consultar el historial del activo {filtros.id_activo_biologico}. "
                    "Verifique su rol y unidades productivas asignadas."
                ),
            )
        return ids_permitidos

    def _archivo(self, filtros, formato: str, resultado, id_usuario: int) -> ArchivoHistorial:
        ahora = datetime.now(timezone.utc)
        filas = [_fila(l) for l in resultado.lineas]
        firma = hashlib.sha256("\n".join("|".join(map(str, f)) for f in filas).encode("utf-8")).hexdigest()
        primera = resultado.lineas[0] if resultado.lineas else None
        documento = Documento(
            titulo="Historial de Suministros",
            columnas=_COLUMNAS,
            filas=filas,
            encabezado=[
                f"Activo: {filtros.id_activo_biologico}"
                + (f" — {primera.nombre_activo} ({primera.especie})" if primera else ""),
                f"Filtros: ciclo={filtros.id_ciclo_productivo or 'TODOS'}, "
                f"fechas={filtros.fecha_inicio_filtro or '-'}..{filtros.fecha_fin_filtro or '-'}, "
                f"tipo={filtros.tipo_suministro_filtro}, origen={filtros.origen_precio_filtro}",
                f"Total de registros: {resultado.total_registros_filtrados} · "
                f"Monto total: {resultado.monto_total_filtrado} COP",
            ],
            pie=[
                *(f"Subtotal {tipo}: {d['monto']} COP ({d['total']} registros)"
                  for tipo, d in resultado.desglose_por_tipo_suministro.items()),
                *(f"Subtotal ciclo {ciclo}: {d['monto']} COP ({d['total']} registros)"
                  for ciclo, d in resultado.desglose_por_ciclo.items()),
                f"Firma del sistema (SHA-256): {firma}",
                f"Generado por SIGAB: {ahora.isoformat(timespec='seconds')}",
            ],
        )
        contenido = generar_pdf(documento, ahora) if formato == "PDF" else generar_excel(documento)
        nombre = (
            f"Historial_Suministros_{filtros.id_activo_biologico}_"
            f"{filtros.fecha_inicio_filtro or 'inicio'}_{filtros.fecha_fin_filtro or 'fin'}{FORMATOS[formato]}"
        )
        self._auditar_exportacion(filtros, id_usuario)
        return ArchivoHistorial(
            contenido=contenido, nombre_archivo=nombre, formato=formato,
            total_registros=resultado.total_registros_filtrados,
        )

    def _auditar_exportacion(self, filtros: FiltrosHistorialSuministro, id_usuario: int) -> None:
        try:
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="historial_suministros",
                    tipo_operacion="EXPORTACION_HISTORIAL_GENERADA",
                    id_usuario=id_usuario,
                    resultado="EXITOSO",
                    id_activo_biologico=filtros.id_activo_biologico,
                    id_ciclo_productivo=filtros.id_ciclo_productivo,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Error al auditar EXPORTACION_HISTORIAL_GENERADA para activo %s", filtros.id_activo_biologico)
