# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-COT v1.1: cotizaciones de venta (sin efecto contable) |
# | 2026-11-05 | Arekkazu | M06 RF-COT: el UPDATE solo acepta columnas de lista cerrada (Bearer CWE-89) |
"""Implementación SQL de :class:`CotizacionRepository`."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.repositories.cotizacion_repository import CotizacionRepository
from src.financial_valuation.infrastructure.repositories.sql import escribir, fila, filas

_COLUMNAS = """c.id_cotizacion, c.fecha_emision, c.id_periodo_contable, c.activos_cotizados, c.valor_razonable_referencia,
    c.valor_cotizacion_propuesto, c.condiciones, c.estado::text AS estado, c.estado_al_cierre::text AS estado_al_cierre,
    c.fecha_vencimiento, c.motivo_anulacion, c.id_usuario, c.fecha_registro, c.version, c.fecha_actualizacion,
    p.estado::text AS estado_periodo"""
# Columnas que ``actualizar`` puede escribir: sus nombres se interpolan en el SQL.
_EDITABLES = {"valor_cotizacion_propuesto", "condiciones", "fecha_vencimiento", "motivo_anulacion", "estado"}
_JOIN = "FROM modulo6.cotizaciones c JOIN modulo6.periodos_contables p ON p.id_periodo_contable = c.id_periodo_contable"


class SqlAlchemyCotizacionRepository(CotizacionRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def agregar(self, datos: dict) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.cotizaciones (fecha_emision, id_periodo_contable, activos_cotizados, valor_cotizacion_propuesto,
                condiciones, estado, fecha_vencimiento, id_usuario, fecha_registro, valor_razonable_referencia)
            VALUES (:fecha_emision, :id_periodo_contable, :activos_cotizados, :valor_cotizacion_propuesto, :condiciones,
                'COTIZADO', :fecha_vencimiento, :id_usuario, now(), :valor_razonable_referencia)
            RETURNING id_cotizacion""", datos)

    def obtener(self, id_cotizacion: int) -> Optional[dict]:
        return fila(self.db, f"SELECT {_COLUMNAS} {_JOIN} WHERE c.id_cotizacion = :id", {"id": id_cotizacion})

    def actualizar(self, id_cotizacion: int, version: int, cambios: dict) -> bool:
        if not cambios or not cambios.keys() <= _EDITABLES:
            raise ValueError(f"Columnas no editables: {sorted(cambios.keys() - _EDITABLES) or 'ninguna'}")
        asignaciones = ", ".join(f"{campo} = :{campo}" for campo in cambios if campo != "estado")
        if "estado" in cambios:
            asignaciones = ", ".join(filter(None, [asignaciones, "estado = CAST(:estado AS modulo6.enum_cotizaciones_estado_cotizacion)"]))
        return bool(escribir(self.db, f"""
            UPDATE modulo6.cotizaciones SET {asignaciones}, version = version + 1, fecha_actualizacion = now()
            WHERE id_cotizacion = :id AND version = :version""", {**cambios, "id": id_cotizacion, "version": version}))

    def listar(self, filtros: dict) -> list[dict]:
        condiciones, params = ["true"], {}
        if filtros.get("estado"):
            condiciones.append("c.estado::text = :estado")
            params["estado"] = filtros["estado"]
        if filtros.get("id_activo_biologico"):
            condiciones.append(":activo = ANY(c.activos_cotizados)")
            params["activo"] = filtros["id_activo_biologico"]
        if filtros.get("id_periodo_contable"):
            condiciones.append("c.id_periodo_contable = :periodo")
            params["periodo"] = filtros["id_periodo_contable"]
        return filas(self.db, f"SELECT {_COLUMNAS} {_JOIN} WHERE {' AND '.join(condiciones)} "
                              "ORDER BY c.fecha_emision DESC, c.id_cotizacion DESC LIMIT 500", params)

    def vencer(self, hoy: date) -> list[dict]:
        return filas(self.db, """
            UPDATE modulo6.cotizaciones c SET estado = 'VENCIDA', version = version + 1, fecha_actualizacion = now()
            FROM modulo6.periodos_contables p
            WHERE p.id_periodo_contable = c.id_periodo_contable AND p.estado <> 'CERRADO'
              AND c.estado = 'COTIZADO' AND c.fecha_vencimiento < :hoy
            RETURNING c.id_cotizacion, c.id_periodo_contable""", {"hoy": hoy})

    def fijar_estado_al_cierre(self, id_periodo_contable: int) -> None:
        escribir(self.db, """UPDATE modulo6.cotizaciones SET estado_al_cierre = estado
                             WHERE id_periodo_contable = :p AND estado_al_cierre IS NULL""", {"p": id_periodo_contable})
