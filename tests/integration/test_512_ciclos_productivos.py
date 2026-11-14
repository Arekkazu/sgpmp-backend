# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""#512: no había forma de crear ciclos productivos ni sus fases, y sin ellos RF-37 no abre el ciclo de un
activo y M05 no deja registrar alimento ni medicamento. Se prueba contra el esquema real, y que M02 lea las
fases en el mismo orden en que se guardaron."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from src.biological_assets.infrastructure.adapters.ciclo_productivo_m09_adapter import CicloProductivoM09Adapter
from src.configuration.application.use_cases.ciclos_productivos.editar_ciclo_productivo_use_case import (
    EditarCicloProductivoUseCase,
)
from src.configuration.application.use_cases.ciclos_productivos.eliminar_ciclo_productivo_use_case import (
    EliminarCicloProductivoUseCase,
)
from src.configuration.application.use_cases.ciclos_productivos.registrar_ciclo_productivo_use_case import (
    RegistrarCicloProductivoUseCase,
)
from src.configuration.infrastructure.repositories.ciclo_biologico_repository import SqlAlchemyCicloBiologicoRepository
from src.configuration.infrastructure.repositories.ciclo_productivo_repository import (
    SqlAlchemyCicloProductivoRepository,
)
from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
from src.shared.errors import AppError

pytestmark = pytest.mark.integration


def _especie_con_etapas(db, *etapas: tuple[str, int]) -> tuple[int, list[int]]:
    especie = db.execute(text("INSERT INTO modulo9.especies(nombre, es_activo, fecha_creacion) "
                              "VALUES (:n, true, now()) RETURNING id_especie"),
                         {"n": f"Ternero {uuid.uuid4().hex[:6]}"}).scalar_one()
    ids = [db.execute(text("INSERT INTO modulo9.ciclos_biologicos(nombre, duracion_dias, id_especie, es_activo) "
                           "VALUES (:n, :d, :e, true) RETURNING id_ciclo_biologico"),
                      {"n": n, "d": d, "e": especie}).scalar_one() for n, d in etapas]
    return especie, ids


def _codigo(llamada) -> str:
    with pytest.raises(AppError) as error:
        llamada()
    return error.value.code


def test_ciclo_productivo_con_fases_en_orden_que_m02_respeta(db_session):
    especie, (cria, levante, ceba) = _especie_con_etapas(db_session, ("Cría", 90), ("Levante", 180), ("Ceba", 120))
    ciclos, etapas = SqlAlchemyCicloProductivoRepository(db_session), SqlAlchemyCicloBiologicoRepository(db_session)
    registrar = RegistrarCicloProductivoUseCase(db_session, ciclos, etapas, SqlAlchemyEspecieRepository(db_session))
    editar = EditarCicloProductivoUseCase(db_session, ciclos, etapas)

    ciclo = registrar.execute(especie, "Cría y levante", [cria, levante])
    assert ciclo.duracion_dias == 270
    m02 = {c.id_ciclo_productivo: c for c in CicloProductivoM09Adapter(db_session).listar_por_especie(especie)}
    assert [f.nombre_fase for f in m02[ciclo.id_ciclo_productivo].fases] == ["Cría", "Levante"]

    assert _codigo(lambda: registrar.execute(especie, "cría Y LEVANTE", [cria])) == "CICLO_PRODUCTIVO_DUPLICADO"
    assert _codigo(lambda: registrar.execute(especie, "Otro", [cria, cria])) == "FASE_REPETIDA"
    otra, (ajena,) = _especie_con_etapas(db_session, ("Engorde", 60))
    assert _codigo(lambda: registrar.execute(especie, "Otro", [ajena])) == "ETAPA_NO_DISPONIBLE"

    # Sin activos en el ciclo, las fases se pueden reordenar y ampliar.
    ciclo = editar.execute(ciclo.id_ciclo_productivo, "Ciclo completo", [cria, levante, ceba])
    assert [f.nombre_fase for f in CicloProductivoM09Adapter(db_session).obtener_ciclo_con_fases(ciclo.id_ciclo_productivo).fases] \
        == ["Cría", "Levante", "Ceba"]

    # Con un activo que ya pasó por el ciclo, solo cambia el nombre y no se puede borrar.
    fase = db_session.execute(text("SELECT min(id_ciclos_productivo_biologico) FROM modulo9.ciclos_productivos_biologicos "
                                   "WHERE id_ciclo_productivo = :c"), {"c": ciclo.id_ciclo_productivo}).scalar_one()
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("INSERT INTO modulo2.gestiones_fases(id_activo_biologico, id_ciclo_productiva, "
                            "id_ciclos_productivo_biologico, fecha_inicio, es_activa, id_usuario) VALUES (-1, :c, :f, now(), true, -1)"),
                       {"c": ciclo.id_ciclo_productivo, "f": fase})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    assert _codigo(lambda: editar.execute(ciclo.id_ciclo_productivo, "Ciclo completo", [cria, ceba])) == "CICLO_PRODUCTIVO_EN_USO"
    assert editar.execute(ciclo.id_ciclo_productivo, "Ciclo completo bovino", [cria, levante, ceba]).nombre == "Ciclo completo bovino"
    assert _codigo(lambda: EliminarCicloProductivoUseCase(db_session, ciclos).execute(ciclo.id_ciclo_productivo)) \
        == "CICLO_PRODUCTIVO_EN_USO"


def test_ciclo_sin_uso_se_elimina_con_sus_fases(db_session):
    especie, (cria,) = _especie_con_etapas(db_session, ("Cría", 90))
    ciclos = SqlAlchemyCicloProductivoRepository(db_session)
    ciclo = RegistrarCicloProductivoUseCase(db_session, ciclos, SqlAlchemyCicloBiologicoRepository(db_session),
                                            SqlAlchemyEspecieRepository(db_session)).execute(especie, "Solo cría", [cria])
    EliminarCicloProductivoUseCase(db_session, ciclos).execute(ciclo.id_ciclo_productivo)
    assert ciclos.obtener(ciclo.id_ciclo_productivo) is None
    assert ciclo.id_ciclo_productivo not in {c.id_ciclo_productivo for c in ciclos.listar_por_especie(especie)}
