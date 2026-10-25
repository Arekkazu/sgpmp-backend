"""
TC-M04-G011 - Correlacion, orden determinista y paginacion de eventos del historial diagnostico.

RF relacionado: RF-67 (CU04). Casos: TC-M04-019 (CA-7, RNF-03), TC-M04-020 y TC-M04-021 (CA-8).

Criterios de la ficha:
    TC-M04-019: alerta y retroalimentacion se correlacionan con su inferencia solo por id_inferencia, nunca por
    timestamp: dos inferencias con el mismo timestamp y distinto id no se mezclan.
    TC-M04-020: paginacion por cursor de maximo 50 registros; al recorrer todas las paginas (>150 eventos) no hay
    duplicados ni omisiones. Probar tambien un tamano de pagina >50.
    TC-M04-021: con timestamps identicos el orden es siempre el mismo, desempatado por id_evento descendente, y
    estable al paginar.

Endpoint real: GET /prediccion/historial/{id_activo_biologico} (fecha_inicio, fecha_fin, incluir_alertas,
cursor_paginacion). Se usa pytest con llamadas HTTP directas (en lugar de una coleccion) porque recorrer cientos de
eventos pagina a pagina y comparar recorridos repetidos es mas claro y confiable asi.

Datos (mismo criterio que TC-M04-G010, decision del 2026-10-19): TEST no tiene inferencias de RF-66 y ningun
endpoint las genera, asi que se crean activos propios por API y se siembran en la BD (usuario QA) inferencias y
retroalimentaciones clinicas solo de esos activos; la alerta de RF-57 se toma de una existente (la tabla de alertas
es inmutable). Al final se borra todo lo sembrado (eventos materializados, retroalimentaciones e inferencias).

Escenarios sembrados:
- A (019): I1 con alerta y retroalimentacion; I2 e I3 con el MISMO timestamp y distinto id, sin eventos asociados.
- B (020): 160 inferencias sin eventos asociados.
- C (020, con eventos asociados): 120 inferencias, una de cada 10 con retroalimentacion 2 h despues.
- D (021): 60 inferencias con el mismo timestamp.

Notas del codigo: id_evento se genera con uuid4() en cada consulta (no es estable) y el desempate real es por
id_resultado_inferencia; el limite de 50 se aplica a la mezcla de inferencias y eventos asociados, y el cursor
toma la fecha del ultimo evento de la pagina (que puede ser una retroalimentacion posterior a su inferencia).

Requisitos: acceso de red a TEST (API y Postgres 5448).
Variables opcionales: BASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo4/RF-67/TC-M04-G011 -v \
        --html=reporte-TC-M04-G011.html --self-contained-html
"""
from __future__ import annotations

import json
import os
import random
import string
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2
import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
TIMEOUT = 60
TAM_PAGINA = 50
DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)


def _sufijo() -> str:
    return "".join(random.choice(string.ascii_lowercase) for _ in range(8))


# --------------------------------------------------------------------------- datos
@pytest.fixture(scope="module")
def api() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": "admin@pecuaria.co", "contrasena": "Test1234!"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Login Administrador: HTTP {r.status_code} {r.text}"
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    yo = s.get(f"{BASE_URL}/usuarios/me", timeout=TIMEOUT).json()
    s.id_usuario = yo.get("id_usuario") or yo.get("usuario", {}).get("id_usuario")
    return s


