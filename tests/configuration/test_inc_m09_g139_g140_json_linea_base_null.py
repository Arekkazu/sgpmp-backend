"""#548 (G139) / #549 (G140): una calibración VISION sin línea base debe guardar
`json_linea_base` como SQL NULL, no como 'null'::jsonb, para cumplir
ck_calibracion_vision_resultado_coherente en FALLIDA y NO_CONVERGIDA."""
from sqlalchemy.dialects.postgresql import psycopg2

from src.configuration.infrastructure.models.calibracion_vision_model import CalibracionVisionModel


def test_json_linea_base_none_se_envia_como_sql_null():
    tipo = CalibracionVisionModel.__table__.c.json_linea_base.type
    procesar = tipo.bind_processor(psycopg2.dialect())
    assert procesar(None) is None
    assert procesar({"a": 1}) == '{"a": 1}'
