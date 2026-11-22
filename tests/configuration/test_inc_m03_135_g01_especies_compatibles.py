# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M03-135-G01 RF-49: especies compatibles de un sensor desde M09 |
"""RF-49 R3 (#849): M09 configura las especies compatibles de un sensor."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.configuration.application.use_cases.sensores.especies_compatibles_sensor_use_case import (
    EspeciesCompatiblesSensorUseCase,
)
from src.shared.errors import NotFoundError, ValidationError


class _Compat:
    def __init__(self):
        self.filas: dict[int, list[int]] = {}

    def listar_especies(self, id_sensor):
        return self.filas.get(id_sensor, [])

    def reemplazar(self, id_sensor, ids):
        self.filas[id_sensor] = ids


def _use_case(*, dispositivo_visible=True):
    sensores = Mock()
    sensores.obtener_por_id.side_effect = lambda i: SimpleNamespace(id_dispositivo_iot=718) if i == 1050 else None
    dispositivos = Mock()
    dispositivos.obtener_por_id.return_value = object() if dispositivo_visible else None
    especies = Mock()
    catalogo = {1: True, 2: True, 3: False}
    especies.obtener_por_id.side_effect = lambda i: (
        SimpleNamespace(id_especie=i, es_activo=catalogo[i], nombre=SimpleNamespace(valor=f"E{i}")) if i in catalogo else None)
    compat = _Compat()
    return EspeciesCompatiblesSensorUseCase(db=Mock(), sensor_repo=sensores, dispositivo_repo=dispositivos,
                                            especie_repo=especies, compatibilidad_repo=compat), compat


def test_reemplaza_la_lista_sin_duplicados():
    use_case, compat = _use_case()
    use_case.reemplazar(1050, [2, 1, 2], None)
    assert compat.filas[1050] == [2, 1]
    assert [e.id_especie for e in use_case.consultar(1050, None)] == [2, 1]


@pytest.mark.parametrize("ids", [[1, 3], [99]])
def test_especie_inactiva_o_inexistente_es_400_sin_escribir(ids):
    use_case, compat = _use_case()
    with pytest.raises(ValidationError) as exc:
        use_case.reemplazar(1050, ids, None)
    assert exc.value.code == "ESPECIE_NO_VALIDA" and not compat.filas


@pytest.mark.parametrize("id_sensor, visible", [(9999, True), (1050, False)])
def test_sensor_inexistente_o_de_otra_finca_es_404(id_sensor, visible):
    use_case, _ = _use_case(dispositivo_visible=visible)
    with pytest.raises(NotFoundError):
        use_case.reemplazar(id_sensor, [1], [5])
