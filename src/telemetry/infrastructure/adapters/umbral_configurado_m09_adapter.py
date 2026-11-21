# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-173-G85 RF-57 E9: consulta los umbrales RF-17 de las especies del área |
"""RF-57 E9: ¿hay umbrales configurados (RF-17, ``modulo9.umbrales_ambientales``) para la variable?

Se miran las especies del área (``modulo9.infraestructuras_especies``, RFC-012). Basta un umbral activo
de la variable para alguna de ellas. Sin área identificada, basta uno para cualquier especie.
"""
from __future__ import annotations

from sqlalchemy import text

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.repositories.umbral_configurado_port import UmbralConfigurado, UmbralConfiguradoPort
from src.telemetry.infrastructure.adapters.variable_alerta_m09_adapter import variable_para_alerta

_SQL_ESPECIES = text("SELECT id_especie FROM modulo9.infraestructuras_especies WHERE id_infraestructura = :area "
                     "ORDER BY id_especie")
_SQL_UMBRAL = text("""
    SELECT EXISTS (SELECT 1 FROM modulo9.umbrales_ambientales
                   WHERE es_activo AND id_variable_ambiental = :variable
                     AND (CAST(:especies AS integer[]) IS NULL OR id_especie = ANY(CAST(:especies AS integer[]))))
""")


class UmbralConfiguradoM09Adapter(UmbralConfiguradoPort):
    def __init__(self, db):
        self.db = db

    def consultar(self, tipo_variable, id_infraestructura):
        variable = variable_para_alerta(self.db, codigo=tipo_variable)
        if variable is None:
            return UmbralConfigurado(False, motivo="VARIABLE_FUERA_DEL_CATALOGO")
        try:
            especies = None
            if id_infraestructura is not None:
                especies = list(self.db.execute(_SQL_ESPECIES, {"area": id_infraestructura}).scalars().all())
                if not especies:
                    return UmbralConfigurado(False, variable["id_variable"], motivo="AREA_SIN_ESPECIES")
            hay = self.db.execute(_SQL_UMBRAL, {"variable": variable["id_variable"], "especies": especies}).scalar_one()
        except Exception as exc:
            raise_from_db_error(exc)
        return UmbralConfigurado(bool(hay), variable["id_variable"], tuple(especies or ()),
                                 None if hay else "SIN_UMBRAL_PARA_LAS_ESPECIES")
