# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: catálogos NIC 41 del módulo financiero |
# | 2026-11-05 | Arekkazu | M06: rótulos legibles de hechos y sentidos para mensajes y archivos |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-302-G01 RF-82/RF-86: hecho RECONOCIMIENTO_DONACION |
"""Catálogos cerrados de M06 (mismos valores que los ENUM de ``modulo6``)."""
from __future__ import annotations

from enum import Enum


class TipoHecho(str, Enum):
    """RF-86 v2.0: hechos contables que producen líneas de asiento."""

    RECONOCIMIENTO_NACIMIENTO = "RECONOCIMIENTO_NACIMIENTO"
    # INC-M06-302-G01: la donación tiene su propia cuenta de ingreso en la matriz (RF-109).
    RECONOCIMIENTO_DONACION = "RECONOCIMIENTO_DONACION"
    RECONOCIMIENTO_DIFERENCIA = "RECONOCIMIENTO_DIFERENCIA"
    VARIACION_VR_TB = "VARIACION_VR_TB"
    VARIACION_VR_PM = "VARIACION_VR_PM"
    PRODUCTO_AGRICOLA = "PRODUCTO_AGRICOLA"
    CONSUMO_INSUMO = "CONSUMO_INSUMO"
    MANO_OBRA_PROPIA = "MANO_OBRA_PROPIA"
    BAJA_ACTIVO = "BAJA_ACTIVO"
    AJUSTE_PERIODO_ANTERIOR = "AJUSTE_PERIODO_ANTERIOR"
    # NIC 41 ¶54-55: el modelo de costo exige asentar depreciación y deterioro (no estaban en RF-86).
    DEPRECIACION_ACTIVO_COSTO = "DEPRECIACION_ACTIVO_COSTO"
    DETERIORO_ACTIVO_COSTO = "DETERIORO_ACTIVO_COSTO"


class Sentido(str, Enum):
    """Qué par de cuentas de la matriz aplica a un hecho (RF-86: la pérdida invierte el par)."""

    GANANCIA = "GANANCIA"
    PERDIDA = "PERDIDA"
    UNICO = "UNICO"
    TRASLADO = "TRASLADO"  # cosecha de consumo: inventario contra activo biológico
    CAPITALIZACION = "CAPITALIZACION"  # inversión capitalizada en el activo


# Rótulos para lo que lee el usuario (mensajes, PDF y CSV): el valor del enum nunca sale tal cual.
ETIQUETA_HECHO = {
    "RECONOCIMIENTO_NACIMIENTO": "Reconocimiento por nacimiento",
    "RECONOCIMIENTO_DONACION": "Reconocimiento por donación",
    "RECONOCIMIENTO_DIFERENCIA": "Diferencia en el reconocimiento inicial",
    "VARIACION_VR_TB": "Variación por transformación biológica",
    "VARIACION_VR_PM": "Variación por precio de mercado",
    "PRODUCTO_AGRICOLA": "Producto agrícola",
    "CONSUMO_INSUMO": "Consumo de insumos",
    "MANO_OBRA_PROPIA": "Mano de obra propia",
    "BAJA_ACTIVO": "Baja del activo",
    "AJUSTE_PERIODO_ANTERIOR": "Ajuste de un período anterior",
    "DEPRECIACION_ACTIVO_COSTO": "Depreciación (modelo de costo)",
    "DETERIORO_ACTIVO_COSTO": "Deterioro (modelo de costo)",
}
ETIQUETA_SENTIDO = {"GANANCIA": "ganancia", "PERDIDA": "pérdida", "UNICO": "único", "TRASLADO": "traslado",
                    "CAPITALIZACION": "capitalización"}
ETIQUETA_SUBTIPO = {"ALIMENTO": "alimento", "MEDICAMENTO": "medicamento", "MANO_OBRA": "mano de obra",
                    "VETERINARIO": "servicio veterinario", "TRANSPORTE": "transporte", "COMISION": "comisión",
                    "IMPUESTO_TRANSACCION": "impuesto de la transacción", "SACRIFICIO": "sacrificio",
                    "INVERSION_DIRECTA": "inversión directa", "OTRO": "otro"}
ETIQUETA_NATURALEZA = {"MANTENIMIENTO": "mantenimiento", "INVERSION": "inversión", "VENTA": "costo de venta"}


def estado_legible(estado: str) -> str:
    """«EN_TRATAMIENTO» → «en tratamiento»: el estado de Activos biológicos dicho como se lee."""
    return estado.replace("_", " ").lower()


