# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77: exportación PDF/CSV y descarga     |
"""Casos de uso: exportar un reporte de gastos a PDF/CSV y descargarlo (RF-77 pasos 8, E6).

La exportación trabaja sobre un reporte ya generado: si se rechaza, el reporte
sigue disponible en pantalla (postcondición de E6b).

- PDF: máximo 500 registros en el detalle (E6b → 422); 25 por página, con
  encabezado, logo y fecha de generación. Un fallo del motor PDF se audita y
  responde 500 (E6a).
- CSV: columnas fecha, categoria, descripcion, monto_cop, estado (CA-10); más de
  50 MB → 413 (E6c), nunca un archivo parcial.
- El archivo queda disponible 24 h para quien lo generó; luego 410 (E6d).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, InfrastructureError, NotFoundError, PayloadTooLargeError
from src.supplies.application.use_cases.exportacion.generador_archivos import (
    Documento,
    generar_csv,
    generar_pdf,
)
from src.supplies.application.use_cases.reporte_gastos.generar_reporte_gastos_use_case import (
    GenerarReporteGastosUseCase,
)
from src.supplies.domain.entities.archivo_exportacion import ArchivoExportacion
from src.supplies.domain.entities.reporte_gasto import ReporteGasto
from src.supplies.domain.repositories.archivo_exportacion_repository import ArchivoExportacionRepository
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.logo_institucional_port import LogoInstitucionalPort
from src.supplies.domain.repositories.reporte_gasto_repository import ReporteGastoRepository

logger = logging.getLogger(__name__)

MAX_REGISTROS_PDF = 500
MAX_BYTES_CSV = 50 * 1024 * 1024
FORMATOS = ("PDF", "CSV")
_COLUMNAS = ["fecha", "categoria", "descripcion", "monto_cop", "estado"]


def _identificador(reporte: ReporteGasto) -> str:
    if reporte.id_activo_biologico is not None:
        return str(reporte.id_activo_biologico)
    if reporte.id_infraestructura is not None:
        return f"INFRA{reporte.id_infraestructura}"
    return f"ESPECIE{reporte.id_especie}"


class ExportarReporteGastosUseCase:
    def __init__(
        self,
        db: Session,
        reporte_repo: ReporteGastoRepository,
        generador: GenerarReporteGastosUseCase,
        archivo_repo: ArchivoExportacionRepository,
        logo_port: LogoInstitucionalPort,
        auditoria_port: AuditoriaSuministroPort,
    ) -> None:
        self.db = db
        self.reporte_repo = reporte_repo
        self.generador = generador
        self.archivo_repo = archivo_repo
        self.logo_port = logo_port
        self.auditoria_port = auditoria_port

    def execute(self, id_reporte: int, formato: str, usuario_actual: UsuarioActual,
                reporte: Optional[ReporteGasto] = None) -> ArchivoExportacion:
        """Exporta el reporte ``id_reporte``. ``reporte`` evita regenerarlo si ya se tiene en memoria."""
        if formato not in FORMATOS:
            raise BusinessRuleError(
                code="FORMATO_EXPORTACION_INVALIDO",
                message="El formato de exportación debe ser PDF o CSV.",
                field="formato_exportacion",
            )
        if reporte is None:
            guardado = self.reporte_repo.obtener(id_reporte)
            if guardado is None:
                raise NotFoundError(
                    code="REPORTE_NO_ENCONTRADO",
                    message=f"El reporte de gastos {id_reporte} no existe.",
                )
            reporte = self.generador.construir_desde_parametros(self._parametros(guardado), usuario_actual)
            reporte.id_reporte_gasto_acumulado = guardado.id_reporte_gasto_acumulado
        return self.exportar(reporte, formato, usuario_actual.id_usuario)

    def exportar(self, reporte: ReporteGasto, formato: str, id_usuario: int) -> ArchivoExportacion:
        ahora = datetime.now(timezone.utc)
        filas = self._filas(reporte)
        nombre_base = f"{_identificador(reporte)}_{reporte.fecha_inicio.isoformat()}_{reporte.fecha_fin.isoformat()}"

        if formato == "PDF":
            if len(filas) > MAX_REGISTROS_PDF:
                raise BusinessRuleError(
                    code="PDF_EXCEDE_LIMITE",
                    message=(
                        f"El reporte contiene {len(filas)} registros y supera el límite de exportación en PDF "
                        f"({MAX_REGISTROS_PDF} registros). Utilice el formato CSV para exportar el volumen "
                        "completo de datos."
                    ),
                    field="formato_exportacion",
                )
            contenido = self._pdf(reporte, filas, ahora, id_usuario)
            nombre = f"Reporte_Gastos_{nombre_base}.pdf"
        else:
            contenido = generar_csv(Documento(titulo="Gastos", columnas=_COLUMNAS, filas=filas))
            if len(contenido) > MAX_BYTES_CSV:
                raise PayloadTooLargeError(
                    code="CSV_EXCEDE_TAMANO",
                    message=(
                        "El archivo CSV generado supera el límite de 50 MB. Reduzca el rango de fechas o aplique "
                        "filtros por categoría para acotar el volumen de datos exportados."
                    ),
                )
            nombre = f"Gastos_{nombre_base}.csv"

        archivo = ArchivoExportacion.nuevo(
            origen="RF77", formato=formato, nombre_archivo=nombre, contenido=contenido,
            total_registros=len(filas), id_usuario=id_usuario, ahora=ahora,
            id_referencia=reporte.id_reporte_gasto_acumulado,
        )
        try:
            guardado = self.archivo_repo.guardar(archivo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return guardado

    def descargar(self, id_archivo: UUID, usuario_actual: UsuarioActual) -> ArchivoExportacion:
        archivo = self.archivo_repo.obtener(id_archivo)
        if archivo is None or archivo.origen != "RF77":
            raise NotFoundError(code="ARCHIVO_NO_ENCONTRADO", message=f"El archivo {id_archivo} no existe.")
        archivo.contenido_para(usuario_actual.id_usuario, datetime.now(timezone.utc))
        return archivo

    # ── Auxiliares ───────────────────────────────────────────────────────────
    @staticmethod
    def _parametros(guardado: ReporteGasto) -> dict:
        if guardado.parametros:
            return guardado.parametros
        # Reportes anteriores a json_parametros: solo hay activo/infraestructura, fechas y tipo de período.
        return {
            "fecha_inicio": guardado.fecha_inicio.isoformat(),
            "fecha_fin": guardado.fecha_fin.isoformat(),
            "tipo_periodo": guardado.tipo_periodo,
            "id_activo_biologico": guardado.id_activo_biologico,
            "id_infraestructura": guardado.id_infraestructura,
        }

    @staticmethod
    def _filas(reporte: ReporteGasto) -> list[list]:
        return [
            [
                linea.fecha.isoformat(),
                linea.categoria,
                linea.descripcion,
                linea.monto if linea.monto is not None else "",
                linea.estado if linea.monto is not None else "SIN_COSTO_REGISTRADO",
            ]
            for linea in sorted(reporte.lineas, key=lambda l: (l.fecha, l.categoria, l.id_origen))
        ]

    def _pdf(self, reporte: ReporteGasto, filas: list[list], ahora: datetime, id_usuario: int) -> bytes:
        encabezado = [
            f"Activo: {reporte.id_activo_biologico or '-'} · Infraestructura: {reporte.id_infraestructura or '-'} "
            f"· Especie: {reporte.id_especie or '-'}",
            f"Período: {reporte.fecha_inicio.isoformat()} – {reporte.fecha_fin.isoformat()} ({reporte.tipo_periodo})",
            f"Gasto total acumulado: {reporte.gasto_total_acumulado} COP",
        ]
        if reporte.gasto_promedio_individuo is not None:
            encabezado.append(f"Gasto promedio por individuo: {reporte.gasto_promedio_individuo:.2f} COP")
        pie = [
            f"{d.categoria}: {d.subtotal} COP ({d.porcentaje} %) — {d.num_registros} registros"
            for d in reporte.desglose_categorias
        ]
        if reporte.tendencia is not None:
            pie.append(f"Tendencia vs. período anterior: {reporte.tendencia.estado} "
                       f"{reporte.tendencia.variacion_porcentual or ''}")
        for nota in (reporte.nota_bajas, reporte.mensaje):
            if nota:
                pie.append(nota)
        documento = Documento(
            titulo="Reporte de Gastos Acumulados",
            columnas=_COLUMNAS,
            filas=filas,
            encabezado=encabezado,
            pie=pie,
            ruta_logo=self.logo_port.ruta_logo(
                id_activo_biologico=reporte.id_activo_biologico, id_infraestructura=reporte.id_infraestructura
            ),
        )
        try:
            return generar_pdf(documento, ahora)
        except Exception as exc:
            self._auditar_fallo_pdf(reporte, id_usuario, exc)
            raise InfrastructureError(
                code="ERROR_GENERACION_PDF",
                message=(
                    "Error al generar el archivo PDF. Puede intentar la exportación nuevamente o descargar en "
                    "formato CSV como alternativa."
                ),
                original_error=exc,
            ) from exc

    def _auditar_fallo_pdf(self, reporte: ReporteGasto, id_usuario: int, exc: Exception) -> None:
        try:
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="exportacion_reporte_gastos",
                    tipo_operacion="REGISTRO_FALLIDO",
                    id_usuario=id_usuario,
                    resultado="FALLIDO",
                    id_activo_biologico=reporte.id_activo_biologico,
                    detalle_causa=f"Fallo del motor PDF (RF-77 E6a): {exc}"[:1000],
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("No se pudo auditar el fallo de exportación PDF del reporte de gastos.")
