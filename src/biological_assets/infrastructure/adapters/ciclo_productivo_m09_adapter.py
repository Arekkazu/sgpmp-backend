from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.repositories.ciclo_consulta_port import (
    CicloConsultaPort,
    CicloProductivoConsulta,
    FaseCiclo,
)


class CicloProductivoM09Adapter(CicloConsultaPort):
    """Consulta directamente modulo9.ciclos_productivos y sus fases biológicas."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_ciclo_con_fases(self, id_ciclo_productivo: int) -> Optional[CicloProductivoConsulta]:
        ciclo_row = self.db.execute(
            text(
                'SELECT cp.id_ciclo_productivo, cp.nombre, cb.id_especie '
                'FROM modulo9.ciclos_productivos cp '
                'LEFT JOIN modulo9.ciclos_biologicos cb '
                '  ON cb.id_ciclo_biologico = cp.id_ciclo_biologico '
                'WHERE cp.id_ciclo_productivo = :id'
            ),
            {'id': id_ciclo_productivo},
        ).fetchone()

        if ciclo_row is None:
            return None
        return self._con_fases(ciclo_row)

    def listar_por_especie(self, id_especie: int) -> list[CicloProductivoConsulta]:
        filas = self.db.execute(
            text(
                'SELECT cp.id_ciclo_productivo, cp.nombre, cb.id_especie '
                'FROM modulo9.ciclos_productivos cp '
                'JOIN modulo9.ciclos_biologicos cb '
                '  ON cb.id_ciclo_biologico = cp.id_ciclo_biologico '
                'WHERE cb.id_especie = :id_especie '
                'ORDER BY cp.nombre'
            ),
            {'id_especie': id_especie},
        ).fetchall()
        return [self._con_fases(f) for f in filas]

    def _con_fases(self, ciclo_row) -> CicloProductivoConsulta:
        id_ciclo_productivo = ciclo_row.id_ciclo_productivo
        fases_rows = self.db.execute(
            text(
                'SELECT cpb.id_ciclos_productivo_biologico, '
                '       cb.id_ciclo_biologico, '
                '       cb.nombre AS nombre_fase, '
                '       cb.duracion_dias '
                'FROM modulo9.ciclos_productivos_biologicos cpb '
                'JOIN modulo9.ciclos_biologicos cb '
                '  ON cb.id_ciclo_biologico = cpb.id_ciclo_biologico '
                'WHERE cpb.id_ciclo_productivo = :id '
                'ORDER BY cpb.id_ciclos_productivo_biologico ASC'
            ),
            {'id': id_ciclo_productivo},
        ).fetchall()

        fases = [
            FaseCiclo(
                id_ciclos_productivo_biologico=r.id_ciclos_productivo_biologico,
                id_ciclo_biologico=r.id_ciclo_biologico,
                nombre_fase=r.nombre_fase,
                duracion_dias=r.duracion_dias,
            )
            for r in fases_rows
        ]

        return CicloProductivoConsulta(
            id_ciclo_productivo=ciclo_row.id_ciclo_productivo,
            nombre=ciclo_row.nombre,
            fases=fases,
            id_especie=ciclo_row.id_especie,
        )

    def metrica_habilitada_en_ciclo(self, id_ciclo_productivo: int, id_metrica_produccion: int) -> bool:
        row = self.db.execute(
            text(
                'SELECT 1 FROM modulo9.metricas_ciclo_productivo '
                'WHERE id_ciclo_productivo = :id_ciclo '
                'AND id_metrica_produccion = :id_metrica '
                'LIMIT 1'
            ),
            {'id_ciclo': id_ciclo_productivo, 'id_metrica': id_metrica_produccion},
        ).fetchone()
        return row is not None
