# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77: exportación PDF/CSV y descarga     |
# | 2026-11-07 | Leandro | INC-M05-272-G25 RF-77: auditar la exportacion exitosa en la misma transaccion del archivo. |
# | 2026-11-08 | Arekkazu | INC-M05-265-G32: textos visibles sin códigos de requisito ni de módulo |
# | 2026-11-10 | Arekkazu | INC-M05-269-G23 RF-77: PDF con nombres del activo, desglose por período y notas de tendencia |
# | 2026-11-10 | Arekkazu | TC-DIS-204 RF-77: PDF con encabezados, montos, fechas y tendencia con signo en palabras |
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
    fecha,
    generar_csv,
    generar_pdf,
    moneda,
    numero,
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
_COLUMNAS = ["fecha", "categoria", "descripcion", "monto_cop", "estado"]  # CSV: formato de integración
_COLUMNAS_PDF = ["Fecha", "Categoría", "Descripción", "Monto", "Estado"]
_ESTADO = {"VALIDADO": "Validado", "SIN_COSTO_REGISTRADO": "Sin costo registrado", "ANULADO": "Anulado"}


def _identificador(reporte: ReporteGasto) -> str:
    if reporte.id_activo_biologico is not None:
        return str(reporte.id_activo_biologico)
    if reporte.id_infraestructura is not None:
        return f"INFRA{reporte.id_infraestructura}"
    return f"ESPECIE{reporte.id_especie}"


_PERIODO = {"MENSUAL": "Mensual", "SEMANAL": "Semanal", "CICLO_COMPLETO": "Ciclo completo"}
_CATEGORIA = {"ALIMENTACION": "Alimentación", "MEDICACION": "Medicación"}
_TENDENCIA = {"CALCULADA": "calculada", "SIN_BASE_COMPARATIVA": "sin base comparativa",
              "SIN_MOVIMIENTO": "sin movimiento en ninguno de los dos períodos"}
_TIPO_ACTIVO = {"INDIVIDUAL": "individual", "POBLACIONAL": "lote"}


def _linea_alcance(reporte: ReporteGasto, alcance: dict) -> str:
    """Encabezado con nombres (RF-77 paso 7, CA-9), nunca ids: «Activo BOV-01 (individual) · Área …»."""
    partes = []
    if reporte.id_activo_biologico is not None:
        tipo = _TIPO_ACTIVO.get((alcance.get("tipo_activo") or "").upper())
        nombre = alcance.get("identificador") or "sin identificador"
        partes.append(f"Activo: {nombre}" + (f" ({tipo})" if tipo else ""))
    partes.append(f"Área: {alcance.get('infraestructura') or 'Todas'}")
    partes.append(f"Especie: {alcance.get('especie') or 'Todas'}")
    return " · ".join(partes)


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
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="archivos_exportacion_suministros",
                    tipo_operacion="INSERT",
                    id_usuario=id_usuario,
                    resultado="EXITOSO",
                    id_activo_biologico=reporte.id_activo_biologico,
                    detalle_causa="Reporte de gastos exportado correctamente.",
                    datos_nuevos={
                        "accion": "EXPORTACION",
                        "id_reporte_gasto_acumulado": reporte.id_reporte_gasto_acumulado,
                        "id_archivo": str(guardado.id_archivo),
                        "formato": guardado.formato,
                        "total_registros": guardado.total_registros,
                    },
                )
            )
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
        alcance = self.generador.detalle_port.describir_alcance(
            reporte.id_activo_biologico, reporte.id_infraestructura, reporte.id_especie
        )
        encabezado = [
            _linea_alcance(reporte, alcance),
            f"Período: {reporte.fecha_inicio:%d/%m/%Y} – {reporte.fecha_fin:%d/%m/%Y} "
            f"({_PERIODO.get(reporte.tipo_periodo, reporte.tipo_periodo.lower())})",
            f"Gasto total acumulado: {moneda(reporte.gasto_total_acumulado)}",
        ]
        if reporte.gasto_promedio_individuo is not None:
            encabezado.append(f"Gasto promedio por individuo: {moneda(reporte.gasto_promedio_individuo)}")
        pie = [
            f"{_CATEGORIA.get(d.categoria, d.categoria.capitalize())}: {moneda(d.subtotal)} ({numero(d.porcentaje, 1)} %) — "
            f"{d.num_registros} registros"
            for d in reporte.desglose_categorias
        ]
        if reporte.desglose_temporal:  # RF-77 pasos 5 y 7, CA-5
            pie.append(f"Desglose {_PERIODO.get(reporte.tipo_periodo, 'por período').lower()}:")
            pie.extend(f"{d.fecha_inicio:%d/%m/%Y} – {d.fecha_fin:%d/%m/%Y}: {moneda(d.monto)}"
                       for d in reporte.desglose_temporal)
        if reporte.tendencia is not None:  # RF-77 paso 6
            t = reporte.tendencia
            if t.variacion_porcentual is not None:
                sentido = "subió" if t.variacion_porcentual > 0 else "bajó" if t.variacion_porcentual < 0 else "se mantuvo"
                signo = "+" if t.variacion_porcentual > 0 else ""
                pie.append(f"Tendencia frente al período anterior: {signo}{numero(t.variacion_porcentual, 1)} % (el gasto {sentido}; "
                           f"período anterior {moneda(t.gasto_periodo_anterior)})")
            else:
                pie.append(f"Tendencia frente al período anterior: {_TENDENCIA.get(t.estado, t.estado.lower())}")
            if t.nota:
                pie.append(t.nota)
        for nota in (reporte.nota_bajas, reporte.causa_no_calculable_promedio, reporte.mensaje):
            if nota:
                pie.append(nota)
        filas = [[fecha(f[0]), _CATEGORIA.get(f[1], f[1]), f[2], moneda(f[3]), _ESTADO.get(f[4], f[4])] for f in filas]
        documento = Documento(
            titulo="Reporte de Gastos Acumulados",
            columnas=_COLUMNAS_PDF,
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
                    detalle_causa=f"Fallo al generar el PDF: {exc}"[:1000],
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("No se pudo auditar el fallo de exportación PDF del reporte de gastos.")
