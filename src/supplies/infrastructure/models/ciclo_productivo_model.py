"""Modelo ORM mínimo para ``modulo9.ciclos_productivos`` (catálogo, M09).

No existía ningún modelo ORM para esta tabla en todo el proyecto — M02
(``gestiones_fases``) y las lecturas de M05 la consultan siempre vía SQL
crudo (``text()``), nunca a través del ORM. Los modelos de CU-04/CU-05
(``RegistroSuministroModel``, ``AcumuladoCicloModel``, ``ProvisionNic41Model``)
declaran ``ForeignKeyConstraint`` hacia esta tabla; SQLAlchemy necesita un
``Table`` registrado en la ``Base`` compartida para resolver esas FK al hacer
``flush()`` (sin esto, falla con ``NoReferencedTableError`` — el error nunca
se había disparado antes de CU-05 porque ningún módulo escribía por ORM en
una tabla con esta FK). Deliberadamente sin ``ForeignKeyConstraint`` propia
(``id_ciclo_biologico``) ni ``relationship``: solo existe para ser un
objetivo de FK resoluble, no para ser consultada por la app.
"""
from typing import Optional

from sqlalchemy import Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class CicloProductivoModel(Base):
    __tablename__ = 'ciclos_productivos'
    __table_args__ = (
        PrimaryKeyConstraint('id_ciclo_productivo', name='ciclos_productivos_pkey'),
        {'schema': 'modulo9'}
    )

    id_ciclo_productivo: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    duracion_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    id_ciclo_biologico: Mapped[Optional[int]] = mapped_column(Integer)
