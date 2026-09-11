"""Caso de uso: exportar la bitácora de auditoría de M05 en CSV/Excel/PDF (RF-80, CU-06).

Formatos elegidos por el usuario (no solo CSV, a diferencia del precedente de
RF-81 en ``exportar_historial_sincrono_use_case.py``): Excel vía ``openpyxl``
y PDF vía ``reportlab.platypus``, ambas dependencias nuevas del proyecto
(``requirements.txt``). Los 3 formatos comparten las mismas columnas y el
mismo límite de registros exportables (``_LIMITE_EXPORTACION``); no hay modo
asíncrono para este CU (a diferencia de RF-81) porque el volumen de
``auditorias_suministros`` es órdenes de magnitud menor.
"""
from __future__ import annotations

import csv
import io
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from src.shared.errors import ValidationError
from src.supplies.domain.entities.evento_auditoria_suministro import EventoAuditoriaSuministroConsulta
from src.supplies.domain.repositories.auditoria_suministro_read_port import (
    AuditoriaSuministroReadPort,
    FiltrosAuditoriaSuministro,
)

_LIMITE_EXPORTACION = 10_000

_CAMPOS = [
    "id_auditoria_suministro",
    "entidad_afectada",
    "tipo_operacion",
    "id_usuario",
    "resultado",
    "fecha_evento",
    "id_activo_biologico",
    "id_ciclo_productivo",
    "id_gestion_fases",
    "costo_afectado",
    "origen_precio",
    "clasificacion_registro",
    "retencion_aplicable",
    "hash_integridad",
    "registro_incompleto",
    "detalle_causa",
    "numero_reintentos",
    "ip_origen",
    "id_sesion",
    "fecha_emision",
]

_FORMATOS_VALIDOS = {"csv", "xlsx", "pdf"}


def _valor(v) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _evento_a_dict(e: EventoAuditoriaSuministroConsulta) -> dict:
    return {campo: _valor(getattr(e, campo)) for campo in _CAMPOS}


class ExportarAuditoriaSuministrosUseCase:
    def __init__(self, read_port: AuditoriaSuministroReadPort) -> None:
        self.read_port = read_port

    def exportar(
        self, filtros: FiltrosAuditoriaSuministro, *, formato: str
    ) -> tuple[bytes, str, str]:
        if formato not in _FORMATOS_VALIDOS:
            raise ValidationError(
                code="FORMATO_EXPORTACION_INVALIDO",
                message=f"Formato '{formato}' no soportado. Use csv, xlsx o pdf.",
                field="formato",
            )

        filtros_export = replace(filtros, pagina=1, registros_por_pagina=_LIMITE_EXPORTACION)
        items, _ = self.read_port.consultar(filtros_export)

        if formato == "csv":
            return (
                self._a_csv(items).encode("utf-8"),
                "text/csv",
                "Auditoria_Suministros.csv",
            )
        if formato == "xlsx":
            return (
                self._a_xlsx(items),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "Auditoria_Suministros.xlsx",
            )
        return (
            self._a_pdf(items),
            "application/pdf",
            "Auditoria_Suministros.pdf",
        )

    def _a_csv(self, items: list[EventoAuditoriaSuministroConsulta]) -> str:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=_CAMPOS)
        writer.writeheader()
        for e in items:
            writer.writerow(_evento_a_dict(e))
        return output.getvalue()

    def _a_xlsx(self, items: list[EventoAuditoriaSuministroConsulta]) -> bytes:
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = "Auditoria Suministros"
        ws.append(_CAMPOS)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for e in items:
            fila = _evento_a_dict(e)
            ws.append([fila[campo] for campo in _CAMPOS])
        for columna in ws.columns:
            largo_max = max((len(str(c.value)) for c in columna if c.value is not None), default=10)
            ws.column_dimensions[columna[0].column_letter].width = min(largo_max + 2, 40)

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def _a_pdf(self, items: list[EventoAuditoriaSuministroConsulta]) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        elementos = [
            Paragraph("Bitácora de Auditoría — Módulo de Suministros (RF-80)", styles["Title"]),
            Paragraph(f"Generado: {datetime.now(timezone.utc).isoformat()}", styles["Normal"]),
            Paragraph(f"Total de registros: {len(items)}", styles["Normal"]),
            Spacer(1, 12),
        ]
        filas = [_CAMPOS] + [
            [str(_evento_a_dict(e).get(campo) or "") for campo in _CAMPOS] for e in items
        ]
        tabla = Table(filas, repeatRows=1)
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
                ]
            )
        )
        elementos.append(tabla)
        doc.build(elementos)
        return buffer.getvalue()
