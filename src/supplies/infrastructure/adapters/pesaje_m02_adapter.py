# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74 E6: descarta pesajes ≤ 0            |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Adaptador de consulta de pesaje (RF-40) contra ``modulo2`` para el ICA (RF-74).

El peso vive en ``modulo2.eventos_crecimeinto`` (``id_evento`` comparte identidad con
``eventos_activos.id_eventos``, donde está ``id_activo_biologico`` y la ``fecha``). Se
usa SQL directo porque no hay modelo ORM de eventos_crecimeinto en este módulo (mismo
patrón que ``evento_sanitario_m02_adapter``).

- INDIVIDUAL  → ``valor_medicion``.
- POBLACIONAL → ``nuevo_peso_promedio`` (peso promedio por individuo).

RF-74 E6: un pesaje ≤ 0 se descarta y se usa el siguiente válido. El límite
máximo por especie que menciona E6 no existe en M09 (RF-16); solo se descarta
el valor no positivo.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.supplies.domain.repositories.pesaje_consulta_port import PesajeConsultaPort
from src.shared.fechas import nombre_zona_usuario

# Variantes de tipo_medicion que representan un pesaje (RF-40).
_TIPOS_PESO = ("PESO", "PESO_VIVO")


class PesajeM02Adapter(PesajeConsultaPort):
    """Consulta el pesaje más reciente en o antes de una fecha en ``modulo2``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_peso_en_o_antes(
        self, id_activo_biologico: int, fecha: date, es_poblacional: bool
    ) -> Optional[Decimal]:
        fila = self._pesaje(id_activo_biologico, fecha, es_poblacional, valido=True)
        return Decimal(fila.peso) if fila is not None else None

    def obtener_peso_invalido_en_o_antes(
        self, id_activo_biologico: int, fecha: date, es_poblacional: bool
    ) -> Optional[tuple[date, Decimal]]:
        fila = self._pesaje(id_activo_biologico, fecha, es_poblacional, valido=False)
        return (fila.fecha, Decimal(fila.peso)) if fila is not None else None

    def _pesaje(self, id_activo_biologico: int, fecha: date, es_poblacional: bool, *, valido: bool):
        columna = "ec.nuevo_peso_promedio" if es_poblacional else "ec.valor_medicion"
        condicion = f"{columna} > 0" if valido else f"{columna} <= 0"
        return self.db.execute(
            text(
                f"SELECT {columna} AS peso, (ea.fecha AT TIME ZONE :tz)::date AS fecha "
                "FROM modulo2.eventos_crecimeinto ec "
                "JOIN modulo2.eventos_activos ea ON ea.id_eventos = ec.id_evento "
                "WHERE ea.id_activo_biologico = :id "
                "  AND upper(ec.tipo_medicion) = ANY(:tipos) "
                f"  AND {condicion} "
                "  AND (ea.fecha AT TIME ZONE :tz)::date <= :fecha "
                "ORDER BY ea.fecha DESC "
                "LIMIT 1"
            ),
            {"id": id_activo_biologico, "tipos": list(_TIPOS_PESO), "fecha": fecha, "tz": nombre_zona_usuario()},
        ).fetchone()
