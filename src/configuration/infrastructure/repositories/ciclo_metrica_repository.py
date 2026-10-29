"""Implementación SQLAlchemy de ``CicloMetricaRepository``.

Los ciclos productivos se ligan a la especie por su ciclo biológico
(``ciclos_productivos.id_ciclo_biologico → ciclos_biologicos.id_especie``).
"""
from __future__ import annotations

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.ciclo_metrica import CicloMetrica
from src.configuration.domain.repositories.ciclo_metrica_repository import CicloMetricaRepository
from src.shared.db_error_translator import raise_from_db_error

_LISTAR = text(
    "SELECT cp.id_ciclo_productivo, cp.nombre, "
    "       EXISTS (SELECT 1 FROM modulo9.metricas_ciclo_productivo mc "
    "               WHERE mc.id_ciclo_productivo = cp.id_ciclo_productivo "
    "                 AND mc.id_metrica_produccion = :id_metrica) AS habilitada "
    "FROM modulo9.ciclos_productivos cp "
    "JOIN modulo9.ciclos_biologicos cb ON cb.id_ciclo_biologico = cp.id_ciclo_biologico "
    "WHERE cb.id_especie = :id_especie "
    "ORDER BY cp.nombre"
)

_QUITAR = text(
    "DELETE FROM modulo9.metricas_ciclo_productivo "
    "WHERE id_metrica_produccion = :id_metrica AND id_ciclo_productivo NOT IN :ids"
).bindparams(bindparam('ids', expanding=True))

_QUITAR_TODOS = text("DELETE FROM modulo9.metricas_ciclo_productivo WHERE id_metrica_produccion = :id_metrica")

# La tabla no tiene UNIQUE (id_ciclo_productivo, id_metrica_produccion); el
# NOT EXISTS evita duplicar una habilitación que ya estaba.
_AGREGAR = text(
    "INSERT INTO modulo9.metricas_ciclo_productivo (id_ciclo_productivo, id_metrica_produccion) "
    "SELECT c, :id_metrica FROM unnest(CAST(:ids AS integer[])) AS c "
    "WHERE NOT EXISTS (SELECT 1 FROM modulo9.metricas_ciclo_productivo mc "
    "                  WHERE mc.id_ciclo_productivo = c AND mc.id_metrica_produccion = :id_metrica)"
)


class SqlAlchemyCicloMetricaRepository(CicloMetricaRepository):
    """Lee y reemplaza ``modulo9.metricas_ciclo_productivo``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar_por_metrica(self, id_metrica_produccion: int, id_especie: int) -> list[CicloMetrica]:
        filas = self.db.execute(_LISTAR, {'id_metrica': id_metrica_produccion, 'id_especie': id_especie})
        return [CicloMetrica(f.id_ciclo_productivo, f.nombre, bool(f.habilitada)) for f in filas]

    def reemplazar(self, id_metrica_produccion: int, ids_ciclos_productivos: set[int]) -> None:
        ids = sorted(ids_ciclos_productivos)
        try:
            if ids:
                self.db.execute(_QUITAR, {'id_metrica': id_metrica_produccion, 'ids': ids})
                self.db.execute(_AGREGAR, {'id_metrica': id_metrica_produccion, 'ids': ids})
            else:
                self.db.execute(_QUITAR_TODOS, {'id_metrica': id_metrica_produccion})
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
