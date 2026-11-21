"""La normalización por fila pertenece a PostgreSQL, no a un segundo pipeline."""
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.repositories.ingesta_telemetria_port import (
    IngestaTelemetriaPort, ResultadoPersistenciaIngesta,
)

_INGESTA = text("""
SELECT * FROM modulo3.fn_ingesta_telemetria(
    :device_id, :sensor_id, :id_variable, :valor, :unidad,
    :timestamp_captura, :timestamp_envio,
    CAST(:origen AS modulo3.enum_telemetria_origen),
    CAST(:categoria AS modulo3.enum_telemetria_categoria_variable),
    CAST(:tipo_dato AS modulo3.enum_telemetria_tipo_dato),
    :valor_agregado, :ventana_agregacion, :latitud, :longitud,
    :nivel_bateria, :calidad_senal_rssi, :calidad_senal_snr,
    :estado_conectividad, CAST(:metadatos AS jsonb))
""")


class SqlAlchemyIngestaTelemetriaRepository(IngestaTelemetriaPort):
    def __init__(self, db: Session):
        self.db = db

    def ingerir(self, parametros):
        valores = dict(parametros, metadatos=json.dumps(parametros['metadatos']))
        try:
            fila = self.db.execute(_INGESTA, valores).mappings().one()
            tiempos = {}
            if fila['id_telemetria'] is not None:
                tiempos = self.db.execute(text("""
                    SELECT timestamp_procesamiento, latencia_procesamiento_ms
                    FROM modulo3.telemetrias WHERE id_telemetria=:id
                """), {'id': fila['id_telemetria']}).mappings().one()
            return ResultadoPersistenciaIngesta(**fila, **tiempos)
        except Exception as exc:
            raise_from_db_error(exc)
