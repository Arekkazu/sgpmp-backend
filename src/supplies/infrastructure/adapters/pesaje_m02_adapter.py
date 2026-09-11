"""Adaptador de consulta de pesaje (RF-40) contra ``modulo2`` para el ICA (RF-74).

El peso vive en ``modulo2.eventos_crecimeinto`` (``id_evento`` comparte identidad con
``eventos_activos.id_eventos``, donde está ``id_activo_biologico`` y la ``fecha``). Se
usa SQL directo porque no hay modelo ORM de eventos_crecimeinto en este módulo (mismo
patrón que ``evento_sanitario_m02_adapter``).

- INDIVIDUAL  → ``valor_medicion``.
- POBLACIONAL → ``nuevo_peso_promedio`` (peso promedio por individuo).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.supplies.domain.repositories.pesaje_consulta_port import PesajeConsultaPort

# Variantes de tipo_medicion que representan un pesaje (RF-40).
_TIPOS_PESO = ("PESO", "PESO_VIVO")


class PesajeM02Adapter(PesajeConsultaPort):
    """Consulta el pesaje más reciente en o antes de una fecha en ``modulo2``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_peso_en_o_antes(
        self, id_activo_biologico: int, fecha: date, es_poblacional: bool
    ) -> Optional[Decimal]:
        columna = "ec.nuevo_peso_promedio" if es_poblacional else "ec.valor_medicion"
        row = self.db.execute(
            text(
                f"SELECT {columna} AS peso "
                "FROM modulo2.eventos_crecimeinto ec "
                "JOIN modulo2.eventos_activos ea ON ea.id_eventos = ec.id_evento "
                "WHERE ea.id_activo_biologico = :id "
                "  AND upper(ec.tipo_medicion) = ANY(:tipos) "
                f"  AND {columna} IS NOT NULL "
                "  AND ea.fecha::date <= :fecha "
                "ORDER BY ea.fecha DESC "
                "LIMIT 1"
            ),
            {"id": id_activo_biologico, "tipos": list(_TIPOS_PESO), "fecha": fecha},
        ).fetchone()
        if row is None or row.peso is None:
            return None
        return Decimal(row.peso)
