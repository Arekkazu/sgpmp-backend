# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-07 RF-53: monitor de ingesta real, con rango acotado y paginación en BD |
"""AJF-07: la pestaña Ingesta pintaba ingestaMock.ts; ahora lee modulo3.bitacora_ingest."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock

import pytest

from src.shared.errors import ValidationError
from src.telemetry.application.use_cases.ingesta.consultar_ingesta_use_case import ConsultarIngestaUseCase
from src.telemetry.domain.entities.lectura_ingesta import IndicadoresIngesta
from src.telemetry.infrastructure.repositories.ingesta_repository import SqlAlchemyIngestaRepository

AHORA = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)


def test_sin_fechas_consulta_las_ultimas_24_horas():
    repo = Mock()
    repo.listar.return_value = ([], 0)
    _, _, f = ConsultarIngestaUseCase(repo).listar(ids_fincas=[1], ahora=AHORA)
    assert (f.desde, f.hasta) == (AHORA - timedelta(hours=24), AHORA)
    assert repo.listar.call_args.args[0].ids_fincas == [1]


@pytest.mark.parametrize('kw, codigo', [
    ({'desde': AHORA - timedelta(days=32), 'hasta': AHORA}, 'RANGO_MAXIMO_EXCEDIDO'),
    ({'desde': AHORA, 'hasta': AHORA - timedelta(hours=1)}, 'RANGO_FECHAS_INVALIDO'),
    ({'por_pagina': 201}, 'POR_PAGINA_INVALIDO'),
    ({'estado_calidad': 'CUALQUIERA'}, 'ESTADO_INVALIDO'),
    ({'origen': 'NUBE'}, 'ORIGEN_INVALIDO'),
])
def test_parametros_invalidos_son_400(kw, codigo):
    with pytest.raises(ValidationError) as e:
        ConsultarIngestaUseCase(Mock()).listar(ids_fincas=None, ahora=AHORA, **kw)
    assert e.value.code == codigo


def test_repositorio_pagina_en_bd_y_toma_el_total_de_la_ventana():
    db = MagicMock()
    fila = {k: None for k in (
        'fecha_captura_dato', 'tipo_evento', 'estado_calidad', 'severidad', 'descripcion', 'id_sensor', 'nombre_sensor',
        'id_dispositivo_iot', 'serial_dispositivo', 'nombre_area', 'gateway_id', 'id_telemetria')}
    fila.update(id_bitacora_ingest=7, fecha_evento=AHORA, total=120)
    db.execute.return_value.mappings.return_value.all.return_value = [fila]
    repo = SqlAlchemyIngestaRepository(db)
    _, _, f = ConsultarIngestaUseCase(repo).listar(ids_fincas=None, pagina=3, por_pagina=50, ahora=AHORA)
    items, total = repo.listar(f)
    sql, params = db.execute.call_args.args
    assert (params['limite'], params['desplazamiento']) == (50, 100)
    assert 't.timestamp_captura = b.fecha_captura_dato' in str(sql)
    assert total == 120 and items[0].id_bitacora_ingest == 7


def test_indicadores_son_del_dia_del_usuario(en_colombia):
    repo = Mock()
    repo.indicadores.return_value = IndicadoresIngesta(10, 8, 1, 1)
    ConsultarIngestaUseCase(repo).indicadores_de_hoy([1])
    desde, hasta, fincas = repo.indicadores.call_args.args
    assert desde.utcoffset() is not None and (hasta - desde) < timedelta(days=1) and fincas == [1]