def _crear(s, ruta, cuerpo, campo):
    r = s.post(f"{BASE_URL}{ruta}", json=cuerpo, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion {ruta}: HTTP {r.status_code} {r.text}"
    return r.json()[campo]


@pytest.fixture(scope="module")
def activos(api) -> dict:
    suf = _sufijo()
    finca = _crear(api, "/configuracion/fincas", {
        "nombre": f"Finca Paginacion Historial {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(api, "/configuracion/especies", {
        "nombre": f"Porcinos Paginacion {suf}", "descripcion": "Especie de prueba TC-M04-G011",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    area = _crear(api, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Corral Paginacion {suf}", "tipo_area": "Corral", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")
    ids = {}
    for clave in "ABCD":
        ids[clave] = _crear(api, "/activos-biologicos", {
            "tipo_activo": "INDIVIDUAL", "id_especie": especie, "fecha_inicio_ciclo": "2026-09-01",
            "origen_financiero": "nacimiento", "id_infraestructura": area, "identificador": f"CERDO-{clave}-{suf}",
            "raza": "Landrace", "sexo": "Macho", "fecha_nacimiento": "2026-05-01T00:00:00", "peso_inicial": "30.0",
            "detalles_procedencia": "Activo de prueba TC-M04-G011"}, "id_activo_biologico")
    return {"ids": ids, "especie": especie}


@pytest.fixture(scope="module")
def sembrado(api, activos):
    ahora = datetime.now(timezone.utc).replace(microsecond=0)
    especie = activos["especie"]
    con = psycopg2.connect(**DB)
    inferencias: list[str] = []
    retros: list[str] = []

    def inferencia(cur, activo, fecha, version, alerta=None):
        id_ri = str(uuid.uuid4())
        inferencias.append(id_ri)
        cur.execute(
            """
            INSERT INTO modulo4.resultados_inferencia
              (id_resultado_inferencia, id_activo_biologico, id_especie, tipo_modelo, id_version_modelo, nivel_riesgo,
               probabilidad_riesgo, probabilidad_enfermedad, confianza_global, modo_ejecucion, fecha_inferencia,
               tiene_alerta_generada, id_alerta_generada)
            VALUES (%s, %s, %s, 'MODELO_PORCINOS', %s, 1, '{"1": 0.6}', '{}', 0.8, 'SERVIDOR', %s, %s, %s)
            """,
            (id_ri, activo, especie, version, fecha, alerta is not None, alerta))
        return id_ri

    def retro(cur, id_ri, activo, fecha):
        id_rc = str(uuid.uuid4())
        retros.append(id_rc)
        cur.execute(
            """
            INSERT INTO modulo4.retroalimentaciones_clinicas
              (id_retroalimentacion, id_resultado_inferencia, id_activo_biologico, estado_retroalimentacion,
               id_usuario_veterinario, observaciones_clinicas, fecha_retroalimentacion)
            VALUES (%s, %s, %s, 'CORRECTO', %s, 'Retroalimentacion de prueba TC-M04-G011', %s)
            """,
            (id_rc, id_ri, activo, api.id_usuario, fecha))

    try:
        with con.cursor() as cur:
            cur.execute("SELECT min(id_version_modelo) FROM modulo4.versiones_modelos")
            version = cur.fetchone()[0]
            cur.execute("SELECT min(id_alerta_patologica) FROM modulo4.alertas_patologicas")
            alerta = cur.fetchone()[0]
            assert version is not None and alerta is not None, "Faltan una version de modelo o una alerta existente"
            ids = activos["ids"]

            # A (019)
            t0, t1 = ahora - timedelta(days=2), ahora - timedelta(days=1)
            i1 = inferencia(cur, ids["A"], t0, version, alerta)
            retro(cur, i1, ids["A"], t0 + timedelta(hours=1))
            i2 = inferencia(cur, ids["A"], t1, version)
            i3 = inferencia(cur, ids["A"], t1, version)
            # B (020)
            b = [inferencia(cur, ids["B"], ahora - timedelta(days=3, minutes=i), version) for i in range(160)]
            # C (020 con eventos asociados)
            c = []
            for i in range(120):
                fecha = ahora - timedelta(days=3, minutes=i)
                id_ri = inferencia(cur, ids["C"], fecha, version)
                c.append(id_ri)
                if i % 10 == 0:
                    retro(cur, id_ri, ids["C"], fecha + timedelta(hours=2))
            # D (021)
            t_d = ahora - timedelta(days=1, hours=5)
            d = [inferencia(cur, ids["D"], t_d, version) for _ in range(60)]
        con.commit()
        yield {"ids": ids, "alerta": alerta, "i1": i1, "i2": i2, "i3": i3, "b": b, "c": c, "d": d,
               "desde": str((ahora - timedelta(days=10)).date()), "hasta": str(ahora.date())}
    finally:
        con.rollback()
        with con.cursor() as cur:
            cur.execute("DELETE FROM modulo4.historial_diagnostico_eventos WHERE id_resultado_inferencia = ANY(%s::uuid[])", (inferencias,))
            cur.execute("DELETE FROM modulo4.retroalimentaciones_clinicas WHERE id_retroalimentacion = ANY(%s::uuid[])", (retros,))
            cur.execute("DELETE FROM modulo4.resultados_inferencia WHERE id_resultado_inferencia = ANY(%s::uuid[])", (inferencias,))
        con.commit()
        con.close()


# --------------------------------------------------------------------------- utilidades
def _pagina(api, sembrado, activo, cursor=None, incluir_alertas=False, extra=None) -> requests.Response:
    params = {"fecha_inicio": sembrado["desde"], "fecha_fin": sembrado["hasta"], "incluir_alertas": str(incluir_alertas).lower()}
    if cursor:
        params["cursor_paginacion"] = cursor
    params.update(extra or {})
    return api.get(f"{BASE_URL}/prediccion/historial/{activo}", params=params, timeout=TIMEOUT)


def _recorrer(api, sembrado, activo, incluir_alertas=False, max_paginas=20) -> list[list[dict]]:
    paginas, cursor = [], None
    for _ in range(max_paginas):
        r = _pagina(api, sembrado, activo, cursor, incluir_alertas)
        assert r.status_code == 200, f"HTTP {r.status_code} {r.text[:300]}"
        cuerpo = r.json()
        paginas.append(cuerpo["eventos"])
        cursor = cuerpo.get("cursor_siguiente")
        if not cursor:
            return paginas
    pytest.fail(f"Mas de {max_paginas} paginas: el cursor no termina")


def _clave(e: dict) -> tuple:
    return e["tipo_evento"], e["id_resultado_inferencia"]


# --------------------------------------------------------------------------- TC-M04-019
def test_tc_m04_019_alerta_y_retroalimentacion_correlacionadas_por_id(api, sembrado):
    r = _pagina(api, sembrado, sembrado["ids"]["A"], incluir_alertas=True)
    assert r.status_code == 200, r.text
    eventos = r.json()["eventos"]
    tipos_i1 = sorted(e["tipo_evento"] for e in eventos if e["id_resultado_inferencia"] == sembrado["i1"])
    assert tipos_i1 == ["ALERTA", "INFERENCIA", "RETROALIMENTACION"], f"Eventos de I1: {tipos_i1}"
    alerta = next(e for e in eventos if e["tipo_evento"] == "ALERTA")
    assert alerta["payload"]["id_alerta_patologica"] == sembrado["alerta"]


def test_tc_m04_019_mismo_timestamp_distinto_id_no_se_correlacionan(api, sembrado):
    eventos = _pagina(api, sembrado, sembrado["ids"]["A"], incluir_alertas=True).json()["eventos"]
    for id_ri in (sembrado["i2"], sembrado["i3"]):
        tipos = [e["tipo_evento"] for e in eventos if e["id_resultado_inferencia"] == id_ri]
        assert tipos == ["INFERENCIA"], f"La inferencia {id_ri} (mismo timestamp que otra) recibio eventos ajenos: {tipos}"


# --------------------------------------------------------------------------- TC-M04-020
def test_tc_m04_020_recorrido_completo_sin_duplicados_ni_omisiones(api, sembrado):
    paginas = _recorrer(api, sembrado, sembrado["ids"]["B"])
    assert all(len(p) <= TAM_PAGINA for p in paginas), f"Tamanos de pagina: {[len(p) for p in paginas]}"
    assert len(paginas) == 4, f"160 eventos en paginas de 50 deberian ser 4 paginas: {[len(p) for p in paginas]}"
    ids = [e["id_resultado_inferencia"] for p in paginas for e in p]
    assert len(ids) == len(set(ids)), "Hay eventos duplicados entre paginas"
    assert set(ids) == set(sembrado["b"]), f"Faltan {len(set(sembrado['b']) - set(ids))} eventos al concatenar las paginas"


def test_tc_m04_020_paginacion_con_eventos_asociados(api, sembrado):
    paginas = _recorrer(api, sembrado, sembrado["ids"]["C"], incluir_alertas=True)
    tamanos = [len(p) for p in paginas]
    assert all(t <= TAM_PAGINA for t in tamanos), f"Paginas con mas de {TAM_PAGINA} registros: {tamanos}"
    claves = [_clave(e) for p in paginas for e in p]
    duplicados = {k for k in claves if claves.count(k) > 1}
    assert not duplicados, f"{len(duplicados)} eventos repetidos entre paginas (cursor tomado de una retroalimentacion)"
    esperadas = {("INFERENCIA", i) for i in sembrado["c"]} | {("RETROALIMENTACION", sembrado["c"][i]) for i in range(0, 120, 10)}
    faltan = esperadas - set(claves)
    assert not faltan, f"{len(faltan)} eventos omitidos al recorrer las paginas"


def test_tc_m04_020_tamano_de_pagina_mayor_a_50_no_se_concede(api, sembrado):
    for nombre in ("limit", "por_pagina", "tamano_pagina", "page_size"):
        r = _pagina(api, sembrado, sembrado["ids"]["B"], extra={nombre: 100})
        assert r.status_code in (200, 400, 422), f"{nombre}=100: HTTP {r.status_code}"
        if r.status_code == 200:
            assert len(r.json()["eventos"]) <= TAM_PAGINA, f"Con {nombre}=100 se devolvieron {len(r.json()['eventos'])} registros"


# --------------------------------------------------------------------------- TC-M04-021
def test_tc_m04_021_orden_identico_en_consultas_repetidas(api, sembrado):
    recorridos = [[e["id_resultado_inferencia"] for p in _recorrer(api, sembrado, sembrado["ids"]["D"]) for e in p] for _ in range(3)]
    assert recorridos[0] == recorridos[1] == recorridos[2], "El orden de eventos con el mismo timestamp cambia entre consultas"
    assert sorted(recorridos[0]) == sorted(sembrado["d"]) and len(recorridos[0]) == 60, "Duplicados u omisiones al paginar empates"


def test_tc_m04_021_id_evento_estable_entre_consultas(api, sembrado):
    a = _pagina(api, sembrado, sembrado["ids"]["D"]).json()["eventos"]
    b = _pagina(api, sembrado, sembrado["ids"]["D"]).json()["eventos"]
    por_inferencia_a = {e["id_resultado_inferencia"]: e["id_evento"] for e in a}
    distintos = [e["id_resultado_inferencia"] for e in b if por_inferencia_a.get(e["id_resultado_inferencia"]) != e["id_evento"]]
    assert not distintos, (
        f"{len(distintos)} eventos devuelven un id_evento distinto en cada consulta (se genera con uuid4 por consulta): "
        "no puede servir para desempatar de forma determinista"
    )


def test_tc_m04_021_empate_desempatado_por_id_evento_descendente(api, sembrado):
    eventos = [e for p in _recorrer(api, sembrado, sembrado["ids"]["D"]) for e in p]
    ids_evento = [e["id_evento"] for e in eventos]
    assert ids_evento == sorted(ids_evento, reverse=True), "Con timestamps identicos el orden no es por id_evento descendente"
