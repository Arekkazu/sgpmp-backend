# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-87/92/93: descarga del comprobante, del estado de resultados y del informe |
"""Caso de uso: arma el documento descargable (CSV, Excel o PDF) de un reporte de M06.

- Comprobante NIC 41 (RF-87 v1.1): CSV y PDF, para registrarlo en SIGCON como comprobante manual.
- Estado de resultados (RF-93): solo APROBADO.
- Informe de revelaciones (RF-92): solo APROBADO o ARCHIVADO (CA-6); Excel o PDF.
Reutiliza el generador de archivos de M05 (mismo formato institucional)."""
from __future__ import annotations

from datetime import datetime, timezone

from src.financial_valuation.domain.repositories.periodo_repository import PeriodoRepository
from src.financial_valuation.domain.repositories.reporte_repository import ReporteRepository
from src.shared.errors import BusinessRuleError, NotFoundError
from src.supplies.application.use_cases.exportacion.generador_archivos import (
    Documento,
    generar_csv,
    generar_excel,
    generar_pdf,
)

ETIQUETAS_COMPONENTES = {
    "ganancia_transformacion_biologica": "Ganancia por transformación biológica",
    "ganancia_precio_mercado": "Ganancia por variación de precio de mercado",
    "ganancia_reconocimiento_inicial": "Ganancia en el reconocimiento inicial",
    "ingresos_productos_agricolas": "Ingresos por productos agrícolas",
    "ganancia_ajustes_periodos_anteriores": "Ajustes de períodos anteriores (ganancia)",
    "perdida_transformacion_biologica": "Pérdida por transformación biológica",
    "perdida_precio_mercado": "Pérdida por variación de precio de mercado",
    "perdida_reconocimiento_inicial": "Pérdida en el reconocimiento inicial",
    "costos_mantenimiento": "Costos de mantenimiento",
    "inversiones_llevadas_a_gasto": "Inversiones llevadas a gasto",
    "bajas_activos": "Bajas de activos (valor en libros)",
    "depreciacion_activos_costo": "Depreciación de activos al costo",
    "deterioro_activos_costo": "Deterioro de activos al costo",
    "perdida_ajustes_periodos_anteriores": "Ajustes de períodos anteriores (pérdida)",
}
_TIPOS = {"csv": ("text/csv", "csv"), "excel": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
          "pdf": ("application/pdf", "pdf")}


def _archivo(doc: Documento, formato: str) -> tuple[bytes, str, str]:
    if formato not in _TIPOS:
        raise BusinessRuleError(code="FORMATO_NO_SOPORTADO", message="Formato no soportado: use csv, excel o pdf.")
    contenido = {"csv": generar_csv, "excel": generar_excel}.get(formato, lambda d: generar_pdf(d, datetime.now(timezone.utc)))(doc)
    tipo, extension = _TIPOS[formato]
    return contenido, tipo, extension


class ExportarReporteUseCase:
    def __init__(self, periodos: PeriodoRepository, reportes: ReporteRepository) -> None:
        self.periodos = periodos
        self.reportes = reportes

    def comprobantes(self, id_periodo_contable: int, formato: str) -> tuple[bytes, str, str]:
        periodo = self.periodos.obtener(id_periodo_contable)
        if periodo is None or periodo.estado != "CERRADO":
            raise BusinessRuleError(code="PERIODO_NO_CERRADO", message="El comprobante existe solo para períodos cerrados.")
        filas = []
        for c in self.periodos.comprobantes(id_periodo_contable):
            for linea in c["lineas"]:
                filas.append([c["codigo"], c["fecha_comprobante"], c["tipo_hecho"], c["especie"], linea["cuenta_debito"],
                              linea["cuenta_credito"], linea["valor"], c["hash_integridad"]])
        doc = Documento(titulo=f"Comprobante NIC 41 {periodo.fecha_inicio:%Y-%m}",
                        columnas=["Comprobante", "Fecha", "Hecho", "Especie", "Cuenta débito", "Cuenta crédito", "Valor", "Hash"],
                        filas=filas, encabezado=[f"Titular: {periodo.numero_id_tributaria}",
                                                 f"Período: {periodo.fecha_inicio} a {periodo.fecha_fin}"])
        return (*_archivo(doc, formato), f"comprobante_nic41_{periodo.numero_id_tributaria}_{periodo.fecha_fin:%Y%m}")

    def estado_resultados(self, id_estado: int, formato: str) -> tuple[bytes, str, str]:
        estado = self.reportes.obtener_estado(id_estado)
        if estado is None:
            raise NotFoundError(code="ESTADO_RESULTADOS_NO_ENCONTRADO", message="El estado de resultados no existe.")
        if estado["estado"] != "APROBADO":
            raise BusinessRuleError(code="ESTADO_RESULTADOS_NO_APROBADO", message="Solo se descarga el estado aprobado.")
        componentes = estado["componentes"] or {}
        filas = [[etiqueta, componentes.get(clave, "0")] for clave, etiqueta in ETIQUETAS_COMPONENTES.items()]
        doc = Documento(titulo="Estado de resultados del período agropecuario", columnas=["Componente", "Valor (COP)"],
                        filas=filas, encabezado=[f"Versión {estado['version']}", f"Filtros: {estado['filtros'] or 'consolidado'}"],
                        pie=[f"Total ingresos: {estado['total_ingresos']}", f"Total gastos: {estado['total_gastos']}",
                             f"Resultado neto: {estado['resultado_neto']}"])
        return (*_archivo(doc, formato), f"estado_resultados_v{estado['version']}")

    def informe(self, id_informe: int, formato: str) -> tuple[bytes, str, str]:
        informe = self.reportes.obtener_informe(id_informe)
        if informe is None:
            raise NotFoundError(code="INFORME_NO_ENCONTRADO", message="El informe no existe.")
        if informe["estado"] not in ("APROBADO", "ARCHIVADO"):  # R2 / CA-6
            raise BusinessRuleError(code="INFORME_NO_APROBADO", message="Solo se descargan informes aprobados.")
        filas = []
        for seccion, valor in (informe["contenido"] or {}).items():
            if isinstance(valor, list):
                for elemento in valor or [{}]:
                    filas.append([seccion, "; ".join(f"{k}: {v}" for k, v in (elemento or {}).items()) if isinstance(elemento, dict) else elemento])
            elif isinstance(valor, dict):
                filas.append([seccion, "; ".join(f"{k}: {v}" for k, v in valor.items())])
            else:
                filas.append([seccion, valor])
        doc = Documento(titulo=f"Informe de revelaciones NIC 41 {informe['version_informe']}", columnas=["Sección", "Detalle"],
                        filas=filas, encabezado=[f"Estado: {informe['estado']}", f"Hash: {informe['hash_informe']}"])
        return (*_archivo(doc, formato), f"revelaciones_nic41_{informe['version_informe']}")
