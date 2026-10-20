"""
TC-M04-G010 - Consulta del historial diagnostico con y sin filtros (arnes de datos + ejecucion de la coleccion).

RF relacionado: RF-67 (CU04). Casos: TC-M04-017 y TC-M04-018 (CA-3 y CA-4).

El caso en si esta en TC-M04-G010.postman_collection.json (misma carpeta). Este archivo existe porque la
precondicion de la ficha ("activo con inferencias previas generadas por RF-66") no se puede preparar por API:
en TEST modulo4.resultados_inferencia esta vacia y ningun endpoint del backend escribe en ella (el motor de
RF-66 es externo). Decision del 2026-10-19: sembrar datos de prueba propios.

Que hace:
1. Crea por API un activo biologico propio (finca, especie, area y activo individual).
2. Inserta en la BD de TEST 6 inferencias SOLO para ese activo (usuario QA, que tiene INSERT/DELETE y sin RLS),
   con niveles de riesgo, patologias y fechas conocidos. Una de ellas se correlaciona con una alerta de RF-57
   que ya existe: modulo4.alertas_patologicas es inmutable (trigger que bloquea UPDATE/DELETE), asi que crear
   una alerta nueva la dejaria para siempre en el TEST compartido.
3. Ejecuta la coleccion con Newman pasando el activo y los conteos esperados por --env-var.
4. Borra todo lo sembrado: primero los eventos que el historial materializa en
   modulo4.historial_diagnostico_eventos y luego las inferencias. El activo creado por API queda (como en el
   resto de los casos).

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


@pytest.fixture(scope="module")
def activo() -> dict:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": "admin@pecuaria.co", "contrasena": "Test1234!"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Login Administrador: HTTP {r.status_code} {r.text}"
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
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
    base = s.get(f"{BASE_URL}/prediccion/patologias?solo_base=true", timeout=TIMEOUT)
    assert base.status_code == 200 and len(base.json()["items"]) >= 2, f"Se necesitan 2 patologias base: {base.text[:200]}"
    patologias = [p["id_patologia"] for p in base.json()["items"][:2]]
    return {"id": id_activo, "especie": especie, "patologias": patologias}


@pytest.fixture(scope="module")
def sembrado(activo):
    """Inserta 6 inferencias del activo y las borra al terminar."""
    ahora = datetime.now(timezone.utc).replace(microsecond=0)
    pat_a, pat_b = activo["patologias"]
    # (dias atras, nivel_riesgo, patologia, con_alerta)
    plan = [(1, 3, pat_a, True), (2, 1, pat_b, False), (4, 3, pat_b, False),
            (6, 2, pat_a, False), (9, 0, None, False), (12, 3, pat_a, False)]
    con = psycopg2.connect(**DB)
    ids: list[str] = []
    try:
        with con.cursor() as cur:
            cur.execute("SELECT min(id_version_modelo) FROM modulo4.versiones_modelos")
            version = cur.fetchone()[0]
            cur.execute("SELECT min(id_alerta_patologica) FROM modulo4.alertas_patologicas")
            alerta = cur.fetchone()[0]
            assert version is not None, "No hay ninguna version de modelo en TEST para referenciar"
            assert alerta is not None, "No hay ninguna alerta de RF-57 existente para correlacionar"
            filas = []
            for dias, riesgo, patologia, con_alerta in plan:
                fecha = ahora - timedelta(days=dias)
                id_ri = str(uuid.uuid4())
                ids.append(id_ri)
                cur.execute(
                    """
                    INSERT INTO modulo4.resultados_inferencia
                      (id_resultado_inferencia, id_activo_biologico, id_especie, tipo_modelo, id_version_modelo,
                       nivel_riesgo, probabilidad_riesgo, id_patologia, probabilidad_enfermedad, confianza_global,
                       modo_ejecucion, latencia_ms, fecha_inicio_ventana, fecha_fin_ventana, fecha_inferencia,
                       tiene_alerta_generada, id_alerta_generada)
                    VALUES (%s, %s, %s, 'MODELO_PORCINOS', %s, %s, %s, %s, %s, 0.85, 'SERVIDOR', 120,
                            %s, %s, %s, %s, %s)
                    """,
                    (id_ri, activo["id"], activo["especie"], version, riesgo,
                     json.dumps({str(n): round(0.1 + 0.2 * (n == riesgo), 2) for n in range(4)}), patologia,
                     json.dumps({str(patologia): 0.7} if patologia else {}),
                     fecha - timedelta(hours=1), fecha, fecha, con_alerta, alerta if con_alerta else None),
                )
                filas.append((id_ri, fecha, riesgo, patologia, con_alerta))
        con.commit()
        rango = [f for f in filas if 3 <= (ahora - f[1]).days <= 7]
        yield {
            "id_activo": activo["id"],
            "desde": str((ahora - timedelta(days=30)).date()),
            "hasta": str((ahora + timedelta(days=1)).date()),
            "rango_desde": str((ahora - timedelta(days=7)).date()),
            "rango_hasta": str((ahora - timedelta(days=3)).date()),
            "esperado_total": len(filas),
            "esperado_rango": len(rango),
            "esperado_riesgo3": sum(1 for f in filas if f[2] == 3),
            "id_patologia_a": pat_a,
            "esperado_patologia_a": sum(1 for f in filas if f[3] == pat_a),
            "id_resultado_con_alerta": next(f[0] for f in filas if f[4]),
            "id_alerta": alerta,
        }
    finally:
        con.rollback()
        with con.cursor() as cur:
            cur.execute("DELETE FROM modulo4.historial_diagnostico_eventos WHERE id_resultado_inferencia = ANY(%s::uuid[])", (ids,))
            cur.execute("DELETE FROM modulo4.resultados_inferencia WHERE id_resultado_inferencia = ANY(%s::uuid[])", (ids,))
        con.commit()
        con.close()


@pytest.fixture(scope="module")
def corrida(sembrado, tmp_path_factory):
    newman = shutil.which("newman")
    if newman is None:
        pytest.skip("newman no esta instalado en el PATH")
    reporte = tmp_path_factory.mktemp("g010") / "newman.json"
    comando = [newman, "run", str(_COLECCION), "-r", "cli,json", "--reporter-json-export", str(reporte)]
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
