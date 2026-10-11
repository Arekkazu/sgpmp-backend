"""INC-M09-64-G54 (#498): dos ediciones simultáneas no pueden pasar ambas el 412.

El control de concurrencia optimista lee la entidad, compara la marca del
cliente y escribe. Sin bloqueo, dos transacciones leen la misma marca a la vez,
las dos pasan la validación y la última pisa a la primera con HTTP 200
(actualización perdida). La lectura de edición ahora toma la fila con
``SELECT ... FOR UPDATE``: la segunda transacción espera a que la primera
confirme y, al despertar, Postgres le entrega la fila ya actualizada, así que
compara contra la marca nueva y responde 412.

Estas pruebas fijan que cada lectura de edición pida el bloqueo y que la
lectura normal no lo pida (no bloquear consultas). La carrera real con dos
peticiones en paralelo está reproducida en
``anotaciones/lote_qa_2026_10_06.md``.
"""
from __future__ import annotations

import importlib
import pkgutil

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

import src

from src.shared.errors import PreconditionFailedError

_ID_INEXISTENTE = 2_000_000_000


def _importar_modelos() -> None:
    """Registra todos los modelos ORM antes de configurar los mappers."""
    for modulo in pkgutil.walk_packages(src.__path__, "src."):
        if ".infrastructure.models." in modulo.name:
            importlib.import_module(modulo.name)


def _sql_emitido(db: Session, operacion) -> list[str]:
    sentencias: list[str] = []
    conexion = db.connection()

    def capturar(_conn, _cursor, statement, *_args):
        sentencias.append(" ".join(statement.split()))

    event.listen(conexion, "before_cursor_execute", capturar)
    try:
        operacion()
    finally:
        event.remove(conexion, "before_cursor_execute", capturar)
    return sentencias


def _lecturas():
    """(nombre, clase de repo, método) de cada lectura usada por una edición con 412."""
    from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
        SqlAlchemyActivoBiologicoRepository,
    )
    from src.configuration.infrastructure.repositories.ciclo_biologico_repository import (
        SqlAlchemyCicloBiologicoRepository,
    )
    from src.configuration.infrastructure.repositories.configuracion_global_repository import (
        SqlAlchemyConfiguracionGlobalRepository,
    )
    from src.configuration.infrastructure.repositories.especie_patologia_repository import (
        SqlAlchemyEspeciePatologiaRepository,
    )
    from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
    from src.configuration.infrastructure.repositories.finca_repository import SqlAlchemyFincaRepository
    from src.configuration.infrastructure.repositories.identidad_visual_repository import (
        SqlAlchemyIdentidadVisualRepository,
    )
    from src.configuration.infrastructure.repositories.infraestructura_repository import (
        SqlAlchemyInfraestructuraRepository,
    )
    from src.configuration.infrastructure.repositories.metrica_produccion_repository import (
        SqlAlchemyMetricaProduccionRepository,
    )
    from src.configuration.infrastructure.repositories.umbral_ambiental_repository import (
        SqlAlchemyUmbralAmbientalRepository,
    )
    from src.prediction.infrastructure.repositories.patologia_m04_repository import (
        SqlAlchemyPatologiaM04Repository,
    )

    return [
        ("infraestructuras", SqlAlchemyInfraestructuraRepository, "obtener_por_id"),
        ("especies", SqlAlchemyEspecieRepository, "obtener_por_id"),
        ("ciclos_biologicos", SqlAlchemyCicloBiologicoRepository, "obtener_por_id"),
        ("especies_patologias", SqlAlchemyEspeciePatologiaRepository, "obtener_por_id"),
        ("metricas_produccion", SqlAlchemyMetricaProduccionRepository, "obtener_por_id"),
        ("umbrales_ambientales", SqlAlchemyUmbralAmbientalRepository, "obtener_por_id"),
        ("fincas", SqlAlchemyFincaRepository, "obtener_por_id"),
        ("configuraciones_globales", SqlAlchemyConfiguracionGlobalRepository, "obtener_por_id"),
        ("identidad_visuales", SqlAlchemyIdentidadVisualRepository, "obtener_por_finca"),
        ("activos_biologicos", SqlAlchemyActivoBiologicoRepository, "obtener_por_id"),
        ("patologias", SqlAlchemyPatologiaM04Repository, "obtener_por_id"),
    ]


_importar_modelos()


@pytest.mark.parametrize(("tabla", "repo_cls", "metodo"), _lecturas(), ids=[t for t, *_ in _lecturas()])
def test_lectura_para_editar_bloquea_la_fila(db_session: Session, tabla, repo_cls, metodo) -> None:
    leer = getattr(repo_cls(db_session), metodo)

    con_bloqueo = _sql_emitido(db_session, lambda: leer(_ID_INEXISTENTE, bloquear=True))
    sin_bloqueo = _sql_emitido(db_session, lambda: leer(_ID_INEXISTENTE + 1))

    lecturas_tabla = [s for s in con_bloqueo if "FROM modulo" in s and tabla in s]
    assert lecturas_tabla, con_bloqueo
    assert all(s.endswith("FOR UPDATE") for s in lecturas_tabla), lecturas_tabla
    assert not any("FOR UPDATE" in s for s in sin_bloqueo), sin_bloqueo


def test_actualizar_usuario_relee_con_bloqueo_antes_de_comparar_version(
    db_session: Session, crear_usuario_db
) -> None:
    """M01 compara la versión dentro del repo: debe releer la fila bloqueada, no
    la copia del identity map que cargó la consulta previa del caso de uso."""
    from src.identity_access.infrastructure.repositories.usuario_repository import (
        SqlAlchemyUsuarioRepository,
    )

    usuario_db = crear_usuario_db()
    repo = SqlAlchemyUsuarioRepository(db_session)
    usuario = repo.obtener_por_id(usuario_db["id_usuario"])
    assert usuario is not None

    def actualizar_con_version_vieja():
        with pytest.raises(PreconditionFailedError):
            repo.actualizar(usuario, version_cliente=usuario.version - 1)

    sentencias = _sql_emitido(db_session, actualizar_con_version_vieja)
    assert any("modulo1.usuarios" in s and s.endswith("FOR UPDATE") for s in sentencias), sentencias
