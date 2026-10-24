"""[RF-43 E-04] Habilitar una métrica en ciclos productivos y patologías del activo
(RF-41), contra el esquema real."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.infrastructure.adapters.parametros_especie_m09_adapter import ParametrosEspecieM09Adapter
from src.configuration.infrastructure.models.especie_patologia_model import EspeciePatologiaModel
from src.configuration.infrastructure.models.metrica_produccion_model import MetricaProduccionModel
from src.configuration.infrastructure.repositories.ciclo_metrica_repository import SqlAlchemyCicloMetricaRepository

pytestmark = pytest.mark.integration


def _especie(db: Session) -> int:
    especie = db.execute(text('SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 1')).scalar()
    if especie is None:
        pytest.skip('Se requiere al menos una especie activa en modulo9.')
    return especie


def _ciclo_productivo(db: Session, id_especie: int, nombre: str) -> int:
    id_bio = db.execute(text(
        "INSERT INTO modulo9.ciclos_biologicos (nombre, duracion_dias, id_especie) "
        "VALUES (:n, 30, :e) RETURNING id_ciclo_biologico"), {'n': f'zz fase {nombre}', 'e': id_especie}).scalar_one()
    return db.execute(text(
        "INSERT INTO modulo9.ciclos_productivos (nombre, duracion_dias, id_ciclo_biologico) "
        "VALUES (:n, 60, :b) RETURNING id_ciclo_productivo"), {'n': nombre, 'b': id_bio}).scalar_one()


def test_reemplaza_los_ciclos_de_la_metrica(db_session: Session) -> None:
    especie = _especie(db_session)
    a = _ciclo_productivo(db_session, especie, 'zz ciclo A')
    b = _ciclo_productivo(db_session, especie, 'zz ciclo B')
    metrica = MetricaProduccionModel(
        nombre='zz alevines', unidad_medida='unidades', tipo_medicion='CONTEO', tiene_estado=True,
        id_especie=especie, aplica_a_tipo_activo='AMBOS', tipo_dato='ENTERO', es_obligatorio=False, es_activo=True,
    )
    db_session.add(metrica)
    db_session.flush()
    repo = SqlAlchemyCicloMetricaRepository(db_session)

    def habilitados() -> set[int]:
        return {c.id_ciclo_productivo for c in repo.listar_por_metrica(metrica.id_metrica_produccion, especie) if c.habilitada}

    repo.reemplazar(metrica.id_metrica_produccion, {a, b})
    repo.reemplazar(metrica.id_metrica_produccion, {a, b})  # idempotente: no duplica
    assert habilitados() >= {a, b}
    assert db_session.execute(text(
        'SELECT count(*) FROM modulo9.metricas_ciclo_productivo WHERE id_metrica_produccion = :m'
    ), {'m': metrica.id_metrica_produccion}).scalar() == 2

    repo.reemplazar(metrica.id_metrica_produccion, {b})
    assert a not in habilitados() and b in habilitados()
    repo.reemplazar(metrica.id_metrica_produccion, set())
    assert habilitados() == set()


def test_patologias_activas_de_la_especie(db_session: Session) -> None:
    especie = _especie(db_session)
    db_session.add_all([
        EspeciePatologiaModel(id_especie=especie, nombre='zz ich', es_activo=True),
        EspeciePatologiaModel(id_especie=especie, nombre='zz retirada', es_activo=False),
    ])
    db_session.flush()
    nombres = [p.nombre for p in ParametrosEspecieM09Adapter(db_session).listar_patologias(especie)]
    assert 'zz ich' in nombres and 'zz retirada' not in nombres
