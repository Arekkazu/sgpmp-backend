"""Implementación SQLAlchemy del puerto ``ContextoInterfazRepository`` (RF-25).

Consulta la vista ``modulo9.vw_rf25_contexto_usuario`` para obtener el contexto
del usuario, ``modulo9.infraestructuras`` para saber si la finca tiene catálogo
configurado y ``modulo1.permisos`` para los módulos autorizados de su rol.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.configuration.domain.entities.contexto_interfaz import ContextoInterfaz
from src.configuration.domain.repositories.contexto_interfaz_repository import ContextoInterfazRepository
from src.shared.errors import GatewayTimeoutError

#: RNF de rendimiento de RF-25: "Tiempo de carga ≤ 2 segundos". El flujo alterno
#: "Fallo en la carga de contexto (Timeout de base de datos)" pide 504 cuando la
#: construcción del contexto lo supera, así que el presupuesto se impone en el
#: propio motor en vez de medirse después de haber esperado de más.
TIMEOUT_CONTEXTO_MS = 2000

#: SQLSTATE 57014 (`query_canceled`): lo que Postgres devuelve al cortar una
#: consulta por `statement_timeout`. Cualquier otro `OperationalError` es una
#: caída de conectividad y debe seguir saliendo como 503 por el handler global.
_SQLSTATE_QUERY_CANCELED = "57014"


class SqlAlchemyContextoInterfazRepository(ContextoInterfazRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_por_usuario(self, id_usuario: int, id_rol: int) -> ContextoInterfaz:
        try:
            return self._construir(id_usuario, id_rol)
        except OperationalError as exc:
            if getattr(exc.orig, "pgcode", None) != _SQLSTATE_QUERY_CANCELED:
                raise
            raise GatewayTimeoutError(
                code="TIMEOUT_CONTEXTO_INTERFAZ",
                message=(
                    "Error al cargar el contexto operativo. Estamos experimentando "
                    "demoras; por favor, intente recargar la página en unos segundos."
                ),
                original_error=exc,
            )

    def _construir(self, id_usuario: int, id_rol: int) -> ContextoInterfaz:
        # `SET LOCAL` vive lo que vive la transacción del request (`get_db` la
        # cierra al terminar), así que el presupuesto no se filtra a otras
        # peticiones que reusen la conexión del pool.
        self.db.execute(text(f"SET LOCAL statement_timeout = {TIMEOUT_CONTEXTO_MS}"))

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
            tiene_infraestructura=self._tiene_infraestructura(fila["id_finca"]),
        )

    def _tiene_infraestructura(self, id_finca: int | None) -> bool:
        """RF-25: la mitad "ni infraestructura (RF-20)" del flujo alterno de 204."""
        if id_finca is None:
            return False
        return bool(
            self.db.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM modulo9.infraestructuras "
                    "WHERE id_finca = :id_finca AND es_activo IS TRUE)"
                ),
                {"id_finca": id_finca},
            ).scalar()
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