class TipoEvidencia(str, Enum):
    """RF-91: tipo de evidencia que sustenta una línea."""

    IOT_DIRECTO = "IOT_DIRECTO"
    REGISTRO_MANUAL = "REGISTRO_MANUAL"
    VARIACION_PRECIO = "VARIACION_PRECIO"
    EVENTO_SANITARIO = "EVENTO_SANITARIO"
    CIERRE_PERIODO = "CIERRE_PERIODO"


class FuentePrecio(str, Enum):
    MERCADO_ACTIVO = "MERCADO_ACTIVO"
    UPRA = "UPRA"
    ESTIMADA = "ESTIMADA"


# RF-89: la jerarquía de fuente prevalece sobre la fecha de vigencia.
PRIORIDAD_FUENTES = (FuentePrecio.MERCADO_ACTIVO, FuentePrecio.UPRA, FuentePrecio.ESTIMADA)


class CategoriaPrecio(str, Enum):
    PESO_KG = "PESO_KG"
    POR_CABEZA = "POR_CABEZA"
    PRODUCTO = "PRODUCTO"  # por unidad de la métrica de producción (RF-85)


class Clasificacion(str, Enum):
    """NIC 41 ¶43-44: productor (genera productos) o consumible (se cosecha el activo)."""

    PRODUCCION = "PRODUCCION"
    CONSUMO = "CONSUMO"


class IndicadorValoracion(str, Enum):
    VALOR_RAZONABLE = "VALOR_RAZONABLE"
    VALORACION_POR_COSTO = "VALORACION_POR_COSTO"


class TipoCierre(str, Enum):
    MENSUAL = "MENSUAL"
    TRIMESTRAL = "TRIMESTRAL"
    ANUAL = "ANUAL"


class EstadoPeriodo(str, Enum):
    ABIERTO = "ABIERTO"
    EN_CIERRE = "EN_CIERRE"
    CERRADO = "CERRADO"


class NaturalezaCosto(str, Enum):
    MANTENIMIENTO = "MANTENIMIENTO"
    INVERSION = "INVERSION"
    VENTA = "VENTA"


class SubtipoCosto(str, Enum):
    ALIMENTO = "ALIMENTO"
    MEDICAMENTO = "MEDICAMENTO"
    MANO_OBRA = "MANO_OBRA"
    VETERINARIO = "VETERINARIO"
    INVERSION_DIRECTA = "INVERSION_DIRECTA"
    TRANSPORTE = "TRANSPORTE"
    COMISION = "COMISION"
    IMPUESTO_TRANSACCION = "IMPUESTO_TRANSACCION"
    SACRIFICIO = "SACRIFICIO"
    OTRO = "OTRO"


# RF-90 eje 1: naturaleza que implica cada subtipo (OTRO la declara el Contador).
NATURALEZA_POR_SUBTIPO = {
    SubtipoCosto.ALIMENTO: NaturalezaCosto.MANTENIMIENTO,
    SubtipoCosto.MEDICAMENTO: NaturalezaCosto.MANTENIMIENTO,
    SubtipoCosto.MANO_OBRA: NaturalezaCosto.MANTENIMIENTO,
    SubtipoCosto.VETERINARIO: NaturalezaCosto.MANTENIMIENTO,
    SubtipoCosto.INVERSION_DIRECTA: NaturalezaCosto.INVERSION,
    SubtipoCosto.TRANSPORTE: NaturalezaCosto.VENTA,
    SubtipoCosto.COMISION: NaturalezaCosto.VENTA,
    SubtipoCosto.IMPUESTO_TRANSACCION: NaturalezaCosto.VENTA,
    SubtipoCosto.SACRIFICIO: NaturalezaCosto.VENTA,
}


class OrigenCosto(str, Enum):
    CONSUMO_INVENTARIO = "CONSUMO_INVENTARIO"
    MANO_OBRA_PROPIA = "MANO_OBRA_PROPIA"
    COMPRA_PROVEEDOR = "COMPRA_PROVEEDOR"
    SERVICIO_TERCERO = "SERVICIO_TERCERO"


ORIGENES_CON_PROVEEDOR = (OrigenCosto.COMPRA_PROVEEDOR, OrigenCosto.SERVICIO_TERCERO)


class VehiculoContable(str, Enum):
    FACTURA_COMPRA = "FACTURA_COMPRA"
    ASIENTO_NIC41 = "ASIENTO_NIC41"
    NINGUNO = "NINGUNO"


class MetodoReparto(str, Enum):
    POR_CABEZAS = "POR_CABEZAS"
    POR_BIOMASA = "POR_BIOMASA"


class Severidad(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# M09 no define regiones: los parámetros de costos de venta y los precios valen para toda la finca.
REGION_GENERAL = "GENERAL"
