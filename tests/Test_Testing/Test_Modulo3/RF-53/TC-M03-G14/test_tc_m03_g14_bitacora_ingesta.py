"""
TC-M03-G14 - Registro completo en bitacora de todos los eventos de ingesta.

RF relacionado: RF-53 (CU01), CA-18. Caso: TC-M03-030.

Criterio de la ficha: todo evento de ingesta (exito, rechazo, error) queda en la
bitacora tecnica con al menos fecha y hora, dispositivo, sensor, tipo de evento,
resultado y severidad.

Como se verifica (Postman + Pytest):
1. Se ejecuta con Newman la coleccion TC-M03-G14.postman_collection.json (misma
   carpeta), que crea sus propios datos y envia a POST /iot/telemetria un lote con
   un evento de cada tipo. La coleccion exporta en el environment la hora de
   inicio, los ids de dispositivo/sensor y la hora de cada evento (g14_*).
2. Se consulta la bitacora tecnica real, modulo3.bitacora_ingest, en la BD de TEST
   (solo lectura, usuario QA) y se busca una fila por cada evento enviado.

La bitacora no tiene endpoint de consulta por API (la ficha lo deja "por
confirmar"); por eso esta parte va contra la BD. member_qa tiene SELECT sobre la
tabla y la tabla no tiene RLS.

Mapeo de los campos de la ficha a columnas de modulo3.bitacora_ingest:
    fecha y hora    -> fecha_evento
    dispositivo     -> id_dispositivo_iot
    sensor          -> id_sensor
    tipo de evento  -> tipo_evento (DATOS_PROCESADOS / ERROR_PROCESAMIENTO)
    resultado       -> estado_calidad (LECTURA_VALIDA, ERROR_UNIDAD, ...)
    severidad       -> severidad

Requisitos: newman en el PATH y acceso de red a TEST (API y Postgres 5448).
Variables opcionales: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-53/TC-M03-G14 -v \
        --html=reporte-TC-M03-G14.html --self-contained-html
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

DB_HOST = os.getenv("DB_HOST", "158.69.200.27")
DB_PORT = os.getenv("DB_PORT", "5448")
DB_USER = os.getenv("DB_USER", "member_qa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "qaSGP2026")
DB_NAME = os.getenv("DB_NAME", "sgpmp_test")

_CARPETA = Path(__file__).parent
_COLECCION = _CARPETA / "TC-M03-G14.postman_collection.json"

# evento -> (dispositivo que lo emite, estado_calidad esperado en la bitacora, tipo_evento esperado)
_EVENTOS = {
    "EXITO_VALIDO": ("ok", "LECTURA_VALIDA", "DATOS_PROCESADOS"),
    "EXITO_SIN_CALIBRAR": ("sc", "ERROR_CALIBRACION", "DATOS_PROCESADOS"),
    "RECHAZO_ESTRUCTURA": ("ok", "ERROR_ESTRUCTURA", "ERROR_PROCESAMIENTO"),
    "RECHAZO_AUTENTICACION": ("ok", "ERROR_AUTENTICACION", "ERROR_PROCESAMIENTO"),
    "RECHAZO_UNIDAD": ("ok", "ERROR_UNIDAD", "ERROR_PROCESAMIENTO"),
    "RECHAZO_TIEMPO": ("ok", "ERROR_TIEMPO", "ERROR_PROCESAMIENTO"),
    "RECHAZO_DUPLICADO": ("ok", "ERROR_DUPLICADO", "ERROR_PROCESAMIENTO"),
    "ERROR_SENSOR": ("ok", "ERROR_SENSOR", "ERROR_PROCESAMIENTO"),
}
_CAMPOS_OBLIGATORIOS = ("fecha_evento", "id_dispositivo_iot", "id_sensor", "tipo_evento", "estado_calidad", "severidad")


@pytest.fixture(scope="module")
def entorno_newman(tmp_path_factory) -> dict:
    """Ejecuta la coleccion y devuelve las variables g14_* exportadas."""
    newman = shutil.which("newman")
    if newman is None:
        pytest.skip("newman no esta instalado en el PATH")
    salida = tmp_path_factory.mktemp("g14") / "environment.json"
    proceso = subprocess.run(
        [newman, "run", str(_COLECCION), "--export-environment", str(salida), "-r", "cli"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if not salida.exists():
        pytest.fail(f"Newman no exporto el environment:\n{proceso.stdout[-3000:]}\n{proceso.stderr[-2000:]}")
    valores = {v["key"]: v["value"] for v in json.loads(salida.read_text(encoding="utf-8"))["values"]}
    faltantes = [k for k in ("g14_inicio", "g14_device_ok", "g14_sensor_ok", "g14_device_sc", "g14_sensor_sc") if not valores.get(k)]
    if faltantes:
        pytest.fail(f"La coleccion no pudo preparar los datos ({faltantes}); salida de Newman:\n{proceso.stdout[-3000:]}")
    return valores


@pytest.fixture(scope="module")
def bitacora(entorno_newman) -> list[dict]:
    """Filas de modulo3.bitacora_ingest de los dos dispositivos del caso, desde el inicio de la corrida."""
    conexion = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME)
    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id_bitacora_ingest, fecha_evento, id_dispositivo_iot, id_sensor, tipo_evento,
                       estado_calidad, severidad, descripcion_text
                FROM modulo3.bitacora_ingest
                WHERE id_dispositivo_iot IN (%s, %s) AND fecha_evento >= %s
                ORDER BY fecha_evento
                """,
                (int(entorno_newman["g14_device_ok"]), int(entorno_newman["g14_device_sc"]), entorno_newman["g14_inicio"]),
            )
            return list(cur.fetchall())
    finally:
        conexion.close()


@pytest.mark.parametrize("evento", list(_EVENTOS))
def test_tc_m03_030_cada_evento_queda_en_bitacora(evento, entorno_newman, bitacora):
    disp, estado, tipo = _EVENTOS[evento]
    if not entorno_newman.get(f"g14_evento_{evento}"):
        pytest.fail(f"La coleccion no llego a enviar el evento {evento}")
    device_id = int(entorno_newman[f"g14_device_{disp}"])
    filas = [f for f in bitacora if f["id_dispositivo_iot"] == device_id and f["estado_calidad"] == estado]
    assert filas, (
        f"{evento}: no hay fila en modulo3.bitacora_ingest con id_dispositivo_iot={device_id} y "
        f"estado_calidad={estado}. Filas del dispositivo: "
        f"{[(f['tipo_evento'], f['estado_calidad']) for f in bitacora if f['id_dispositivo_iot'] == device_id]}"
    )
    assert filas[0]["tipo_evento"] == tipo


@pytest.mark.parametrize("evento", list(_EVENTOS))
def test_tc_m03_030_cada_registro_tiene_los_campos_minimos(evento, entorno_newman, bitacora):
    disp, estado, _ = _EVENTOS[evento]
    device_id = int(entorno_newman[f"g14_device_{disp}"])
    sensor_id = int(entorno_newman[f"g14_sensor_{disp}"])
    filas = [f for f in bitacora if f["id_dispositivo_iot"] == device_id and f["estado_calidad"] == estado]
    if not filas:
        pytest.fail(f"{evento}: sin fila en la bitacora (ver test de presencia)")
    fila = filas[0]
    vacios = [c for c in _CAMPOS_OBLIGATORIOS if fila[c] in (None, "")]
    assert not vacios, f"{evento}: campos minimos vacios en la bitacora: {vacios}"
    assert fila["id_sensor"] == sensor_id, f"{evento}: sensor registrado {fila['id_sensor']}, esperado {sensor_id}"
