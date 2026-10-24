"""
TC-M04-G014 - Tiempo de respuesta del historial diagnostico de un mes (arnes de datos + ejecucion de k6).

RF relacionado: RF-67 (CU04), RNF-01 y CA-10. Caso: TC-M04-027.

El caso en si esta en test_tc_m04_027_rendimiento_historial.js (k6, misma carpeta). Este archivo prepara el "juego
de datos precargado" que pide la ficha, porque TEST no tiene inferencias de RF-66 y ningun endpoint las genera
(mismo criterio que TC-M04-G010, decision del 2026-10-19):
1. Crea por API un activo biologico propio.
2. Inserta en lote 4300 inferencias de ese activo, una cada 10 minutos durante los ultimos 30 dias, con niveles de
   riesgo 0-3, dos patologias base y una de cada 100 correlacionada con una alerta existente (la tabla de alertas es
   inmutable, no se crean alertas nuevas).
3. Ejecuta k6 con -e ID_ACTIVO/ID_PATOLOGIA/ESPERADO y lee su resumen (--summary-export).
4. Borra lo sembrado y los eventos que el historial materializo al consultarse.

Si k6 no esta en el PATH el test queda en SKIP (los datos igual se siembran y se borran).
Carga: ~5 consultas/s durante 1 min mas un recorrido completo; coordinar el horario con el equipo.

Requisitos: k6 en el PATH y acceso de red a TEST (API y Postgres 5448).
Variables opcionales: BASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo4/RF-67/TC-M04-G014 -v -s \
        --html=reporte-TC-M04-G014.html --self-contained-html
"""
from __future__ import annotations

import json
import os
import random
import shutil
import string
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
TIMEOUT = 60
TOTAL = 4300
DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)
_SCRIPT = Path(__file__).parent / "test_tc_m04_027_rendimiento_historial.js"


def _crear(s, ruta, cuerpo, campo):
    r = s.post(f"{BASE_URL}{ruta}", json=cuerpo, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion {ruta}: HTTP {r.status_code} {r.text}"
    return r.json()[campo]


@pytest.fixture(scope="module")
def sembrado():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": "admin@pecuaria.co", "contrasena": "Test1234!"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Login Administrador: HTTP {r.status_code} {r.text}"
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    suf = "".join(random.choice(string.ascii_lowercase) for _ in range(8))
    finca = _crear(s, "/configuracion/fincas", {
        "nombre": f"Finca Rendimiento Historial {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(s, "/configuracion/especies", {
        "nombre": f"Porcinos Rendimiento Historial {suf}", "descripcion": "Especie de prueba TC-M04-G014",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    area = _crear(s, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Corral Rendimiento {suf}", "tipo_area": "Corral", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")
    activo = _crear(s, "/activos-biologicos", {
        "tipo_activo": "INDIVIDUAL", "id_especie": especie, "fecha_inicio_ciclo": "2026-09-01",
        "origen_financiero": "nacimiento", "id_infraestructura": area, "identificador": f"CERDO-{suf}",
        "raza": "Landrace", "sexo": "Macho", "fecha_nacimiento": "2026-05-01T00:00:00", "peso_inicial": "30.0",
        "detalles_procedencia": "Activo de prueba TC-M04-G014"}, "id_activo_biologico")
    base = s.get(f"{BASE_URL}/prediccion/patologias?solo_base=true", timeout=TIMEOUT).json()["items"]
    patologias = [p["id_patologia"] for p in base[:2]]
    assert len(patologias) == 2, "Se necesitan 2 patologias base"

    ahora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    con = psycopg2.connect(**DB)
    ids: list[str] = []
    try:
        with con.cursor() as cur:
            cur.execute("SELECT min(id_version_modelo) FROM modulo4.versiones_modelos")
            version = cur.fetchone()[0]
            cur.execute("SELECT min(id_alerta_patologica) FROM modulo4.alertas_patologicas")
            alerta = cur.fetchone()[0]
            assert version is not None and alerta is not None, "Faltan una version de modelo o una alerta existente"
            filas = []
            for i in range(TOTAL):
                id_ri = str(uuid.uuid4())
                ids.append(id_ri)
                fecha = ahora - timedelta(minutes=10 * (i + 1))
                con_alerta = i % 100 == 0
                filas.append((id_ri, activo, especie, version, i % 4, json.dumps({str(i % 4): 0.7}),
                              patologias[i % 2] if i % 3 else None, "{}", 0.8, fecha, con_alerta, alerta if con_alerta else None))
            psycopg2.extras.execute_values(cur, """
                INSERT INTO modulo4.resultados_inferencia
                  (id_resultado_inferencia, id_activo_biologico, id_especie, tipo_modelo, id_version_modelo, nivel_riesgo,
                   probabilidad_riesgo, id_patologia, probabilidad_enfermedad, confianza_global, modo_ejecucion,
                   fecha_inferencia, tiene_alerta_generada, id_alerta_generada)
                VALUES %s""", filas,
                template="(%s, %s, %s, 'MODELO_PORCINOS', %s, %s, %s, %s, %s, %s, 'SERVIDOR', %s, %s, %s)", page_size=500)
        con.commit()
        yield {"id_activo": activo, "id_patologia": patologias[0]}
    finally:
        con.rollback()
        with con.cursor() as cur:
            cur.execute("DELETE FROM modulo4.historial_diagnostico_eventos WHERE id_resultado_inferencia = ANY(%s::uuid[])", (ids,))
            cur.execute("DELETE FROM modulo4.resultados_inferencia WHERE id_resultado_inferencia = ANY(%s::uuid[])", (ids,))
        con.commit()
        con.close()


@pytest.fixture(scope="module")
def resumen(sembrado, tmp_path_factory):
    k6 = shutil.which("k6")
    if k6 is None:
        pytest.skip("k6 no esta instalado en el PATH")
    salida = tmp_path_factory.mktemp("g014") / "resumen.json"
    proceso = subprocess.run(
        [k6, "run", "--summary-export", str(salida), "-e", f"BASE_URL={BASE_URL}", "-e", f"ID_ACTIVO={sembrado['id_activo']}",
         "-e", f"ID_PATOLOGIA={sembrado['id_patologia']}", "-e", f"ESPERADO={TOTAL}", str(_SCRIPT)],
        capture_output=True, text=True, encoding="utf-8")
    print(proceso.stdout[-4000:])
    assert salida.exists(), f"k6 no genero el resumen:\n{proceso.stderr[-2000:]}"
    return json.loads(salida.read_text(encoding="utf-8"))["metrics"]


@pytest.mark.parametrize("consulta", ["sin_filtros", "riesgo", "patologia", "alertas", "recorrido"])
def test_tc_m04_027_p95_menor_a_1_5_segundos(resumen, consulta):
    metrica = resumen.get(f"http_req_duration{{consulta:{consulta}}}")
    assert metrica, f"Sin mediciones para la consulta {consulta}"
    p95 = metrica["p(95)"]
    assert p95 < 1500, f"p95 de la consulta {consulta}: {p95:.0f} ms (umbral 1500 ms)"


def test_tc_m04_027_sin_perdida_de_integridad_ni_de_orden(resumen):
    errores = resumen.get("tc_m04_027_errores_integridad", {}).get("count", 0)
    assert errores == 0, f"{errores} problemas de integridad (orden, duplicados o conteo) al recorrer el mes"
