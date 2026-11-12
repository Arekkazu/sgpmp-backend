# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..88: cálculos, reconocimientos, mediciones, variaciones y valoración por costo |
# | 2026-11-05 | Arekkazu | M06 RF-83..88: listados del período y datos del modelo de costo por activo |
# | 2026-11-08 | Arekkazu | INC-M06-314-G15 RF-83: mediciones del período filtrables por evento y estimación, con id_evento e id_periodo_contable |
# | 2026-11-09 | destroyerban | INC-M06-317-G17 RF-84: cálculo en revisión y validación del valor neto ≤ 0 |
# | 2026-11-09 | destroyerban | INC-M06-320-G24 RF-85 FA-4: la cosecha del 100 % deja el activo en cero e inicia su baja |
# | 2026-11-09 | destroyerban | INC-M06-325-G30 RF-85 RNF-85-05: historial de productos con filtros, evento y usuario |
# | 2026-11-10 | destroyerban | INC-M06-336-G36 RF-86: correctivo de variaciones con aprobación del Contador |
# | 2026-11-10 | Arekkazu | INC-M06-297-G34 RF-86: eventos del período con medición pendiente |
"""Implementación SQL de :class:`ValoracionRepository`."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.valoracion import (
    CalculoValor,
    Medicion,
    Reconocimiento,
    ValoracionCosto,
    VariacionRegistro,
)
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.infrastructure.repositories.sql import CONSUMIDO_POR_COSECHA, a_json, escribir, fila, filas
from src.shared.fechas import nombre_zona_usuario

_COLUMNAS_CALCULO = """id_calculo_valor_razonable, id_activo_biologico, id_precio_mercado, id_periodo_contable, magnitud,
    unidad_magnitud, precio_unitario, valor_razonable_bruto, costo_transporte, costo_comisiones,
    costo_impuestos_transaccion, otros_costos_disposicion, valor_neto, metodo_costo::text AS metodo_costo,
    json_metodo_costo, id_usuario, estado::text AS estado, justificacion, id_parametro_costo_venta, id_evento_magnitud,
    tiene_valor_estimado, fecha_calculo"""

_COLUMNAS_RECONOCIMIENTO = """id_reconocimiento_inicial, id_activo_biologico, estado::text AS estado,
    clasificacion::text AS clasificacion, indicador_valoracion::text AS indicador_valoracion,
    valor_razonable_neto_inicial, fecha_reconocimiento, id_periodo_contable, origen_financiero::text AS origen_financiero,
    costo_adquisicion, id_precio_mercado, id_calculo_valor_razonable, id_valoracion_por_costo, es_apertura,
    cuenta_debito, cuenta_credito"""


# Los cálculos de un producto agrícola (RF-85) no son base de la valoración del activo.
ES_BASE = "COALESCE((json_metodo_costo->>'es_producto')::boolean, false) = false"


# Activo, especie, finca y clasificación de cada registro de los listados del período.
_ACTIVO = """a.identificador, a.tipo::text AS tipo_activo, a.id_especie, e.nombre AS especie, f.nombre AS finca,
    ri.clasificacion::text AS clasificacion"""
_JOIN_ACTIVO = """JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = x.id_activo_biologico
    JOIN modulo9.especies e ON e.id_especie = a.id_especie
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
    JOIN modulo9.fincas f ON f.id_finca = i.id_finca
    LEFT JOIN modulo6.reconocimientos_iniciales ri
           ON ri.id_activo_biologico = a.id_activo_biologico AND ri.estado = 'CONFIRMADO'"""


# Filtros del historial de productos agrícolas (RNF-85-05: activo, período, tipo de producto y rango de valores).
_FILTROS_PRODUCTOS = (
    ("id_periodo_contable", "x.id_periodo_contable = :id_periodo_contable"),
    ("id_activo_biologico", "x.id_activo_biologico = :id_activo_biologico"),
    ("tipo", "x.tipo::text = :tipo"),
    ("id_especie", "a.id_especie = :id_especie"),
    ("producto_agricola", "x.producto_agricola = :producto_agricola"),
    ("valor_min", "x.valor_producto >= :valor_min"),
    ("valor_max", "x.valor_producto <= :valor_max"),
)


def _calculo(f: dict) -> CalculoValor:
    return CalculoValor(**{**f, "json_metodo_costo": f.get("json_metodo_costo") or {}})


class SqlAlchemyValoracionRepository(ValoracionRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- RF-84 ---------------------------------------------------------------------------------

    def agregar_calculo(self, calculo: CalculoValor) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.calculos_valor_razonable (id_activo_biologico, id_precio_mercado, id_parametro_costo_venta,
                valor_razonable_bruto, costo_transporte, costo_comisiones, costo_impuestos_transaccion,
                otros_costos_disposicion, valor_neto, metodo_costo, justificacion, estado, id_usuario, id_periodo_contable,
                magnitud, unidad_magnitud, precio_unitario, id_evento_magnitud, tiene_valor_estimado, json_metodo_costo)
            VALUES (:id_activo_biologico, :id_precio_mercado, :id_parametro_costo_venta, :valor_razonable_bruto,
                :costo_transporte, :costo_comisiones, :costo_impuestos_transaccion, :otros_costos_disposicion, :valor_neto,
                CAST(:metodo_costo AS modulo6.enum_calculos_valor_razonable_metodo_costo), :justificacion,
                CAST(:estado AS modulo6.enum_calculos_valor_razonable_estado), :id_usuario, :id_periodo_contable,
                :magnitud, :unidad_magnitud, :precio_unitario, :id_evento_magnitud, :tiene_valor_estimado,
                CAST(:json_metodo_costo AS jsonb))
            RETURNING id_calculo_valor_razonable
        """, {**{k: getattr(calculo, k) for k in (
            "id_activo_biologico", "id_precio_mercado", "id_parametro_costo_venta", "valor_razonable_bruto",
            "costo_transporte", "costo_comisiones", "costo_impuestos_transaccion", "otros_costos_disposicion",
            "valor_neto", "metodo_costo", "justificacion", "estado", "id_usuario", "id_periodo_contable", "magnitud",
            "unidad_magnitud", "precio_unitario", "id_evento_magnitud", "tiene_valor_estimado")},
            "json_metodo_costo": a_json(calculo.json_metodo_costo)})

    def obtener_calculo(self, id_calculo_valor_razonable: int) -> Optional[CalculoValor]:
        f = fila(self.db, f"""SELECT {_COLUMNAS_CALCULO} FROM modulo6.calculos_valor_razonable
                              WHERE id_calculo_valor_razonable = :id""", {"id": id_calculo_valor_razonable})
        return _calculo(f) if f else None

    def validar_calculo(self, id_calculo_valor_razonable: int, validacion: dict) -> None:
        escribir(self.db, """
            UPDATE modulo6.calculos_valor_razonable
               SET estado = 'CALCULADO',
                   json_metodo_costo = COALESCE(json_metodo_costo, '{}'::jsonb)
                       || jsonb_build_object('validacion_valor_no_positivo', CAST(:validacion AS jsonb))
             WHERE id_calculo_valor_razonable = :id AND estado = 'REVISION_REQUERIDA'
        """, {"id": id_calculo_valor_razonable, "validacion": a_json(validacion)})

    def ultimo_calculo(self, id_activo_biologico: int, hasta: Optional[date] = None) -> Optional[CalculoValor]:
        """Último cálculo CALCULADO del activo (base de la siguiente medición).

        ``None`` si ese cálculo lo consumió una cosecha del 100 % (RF-85 FA-4): el activo vale cero y una baja
        posterior no vuelve a asentar su valor."""
        consumido = CONSUMIDO_POR_COSECHA.format(calculo="c.id_calculo_valor_razonable")
        f = fila(self.db, f"""SELECT {_COLUMNAS_CALCULO}, {consumido} AS consumido_por_cosecha
                              FROM modulo6.calculos_valor_razonable c
                              WHERE id_activo_biologico = :a AND estado = 'CALCULADO' AND {ES_BASE}
                                AND (CAST(:h AS date) IS NULL OR fecha_calculo::date <= :h)
                              ORDER BY fecha_calculo DESC, id_calculo_valor_razonable DESC LIMIT 1""",
                 {"a": id_activo_biologico, "h": hasta})
        if f is None or f.pop("consumido_por_cosecha"):
            return None
        return _calculo(f)

    # --- RF-83 / RF-86 -------------------------------------------------------------------------

    def agregar_medicion(self, medicion: Medicion) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.mediciones_posteriores (id_activo_biologico, id_evento, id_calculo_actual, id_calculo_anterior,
                origen_medicion, valor_razonable_anterior, valor_razonable_actual, ganancia_perdida_transformacion,
                ganancia_perdida_precio_mercado, variacion_total, tiene_valor_estimado, estado, id_periodo_contable,
                fecha_medicion, supuestos_aplicados)
            VALUES (:a, :e, :act, :ant, CAST(:o AS modulo6.enum_mediciones_posteriores_origen_medicion), :vant, :vact,
                :tb, :pm, :tot, :est, 'COMPLETADO', :p, now(), CAST(:sup AS jsonb))
            RETURNING id_medicion_posterior
        """, {"a": medicion.id_activo_biologico, "e": medicion.id_evento, "act": medicion.id_calculo_actual,
              "ant": medicion.id_calculo_anterior, "o": medicion.origen_medicion,
              "vant": medicion.valor_razonable_anterior, "vact": medicion.valor_razonable_actual,
              "tb": medicion.ganancia_perdida_transformacion, "pm": medicion.ganancia_perdida_precio_mercado,
              "tot": medicion.variacion_total, "est": medicion.tiene_valor_estimado, "p": medicion.id_periodo_contable,
              "sup": a_json(medicion.supuestos_aplicados)})

    def agregar_variacion(self, variacion: VariacionRegistro) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.variaciones_valor_razonable (id_activo_biologico, tipo, monto_variacion, variacion_transformacion,
                variacion_precio_mercado, valor_razonable_anterior, valor_razonable_nuevo, id_evento, id_medicion_posterior,
                id_periodo_contable, estado_trazabilidad, tiene_estimacion, id_usuario, fecha_registro, id_precio_mercado,
                id_cierre, id_variacion_corregida)
            VALUES (:a, CAST(:t AS modulo6.enum_variaciones_valor_razonable_tipo), :m, :tb, :pm, :vant, :vnue, :e, :med, :p,
                'VERIFICACION_PENDIENTE', :est, :u, now(), :precio, :cierre, :corregida)
            RETURNING id_variacion_valor_razonable
        """, {"a": variacion.id_activo_biologico, "t": variacion.tipo, "m": variacion.monto_variacion,
              "tb": variacion.variacion_transformacion, "pm": variacion.variacion_precio_mercado,
              "vant": variacion.valor_razonable_anterior, "vnue": variacion.valor_razonable_nuevo, "e": variacion.id_evento,
              "med": variacion.id_medicion_posterior, "p": variacion.id_periodo_contable, "est": variacion.tiene_estimacion,
              "u": variacion.id_usuario, "precio": variacion.id_precio_mercado, "cierre": variacion.id_cierre,
              "corregida": variacion.id_variacion_corregida})

    # --- RF-82 ---------------------------------------------------------------------------------

    def reconocimiento_confirmado(self, id_activo_biologico: int) -> Optional[Reconocimiento]:
        f = fila(self.db, f"""SELECT {_COLUMNAS_RECONOCIMIENTO} FROM modulo6.reconocimientos_iniciales
                              WHERE id_activo_biologico = :a AND estado = 'CONFIRMADO'""", {"a": id_activo_biologico})
        return Reconocimiento(**f) if f else None

    def agregar_reconocimiento(self, datos: dict) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.reconocimientos_iniciales (id_activo_biologico, fecha_reconocimiento, clasificacion,
                indicador_valoracion, id_precio_mercado, valor_razonable_neto_inicial, costos_venta_estimados, estado,
                cuenta_debito, cuenta_credito, id_usuario, id_periodo_contable, fecha_creacion, metodo_valoracion,
                costo_adquisicion, origen_financiero, id_calculo_valor_razonable, id_valoracion_por_costo, es_apertura)
            VALUES (:id_activo_biologico, :fecha_reconocimiento,
                CAST(:clasificacion AS modulo6.enum_reconocimientos_iniciales_clasificacion),
                CAST(:indicador_valoracion AS modulo6.enum_reconocimientos_iniciales_indicador_valoracion),
                :id_precio_mercado, :valor_razonable_neto_inicial, :costos_venta_estimados, 'CONFIRMADO', :cuenta_debito,
                :cuenta_credito, :id_usuario, :id_periodo_contable, now(), :indicador_valoracion, :costo_adquisicion,
                CAST(:origen_financiero AS modulo2.enum_activo_biologico_origen_financiero), :id_calculo_valor_razonable,
                :id_valoracion_por_costo, :es_apertura)
            RETURNING id_reconocimiento_inicial
        """, datos, {"uq_reconocimiento_inicial_id_activo_biologico_confirmado":
                     "El activo ya tiene un reconocimiento inicial confirmado."})

    def revertir_reconocimiento(self, id_reconocimiento, motivo, id_usuario, monto, cuenta_debito, cuenta_credito) -> int:
        id_revision = escribir(self.db, """
            INSERT INTO modulo6.revisiones_reconocimiento (id_reconocimiento_revertido, motivo_revision, monto_revision,
                cuenta_debito, cuenta_credito, id_usuario, fecha_revision)
            VALUES (:r, :m, :monto, :d, :c, :u, now()) RETURNING id_revision_reconocimiento
        """, {"r": id_reconocimiento, "m": motivo, "monto": monto, "d": cuenta_debito, "c": cuenta_credito, "u": id_usuario})
        escribir(self.db, """UPDATE modulo6.reconocimientos_iniciales
                             SET estado = 'REVERTIDO', justificacion_reversion = :m, id_usuario_reversion = :u,
                                 fecha_reversion = now()
                             WHERE id_reconocimiento_inicial = :r AND estado = 'CONFIRMADO'""",
                 {"r": id_reconocimiento, "m": motivo, "u": id_usuario})
        return id_revision

    def dependientes_reconocimiento(self, reconocimiento: Reconocimiento) -> list[dict]:
        return filas(self.db, """
            SELECT 'MEDICION_POSTERIOR' AS tipo, m.id_medicion_posterior AS id, m.fecha_medicion AS fecha
            FROM modulo6.mediciones_posteriores m
            JOIN modulo6.reconocimientos_iniciales r ON r.id_reconocimiento_inicial = :r
            WHERE m.id_activo_biologico = r.id_activo_biologico AND m.fecha_medicion >= r.fecha_creacion
            UNION ALL
            SELECT 'VARIACION', v.id_variacion_valor_razonable, v.fecha_registro
            FROM modulo6.variaciones_valor_razonable v
            JOIN modulo6.reconocimientos_iniciales r ON r.id_reconocimiento_inicial = :r
            WHERE v.id_activo_biologico = r.id_activo_biologico AND v.fecha_registro >= r.fecha_creacion
            UNION ALL
            SELECT 'CIERRE_PERIODO', l.id_comprobante_nic41, c.fecha_creacion
            FROM modulo6.lineas_asiento_nic41 l JOIN modulo6.comprobantes_nic41 c USING (id_comprobante_nic41)
            WHERE l.tabla_origen = 'reconocimientos_iniciales' AND l.id_origen = :r
            ORDER BY 3""", {"r": reconocimiento.id_reconocimiento_inicial})

    def reconocimientos_del_activo(self, id_activo_biologico: int) -> list[dict]:
        return filas(self.db, f"""
            SELECT {_COLUMNAS_RECONOCIMIENTO}, costos_venta_estimados, justificacion_reversion, fecha_reversion,
                   fecha_creacion
            FROM modulo6.reconocimientos_iniciales WHERE id_activo_biologico = :a ORDER BY fecha_creacion""",
            {"a": id_activo_biologico})

    # --- RF-88 ---------------------------------------------------------------------------------

    def agregar_valoracion_costo(self, valoracion: ValoracionCosto) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.valoraciones_por_costos (id_activo_biologico, escenario_activacion, costos_adquisicion,
                tasa_depreciacion, fecha_adquisicion, depreciacion_acumulada, deterioro_acumulado, valor_contable_por_costo,
                razon_sin_mercado, id_usuario, fecha_marcacion, es_activa, justificacion, vida_util_meses)
            VALUES (:a, CAST(:esc AS modulo6.enum_valoraciones_por_costos_escenario), :c, :t, :f, :dep, :det, :v, :razon,
                :u, now(), true, :j, :vida)
            RETURNING id_valoracion_por_costo
        """, {"a": valoracion.id_activo_biologico, "esc": valoracion.escenario_activacion,
              "c": valoracion.costos_adquisicion, "t": valoracion.tasa_depreciacion, "f": valoracion.fecha_adquisicion,
              "dep": valoracion.depreciacion_acumulada, "det": valoracion.deterioro_acumulado,
              "v": valoracion.valor_contable_por_costo, "razon": valoracion.razon_sin_mercado,
              "u": valoracion.id_usuario, "j": valoracion.justificacion, "vida": valoracion.vida_util_meses},
            {"unique_valoraciones_por_costos_activo_biologico": "El activo ya tiene una valoración por costo."})

    def valoracion_costo_activa(self, id_activo_biologico: int) -> Optional[ValoracionCosto]:
        f = fila(self.db, """
            SELECT id_valoracion_por_costo, id_activo_biologico, escenario_activacion::text AS escenario_activacion,
                   costos_adquisicion, tasa_depreciacion, vida_util_meses, fecha_adquisicion, depreciacion_acumulada,
                   deterioro_acumulado, valor_contable_por_costo, razon_sin_mercado, id_usuario, es_activa, justificacion
            FROM modulo6.valoraciones_por_costos WHERE id_activo_biologico = :a AND es_activa""", {"a": id_activo_biologico})
        return ValoracionCosto(**f) if f else None

    def actualizar_valoracion_costo(self, valoracion: ValoracionCosto) -> None:
        escribir(self.db, """
            UPDATE modulo6.valoraciones_por_costos
            SET costos_adquisicion = :c, depreciacion_acumulada = :dep, deterioro_acumulado = :det,
                valor_contable_por_costo = :v, es_activa = :act
            WHERE id_valoracion_por_costo = :id""",
                 {"id": valoracion.id_valoracion_por_costo, "c": valoracion.costos_adquisicion,
                  "dep": valoracion.depreciacion_acumulada, "det": valoracion.deterioro_acumulado,
                  "v": valoracion.valor_contable_por_costo, "act": valoracion.es_activa})

    def agregar_deterioro(self, id_valoracion, id_evento_sanitario, monto, justificacion, id_usuario) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.deterioros_activos (id_valoracion_por_costo, id_evento_sanitario, impacto_economico_cop,
                justificacion, id_usuario, fecha_registro)
            VALUES (:v, :e, :m, :j, :u, now()) RETURNING id_deterioro_activo
        """, {"v": id_valoracion, "e": id_evento_sanitario, "m": monto, "j": justificacion, "u": id_usuario})

    # --- RF-85 ---------------------------------------------------------------------------------

    def agregar_producto(self, datos: dict) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.reconocimientos_productos_agricolas (id_evento_productivo, id_activo_biologico,
                producto_agricola, cantidad_cosechada, unidad_medida, precio_mercado_producto, costo_venta_producto,
                valor_producto, proporcion_cosechada, valor_reduccion_activo, id_calculo_valor_razonable,
                id_periodo_contable, justificacion, fecha_cosecha, fecha_registro, id_usuario, tipo, id_medicion_posterior)
            VALUES (:id_evento_productivo, :id_activo_biologico, :producto_agricola, :cantidad_cosechada, :unidad_medida,
                :precio_mercado_producto, :costo_venta_producto, :valor_producto, :proporcion_cosechada,
                :valor_reduccion_activo, :id_calculo_valor_razonable, :id_periodo_contable, :justificacion, :fecha_cosecha,
                now(), :id_usuario, CAST(:tipo AS modulo6.enum_reconocimientos_productos_agricolas_tipo_producto),
                :id_medicion_posterior)
            RETURNING id_reconocimiento_producto_agricola
        """, datos, {"uq_reconocimientos_productos_agricolas_evento_productivo":
                     "El evento productivo ya tiene un producto agrícola reconocido."})

    # --- Consulta ------------------------------------------------------------------------------

    def activos_valorados(self) -> list[dict]:
        """Activos reconocidos con su último valor razonable neto o su valor por costo."""
        return filas(self.db, f"""
        SELECT a.id_activo_biologico, a.identificador, a.tipo::text AS tipo, e.nombre AS especie, f.nombre AS finca,
               est.nombre AS estado, ri.clasificacion::text AS clasificacion, ri.fecha_reconocimiento,
               ri.indicador_valoracion::text AS indicador_reconocimiento, ri.es_apertura,
               (vc.id_valoracion_por_costo IS NOT NULL) AS valorado_por_costo, vc.valor_contable_por_costo,
               vc.costos_adquisicion AS costo_base, vc.depreciacion_acumulada, vc.deterioro_acumulado, vc.vida_util_meses,
               vc.razon_sin_mercado, vc.fecha_marcacion, vc.escenario_activacion::text AS escenario_costo,
               a.id_especie, i.id_finca, a.id_infraestructura, i.nombre AS infraestructura,
               ri.costo_adquisicion, ri.origen_financiero::text AS origen_financiero,
               ri.valor_razonable_neto_inicial AS valor_inicial,
               CASE WHEN c.consumido_por_cosecha THEN 0 ELSE c.valor_neto END AS valor_razonable_neto,
               c.fecha_calculo, c.tiene_valor_estimado, COALESCE(c.consumido_por_cosecha, false) AS cosechado_completamente
        FROM modulo6.reconocimientos_iniciales ri
        JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = ri.id_activo_biologico
        JOIN modulo9.especies e ON e.id_especie = a.id_especie
        JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
        JOIN modulo9.fincas f ON f.id_finca = i.id_finca
        JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = a.id_estado
        LEFT JOIN modulo6.valoraciones_por_costos vc ON vc.id_activo_biologico = a.id_activo_biologico AND vc.es_activa
        LEFT JOIN LATERAL (SELECT valor_neto, fecha_calculo, tiene_valor_estimado,
                                  {CONSUMIDO_POR_COSECHA.format(calculo="c.id_calculo_valor_razonable")} AS consumido_por_cosecha
                           FROM modulo6.calculos_valor_razonable c
                           WHERE c.id_activo_biologico = a.id_activo_biologico AND c.estado = 'CALCULADO'
                             AND COALESCE((c.json_metodo_costo->>'es_producto')::boolean, false) = false
                           ORDER BY c.fecha_calculo DESC, c.id_calculo_valor_razonable DESC LIMIT 1) c ON true
        WHERE ri.estado = 'CONFIRMADO' ORDER BY a.identificador""")


    def historial_activo(self, id_activo_biologico: int) -> dict:
        p = {"a": id_activo_biologico}
        return {
            "reconocimientos": self.reconocimientos_del_activo(id_activo_biologico),
            "calculos": filas(self.db, f"""SELECT {_COLUMNAS_CALCULO} FROM modulo6.calculos_valor_razonable
                                           WHERE id_activo_biologico = :a ORDER BY fecha_calculo DESC LIMIT 100""", p),
            "mediciones": filas(self.db, """
                SELECT id_medicion_posterior, id_evento, origen_medicion::text AS origen_medicion, valor_razonable_anterior,
                       valor_razonable_actual, ganancia_perdida_transformacion, ganancia_perdida_precio_mercado,
                       variacion_total, tiene_valor_estimado, fecha_medicion, id_periodo_contable, supuestos_aplicados
                FROM modulo6.mediciones_posteriores WHERE id_activo_biologico = :a ORDER BY fecha_medicion DESC LIMIT 100""", p),
            "productos": filas(self.db, """
                SELECT id_reconocimiento_producto_agricola, id_evento_productivo, producto_agricola, cantidad_cosechada,
                       unidad_medida, valor_producto, valor_reduccion_activo, tipo::text AS tipo, fecha_cosecha
                FROM modulo6.reconocimientos_productos_agricolas WHERE id_activo_biologico = :a ORDER BY fecha_cosecha DESC""", p),
            "valoracion_costo": fila(self.db, """
                SELECT id_valoracion_por_costo, escenario_activacion::text AS escenario_activacion, costos_adquisicion,
                       vida_util_meses, depreciacion_acumulada, deterioro_acumulado, valor_contable_por_costo,
                       razon_sin_mercado, es_activa, fecha_marcacion
                FROM modulo6.valoraciones_por_costos WHERE id_activo_biologico = :a""", p),
        }

    # --- Listados del período (vistas de medición, variaciones, cálculos y productos) ------------------

    def mediciones_del_periodo(self, id_periodo_contable: int, id_evento: Optional[int] = None,
                               tiene_valor_estimado: Optional[bool] = None) -> list[dict]:
        # Filtros en AND; uno omitido (NULL) no filtra.
        return filas(self.db, f"""
            SELECT x.id_medicion_posterior, x.id_activo_biologico, {_ACTIVO}, x.id_evento, x.id_periodo_contable,
                   x.origen_medicion::text AS origen_medicion,
                   x.valor_razonable_anterior, x.valor_razonable_actual, x.ganancia_perdida_transformacion,
                   x.ganancia_perdida_precio_mercado, x.variacion_total, x.tiene_valor_estimado, x.estado::text AS estado,
                   x.fecha_medicion
            FROM modulo6.mediciones_posteriores x {_JOIN_ACTIVO}
            WHERE x.id_periodo_contable = :p
              AND (CAST(:e AS integer) IS NULL OR x.id_evento = :e)
              AND (CAST(:est AS boolean) IS NULL OR x.tiene_valor_estimado = :est)
            ORDER BY x.fecha_medicion DESC, x.id_medicion_posterior DESC""",
            {"p": id_periodo_contable, "e": id_evento, "est": tiene_valor_estimado})

    def eventos_pendientes_del_periodo(self, id_periodo_contable: int) -> list[dict]:
        # El día del evento en la zona del usuario, igual que al procesarlo (fecha_usuario).
        return filas(self.db, f"""
            SELECT pr.id_evento, x.id_activo_biologico, {_ACTIVO}, x.fecha AS fecha_evento,
                   pr.detalle AS motivo, pr.fecha_procesamiento
            FROM modulo6.procesamientos_eventos_m02 pr
            JOIN modulo2.eventos_activos x ON x.id_eventos = pr.id_evento
            {_JOIN_ACTIVO}
            JOIN modulo6.periodos_contables p
              ON p.id_periodo_contable = :p AND p.numero_id_tributaria = f.numero_id_tributaria
            WHERE pr.resultado = 'MEDICION_PENDIENTE'
              AND (x.fecha AT TIME ZONE :tz)::date BETWEEN p.fecha_inicio AND p.fecha_fin
            ORDER BY x.fecha DESC, pr.id_evento DESC""",
            {"p": id_periodo_contable, "tz": nombre_zona_usuario()})

    def variaciones_del_periodo(self, id_periodo_contable: int) -> list[dict]:
        # La verificación de trazabilidad actualiza la línea; la variación guarda el estado con que nació.
        return filas(self.db, f"""
            SELECT x.id_variacion_valor_razonable, x.id_activo_biologico, {_ACTIVO}, x.tipo::text AS tipo,
                   x.monto_variacion, x.valor_razonable_anterior, x.valor_razonable_nuevo, x.tiene_estimacion,
                   x.fecha_registro, l.id_linea_asiento_nic41 AS id_linea, l.tipo_evidencia::text AS tipo_evidencia,
                   COALESCE(l.estado_trazabilidad, x.estado_trazabilidad)::text AS estado_trazabilidad,
                   x.id_variacion_corregida, (x.id_variacion_corregida IS NOT NULL) AS es_correctivo,
                   sc.id_solicitud_correctivo_variacion AS id_solicitud_correctivo, sc.estado AS estado_correctivo
            FROM modulo6.variaciones_valor_razonable x {_JOIN_ACTIVO}
            LEFT JOIN modulo6.solicitudes_correctivos_variaciones sc
                   ON sc.id_variacion_valor_razonable = x.id_variacion_valor_razonable AND sc.estado IN ('PENDIENTE', 'APROBADA')
            LEFT JOIN modulo6.lineas_asiento_nic41 l
                   ON l.tabla_origen = 'variaciones_valor_razonable' AND l.id_origen = x.id_variacion_valor_razonable
                  AND l.es_reverso = (x.id_variacion_corregida IS NOT NULL)  -- la del correctivo es la inversa
            WHERE x.id_periodo_contable = :p ORDER BY x.fecha_registro DESC, x.id_variacion_valor_razonable DESC""",
            {"p": id_periodo_contable})

    def calculos_del_periodo(self, id_periodo_contable: int) -> list[dict]:
        return filas(self.db, f"""
            SELECT x.id_calculo_valor_razonable, x.id_activo_biologico, {_ACTIVO}, x.magnitud, x.unidad_magnitud,
                   x.precio_unitario, x.valor_razonable_bruto,
                   x.costo_transporte + x.costo_comisiones + x.costo_impuestos_transaccion + x.otros_costos_disposicion
                       AS costos_venta,
                   x.valor_neto, x.metodo_costo::text AS metodo_costo, x.estado::text AS estado, x.tiene_valor_estimado,
                   COALESCE((x.json_metodo_costo->>'es_producto')::boolean, false) AS es_producto, x.fecha_calculo
            FROM modulo6.calculos_valor_razonable x {_JOIN_ACTIVO}
            WHERE x.id_periodo_contable = :p ORDER BY x.fecha_calculo DESC, x.id_calculo_valor_razonable DESC""",
            {"p": id_periodo_contable})

    def productos_agricolas(self, filtros: dict) -> list[dict]:
        """RF-85 RNF-85-05: historial de productos reconocidos; los filtros se combinan con AND y uno omitido no filtra."""
        condiciones, params = [], {}
        for campo, sql in _FILTROS_PRODUCTOS:
            if filtros.get(campo) not in (None, ""):
                condiciones.append(sql)
                params[campo] = filtros[campo]
        return filas(self.db, f"""
            SELECT x.id_reconocimiento_producto_agricola, x.id_evento_productivo, x.id_activo_biologico, {_ACTIVO},
                   x.producto_agricola, x.cantidad_cosechada, x.unidad_medida, x.precio_mercado_producto,
                   x.costo_venta_producto, x.valor_producto, x.valor_reduccion_activo, x.tipo::text AS tipo,
                   x.fecha_cosecha, x.id_periodo_contable, x.id_usuario,
                   NULLIF(trim(coalesce(u.nombre, '') || ' ' || coalesce(u.apellidos, '')), '') AS nombre_usuario
            FROM modulo6.reconocimientos_productos_agricolas x {_JOIN_ACTIVO}
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = x.id_usuario
            WHERE {" AND ".join(condiciones) or "true"}
            ORDER BY x.fecha_cosecha DESC, x.id_reconocimiento_producto_agricola DESC LIMIT 500""", params)
