# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-86 v2.0: persistencia de las líneas de asiento NIC 41 |
# | 2026-11-10 | Arekkazu | INC-M06-351-G45 RF-87: lectura de una línea y de sus ajustes posteriores |
# | 2026-11-12 | Arekkazu | TC-DIS-256 RF-91: cada línea trae el nombre y el tipo de su activo |
"""Implementación SQL de :class:`AsientoRepository`. Las líneas son inmutables salvo las
transiciones que permite ``fn_proteger_linea_asiento_nic41`` (cuentas pendientes, trazabilidad,
comprobante y traslado de período por exclusión autorizada)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import LineaAsiento
from src.financial_valuation.domain.repositories.asiento_repository import AsientoRepository
from src.financial_valuation.infrastructure.repositories.sql import escribir, fila, filas
from src.shared.nombre_activo import nombre_activo_sql

_COLUMNAS = """id_linea_asiento_nic41, tipo_hecho::text AS tipo_hecho, sentido::text AS sentido, estado::text AS estado,
    valor, fecha_hecho, id_periodo_contable, id_activo_biologico, id_especie, id_finca, numero_id_tributaria,
    tabla_origen, id_origen, tipo_evidencia, subtipo_costo::text AS subtipo_costo, es_estimacion, es_reverso,
    tipo_hecho_corregido::text AS tipo_hecho_corregido, id_linea_corregida, cuenta_debito, cuenta_credito,
    justificacion, id_usuario"""


def _linea(f: dict) -> LineaAsiento:
    return LineaAsiento(**{**f, "valor": Decimal(f["valor"])})


class SqlAlchemyAsientoRepository(AsientoRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def agregar(self, linea: LineaAsiento) -> LineaAsiento:
        linea.id_linea_asiento_nic41 = escribir(self.db, """
            INSERT INTO modulo6.lineas_asiento_nic41 (
                tipo_hecho, sentido, estado, tipo_evidencia, fecha_hecho, id_periodo_contable, id_activo_biologico,
                id_especie, id_finca, numero_id_tributaria, subtipo_costo, cuenta_debito, cuenta_credito, valor,
                tabla_origen, id_origen, es_estimacion, es_reverso, tipo_hecho_corregido, id_linea_corregida,
                justificacion, id_usuario)
            VALUES (
                CAST(:tipo_hecho AS modulo6.enum_linea_asiento_nic41_tipo_hecho),
                CAST(:sentido AS modulo6.enum_linea_asiento_nic41_sentido),
                CAST(:estado AS modulo6.enum_linea_asiento_nic41_estado), :tipo_evidencia, :fecha_hecho,
                :id_periodo_contable, :id_activo_biologico, :id_especie, :id_finca, :numero_id_tributaria,
                CAST(:subtipo_costo AS modulo6.enum_registros_costos_subtipo_costo), :cuenta_debito, :cuenta_credito,
                :valor, :tabla_origen, :id_origen, :es_estimacion, :es_reverso,
                CAST(:tipo_hecho_corregido AS modulo6.enum_linea_asiento_nic41_tipo_hecho), :id_linea_corregida,
                :justificacion, :id_usuario)
            RETURNING id_linea_asiento_nic41
        """, {k: getattr(linea, k) for k in (
            "tipo_hecho", "sentido", "estado", "tipo_evidencia", "fecha_hecho", "id_periodo_contable",
            "id_activo_biologico", "id_especie", "id_finca", "numero_id_tributaria", "subtipo_costo", "cuenta_debito",
            "cuenta_credito", "valor", "tabla_origen", "id_origen", "es_estimacion", "es_reverso",
            "tipo_hecho_corregido", "id_linea_corregida", "justificacion", "id_usuario")})
        return linea

    def obtener(self, id_linea: int) -> Optional[LineaAsiento]:
        f = fila(self.db, f"SELECT {_COLUMNAS} FROM modulo6.lineas_asiento_nic41 WHERE id_linea_asiento_nic41 = :id",
                 {"id": id_linea})
        return _linea(f) if f else None

    def ajustes_de(self, id_linea: int) -> list[LineaAsiento]:
        return [_linea(f) for f in filas(self.db, f"""SELECT {_COLUMNAS} FROM modulo6.lineas_asiento_nic41
            WHERE id_linea_corregida = :id ORDER BY 1""", {"id": id_linea})]

    def lineas_de_origen(self, tabla_origen: str, id_origen: int) -> list[LineaAsiento]:
        return [_linea(f) for f in filas(self.db, f"""SELECT {_COLUMNAS} FROM modulo6.lineas_asiento_nic41
            WHERE tabla_origen = :t AND id_origen = :i AND id_linea_corregida IS NULL ORDER BY 1""",
            {"t": tabla_origen, "i": id_origen})]

    def pendientes_de_cuenta(self, id_periodo_contable: Optional[int] = None) -> list[LineaAsiento]:
        return [_linea(f) for f in filas(self.db, f"""
            SELECT {_COLUMNAS} FROM modulo6.lineas_asiento_nic41 l
            WHERE l.estado = 'PENDIENTE_CUENTA'
              AND (CAST(:p AS integer) IS NULL OR l.id_periodo_contable = :p)
              AND EXISTS (SELECT 1 FROM modulo6.periodos_contables pc
                          WHERE pc.id_periodo_contable = l.id_periodo_contable AND pc.estado = 'ABIERTO')
            ORDER BY 1""", {"p": id_periodo_contable})]

    def registrar_cuentas(self, id_linea: int, cuenta_debito: str, cuenta_credito: str) -> None:
        escribir(self.db, """UPDATE modulo6.lineas_asiento_nic41
                             SET cuenta_debito = :d, cuenta_credito = :c, estado = 'REGISTRADA'
                             WHERE id_linea_asiento_nic41 = :id AND estado = 'PENDIENTE_CUENTA'""",
                 {"id": id_linea, "d": cuenta_debito, "c": cuenta_credito})

    def del_periodo(self, id_periodo_contable: int) -> list[LineaAsiento]:
        resultado = []
        # TC-DIS-256: la línea trae el nombre y el tipo de su activo; quien solo lee la trazabilidad (el auditor)
        # no tiene acceso a la lista de activos valorados para buscarlos.
        for f in filas(self.db, f"""SELECT {_COLUMNAS}, estado_trazabilidad::text AS estado_trazabilidad,
                                           id_comprobante_nic41,
                                           (SELECT {nombre_activo_sql('ab')} FROM modulo2.activos_biologicos ab
                                             WHERE ab.id_activo_biologico = l.id_activo_biologico) AS identificador_activo,
                                           (SELECT ab.tipo::text FROM modulo2.activos_biologicos ab
                                             WHERE ab.id_activo_biologico = l.id_activo_biologico) AS tipo_activo
                                    FROM modulo6.lineas_asiento_nic41 l WHERE id_periodo_contable = :p ORDER BY 1""",
                       {"p": id_periodo_contable}):
            extra = {k: f.pop(k) for k in ("estado_trazabilidad", "id_comprobante_nic41", "identificador_activo", "tipo_activo")}
            linea = _linea(f)
            linea.extra = extra
            resultado.append(linea)
        return resultado

    def cambiar_trazabilidad(self, id_linea: int, estado: str) -> None:
        escribir(self.db, """UPDATE modulo6.lineas_asiento_nic41 SET estado_trazabilidad =
                                 CAST(:e AS modulo6.enum_variaciones_valor_razonable_estado_trazabilidad)
                             WHERE id_linea_asiento_nic41 = :id""", {"id": id_linea, "e": estado})

    def mover_a_periodo(self, ids_lineas: list[int], id_periodo_contable: int) -> None:
        if ids_lineas:
            escribir(self.db, """UPDATE modulo6.lineas_asiento_nic41 SET id_periodo_contable = :p
                                 WHERE id_linea_asiento_nic41 = ANY(:ids)""", {"p": id_periodo_contable, "ids": ids_lineas})

    def asignar_comprobante(self, ids_lineas: list[int], id_comprobante: int) -> None:
        escribir(self.db, """UPDATE modulo6.lineas_asiento_nic41 SET id_comprobante_nic41 = :c
                             WHERE id_linea_asiento_nic41 = ANY(:ids)""", {"c": id_comprobante, "ids": ids_lineas})

    def del_activo(self, id_activo_biologico: int) -> list[LineaAsiento]:
        return [_linea(f) for f in filas(self.db, f"""SELECT {_COLUMNAS} FROM modulo6.lineas_asiento_nic41
            WHERE id_activo_biologico = :a ORDER BY 1""", {"a": id_activo_biologico})]
