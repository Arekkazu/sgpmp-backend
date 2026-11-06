# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-96/RF-97: Mappers 02/06, rango alineado, envelope y hash de contenido |
"""Núcleo AAEF de M07 (RF-96 v2.0, RF-97 v3.0, RF-AE02 v3.0). Python puro, sin BD ni FastAPI.

Transforma lo que M06 ya calculó; no recalcula ni decide nada contable (Anticorruption Layer).
Ajustes al RF verificados contra el código de SIGCON y AgroFusion (ver el plan de M07):
- Un ``02`` por **factura** (proveedor + prefijo + número) con una línea por registro de costo:
  M06 reparte una factura entre varios activos y SIGCON rechaza una segunda factura con el mismo
  número de proveedor en la empresa.
- ``Prefix = ""`` si la factura no tiene prefijo: AgroFusion acepta el texto vacío y SIGCON usa
  solo el número; exigirlo tumbaría el envelope completo por un costo.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from src.financial_valuation.domain.services.nic41 import CERO, hash_sha256, truncar2
from src.financial_valuation.domain.value_objects.nic41 import ETIQUETA_HECHO, ETIQUETA_SUBTIPO

ESTANDAR_AAEF = "1.0"  # versión del estándar que acepta SIGCON (RF-98 D-17.11), no la del contrato
MONEDA = "COP"
MAPPER_COMPRAS = "COMPRAS"
MAPPER_COMPROBANTE_NIC41 = "COMPROBANTE_NIC41"
MAPPERS_DISPONIBLES = (MAPPER_COMPRAS, MAPPER_COMPROBANTE_NIC41)
TIPO_COMPRA = {"Code": "02", "Name": "Factura de compra"}
TIPO_COMPROBANTE = {"Code": "06", "Name": "Comprobante contable NIC 41"}


class AaefError(Exception):
    """Error de negocio de la generación (RF-97 FA, RF-96 FA). ``codigo`` va al cliente; ``mensaje`` es legible."""

    def __init__(self, codigo: str, mensaje: str, campo: Optional[str] = None, detalle: Optional[dict] = None):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.campo, self.detalle = codigo, mensaje, campo, detalle or {}


@dataclass(frozen=True)
class Titular:
    nit: str
    razon_social: str


@dataclass(frozen=True)
class Periodo:
    fecha_inicio: date
    fecha_fin: date
    estado: str

    @property
    def etiqueta(self) -> str:
        if (self.fecha_inicio.year, self.fecha_inicio.month) == (self.fecha_fin.year, self.fecha_fin.month):
            return f"{self.fecha_inicio:%Y-%m}"
        return f"{self.fecha_inicio:%Y-%m} a {self.fecha_fin:%Y-%m}"


@dataclass(frozen=True)
class CostoFactura:
    """Un registro de RF-90 con vehículo factura de compra (un activo de un reparto)."""

    id_registro_costo: int
    tercero_nit: str
    tercero_razon_social: str
    factura_prefijo: Optional[str]
    factura_numero: str
    fecha_factura: date
    fecha_vencimiento_factura: Optional[date]
    subtipo_costo: str
    monto_costo: Decimal
    cuenta_debito: Optional[str]
    activo: str


@dataclass(frozen=True)
class ComprobanteNic41:
    codigo: str
    tipo_hecho: str
    especie: str
    fecha_comprobante: date
    lineas: list[dict]


@dataclass(frozen=True)
class SistemaOrigen:
    system_id: str
    system_name: str
    environment: str


# --- RF-97 5.1: rango alineado a períodos cerrados del titular ---------------------------------

def validar_rango(periodos: Iterable[Periodo], desde: date, hasta: date) -> list[Periodo]:
    """Devuelve los períodos del rango, o ``RANGO_NO_ALINEADO`` / ``PERIODO_NO_CERRADO``."""
    periodos = sorted(periodos, key=lambda p: p.fecha_inicio)
    if not periodos:
        raise AaefError("RANGO_NO_ALINEADO", "El productor todavía no tiene períodos contables.", "desde")
    inicios = {p.fecha_inicio for p in periodos}
    fines = {p.fecha_fin for p in periodos}
    if desde not in inicios or hasta not in fines:
        sugerido_desde = _cercano(periodos, desde).fecha_inicio
        sugerido_hasta = max(_cercano(periodos, hasta).fecha_fin, sugerido_desde)
        raise AaefError(
            "RANGO_NO_ALINEADO",
            "El rango debe empezar el primer día y terminar el último día de períodos contables. "
            f"Rango válido más cercano: {sugerido_desde.isoformat()} a {sugerido_hasta.isoformat()}.",
            "desde" if desde not in inicios else "hasta",
        )
    del_rango = [p for p in periodos if p.fecha_inicio >= desde and p.fecha_fin <= hasta]
    for periodo in del_rango:
        if periodo.estado != "CERRADO":
            raise AaefError("PERIODO_NO_CERRADO",
                            f"El período {periodo.etiqueta} no está cerrado. Solo se pueden consultar períodos cerrados.")
    return del_rango


def _cercano(periodos: list[Periodo], dia: date) -> Periodo:
    for periodo in periodos:
        if periodo.fecha_inicio <= dia <= periodo.fecha_fin:
            return periodo
    return min(periodos, key=lambda p: min(abs((p.fecha_inicio - dia).days), abs((p.fecha_fin - dia).days)))


# --- RF-96: Mappers ------------------------------------------------------------------------------

def _cuenta(valor: Optional[str], documento: str) -> str:
    if not valor or not str(valor).isdigit():
        raise AaefError("MAPPER_FALLIDO", f"El documento {documento} no tiene una cuenta contable válida. "
                        "Revise la matriz contable en Configuración contable.", "accounting_account",
                        {"mapper": MAPPER_COMPRAS, "documento": documento})
    return str(valor)


def _totales(subtotal: Decimal, saldo: Decimal) -> dict:
    return {"Subtotal": subtotal, "TotalVAT": CERO, "TotalWithholdings": CERO, "TotalDiscounts": CERO,
            "TotalPayment": subtotal, "OutstandingBalance": saldo}


def mapear_compras(costos: Iterable[CostoFactura]) -> list[dict]:
    """Mapper de Compras (``02``): un documento por factura, una línea por registro (RF-AE02 5.3)."""
    facturas: dict[tuple, list[CostoFactura]] = {}
    for costo in costos:
        if not (costo.tercero_nit and costo.tercero_razon_social and costo.factura_numero and costo.fecha_factura):
            raise AaefError("MAPPER_FALLIDO", f"El costo {costo.id_registro_costo} no tiene completos los datos de la "
                            "factura del proveedor.", "Header", {"mapper": MAPPER_COMPRAS})
        clave = (costo.tercero_nit, costo.factura_prefijo or "", costo.factura_numero)
        facturas.setdefault(clave, []).append(costo)
    documentos = []
    for (nit, prefijo, numero), registros in facturas.items():
        registros.sort(key=lambda c: c.id_registro_costo)
        primero = registros[0]
        document_id = f"COS-{primero.id_registro_costo}-{primero.fecha_factura:%Y%m%d}"
        lineas = []
        for costo in registros:
            valor = truncar2(costo.monto_costo)
            lineas.append({
                "Code": costo.subtipo_costo,
                "Name": ETIQUETA_SUBTIPO.get(costo.subtipo_costo, costo.subtipo_costo).capitalize(),
                "Description": f"Activo biológico {costo.activo}",
                "LineType": costo.subtipo_costo,
                "accounting_account": [_cuenta(costo.cuenta_debito, document_id)],
                "Quantity": Decimal(1),
                "UnitPrice": valor,
                "Value": valor,
                "Taxes": [],
            })
        subtotal = sum((ln["Value"] for ln in lineas), CERO)
        emision = primero.fecha_factura.isoformat()
        documentos.append({
            "Header": {"DocumentId": document_id, "Prefix": prefijo, "Serial": numero, "Type": dict(TIPO_COMPRA),
                       "IssueDate": emision,
                       "DueDate": (primero.fecha_vencimiento_factura or primero.fecha_factura).isoformat(),
                       "Status": "ACTIVE", "UpdatedAt": emision},
            "ThirdParty": {"NIT": nit, "Name": primero.tercero_razon_social},
            "Totals": _totales(subtotal, subtotal),
            "Lines": lineas,
        })
    return documentos


def mapear_comprobantes(comprobantes: Iterable[ComprobanteNic41], titular: Titular) -> list[dict]:
    """Mapper de Comprobante NIC 41 (``06``): una línea por par de cuentas (RF-AE02 5.4)."""
    documentos = []
    prefijo_codigo = f"NIC-{titular.nit}-"
    for comprobante in comprobantes:
        if not comprobante.codigo.startswith(prefijo_codigo):
            raise AaefError("MAPPER_FALLIDO", f"El comprobante {comprobante.codigo} no pertenece al productor consultado.",
                            "DocumentId", {"mapper": MAPPER_COMPROBANTE_NIC41})
        fecha = comprobante.fecha_comprobante.isoformat()
        nombre = ETIQUETA_HECHO.get(comprobante.tipo_hecho, comprobante.tipo_hecho)
        lineas = []
        for par in comprobante.lineas:
            valor = truncar2(Decimal(str(par["valor"])))
            if valor <= 0:
                raise AaefError("MAPPER_FALLIDO", f"El comprobante {comprobante.codigo} tiene una línea sin valor.",
                                "Value", {"mapper": MAPPER_COMPROBANTE_NIC41})
            lineas.append({
                "Code": comprobante.tipo_hecho, "Name": nombre,
                "Description": f"{comprobante.especie} · {comprobante.fecha_comprobante:%Y-%m}",
                "LineType": comprobante.tipo_hecho,
                "accounting_account": [_cuenta(par.get("cuenta_debito"), comprobante.codigo),
                                       _cuenta(par.get("cuenta_credito"), comprobante.codigo)],
                "Quantity": Decimal(1), "UnitPrice": valor, "Value": valor, "Taxes": [],
            })
        subtotal = sum((ln["Value"] for ln in lineas), CERO)
        documentos.append({
            "Header": {"DocumentId": comprobante.codigo, "Prefix": "NIC",
                       "Serial": comprobante.codigo[len(prefijo_codigo):], "Type": dict(TIPO_COMPROBANTE),
                       "IssueDate": fecha, "DueDate": fecha, "Status": "ACTIVE", "UpdatedAt": fecha},
            "ThirdParty": {"NIT": titular.nit, "Name": titular.razon_social},
            "Totals": _totales(subtotal, CERO),
            "Lines": lineas,
        })
    return documentos


# --- RF-97: envelope, hash y tamaño ---------------------------------------------------------------

def hash_contenido(invoices: list[dict]) -> str:
    """SHA-256 de ``{invoices, transactions}`` canónico (claves ordenadas, importes de 2 decimales). RF-97 5.5."""
    return hash_sha256({"invoices": invoices, "transactions": []})


def construir_envelope(
    titular: Titular, desde: date, hasta: date, sistema: SistemaOrigen, generado_por: str, generado_en: date,
    compras: list[dict], comprobantes: list[dict],
) -> dict:
    """Envelope con los nombres exactos que valida AgroFusion (RF-97 5.4)."""
    invoices = sorted(compras + comprobantes, key=lambda d: d["Header"]["DocumentId"])
    bruto = sum((d["Totals"]["Subtotal"] for d in invoices), CERO)
    neto = sum((d["Totals"]["TotalPayment"] for d in invoices), CERO)
    return {
        "metadata": {
            "ExchangeId": f"SGPMP-{titular.nit}-{desde:%Y%m%d}-{hasta:%Y%m%d}-{secrets.randbelow(10 ** 7):07d}",
            "GeneratedAt": generado_en.isoformat(),
            "StandardVersion": ESTANDAR_AAEF,
            "RequestedPeriod": {"From": desde.isoformat(), "To": hasta.isoformat()},
            "SourceSystem": {"SystemId": sistema.system_id, "SystemName": sistema.system_name,
                             "SystemNIT": titular.nit, "Environment": sistema.environment},
            "GeneratedBy": generado_por,
        },
        "summary": {"TotalDocuments": len(invoices), "TotalInvoices": len(invoices), "TotalTransactions": 0,
                    "TotalGrossAmount": bruto, "TotalNet": neto, "Currency": MONEDA},
        "invoices": invoices,
        "transactions": [],
    }


def verificar_cuadre(envelope: dict) -> None:
    """RF-96 Fase 4: ``TotalPayment = Subtotal = Σ Value`` con diferencia 0,00 en cada documento."""
    for documento in envelope["invoices"]:
        suma = sum((ln["Value"] for ln in documento["Lines"]), CERO)
        totales = documento["Totals"]
        if not (suma == totales["Subtotal"] == totales["TotalPayment"]):
            raise AaefError("MAPPER_FALLIDO", f"El documento {documento['Header']['DocumentId']} no cuadra.", "Totals")


def serializar(envelope: dict) -> bytes:
    """JSON UTF-8 del envelope; los importes salen como número (AgroFusion los valida como ``float``)."""
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"),
                      default=lambda v: float(v) if isinstance(v, Decimal) else str(v)).encode("utf-8")


def controlar_tamano(cuerpo: bytes, limite_bytes: int) -> None:
    if len(cuerpo) > limite_bytes:
        raise AaefError("TAMANO_EXCEDIDO", f"La información del rango supera {limite_bytes // (1024 * 1024)} MB. "
                        "Consulte un rango menor (un período).")
