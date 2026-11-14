# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-277-G20 RF-77: validar serialización, precisión, snapshot y compatibilidad del promedio. |
"""Regresión de serialización; la integración verifica la BD y los endpoints."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.supplies.application.use_cases.reporte_gastos.procesar_cola_reportes_gastos_use_case import _resultado_json
from src.supplies.domain.entities.reporte_gasto import FiltrosReporteGasto, ReporteGasto, TendenciaGasto
from src.supplies.infrastructure.repositories.reporte_gasto_repository import SqlAlchemyReporteGastoRepository

from src.supplies.infrastructure.schema.reporte_gasto_schema import ReporteGastoResponse

CAUSA = 'La cantidad actual del lote es cero. No es posible calcular el promedio por individuo.'


def reporte(**cambios):
    return ReporteGasto(**(dict(
        fecha_inicio=date(2026, 11, 1), fecha_fin=date(2026, 11, 8),
        tipo_periodo='CICLO_COMPLETO', gasto_total_acumulado=Decimal('50000'),
        id_activo_biologico=8, gasto_promedio_individuo=None, causa_no_calculable_promedio=CAUSA,
    ) | cambios))


def test_cantidad_cero_se_serializa_como_no_calculable_y_conserva_causa():
    respuesta = ReporteGastoResponse.desde_entidad(reporte()).model_dump(mode='json')
    assert respuesta['gasto_promedio_individuo'] == 'NO_CALCULABLE'
    assert respuesta['causa_no_calculable_promedio'] == CAUSA
    assert Decimal(respuesta['gasto_total_acumulado']) == Decimal('50000')



@pytest.mark.parametrize('promedio', [Decimal('0'), Decimal('1000'), Decimal('333.3333333333333333333333333')])
def test_promedios_calculables_conservan_precision_y_tipo(promedio):
    original = reporte(gasto_promedio_individuo=promedio, causa_no_calculable_promedio=None)
    respuesta = ReporteGastoResponse.desde_entidad(original)
    assert respuesta.gasto_promedio_individuo == promedio
    assert respuesta.model_dump(mode='json')['gasto_promedio_individuo'] == str(promedio)
    assert original.gasto_promedio_individuo == promedio


def test_promedio_no_aplicable_conserva_null():
    r = ReporteGastoResponse.desde_entidad(reporte(causa_no_calculable_promedio=None))
    assert r.model_dump(mode='json')['gasto_promedio_individuo'] is None


@pytest.mark.parametrize('valor', [None, 'NO_CALCULABLE'])
def test_snapshot_async_admite_resultado_previo_y_literal(valor):
    r = ReporteGastoResponse.desde_snapshot_y_resultado_json(reporte(), {
        'gasto_total_acumulado': '50000', 'gasto_promedio_individuo': valor,
        'causa_no_calculable_promedio': CAUSA,
    })
    assert r.model_dump(mode='json')['gasto_promedio_individuo'] == 'NO_CALCULABLE'
    assert r.causa_no_calculable_promedio == CAUSA


def test_resultado_del_worker_conserva_precision_y_estado_no_calculable():
    r = reporte(tendencia=TendenciaGasto(Decimal('50000'), Decimal('0'), None, 'SIN_BASE_COMPARATIVA'))
    resultado = _resultado_json(r)
    assert resultado['gasto_promedio_individuo'] is None and resultado['causa_no_calculable_promedio'] == CAUSA
    api = ReporteGastoResponse.desde_snapshot_y_resultado_json(r, resultado)
    assert api.gasto_promedio_individuo == 'NO_CALCULABLE'
    assert r.gasto_promedio_individuo is None


def test_schema_no_admite_cualquier_cadena_como_promedio():
    datos = ReporteGastoResponse.desde_entidad(reporte()).model_dump()
    datos['gasto_promedio_individuo'] = 'OTRO_ESTADO'
    with pytest.raises(PydanticValidationError):
        ReporteGastoResponse.model_validate(datos)
    schema = ReporteGastoResponse.model_json_schema()['properties']['gasto_promedio_individuo']
    assert any(opcion.get('const') == 'NO_CALCULABLE' for opcion in schema['anyOf'])


@pytest.mark.parametrize('promedio,causa', [(None, CAUSA), (Decimal('1000.1234'), None), (None, None)])
def test_repositorio_conserva_resumen_y_parametros_sin_mutar_el_reporte(promedio, causa):
    db = Mock()
    original = reporte(gasto_promedio_individuo=promedio, causa_no_calculable_promedio=causa,
                       parametros={'fecha_inicio': '2026-11-01', 'fecha_fin': '2026-11-08', 'id_activo_biologico': 8})
    repo = SqlAlchemyReporteGastoRepository(db)
    repo.guardar(original)
    orm = db.add.call_args.args[0]
    assert 'resumen_promedio' not in original.parametros
    recuperado = repo._a_entidad(orm)
    assert recuperado.gasto_promedio_individuo == promedio and recuperado.causa_no_calculable_promedio == causa
    filtros = FiltrosReporteGasto.desde_dict(recuperado.parametros)
    assert filtros.id_activo_biologico == 8 and filtros.fecha_inicio == date(2026, 11, 1)
    db.commit.assert_not_called()


def test_snapshot_antiguo_no_inventa_cantidad_cero_ni_promedio():
    orm = SimpleNamespace(id_reporte_gasto_acumulado=1, id_activo_biologico=8, id_infraestructura=None,
        fecha_incio_reporte=date(2026, 11, 1), fecha_fin_report=date(2026, 11, 8), categoria='CICLO_COMPLETO',
        total_costo_directo=Decimal('50000'), id_usuario=7, fecha_generacion=None,
        json_parametros={'fecha_inicio': '2026-11-01', 'fecha_fin': '2026-11-08'})
    antiguo = SqlAlchemyReporteGastoRepository._a_entidad(orm)
    assert antiguo.gasto_promedio_individuo is None and antiguo.causa_no_calculable_promedio is None
