"""RF-51 (INC-M02-98-G96): un outlier biológicamente imposible no debe publicarse
como ganancia_peso válida, y conversion_alimenticia debe calcularse con datos
reales de M05 en vez de devolver siempre REQUIERE_M05.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from src.biological_assets.infrastructure.repositories.indicadores_repository import (
    SqlAlchemyIndicadoresRepository,
)


class _Fila:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class _ResultadoFake:
    def __init__(self, filas: list[_Fila]) -> None:
        self._filas = filas

    def fetchall(self):
        return self._filas

    def fetchone(self):
        return self._filas[0] if self._filas else None


class DbFake:
    """Devuelve resultados canned en el orden en que se llama a execute()."""

    def __init__(self, resultados: list[list[_Fila]]) -> None:
        self._cola = [_ResultadoFake(f) for f in resultados]

    def execute(self, _stmt, _params=None):
        return self._cola.pop(0)


AHORA = datetime.now(timezone.utc)


def test_ganancia_peso_outlier_no_se_publica_como_valida():
    filas = [
        _Fila(valor_medicion=Decimal('10.00'), fecha=datetime(2026, 8, 1, tzinfo=timezone.utc)),
        _Fila(valor_medicion=Decimal('510.00'), fecha=datetime(2026, 8, 2, tzinfo=timezone.utc)),
    ]
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([filas]))

    ind, aviso = repo._calcular_ganancia_peso(280, date(2026, 8, 1), date(2026, 8, 2), AHORA)

    assert ind.disponible is False
    assert ind.valor is None
    assert aviso is not None and aviso.startswith('OUTLIER_CRITICO')


def test_ganancia_peso_normal_se_publica():
    filas = [
        _Fila(valor_medicion=Decimal('10.00'), fecha=datetime(2026, 8, 1, tzinfo=timezone.utc)),
        _Fila(valor_medicion=Decimal('12.00'), fecha=datetime(2026, 8, 11, tzinfo=timezone.utc)),
    ]
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([filas]))

    ind, aviso = repo._calcular_ganancia_peso(280, date(2026, 8, 1), date(2026, 8, 11), AHORA)

    assert ind.disponible is True
    assert aviso is None
    assert ind.valor == Decimal('0.2000')


def test_conversion_alimenticia_calcula_fcr_con_datos_m05():
    filas_peso = [
        _Fila(valor_medicion=Decimal('10.00'), fecha=datetime(2026, 8, 1, tzinfo=timezone.utc)),
        _Fila(valor_medicion=Decimal('12.00'), fecha=datetime(2026, 8, 11, tzinfo=timezone.utc)),
    ]
    fila_consumo = _Fila(total_kg=Decimal('20.00'))
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([filas_peso, [fila_consumo]]))

    ind, aviso = repo._calcular_conversion_alimenticia(280, date(2026, 8, 1), date(2026, 8, 11), AHORA)

    assert aviso is None
    assert ind.disponible is True
    assert ind.valor == Decimal('10.0000')  # 20 kg alimento / 2 kg ganados


def test_conversion_alimenticia_sin_consumo_no_falla_por_division_cero():
    filas_peso = [
        _Fila(valor_medicion=Decimal('10.00'), fecha=datetime(2026, 8, 1, tzinfo=timezone.utc)),
        _Fila(valor_medicion=Decimal('12.00'), fecha=datetime(2026, 8, 11, tzinfo=timezone.utc)),
    ]
    fila_consumo = _Fila(total_kg=Decimal('0'))
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([filas_peso, [fila_consumo]]))

    ind, aviso = repo._calcular_conversion_alimenticia(280, date(2026, 8, 1), date(2026, 8, 11), AHORA)

    assert ind.disponible is False
    assert ind.valor is None
    assert aviso is not None and aviso.startswith('DATOS_INSUFICIENTES')


# ── INC-M02-93-G93 (RF-50 FA-03): conteo de métricas de peso por rango ──────

def test_contar_metricas_peso_en_rango_cero():
    fila_conteo = _Fila(total=0)
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([[fila_conteo]]))

    total = repo.contar_metricas_peso_en_rango(279, date(2026, 6, 1), date(2026, 8, 31))

    assert total == 0


def test_contar_metricas_peso_en_rango_con_datos():
    fila_conteo = _Fila(total=4)
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([[fila_conteo]]))

    total = repo.contar_metricas_peso_en_rango(279, date(2026, 6, 1), date(2026, 8, 31))

    assert total == 4


# ── INC-M02-94-G93: advertencia cuando metricas_actuales queda fuera del
# rango solicitado. `peso_actual`/`fecha_ultimo_peso` siguen siendo el
# estado MÁS RECIENTE del activo (no se filtran por rango -- ese es su
# significado), pero ahora se avisa explícitamente cuando ese valor no
# corresponde al periodo que pidió el consumidor.

def _fila_ficha(fecha_ultimo_peso) -> _Fila:
    return _Fila(
        peso_actual=Decimal('250.0'),
        unidad_peso='kg',
        fecha_ultimo_peso=fecha_ultimo_peso,
        cantidad_actual=None,
        biomasa_total=None,
    )


def test_metricas_peso_posterior_al_rango_agrega_advertencia():
    fila = _fila_ficha(date(2026, 9, 10))
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([[fila], []]))

    metricas = repo._obtener_metricas(279, date(2026, 6, 1), date(2026, 8, 31))

    assert 'advertencia_peso_fuera_de_rango' in metricas
    assert '2026-09-10' in metricas['advertencia_peso_fuera_de_rango']
    assert '2026-06-01' in metricas['advertencia_peso_fuera_de_rango']
    assert '2026-08-31' in metricas['advertencia_peso_fuera_de_rango']
    # El valor no se filtra ni se oculta -- sigue devolviéndose tal cual.
    assert metricas['peso_actual'] == 250.0
    assert metricas['fecha_ultimo_peso'] == '2026-09-10'


def test_metricas_peso_anterior_al_rango_agrega_advertencia():
    fila = _fila_ficha(date(2026, 1, 1))
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([[fila], []]))

    metricas = repo._obtener_metricas(279, date(2026, 6, 1), date(2026, 8, 31))

    assert 'advertencia_peso_fuera_de_rango' in metricas


def test_metricas_peso_dentro_del_rango_sin_advertencia():
    fila = _fila_ficha(date(2026, 7, 15))
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([[fila], []]))

    metricas = repo._obtener_metricas(279, date(2026, 6, 1), date(2026, 8, 31))

    assert 'advertencia_peso_fuera_de_rango' not in metricas


def test_metricas_sin_rango_solicitado_sin_advertencia():
    fila = _fila_ficha(date(2026, 9, 10))
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([[fila], []]))

    metricas = repo._obtener_metricas(279, None, None)

    assert 'advertencia_peso_fuera_de_rango' not in metricas


def test_metricas_sin_peso_registrado_sin_advertencia():
    fila = _fila_ficha(None)
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([[fila], []]))

    metricas = repo._obtener_metricas(279, date(2026, 6, 1), date(2026, 8, 31))

    assert 'advertencia_peso_fuera_de_rango' not in metricas
    assert metricas['fecha_ultimo_peso'] is None


def test_metricas_rango_abierto_sin_fecha_fin_no_marca_fuera_de_rango():
    # Solo fecha_inicio dada; el peso es posterior -- sin límite superior no
    # hay "fuera de rango" por el lado derecho.
    fila = _fila_ficha(date(2026, 9, 10))
    repo = SqlAlchemyIndicadoresRepository(db=DbFake([[fila], []]))

    metricas = repo._obtener_metricas(279, date(2026, 6, 1), None)

    assert 'advertencia_peso_fuera_de_rango' not in metricas
