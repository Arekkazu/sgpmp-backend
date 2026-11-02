# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: ventana de lecturas del activo, contra PostgreSQL real    |
# | 2026-10-31 | Arekkazu | RF-17/RF-66 C3: rangos RF-17 de la especie del activo            |
# | 2026-11-02 | Arekkazu | RF-62/RF-66: apto_para_ia de la evaluación VIGENTE de RF-62      |
"""``VentanaInferenciaM02Adapter`` contra PostgreSQL real (como usuario de servicio, bajo RLS).

Un activo con dos sensores ``directa`` (temperatura y cardiaca) y uno ``ambiental``: la ventana
trae solo las lecturas de los directos, de las variables de ET-02, dentro de las 2 h previas al
paquete y con el nombre de ET-02. Un sensor sin activo queda sin ventana. La ventana lleva las
bandas RF-17 (sano = tramo normal, plausible = valor_min–valor_max) de la especie del activo.
``apto_para_ia`` es el de la evaluación VIGENTE de RF-62, no la columna de ``telemetrias``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from src.shared.database import declarar_identidad_sistema
from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.infrastructure.adapters.ventana_inferencia_m02_adapter import VentanaInferenciaM02Adapter
from tests.integration.test_control_acceso_f4_aislamiento import _finca_con_activo

pytestmark = pytest.mark.integration

AHORA = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
TEMP, FC, HUMEDAD = 13, 14, 10  # modulo9.variables_ambientales (codigo_telemetria TEMP_CORPORAL, ...)


def _paquete(id_paquete: int, sensor: int, fecha=AHORA) -> PaqueteInferencia:
    return PaqueteInferencia(id_sensor=sensor, id_dispositivo_iot=1, id_evento_edge_computing=1,
                             tipo_variable="TEMP_CORPORAL", valor_numerico=Decimal("39.9"),
                             estado_calidad="VALIDO", fecha_envio=fecha, estado_paquete="PENDIENTE",
                             intento_envios=0, contexto_incompleto=False, id_paquetes_inferencia=id_paquete)


@pytest.fixture
def escenario(db_session, crear_usuario_db):
    db = db_session
    usuario = crear_usuario_db(id_rol=3)
    db.execute(text("SET LOCAL session_replication_role = replica"))
    _, _, activo = _finca_con_activo(db, usuario["id_usuario"])
    base = uuid.uuid4().int % 10**6 * 10
    s_temp, s_fc, s_amb, s_suelto = base + 1, base + 2, base + 3, base + 4

    def asociar(sensor, tipo, inicio=AHORA - timedelta(days=30)):
        db.execute(text(
            "INSERT INTO modulo2.asociaciones_activos_sensores (id_sensor, id_usuario, fecha_inicio, "
            "id_activo_biologico, tipo) VALUES (:s, :u, :i, :a, CAST(:t AS modulo2.enum_asociaciones_activos_sensores_tipo))"),
            {"s": sensor, "u": usuario["id_usuario"], "i": inicio, "a": activo, "t": tipo})

    asociar(s_temp, "directa")
    asociar(s_fc, "directa")
    asociar(s_amb, "ambiental")

    def evaluacion(id_telemetria, sensor, apto, estado="VIGENTE"):
        db.execute(text(
            "INSERT INTO modulo3.telemetria_calidad (id_telemetria, id_sensor, clasificacion_calidad, "
            "apto_para_ia, estado_evaluacion) VALUES (:t, :s, :c, :apto, :e)"),
            {"t": id_telemetria, "s": sensor, "c": "APTO" if apto else "NO_APTO", "apto": apto, "e": estado})

    def lectura(sensor, variable, minutos_antes, valor, apto=True):
        """Lectura con la columna apto_para_ia en su default (RF-62 no la toca) y su evaluación RF-62."""
        id_telemetria = db.execute(text(
            "INSERT INTO modulo3.telemetrias (id_sensor, id_variable, id_dispositivo_iot, valor_crudo, "
            "timestamp_captura, timestamp_procesamiento, origen, estado_calidad, metadatos, "
            "categoria_variable, unidad_medida) VALUES (:s, :v, 1, :valor, :ts, :ts, "
            "'TIEMPO_REAL', 'LECTURA_VALIDA', '{}', 'ANIMAL', 'x') RETURNING id_telemetria"),
            {"s": sensor, "v": variable, "valor": valor, "ts": AHORA - timedelta(minutes=minutos_antes)}).scalar_one()
        evaluacion(id_telemetria, sensor, apto)
        return id_telemetria

    lectura(s_temp, TEMP, 5, 39.1)
    # La evaluación superada (apta) no cuenta: vale la VIGENTE (no apta).
    evaluacion(lectura(s_fc, FC, 10, 72, apto=False), s_fc, True, estado="SUPERADA")
    lectura(s_temp, TEMP, 150, 38.4)        # fuera de la ventana de 2 h
    lectura(s_temp, TEMP, -5, 39.5)         # posterior al paquete
    lectura(s_amb, HUMEDAD, 5, 60.0)        # sensor ambiental: no es del animal

    # Umbral RF-17 de temperatura corporal para la especie del activo (C3 de ET-02).
    umbral = db.execute(text(
        "INSERT INTO modulo9.umbrales_ambientales (id_especie, id_variable_ambiental, unidad_medida, "
        "valor_min, valor_max, es_activo, fecha_actualizacion) SELECT id_especie, :v, '°C', 35.5, 42.5, true, now() "
        "FROM modulo2.activos_biologicos WHERE id_activo_biologico = :a RETURNING id_umbral_ambiental"),
        {"v": TEMP, "a": activo}).scalar_one()
    for nivel, inf, sup in (("normal", 38.0, 39.5), ("precaucion", 39.5, 40.5), ("critico", 40.5, 42.5)):
        db.execute(text(
            "INSERT INTO modulo9.niveles_alerta_ambientales (id_umbral_ambiental, nivel, limite_inferior, "
            "limite_superior) VALUES (:u, CAST(:n AS modulo9.enum_nivel_alerta), :i, :s)"),
            {"u": umbral, "n": nivel, "i": inf, "s": sup})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    declarar_identidad_sistema(db)
    return dict(activo=activo, s_temp=s_temp, s_fc=s_fc, s_suelto=s_suelto)


def test_ventana_del_activo_con_las_lecturas_de_et02(db_session, escenario):
    ventanas = VentanaInferenciaM02Adapter(db_session).ventanas([
        _paquete(1, escenario["s_temp"], AHORA - timedelta(minutes=1)),
        _paquete(2, escenario["s_fc"]),
        _paquete(3, escenario["s_suelto"]),
    ])
    assert ventanas[1].id_activo_biologico == ventanas[2].id_activo_biologico == escenario["activo"]
    # Las dos ventanas del mismo activo son la misma, anclada en su paquete más reciente.
    assert ventanas[1].lecturas == ventanas[2].lecturas
    assert [(lec["variable"], lec["valor"], lec["apto_para_ia"]) for lec in ventanas[2].lecturas] == [
        ("frecuencia_cardiaca", 72.0, False),
        ("temperatura_corporal", 39.1, True),
    ]
    assert ventanas[2].rangos_especie["temperatura_corporal"] == {"sano": [38.0, 39.5], "plausible": [35.5, 42.5]}
    assert "actividad_indice" not in ventanas[2].rangos_especie
    assert (ventanas[3].id_activo_biologico, ventanas[3].lecturas, ventanas[3].rangos_especie) == (None, [], {})


def test_lote_vacio(db_session):
    assert VentanaInferenciaM02Adapter(db_session).ventanas([]) == {}
