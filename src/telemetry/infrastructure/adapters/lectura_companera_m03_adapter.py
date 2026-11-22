# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-164-G71 RF-57 E14: busca la variable compañera en telemetrías del área |
"""RF-57 E14: lectura válida de la otra variable requerida de una regla compuesta, en la misma área."""
from sqlalchemy import text

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.repositories.lectura_companera_port import LecturaCompanera, LecturaCompaneraPort

_SQL = text("""
    SELECT t.id_telemetria, t.id_sensor, COALESCE(t.valor_ajustado, t.valor_crudo) AS valor, t.timestamp_captura
    FROM modulo3.telemetrias t
    JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = t.id_dispositivo_iot
    JOIN modulo9.variables_ambientales v ON v.id_variable_ambiental = t.id_variable
    WHERE v.codigo_telemetria = :codigo
      AND t.estado_calidad = 'LECTURA_VALIDA'
      AND (CASE WHEN CAST(:area AS integer) IS NULL THEN d.id_dispositivo_iot = :dispositivo
                ELSE d.id_infraestructura = :area END)
      AND t.timestamp_captura BETWEEN CAST(:momento AS timestamptz) - make_interval(mins => :ventana)
                                  AND CAST(:momento AS timestamptz) + make_interval(mins => :ventana)
    ORDER BY abs(extract(epoch FROM t.timestamp_captura - CAST(:momento AS timestamptz))), t.id_telemetria DESC
    LIMIT 1
""")


class LecturaCompaneraM03Adapter(LecturaCompaneraPort):
    def __init__(self, db):
        self.db = db

    def ultima_lectura_valida(self, tipo_variable, id_infraestructura, id_dispositivo, momento, ventana_min):
        try:
            fila = self.db.execute(_SQL, {"codigo": tipo_variable, "area": id_infraestructura,
                                          "dispositivo": id_dispositivo, "momento": momento,
                                          "ventana": ventana_min}).mappings().first()
        except Exception as exc:
            raise_from_db_error(exc)
        if fila is None:
            return None
        return LecturaCompanera(fila["id_telemetria"], fila["id_sensor"], tipo_variable, fila["valor"],
                                fila["timestamp_captura"])
