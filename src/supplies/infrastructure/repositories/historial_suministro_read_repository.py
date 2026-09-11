"""Implementación de :class:`HistorialSuministroReadPort` (RF-81).

SQL propio con ``text()`` sobre ``modulo5.registro_suministro`` (no la vista
``vw_m05_historial_suministros_detalle``: su ``LEFT JOIN tipos_alimentos ON
id_tipo_elemento::text = id_idempotencia::text`` es un join espurio —
``id_idempotencia`` es un UUID aleatorio, nunca coincide con un id de
catálogo. Aquí se resuelve la descripción uniendo directamente contra
``registros_consumo_alimentos``/``registros_medicamentos`` por
``id_registro_rf75``/``id_registro_rf76``, que sí es la relación real).

El enriquecimiento M02 (Fase 4 del RF-81: nombre del activo, especie, ciclo,
estado del ciclo) se resuelve en la misma consulta/transacción — ``modulo2``
y ``modulo9`` viven en la misma base de datos que ``modulo5`` (no hay una
llamada de red real a un servicio M02 separado), así que no existe un modo de
fallo de timeout genuino que simular; ``datos_contexto_no_disponibles`` es
siempre ``False`` en esta implementación (ver ``cu04_gaps_bd_rf77_rf81.md``).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.supplies.domain.entities.historial_suministro import (
    FiltrosHistorialSuministro,
    LineaHistorialSuministro,
    ResultadoHistorialSuministro,
)
from src.supplies.domain.repositories.historial_suministro_read_port import HistorialSuministroReadPort
from src.supplies.domain.value_objects.historial_suministro_enums import TipoSuministroFiltro

_JOINS = """
    FROM modulo5.registro_suministro rs
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = rs.id_activo_biologico
    JOIN modulo9.especies esp ON esp.id_especie = ab.id_especie
    JOIN modulo9.ciclos_productivos cp ON cp.id_ciclo_productivo = rs.id_ciclo_productivo
    LEFT JOIN modulo5.registros_consumo_alimentos rca ON rca.id_registro_rf75 = rs.id_registro_rf75
    LEFT JOIN modulo5.registros_medicamentos rm ON rm.id_registro_rf76 = rs.id_registro_rf76
    LEFT JOIN LATERAL (
        SELECT es_activa FROM modulo2.gestiones_fases
        WHERE id_activo_biologico = rs.id_activo_biologico AND id_ciclo_productiva = rs.id_ciclo_productivo
        ORDER BY es_activa DESC, fecha_inicio DESC LIMIT 1
    ) gf ON true
"""

_WHERE = """
    WHERE rs.id_activo_biologico = :id_activo_biologico
      AND (:id_ciclo_productivo IS NULL OR rs.id_ciclo_productivo = :id_ciclo_productivo)
      AND (:fecha_inicio IS NULL OR rs.fecha_aplicacion >= :fecha_inicio)
      AND (:fecha_fin IS NULL OR rs.fecha_aplicacion <= :fecha_fin)
      AND (
          :tipo_suministro IS NULL
          OR (:tipo_suministro = 'ALIMENTO' AND rs.id_registro_rf75 IS NOT NULL)
          OR (:tipo_suministro = 'MEDICAMENTO' AND rs.id_registro_rf76 IS NOT NULL)
      )
      AND (:origen_precio IS NULL OR rs.origen_precio = :origen_precio)
      AND (:costo_min IS NULL OR rs.costo_registro >= :costo_min)
      AND (:costo_max IS NULL OR rs.costo_registro <= :costo_max)
      AND (:ids_permitidos IS NULL OR rs.id_activo_biologico = ANY(:ids_permitidos))
