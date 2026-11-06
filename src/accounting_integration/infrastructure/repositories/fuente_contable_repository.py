# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-97: lectura de M06/M09 para el envelope AAEF |
"""Lectura de M06 y M09 para RF-97, como el usuario de servicio.

El acceso ya se autorizó antes (permiso y todas las fincas del titular, RF-95 5.3). Leer como
Sistema evita que RLS recorte el resultado: la condición (d) contaría solo las fincas visibles y un
costo de un activo trasladado a otra finca desaparecería del envelope sin aviso."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.accounting_integration.domain.repositories.fuente_contable_repository import FuenteContableRepository
from src.accounting_integration.domain.services.aaef import ComprobanteNic41, CostoFactura, Periodo, Titular
from src.financial_valuation.infrastructure.repositories.sql import fila, filas
from src.shared.database import como_sistema

_RANGO = "p.numero_id_tributaria = :nit AND p.fecha_inicio >= :desde AND p.fecha_fin <= :hasta"


class SqlAlchemyFuenteContableRepository(FuenteContableRepository):
    def __init__(self, db: Session):
        self.db = db

    def titular(self, nit: str) -> Optional[Titular]:
        with como_sistema(self.db):
            f = fila(self.db, """
                SELECT numero_id_tributaria AS nit,
                       (array_agg(razon_social ORDER BY fecha_actualizacion DESC NULLS LAST))[1] AS razon_social
                FROM modulo9.fincas WHERE numero_id_tributaria = :nit AND es_activo GROUP BY numero_id_tributaria
            """, {"nit": nit})
        return Titular(f["nit"], f["razon_social"]) if f else None

    def fincas_titular(self, nit: str) -> set[int]:
        with como_sistema(self.db):
            return {f["id_finca"] for f in filas(self.db, "SELECT id_finca FROM modulo9.fincas "
                                                          "WHERE numero_id_tributaria = :nit AND es_activo", {"nit": nit})}

    def fincas_usuario(self, id_usuario: int) -> set[int]:
        with como_sistema(self.db):
            return {f["id_finca"] for f in filas(self.db, "SELECT id_finca FROM modulo9.usuarios_fincas "
                                                          "WHERE id_usuario = :u AND es_activo", {"u": id_usuario})}

    def periodos(self, nit: str) -> list[Periodo]:
        return [Periodo(f["fecha_inicio"], f["fecha_fin"], f["estado"]) for f in filas(self.db, """
            SELECT fecha_inicio, fecha_fin, estado::text AS estado FROM modulo6.periodos_contables
            WHERE numero_id_tributaria = :nit ORDER BY fecha_inicio
        """, {"nit": nit})]

    def costos_factura(self, nit: str, desde: date, hasta: date) -> list[CostoFactura]:
        # Por período del costo, no por fecha de factura: el contenido de un rango cerrado no cambia.
        with como_sistema(self.db):
            resultado = filas(self.db, f"""
                SELECT c.id_registro_costo, c.tercero_nit, c.tercero_razon_social, c.factura_prefijo, c.factura_numero,
                       c.fecha_factura, c.fecha_vencimiento_factura, c.subtipo_costo::text AS subtipo_costo, c.monto_costo,
                       c.cuenta_debito, COALESCE(a.identificador, a.id_activo_biologico::text) AS activo
                FROM modulo6.registros_costos c
                JOIN modulo6.periodos_contables p ON p.id_periodo_contable = c.id_periodo_contable
                JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = c.id_activo_biologico
                WHERE {_RANGO} AND c.vehiculo_contable = 'FACTURA_COMPRA' AND c.estado = 'REGISTRADO' AND NOT c.es_reverso
                  AND NOT EXISTS (SELECT 1 FROM modulo6.registros_costos r WHERE r.id_registro_costo_compensado = c.id_registro_costo)
                ORDER BY c.id_registro_costo
            """, {"nit": nit, "desde": desde, "hasta": hasta})
        return [CostoFactura(**f) for f in resultado]

    def comprobantes(self, nit: str, desde: date, hasta: date) -> list[ComprobanteNic41]:
        with como_sistema(self.db):
            resultado = filas(self.db, """
                SELECT cp.codigo, cp.tipo_hecho::text AS tipo_hecho, e.nombre AS especie, cp.fecha_comprobante,
                       cp.json_lineas AS lineas
                FROM modulo6.comprobantes_nic41 cp JOIN modulo9.especies e ON e.id_especie = cp.id_especie
                WHERE cp.numero_id_tributaria = :nit AND cp.fecha_comprobante BETWEEN :desde AND :hasta
                ORDER BY cp.codigo
            """, {"nit": nit, "desde": desde, "hasta": hasta})
        return [ComprobanteNic41(**f) for f in resultado]

    def lineas_sin_trazabilidad(self, nit: str, desde: date, hasta: date) -> int:
        return fila(self.db, f"""
            SELECT count(*) AS n FROM modulo6.lineas_asiento_nic41 l
            JOIN modulo6.periodos_contables p ON p.id_periodo_contable = l.id_periodo_contable
            WHERE {_RANGO} AND l.estado_trazabilidad = 'PENDIENTE_TRAZABILIDAD'
        """, {"nit": nit, "desde": desde, "hasta": hasta})["n"]
