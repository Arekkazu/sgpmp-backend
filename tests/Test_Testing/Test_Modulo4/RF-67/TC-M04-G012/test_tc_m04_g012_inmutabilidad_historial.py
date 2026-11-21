# | Fecha      | Nombre     | Que se hizo                                                                        |
# |------------|------------|------------------------------------------------------------------------------------|
# | 2026-10-26 | HulkyZeus  | TC-M04-G012 RF-67: limpieza tolerante (historial inmutable) e inferencia posterior a la patologia |
"""
TC-M04-G012 - Inmutabilidad e integridad del historial diagnostico.

RF relacionado: RF-67 (CU04). Casos: TC-M04-022 (CA-11), TC-M04-023 (CA-5/CA-6, append-only) y TC-M04-036 (CA-9).

Criterios de la ficha:
    TC-M04-022: el historial muestra el nombre de la patologia vigente al momento de la inferencia; renombrarla o
    inactivarla despues no lo altera.
    TC-M04-023: PUT/PATCH/DELETE sobre un resultado se bloquean, por API y en BD; una retroalimentacion sobre el mismo
    resultado se persiste como evento independiente.
    TC-M04-036: id_evento unico en toda la tabla, incluso con reintentos o fallos parciales de escritura.

Endpoints: GET /prediccion/historial/{id_activo_biologico}, POST /prediccion/retroalimentacion (RF-72),
/prediccion/patologias (renombrar/inactivar). Mismo formato que TC-M04-G011 (pytest con llamadas HTTP directas).

Datos (decision del 2026-10-19, igual que TC-M04-G010): TEST no tiene inferencias de RF-66, asi que se crean activos y
una patologia propios por API y se siembran inferencias en la BD (usuario QA). Al final se intenta borrar lo sembrado y
lo que el historial y la retroalimentacion generaron; como esas tablas ya son inmutables (INC-M04-145) el borrado puede
quedar bloqueado: se avisa con una advertencia (warnings) y el dato queda en TEST, sin marcar el caso como fallido.

SEGURIDAD: los UPDATE/DELETE directos de TC-M04-023 se ejecutan dentro de una transaccion que SIEMPRE se revierte y
solo sobre filas sembradas por este archivo.

TC-M04-036, "reintentos o fallo parcial": la escritura de eventos ocurre al consultar el historial
(materializar_eventos). Se simulan reintentos lanzando 10 consultas simultaneas del mismo historial nuevo y se revisa
en la BD que no haya id_evento repetidos (clave primaria) ni el mismo evento (id_resultado_inferencia, tipo_evento)
materializado dos veces con ids distintos.

Notas del codigo (version original, 2026-10-19; INC-M04-144/145/146 las corrigieron despues): nombre_patologia se leia
de modulo9.patologias en cada consulta (no del momento de la inferencia); resultados_inferencia e
historial_diagnostico_eventos no tenian triggers de inmutabilidad; la materializacion revisaba "si ya existe" antes de
insertar, sin indice unico sobre (id_resultado_inferencia, tipo_evento).

Requisitos: acceso de red a TEST (API y Postgres 5448).
Variables opcionales: BASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo4/RF-67/TC-M04-G012 -v \
        --html=reporte-TC-M04-G012.html --self-contained-html
"""
from __future__ import annotations

import os
import random
import string
import threading
import uuid
import warnings
from datetime import datetime, timedelta, timezone

import psycopg2
import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
TIMEOUT = 60
DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)
DESC = "Cuadro clínico de prueba con alteración sostenida de las variables fisiológicas asociadas durante horas."


def _sufijo() -> str:
    return "".join(random.choice(string.ascii_lowercase) for _ in range(8))


@pytest.fixture(scope="module")
def api() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": "admin@pecuaria.co", "contrasena": "Test1234!"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Login Administrador: HTTP {r.status_code} {r.text}"
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module")
def api_vet() -> requests.Session:
    # La retroalimentacion clinica (RF-72) es del rol Veterinario: el Administrador recibe 403.
    s = requests.Session()
    r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": "juan.carlos@email.com", "contrasena": "Test1234!"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Login Veterinario: HTTP {r.status_code} {r.text}"
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


