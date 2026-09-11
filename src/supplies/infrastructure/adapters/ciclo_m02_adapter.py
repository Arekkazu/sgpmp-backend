"""Adaptador de consulta del ciclo productivo abierto (RF-37 / RF-38 / RF-78).

Un activo tiene ciclo abierto cuando existe una fase activa en
``modulo2.gestiones_fases``. Reutiliza ``obtener_fase_activa`` de
biological_assets. ``obtener_por_id`` (CU-05) consulta ``GestionFaseModel``
directamente — no existe un método equivalente en
``SqlAlchemyActivoBiologicoRepository`` y no amerita agregarlo ahí solo para
este CU (lectura por PK, sin lógica de negocio de M02 involucrada).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.infrastructure.models.gestion_fase_model import GestionFaseModel
from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)
from src.supplies.domain.repositories.ciclo_abierto_port import (
    CicloAbierto,
    CicloAbiertoPort,
    FaseProductiva,
)


class CicloM02Adapter(CicloAbiertoPort):
    """Verifica el ciclo/fase productivo abierto de un activo en ``modulo2``."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._repo = SqlAlchemyActivoBiologicoRepository(db)

    def obtener_abierto(self, id_activo: int) -> Optional[CicloAbierto]:
        fase = self._repo.obtener_fase_activa(id_activo)
        if fase is None:
            return None
        return CicloAbierto(
            id_ciclo_productivo=fase.id_ciclo_productiva,
            fecha_inicio=fase.fecha_inicio,
            id_gestion_fases=fase.id_gestion_fases,
        )

    def obtener_por_id(self, id_gestion_fases: int) -> Optional[FaseProductiva]:
        orm = self.db.get(GestionFaseModel, id_gestion_fases)
        if orm is None:
            return None
        return FaseProductiva(
            id_gestion_fases=orm.id_gestion_fases,
            id_activo_biologico=orm.id_activo_biologico,
            id_ciclo_productivo=orm.id_ciclo_productiva,
            fecha_inicio=orm.fecha_inicio,
            fecha_finalizacion=orm.fecha_finalizacion,
            es_activa=orm.es_activa,
        )
