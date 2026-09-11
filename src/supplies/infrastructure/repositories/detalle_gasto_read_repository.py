"""Implementación de :class:`DetalleGastoReadPort` (RF-77).

SQL propio con ``text()`` (patrón de ``historial_telemetria_repository.py``)
en vez de las vistas ``vw_m05_reporte_gastos_detalle``: la vista no expone
``id_infraestructura``/``id_especie``, necesarios para filtrar reportes
agregados por infraestructura o especie. Consolida RF-75 (consumo de
alimento) + RF-76 (medicamentos), replicando el SQL literal del proceso de
RF-77 (Restricción 1: solo ``VALIDADO``).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.supplies.domain.entities.reporte_gasto import LineaGasto
from src.supplies.domain.repositories.detalle_gasto_read_port import DetalleGastoReadPort

_SQL_DETALLE = text(
    """
    SELECT 'ALIMENTACION' AS categoria,
           rca.id_consumo_alimeto AS id_origen,
           rca.id_activo_biologico,
           ab.id_infraestructura,
           ab.id_especie,
           COALESCE(rca.fecha_consumo, rca.fecha_registro::date) AS fecha,
           COALESCE(ta.nombre, rca.tipo_alimento) AS descripcion,
           rca.cantidad_suministrada AS cantidad,
           rca.costo_unitario,
           rca.costo_total AS monto,
           rca.estado_registro AS estado
    FROM modulo5.registros_consumo_alimentos rca
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = rca.id_activo_biologico
    LEFT JOIN modulo5.tipos_alimentos ta ON ta.id_tipo_elemento = rca.id_tipo_alimento
    WHERE rca.estado_registro = 'VALIDADO'
      AND COALESCE(rca.fecha_consumo, rca.fecha_registro::date) BETWEEN :fecha_inicio AND :fecha_fin
      AND (:id_activo_biologico IS NULL OR rca.id_activo_biologico = :id_activo_biologico)
      AND (:id_infraestructura IS NULL OR ab.id_infraestructura = :id_infraestructura)
      AND (:id_especie IS NULL OR ab.id_especie = :id_especie)

    UNION ALL

    SELECT 'MEDICACION' AS categoria,
           rm.id_registro_medicamento AS id_origen,
           rm.id_activo_biologico,
           ab.id_infraestructura,
           ab.id_especie,
           rm.fecha_aplicacion AS fecha,
           rm.nombre_medicamento AS descripcion,
           rm.cantidad AS cantidad,
           rm.costo_unitario_medicamento AS costo_unitario,
           rm.costo_total_medicamento AS monto,
           rm.estado_registro AS estado
    FROM modulo5.registros_medicamentos rm
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = rm.id_activo_biologico
    WHERE rm.estado_registro = 'VALIDADO'
      AND rm.fecha_aplicacion BETWEEN :fecha_inicio AND :fecha_fin
      AND (:id_activo_biologico IS NULL OR rm.id_activo_biologico = :id_activo_biologico)
      AND (:id_infraestructura IS NULL OR ab.id_infraestructura = :id_infraestructura)
      AND (:id_especie IS NULL OR ab.id_especie = :id_especie)
    """
)


class SqlAlchemyDetalleGastoReadRepository(DetalleGastoReadPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def consultar(
        self,
        *,
        fecha_inicio: date,
        fecha_fin: date,
        id_activo_biologico: Optional[int] = None,
        id_infraestructura: Optional[int] = None,
        id_especie: Optional[int] = None,
        categorias: Optional[list[str]] = None,
    ) -> list[LineaGasto]:
        filas = self.db.execute(
            _SQL_DETALLE,
            {
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "id_activo_biologico": id_activo_biologico,
                "id_infraestructura": id_infraestructura,
                "id_especie": id_especie,
            },
        ).mappings().all()

        lineas = [
            LineaGasto(
                categoria=f["categoria"],
                id_origen=f["id_origen"],
                id_activo_biologico=f["id_activo_biologico"],
                id_infraestructura=f["id_infraestructura"],
                id_especie=f["id_especie"],
                fecha=f["fecha"],
                descripcion=f["descripcion"] or "",
                cantidad=f["cantidad"],
                costo_unitario=f["costo_unitario"],
                monto=f["monto"] if f["costo_unitario"] is not None else None,
                estado=f["estado"],
            )
            for f in filas
        ]
        if categorias:
            lineas = [l for l in lineas if l.categoria in categorias]
        return lineas
