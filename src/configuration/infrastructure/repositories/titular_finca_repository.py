# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | RF-19 v1.1: persistencia del titular tributario de la finca |
"""Implementación SQL de :class:`TitularFincaRepository` (columnas de ``modulo9.fincas``)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.repositories.titular_finca_repository import TitularFincaRepository
from src.configuration.domain.value_objects.titular_tributario import TitularTributario
from src.shared.db_error_translator import raise_from_db_error

_COLUMNAS = "id_finca, nombre, tipo_id_tributaria, numero_id_tributaria, dv, razon_social"


class SqlAlchemyTitularFincaRepository(TitularFincaRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener(self, id_finca: int) -> Optional[dict]:
        f = self.db.execute(text(f"SELECT {_COLUMNAS} FROM modulo9.fincas WHERE id_finca = :f"), {"f": id_finca}).first()
        return dict(f._mapping) if f else None

    def otro_con_mismo_numero(self, numero_id_tributaria: str, id_finca: int) -> Optional[dict]:
        f = self.db.execute(text(f"""SELECT {_COLUMNAS} FROM modulo9.fincas
                                     WHERE numero_id_tributaria = :n AND id_finca <> :f LIMIT 1"""),
                            {"n": numero_id_tributaria, "f": id_finca}).first()
        return dict(f._mapping) if f else None

    def guardar(self, id_finca: int, titular: Optional[TitularTributario]) -> None:
        try:
            self.db.execute(text("""UPDATE modulo9.fincas SET tipo_id_tributaria = :t, numero_id_tributaria = :n,
                                        dv = :dv, razon_social = :r, fecha_actualizacion = now()
                                    WHERE id_finca = :f"""), {
                "f": id_finca, "t": titular.tipo_id_tributaria if titular else None,
                "n": titular.numero_id_tributaria if titular else None, "dv": titular.dv if titular else None,
                "r": titular.razon_social.strip() if titular else None})
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
