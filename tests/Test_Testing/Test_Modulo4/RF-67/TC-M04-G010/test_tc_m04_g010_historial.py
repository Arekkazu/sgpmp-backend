# | Fecha      | Nombre     | Que se hizo                                                                      |
# |------------|------------|----------------------------------------------------------------------------------|
# | 2026-10-26 | HulkyZeus  | TC-M04-G010 RF-67: siembra unica e idempotente, sin borrar (historial inmutable)  |
"""
TC-M04-G010 - Consulta del historial diagnostico con y sin filtros (arnes de datos + ejecucion de la coleccion).

RF relacionado: RF-67 (CU04). Casos: TC-M04-017 y TC-M04-018 (CA-3 y CA-4).

El caso en si esta en TC-M04-G010.postman_collection.json (misma carpeta). Este archivo existe porque la
precondicion de la ficha ("activo con inferencias previas generadas por RF-66") no se puede preparar por API:
en TEST modulo4.resultados_inferencia esta vacia y ningun endpoint del backend escribe en ella (el motor de
RF-66 es externo). Decision del 2026-10-19: sembrar datos de prueba propios.

Que hace:
1. Crea por API un activo biologico propio (finca, especie, area y activo individual).
2. Inserta en la BD de TEST 6 inferencias SOLO para ese activo (una sola vez) (usuario QA, que tiene INSERT/DELETE y sin RLS),
   con niveles de riesgo, patologias y fechas conocidos. Una de ellas se correlaciona con una alerta de RF-57
   que ya existe: modulo4.alertas_patologicas es inmutable (trigger que bloquea UPDATE/DELETE), asi que crear
   una alerta nueva la dejaria para siempre en el TEST compartido.
3. Ejecuta la coleccion con Newman pasando el activo y los conteos esperados por --env-var.
4. NO borra nada: modulo4.historial_diagnostico_eventos es inmutable (RF-67, INC-M04-145: triggers que
   bloquean UPDATE/DELETE) y la API materializa ahi un evento por inferencia consultada. La siembra es por eso
   unica e idempotente: las inferencias llevan ids deterministas (uuid5) y fechas fijas del pasado, asi que la
   primera corrida crea el activo y las inserta, y las siguientes reutilizan el mismo activo y los mismos datos
   (los eventos del historial tienen id estable, INC-M04-146, y no se duplican). Las expectativas se calculan
   leyendo lo sembrado. Un fallo a medias se completa en la siguiente corrida.

Requisitos: newman en el PATH y acceso de red a TEST (API y Postgres 5448).
Variables opcionales: BASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo4/RF-67/TC-M04-G010 -v \
        --html=reporte-TC-M04-G010.html --self-contained-html
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
TIMEOUT = 30
DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)
_COLECCION = Path(__file__).parent / "TC-M04-G010.postman_collection.json"


def _sufijo() -> str:
    return "".join(random.choice(string.ascii_lowercase) for _ in range(8))


def _crear(s, ruta, cuerpo, campo):
    r = s.post(f"{BASE_URL}{ruta}", json=cuerpo, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion {ruta}: HTTP {r.status_code} {r.text}"
    return r.json()[campo]


# Ids deterministas y fechas fijas (pasadas): la misma siembra en cada corrida. El historial rechaza fecha_fin futura.
NAMESPACE_SIEMBRA = uuid.UUID("5b0c1a64-7d0e-4a57-9c1d-0f6f6a2f1010")
ANCLA = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
# (dias antes del ancla, nivel_riesgo, indice de patologia base o None, con_alerta)
PLAN = [(1, 3, 0, True), (2, 1, 1, False), (4, 3, 1, False), (6, 2, 0, False), (9, 0, None, False), (12, 3, 0, False)]


def _sesion() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": "admin@pecuaria.co", "contrasena": "Test1234!"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Login Administrador: HTTP {r.status_code} {r.text}"
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


def _crear_activo(s) -> dict:
    suf = _sufijo()
    finca = _crear(s, "/configuracion/fincas", {
        "nombre": f"Finca Historial Diagnostico {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(s, "/configuracion/especies", {
        "nombre": f"Porcinos Historial {suf}", "descripcion": "Especie de prueba TC-M04-G010",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    area = _crear(s, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Corral Historial {suf}", "tipo_area": "Corral", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")
    id_activo = _crear(s, "/activos-biologicos", {
        "tipo_activo": "INDIVIDUAL", "id_especie": especie, "fecha_inicio_ciclo": "2026-09-01",
        "origen_financiero": "nacimiento", "id_infraestructura": area, "identificador": f"CERDO-{suf}",
        "raza": "Landrace", "sexo": "Macho", "fecha_nacimiento": "2026-05-01T00:00:00", "peso_inicial": "30.0",
        "detalles_procedencia": "Activo de prueba TC-M04-G010"}, "id_activo_biologico")
    return {"id": id_activo, "especie": especie}


def _patologias_base(s) -> list[int]:
    base = s.get(f"{BASE_URL}/prediccion/patologias?solo_base=true", timeout=TIMEOUT)
    assert base.status_code == 200 and len(base.json()["items"]) >= 2, f"Se necesitan 2 patologias base: {base.text[:200]}"
    return [p["id_patologia"] for p in base.json()["items"][:2]]


_LEER = """
    SELECT id_resultado_inferencia::text AS id, id_activo_biologico, id_especie, fecha_inferencia, nivel_riesgo,
           id_patologia, tiene_alerta_generada, id_alerta_generada
    FROM modulo4.resultados_inferencia WHERE id_resultado_inferencia = ANY(%s::uuid[]) ORDER BY fecha_inferencia DESC
