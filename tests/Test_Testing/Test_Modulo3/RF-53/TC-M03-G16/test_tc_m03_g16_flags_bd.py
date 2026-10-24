"""
TC-M03-G16 - Marcado de metadata de calidad sin rechazo del dato (verificacion en BD).

RF relacionado: RF-53 (CU01). Casos: TC-M03-012 (E4), TC-M03-034 (E13),
TC-M03-068 (E17) y TC-M03-069 (E14).

Criterio de la ficha: el dato se persiste con normalidad y queda marcado en su
metadata de calidad: latencia_alta (012), frecuencia_anomala (034), posible_drift
(068) y calidad de senal registrada (069).

Como se verifica (Postman + BD):
1. Se ejecuta con Newman TC-M03-G16.postman_collection.json (misma carpeta), que
   crea sus datos, envia las lecturas, comprueba que ninguna se rechaza y exporta
   los id_telemetria en el environment (g16_*).
2. Se leen esas filas en modulo3.telemetrias de la BD de TEST (solo lectura,
   usuario QA; la tabla no tiene RLS) y se verifican los flags, que la API no
   expone.

Requisitos: newman en el PATH y acceso de red a TEST (API y Postgres 5448).
Variables opcionales: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.
BROKER_TOKEN: token de servicio del broker de TEST (DEV-06), sin el cual /iot/* responde 401.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-53/TC-M03-G16 -v \
        --html=reporte-TC-M03-G16.html --self-contained-html
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

DB_HOST = os.getenv("DB_HOST", "158.69.200.27")
DB_PORT = os.getenv("DB_PORT", "5448")
DB_USER = os.getenv("DB_USER", "member_qa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "qaSGP2026")
DB_NAME = os.getenv("DB_NAME", "sgpmp_test")

_COLECCION = Path(__file__).parent / "TC-M03-G16.postman_collection.json"


@pytest.fixture(scope="module")
def ids(tmp_path_factory) -> dict:
    """Ejecuta la coleccion y devuelve los id_telemetria exportados por caso."""
    newman = shutil.which("newman")
    if newman is None:
        pytest.skip("newman no esta instalado en el PATH")
    salida = tmp_path_factory.mktemp("g16") / "environment.json"
    proceso = subprocess.run(
        # DEV-06: /iot/* exige el token de servicio del broker; se toma de BROKER_TOKEN y no se versiona.
        [newman, "run", str(_COLECCION), "--export-environment", str(salida), "-r", "cli",
         "--env-var", f"broker_token={os.getenv('BROKER_TOKEN', '')}"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if not salida.exists():
        pytest.fail(f"Newman no exporto el environment:\n{proceso.stdout[-3000:]}\n{proceso.stderr[-2000:]}")
    env = {v["key"]: v["value"] for v in json.loads(salida.read_text(encoding="utf-8"))["values"]}

    def uno(clave):
        return int(env[clave]) if env.get(clave, "").isdigit() else None

    def lista(clave):
        return [int(x) for x in json.loads(env.get(clave) or "[]") if x]

    resultado = {
        "012a": uno("g16_tel_012a"),
        "012b": uno("g16_tel_012b"),
        "034": lista("g16_tel_034"),
        "068": lista("g16_tel_068"),
        "069": uno("g16_tel_069"),
    }
    if not any(resultado.values()):
        pytest.fail(f"La coleccion no persistio ninguna lectura; salida de Newman:\n{proceso.stdout[-3000:]}")
    return resultado


@pytest.fixture(scope="module")
def filas(ids) -> dict[int, dict]:
    todos = [i for v in ids.values() for i in (v if isinstance(v, list) else [v]) if i]
    conexion = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME)
    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id_telemetria, estado_calidad::text AS estado_calidad, valor_crudo, latencia_alta,
                       frecuencia_anomala, posible_drift, calidad_senal_rssi, calidad_senal_snr, metadatos
                FROM modulo3.telemetrias
                WHERE id_telemetria = ANY(%s)
                """,
                (todos,),
            )
            return {f["id_telemetria"]: f for f in cur.fetchall()}
    finally:
        conexion.close()


def _fila(filas, id_telemetria, caso):
    if id_telemetria is None:
        pytest.fail(f"{caso}: la coleccion no persistio la lectura (ver reporte de Newman)")
    assert id_telemetria in filas, f"{caso}: id_telemetria {id_telemetria} no esta en modulo3.telemetrias"
    return filas[id_telemetria]


@pytest.mark.parametrize("variante", ["012a", "012b"])
def test_tc_m03_012_latencia_alta_marcada_sin_rechazo(variante, ids, filas):
    fila = _fila(filas, ids[variante], f"TC-M03-{variante}")
    assert fila["estado_calidad"] == "LECTURA_VALIDA"
    assert fila["latencia_alta"] is True, (
        f"TC-M03-{variante}: latencia_alta={fila['latencia_alta']} para un dato capturado hace 3 h "
        f"(metadatos={fila['metadatos']})"
    )


def test_tc_m03_034_frecuencia_anomala_marcada_sin_rechazo(ids, filas):
    # La primera lectura no tiene una anterior con la cual comparar; desde la segunda el intervalo
    # (1 min) no corresponde a la frecuencia configurada (10 min).
    lecturas = ids["034"]
    assert len(lecturas) == 5, f"TC-M03-034: se esperaban 5 lecturas persistidas, hay {len(lecturas)}"
    sin_marca = [i for i in lecturas[1:] if _fila(filas, i, "TC-M03-034")["frecuencia_anomala"] is not True]
    assert not sin_marca, f"TC-M03-034: lecturas sin frecuencia_anomala=true: {sin_marca}"
    assert all(_fila(filas, i, "TC-M03-034")["estado_calidad"] == "LECTURA_VALIDA" for i in lecturas)


def test_tc_m03_068_posible_drift_marcado_sin_rechazo(ids, filas):
    lecturas = ids["068"]
    assert len(lecturas) == 10, f"TC-M03-068: se esperaban 10 lecturas persistidas, hay {len(lecturas)}"
    ultima = _fila(filas, lecturas[-1], "TC-M03-068")
    assert ultima["estado_calidad"] == "LECTURA_VALIDA"
    assert ultima["posible_drift"] is True, (
        f"TC-M03-068: posible_drift={ultima['posible_drift']} tras 10 lecturas con +3 °C de sesgo"
    )


def test_tc_m03_069_calidad_senal_registrada_sin_afectar_el_dato(ids, filas):
    fila = _fila(filas, ids["069"], "TC-M03-069")
    assert fila["estado_calidad"] == "LECTURA_VALIDA"
    assert fila["valor_crudo"] == Decimal("25.0")
    assert fila["calidad_senal_rssi"] == Decimal("-120")
    assert fila["calidad_senal_snr"] == Decimal("-20")
