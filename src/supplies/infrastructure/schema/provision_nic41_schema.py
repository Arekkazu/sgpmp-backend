"""Schemas de respuesta para las provisiones consolidadas NIC-41 (RF-79)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ProvisionNic41Response(BaseModel):
    """Reporte consolidado NIC-41 de una instancia de ciclo productivo.

    ``lista_registros`` viene paginada en el endpoint de consulta puntual
    (``pagina``/``por_pagina``); ``total_registros`` siempre refleja el total
    real del reporte, no el tamaño de la página devuelta.
    """

    id_provision: Optional[int]
    id_activo_biologico: int
    id_ciclo_productivo: Optional[int]
    id_gestion_fases: Optional[int]
    modalidad: str
    monto_provision: Decimal
    desglose_categoria: dict[str, Decimal]
    lista_registros: list[dict]
    total_registros: int
    version_reporte: int
    id_reporte_anterior: Optional[int]
    motivo_correccion: Optional[str]
    es_reporte_potencialmente_incompleto: bool
    estado: str
    hash_integridad: Optional[str]
    fecha_generacion: Optional[datetime.datetime]
    fecha_entrega_m06: Optional[datetime.datetime]

    @classmethod
    def desde_entidad(cls, provision, *, pagina: int = 1, por_pagina: int = 50) -> "ProvisionNic41Response":
        total = len(provision.lista_registros)
        inicio = (pagina - 1) * por_pagina
        pagina_registros = provision.lista_registros[inicio : inicio + por_pagina]
        return cls(
            id_provision=provision.id_provision,
            id_activo_biologico=provision.id_activo_biologico,
            id_ciclo_productivo=provision.id_ciclo_productivo,
            id_gestion_fases=provision.id_gestion_fases,
            modalidad=provision.modalidad,
            monto_provision=provision.monto_provision,
            desglose_categoria=provision.desglose_categoria,
            lista_registros=pagina_registros,
            total_registros=total,
            version_reporte=provision.version_reporte,
            id_reporte_anterior=provision.id_reporte_anterior,
            motivo_correccion=provision.motivo_correccion,
            es_reporte_potencialmente_incompleto=provision.es_reporte_potencialmente_incompleto,
            estado=provision.estado,
            hash_integridad=provision.hash_integridad,
            fecha_generacion=provision.fecha_generacion,
            fecha_entrega_m06=provision.fecha_entrega_m06,
        )


class ListaVersionesProvisionResponse(BaseModel):
    """Cadena de versiones de un reporte consolidado (sin ``lista_registros``, solo metadatos)."""

    total: int
    versiones: list[ProvisionNic41Response]
