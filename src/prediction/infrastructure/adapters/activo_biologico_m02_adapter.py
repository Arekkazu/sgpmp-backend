"""Adaptador real de acceso a activos biológicos para ``prediction`` (RF-25).

Sustituye al ``ActivoBiologicoStubAdapter``: valida que el activo exista y que
pertenezca a una finca dentro del alcance del usuario (o que el rol sea global),
cerrando el IDOR del historial diagnóstico.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.repositories.activo_biologico_port import ActivoBiologicoPort
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter

_SQL_FINCA_DEL_ACTIVO = text(
    """
    SELECT i.id_finca
    FROM modulo2.activos_biologicos ab
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
    WHERE ab.id_activo_biologico = :id_activo
    """
)


class ActivoBiologicoM02Adapter(ActivoBiologicoPort):
    def __init__(self, db: Session) -> None:
        self._db = db

    def activo_existe_y_accesible(self, id_activo: int, id_usuario: int, id_rol: int) -> bool:
        fila = self._db.execute(
            _SQL_FINCA_DEL_ACTIVO, {"id_activo": id_activo}
        ).first()
        if fila is None:
            return False
        alcance = AlcanceFincaAdapter(self._db)
        if alcance.es_global(id_rol):
            return True
        ids_fincas = alcance.listar_ids_fincas_permitidas(id_usuario, id_rol)
        return ids_fincas is not None and fila.id_finca in ids_fincas
