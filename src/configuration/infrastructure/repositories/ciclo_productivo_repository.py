# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Implementación SQL de :class:`CicloProductivoRepository`.

``ciclos_productivos.id_ciclo_biologico`` guarda la primera fase: de ahí sale la especie del ciclo (M02 la lee
así). Las fases viven en ``ciclos_productivos_biologicos`` y su orden es el de inserción, el mismo que usa
RF-37 para la secuencia estándar."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.ciclo_productivo import CicloProductivo, FaseCicloProductivo
from src.configuration.domain.repositories.ciclo_productivo_repository import CicloProductivoRepository
from src.shared.db_error_translator import raise_from_db_error

_CICLOS = """
    SELECT cp.id_ciclo_productivo, cp.nombre, cb.id_especie,
           EXISTS (SELECT 1 FROM modulo2.gestiones_fases g WHERE g.id_ciclo_productiva = cp.id_ciclo_productivo) AS en_uso
    FROM modulo9.ciclos_productivos cp
    JOIN modulo9.ciclos_biologicos cb ON cb.id_ciclo_biologico = cp.id_ciclo_biologico
"""

_FASES = text("""
    SELECT cpb.id_ciclo_productivo, cb.id_ciclo_biologico, cb.nombre, cb.duracion_dias
    FROM modulo9.ciclos_productivos_biologicos cpb
    JOIN modulo9.ciclos_biologicos cb ON cb.id_ciclo_biologico = cpb.id_ciclo_biologico
    WHERE cpb.id_ciclo_productivo = ANY(:ids)
    ORDER BY cpb.id_ciclo_productivo, cpb.id_ciclos_productivo_biologico
""")

# Las métricas habilitadas en el ciclo (RF-43) son configuración suya: se van con él.
_BORRAR = (
    text("DELETE FROM modulo9.metricas_ciclo_productivo WHERE id_ciclo_productivo = :id"),
    text("DELETE FROM modulo9.ciclos_productivos_biologicos WHERE id_ciclo_productivo = :id"),
    text("DELETE FROM modulo9.ciclos_productivos WHERE id_ciclo_productivo = :id"),
)


class SqlAlchemyCicloProductivoRepository(CicloProductivoRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def _con_fases(self, filas) -> list[CicloProductivo]:
        ciclos = [CicloProductivo(nombre=f.nombre, id_especie=f.id_especie, id_ciclo_productivo=f.id_ciclo_productivo,
                                  en_uso=f.en_uso) for f in filas]
        por_id = {c.id_ciclo_productivo: c for c in ciclos}
        if por_id:
            for f in self.db.execute(_FASES, {"ids": list(por_id)}):
                por_id[f.id_ciclo_productivo].fases.append(
                    FaseCicloProductivo(id_ciclo_biologico=f.id_ciclo_biologico, nombre=f.nombre,
                                        duracion_dias=f.duracion_dias))
        return ciclos

    def listar_por_especie(self, id_especie: int) -> list[CicloProductivo]:
        return self._con_fases(self.db.execute(
            text(_CICLOS + " WHERE cb.id_especie = :e ORDER BY lower(cp.nombre), cp.id_ciclo_productivo"),
            {"e": id_especie}).all())

    def obtener(self, id_ciclo_productivo: int) -> Optional[CicloProductivo]:
        ciclos = self._con_fases(self.db.execute(text(_CICLOS + " WHERE cp.id_ciclo_productivo = :id"),
                                                 {"id": id_ciclo_productivo}).all())
        return ciclos[0] if ciclos else None

    def existe_nombre(self, id_especie: int, nombre: str, excluir: Optional[int] = None) -> bool:
        return self.db.execute(text("""
            SELECT 1 FROM modulo9.ciclos_productivos cp
            JOIN modulo9.ciclos_biologicos cb ON cb.id_ciclo_biologico = cp.id_ciclo_biologico
            WHERE cb.id_especie = :e AND lower(cp.nombre) = lower(:n)
              AND cp.id_ciclo_productivo IS DISTINCT FROM CAST(:x AS integer)
            LIMIT 1"""), {"e": id_especie, "n": nombre, "x": excluir}).first() is not None

    def guardar(self, ciclo: CicloProductivo) -> CicloProductivo:
        datos = {"n": ciclo.nombre, "d": ciclo.duracion_dias, "b": ciclo.fases[0].id_ciclo_biologico}
        try:
            if ciclo.id_ciclo_productivo is None:
                ciclo.id_ciclo_productivo = self.db.execute(text("""
                    INSERT INTO modulo9.ciclos_productivos (nombre, duracion_dias, id_ciclo_biologico)
                    VALUES (:n, :d, :b) RETURNING id_ciclo_productivo"""), datos).scalar_one()
                actuales: list[int] = []
            else:
                self.db.execute(text("""
                    UPDATE modulo9.ciclos_productivos SET nombre = :n, duracion_dias = :d, id_ciclo_biologico = :b
                    WHERE id_ciclo_productivo = :id"""), {**datos, "id": ciclo.id_ciclo_productivo})
                actuales = [r[0] for r in self.db.execute(text("""
                    SELECT id_ciclo_biologico FROM modulo9.ciclos_productivos_biologicos
                    WHERE id_ciclo_productivo = :id ORDER BY id_ciclos_productivo_biologico"""),
                    {"id": ciclo.id_ciclo_productivo})]
            nuevas = [f.id_ciclo_biologico for f in ciclo.fases]
            if nuevas != actuales:  # delete-then-insert: el orden de inserción es la secuencia
                self.db.execute(text("DELETE FROM modulo9.ciclos_productivos_biologicos WHERE id_ciclo_productivo = :id"),
                                {"id": ciclo.id_ciclo_productivo})
                for id_etapa in nuevas:
                    self.db.execute(text("""
                        INSERT INTO modulo9.ciclos_productivos_biologicos (id_ciclo_productivo, id_ciclo_biologico)
                        VALUES (:id, :b)"""), {"id": ciclo.id_ciclo_productivo, "b": id_etapa})
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
        return ciclo

    def eliminar(self, id_ciclo_productivo: int) -> None:
        try:
            for sql in _BORRAR:
                self.db.execute(sql, {"id": id_ciclo_productivo})
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
