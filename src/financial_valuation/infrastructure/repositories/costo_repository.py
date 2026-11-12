# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-90 v2.0 / RF-79: costos del activo y bandeja de provisiones de M05 |
# | 2026-11-05 | Arekkazu | M06 RF-90: filtro por tipo de costo, especie y finca del activo; mensaje sin códigos |
# | 2026-11-11 | Arekkazu | USAB-M05-M06 T-01 RF-75..94: el activo sin identificador se nombra «Lote N», nunca null |
"""Implementación SQL de :class:`CostoRepository`."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.recepcion_provision import RecepcionProvision
from src.financial_valuation.domain.repositories.costo_repository import CostoRepository
from src.financial_valuation.infrastructure.repositories.sql import escribir, fila, filas
from src.shared.nombre_activo import nombre_activo_sql

_COLUMNAS = f"""c.id_registro_costo, c.naturaleza_costo::text AS naturaleza_costo, c.subtipo_costo::text AS subtipo_costo,
    c.origen_costo::text AS origen_costo, c.vehiculo_contable::text AS vehiculo_contable, c.id_activo_biologico,
    {nombre_activo_sql()} AS activo, c.monto_costo, c.fecha_costo, c.id_periodo_contable, c.estado::text AS estado,
    c.politica_capitalizacion::text AS politica_capitalizacion, c.justificacion, c.id_origen_m05, c.tercero_nit,
    c.tercero_dv, c.tercero_razon_social, c.factura_prefijo, c.factura_numero, c.fecha_factura,
    c.fecha_vencimiento_factura, c.id_grupo_reparto, c.metodo_reparto::text AS metodo_reparto, c.cuenta_debito,
    c.cuenta_credito, c.es_cuenta_manual, c.es_reverso, c.id_usuario, c.fecha_registro, a.id_especie,
    a.id_infraestructura, i.id_finca, e.nombre AS especie, f.nombre AS finca"""
_JOIN = """FROM modulo6.registros_costos c
    JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = c.id_activo_biologico
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
    JOIN modulo9.especies e ON e.id_especie = a.id_especie
    JOIN modulo9.fincas f ON f.id_finca = i.id_finca"""


def _filtros_sql(filtros: dict) -> tuple[str, dict]:
    condiciones, params = [], {}
    for campo, sql in (("id_activo_biologico", "c.id_activo_biologico = :id_activo_biologico"),
                       ("id_periodo_contable", "c.id_periodo_contable = :id_periodo_contable"),
                       ("estado", "c.estado::text = :estado"), ("naturaleza_costo", "c.naturaleza_costo::text = :naturaleza_costo"),
                       ("subtipo_costo", "c.subtipo_costo::text = :subtipo_costo"),
                       ("origen_costo", "c.origen_costo::text = :origen_costo"), ("id_especie", "a.id_especie = :id_especie"),
                       ("id_infraestructura", "a.id_infraestructura = :id_infraestructura"),
                       ("id_finca", "i.id_finca = :id_finca")):
        if filtros.get(campo) not in (None, ""):
            condiciones.append(sql)
            params[campo] = filtros[campo]
    return (" AND ".join(condiciones) or "true"), params


class SqlAlchemyCostoRepository(CostoRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def agregar(self, datos: dict) -> int:
        campos = {"naturaleza_costo": None, "subtipo_costo": None, "politica_capitalizacion": None,
                  "estado": "REGISTRADO", "justificacion": None, "id_origen_m05": None, "tercero_nit": None,
                  "tercero_dv": None, "tercero_razon_social": None, "factura_prefijo": None, "factura_numero": None,
                  "fecha_factura": None, "fecha_vencimiento_factura": None, "id_grupo_reparto": None,
                  "metodo_reparto": None, "cuenta_debito": None, "cuenta_credito": None, "es_cuenta_manual": False,
                  "es_reverso": False, "id_registro_costo_compensado": None, **datos}
        return escribir(self.db, """
            INSERT INTO modulo6.registros_costos (naturaleza_costo, subtipo_costo, id_activo_biologico, monto_costo,
                exportable_aaef, politica_capitalizacion, estado, justificacion, id_periodo_contable, id_usuario,
                fecha_registro, origen_costo, vehiculo_contable, fecha_costo, id_origen_m05, tercero_nit, tercero_dv,
                tercero_razon_social, factura_prefijo, factura_numero, fecha_factura, fecha_vencimiento_factura,
                id_grupo_reparto, metodo_reparto, cuenta_debito, cuenta_credito, es_cuenta_manual, es_reverso,
                id_registro_costo_compensado)
            VALUES (CAST(:naturaleza_costo AS modulo6.enum_registros_costos_naturaleza_costo),
                CAST(:subtipo_costo AS modulo6.enum_registros_costos_subtipo_costo), :id_activo_biologico, :monto_costo,
                false, CAST(:politica_capitalizacion AS modulo6.enum_registros_costos_politica_capitalizacion),
                CAST(:estado AS modulo6.enum_registros_costos_estado_costo), :justificacion, :id_periodo_contable,
                :id_usuario, now(), CAST(:origen_costo AS modulo6.enum_registro_costo_origen_costo),
                CAST(:vehiculo_contable AS modulo6.enum_registro_costo_vehiculo_contable), :fecha_costo, :id_origen_m05,
                :tercero_nit, :tercero_dv, :tercero_razon_social, :factura_prefijo, :factura_numero, :fecha_factura,
                :fecha_vencimiento_factura, :id_grupo_reparto,
                CAST(:metodo_reparto AS modulo6.enum_registro_costo_metodo_reparto), :cuenta_debito, :cuenta_credito,
                :es_cuenta_manual, :es_reverso, :id_registro_costo_compensado)
            RETURNING id_registro_costo
        """, campos, {"uq_registro_costo_id_origen_m05": "El consumo de Suministros ya fue registrado como costo.",
                      "uq_registro_costo_factura_id_activo_biologico": "La factura ya está registrada para este activo."})

    def obtener(self, id_registro_costo: int) -> Optional[dict]:
        return fila(self.db, f"SELECT {_COLUMNAS} {_JOIN} WHERE c.id_registro_costo = :id", {"id": id_registro_costo})

    def clasificar(self, id_registro_costo, naturaleza, politica, vehiculo, cuenta_debito, cuenta_credito, justificacion) -> None:
        escribir(self.db, """
            UPDATE modulo6.registros_costos
            SET naturaleza_costo = CAST(:n AS modulo6.enum_registros_costos_naturaleza_costo),
                politica_capitalizacion = CAST(:p AS modulo6.enum_registros_costos_politica_capitalizacion),
                vehiculo_contable = CAST(:v AS modulo6.enum_registro_costo_vehiculo_contable),
                cuenta_debito = :d, cuenta_credito = :c, estado = 'REGISTRADO',
                justificacion = concat_ws(' | ', justificacion, :j)
            WHERE id_registro_costo = :id AND estado = 'PENDIENTE_CLASIFICACION'
        """, {"id": id_registro_costo, "n": naturaleza, "p": politica, "v": vehiculo, "d": cuenta_debito,
              "c": cuenta_credito, "j": justificacion})

    def factura_registrada(self, tercero_nit, factura_prefijo, factura_numero) -> Optional[dict]:
        return fila(self.db, """SELECT id_registro_costo, id_grupo_reparto FROM modulo6.registros_costos
                                WHERE tercero_nit = :n AND factura_prefijo IS NOT DISTINCT FROM :p AND factura_numero = :f
                                LIMIT 1""", {"n": tercero_nit, "p": factura_prefijo, "f": factura_numero})

    def listar(self, filtros: dict) -> list[dict]:
        donde, params = _filtros_sql(filtros)
        return filas(self.db, f"SELECT {_COLUMNAS} {_JOIN} WHERE {donde} ORDER BY c.fecha_costo DESC, c.id_registro_costo DESC LIMIT 500",
                     params)

    def del_periodo(self, id_periodo_contable: int, filtros: Optional[dict] = None) -> list[dict]:
        donde, params = _filtros_sql({**(filtros or {}), "id_periodo_contable": id_periodo_contable})
        return filas(self.db, f"SELECT {_COLUMNAS} {_JOIN} WHERE {donde} AND c.estado = 'REGISTRADO'", params)

    def pendientes_clasificacion(self, id_periodo_contable: int) -> list[dict]:
        return filas(self.db, f"SELECT {_COLUMNAS} {_JOIN} WHERE c.id_periodo_contable = :p AND c.estado = 'PENDIENTE_CLASIFICACION'",
                     {"p": id_periodo_contable})

    def recepciones_pendientes(self, limite: int) -> list[tuple[int, RecepcionProvision]]:
        """Solo las de activos ya reconocidos: RF-90 exige reconocimiento previo (las demás esperan)."""
        resultado = []
        for f in filas(self.db, """
            SELECT r.id_recepcion_provision_m05, r.id_evento_provision, r.modalidad, r.schema_version, r.id_activo_biologico,
                   r.id_gestion_fases, r.json_contenido, r.fecha_recepcion
            FROM modulo6.recepciones_provisiones_m05 r
            WHERE r.fecha_procesamiento IS NULL
              AND (r.modalidad = 'CONSOLIDADO' OR EXISTS (
                  SELECT 1 FROM modulo6.reconocimientos_iniciales ri
                  WHERE ri.id_activo_biologico = r.id_activo_biologico AND ri.estado = 'CONFIRMADO'))
            ORDER BY r.fecha_recepcion, r.id_recepcion_provision_m05 LIMIT :l""", {"l": limite}):
            resultado.append((f["id_recepcion_provision_m05"], RecepcionProvision(
                id_evento_provision=f["id_evento_provision"], modalidad=f["modalidad"], schema_version=f["schema_version"],
                id_activo_biologico=f["id_activo_biologico"], contenido=f["json_contenido"],
                id_gestion_fases=f["id_gestion_fases"], fecha_recepcion=f["fecha_recepcion"])))
        return resultado

    def marcar_recepcion(self, id_recepcion: int, resultado: str) -> None:
        escribir(self.db, """UPDATE modulo6.recepciones_provisiones_m05
                             SET fecha_procesamiento = now(), resultado_procesamiento = :r
                             WHERE id_recepcion_provision_m05 = :id""", {"id": id_recepcion, "r": resultado[:40]})

    def recepciones_pendientes_titular(self, numero_id_tributaria: str, hasta: date) -> int:
        f = fila(self.db, """
            SELECT count(*) AS n FROM modulo6.recepciones_provisiones_m05 r
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = r.id_activo_biologico
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
            JOIN modulo9.fincas f ON f.id_finca = i.id_finca
            JOIN modulo6.reconocimientos_iniciales ri ON ri.id_activo_biologico = a.id_activo_biologico AND ri.estado = 'CONFIRMADO'
            WHERE r.fecha_procesamiento IS NULL AND r.modalidad = 'INCREMENTAL' AND f.numero_id_tributaria = :n
              AND r.fecha_recepcion::date <= :h""", {"n": numero_id_tributaria, "h": hasta})
        return f["n"] if f else 0

    def fecha_aplicacion_m05(self, id_registro_suministro: str) -> Optional[date]:
        f = fila(self.db, "SELECT fecha_aplicacion FROM modulo5.registro_suministro WHERE id_registro_suministro = CAST(:id AS uuid)",
                 {"id": id_registro_suministro})
        return f["fecha_aplicacion"] if f else None
