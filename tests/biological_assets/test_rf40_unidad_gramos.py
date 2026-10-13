"""[RF-40] M09 escribe los gramos como "g" y la tabla de crecimiento como "gr"."""
from decimal import Decimal

from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import RegistrarEventoCrecimientoDTO


def test_gramos_de_m09_se_guardan_como_gr() -> None:
    dto = RegistrarEventoCrecimientoDTO(tipo_medicion='PESO', valor_medicion=Decimal('12.5'), unidad_medida='g')
    assert dto.unidad_medida == 'gr'
