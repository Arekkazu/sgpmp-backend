# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: ventana de lecturas del activo, contra PostgreSQL real    |
"""``VentanaInferenciaM02Adapter`` contra PostgreSQL real (como usuario de servicio, bajo RLS).

Un activo con dos sensores ``directa`` (temperatura y cardiaca) y uno ``ambiental``: la ventana
trae solo las lecturas de los directos, de las variables de ET-02, dentro de las 2 h previas al
paquete y con el nombre de ET-02. Un sensor sin activo queda sin ventana.
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

    def lectura(sensor, variable, minutos_antes, valor, apto=True):
        db.execute(text(
            "INSERT INTO modulo3.telemetrias (id_sensor, id_variable, id_dispositivo_iot, valor_crudo, "
            "timestamp_captura, timestamp_procesamiento, origen, estado_calidad, metadatos, "
            "categoria_variable, unidad_medida, apto_para_ia) VALUES (:s, :v, 1, :valor, :ts, :ts, "
            "'TIEMPO_REAL', 'LECTURA_VALIDA', '{}', 'ANIMAL', 'x', :apto)"),
            {"s": sensor, "v": variable, "valor": valor, "ts": AHORA - timedelta(minutes=minutos_antes),
             "apto": apto})

    lectura(s_temp, TEMP, 5, 39.1)
    lectura(s_fc, FC, 10, 72, apto=False)
    lectura(s_temp, TEMP, 150, 38.4)        # fuera de la ventana de 2 h
    lectura(s_temp, TEMP, -5, 39.5)         # posterior al paquete
    lectura(s_amb, HUMEDAD, 5, 60.0)        # sensor ambiental: no es del animal
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
    assert (ventanas[3].id_activo_biologico, ventanas[3].lecturas) == (None, [])


def test_lote_vacio(db_session):
    assert VentanaInferenciaM02Adapter(db_session).ventanas([]) == {}