"""


@pytest.fixture(scope="module")
def sembrado():
    """Siembra (una sola vez) las 6 inferencias del activo y devuelve los parametros de la coleccion."""
    ids = [str(uuid.uuid5(NAMESPACE_SIEMBRA, f"inferencia-{i}")) for i in range(len(PLAN))]
    con = psycopg2.connect(**DB)
    try:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(_LEER, (ids,))
            filas = cur.fetchall()
            if len(filas) < len(ids):  # primera corrida (o una a medias): se completa lo que falte
                s = _sesion()
                activo = {"id": filas[0]["id_activo_biologico"], "especie": filas[0]["id_especie"]} if filas else _crear_activo(s)
                patologias = _patologias_base(s)
                cur.execute("SELECT min(id_version_modelo) AS v FROM modulo4.versiones_modelos")
                version = cur.fetchone()["v"]
                cur.execute("SELECT min(id_alerta_patologica) AS a FROM modulo4.alertas_patologicas")
                alerta = cur.fetchone()["a"]
                assert version is not None, "No hay ninguna version de modelo en TEST para referenciar"
                assert alerta is not None, "No hay ninguna alerta de RF-57 existente para correlacionar"
                for id_ri, (dias, riesgo, idx_pat, con_alerta) in zip(ids, PLAN):
                    patologia = patologias[idx_pat] if idx_pat is not None else None
                    fecha = ANCLA - timedelta(days=dias)
                    cur.execute(
                        """
                        INSERT INTO modulo4.resultados_inferencia
                          (id_resultado_inferencia, id_activo_biologico, id_especie, tipo_modelo, id_version_modelo,
                           nivel_riesgo, probabilidad_riesgo, id_patologia, probabilidad_enfermedad, confianza_global,
                           modo_ejecucion, latencia_ms, fecha_inicio_ventana, fecha_fin_ventana, fecha_inferencia,
                           tiene_alerta_generada, id_alerta_generada)
                        VALUES (%s, %s, %s, 'MODELO_PORCINOS', %s, %s, %s, %s, %s, 0.85, 'SERVIDOR', 120,
                                %s, %s, %s, %s, %s)
                        ON CONFLICT (id_resultado_inferencia) DO NOTHING
                        """,
                        (id_ri, activo["id"], activo["especie"], version, riesgo,
                         json.dumps({str(n): round(0.1 + 0.2 * (n == riesgo), 2) for n in range(4)}), patologia,
                         json.dumps({str(patologia): 0.7} if patologia else {}),
                         fecha - timedelta(hours=1), fecha, fecha, con_alerta, alerta if con_alerta else None),
                    )
                con.commit()
                cur.execute(_LEER, (ids,))
                filas = cur.fetchall()
        assert len(filas) == len(ids), f"Siembra incompleta: {len(filas)} de {len(ids)} inferencias"
    finally:
        con.close()

    # Las expectativas salen de lo sembrado (no de constantes): la fuente de verdad es la BD.
    primera = next(f for f in filas if f["id"] == ids[0])           # la que lleva alerta y patologia A
    pat_a = primera["id_patologia"]
    en_rango = [f for f in filas if 3 <= (ANCLA - f["fecha_inferencia"]).days <= 7]
    return {
        "id_activo": primera["id_activo_biologico"],
        "desde": str((ANCLA - timedelta(days=30)).date()),
        "hasta": str(datetime.now(timezone.utc).date()),  # el historial rechaza fecha_fin futura (FECHA_FIN_FUTURA)
        "rango_desde": str((ANCLA - timedelta(days=7)).date()),
        "rango_hasta": str((ANCLA - timedelta(days=3)).date()),
        "esperado_total": len(filas),
        "esperado_rango": len(en_rango),
        "esperado_riesgo3": sum(1 for f in filas if f["nivel_riesgo"] == 3),
        "id_patologia_a": pat_a,
        "esperado_patologia_a": sum(1 for f in filas if f["id_patologia"] == pat_a),
        "id_resultado_con_alerta": ids[0],
        "id_alerta": primera["id_alerta_generada"],
    }


@pytest.fixture(scope="module")
def corrida(sembrado, tmp_path_factory):
    newman = shutil.which("newman")
    if newman is None:
        pytest.skip("newman no esta instalado en el PATH")
    reporte = tmp_path_factory.mktemp("g010") / "newman.json"
    html = Path(__file__).parent / "Resultados" / "reporte-TC-M04-G010.html"
    comando = [newman, "run", str(_COLECCION), "-r", "cli,json,htmlextra", "--reporter-json-export", str(reporte),
               "--reporter-htmlextra-export", str(html), "--reporter-htmlextra-skipHeaders", "Authorization",
               "--reporter-htmlextra-title", "TC-M04-G010 Consulta del historial diagnóstico con y sin filtros"]
    for clave, valor in sembrado.items():
        comando += ["--env-var", f"{clave}={valor}"]
    proceso = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8")
    assert reporte.exists(), f"Newman no genero el reporte:\n{proceso.stdout[-3000:]}\n{proceso.stderr[-2000:]}"
    return json.loads(reporte.read_text(encoding="utf-8"))["run"]


def _fallas(corrida, prefijo: str) -> list[str]:
    fallas = []
    for ejecucion in corrida["executions"]:
        for a in ejecucion.get("assertions", []):
            if a["assertion"].startswith(prefijo) and a.get("error"):
                fallas.append(f"{a['assertion']} -> {a['error']['message']}")
    return fallas


def test_tc_m04_017_historial_sin_filtros(corrida):
    fallas = _fallas(corrida, "TC-M04-017")
    assert not fallas, "\n".join(fallas)


@pytest.mark.parametrize("filtro", ["fechas", "riesgo", "patología", "alertas"])
def test_tc_m04_018_historial_con_filtros(corrida, filtro):
    fallas = _fallas(corrida, f"TC-M04-018 {filtro}")
    assert not fallas, "\n".join(fallas)
