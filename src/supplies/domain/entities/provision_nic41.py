# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: contenido del consolidado a M06    |
"""Entidad de dominio ``ProvisionNic41`` (RF-79 — reporte consolidado NIC 41).

Python puro. Representa una fila de ``modulo5.provision_nic41``, usada
exclusivamente con ``modalidad=CONSOLIDADO`` en este CU (ver
``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md`` Gap 11 — el valor
``INCREMENTAL`` del enum queda sin usar). Inmutable una vez persistida:
correcciones crean una fila nueva con ``version_reporte`` incrementado e
``id_reporte_anterior`` apuntando a la versión previa, nunca ``UPDATE`` sobre
la existente. ``hash_integridad`` lo calcula el trigger de BD
(``trg_provision_hash``), no la app.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(eq=False)
class ProvisionNic41:
    """Reporte consolidado de provisión de costos NIC-41 de una instancia de ciclo."""

    id_activo_biologico: int
    modalidad: str
    monto_provision: Decimal
    id_ciclo_productivo: Optional[int] = None
    id_gestion_fases: Optional[int] = None
    desglose_categoria: dict[str, Decimal] = field(default_factory=dict)
    lista_registros: list[dict] = field(default_factory=list)
    version_reporte: int = 1
    id_reporte_anterior: Optional[int] = None
    motivo_correccion: Optional[str] = None
    es_reporte_potencialmente_incompleto: bool = False
    estado: str = "GENERADO"
    id_provision: Optional[int] = None
    hash_integridad: Optional[str] = None
    fecha_generacion: Optional[datetime] = None
    fecha_entrega_m06: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        id_activo_biologico: int,
        id_ciclo_productivo: int,
        id_gestion_fases: int,
        monto_provision: Decimal,
        desglose_categoria: dict[str, Decimal],
        lista_registros: list[dict],
        es_reporte_potencialmente_incompleto: bool = False,
        version_reporte: int = 1,
        id_reporte_anterior: Optional[int] = None,
        motivo_correccion: Optional[str] = None,
    ) -> "ProvisionNic41":
        """Construye un reporte consolidado nuevo, sin persistir."""
        return cls(
            id_activo_biologico=id_activo_biologico,
            id_ciclo_productivo=id_ciclo_productivo,
            id_gestion_fases=id_gestion_fases,
            modalidad="CONSOLIDADO",
            monto_provision=monto_provision,
            desglose_categoria=desglose_categoria,
            lista_registros=lista_registros,
            es_reporte_potencialmente_incompleto=es_reporte_potencialmente_incompleto,
            version_reporte=version_reporte,
            id_reporte_anterior=id_reporte_anterior,
            motivo_correccion=motivo_correccion,
            estado="GENERADO",
        )

    def contenido_m06(self) -> dict:
        """Reporte consolidado para M06 (RF-79 Salida 2), sin el envoltorio del evento."""
        fechas = sorted(r["fecha_aplicacion"] for r in self.lista_registros if r.get("fecha_aplicacion"))
        return {
            "id_reporte": self.id_provision,
            "id_activo": self.id_activo_biologico,
            "id_ciclo": self.id_ciclo_productivo,
            "id_gestion_fases": self.id_gestion_fases,
            "monto_total_ciclo": str(self.monto_provision),
            "desglose_por_categoria": {k: str(v) for k, v in self.desglose_categoria.items()},
            "lista_registros_suministros": self.lista_registros,
            "cantidad_registros": len(self.lista_registros),
            "fecha_primer_registro": fechas[0] if fechas else None,
            "fecha_ultimo_registro": fechas[-1] if fechas else None,
            "version_reporte": self.version_reporte,
            "id_reporte_anterior": self.id_reporte_anterior,
            "motivo_correccion": self.motivo_correccion,
            "reporte_potencialmente_incompleto": self.es_reporte_potencialmente_incompleto,
            "hash_integridad": self.hash_integridad,
            "timestamp_generacion": self.fecha_generacion.isoformat() if self.fecha_generacion else None,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProvisionNic41):
            return NotImplemented
        if self.id_provision is None or other.id_provision is None:
            return self is other
        return self.id_provision == other.id_provision

    def __hash__(self) -> int:
        return hash(self.id_provision)
