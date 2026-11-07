# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-05 | Arekkazu | M06 RF-COT: el UPDATE de cotizaciones rechaza columnas fuera de la lista cerrada |
"""Los nombres de columna de ``actualizar`` se interpolan en el SQL: solo pasan los de la lista cerrada."""
import pytest

from src.financial_valuation.infrastructure.repositories.cotizacion_repository import SqlAlchemyCotizacionRepository


@pytest.mark.parametrize("cambios", [{}, {"id_usuario = 1 --": 1}, {"condiciones": "x", "version": 9}])
def test_actualizar_rechaza_columnas_no_editables(cambios):
    with pytest.raises(ValueError):
        SqlAlchemyCotizacionRepository(db=None).actualizar(1, 1, cambios)
