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