"""

_SQL_PAGINA = text(
    f"""
    SELECT rs.id_registro_suministro, rs.id_activo_biologico, rs.id_ciclo_productivo,
           CASE WHEN rs.id_registro_rf75 IS NOT NULL THEN 'ALIMENTO' ELSE 'MEDICAMENTO' END AS tipo_suministro,
           COALESCE(rca.tipo_alimento, rm.nombre_medicamento, '') AS descripcion,
           rs.fecha_aplicacion, rs.cantidad, rs.unidad_medida,
           rs.precio_unitario_resuelto AS precio_unitario, rs.costo_registro, rs.origen_precio,
           rs.tipo_operacion, rs.observacion, rs.fecha_registro,
           ab.identificador AS nombre_activo, esp.nombre AS especie, cp.nombre AS nombre_ciclo,
           CASE WHEN gf.es_activa THEN 'ACTIVO' ELSE 'CERRADO' END AS estado_ciclo
    {_JOINS}
    {_WHERE}
    ORDER BY rs.fecha_aplicacion DESC, rs.id_registro_suministro DESC
    LIMIT :limite OFFSET :offset
    """
)

_SQL_TOTAL = text(f"SELECT COUNT(*) AS total, COALESCE(SUM(rs.costo_registro), 0) AS monto {_JOINS} {_WHERE}")

_SQL_POR_TIPO = text(
    f"""
    SELECT CASE WHEN rs.id_registro_rf75 IS NOT NULL THEN 'ALIMENTO' ELSE 'MEDICAMENTO' END AS tipo,
           COUNT(*) AS total, COALESCE(SUM(rs.costo_registro), 0) AS monto
    {_JOINS} {_WHERE}
    GROUP BY 1
    """
)

_SQL_POR_CICLO = text(
    f"""
    SELECT cp.nombre AS ciclo, COUNT(*) AS total, COALESCE(SUM(rs.costo_registro), 0) AS monto
    {_JOINS} {_WHERE}
    GROUP BY cp.nombre
    """
)

_SQL_CONTAR_TOTAL_ACTIVO = text(
    "SELECT COUNT(*) FROM modulo5.registro_suministro WHERE id_activo_biologico = :id_activo_biologico"
)

_SQL_CICLO_PERTENECE_A_ACTIVO = text(
    """
    SELECT EXISTS (
        SELECT 1 FROM modulo2.gestiones_fases
        WHERE id_activo_biologico = :id_activo_biologico AND id_ciclo_productiva = :id_ciclo_productivo
    )
    """
)


def _params(filtros: FiltrosHistorialSuministro, ids_activos_permitidos: Optional[list[int]]) -> dict:
    tipo = filtros.tipo_suministro_filtro
    tipo_normalizado = None if tipo in (None, TipoSuministroFiltro.TODOS.value) else tipo
    origen = filtros.origen_precio_filtro
    origen_normalizado = None if origen in (None, "TODOS") else origen
    return {
        "id_activo_biologico": filtros.id_activo_biologico,
        "id_ciclo_productivo": filtros.id_ciclo_productivo,
        "fecha_inicio": filtros.fecha_inicio_filtro,
        "fecha_fin": filtros.fecha_fin_filtro,
        "tipo_suministro": tipo_normalizado,
        "origen_precio": origen_normalizado,
        "costo_min": filtros.costo_min,
        "costo_max": filtros.costo_max,
        "ids_permitidos": ids_activos_permitidos,
    }


class SqlAlchemyHistorialSuministroReadRepository(HistorialSuministroReadPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def contar_total_activo(self, id_activo_biologico: int) -> int:
        return self.db.execute(
            _SQL_CONTAR_TOTAL_ACTIVO, {"id_activo_biologico": id_activo_biologico}
        ).scalar_one()

    def ciclo_pertenece_a_activo(self, id_activo_biologico: int, id_ciclo_productivo: int) -> bool:
        return self.db.execute(
            _SQL_CICLO_PERTENECE_A_ACTIVO,
            {"id_activo_biologico": id_activo_biologico, "id_ciclo_productivo": id_ciclo_productivo},
        ).scalar_one()

    def consultar(
        self,
        filtros: FiltrosHistorialSuministro,
        ids_activos_permitidos: Optional[list[int]],
    ) -> ResultadoHistorialSuministro:
        params = _params(filtros, ids_activos_permitidos)

        # Tipos SERVICIO_VETERINARIO/INSEMINACION no tienen tabla origen en modulo5 (gap doc):
        # cortocircuita a resultado vacío en vez de ejecutar una consulta que nunca puede matchear.
        if filtros.tipo_suministro_filtro in (
            TipoSuministroFiltro.SERVICIO_VETERINARIO.value,
            TipoSuministroFiltro.INSEMINACION.value,
        ):
            return ResultadoHistorialSuministro()

        offset = (filtros.pagina - 1) * filtros.registros_por_pagina
        filas_pagina = self.db.execute(
            _SQL_PAGINA, {**params, "limite": filtros.registros_por_pagina, "offset": offset}
        ).mappings().all()
        total_fila = self.db.execute(_SQL_TOTAL, params).mappings().one()
        por_tipo = self.db.execute(_SQL_POR_TIPO, params).mappings().all()
        por_ciclo = self.db.execute(_SQL_POR_CICLO, params).mappings().all()

        lineas = [
            LineaHistorialSuministro(
                id_registro_suministro=str(f["id_registro_suministro"]),
                id_activo_biologico=f["id_activo_biologico"],
                id_ciclo_productivo=f["id_ciclo_productivo"],
                tipo_suministro=f["tipo_suministro"],
                descripcion=f["descripcion"],
                fecha_aplicacion=f["fecha_aplicacion"],
                cantidad=f["cantidad"],
                unidad_medida=f["unidad_medida"],
                precio_unitario=f["precio_unitario"],
                costo_registro=f["costo_registro"],
                origen_precio=f["origen_precio"],
                tipo_operacion=f["tipo_operacion"] or "REGISTRO",
                observacion=f["observacion"],
                fecha_registro=f["fecha_registro"],
                nombre_activo=f["nombre_activo"],
                especie=f["especie"],
                nombre_ciclo=f["nombre_ciclo"],
                estado_ciclo=f["estado_ciclo"],
            )
            for f in filas_pagina
        ]
        return ResultadoHistorialSuministro(
            lineas=lineas,
            total_registros_filtrados=total_fila["total"],
            monto_total_filtrado=total_fila["monto"] or Decimal("0"),
            desglose_por_tipo_suministro={f["tipo"]: {"total": f["total"], "monto": f["monto"]} for f in por_tipo},
            desglose_por_ciclo={f["ciclo"]: {"total": f["total"], "monto": f["monto"]} for f in por_ciclo},
        )
