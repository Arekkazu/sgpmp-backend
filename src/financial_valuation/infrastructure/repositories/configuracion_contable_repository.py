# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-84/88/109: configuración contable, costos de venta y matriz |
# | 2026-11-12 | Arekkazu | M06 RF-82: 403 si la RLS oculta la configuración contable (antes 500) |
"""Implementación SQL de :class:`ConfiguracionContableRepository`."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import (
    AsignacionCuenta,
    ConfiguracionContable,
    ParametroCostosVenta,
    ParametroEspecie,
)
from src.financial_valuation.domain.repositories.configuracion_contable_repository import (
    ConfiguracionContableRepository,
)
from src.financial_valuation.domain.value_objects.nic41 import REGION_GENERAL
from src.financial_valuation.infrastructure.repositories.sql import escribir, fila, filas
from src.shared.errors import AuthorizationError



class SqlAlchemyConfiguracionContableRepository(ConfiguracionContableRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener(self) -> ConfiguracionContable:
        f = fila(self.db, """SELECT tipo_cierre::text AS tipo_cierre, pct_umbral_desviacion_precio,
                                    dias_alerta_vencimiento_precio, fecha_inicio_operacion, fecha_actualizacion
                             FROM modulo6.configuraciones_contables WHERE id_configuracion_contable = 1""")
        if f is None:
            # La fila 1 la siembra la migración; si no llega es la RLS: el rol no lee configuracion_contable.
            raise AuthorizationError(code="SIN_PERMISO_CONFIGURACION_CONTABLE", message=(
                "Tu rol no tiene permiso para consultar la configuración contable, que esta operación necesita. "
                "Pide a un administrador que te lo asigne."))
        return ConfiguracionContable(**f)

    def actualizar(self, tipo_cierre: str, pct_umbral: Decimal, dias_alerta: int, id_usuario: int) -> ConfiguracionContable:
        escribir(self.db, """UPDATE modulo6.configuraciones_contables
                             SET tipo_cierre = :t, pct_umbral_desviacion_precio = :u, dias_alerta_vencimiento_precio = :d,
                                 id_usuario = :usr, fecha_actualizacion = now()
                             WHERE id_configuracion_contable = 1""",
                 {"t": tipo_cierre, "u": pct_umbral, "d": dias_alerta, "usr": id_usuario})
        return self.obtener()

    def parametro_especie(self, id_especie: int) -> Optional[ParametroEspecie]:
        f = fila(self.db, """SELECT id_especie, clasificacion::text AS clasificacion, categoria_precio::text AS categoria_precio,
                                    vida_util_meses
                             FROM modulo6.parametros_contables_especies WHERE id_especie = :e""", {"e": id_especie})
        return ParametroEspecie(**f) if f else None

    def listar_parametros_especie(self) -> list[dict]:
        return filas(self.db, """
            SELECT e.id_especie, e.nombre AS especie, p.clasificacion::text AS clasificacion,
                   p.categoria_precio::text AS categoria_precio, p.vida_util_meses, p.fecha_actualizacion
            FROM modulo9.especies e
            LEFT JOIN modulo6.parametros_contables_especies p ON p.id_especie = e.id_especie
            WHERE e.es_activo ORDER BY e.nombre""")

    def guardar_parametro_especie(self, parametro: ParametroEspecie, id_usuario: int) -> None:
        escribir(self.db, """
            INSERT INTO modulo6.parametros_contables_especies (id_especie, clasificacion, categoria_precio, vida_util_meses, id_usuario)
            VALUES (:e, :c, :cat, :v, :u)
            ON CONFLICT (id_especie) DO UPDATE SET clasificacion = EXCLUDED.clasificacion,
                categoria_precio = EXCLUDED.categoria_precio, vida_util_meses = EXCLUDED.vida_util_meses,
                id_usuario = EXCLUDED.id_usuario, fecha_actualizacion = now()
        """, {"e": parametro.id_especie, "c": parametro.clasificacion, "cat": parametro.categoria_precio,
              "v": parametro.vida_util_meses, "u": id_usuario})

    def costos_venta_vigentes(self, id_especie: int) -> Optional[ParametroCostosVenta]:
        f = fila(self.db, """SELECT id_parametro_costo_venta, id_especie, region, pct_transporte, pct_comisiones, pct_impuestos
                             FROM modulo6.parametros_costos_venta
                             WHERE id_especie = :e AND region = :r AND es_activo""",
                 {"e": id_especie, "r": REGION_GENERAL})
        return ParametroCostosVenta(**f) if f else None

    def listar_costos_venta(self) -> list[dict]:
        return filas(self.db, """
            SELECT p.id_parametro_costo_venta, p.id_especie, e.nombre AS especie, p.region, p.pct_transporte,
                   p.pct_comisiones, p.pct_impuestos, p.es_activo, p.fecha_creacion
            FROM modulo6.parametros_costos_venta p JOIN modulo9.especies e ON e.id_especie = p.id_especie
            ORDER BY e.nombre, p.fecha_creacion DESC""")

    def guardar_costos_venta(self, id_especie, region, pct_transporte, pct_comisiones, pct_impuestos, id_usuario) -> int:
        escribir(self.db, """UPDATE modulo6.parametros_costos_venta SET es_activo = false
                             WHERE id_especie = :e AND region = :r AND es_activo""", {"e": id_especie, "r": region})
        return escribir(self.db, """
            INSERT INTO modulo6.parametros_costos_venta (id_especie, region, pct_transporte, pct_comisiones, pct_impuestos,
                                                         es_activo, id_usuario)
            VALUES (:e, :r, :t, :c, :i, true, :u) RETURNING id_parametro_costo_venta
        """, {"e": id_especie, "r": region, "t": pct_transporte, "c": pct_comisiones, "i": pct_impuestos, "u": id_usuario})

    def resolver_cuenta(self, tipo_hecho, sentido, id_especie, subtipo_costo) -> Optional[AsignacionCuenta]:
        f = fila(self.db, """
            SELECT id_asignacion_cuenta_contable, tipo_hecho::text AS tipo_hecho, sentido::text AS sentido, id_especie,
                   subtipo_costo::text AS subtipo_costo, cuenta_debito, cuenta_credito
            FROM modulo6.asignaciones_cuentas_contables
            WHERE es_activo AND tipo_hecho::text = :t AND sentido::text = :s
              AND (id_especie = :e OR id_especie IS NULL)
              AND (subtipo_costo::text = :st OR subtipo_costo IS NULL)
            ORDER BY id_especie NULLS LAST, subtipo_costo NULLS LAST
            LIMIT 1""", {"t": tipo_hecho, "s": sentido, "e": id_especie, "st": subtipo_costo})
        return AsignacionCuenta(**f) if f else None

    def listar_asignaciones(self) -> list[AsignacionCuenta]:
        return [AsignacionCuenta(**f) for f in filas(self.db, """
            SELECT id_asignacion_cuenta_contable, tipo_hecho::text AS tipo_hecho, sentido::text AS sentido, id_especie,
                   subtipo_costo::text AS subtipo_costo, cuenta_debito, cuenta_credito
            FROM modulo6.asignaciones_cuentas_contables WHERE es_activo
            ORDER BY tipo_hecho, sentido, id_especie NULLS FIRST, subtipo_costo NULLS FIRST""")]

    def guardar_asignacion(self, tipo_hecho, sentido, id_especie, subtipo_costo, cuenta_debito, cuenta_credito, id_usuario) -> int:
        escribir(self.db, """
            UPDATE modulo6.asignaciones_cuentas_contables SET es_activo = false
            WHERE es_activo AND tipo_hecho::text = :t AND sentido::text = :s
              AND id_especie IS NOT DISTINCT FROM :e AND subtipo_costo::text IS NOT DISTINCT FROM :st
        """, {"t": tipo_hecho, "s": sentido, "e": id_especie, "st": subtipo_costo})
        return escribir(self.db, """
            INSERT INTO modulo6.asignaciones_cuentas_contables
                (tipo_hecho, sentido, id_especie, subtipo_costo, cuenta_debito, cuenta_credito, id_usuario)
            VALUES (CAST(:t AS modulo6.enum_linea_asiento_nic41_tipo_hecho), CAST(:s AS modulo6.enum_linea_asiento_nic41_sentido),
                    :e, CAST(:st AS modulo6.enum_registros_costos_subtipo_costo), :d, :c, :u)
            RETURNING id_asignacion_cuenta_contable
        """, {"t": tipo_hecho, "s": sentido, "e": id_especie, "st": subtipo_costo, "d": cuenta_debito,
              "c": cuenta_credito, "u": id_usuario})

    def desactivar_asignacion(self, id_asignacion: int) -> bool:
        return bool(escribir(self.db, """UPDATE modulo6.asignaciones_cuentas_contables SET es_activo = false
                                         WHERE id_asignacion_cuenta_contable = :id AND es_activo""", {"id": id_asignacion}))
