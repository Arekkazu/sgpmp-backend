# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-84: script del grupo TC-M06-G17 (pytest + sandbox, rol Contador) |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G17-V2.0.html |
# | 2026-11-13 | Daniela Castillo | M06 V2.0 (2.ª pasada): la base de datos pasa a ser la fuente de verdad (SQL ya funciona), expectativas alineadas con las correcciones de Desarrollo (notas de la versión 1.4.0) y las precondiciones que fallan ya no se omiten: quedan en rojo con diagnóstico |
"""
TC-M06-G17 - Valor neto en el límite (0,0001; 0; negativo) y REVISION_REQUERIDA.   RF-84 (CU03 FA-02/FA-03).   Casos: TC-M06-082 a TC-M06-086 (con subcasos b y c).

Bruto = 1.000,0000 (1 cabeza a 1.000,00). Los costos se ingresan como costos manuales en la confirmación del reconocimiento (única entrada
manual de RF-84) con la especie sin parámetros de M09.
Comportamiento del backend: un neto <= 0 NO se persiste: la confirmación responde VALOR_NETO_NO_POSITIVO (4xx) y GET /simulacion devuelve el
cálculo con estado REVISION_REQUERIDA (sin guardarlo). La ficha y RF-84 (paso 6, FA-2, CA-5) piden que el cálculo QUEDE en REVISION_REQUERIDA,
que se emita la alerta y que el Contador pueda validarlo con justificación: cada exigencia va en un caso aparte (083/083b/083c, 084/084b/084c,
085 y 086). La notificación al Contador en pantalla se prueba en Cypress (G31); aquí se verifica el registro de la alerta en la auditoría RF-94.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G17/TC-M06-G17.py" -v -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G17/reporte-TC-M06-G17-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

JUSTIF = "Costos de disposición QA TC-M06 con soporte documental: cotización No. 456 del comprador."
SEV_ALERTA = ("WARNING", "ADVERTENCIA", "ALERTA", "CRITICA", "CRITICO", "CRITICAL", "ERROR")
SEV_CRITICA = ("CRITICA", "CRITICO", "CRITICAL", "ERROR", "ALTA")


@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()


@pytest.fixture(scope="module")
def esc(env):
    return env.escenario(categoria="POR_CABEZA", precio="1000.00", costos=None)


def _alertas(env, ida, severidades):
    """Eventos de auditoría RF-94 del activo con severidad de alerta (o de tipo ALERTA/NETO)."""
    out = []
    for e in env.auditoria(ida):
        sev = str(e.get("severidad") or e.get("severidad_evento") or "").upper()
        tipo = str(e.get("tipo_evento") or "").upper()
        if sev in severidades or "ALERTA" in tipo or "NETO" in tipo:
            out.append((tipo, sev))
    return out


def _eventos_alerta(env, ida):
    """(tipo, severidad) de TODOS los eventos de alerta del activo; la severidad se muestra siempre para poder comprobar el nivel exacto."""
    out = []
    for e in env.auditoria(ida):
        sev = str(e.get("severidad") or e.get("severidad_evento") or "").upper()
        tipo = str(e.get("tipo_evento") or "").upper()
        if sev in SEV_ALERTA or "ALERTA" in tipo or "NETO" in tipo:
            out.append((tipo, sev))
    return out


@pytest.fixture(scope="module")
def cero(env):
    """Activo con costos de M09 = 100 % del bruto (neto 0): simulación y confirmación bloqueada, una sola vez."""
    env.presupuesto(30)
    e = env.escenario(categoria="POR_CABEZA", precio="1000.00", costos=("0.5", "0.4", "0.1"))
    ida = env.activo(e, origen="nacimiento", costo=None, soporte=None)
    sim = env.simulacion(ida)
    conf = env.confirmar(ida)
    return ida, sim, conf


@pytest.fixture(scope="module")
def negativo(env, esc):
    """Activo con transporte manual 1000,0001 sobre bruto 1000,0000 (neto -0,0001): confirmación bloqueada, una sola vez."""
    env.presupuesto(25)
    ida, r = env.confirmar_manual(esc, {"transporte": "1000.0001"}, JUSTIF)
    return ida, r


def test_TC_M06_082_neto_positivo_minimo_se_acepta(env, esc):
    env.presupuesto(25)
    ida, r = env.confirmar_manual(esc, {"transporte": "999.9999"}, JUSTIF)
    assert r.status in (200, 201), r
    c = env.calculo(ida)
    assert dec(c["valor_neto"]) == dec("0.0001") and c["estado"] == "CALCULADO", c
    assert not _alertas(env, ida, SEV_ALERTA), f"con neto positivo no debe haber alerta: {_alertas(env, ida, SEV_ALERTA)}"


def test_TC_M06_083_neto_cero_se_bloquea_y_se_simula_en_revision(env, cero):
    ida, s, c = cero
    assert s.status == 200 and s.get("es_valido") is True, s
    assert dec(s.get("calculo")["valor_neto"]) == 0 and s.get("calculo")["estado"] == "REVISION_REQUERIDA", s
    assert 400 <= c.status < 500 and "VALOR_NETO_NO_POSITIVO" in c.text, \
        f"la confirmación con neto 0 debe quedar bloqueada con VALOR_NETO_NO_POSITIVO: {c}"
    obs("Neto 0: la confirmación se bloquea con VALOR_NETO_NO_POSITIVO y el cálculo queda registrado en REVISION_REQUERIDA hasta que el Contador lo valide con justificación (083b/083c y 085).")


def test_TC_M06_083b_neto_cero_genera_alerta(env, cero):
    ida, _, _ = cero
    al = _eventos_alerta(env, ida)
    assert al, f"con neto 0 debe quedar una alerta (preventiva o crítica) registrada para el Contador; eventos de auditoría: {env.tipos_auditoria(ida)}"
    # RF-84 FA-2 y CA-5: «alerta crítica» para neto <= 0; CU03 FA-03 la llama preventiva para el 0. Se documenta el nivel real (ficha 083).
    obs(f"Nivel real de la alerta con neto 0: {al} (RF-84 FA-2/CA-5 pide crítica; CU03 FA-03 preventiva).")


def test_TC_M06_083c_neto_cero_queda_registrado_en_revision_requerida(env, cero):
    ida, _, _ = cero
    c = env.calculo(ida)
    assert c is not None and c["estado"] == "REVISION_REQUERIDA", \
        f"el cálculo con neto 0 debe quedar registrado en REVISION_REQUERIDA hasta la validación del Contador: {c}"


def test_TC_M06_084_neto_negativo_bloquea_y_no_se_usa(env, negativo):
    ida, r = negativo
    assert 400 <= r.status < 500 and "VALOR_NETO_NO_POSITIVO" in r.text, f"se esperaba el bloqueo por neto no positivo: {r}"
    assert not lineas_de(env.historial(ida)), "el valor con neto negativo no debe usarse en el reconocimiento (sin asientos)"


def test_TC_M06_084b_neto_negativo_genera_alerta_critica(env, negativo):
    ida, _ = negativo
    al = _eventos_alerta(env, ida)
    assert al, f"con neto negativo debe quedar una alerta registrada; eventos de auditoría: {env.tipos_auditoria(ida)}"
    # RF-84 FA-2 y CA-5: la alerta del neto <= 0 es CRÍTICA: se exige la severidad, no basta con que el tipo de evento diga «alerta».
    assert any(sev in SEV_CRITICA for _, sev in al), f"la alerta del neto negativo debe ser CRÍTICA (RF-84 FA-2, CA-5); eventos de alerta (tipo, severidad): {al}"


def test_TC_M06_084c_neto_negativo_queda_registrado_en_revision_requerida(env, negativo):
    ida, _ = negativo
    c = env.calculo(ida)
    assert c is not None and c["estado"] == "REVISION_REQUERIDA", \
        f"el cálculo con neto negativo debe quedar registrado en REVISION_REQUERIDA: {c}"


def _operacion_validacion(env, ida):
    """INC-M06-317 (corregido por Desarrollo, #1004 / PR #1053): el Contador valida con justificación un cálculo con neto no positivo.
    El nombre de la operación no está en el RF: se busca en el OpenAPI del backend de TEST (una ruta POST/PUT/PATCH de /finanzas con «valid» y
    «calculo»/«revision»). Si no existe, el caso FALLA (rojo) con el listado de rutas parecidas para pasárselo a Desarrollo.
    Devuelve (método, ruta con los ids puestos, nombre del campo de justificación)."""
    r = requests.get(f"{BASE_URL}/openapi.json", timeout=30)
    assert r.status_code == 200, (f"no se pudo leer {BASE_URL}/openapi.json ({r.status_code}) para ubicar la operación de validación de INC-M06-317; "
                                  "pedirle a Desarrollo el endpoint y el cuerpo de la validación (PR #1053)")
    doc = r.json()
    candidatas = []
    for ruta, ops in doc.get("paths", {}).items():
        bajo = ruta.lower()
        if "/finanzas" in bajo and "valid" in bajo and ("calculo" in bajo or "revision" in bajo or "reconocimiento" in bajo):
            for metodo in ("post", "put", "patch"):
                if metodo in ops:
                    candidatas.append((metodo.upper(), ruta, ops[metodo]))
    assert candidatas, ("INC-M06-317: el OpenAPI de TEST no expone ninguna operación para validar con justificación un cálculo de neto no positivo "
                        "(ruta de /finanzas con «valid» y «calculo» o «revision»); Desarrollo la declaró corregida en #1004")
    metodo, plantilla, op = candidatas[0]
    cal = env.calculo(ida)
    ids = {"calculo": cal.get("id_calculo_valor_razonable") if cal else None, "activo": ida}
    ruta = plantilla
    for nombre in re.findall(r"\{([^}]+)\}", plantilla):
        clave = "calculo" if "calculo" in nombre.lower() else "activo" if "activo" in nombre.lower() else None
        assert clave and ids.get(clave) is not None, f"no se pudo resolver el parámetro {{{nombre}}} de {plantilla}"
        ruta = ruta.replace("{" + nombre + "}", str(ids[clave]))
    campo = "justificacion"
    esquema = (((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
    if "$ref" in esquema:
        esquema = doc.get("components", {}).get("schemas", {}).get(esquema["$ref"].split("/")[-1], {})
    for k in (esquema.get("properties") or {}):
        if "justific" in k.lower():
            campo = k
    obs(f"operación de validación encontrada en el OpenAPI: {metodo} {plantilla} (campo de justificación: {campo}); otras candidatas: {[c[:2] for c in candidatas[1:]]}")
    return metodo, ruta, campo


def test_TC_M06_085_validacion_explicita_de_neto_no_positivo(env, cero):
    """CU03 FA-02/FA-03; RF-84 paso 6, CA-5 (INC-M06-317, corregido por Desarrollo): el cálculo con neto 0 queda en REVISION_REQUERIDA y el
    Contador lo valida con justificación."""
    env.presupuesto(25)
    ida, _, _ = cero
    antes = env.calculo(ida)
    assert antes is not None and antes["estado"] == "REVISION_REQUERIDA", f"precondición: el cálculo debe estar en REVISION_REQUERIDA: {antes}"
    metodo, ruta, campo = _operacion_validacion(env, ida)
    r = env.call(metodo, ruta, "contador", json={campo: JUSTIF})
    assert r.status in (200, 201), f"el Contador debe poder validar el cálculo con justificación: {metodo} {ruta} respondió {r}"
    despues = env.calculo(ida)
    assert despues["estado"] != "REVISION_REQUERIDA", f"tras validar, el cálculo ya no debe seguir en REVISION_REQUERIDA: {despues}"
    bd = env.calculo_bd(ida)
    assert str(bd.get("estado")) == str(despues["estado"]), f"base de datos y API difieren en el estado: {bd.get('estado')} / {despues['estado']}"
    assert JUSTIF in str(bd), "la justificación de la validación debe quedar guardada en la base de datos"


def test_TC_M06_086_validacion_sin_justificacion_de_neto_no_positivo(env, negativo):
    env.presupuesto(25)
    ida, _ = negativo
    antes = env.calculo(ida)
    assert antes is not None and antes["estado"] == "REVISION_REQUERIDA", f"precondición: el cálculo debe estar en REVISION_REQUERIDA: {antes}"
    metodo, ruta, campo = _operacion_validacion(env, ida)
    for cuerpo in ({}, {campo: ""}, {campo: "   "}):
        r = env.call(metodo, ruta, "contador", json=cuerpo)
        assert 400 <= r.status < 500, f"la validación sin justificación ({cuerpo}) debe rechazarse con 4xx y respondió {r}"
    despues = env.calculo(ida)
    assert despues["estado"] == "REVISION_REQUERIDA", f"el rechazo no debe cambiar el estado del cálculo: {despues}"
    assert str(env.calculo_bd(ida).get("estado")) == "REVISION_REQUERIDA", "la base de datos debe conservar REVISION_REQUERIDA"
