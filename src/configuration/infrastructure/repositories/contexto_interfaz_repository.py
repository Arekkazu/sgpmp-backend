"""Implementación SQLAlchemy del puerto ``ContextoInterfazRepository`` (RF-25).

Consulta la vista ``modulo9.vw_rf25_contexto_usuario`` para obtener el contexto
del usuario y ``modulo1.permisos`` para los módulos autorizados de su rol.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.contexto_interfaz import ContextoInterfaz
from src.configuration.domain.repositories.contexto_interfaz_repository import ContextoInterfazRepository


class SqlAlchemyContextoInterfazRepository(ContextoInterfazRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_por_usuario(self, id_usuario: int, id_rol: int) -> ContextoInterfaz:
        # La vista emite una fila por finca activa del usuario, así que sin ORDER BY la
        # "finca activa" era la que Postgres devolviera primero: podía cambiar entre dos
        # peticiones seguidas y con ella la marca institucional de RF-26. Se fija la de
        # menor id — determinista y estable mientras no exista un selector de finca.
        # `especies_en_finca` es el nombre real de la columna en la vista; el alias que se
        # usaba antes no existe y hacía que este endpoint respondiera 500 contra la BD.
        fila = self.db.execute(
            text(
                "SELECT id_usuario, nombre_completo, id_rol, nombre_rol, "
                "id_finca, finca_activa, departamento, "
                "especies_en_finca AS especies_configuradas "
                "FROM modulo9.vw_rf25_contexto_usuario "
                "WHERE id_usuario = :id_usuario "
                "ORDER BY id_finca NULLS LAST"
            ),
            {"id_usuario": id_usuario},
        ).mappings().first()

        modulos = self._obtener_modulos_autorizados(id_rol)

        if fila is None:
            return ContextoInterfaz(
                id_usuario=id_usuario,
                nombre_completo="",
                id_rol=id_rol,
                nombre_rol="",
                id_finca=None,
                finca_activa=None,
                departamento=None,
                especies_configuradas=[],
                modulos_autorizados=modulos,
            )

        return ContextoInterfaz(
            id_usuario=fila["id_usuario"],
            nombre_completo=fila["nombre_completo"] or "",
            id_rol=fila["id_rol"],
            nombre_rol=fila["nombre_rol"] or "",
            id_finca=fila["id_finca"],
            finca_activa=fila["finca_activa"],
            departamento=fila["departamento"],
            especies_configuradas=list(fila["especies_configuradas"] or []),
            modulos_autorizados=modulos,
        )

    def _obtener_modulos_autorizados(self, id_rol: int) -> list[str]:
        filas = self.db.execute(
            text(
                "SELECT DISTINCT r.nombre_recurso "
                "FROM modulo1.permisos p "
                "JOIN modulo1.recursos r ON r.id_recurso = p.id_recurso "
                "WHERE p.id_rol = :id_rol AND p.es_activo IS TRUE "
                "ORDER BY r.nombre_recurso"
            ),
            {"id_rol": id_rol},
        ).mappings().all()
        return [f["nombre_recurso"] for f in filas]
