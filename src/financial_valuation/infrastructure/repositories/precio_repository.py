# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-89: repositorio append-only de precios de mercado |
# | 2026-11-11 | Arekkazu | TC-M06-G106 RF-89 FA-6: un precio corregido no avisa vencimiento |
"""Implementación SQL de :class:`PrecioRepository`. ``categoria`` es un arreglo de un solo valor
(diseño del baseline, ``ck_precio_mercado_categoria_unica``)."""
from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.repositories.precio_repository import PrecioRepository
from src.financial_valuation.domain.services.precios import Precio
from src.financial_valuation.infrastructure.repositories.sql import escribir, fila, filas

_COLUMNAS = """id_precio_mercado, id_especie, categoria[1]::text AS categoria, precio_unitario, unidad_medida,
               fuente::text AS fuente, fecha_vigencia, fecha_vencimiento, id_metrica_produccion, evidencia,
               justificacion, id_precio_corregido"""


def _precio(f: dict) -> Precio:
    return Precio(**{**f, "precio_unitario": Decimal(f["precio_unitario"])})


class SqlAlchemyPrecioRepository(PrecioRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def agregar(self, precio: Precio, region: Optional[str], origen: str, id_usuario: int, estado_inicial: str) -> Precio:
        nuevo_id = escribir(self.db, """
            INSERT INTO modulo6.precios_mercado (id_especie, categoria, precio_unitario, unidad_medida, fecha_vencimiento,
                fecha_vigencia, fuente, estado, evidencia, justificacion, origen_registro, id_usuario, id_precio_corregido,
                region, hash_evidencia, id_metrica_produccion)
            VALUES (:e, ARRAY[CAST(:c AS modulo6.enum_precio_mercado_categoria)], :p, :u, :venc, :vig,
                    CAST(:f AS modulo6.enum_precio_mercado_fuente), CAST(:est AS modulo6.enum_precio_mercado_estado),
                    :ev, :j, CAST(:o AS modulo6.enum_precios_mercado_origen_precio), :usr, :corr, :r, :h, :m)
            RETURNING id_precio_mercado
        """, {"e": precio.id_especie, "c": precio.categoria, "p": precio.precio_unitario, "u": precio.unidad_medida,
              "venc": precio.fecha_vencimiento, "vig": precio.fecha_vigencia, "f": precio.fuente, "est": estado_inicial,
              "ev": precio.evidencia, "j": precio.justificacion, "o": origen, "usr": id_usuario,
              "corr": precio.id_precio_corregido, "r": region,
              "h": hashlib.sha256(precio.evidencia.encode("utf-8")).hexdigest(), "m": precio.id_metrica_produccion})
        return self.obtener(nuevo_id)

    def obtener(self, id_precio_mercado: int) -> Optional[Precio]:
        f = fila(self.db, f"SELECT {_COLUMNAS} FROM modulo6.precios_mercado WHERE id_precio_mercado = :id",
                 {"id": id_precio_mercado})
        return _precio(f) if f else None

    def de_especie(self, id_especie: int, categoria: str, id_metrica_produccion: Optional[int] = None) -> list[Precio]:
        return [_precio(f) for f in filas(self.db, f"""
            SELECT {_COLUMNAS} FROM modulo6.precios_mercado
            WHERE id_especie = :e AND categoria[1]::text = :c
              AND id_metrica_produccion IS NOT DISTINCT FROM CAST(:m AS integer)""",
            {"e": id_especie, "c": categoria, "m": id_metrica_produccion})]

    def listar(self, id_especie: Optional[int]) -> list[Precio]:
        return [_precio(f) for f in filas(self.db, f"""
            SELECT {_COLUMNAS} FROM modulo6.precios_mercado
            WHERE CAST(:e AS integer) IS NULL OR id_especie = :e
            ORDER BY fecha_vigencia DESC, id_precio_mercado DESC""", {"e": id_especie})]

    def por_vencer(self, desde: date, hasta: date) -> list[Precio]:
        return [_precio(f) for f in filas(self.db, f"""SELECT {_COLUMNAS} FROM modulo6.precios_mercado
                                                       WHERE fecha_vencimiento BETWEEN :d AND :h
                                                         AND NOT EXISTS (SELECT 1 FROM modulo6.precios_mercado c
                                                                         WHERE c.id_precio_corregido = precios_mercado.id_precio_mercado)""",
                                          {"d": desde, "h": hasta})]
