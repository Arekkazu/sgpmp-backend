"""[RF-43] El evento productivo elige el producto por su métrica (id), no por la
categoría de medición.

Antes ``tipo_producto`` se comparaba contra ``tipo_medicion`` (PESO, CONTEO...):
"alevines producidos" solo pasaba escribiendo CONTEO, y con dos métricas de la
misma categoría la consulta tomaba cualquiera de las dos.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.infrastructure.adapters.parametros_especie_m09_adapter import ParametrosEspecieM09Adapter
from src.configuration.infrastructure.models.metrica_produccion_model import MetricaProduccionModel

pytestmark = pytest.mark.integration


def _metrica(db: Session, id_especie: int, nombre: str, aplica: str, es_activo: bool = True) -> int:
    m = MetricaProduccionModel(
        nombre=nombre, unidad_medida='unidades', tipo_medicion='CONTEO', tiene_estado=True,
        id_especie=id_especie, aplica_a_tipo_activo=aplica, tipo_dato='ENTERO',
        es_obligatorio=False, es_activo=es_activo,
    )
    db.add(m)
    db.flush()
    return m.id_metrica_produccion


def test_metricas_productivas_por_id_y_tipo_de_activo(db_session: Session) -> None:
    especie = db_session.execute(
        text('SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 1')
    ).scalar()
    if especie is None:
        pytest.skip('Se requiere al menos una especie activa en modulo9.')

    alevines = _metrica(db_session, especie, 'zz alevines producidos', 'AMBOS')
    solo_individual = _metrica(db_session, especie, 'zz crias individuales', 'INDIVIDUAL')
    inactiva = _metrica(db_session, especie, 'zz conteo retirado', 'AMBOS', es_activo=False)
    adapter = ParametrosEspecieM09Adapter(db_session)

    # Dos métricas CONTEO de la especie: cada id resuelve la suya, con su nombre.
    lote = adapter.obtener_metrica_productiva(alevines, especie, 'POBLACIONAL')
    assert lote is not None and lote.tipo_producto == 'zz alevines producidos'
    assert lote.tipo_medicion == 'CONTEO'
    assert adapter.obtener_metrica_productiva(solo_individual, especie, 'INDIVIDUAL').tipo_producto == 'zz crias individuales'

    # Fuera del catálogo del activo: otro tipo de activo, inactiva u otra especie.
    assert adapter.obtener_metrica_productiva(solo_individual, especie, 'POBLACIONAL') is None
    assert adapter.obtener_metrica_productiva(inactiva, especie, 'POBLACIONAL') is None
    assert adapter.obtener_metrica_productiva(alevines, especie + 100000, 'POBLACIONAL') is None

    ids_lote = [m.id_metrica_produccion for m in adapter.listar_metricas_productivas(especie, 'POBLACIONAL')]
    assert alevines in ids_lote
    assert solo_individual not in ids_lote and inactiva not in ids_lote
