# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82/83/87: lectura del activo en M02 con su finca y titular |
# | 2026-11-05 | Arekkazu | M06 RF-88: eventos sanitarios del activo para elegir el del deterioro |
# | 2026-11-09 | destroyerban | INC-M06-326-G30 RF-85: la magnitud del activo descuenta lo cosechado desde el último pesaje |
# | 2026-11-10 | Arekkazu | INC-M06-350-G44 RF-87: fincas del período que perdieron el titular |
"""Adaptador de :class:`ActivoFinancieroPort` sobre ``modulo2`` y ``modulo9``.

Corre con la identidad del request: el RLS de ``modulo2`` limita los activos a las fincas del
usuario. El peso es el último PESAJE de RF-40 (INDIVIDUAL: ``valor_medicion``; POBLACIONAL:
``nuevo_peso_promedio``, o el peso promedio del detalle si no hay pesaje), en kilogramos. Los kg cosechados
como producto de consumo después de ese pesaje se descuentan de la magnitud (RF-85: la reducción es acumulativa)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.activo_financiero import ESTADOS_VALORABLES, DatosActivo
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.infrastructure.repositories.sql import fila, filas
from src.shared.fechas import nombre_zona_usuario

_BASE = """
SELECT a.id_activo_biologico, a.identificador, a.tipo::text AS tipo, a.id_especie, e.nombre AS especie,
       est.nombre AS estado, a.id_infraestructura, i.id_finca, f.nombre AS finca, f.numero_id_tributaria,
       f.razon_social, (a.fecha_creacion AT TIME ZONE :tz)::date AS fecha_ingreso,
       a.origen_financiero::text AS origen_financiero, a.costo_adquisicion, a.soporte_documental,
       d.cantidad_actual, COALESCE(p.peso, d.peso_promedio) AS peso_kg, p.id_evento AS id_evento_peso,
       a.id_dispositivo_iot, k.kg_cosechados