def _crear(s, ruta, cuerpo, campo):
    r = s.post(f"{BASE_URL}{ruta}", json=cuerpo, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion {ruta}: HTTP {r.status_code} {r.text}"
    return r.json()[campo]


@pytest.fixture(scope="module")
def datos(api):
    suf = _sufijo()
    finca = _crear(api, "/configuracion/fincas", {
        "nombre": f"Finca Inmutabilidad Historial {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(api, "/configuracion/especies", {
        "nombre": f"Porcinos Inmutabilidad {suf}", "descripcion": "Especie de prueba TC-M04-G012",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    area = _crear(api, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Corral Inmutabilidad {suf}", "tipo_area": "Corral", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")
    activos = {clave: _crear(api, "/activos-biologicos", {
        "tipo_activo": "INDIVIDUAL", "id_especie": especie, "fecha_inicio_ciclo": "2026-09-01",
        "origen_financiero": "nacimiento", "id_infraestructura": area, "identificador": f"CERDO-{clave[:4]}-{suf}",
        "raza": "Landrace", "sexo": "Macho", "fecha_nacimiento": "2026-05-01T00:00:00", "peso_inicial": "30.0",
        "detalles_procedencia": "Activo de prueba TC-M04-G012"}, "id_activo_biologico") for clave in ("historico", "concurrente")}
    nombre_original = f"Patologia Historica {suf}"
    id_patologia = _crear(api, "/prediccion/patologias", {
        "nombre_patologia": nombre_original, "especie_aplicable": str(especie),
        "variables_sensoricas_asociadas": [13, 14], "descripcion_clinica": DESC}, "id_patologia")

    ahora = datetime.now(timezone.utc).replace(microsecond=0)
    con = psycopg2.connect(**DB)
    inferencias: list[str] = []
    try:
        with con.cursor() as cur:
            cur.execute("SELECT min(id_version_modelo) FROM modulo4.versiones_modelos")
            version = cur.fetchone()[0]
            assert version is not None, "No hay ninguna version de modelo en TEST para referenciar"

            def inferencia(activo, fecha, patologia=None):
                id_ri = str(uuid.uuid4())
                inferencias.append(id_ri)
                cur.execute(
                    """
                    INSERT INTO modulo4.resultados_inferencia
                      (id_resultado_inferencia, id_activo_biologico, id_especie, tipo_modelo, id_version_modelo,
                       nivel_riesgo, probabilidad_riesgo, id_patologia, probabilidad_enfermedad, confianza_global,
                       modo_ejecucion, fecha_inferencia)
                    VALUES (%s, %s, %s, 'MODELO_PORCINOS', %s, 2, '{"2": 0.7}', %s, '{}', 0.8, 'SERVIDOR', %s)
                    """, (id_ri, activo, especie, version, patologia, fecha))
                return id_ri

            # La inferencia va DESPUES de crear la patologia y ANTES de renombrarla/inactivarla (el orden real):
            # con fecha anterior a la creacion no existe nombre vigente a esa fecha y el historial cae al nombre actual.
            historica = inferencia(activos["historico"], datetime.now(timezone.utc), id_patologia)
            concurrentes = [inferencia(activos["concurrente"], ahora - timedelta(hours=1, minutes=i)) for i in range(20)]
        con.commit()
        yield {"activos": activos, "id_patologia": id_patologia, "nombre_original": nombre_original, "suf": suf,
               "historica": historica, "concurrentes": concurrentes,
               "desde": str((ahora - timedelta(days=10)).date()), "hasta": str(ahora.date())}
    finally:
        con.rollback()
        # Cada borrado en su propia transaccion: si la base lo bloquea (historial inmutable, INC-M04-145) se avisa
        # y se sigue; no es un fallo del caso, solo queda ese dato en TEST.
        for tabla, borrar in (
            ("historial_diagnostico_eventos", "DELETE FROM modulo4.historial_diagnostico_eventos WHERE id_resultado_inferencia = ANY(%s::uuid[])"),
            ("retroalimentaciones_clinicas", "DELETE FROM modulo4.retroalimentaciones_clinicas WHERE id_resultado_inferencia = ANY(%s::uuid[])"),
            ("resultados_inferencia", "DELETE FROM modulo4.resultados_inferencia WHERE id_resultado_inferencia = ANY(%s::uuid[])"),
        ):
            try:
                with con.cursor() as cur:
                    cur.execute(borrar, (inferencias,))
                con.commit()
            except psycopg2.Error as exc:
                con.rollback()
                warnings.warn(f"TC-M04-G012: no se pudo limpiar {tabla} ({str(exc).splitlines()[0]}); el dato queda en TEST.")
        con.close()


def _historial(api, datos, clave) -> list[dict]:
    r = api.get(f"{BASE_URL}/prediccion/historial/{datos['activos'][clave]}",
                params={"fecha_inicio": datos["desde"], "fecha_fin": datos["hasta"]}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Historial: HTTP {r.status_code} {r.text[:300]}"
    return r.json()["eventos"]


def _inferencia(eventos, id_ri) -> dict:
    return next(e for e in eventos if e["tipo_evento"] == "INFERENCIA" and e["id_resultado_inferencia"] == id_ri)


# --------------------------------------------------------------------------- TC-M04-022
@pytest.fixture(scope="module")
def renombrada(api, datos):
    antes = _inferencia(_historial(api, datos, "historico"), datos["historica"])["payload"]["nombre_patologia"]
    r = api.patch(f"{BASE_URL}/prediccion/patologias/{datos['id_patologia']}", json={
        "nombre_patologia": f"Patologia Renombrada {datos['suf']}", "descripcion_clinica": DESC,
        "variables_sensoricas_asociadas": [13, 14]}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Renombrar la patologia: HTTP {r.status_code} {r.text}"
    tras_renombrar = _inferencia(_historial(api, datos, "historico"), datos["historica"])["payload"]["nombre_patologia"]
    r = api.patch(f"{BASE_URL}/prediccion/patologias/{datos['id_patologia']}/desactivar", timeout=TIMEOUT)
    assert r.status_code == 200, f"Inactivar la patologia: HTTP {r.status_code} {r.text}"
    tras_inactivar = _inferencia(_historial(api, datos, "historico"), datos["historica"])["payload"]["nombre_patologia"]
    return {"antes": antes, "tras_renombrar": tras_renombrar, "tras_inactivar": tras_inactivar}


def test_tc_m04_022_antes_del_cambio_se_ve_el_nombre_original(renombrada, datos):
    assert renombrada["antes"] == datos["nombre_original"]


def test_tc_m04_022_renombrar_no_altera_el_evento_historico(renombrada, datos):
    assert renombrada["tras_renombrar"] == datos["nombre_original"], (
        f"El historial muestra '{renombrada['tras_renombrar']}' en lugar del nombre vigente al momento de la inferencia "
        f"('{datos['nombre_original']}'): el nombre se lee de la tabla actual de patologias"
    )


def test_tc_m04_022_inactivar_no_altera_el_evento_historico(renombrada, datos):
    assert renombrada["tras_inactivar"] == datos["nombre_original"]


# --------------------------------------------------------------------------- TC-M04-023
@pytest.mark.parametrize("metodo", ["PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("ruta", ["/prediccion/historial/{activo}", "/prediccion/historial/{activo}/{resultado}",
                                  "/prediccion/resultados/{resultado}"])
def test_tc_m04_023_modificar_o_eliminar_por_api_no_se_completa(api, datos, metodo, ruta):
    destino = ruta.format(activo=datos["activos"]["historico"], resultado=datos["historica"])
    r = api.request(metodo, f"{BASE_URL}{destino}", json={"nivel_riesgo": 0}, timeout=TIMEOUT)
    assert r.status_code in (403, 404, 405), f"{metodo} {destino}: HTTP {r.status_code} {r.text[:200]}"


@pytest.mark.parametrize("tabla,sentencia", [
    ("resultados_inferencia", "UPDATE modulo4.resultados_inferencia SET nivel_riesgo = 0 WHERE id_resultado_inferencia = %s"),
    ("resultados_inferencia", "DELETE FROM modulo4.resultados_inferencia WHERE id_resultado_inferencia = %s"),
    ("historial_diagnostico_eventos", "UPDATE modulo4.historial_diagnostico_eventos SET payload = '{}' WHERE id_resultado_inferencia = %s"),
    ("historial_diagnostico_eventos", "DELETE FROM modulo4.historial_diagnostico_eventos WHERE id_resultado_inferencia = %s"),
], ids=["update-resultado", "delete-resultado", "update-evento", "delete-evento"])
def test_tc_m04_023_modificar_o_eliminar_en_bd_no_se_completa(api, datos, tabla, sentencia):
    _historial(api, datos, "historico")  # asegura que los eventos del resultado esten materializados
    con = psycopg2.connect(**DB)
    con.autocommit = False
    try:
        with con.cursor() as cur:
            cur.execute(sentencia, (datos["historica"],))
            afectadas = cur.rowcount
    except psycopg2.Error:
        afectadas = 0  # bloqueado (trigger/permiso): es lo esperado
    finally:
        con.rollback()  # nunca se confirma nada
        con.close()
    assert afectadas == 0, f"{tabla}: la sentencia modifico {afectadas} fila(s) (revertidas por la prueba); no hay bloqueo append-only"


def test_tc_m04_023_retroalimentacion_se_persiste_como_evento_independiente(api, api_vet, datos):
    antes = _inferencia(_historial(api, datos, "historico"), datos["historica"])
    r = api_vet.post(f"{BASE_URL}/prediccion/retroalimentacion", json={
        "id_resultado_inferencia": datos["historica"], "id_activo_biologico": datos["activos"]["historico"],
        "estado_retroalimentacion": "CORRECTO", "observaciones_clinicas": "Retroalimentacion de prueba TC-M04-023"},
        timeout=TIMEOUT)
    assert r.status_code == 201, f"Registrar retroalimentacion: HTTP {r.status_code} {r.text}"
    eventos = _historial(api, datos, "historico")
    despues = _inferencia(eventos, datos["historica"])
    retros = [e for e in eventos if e["tipo_evento"] == "RETROALIMENTACION" and e["id_resultado_inferencia"] == datos["historica"]]
    assert len(retros) == 1, f"Se esperaba un evento RETROALIMENTACION independiente, hay {len(retros)}"
    assert despues["payload"] == antes["payload"] or (
        {k: v for k, v in despues["payload"].items() if k != "nombre_patologia"}
        == {k: v for k, v in antes["payload"].items() if k != "nombre_patologia"}
    ), "La retroalimentacion modifico el evento de inferencia"


# --------------------------------------------------------------------------- TC-M04-036
@pytest.fixture(scope="module")
def materializado_concurrente(api, datos):
    """10 consultas simultaneas de un historial nunca consultado (reintentos de escritura en paralelo)."""
    errores = []

    def consultar():
        try:
            # requests.get propio por hilo: una Session no es segura para usarse en paralelo.
            r = requests.get(f"{BASE_URL}/prediccion/historial/{datos['activos']['concurrente']}",
                             params={"fecha_inicio": datos["desde"], "fecha_fin": datos["hasta"]},
                             headers=dict(api.headers), timeout=TIMEOUT)
            if r.status_code != 200:
                errores.append(r.status_code)
        except requests.RequestException as exc:
            errores.append(type(exc).__name__)

    hilos = [threading.Thread(target=consultar) for _ in range(10)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    con = psycopg2.connect(**DB)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT count(*), count(DISTINCT id_evento) FROM modulo4.historial_diagnostico_eventos")
            total, distintos = cur.fetchone()
            cur.execute(
                """SELECT id_resultado_inferencia, tipo_evento, count(*) FROM modulo4.historial_diagnostico_eventos
                   WHERE id_resultado_inferencia = ANY(%s::uuid[]) GROUP BY 1, 2 HAVING count(*) > 1""",
                (datos["concurrentes"],))
            repetidos = cur.fetchall()
            cur.execute("SELECT count(*) FROM pg_constraint WHERE conrelid = 'modulo4.historial_diagnostico_eventos'::regclass AND contype = 'p'")
            tiene_pk = cur.fetchone()[0] == 1
    finally:
        con.close()
    return {"errores": errores, "total": total, "distintos": distintos, "repetidos": repetidos, "tiene_pk": tiene_pk}


def test_tc_m04_036_consultas_concurrentes_sin_error(materializado_concurrente):
    assert not materializado_concurrente["errores"], f"Errores en las consultas simultaneas: {materializado_concurrente['errores']}"


def test_tc_m04_036_id_evento_unico_en_toda_la_tabla(materializado_concurrente):
    assert materializado_concurrente["tiene_pk"], "historial_diagnostico_eventos no tiene clave primaria"
    assert materializado_concurrente["total"] == materializado_concurrente["distintos"], "Hay id_evento repetidos en la tabla"


def test_tc_m04_036_cada_evento_materializado_una_sola_vez(materializado_concurrente):
    repetidos = materializado_concurrente["repetidos"]
    assert not repetidos, (
        f"{len(repetidos)} eventos (id_resultado_inferencia, tipo_evento) quedaron materializados mas de una vez con "
        f"distinto id_evento tras las escrituras simultaneas: {repetidos[:5]}"
    )
