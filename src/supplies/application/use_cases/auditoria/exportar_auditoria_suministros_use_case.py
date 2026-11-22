# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-08 | Arekkazu | INC-M05-265-G32: textos visibles sin códigos de requisito ni de módulo |
# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-278-G39 RF-80: conservar UUID y versión de integridad al exportar auditoría. |
# | 2026-11-10 | Arekkazu | CP111/TC-DIS-208 RF-80: PDF y Excel con encabezados y valores legibles; el PDF ya no recorta columnas |
# | 2026-11-12 | Arekkazu | USAB-M05-M06 N-07 RF-80: Excel y PDF nombran al usuario (o al Sistema) y al activo |
"""Caso de uso: exportar la bitácora de auditoría de M05 en CSV/Excel/PDF (RF-80, CU-06).

Formatos elegidos por el usuario (no solo CSV, a diferencia del precedente de
RF-81 en ``exportar_historial_sincrono_use_case.py``): Excel vía ``openpyxl``
y PDF vía ``reportlab.platypus``, ambas dependencias nuevas del proyecto
(``requirements.txt``). Los 3 formatos comparten las mismas columnas y el
mismo límite de registros exportables (``_LIMITE_EXPORTACION``); no hay modo
asíncrono para este CU (a diferencia de RF-81) porque el volumen de
``auditorias_suministros`` es órdenes de magnitud menor.

El CSV conserva los nombres técnicos de las columnas y los valores crudos: es el
formato para integraciones. Excel y PDF los leen personas, así que llevan
encabezados y valores en palabras (mismas 22 columnas, mismo orden que el CSV), y
el PDF reparte el ancho de la hoja entre las columnas con salto de línea (CP111).
"""
from __future__ import annotations

import csv
import io
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from src.shared.errors import ValidationError
from src.supplies.application.use_cases.exportacion.generador_archivos import (
    Documento,
    fecha,
    generar_excel,
    generar_pdf,
    legible,
    moneda,
)
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
    "id_evento_m05",
    "version_hash_integridad",
]

# Encabezado legible de cada columna, en el mismo orden que ``_CAMPOS``.
_ETIQUETAS = {
    "id_auditoria_suministro": "N.º de evento",
    "entidad_afectada": "Entidad afectada",
    "tipo_operacion": "Operación",
    "id_usuario": "Usuario",
    "resultado": "Resultado",
    "fecha_evento": "Fecha y hora",
    "id_activo_biologico": "Activo",
    "id_ciclo_productivo": "Ciclo productivo",
    "id_gestion_fases": "Instancia del ciclo",
    "costo_afectado": "Costo afectado",
    "origen_precio": "Origen del precio",
    "clasificacion_registro": "Clasificación",
    "retencion_aplicable": "Retención",
    "hash_integridad": "Huella de integridad",
    "registro_incompleto": "Registro incompleto",
    "detalle_causa": "Detalle",
    "numero_reintentos": "Reintentos",
    "ip_origen": "IP de origen",
    "id_sesion": "Sesión",
    "fecha_emision": "Fecha de emisión",
    "id_evento_m05": "Identificador del evento",
    "version_hash_integridad": "Versión de la huella",
}
_OPERACION = {
    "SUMINISTRO_REGISTRADO": "Suministro registrado", "SUMINISTRO_CORREGIDO": "Suministro corregido",
    "REGISTRO_FALLIDO": "Registro fallido", "CONFLICTO_CONCURRENCIA": "Conflicto de concurrencia",
    "CICLO_CONSOLIDADO": "Ciclo consolidado", "PROVISION_INCREMENTAL_ENTREGADA": "Provisión entregada",
    "PROVISION_INCREMENTAL_FALLIDA": "Provisión fallida", "REPORTE_COSTOS_GENERADO": "Reporte de costos generado",
    "PRECIO_MANUAL_INGRESADO": "Precio manual ingresado", "ACUMULADO_ACTUALIZADO": "Acumulado actualizado",
    "PROVISION_PENDIENTE": "Provisión pendiente", "CONSULTA_HISTORIAL_EJECUTADA": "Consulta de historial",
    "EXPORTACION_HISTORIAL_GENERADA": "Exportación generada", "EXPORTACION_HISTORIAL_ELIMINADA": "Exportación eliminada",
    "REGISTRO": "Registro", "CORRECCION": "Corrección",
    "INSERT": "Creación", "UPDATE": "Modificación", "DELETE": "Eliminación", "SELECT": "Consulta",
}
_RESULTADO = {"EXITOSO": "Exitoso", "FALLIDO": "Fallido", "PARCIAL": "Parcial", "RECHAZADO": "Rechazado", "ADVERTENCIA": "Advertencia"}
_CLASIFICACION = {"NIC41": "NIC-41 (5 años)", "TECNICO": "Técnico (1 año)"}
_ORIGEN_PRECIO = {"MANUAL": "Precio manual", "M40_AUTOMATICO": "Precio automático", "CATALOGO": "Catálogo"}


def _entidad(nombre: Optional[str]) -> str:
    """Nombre de tabla o de entidad en palabras: «reporte_gastos_acumulados» → «Reporte gastos acumulados»."""
    return (nombre or "").replace("_", " ").strip().capitalize()


def _legible(campo: str, valor) -> str:
    if valor is None or valor == "":
        return ""
    if campo == "tipo_operacion":
        return legible(valor, _OPERACION)
    if campo == "resultado":
        return legible(valor, _RESULTADO)
    if campo == "clasificacion_registro":
        return legible(valor, _CLASIFICACION)
    if campo == "origen_precio":
        return legible(valor, _ORIGEN_PRECIO)
    if campo == "entidad_afectada":
        return _entidad(valor)
    if campo == "costo_afectado":
        return moneda(valor)
    if campo in ("fecha_evento", "fecha_emision"):
        return fecha(valor)
    if campo == "registro_incompleto":
        return "Sí" if valor else "No"
    return str(valor)


def _celda(e: EventoAuditoriaSuministroConsulta, campo: str) -> str:
    """Quién y sobre qué activo, por su nombre (N-07); el CSV conserva los ids para cruzarlos."""
    if campo == "id_usuario" and e.id_usuario is not None:
        return e.nombre_usuario or "Otro usuario"
    if campo == "id_activo_biologico" and e.id_activo_biologico is not None:
        return e.nombre_activo or ""
    return _legible(campo, getattr(e, campo))


def _documento(items: list[EventoAuditoriaSuministroConsulta]) -> Documento:
    filas = [[_celda(e, campo) for campo in _CAMPOS] for e in items]
    return Documento(
        titulo="Bitácora de auditoría de suministros",
        columnas=[_ETIQUETAS[c] for c in _CAMPOS],
        filas=filas,
        encabezado=[f"Total de registros: {len(items)}"],
    )


_FORMATOS_VALIDOS = {"csv", "xlsx", "pdf"}


def _valor(v) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
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
        return generar_excel(_documento(items))

    def _a_pdf(self, items: list[EventoAuditoriaSuministroConsulta]) -> bytes:
        return generar_pdf(_documento(items), datetime.now(timezone.utc))