FROM modulo2.activos_biologicos a
JOIN modulo9.especies e ON e.id_especie = a.id_especie
JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = a.id_estado
JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
JOIN modulo9.fincas f ON f.id_finca = i.id_finca
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d ON d.id_activo_biologico = a.id_activo_biologico
LEFT JOIN LATERAL (
    SELECT CASE WHEN a.tipo = 'POBLACIONAL' THEN ec.nuevo_peso_promedio ELSE ec.valor_medicion END AS peso,
           ec.id_evento, ea.fecha
    FROM modulo2.eventos_crecimeinto ec
    JOIN modulo2.eventos_activos ea ON ea.id_eventos = ec.id_evento
    WHERE ea.id_activo_biologico = a.id_activo_biologico
      AND upper(ec.tipo_medicion) IN ('PESO', 'PESO_VIVO', 'PESAJE')
      AND (CASE WHEN a.tipo = 'POBLACIONAL' THEN ec.nuevo_peso_promedio ELSE ec.valor_medicion END) > 0
    ORDER BY ea.fecha DESC, ea.id_eventos DESC
    LIMIT 1
) p ON true
LEFT JOIN LATERAL (
    SELECT COALESCE(sum(rp.cantidad_cosechada), 0) AS kg_cosechados
    FROM modulo6.reconocimientos_productos_agricolas rp
    JOIN modulo2.eventos_activos ev ON ev.id_eventos = rp.id_evento_productivo
    WHERE rp.id_activo_biologico = a.id_activo_biologico AND rp.tipo = 'PRODUCTO_DE_CONSUMO'
      AND (p.id_evento IS NULL OR ev.fecha > p.fecha OR (ev.fecha = p.fecha AND ev.id_eventos > p.id_evento))
) k ON true
"""

_CONFIRMADO = """EXISTS (SELECT 1 FROM modulo6.reconocimientos_iniciales r
                         WHERE r.id_activo_biologico = a.id_activo_biologico AND r.estado = 'CONFIRMADO')"""


def _activo(f: dict) -> DatosActivo:
    return DatosActivo(
        id_activo_biologico=f["id_activo_biologico"], identificador=f["identificador"], tipo=f["tipo"],
        id_especie=f["id_especie"], especie=f["especie"], estado=f["estado"],
        id_infraestructura=f["id_infraestructura"], id_finca=f["id_finca"], finca=f["finca"],
        numero_id_tributaria=f["numero_id_tributaria"], razon_social=f["razon_social"],
        fecha_ingreso=f["fecha_ingreso"], origen_financiero=f["origen_financiero"],
        costo_adquisicion=Decimal(f["costo_adquisicion"]) if f["costo_adquisicion"] is not None else None,
        soporte_documental=f["soporte_documental"], cantidad_actual=f["cantidad_actual"],
        peso_kg=Decimal(f["peso_kg"]) if f["peso_kg"] is not None else None, id_evento_peso=f["id_evento_peso"],
        id_dispositivo_iot=f["id_dispositivo_iot"], kg_cosechados=Decimal(f["kg_cosechados"] or 0),
    )


class ActivoFinancieroM02Adapter(ActivoFinancieroPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener(self, id_activo_biologico: int) -> Optional[DatosActivo]:
        f = fila(self.db, _BASE + " WHERE a.id_activo_biologico = :id",
                 {"id": id_activo_biologico, "tz": nombre_zona_usuario()})
        return _activo(f) if f else None

    def listar_sin_reconocimiento(self) -> list[DatosActivo]:
        return [_activo(f) for f in filas(
            self.db, _BASE + f" WHERE NOT {_CONFIRMADO} AND est.nombre = ANY(:estados) ORDER BY a.id_activo_biologico",
            {"tz": nombre_zona_usuario(), "estados": list(ESTADOS_VALORABLES)},
        )]

    def listar_reconocidos(self, numero_id_tributaria: str) -> list[DatosActivo]:
        return [_activo(f) for f in filas(
            self.db, _BASE + f" WHERE {_CONFIRMADO} AND est.nombre = ANY(:estados) AND f.numero_id_tributaria = :nit"
                             " ORDER BY a.id_activo_biologico",
            {"tz": nombre_zona_usuario(), "estados": list(ESTADOS_VALORABLES), "nit": numero_id_tributaria},
        )]

    def fincas_sin_titular_del_periodo(self, id_periodo_contable: int, numero_id_tributaria: str) -> list[str]:
        return [f["nombre"] for f in filas(self.db, """
            SELECT DISTINCT f.nombre FROM modulo6.lineas_asiento_nic41 l JOIN modulo9.fincas f ON f.id_finca = l.id_finca
            WHERE l.id_periodo_contable = :p AND f.numero_id_tributaria IS DISTINCT FROM :nit ORDER BY 1""",
            {"p": id_periodo_contable, "nit": numero_id_tributaria})]

    def especie(self, id_especie: int) -> Optional[dict]:
        return fila(self.db, "SELECT id_especie, nombre, es_activo FROM modulo9.especies WHERE id_especie = :e",
                    {"e": id_especie})

    def metrica_produccion(self, id_metrica_produccion: int) -> Optional[dict]:
        return fila(self.db, """SELECT id_metrica_produccion, nombre, unidad_medida, id_especie
                                FROM modulo9.metricas_produccion WHERE id_metrica_produccion = :m""",
                    {"m": id_metrica_produccion})

    def evento_sanitario_del_activo(self, id_evento: int, id_activo_biologico: int) -> bool:
        return fila(self.db, """
            SELECT 1 AS ok FROM modulo2.eventos_sanitarios es
            JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento
            WHERE es.id_evento = :e AND ea.id_activo_biologico = :a
        """, {"e": id_evento, "a": id_activo_biologico}) is not None

    def eventos_sanitarios_del_activo(self, id_activo_biologico: int) -> list[dict]:
        return filas(self.db, """
            SELECT es.id_evento, ea.fecha, es.tipo::text AS tipo, es.diagnostico
            FROM modulo2.eventos_sanitarios es
            JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento
            WHERE ea.id_activo_biologico = :a ORDER BY ea.fecha DESC LIMIT 100
        """, {"a": id_activo_biologico})
