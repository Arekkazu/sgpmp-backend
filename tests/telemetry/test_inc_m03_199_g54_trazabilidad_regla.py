# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-199-G54 RF-55: contrato de trazabilidad de la regla sin BD |
"""INC-M03-199-G54: el DTO de POST /iot/eventos-edge ya no descarta la regla enviada en el nivel superior."""
import pytest
from pydantic import ValidationError

from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO

BASE = dict(device_id=1, sensor_id=1, serial="S", clasificacion_rf55="DESVIACION_COMPUESTA", variables_involucradas=[],
            timestamp_captura="2026-10-28T00:00:00Z", timestamp_procesamiento_edge="2026-10-28T00:00:01Z",
            estado_conectividad=True)


def test_campos_en_el_nivel_superior_se_conservan_en_metadata_edge():
    dto = RecibirEventoEdgeDTO(**BASE, regla_aplicada="RC-07", nombre_regla="ESTRES_TERMICO", version_regla=3,
                               metadata_edge={"firmware": "1.2"})
    assert dto.metadata_edge == {"firmware": "1.2", "regla_aplicada": "RC-07", "nombre_regla": "ESTRES_TERMICO",
                                 "version_regla": 3}


def test_campos_dentro_de_metadata_edge_tambien_se_exponen():
    dto = RecibirEventoEdgeDTO(**BASE, metadata_edge={"regla_aplicada": 7, "nombre_regla": "X", "version_regla": 2})
    assert (dto.regla_aplicada, dto.nombre_regla, dto.version_regla) == (7, "X", 2)


def test_mismo_valor_en_ambos_lugares_es_valido():
    dto = RecibirEventoEdgeDTO(**BASE, version_regla=2, metadata_edge={"version_regla": 2})
    assert dto.metadata_edge["version_regla"] == 2


@pytest.mark.parametrize("extra", [
    {"version_regla": 2, "metadata_edge": {"version_regla": 3}},
    {"version_regla": 0},
    {"version_regla": "x"},
    {"metadata_edge": {"version_regla": "x"}},
    {"regla_aplicada": "   "},
    {"nombre_regla": ""},
])
def test_valores_incoherentes_o_invalidos_se_rechazan(extra):
    with pytest.raises(ValidationError):
        RecibirEventoEdgeDTO(**BASE, **extra)


def test_sin_campos_no_se_inventa_nada():
    dto = RecibirEventoEdgeDTO(**BASE)
    assert (dto.regla_aplicada, dto.nombre_regla, dto.version_regla, dto.metadata_edge) == (None, None, None, None)
