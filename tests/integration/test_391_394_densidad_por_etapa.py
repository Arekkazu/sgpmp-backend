# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #391/#394 RF-16/RF-36: densidad máxima por etapa contra el esquema real |
"""#391/#394 contra el esquema real: la densidad de la etapa se guarda con su auditoría y CHECK, y M02 la lee
para el lote que está en esa fase."""
from __future__ import annotations

from decimal import Decimal as D

import pytest
from sqlalchemy import text

import main  # noqa: F401  (registra todos los modelos ORM, la auditoría referencia modulo1.usuarios)

from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter
from src.configuration.application.use_cases.ciclos.configurar_densidad_etapa_use_case import (
    ConfigurarDensidadEtapaUseCase,
)
from src.configuration.infrastructure.repositories.auditoria_ciclo_repository import SqlAlchemyAuditoriaCicloRepository
from src.configuration.infrastructure.repositories.ciclo_biologico_repository import SqlAlchemyCicloBiologicoRepository
from src.shared.errors import PreconditionFailedError
from tests.integration.test_512_ciclos_productivos import _especie_con_etapas

pytestmark = pytest.mark.integration


def test_densidad_de_la_etapa_se_audita_y_m02_la_aplica_al_lote_en_esa_fase(db_session, crear_usuario_db):
    uid = crear_usuario_db(id_rol=1)["id_usuario"]
    _, (ceba,) = _especie_con_etapas(db_session, ("Ceba", 120))
    configurar = ConfigurarDensidadEtapaUseCase(db_session, SqlAlchemyCicloBiologicoRepository(db_session),
                                                SqlAlchemyAuditoriaCicloRepository(db_session))
    etapa = configurar.execute(ceba, densidad_maxima=D("2.5"), biomasa_maxima=None, aviso_preventivo_pct=85,
                               fecha_actualizacion=None, id_usuario=uid)
    assert (etapa.densidad_maxima, etapa.aviso_preventivo_pct) == (D("2.50"), 85)
    auditoria = db_session.execute(text("SELECT tipo_operacion, valores_nuevos->>'densidad_maxima' FROM "
                                        "modulo9.auditorias_ciclos_biologicos WHERE id_ciclo_biologico = :c"),
                                   {"c": ceba}).one()
    assert tuple(auditoria) == ("UPDATE", "2.50")

    with pytest.raises(PreconditionFailedError):  # sin la fecha leída, una etapa ya editada responde 412
        configurar.execute(ceba, densidad_maxima=D("3"), biomasa_maxima=None, aviso_preventivo_pct=90,
                           fecha_actualizacion=None, id_usuario=uid)

    # Un lote con la fase de Ceba activa recibe ese límite.
    cp = db_session.execute(text("INSERT INTO modulo9.ciclos_productivos(nombre, duracion_dias, id_ciclo_biologico) "
                                 "VALUES ('Engorde', 120, :c) RETURNING id_ciclo_productivo"), {"c": ceba}).scalar_one()
    fase = db_session.execute(text("INSERT INTO modulo9.ciclos_productivos_biologicos(id_ciclo_productivo, id_ciclo_biologico) "
                                   "VALUES (:p, :c) RETURNING id_ciclos_productivo_biologico"), {"p": cp, "c": ceba}).scalar_one()
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("INSERT INTO modulo2.gestiones_fases(id_activo_biologico, id_ciclo_productiva, "
                            "id_ciclos_productivo_biologico, fecha_inicio, es_activa, id_usuario) VALUES (-7, :p, :f, now(), true, -1)"),
                       {"p": cp, "f": fase})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    limite = InfraestructuraM09Adapter(db_session).limite_etapa_del_activo(-7)
    assert (limite.nombre_etapa, limite.densidad_maxima, limite.aviso_preventivo_pct) == ("Ceba", D("2.50"), 85)
    assert InfraestructuraM09Adapter(db_session).limite_etapa_del_activo(-8) is None


def test_la_base_rechaza_densidad_fuera_de_rango(db_session):
    _, (cria,) = _especie_con_etapas(db_session, ("Cría", 90))
    with pytest.raises(Exception, match="ck_ciclo_biologico_densidad_maxima"):
        with db_session.begin_nested():
            db_session.execute(text("UPDATE modulo9.ciclos_biologicos SET densidad_maxima = 0 WHERE id_ciclo_biologico = :c"),
                               {"c": cria})
