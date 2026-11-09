# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-06 | Juan Manuel      | TC-M05-G01..G05 RF-74: colecciones con sandbox |
# | 2026-11-06 | Juan Manuel      | TC-M05 RF-74: verificaciones por API (RLS) y A=825 |
# | 2026-11-06 | Juan Manuel      | TC-M05-G06 (RF-74) y G08-G10 (RF-75)              |
# | 2026-11-06 | Juan Manuel      | TC-M05-G11, G12 (RF-75) y G26-G28 (RF-78)         |
# | 2026-11-06 | Juan Manuel      | TC-M05-G29, G30 (RF-78) y G32 (RF-79)             |
# | 2026-11-06 | Juan Manuel      | TC-M05-G33 a G35 (RF-79)                          |
# | 2026-11-09 | Juan Manuel      | TC-M05 re-ejecucion: conteos relativos (batch activo), TC-001 con activo nuevo, 046/051/060 con datos reales |
"""Genera las colecciones Newman de M05 (RF-74, RF-75, RF-78 y RF-79; grupos G01 a G35).

Uso (desde esta carpeta):  python construir_colecciones_rf74.py
Escribe ../RF-xx/TC-M05-Gnn/tc-m05-gnn.json. Se ejecutan desde Test_Modulo5 con:
    .\\correr_newman_m05.ps1 -Caso G01 -Rf RF-74

Todas corren dentro del sandbox transaccional del DBA (una transacción por corrida que el último
paso revierte con DELETE /test-control/runs/{run_id}). Sin `sandbox_secret` las peticiones se
desvían a 127.0.0.1:9 y nada llega a TEST.

Como cada corrida se revierte, ninguna colección depende de lo que dejó otra: cada una vuelve a
registrar, dentro de su propia transacción, los pesajes y consumos que necesitan sus casos
(carpeta "Preparación").

El activo A tiene que existir en TEST desde antes (`id_activo_a`): el backend rechaza eventos con
fecha anterior al registro del activo (FECHA_ANTERIOR_REGISTRO) y los casos fechan el primer
pesaje en D-20. Con `id_activo_a=0` la colección solo busca candidatos aptos y los lista en el
reporte, sin ejecutar casos.
"""
from __future__ import annotations

import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
ICA = "{{base_url}}/suministros/eficiencia-alimenticia"
ROLLBACK = "ROLLBACK - Revertir la transacción de la corrida"

# ─────────────────────────────── scripts de colección ───────────────────────────────
PRE_COLECCION = [
    "// Sandbox transaccional de TEST (DBA): toda la corrida va en una transaccion que NUNCA se confirma y el",
    "// ultimo paso la revierte (DELETE /test-control/runs/{run_id}). El secreto no se guarda en este archivo:",
    "// se pasa al ejecutar:  newman run <coleccion> --env-var \"sandbox_secret=<secreto>\"",
    "const secreto = pm.variables.get('sandbox_secret');",
    "if (!secreto) {",
    "  console.error('Falta sandbox_secret: ejecutar con --env-var sandbox_secret=<secreto>. Peticion desviada, no se envia a TEST.');",
    "  pm.request.url.update('http://127.0.0.1:9/falta-sandbox_secret');",
    "} else {",
    "  if (!pm.collectionVariables.get('run_id')) { pm.collectionVariables.set('run_id', 'test-' + pm.variables.replaceIn('{{$guid}}')); }",
    "  pm.request.headers.upsert({ key: 'X-Test-Run-Id', value: pm.collectionVariables.get('run_id') });",
    "  pm.request.headers.upsert({ key: 'X-Sandbox-Secret', value: secreto });",
    "}",
    "// 'Hoy' del backend sale de esta cabecera (hoy_usuario); sin ella seria el dia UTC.",
    "pm.request.headers.upsert({ key: 'X-Zona-Horaria', value: 'America/Bogota' });",
    "// Si el login de ese rol fallo, la peticion no se envia (el fallo queda en el test del login).",
    "const auth = (pm.request.headers.get('Authorization') || '').match(/\{\{(tok_\w+)\}\}/);",
    "if (auth && !pm.collectionVariables.get(auth[1])) { console.warn('Sin ' + auth[1] + ' (login fallido): se omite ' + pm.info.requestName); pm.execution.skipRequest(); }",
    "// Fechas relativas a D (hoy en Bogota, UTC-05:00 sin horario de verano), calculadas una vez por corrida.",
    "if (!pm.collectionVariables.get('dia_m0')) {",
    "  const bog = new Date(Date.now() - 5 * 3600 * 1000);",
    "  const dia = n => new Date(bog.getTime() - n * 86400000).toISOString().slice(0, 10);",
    "  [0, 1, 2, 3, 4, 5, 6, 10, 20].forEach(n => pm.collectionVariables.set('dia_m' + n, dia(n)));",
    "  pm.collectionVariables.set('dia_p1', dia(-1));",
    "  pm.collectionVariables.set('dia_mes', bog.toISOString().slice(0, 8) + '01');",
    "  // P3/P4 van en D a las 08:00 y 09:00; si todavia no son las 09:05 en Bogota serian fechas futuras",
    "  // (FECHA_FUTURA), asi que se usan hace 4 y 2 minutos, manteniendo P4 despues de P3.",
    "  const hhmmss = bog.toISOString().slice(11, 19);",
    "  if (hhmmss >= '09:05:00') { pm.collectionVariables.set('hora_p3', '08:00:00'); pm.collectionVariables.set('hora_p4', '09:00:00'); }",
    "  else {",
    "    pm.collectionVariables.set('hora_p3', new Date(bog.getTime() - 240000).toISOString().slice(11, 19));",
    "    pm.collectionVariables.set('hora_p4', new Date(bog.getTime() - 120000).toISOString().slice(11, 19));",
    "  }",
    "}",
]


# ─────────────────────────────── helpers de items ───────────────────────────────
def _url(raw: str) -> str:
    # Como string: el SDK de Postman ignora `raw` cuando la URL viene como objeto sin host/path.
    return raw


def req(nombre, metodo, url, *, token="tok_admin", body=None, tests=None, pre=None, descripcion=None):
    headers = []
    if token:
        headers.append({"key": "Authorization", "value": "Bearer {{" + token + "}}"})
    item = {"name": nombre, "event": [], "request": {"method": metodo, "header": headers, "url": _url(url)}}
    if body is not None:
        headers.append({"key": "Content-Type", "value": "application/json"})
        texto = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False, indent=2)
        item["request"]["body"] = {"mode": "raw", "raw": texto, "options": {"raw": {"language": "json"}}}
    if descripcion:
        item["request"]["description"] = descripcion
    if pre:
        item["event"].append({"listen": "prerequest", "script": {"type": "text/javascript", "exec": pre}})
    if tests:
        item["event"].append({"listen": "test", "script": {"type": "text/javascript", "exec": tests}})
    return item


def carpeta(nombre, items, descripcion=None):
    c = {"name": nombre, "item": items}
    if descripcion:
        c["description"] = descripcion
    return c


def sql(nombre, consulta, tests, *, guardar=None, pre=None):
    """POST /test-control/query: SELECT de solo lectura dentro de la transacción de la corrida."""
    t = [
        "pm.test('" + nombre.split(' - ')[0] + " - consulta de auditoria respondida (200)', () => pm.response.to.have.status(200));",
        "const filas = (pm.response.json() || {}).data || [];",
        "console.log(JSON.stringify(filas));",
    ]
    if guardar:
        t.append("pm.collectionVariables.set('" + guardar + "', JSON.stringify(filas));")
    return req(nombre, "POST", "{{base_url}}/test-control/query", token=None,
               body=json.dumps({"query": " ".join(consulta.split())}, ensure_ascii=False), tests=t + tests, pre=pre)


def login(var_token, var_correo, var_contrasena, rol, var_id):
    return req(
        f"Login {rol}", "POST", "{{base_url}}/sesiones/", token=None,
        body="{\n  \"correo_electronico\": \"{{" + var_correo + "}}\",\n  \"contrasena\": \"{{" + var_contrasena + "}}\"\n}",
        tests=[
            f"pm.test('Login {rol} (200)', () => pm.response.to.have.status(200));",
            f"pm.collectionVariables.set('{var_token}', '');",
            f"if (pm.response.code === 200) {{ const t = pm.response.json().token; pm.collectionVariables.set('{var_token}', t);"
            f" pm.collectionVariables.set('{var_id}', JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).sub); }}",
        ],
    )


def rollback():
    return carpeta("9. Rollback del sandbox (la BD queda como estaba)", [
        req(ROLLBACK, "DELETE", "{{base_url}}/test-control/runs/{{run_id}}", token=None, tests=[
            "pm.test('ROLLBACK - sandbox revertido (200)', () => pm.response.to.have.status(200));",
            "pm.collectionVariables.unset('run_id');",
        ]),
    ])


# ── Preparación: pesajes (RF-40) y consumos (RF-75) sobre A ──
def pesaje(nombre, valor, fecha_hora, token="tok_admin"):
    return req(
        nombre, "POST", "{{base_url}}/activos-biologicos/{{id_activo_a}}/eventos/crecimiento", token=token,
        body="{\n  \"tipo_medicion\": \"PESO\",\n  \"valor_medicion\": " + str(valor)
             + ",\n  \"unidad_medida\": \"kg\",\n  \"fecha\": \"" + fecha_hora + "\",\n  \"descripcion\": \"QA TC-M05 RF-74\"\n}",
        tests=[
            f"pm.test('{nombre.split(' - ')[0]} - pesaje {valor} kg registrado (200/201)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201]));",
            "if (![200, 201].includes(pm.response.code)) console.error('Pesaje rechazado: ' + pm.response.text());",
        ],
    )


def consumo(nombre, cantidad, dia_var, token="tok_admin"):
    return req(
        nombre, "POST", "{{base_url}}/suministros/consumo-alimentos", token=token,
        body="{\n  \"id_activo_biologico\": {{id_activo_a}},\n  \"id_tipo_alimento\": {{id_tipo_alimento}},\n  \"fecha_consumo\": \"{{"
             + dia_var + "}}\",\n  \"hora_suministro\": \"07:00:00\",\n  \"cantidad_alimento\": " + str(cantidad)
             + ",\n  \"costo_unitario\": 1500,\n  \"observaciones\": \"QA TC-M05 RF-74\"\n}",
        tests=[
            f"pm.test('{nombre.split(' - ')[0]} - consumo {cantidad} kg registrado (200/201)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201]));",
            "if (![200, 201].includes(pm.response.code)) console.error('Consumo rechazado: ' + pm.response.text());",
        ],
    )


def calcular(nombre, periodo, token, tests, *, id_activo="{{id_activo_a}}", guardar_id=None):
    t = list(tests)
    if guardar_id:
        t.insert(0, "if (pm.response.code === 200) pm.collectionVariables.set('" + guardar_id + "', pm.response.json().id_resultado_ica);")
    return req(nombre, "POST", ICA + "/calcular", token=token,
               body="{\n  \"id_activo_biologico\": " + id_activo + ",\n  \"periodo_evaluacion\": \"" + periodo + "\"\n}",
               tests=["const r = pm.response.code === 200 ? pm.response.json() : {};",
                      "console.log(pm.response.text());"] + t)


def num(campo):
    """Decimal llega como string en JSON (Pydantic 2); null se conserva."""
    return f"(r.{campo} === null || r.{campo} === undefined ? null : Number(r.{campo}))"


def check_ca(tc, *, estado, ca=None, clase=None, causa=None, score=None, alimento=None, ganancia=None):
    t = [f"pm.test('{tc} - HTTP 200', () => pm.response.to.have.status(200));",
         f"pm.test('{tc} - estado_resultado = {estado}', () => pm.expect(r.estado_resultado).to.eql('{estado}'));"]
    if ca is None:
        t.append(f"pm.test('{tc} - ca_calculado = null', () => pm.expect(r.ca_calculado).to.eql(null));")
        t.append(f"pm.test('{tc} - clasificacion_ca = null', () => pm.expect(r.clasificacion_ca).to.eql(null));")
    else:
        t.append(f"pm.test('{tc} - ca_calculado = {ca} (truncado a 4 decimales)', () => pm.expect({num('ca_calculado')}).to.eql({ca}));")
    if clase:
        t.append(f"pm.test('{tc} - clasificacion_ca = {clase}', () => pm.expect(r.clasificacion_ca).to.eql('{clase}'));")
    if causa:
        t.append(f"pm.test('{tc} - causa_no_calculo = {causa}', () => pm.expect(r.causa_no_calculo).to.eql('{causa}'));")
    elif estado == "CALCULADO":
        t.append(f"pm.test('{tc} - causa_no_calculo = null', () => pm.expect(r.causa_no_calculo).to.eql(null));")
    if score is not None:
        t.append(f"pm.test('{tc} - data_quality_score = {score}', () => pm.expect(r.data_quality_score).to.eql({score}));")
    if alimento is not None:
        t.append(f"pm.test('{tc} - alimento_consumido_total_kg = {alimento}', () => pm.expect({num('alimento_consumido_total_kg')}).to.eql({alimento}));")
    if ganancia is not None:
        t.append(f"pm.test('{tc} - ganancia_peso_kg = {ganancia}', () => pm.expect({num('ganancia_peso_kg')}).to.eql({ganancia}));")
    t.append(f"pm.test('{tc} - queda como vigente', () => pm.expect(r.es_vigente).to.eql(true));")
    return t


def ok200(tc):
    return [f"pm.test('{tc} - HTTP 200', () => pm.response.to.have.status(200));"]


# ── Precondiciones: logins + aptitud del activo A ──
# modulo1, modulo2, modulo3 y modulo9 tienen RLS y /test-control/query corre sin identidad (0 filas):
# esos datos se leen por la API como Administrador. Solo modulo5 se consulta por SQL.
SQL_APTITUD_M05 = """
SELECT (SELECT count(*) FROM modulo5.resultado_ica r WHERE r.id_activo_biologico = {{id_activo_a}}) AS n_resultados,
 (SELECT count(*) FROM modulo5.registros_consumo_alimentos c WHERE c.id_activo_biologico = {{id_activo_a}}) AS n_consumos,
 (SELECT coalesce(max(id_resultado_ica), 0) FROM modulo5.resultado_ica) AS max_resultado,
 (SELECT coalesce(max(id_auditoria_suministro), 0) FROM modulo5.auditorias_suministros) AS max_auditoria,
 (SELECT count(*) FROM modulo5.resultado_ica r WHERE r.id_activo_biologico = {{id_activo_a}} AND r.periodo_evaluacion::text = 'SEMANAL') AS prev_semanal,
 (SELECT count(*) FROM modulo5.resultado_ica r WHERE r.id_activo_biologico = {{id_activo_a}} AND r.periodo_evaluacion::text = 'POR_CICLO') AS prev_ciclo,
 (SELECT count(*) FROM modulo5.resultado_ica r WHERE r.id_activo_biologico = {{id_activo_a}} AND r.periodo_evaluacion::text = 'SEMANAL' AND r.es_vigente) AS vig_semanal,
 (SELECT count(*) FROM modulo5.resultado_ica r WHERE r.id_activo_biologico = {{id_activo_a}} AND r.periodo_evaluacion::text = 'POR_CICLO' AND r.es_vigente) AS vig_ciclo
"""
# Desde 2026-11-07 el batch nocturno vuelve a guardar: cada noche deja resultados AUTOMATICO (CA_NO_CALCULABLE)
# en todos los activos ACTIVOS, asi que A ya no puede estar "sin ICA". Los conteos se hacen sobre lo que crea
# la corrida (id > max_resultado / max_auditoria) y TC-M05-001 usa un activo recien registrado dentro del sandbox.


def precondiciones(logins, *, nivel="completo", tipo="INDIVIDUAL", sin_ica=True):
    """Logins + verificación de que A sirve para los casos (si no, salta al rollback).

    nivel="completo": A apto para registrar P1 en D-20 sobre un historial limpio (G01, G02, G03, G05).
    nivel="activo": basta con que A exista y esté ACTIVO (G04).
    """
    A = "{{base_url}}/activos-biologicos/{{id_activo_a}}"

    def guardar(var):
        return ["pm.test('PRE - consulta respondida (200)', () => pm.response.to.have.status(200));",
                f"pm.collectionVariables.set('{var}', pm.response.code === 200 ? pm.response.text() : '');"]

    def asignar(rol, tok, var_id):
        """Agrega la finca de A a las del usuario (PUT reemplaza la lista: se envía la unión). Se revierte con el sandbox."""
        return [
            # Se leen como Administrador en el detalle: algunos roles (Contador) reciben 403 al listar sus fincas, y sin la
            # lista el PUT (que reemplaza) les quitaria las demas fincas durante la corrida.
            req(f"PRE - Fincas actuales del {rol} (detalle, como Administrador)", "GET", "{{base_url}}/usuarios/{{" + var_id + "}}/detalle", token="tok_admin", tests=[
                f"pm.test('PRE - detalle del {rol} consultado (200)', () => pm.response.to.have.status(200));",
                f"pm.collectionVariables.set('fincas_{tok}', pm.response.code === 200 ? pm.response.text() : '');"]),
            req(f"PRE - Asignar al {rol} la finca de A (solo dentro del sandbox)", "PUT",
                "{{base_url}}/usuarios/{{" + var_id + "}}/fincas", token="tok_admin", body="{{body_fincas_" + tok + "}}",
                pre=["let fs = []; try { fs = (JSON.parse(pm.collectionVariables.get('fincas_" + tok + "') || '{}').fincas || []).map(x => x.id_finca); } catch (e) {}",
                     "const fa = Number(pm.collectionVariables.get('id_finca_a'));",
                     "if (fa && !fs.includes(fa)) fs.push(fa);",
                     "pm.collectionVariables.set('body_fincas_" + tok + "', JSON.stringify({ ids_fincas: fs }));"],
                tests=[f"pm.test('PRE - {rol} asignado a la finca de A (200)', () => pm.response.to.have.status(200));",
                       "console.log(pm.response.text());"]),
        ]

    items = list(logins) + [
        req("PRE - Activo A: detalle", "GET", A, token="tok_admin", tests=guardar("pre_activo")),
        req("PRE - Area de A (finca)", "GET", "{{base_url}}/configuracion/infraestructuras/{{id_infra_a}}", token="tok_admin",
            pre=["let a = {}; try { a = JSON.parse(pm.collectionVariables.get('pre_activo') || '{}'); } catch (e) {}",
                 "pm.collectionVariables.set('id_infra_a', a.id_infraestructura || 0);"],
            tests=["pm.test('PRE - area consultada (200)', () => pm.response.to.have.status(200));",
                   "pm.collectionVariables.set('id_finca_a', pm.response.code === 200 ? pm.response.json().id_finca : '');",
                   "pm.collectionVariables.set('vet_en_finca', 1);"]),
    ]
    for rol, tok, var in (("Productor", "tok_prod", "id_productor"), ("Veterinario", "tok_vet", "id_veterinario"),
                          ("Gestor de Granja", "tok_ges", "id_gestor"), ("Contador", "tok_cont", "id_contador")):
        if any(l["name"] == f"Login {rol}" for l in logins):
            items += asignar(rol, tok, var)
    if nivel == "completo":
        items += [
            req("PRE - Activo A: fases", "GET", A + "/fases", token="tok_admin", tests=guardar("pre_fases")),
            req("PRE - Activo A: eventos", "GET", A + "/eventos", token="tok_admin", tests=guardar("pre_eventos")),
            req("PRE - Activo A: alertas de conversion alimenticia", "GET",
                "{{base_url}}/iot/alertas?id_activo_biologico={{id_activo_a}}&tipo_alerta=CONVERSION_ALIMENTICIA",
                token="tok_admin", tests=guardar("pre_alertas")),
        ]
    criterios = [
        "const m5 = filas[0] || {};",
        "const j = k => { try { return JSON.parse(pm.collectionVariables.get(k) || 'null'); } catch (e) { return null; } };",
        "const a = j('pre_activo') || {};",
        "const fallos = [];",
        "const crit = (ok, txt) => { pm.test('PRE - ' + txt, () => pm.expect(ok, txt).to.eql(true)); if (!ok) fallos.push(txt); };",
        "crit(String(pm.variables.get('id_activo_a')) !== '0', 'Se indico id_activo_a (correr con --env-var id_activo_a=<id>)');",
        "crit(a.id_activo_biologico !== undefined, 'El activo A (' + pm.variables.get('id_activo_a') + ') existe');",
        "crit(a.id_estado === 1, 'A en estado ACTIVO; actual ' + a.nombre_estado);",
        "pm.collectionVariables.set('id_creador', a.id_usuario);",
        "pm.collectionVariables.set('max_resultado', m5.max_resultado);",
        "['max_auditoria', 'prev_semanal', 'prev_ciclo', 'vig_semanal', 'vig_ciclo'].forEach(k => pm.collectionVariables.set(k, Number(m5[k] || 0)));",
    ]
    if nivel == "completo":
        criterios += [
            "const tsP1 = new Date(pm.variables.get('dia_m20') + 'T08:00:00-05:00');",
            "const inicioD20 = new Date(pm.variables.get('dia_m20') + 'T00:00:00-05:00');",
            "const fase = ((j('pre_fases') || {}).fases || []).find(f => f.es_activa) || {};",
            "const evs = (j('pre_eventos') || {}).eventos || [];",
            "const pes = evs.filter(e => e.crecimiento && ['PESO', 'PESO_VIVO'].includes(String(e.crecimiento.tipo_medicion).toUpperCase()));",
            "const ult = evs.map(e => new Date(e.fecha)).sort((x, y) => y - x)[0];",
            "const alertas = ((j('pre_alertas') || {}).items || []).filter(x => ['ACTIVA', 'EN_ATENCION'].includes(x.estado_alerta));",
            f"crit(a.tipo === '{tipo}', 'A es {tipo} (los valores esperados dependen del tipo); actual ' + a.tipo);",
            "crit(new Date(a.fecha_creacion) <= tsP1, 'A registrado antes de P1 (D-20 08:00); registrado ' + a.fecha_creacion);",
            "crit(fase.id_gestion_fases !== undefined && new Date(fase.fecha_inicio) < inicioD20, 'A con fase activa iniciada antes de D-20 (F); inicio ' + fase.fecha_inicio);",
            "crit(!ult || ult <= tsP1, 'Ultimo evento de A anterior a P1; ultimo ' + (ult ? ult.toISOString() : 'ninguno'));",
            "crit(pes.length === 0, 'A sin pesajes previos; tiene ' + pes.length);",
            # sin_ica ya no se exige (batch nocturno activo): se informa cuantos tiene, sin bloquear.
            "console.log('A tiene ' + m5.n_resultados + ' resultados ICA previos (del batch nocturno); los conteos usan solo los de esta corrida.');",
            "crit(Number(m5.n_consumos) === 0, 'A sin consumos registrados; tiene ' + m5.n_consumos);",
            "crit(alertas.length === 0, 'A sin alertas de conversion alimenticia abiertas; tiene ' + alertas.length);",
            "pm.collectionVariables.set('id_fase_activa', fase.id_gestion_fases);",
            "pm.collectionVariables.set('cantidad_actual_a', ((a.detalle_poblacional || {}).cantidad_actual) || '');",
            "// F = dia (Bogota) de inicio de la fase activa: es la cota inferior de la fecha de consumo (RF-75 E3).",
            "if (fase.fecha_inicio) {",
            "  const f0 = new Date(new Date(fase.fecha_inicio).getTime() - 5 * 3600 * 1000);",
            "  const df = n => new Date(f0.getTime() + n * 86400000).toISOString().slice(0, 10);",
            "  [['dia_Fm1', -1], ['dia_F', 0], ['dia_Fp1', 1], ['dia_Fp2', 2], ['dia_Fp3', 3]].forEach(([k, n]) => pm.collectionVariables.set(k, df(n)));",
            "}",
        ]
    criterios.append(
        "if (fallos.length) { console.error('A no es apto: ' + fallos.join(' | ')); pm.execution.setNextRequest('" + ROLLBACK + "'); }")
    items.append(sql("PRE - Aptitud del activo A para los casos", SQL_APTITUD_M05, criterios))
    return carpeta("0. Precondiciones (logins y activo A apto)", items)


def asignar_finca_de(id_activo, rol="Contador", tok="tok_cont", var_id="id_contador"):
    """Suma al usuario la finca del activo indicado (ademas de las que ya tiene). PUT reemplaza la lista: se envia la union.
    Solo dentro del sandbox; el rollback la revierte. Sirve para no confundir un 404 por alcance de finca con un defecto."""
    v = f"finca_{id_activo}"
    return [
        req(f"PRE - Finca del activo {id_activo}", "GET", "{{base_url}}/activos-biologicos/" + str(id_activo), token="tok_admin", tests=[
            "pm.test('PRE - activo consultado (200)', () => pm.response.to.have.status(200));",
            f"pm.collectionVariables.set('infra_{id_activo}', pm.response.code === 200 ? pm.response.json().id_infraestructura : 0);"]),
        req(f"PRE - Area del activo {id_activo}", "GET", "{{base_url}}/configuracion/infraestructuras/{{infra_" + str(id_activo) + "}}", token="tok_admin", tests=[
            "pm.test('PRE - area consultada (200)', () => pm.response.to.have.status(200));",
            f"pm.collectionVariables.set('{v}', pm.response.code === 200 ? pm.response.json().id_finca : '');"]),
        # El Contador no puede listar sus fincas (403 en /configuracion/fincas): se leen como Administrador en el detalle.
        req(f"PRE - Fincas actuales del {rol} (detalle, como Administrador)", "GET", "{{base_url}}/usuarios/{{" + var_id + "}}/detalle", token="tok_admin", tests=[
            "pm.test('PRE - detalle consultado (200)', () => pm.response.to.have.status(200));",
            f"pm.collectionVariables.set('fincas_{tok}_{id_activo}', pm.response.code === 200 ? pm.response.text() : '');"]),
        req(f"PRE - Asignar al {rol} la finca del activo {id_activo} (solo dentro del sandbox)", "PUT",
            "{{base_url}}/usuarios/{{" + var_id + "}}/fincas", token="tok_admin", body="{{body_" + v + "}}",
            pre=["let fs = []; try { fs = (JSON.parse(pm.collectionVariables.get('fincas_" + tok + "_" + str(id_activo) + "') || '{}').fincas || []).map(x => x.id_finca); } catch (e) {}",
                 f"const fx = Number(pm.collectionVariables.get('{v}'));",
                 "if (fx && !fs.includes(fx)) fs.push(fx);",
                 f"pm.collectionVariables.set('body_{v}', JSON.stringify({{ ids_fincas: fs }}));"],
            tests=[f"pm.test('PRE - {rol} asignado a la finca del activo {id_activo} (200)', () => pm.response.to.have.status(200));",
                   "console.log(pm.response.text());"]),
    ]


def fase_sin_cambio(nombre):
    """Un pesaje puede avanzar la fase sola (RF-40, duración de fase): eso movería F y cambiaría POR_CICLO."""
    return req(nombre, "GET", "{{base_url}}/activos-biologicos/{{id_activo_a}}/fases", token="tok_admin", tests=[
        "const fase = ((pm.response.code === 200 ? pm.response.json() : {}).fases || []).find(f => f.es_activa) || {};",
        "pm.test('" + nombre.split(' - ')[0] + " - La fase activa de A no cambio con el pesaje (F se mantiene)', () => pm.expect(String(fase.id_gestion_fases)).to.eql(String(pm.collectionVariables.get('id_fase_activa'))));",
    ])


LOGIN_ADMIN = login("tok_admin", "correo_admin", "contrasena_admin", "Administrador", "id_admin")
LOGIN_PROD = login("tok_prod", "correo_productor", "contrasena_productor", "Productor", "id_productor")
LOGIN_VET = login("tok_vet", "correo_veterinario", "contrasena_veterinario", "Veterinario", "id_veterinario")
LOGIN_ING = login("tok_ing", "correo_ingeniero", "contrasena_ingeniero", "Ingeniero de Campo", "id_ingeniero")
LOGIN_CONT = login("tok_cont", "correo_contador", "contrasena_contador", "Contador", "id_contador")


# ── Pasos reutilizables (casos de G01 y G02) ──
def g01_items(silencioso=False, actor="tok_prod"):
    """Casos de G01; con silencioso=True se usan como preparación en G03 (solo verifican 200)."""
    t = (lambda tc, lst: ok200(tc)) if silencioso else (lambda tc, lst: lst)
    p = "PREP " if silencioso else ""
    return [
        calcular(f"{p}TC-M05-002 - Calcular SEMANAL sin pesajes ni consumos", "SEMANAL", actor,
                 t("TC-M05-002", check_ca("TC-M05-002", estado="CA_NO_CALCULABLE", causa="SIN_PESO_INICIAL", score=0) + [
                     "pm.test('TC-M05-002 - periodo D-6 a D', () => { pm.expect(r.fecha_inicio_periodo).to.eql(pm.variables.get('dia_m6')); pm.expect(r.fecha_fin_periodo).to.eql(pm.variables.get('dia_m0')); });",
                     "pm.test('TC-M05-002 - tipo_calculo = MANUAL e id_usuario del Productor', () => { pm.expect(r.tipo_calculo).to.eql('MANUAL'); pm.expect(String(r.id_usuario)).to.eql(String(pm.collectionVariables.get('id_productor'))); });",
                 ]), guardar_id="id_res_002"),
        consumo(f"PREP E2 - Consumo C0 = 20 kg en D-10 (dentro del ciclo, fuera de la semana)", 20, "dia_m10"),
        pesaje(f"PREP P1 - Pesaje P1 = 100 kg en D-20 08:00", 100, "{{dia_m20}}T08:00:00-05:00"),
        fase_sin_cambio("PREP P1 - Fase activa sin avance automatico"),
        calcular(f"{p}TC-M05-003a - Calcular SEMANAL solo con P1 (sin consumo en la semana)", "SEMANAL", actor,
                 t("TC-M05-003a", check_ca("TC-M05-003a", estado="CA_NO_CALCULABLE", causa="SIN_REGISTROS_CONSUMO", score=50))),
        calcular(f"{p}TC-M05-003b - Calcular POR_CICLO (no hay pesaje en o antes de F)", "POR_CICLO", actor,
                 t("TC-M05-003b", check_ca("TC-M05-003b", estado="CA_NO_CALCULABLE", causa="SIN_PESO_INICIAL", score=50))),
        consumo("PREP C1 - Consumo C1 = 30 kg en D-5 07:00", 30, "dia_m5"),
        calcular(f"{p}TC-M05-004 - Calcular SEMANAL con ganancia de peso cero", "SEMANAL", actor,
                 t("TC-M05-004", check_ca("TC-M05-004", estado="CA_NO_CALCULABLE", causa="PESO_SIN_VARIACION_POSITIVA", score=100, alimento=30, ganancia=0) + [
                     "pm.test('TC-M05-004 - El mensaje informa los pesos (100 kg -> 100 kg) como pide el RF', () => pm.expect(String(r.mensaje || ''), 'mensaje: ' + r.mensaje).to.match(/100(\\.0+)?\\s*kg\\s*(→|->)\\s*100(\\.0+)?\\s*kg/));",
                 ])),
    ]


def g02_items(silencioso=False, actor_vet="tok_vet", actor="tok_admin"):
    """TC-M05-005 lo calcula el Veterinario (ficha); el resto no fija actor y va con el Administrador."""
    t = (lambda tc, lst: ok200(tc)) if silencioso else (lambda tc, lst: lst)
    p = "PREP " if silencioso else ""
    def alertas(nombre, tests):
        """GET /iot/alertas como Administrador (modulo3.alertas tiene RLS para el sandbox)."""
        return req(nombre, "GET", "{{base_url}}/iot/alertas?id_activo_biologico={{id_activo_a}}&tipo_alerta=CONVERSION_ALIMENTICIA",
                   token="tok_admin", tests=["pm.test('consulta de alertas (200)', () => pm.response.to.have.status(200));",
                                             "const filas = pm.response.code === 200 ? (pm.response.json().items || []) : [];",
                                             "console.log(JSON.stringify(filas));"] + tests)

    items = [
        pesaje("PREP P2 - Pesaje P2 = 113 kg en D-1 08:00", 113, "{{dia_m1}}T08:00:00-05:00"),
        calcular(f"{p}TC-M05-005 - Calcular SEMANAL como Veterinario (30 kg / 13 kg)", "SEMANAL", actor_vet,
                 t("TC-M05-005", check_ca("TC-M05-005", estado="CALCULADO", ca=2.3076, clase="ACEPTABLE", score=100, alimento=30, ganancia=13) + [
                     "pm.test('TC-M05-005 - Truncado, no redondeado (30/13 = 2.30769...; redondear daria 2.3077)', () => pm.expect(String(r.ca_calculado)).to.match(/^2\\.3076/));",
                     "pm.test('TC-M05-005 - tipo_calculo = MANUAL', () => pm.expect(r.tipo_calculo).to.eql('MANUAL'));",
                     "pm.test('TC-M05-005 - Tiempo de respuesta <= 2 s (CA-8): ' + pm.response.responseTime + ' ms', () => pm.expect(pm.response.responseTime).to.be.at.most(2000));",
                 ]), guardar_id="id_res_005"),
    ]
    if not silencioso:
        items.append(req("TC-M05-005 - El vigente SEMANAL es el recien calculado", "GET",
                         ICA + "/activos/{{id_activo_a}}/vigente?periodo=SEMANAL", token=actor_vet, tests=[
            "pm.test('TC-M05-005 - HTTP 200', () => pm.response.to.have.status(200));",
            "const v = pm.response.json();",
            "pm.test('TC-M05-005 - tiene_resultado y es el mismo id', () => { pm.expect(v.tiene_resultado).to.eql(true); pm.expect(String(v.resultado.id_resultado_ica)).to.eql(String(pm.collectionVariables.get('id_res_005'))); });",
        ]))
    items += [
        consumo("PREP C2 - Consumo C2 = 15.5 kg en D-4 07:00 (total 45.5)", 15.5, "dia_m4"),
        calcular(f"{p}TC-M05-006a - CA = 3.5000 (45.5 / 13)", "SEMANAL", actor,
                 t("TC-M05-006a", check_ca("TC-M05-006a", estado="CALCULADO", ca=3.5, clase="ACEPTABLE"))),
        consumo("PREP C3 - Consumo C3 = 0.01 kg en D-3 07:00 (total 45.51)", 0.01, "dia_m3"),
        calcular(f"{p}TC-M05-006b - CA = 3.5007 (45.51 / 13)", "SEMANAL", actor,
                 t("TC-M05-006b", check_ca("TC-M05-006b", estado="CALCULADO", ca=3.5007, clase="BAJA"))),
    ]
    if not silencioso:
        items.append(alertas("TC-M05-006 - Sin alerta de conversion alimenticia (ACEPTABLE/BAJA)",
                         ["pm.test('TC-M05-006 - 0 alertas CONVERSION_ALIMENTICIA para A', () => pm.expect(filas.length).to.eql(0));"]))
    items += [
        consumo("PREP C4 - Consumo C4 = 19.49 kg en D-2 07:00 (total 65.00)", 19.49, "dia_m2"),
        calcular(f"{p}TC-M05-007a - CA = 5.0000 (65.00 / 13)", "SEMANAL", actor,
                 t("TC-M05-007a", check_ca("TC-M05-007a", estado="CALCULADO", ca=5, clase="BAJA"))),
    ]
    if not silencioso:
        items.append(alertas("TC-M05-007a - CA 5.0000 no genera alerta",
                         ["pm.test('TC-M05-007a - 0 alertas CONVERSION_ALIMENTICIA para A', () => pm.expect(filas.length).to.eql(0));"]))
    items += [
        consumo("PREP C5 - Consumo C5 = 0.01 kg en D-1 07:00 (total 65.01)", 0.01, "dia_m1"),
        calcular(f"{p}TC-M05-007b - CA = 5.0007 (65.01 / 13) -> CRITICA", "SEMANAL", actor,
                 t("TC-M05-007b", check_ca("TC-M05-007b", estado="CALCULADO", ca=5.0007, clase="CRITICA"))),
    ]
    if not silencioso:
        items += [
            alertas("TC-M05-007b - Se crea 1 alerta CRITICA de conversion alimenticia", [
                "const al = filas[0] || {};",
                "pm.test('TC-M05-007b - exactamente 1 alerta CONVERSION_ALIMENTICIA', () => pm.expect(filas.length).to.eql(1));",
                "pm.test('TC-M05-007b - severidad CRITICO', () => pm.expect(al.severidad).to.eql('CRITICO'));",
                "pm.test('TC-M05-007b - origen_evento BACKEND (calculo manual)', () => pm.expect(al.origen_evento).to.eql('BACKEND'));",
                "pm.test('TC-M05-007b - valor = 5.0007', () => pm.expect(Number(al.valor)).to.eql(5.0007));",
            ]),
            req("TC-M05-007b - Notificacion de CA CRITICA al Productor y al Veterinario del activo", "GET",
                "{{base_url}}/notificaciones?tamano=50", token="tok_vet", tests=[
                "pm.test('TC-M05-007b - bandeja del Veterinario consultada (200)', () => pm.response.to.have.status(200));",
                "const it = pm.response.code === 200 ? (pm.response.json().items || []) : [];",
                "const hay = it.some(n => String(n.mensaje).includes('conversión alimenticia del activo ' + pm.variables.get('id_activo_a') + ' es CRÍTICA'));",
                "if (Number(pm.collectionVariables.get('vet_en_finca')) > 0) {",
                "  pm.test('TC-M05-007b - el Veterinario {{correo_veterinario}} recibio la notificacion CRITICA', () => pm.expect(hay).to.eql(true));",
                "} else {",
                "  pm.test('TC-M05-007b - el Veterinario {{correo_veterinario}} no esta asignado a la finca de A: no debe recibirla', () => pm.expect(hay).to.eql(false));",
                "}",
                "pm.test.skip('TC-M05-007b - Notificacion al Productor del activo (usuario ' + pm.collectionVariables.get('id_creador') + ', quien lo registro): no verificable, sin credencial de ese usuario y modulo1.notificaciones tiene RLS para el sandbox', () => {});",
            ]),
        ]
    items.append(calcular(f"{p}TC-M05-007c - Recalcular SEMANAL (sigue CRITICA)", "SEMANAL", actor,
                          t("TC-M05-007c", check_ca("TC-M05-007c", estado="CALCULADO", ca=5.0007, clase="CRITICA"))))
    if not silencioso:
        items.append(alertas("TC-M05-007c - La alerta abierta se consolida, no se duplica", [
            "pm.test('TC-M05-007c - sigue habiendo 1 sola alerta', () => pm.expect(filas.length).to.eql(1));",
            "pm.test('TC-M05-007c - frecuencia_evento = 2 (consolidada)', () => pm.expect(Number((filas[0] || {}).frecuencia_evento)).to.eql(2));",
        ]))
    items += [
        pesaje("PREP P3 - Pesaje P3 = 132.5 kg en D (ganancia 32.5)", 132.5, "{{dia_m0}}T{{hora_p3}}-05:00"),
        calcular(f"{p}TC-M05-008a - CA = 2.0003 (65.01 / 32.5)", "SEMANAL", actor,
                 t("TC-M05-008a", check_ca("TC-M05-008a", estado="CALCULADO", ca=2.0003, clase="ACEPTABLE", ganancia=32.5))),
        pesaje("PREP P4 - Pesaje P4 = 132.51 kg en D, despues de P3 (ganancia 32.51)", 132.51, "{{dia_m0}}T{{hora_p4}}-05:00"),
        calcular(f"{p}TC-M05-008b - CA = 1.9996 (65.01 / 32.51)", "SEMANAL", actor,
                 t("TC-M05-008b", check_ca("TC-M05-008b", estado="CALCULADO", ca=1.9996, clase="EXCELENTE", ganancia=32.51))),
    ]
    return items


def guardar_info(nombre, descripcion, items, var):
    return {"info": {"name": nombre, "description": descripcion,
                     "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
            "event": [{"listen": "prerequest", "script": {"type": "text/javascript", "exec": PRE_COLECCION}}],
            "variable": [{"key": k, "value": v} for k, v in var.items()],
            "item": items}


VARS = {
    "base_url": BASE_URL, "id_activo_a": "825", "id_tipo_alimento": "1", "id_activo_inactivo": "2",
    "run_id": "", "tok_admin": "", "tok_prod": "", "tok_vet": "", "tok_ing": "", "tok_cont": "",
}

PIE = (" Corre en el sandbox transaccional (todo se revierte al final). El activo A (id_activo_a) debe existir"
       " en TEST: el backend no acepta eventos anteriores al registro del activo y P1 va en D-20. Con"
       " id_activo_a=0 solo lista candidatos aptos. Los consumos 'de E2' (casos de RF-75) se reemplazan por"
       " C0 = 20 kg en D-10, dentro del ciclo y fuera de la semana.")


# ─────────────────────────────── G01 ───────────────────────────────
def g01():
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD, LOGIN_VET]),
        carpeta("1. TC-M05-001 Consultar ICA sin resultado previo", [
            # El batch nocturno calcula cada noche para todo activo ACTIVO: el unico activo ACTIVO sin ICA es uno recien
            # registrado. Se registra N (misma especie y area que A) dentro del sandbox; el rollback lo elimina.
            req("PREP - Registrar el activo N recien creado (solo dentro del sandbox)", "POST", "{{base_url}}/activos-biologicos",
                token="tok_admin",
                body="{\n  \"tipo_activo\": \"INDIVIDUAL\",\n  \"id_especie\": {{id_especie_a}},\n  \"fecha_inicio_ciclo\": \"{{dia_m0}}\",\n"
                     "  \"origen_financiero\": \"compra\",\n  \"costo_adquisicion\": 1000,\n"
                     "  \"soporte_documental\": \"QA TC-M05-001 (se revierte con el sandbox)\",\n  \"id_infraestructura\": {{id_infra_a}},\n"
                     "  \"identificador\": \"QA-M05-001-{{$timestamp}}\",\n  \"raza\": \"Cachama\",\n  \"sexo\": \"Macho\",\n"
                     "  \"fecha_nacimiento\": \"2025-01-01\"\n}",
                pre=["let a = {}; try { a = JSON.parse(pm.collectionVariables.get('pre_activo') || '{}'); } catch (e) {}",
                     "pm.collectionVariables.set('id_especie_a', a.id_especie || 0);"],
                tests=["pm.test('PREP - activo N registrado (200/201)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201]));",
                       "const n = [200, 201].includes(pm.response.code) ? pm.response.json() : {};",
                       "console.log(pm.response.text().slice(0, 1500));",
                       "pm.collectionVariables.set('id_activo_n', n.id_activo_biologico || n.id || 0);"]),
            req("TC-M05-001a - Vigente MENSUAL sin calculos previos", "GET", ICA + "/activos/{{id_activo_n}}/vigente?periodo=MENSUAL",
                token="tok_prod", tests=[
                    "pm.test('TC-M05-001a - HTTP 200 (no es error)', () => pm.response.to.have.status(200));",
                    "const v = pm.response.json();",
                    "pm.test('TC-M05-001a - tiene_resultado = false y resultado = null', () => { pm.expect(v.tiene_resultado).to.eql(false); pm.expect(v.resultado).to.eql(null); });",
                    "pm.test('TC-M05-001a - mensaje del RF', () => pm.expect(v.mensaje).to.eql('No hay un resultado ICA vigente para el activo y período indicados.'));",
                ]),
            req("TC-M05-001b - Historial vacio", "GET", ICA + "/activos/{{id_activo_n}}/historial", token="tok_prod", tests=[
                "pm.test('TC-M05-001b - HTTP 200', () => pm.response.to.have.status(200));",
                "pm.test('TC-M05-001b - total = 0', () => pm.expect(pm.response.json().total).to.eql(0));",
            ]),
            sql("TC-M05-001c - Las consultas no crean filas en resultado_ica",
                "SELECT count(*) AS n FROM modulo5.resultado_ica WHERE id_activo_biologico = {{id_activo_n}}",
                ["pm.test('TC-M05-001c - 0 filas de N en resultado_ica', () => pm.expect(Number(filas[0].n)).to.eql(0));"]),
        ]),
        carpeta("2. TC-M05-002 a 004 Calculos no calculables y jerarquia de causas", g01_items()[:1] + [
            sql("TC-M05-002 - Fila persistida en resultado_ica", """
                SELECT r.id_resultado_ica, r.es_vigente, r.tipo_calculo, r.id_usuario, r.periodo_evaluacion
                FROM modulo5.resultado_ica r WHERE r.id_activo_biologico = {{id_activo_a}} AND r.id_resultado_ica > {{max_resultado}}
            """, [
                "pm.test('TC-M05-002 - 1 fila nueva, SEMANAL, vigente, MANUAL, id_usuario del Productor', () => {",
                "  pm.expect(filas.length).to.eql(1);",
                "  pm.expect(filas[0].es_vigente).to.eql(true); pm.expect(filas[0].tipo_calculo).to.eql('MANUAL');",
                "  pm.expect(String(filas[0].id_usuario)).to.eql(String(pm.collectionVariables.get('id_productor')));",
                "});",
            ]),
        ] + g01_items()[1:6] + [
            sql("TC-M05-003c - El SEMANAL de TC-M05-002 dejo de ser vigente",
                "SELECT es_vigente FROM modulo5.resultado_ica WHERE id_resultado_ica = {{id_res_002}}",
                ["pm.test('TC-M05-003c - es_vigente = false', () => pm.expect((filas[0] || {}).es_vigente).to.eql(false));"]),
        ] + g01_items()[6:]),
        rollback(),
    ]
    return guardar_info(
        "RF-74 - TC-M05-G01 Consulta y calculo del ICA sin datos suficientes, con jerarquia de causas",
        "Automatiza TC-M05-001 a 004 sobre el activo A, en el orden E0 -> E1 -> E3 de la ficha." + PIE, items, VARS)


# ─────────────────────────────── G02 ───────────────────────────────
def g02():
    prep = g01_items(silencioso=True)
    prep_sin_calculos = [i for i in prep if not i["name"].startswith("PREP TC-")]
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD, LOGIN_VET]),
        carpeta("1. Preparacion (pesaje P1 y consumos C0 y C1, como en G01)", prep_sin_calculos),
        carpeta("2. TC-M05-005 a 008 Calculo exitoso y fronteras de clasificacion", g02_items()),
        rollback(),
    ]
    return guardar_info(
        "RF-74 - TC-M05-G02 Calculo exitoso del CA y fronteras de clasificacion",
        "Automatiza TC-M05-005 a 008: truncado a 4 decimales, tiempo de respuesta y fronteras 2.0 / 3.5 / 5.0"
        " con la alerta CRITICA y su consolidacion." + PIE, items, VARS)


# ─────────────────────────────── G03 ───────────────────────────────
def g03():
    foto_consumos = """
        SELECT id_consumo_alimeto, cantidad_suministrada, costo_total, estado_registro::text AS estado_registro
        FROM modulo5.registros_consumo_alimentos WHERE id_activo_biologico = {{id_activo_a}} ORDER BY 1
    """
    eventos_url = "{{base_url}}/activos-biologicos/{{id_activo_a}}/eventos"
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD, LOGIN_VET]),
        carpeta("1. Preparacion (todos los pasos de G01 y G02: 11 calculos SEMANAL y 1 POR_CICLO)",
                g01_items(silencioso=True, actor="tok_admin") + g02_items(silencioso=True, actor_vet="tok_admin")),
        carpeta("2. TC-M05-009 Historial y un unico vigente por periodo", [
            req("TC-M05-009a - Historial SEMANAL de A", "GET", ICA + "/activos/{{id_activo_a}}/historial?periodo=SEMANAL",
                token="tok_admin", tests=[
                    "pm.test('TC-M05-009a - HTTP 200', () => pm.response.to.have.status(200));",
                    "const h = pm.response.json(); const it = h.items || [];",
                    "const esp = 11 + Number(pm.collectionVariables.get('prev_semanal'));",
                    "pm.test('TC-M05-009a - todos los calculos SEMANAL: 11 de la corrida + ' + pm.collectionVariables.get('prev_semanal') + ' previos del batch', () => pm.expect(h.total).to.eql(esp));",
                    "pm.test('TC-M05-009a - del mas reciente al mas antiguo (fecha_calculo desc, id desc)', () => {",
                    "  for (let i = 1; i < it.length; i++) {",
                    "    const a = new Date(it[i-1].fecha_calculo), b = new Date(it[i].fecha_calculo);",
                    "    pm.expect(a > b || (a.getTime() === b.getTime() && it[i-1].id_resultado_ica > it[i].id_resultado_ica), 'posicion ' + i).to.eql(true);",
                    "  }",
                    "});",
                    "pm.test('TC-M05-009a - solo el primero (ultimo calculado) es vigente', () => { pm.expect(it[0].es_vigente).to.eql(true); pm.expect(it.slice(1).every(x => x.es_vigente === false)).to.eql(true); });",
                ]),
            sql("TC-M05-009b - 1 vigente por periodo y ningun calculo borrado", """
                SELECT periodo_evaluacion::text AS periodo, count(*) AS total, count(*) FILTER (WHERE es_vigente) AS vigentes
                FROM modulo5.resultado_ica WHERE id_activo_biologico = {{id_activo_a}} GROUP BY 1 ORDER BY 1
            """, [
                "const p = Object.fromEntries(filas.map(f => [f.periodo, f]));",
                "pm.test('TC-M05-009b - exactamente 1 vigente en cada periodo', () => filas.forEach(f => pm.expect(Number(f.vigentes), f.periodo).to.eql(1)));",
                "const ps = Number(pm.collectionVariables.get('prev_semanal')), pc = Number(pm.collectionVariables.get('prev_ciclo'));",
                "pm.test('TC-M05-009b - SEMANAL conserva los 11 calculos + ' + ps + ' previos (CA-5, FA-08)', () => pm.expect(Number((p.SEMANAL || {}).total)).to.eql(11 + ps));",
                "pm.test('TC-M05-009b - POR_CICLO conserva su calculo + ' + pc + ' previos', () => pm.expect(Number((p.POR_CICLO || {}).total)).to.eql(1 + pc));",
            ]),
        ]),
        carpeta("3. TC-M05-012 Auditoria de cada calculo", [
            sql("TC-M05-012 - auditorias_suministros de resultado_ica de A", """
                SELECT tipo_operacion::text AS tipo_operacion, id_usuario, datos_anteriores, datos_nuevos,
                       hash_integridad, resultado::text AS resultado
                FROM modulo5.auditorias_suministros
                WHERE entidad_afectada = 'resultado_ica' AND id_activo_biologico = {{id_activo_a}}
                  AND id_auditoria_suministro > {{max_auditoria}}
                ORDER BY fecha_evento, id_auditoria_suministro
            """, [
                "const ins = filas.filter(f => f.tipo_operacion === 'INSERT'), upd = filas.filter(f => f.tipo_operacion === 'UPDATE');",
                "const actores = [String(pm.collectionVariables.get('id_admin'))];",
                "const vs = Number(pm.collectionVariables.get('vig_semanal')), vc = Number(pm.collectionVariables.get('vig_ciclo'));",
                "pm.test('TC-M05-012 - 1 INSERT por cada calculo (12)', () => pm.expect(ins.length).to.eql(12));",
                "pm.test('TC-M05-012 - 1 UPDATE por cada vigente desmarcado (10 SEMANAL propios + ' + (vs + vc) + ' vigentes previos del batch)', () => pm.expect(upd.length).to.eql(10 + vs + vc));",
                "pm.test('TC-M05-012 - los INSERT llevan el id_usuario del actor (Administrador)', () => ins.forEach((f, i) => pm.expect(actores, 'INSERT ' + i + ' id_usuario=' + f.id_usuario).to.include(String(f.id_usuario))));",
                "pm.test('TC-M05-012 - los INSERT traen datos_nuevos con ca, clasificacion, causa y periodo', () => ins.forEach(f => { const d = typeof f.datos_nuevos === 'string' ? JSON.parse(f.datos_nuevos) : f.datos_nuevos; ['ca_calculado', 'clasificacion_ca', 'causa_no_calculo', 'periodo_evaluacion'].forEach(k => pm.expect(d).to.have.property(k)); }));",
                "pm.test('TC-M05-012 - los UPDATE pasan es_vigente de true a false', () => upd.forEach(f => { const a = typeof f.datos_anteriores === 'string' ? JSON.parse(f.datos_anteriores) : f.datos_anteriores; const n = typeof f.datos_nuevos === 'string' ? JSON.parse(f.datos_nuevos) : f.datos_nuevos; pm.expect(a.es_vigente).to.eql(true); pm.expect(n.es_vigente).to.eql(false); }));",
                "pm.test('TC-M05-012 - hash_integridad no nulo en todas las filas', () => filas.forEach((f, i) => pm.expect(f.hash_integridad, 'fila ' + i).to.not.eql(null)));",
                "pm.test('TC-M05-012 - resultado = EXITOSO en todas las filas', () => filas.forEach(f => pm.expect(f.resultado).to.eql('EXITOSO')));",
            ]),
        ]),
        carpeta("4. TC-M05-013 El calculo es de solo lectura sobre consumos y pesajes", [
            sql("TC-M05-013a - Foto de consumos ANTES", foto_consumos, [], guardar="consumos_antes"),
            req("TC-M05-013a - Foto de eventos (pesajes) ANTES", "GET", eventos_url, token="tok_admin", tests=[
                "pm.test('TC-M05-013a - HTTP 200', () => pm.response.to.have.status(200));",
                "pm.collectionVariables.set('eventos_antes', pm.response.text());",
            ]),
            calcular("TC-M05-013b - Calcular SEMANAL", "SEMANAL", "tok_admin", ok200("TC-M05-013b")),
            calcular("TC-M05-013b - Calcular MENSUAL", "MENSUAL", "tok_admin", ok200("TC-M05-013b")),
            calcular("TC-M05-013b - Calcular POR_CICLO", "POR_CICLO", "tok_admin", ok200("TC-M05-013b")),
            sql("TC-M05-013c - Foto de consumos DESPUES (identica)", foto_consumos, [
                "pm.test('TC-M05-013c - consumos sin cambios de cantidad, costo ni estado (CA-4)', () => pm.expect(JSON.stringify(filas)).to.eql(pm.collectionVariables.get('consumos_antes')));",
            ]),
            req("TC-M05-013c - Foto de eventos (pesajes) DESPUES (identica)", "GET", eventos_url, token="tok_admin", tests=[
                "pm.test('TC-M05-013c - HTTP 200', () => pm.response.to.have.status(200));",
                "pm.test('TC-M05-013c - eventos y pesajes sin cambios (CA-4)', () => pm.expect(pm.response.text()).to.eql(pm.collectionVariables.get('eventos_antes')));",
            ]),
        ]),
        rollback(),
    ]
    return guardar_info(
        "RF-74 - TC-M05-G03 Historial, unicidad del vigente, auditoria y solo lectura del calculo",
        "Automatiza TC-M05-009, 012 y 013 sobre lo que dejan los pasos de G01 y G02, repetidos en la preparacion"
        " de esta misma corrida. Nota: dentro del sandbox now() queda fijo en el inicio de la transaccion, asi que"
        " todos los calculos tienen la misma fecha_calculo y el orden 'mas reciente primero' lo da el id." + PIE,
        items, VARS)


# ─────────────────────────────── G04 ───────────────────────────────
def g04():
    contar = "SELECT count(*) AS n FROM modulo5.resultado_ica WHERE id_activo_biologico IN ({{id_activo_a}}, {{id_activo_inactivo}}, 999999)"

    def rechazo(tc, cuerpo, codigo, http, extra=None):
        t = [f"pm.test('{tc} - HTTP {http}', () => pm.response.to.have.status({http}));",
             "const e = pm.response.json(); console.log(pm.response.text());"]
        if codigo:
            t.append(f"pm.test('{tc} - code = {codigo}', () => pm.expect(e.error_code || e.code).to.eql('{codigo}'));")
        t += extra or []
        return req(f"{tc} - {cuerpo['_nombre']}", "POST", ICA + "/calcular", token="tok_admin",
                   body=cuerpo["_raw"], tests=t)

    def acceso(tc, rol, token, metodo, esperado):
        url = ICA + ("/calcular" if metodo == "POST" else "/activos/{{id_activo_a}}/vigente?periodo=SEMANAL")
        body = "{\n  \"id_activo_biologico\": {{id_activo_a}},\n  \"periodo_evaluacion\": \"SEMANAL\"\n}" if metodo == "POST" else None
        accion = "calcular" if metodo == "POST" else "consultar vigente"
        return req(f"{tc} - {rol}: {accion} -> {esperado}", metodo, url, token=token, body=body,
                   tests=[f"pm.test('{tc} - {rol} {accion}: HTTP {esperado}', () => pm.response.to.have.status({esperado}));",
                          "console.log(pm.response.text());"])

    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_VET, LOGIN_ING, LOGIN_CONT], nivel="activo"),
        carpeta("1. TC-M05-010 Validaciones de entrada y estado del activo", [
            req("TC-M05-010 - Confirmar que el activo {{id_activo_inactivo}} sigue INACTIVO", "GET",
                "{{base_url}}/activos-biologicos/{{id_activo_inactivo}}", token="tok_admin", tests=[
                    "pm.test('TC-M05-010 - HTTP 200', () => pm.response.to.have.status(200));",
                    "const a = pm.response.json();",
                    "pm.test('TC-M05-010 - el activo de control no esta ACTIVO (estado ' + a.nombre_estado + ')', () => pm.expect(a.id_estado).to.not.eql(1));",
                ]),
            sql("TC-M05-010 - Filas de resultado_ica antes de los rechazos", contar, [
                "pm.collectionVariables.set('n_res_antes', filas[0].n);"]),
            rechazo("TC-M05-010a", {"_nombre": "Activo inexistente (999999) -> 404",
                                    "_raw": "{\n  \"id_activo_biologico\": 999999,\n  \"periodo_evaluacion\": \"SEMANAL\"\n}"},
                    "ACTIVO_NO_ENCONTRADO", 404),
            rechazo("TC-M05-010b", {"_nombre": "Activo no ACTIVO -> 422 con el mensaje del E1",
                                    "_raw": "{\n  \"id_activo_biologico\": {{id_activo_inactivo}},\n  \"periodo_evaluacion\": \"SEMANAL\"\n}"},
                    "ACTIVO_NO_ACTIVO", 422, [
                        "pm.test('TC-M05-010b - mensaje del E1', () => pm.expect(e.message).to.eql('El activo biológico con ID ' + pm.variables.get('id_activo_inactivo') + ' no está en estado ACTIVO. El cálculo del CA solo aplica a activos en producción.'));"]),
            rechazo("TC-M05-010c", {"_nombre": "periodo_evaluacion ANUAL -> 400",
                                    "_raw": "{\n  \"id_activo_biologico\": {{id_activo_a}},\n  \"periodo_evaluacion\": \"ANUAL\"\n}"},
                    None, 400),
            rechazo("TC-M05-010d", {"_nombre": "id_activo_biologico = 0 -> 400",
                                    "_raw": "{\n  \"id_activo_biologico\": 0,\n  \"periodo_evaluacion\": \"SEMANAL\"\n}"},
                    None, 400),
            sql("TC-M05-010e - Ningun rechazo creo filas en resultado_ica", contar, [
                "pm.test('TC-M05-010e - mismas filas que antes de los rechazos', () => pm.expect(String(filas[0].n)).to.eql(String(pm.collectionVariables.get('n_res_antes'))));"]),
        ]),
        carpeta("2. TC-M05-011 Control de acceso por rol (recurso 49)", [
            acceso("TC-M05-011a", "Contador", "tok_cont", "POST", 403),
            acceso("TC-M05-011b", "Contador", "tok_cont", "GET", 403),
            acceso("TC-M05-011c", "Ingeniero de Campo", "tok_ing", "POST", 403),
            acceso("TC-M05-011d", "Ingeniero de Campo", "tok_ing", "GET", 403),
            acceso("TC-M05-011e", "Sin token", None, "POST", 401),
            acceso("TC-M05-011f", "Sin token", None, "GET", 401),
            sql("TC-M05-011g - Ningun rechazo creo filas en resultado_ica", contar, [
                "pm.test('TC-M05-011g - mismas filas que antes', () => pm.expect(String(filas[0].n)).to.eql(String(pm.collectionVariables.get('n_res_antes'))));"]),
            acceso("TC-M05-011h", "Veterinario (control positivo)", "tok_vet", "POST", 200),
            acceso("TC-M05-011i", "Veterinario (control positivo)", "tok_vet", "GET", 200),
        ]),
        rollback(),
    ]
    return guardar_info(
        "RF-74 - TC-M05-G04 Validaciones de entrada y control de acceso del calculo",
        "Automatiza TC-M05-010 y 011. Son rechazos que no escriben datos; el unico calculo real es el control"
        " positivo del Veterinario, que el rollback revierte. A solo necesita existir y estar ACTIVO."
        " id_activo_inactivo (por defecto 2) es el activo de control no ACTIVO.", items, VARS)


# ─────────────────────────────── G05 ───────────────────────────────
def g05():
    def panel(tc, rol, token, ruta, esperado, extra=None):
        return req(f"{tc} - {rol}: batch/{ruta} -> {esperado}", "GET", ICA + "/batch/" + ruta, token=token,
                   tests=[f"pm.test('{tc} - {rol} batch/{ruta}: HTTP {esperado}', () => pm.response.to.have.status({esperado}));",
                          "console.log(pm.response.text().slice(0, 3000));"] + (extra or []))

    estado_extra = [
        "if (pm.response.code === 200) {",
        "  const c = pm.response.json();",
        "  pm.test('TC-M05-014 - corridas de la mas reciente a la mas antigua', () => { for (let i = 1; i < c.length; i++) pm.expect(new Date(c[i-1].hora_inicio) >= new Date(c[i].hora_inicio), 'posicion ' + i).to.eql(true); });",
        "  pm.test('TC-M05-014 - cada corrida trae estado y hora de inicio', () => c.forEach(x => { pm.expect(['EN_EJECUCION', 'COMPLETADO', 'INTERRUMPIDO']).to.include(x.estado); pm.expect(x.hora_inicio).to.be.a('string'); }));",
        "  const colgada = c.find(x => x.estado === 'EN_EJECUCION' && (Date.now() - new Date(x.hora_inicio)) > 24 * 3600 * 1000);",
        "  pm.collectionVariables.set('id_en_ejecucion', (c.find(x => x.estado === 'EN_EJECUCION') || {}).id_ejecucion || '');",
        "  pm.collectionVariables.set('id_completado', (c.find(x => x.estado === 'COMPLETADO') || {}).id_ejecucion || '51');",
        "  pm.test('TC-M05-014 - el batch nocturno no esta detenido (sin corrida EN_EJECUCION de mas de 24 h)' + (colgada ? ': corrida ' + colgada.id_ejecucion + ' EN_EJECUCION desde ' + colgada.hora_inicio + ', ' + colgada.cantidad_activos_procesados + ' de ' + colgada.cantidad_activos_total + ' procesados' : ''), () => pm.expect(colgada, 'corrida colgada').to.eql(undefined));",
        "  const ultima = c.find(x => x.estado === 'COMPLETADO');",
        "  pm.test('TC-M05-014 - hay una corrida COMPLETADO en las ultimas 48 h' + (ultima ? ' (ultima: ' + ultima.hora_inicio + ')' : ''), () => pm.expect(ultima && (Date.now() - new Date(ultima.hora_inicio)) < 48 * 3600 * 1000).to.eql(true));",
        "}",
    ]
    ejecuciones = """
        SELECT id_ejecucion, estado::text AS estado, hora_corte, causa_interrupcion::text AS causa_interrupcion,
               id_usuario_interrupcion
        FROM modulo5.ejecuciones_batch_ica WHERE id_ejecucion = {{id_en_ejecucion}}
    """
    sin_corrida = ["if (!pm.collectionVariables.get('id_en_ejecucion')) pm.execution.skipRequest();"]
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD, LOGIN_VET]),
        carpeta("1. TC-M05-014 Panel del batch ICA (recurso 50)", [
            panel("TC-M05-014", "Administrador", "tok_admin", "estado", 200, estado_extra),
            panel("TC-M05-014", "Administrador", "tok_admin", "cola", 200),
            panel("TC-M05-014", "Administrador", "tok_admin", "fallos", 200),
            panel("TC-M05-014", "Productor", "tok_prod", "estado", 200),
            panel("TC-M05-014", "Productor", "tok_prod", "cola", 200),
            panel("TC-M05-014", "Productor", "tok_prod", "fallos", 200),
            panel("TC-M05-014", "Veterinario", "tok_vet", "estado", 403),
            panel("TC-M05-014", "Veterinario", "tok_vet", "cola", 403),
            panel("TC-M05-014", "Veterinario", "tok_vet", "fallos", 403),
        ]),
        carpeta("2. TC-M05-015 Control del batch", [
            # Solo se envía si hay una corrida EN_EJECUCION: sin ella el backend arrancaría un batch real sobre
            # todos los activos, y el batch escribe con sesiones propias (sesion_sistema) que el sandbox NO revierte.
            req("TC-M05-015a - Disparar con una corrida EN_EJECUCION -> 409", "POST", ICA + "/batch/ejecutar",
                token="tok_admin", body="{\n  \"solo_cola\": false\n}", pre=[
                    "if (!pm.collectionVariables.get('id_en_ejecucion')) {",
                    "  console.warn('No hay corrida EN_EJECUCION: no se dispara (arrancaria un batch real fuera del sandbox).');",
                    "  pm.execution.skipRequest();",
                    "}"],
                tests=["pm.test('TC-M05-015a - HTTP 409', () => pm.response.to.have.status(409));",
                       "pm.test('TC-M05-015a - code = BATCH_EN_CURSO', () => pm.expect(pm.response.json().error_code || pm.response.json().code).to.eql('BATCH_EN_CURSO'));"]),
            req("TC-M05-015b - Interrumpir una corrida COMPLETADO -> 422", "POST", ICA + "/batch/{{id_completado}}/interrumpir",
                token="tok_admin", body="{\n  \"motivo\": \"QA TC-M05-015\"\n}",
                tests=["pm.test('TC-M05-015b - HTTP 422', () => pm.response.to.have.status(422));",
                       "pm.test('TC-M05-015b - code = BATCH_NO_EN_EJECUCION', () => pm.expect(pm.response.json().error_code || pm.response.json().code).to.eql('BATCH_NO_EN_EJECUCION'));"]),
            req("TC-M05-015c - Interrumpir una corrida inexistente -> 404", "POST", ICA + "/batch/999999/interrumpir",
                token="tok_admin", body="{\n  \"motivo\": \"QA TC-M05-015\"\n}",
                tests=["pm.test('TC-M05-015c - HTTP 404', () => pm.response.to.have.status(404));",
                       "pm.test('TC-M05-015c - code = EJECUCION_NO_ENCONTRADA', () => pm.expect(pm.response.json().error_code || pm.response.json().code).to.eql('EJECUCION_NO_ENCONTRADA'));"]),
            # La interrupción sí queda dentro de la transacción: el rollback la revierte y la corrida real no cambia.
            req("TC-M05-015d - Interrumpir la corrida EN_EJECUCION (se revierte con el sandbox)", "POST",
                ICA + "/batch/{{id_en_ejecucion}}/interrumpir", token="tok_admin",
                body="{\n  \"motivo\": \"Corrida detenida desde 2026-10-13\"\n}", pre=sin_corrida, tests=[
                    "pm.test('TC-M05-015d - HTTP 200', () => pm.response.to.have.status(200));",
                    "const e = pm.response.code === 200 ? pm.response.json() : {}; console.log(pm.response.text());",
                    "pm.test('TC-M05-015d - estado INTERRUMPIDO', () => pm.expect(e.estado).to.eql('INTERRUMPIDO'));",
                    "pm.test('TC-M05-015d - hora_corte informada', () => pm.expect(e.hora_corte).to.be.a('string'));",
                    "pm.test('TC-M05-015d - causa_interrupcion = MANUAL (actual: ' + e.causa_interrupcion + ')', () => pm.expect(e.causa_interrupcion).to.eql('MANUAL'));",
                ]),
            sql("TC-M05-015d - Persistencia de la interrupcion", ejecuciones, [
                "const f = filas[0] || {};",
                "pm.test('TC-M05-015d - id_usuario_interrupcion = Administrador', () => pm.expect(String(f.id_usuario_interrupcion)).to.eql(String(pm.collectionVariables.get('id_admin'))));",
            ], pre=sin_corrida),
            req("TC-M05-015d - Notificacion BATCH_ICA_INTERRUMPIDO al Administrador", "GET",
                "{{base_url}}/notificaciones?tamano=20", token="tok_admin", pre=sin_corrida, tests=[
                "pm.test('TC-M05-015d - bandeja del Administrador (200)', () => pm.response.to.have.status(200));",
                "const it = pm.response.code === 200 ? (pm.response.json().items || []) : [];",
                "pm.test('TC-M05-015d - el Administrador recibio el aviso de corrida interrumpida', () => pm.expect(it.some(n => /interrump/i.test(n.mensaje) && /batch|c[aá]lculo/i.test(n.mensaje))).to.eql(true));",
            ]),
            req("TC-M05-015d - Notificacion BATCH_ICA_INTERRUMPIDO al Productor", "GET",
                "{{base_url}}/notificaciones?tamano=20", token="tok_prod", pre=sin_corrida, tests=[
                "pm.test('TC-M05-015d - bandeja del Productor (200)', () => pm.response.to.have.status(200));",
                "const it = pm.response.code === 200 ? (pm.response.json().items || []) : [];",
                "pm.test('TC-M05-015d - el Productor recibio el aviso de corrida interrumpida', () => pm.expect(it.some(n => /interrump/i.test(n.mensaje) && /batch|c[aá]lculo/i.test(n.mensaje))).to.eql(true));",
            ]),
            # La reactivacion se ejecuto FUERA del sandbox el 2026-11-09 con autorizacion del DBA (el batch usa sesiones
            # propias y dentro del sandbox escribiria datos reales): aqui solo se verifica, en lectura, la corrida que dejo.
            req("TC-M05-015e - Reactivacion (batch/ejecutar solo_cola=true, corrida {{id_reactivacion}} fuera del sandbox)", "GET",
                ICA + "/batch/estado", token="tok_admin", tests=[
                    "pm.test('TC-M05-015e - panel consultable (200)', () => pm.response.to.have.status(200));",
                    "const r = (pm.response.code === 200 ? pm.response.json() : []).find(x => String(x.id_ejecucion) === pm.collectionVariables.get('id_reactivacion')) || {};",
                    "pm.test('TC-M05-015e - la reactivacion quedo COMPLETADO, disparo MANUAL y sin fallidos', () => { pm.expect(r.estado).to.eql('COMPLETADO'); pm.expect(r.tipo_disparo).to.eql('MANUAL'); pm.expect(Number(r.cantidad_fallidos)).to.eql(0); pm.expect(r.hora_fin).to.be.a('string'); });",
                    "pm.test('TC-M05-015e - proceso toda su cola (0 pendientes)', () => pm.expect(Number(r.cantidad_activos_pendientes)).to.eql(0));",
                    "console.log('TC-M05-015e - POST batch/ejecutar {solo_cola:true} respondio 200 el 2026-11-09 09:22 UTC; ver evidencia_TC-M05-015e_fuera_sandbox.txt');",
                ]),
        ]),
        carpeta("3. TC-M05-016 Reintento manual y CA final al cerrar el ciclo", [
            pesaje("PREP P1 - Pesaje P1 = 100 kg en D-20 08:00", 100, "{{dia_m20}}T08:00:00-05:00"),
            consumo("PREP C1 - Consumo C1 = 30 kg en D-5 07:00", 30, "dia_m5"),
            pesaje("PREP P2 - Pesaje P2 = 113 kg en D-1 08:00", 113, "{{dia_m1}}T08:00:00-05:00"),
            calcular("PREP - Calculo manual SEMANAL previo (vigente a reemplazar)", "SEMANAL", "tok_admin",
                     ok200("PREP"), guardar_id="id_res_previo"),
            req("TC-M05-016a - Reintento manual del calculo de A", "POST", ICA + "/batch/activos/{{id_activo_a}}/reintentar",
                token="tok_admin", tests=[
                    "pm.test('TC-M05-016a - HTTP 200', () => pm.response.to.have.status(200));",
                    "const h = pm.response.code === 200 ? pm.response.json() : {items: []}; console.log(pm.response.text());",
                    "const per = h.items.map(x => x.periodo_evaluacion).sort();",
                    "pm.test('TC-M05-016a - recalcula SEMANAL, MENSUAL y POR_CICLO', () => pm.expect(per).to.eql(['MENSUAL', 'POR_CICLO', 'SEMANAL']));",
                    "pm.test('TC-M05-016a - tipo_calculo = REINTENTO_MANUAL en los 3', () => h.items.forEach(x => pm.expect(x.tipo_calculo, x.periodo_evaluacion).to.eql('REINTENTO_MANUAL')));",
                    "pm.test('TC-M05-016a - id_usuario del Administrador en los 3', () => h.items.forEach(x => pm.expect(String(x.id_usuario), x.periodo_evaluacion).to.eql(String(pm.collectionVariables.get('id_admin')))));",
                    "pm.test('TC-M05-016a - los 3 quedan vigentes', () => h.items.forEach(x => pm.expect(x.es_vigente, x.periodo_evaluacion).to.eql(true)));",
                ]),
            sql("TC-M05-016a - El vigente SEMANAL anterior quedo reemplazado",
                "SELECT es_vigente FROM modulo5.resultado_ica WHERE id_resultado_ica = {{id_res_previo}}",
                ["pm.test('TC-M05-016a - el calculo manual previo ya no es vigente', () => pm.expect((filas[0] || {}).es_vigente).to.eql(false));"]),
            req("TC-M05-016b - Cerrar el ciclo productivo de A (RF-38, se revierte con el sandbox)", "POST",
                "{{base_url}}/activos-biologicos/{{id_activo_a}}/cierre", token="tok_admin",
                body="{\n  \"fecha_cierre\": \"{{dia_m0}}\",\n  \"motivo_cierre\": \"venta\",\n  \"descripcion_cierre\": \"QA TC-M05-016\"\n}",
                tests=["pm.test('TC-M05-016b - cierre aceptado (200/201)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201]));",
                       "console.log(pm.response.text());"]),
            sql("TC-M05-016c - CA POR_CICLO final con fecha_fin = fecha de cierre", """
                SELECT id_resultado_ica, es_vigente, fecha_fin_periodo::text AS fecha_fin, tipo_calculo::text AS tipo_calculo,
                       estado_resultado::text AS estado_resultado, ca_calculado
                FROM modulo5.resultado_ica
                WHERE id_activo_biologico = {{id_activo_a}} AND periodo_evaluacion::text = 'POR_CICLO'
                ORDER BY id_resultado_ica DESC
            """, [
                "const f = filas[0] || {};",
                "pm.test('TC-M05-016c - hay un POR_CICLO nuevo despues del reintento', () => pm.expect(filas.length).to.be.at.least(2));",
                "pm.test('TC-M05-016c - el ultimo POR_CICLO es vigente', () => pm.expect(f.es_vigente).to.eql(true));",
                "pm.test('TC-M05-016c - fecha_fin_periodo = fecha de cierre (D)', () => pm.expect(f.fecha_fin).to.eql(pm.variables.get('dia_m0')));",
            ]),
        ]),
        rollback(),
    ]
    return guardar_info(
        "RF-74 - TC-M05-G05 Panel y control del motor batch ICA",
        "Automatiza TC-M05-014, 015 y 016. Lo que escribe la colección (interrupción de la corrida en curso,"
        " reintento, cierre de ciclo) queda dentro del sandbox y se revierte. La reactivación (batch/ejecutar con"
        " solo_cola=true) se ejecutó fuera del sandbox el 2026-11-09 con autorización del DBA (corrida 60), porque el"
        " batch procesa cada activo con sesiones propias; aquí se verifica en lectura." + PIE, items,
        {**VARS, "id_reactivacion": "60"})



# ─────────────────────────────── G06 (RF-74, activo POBLACIONAL B) ───────────────────────────────
def g06():
    pes = lambda nombre, prom, fecha: req(
        nombre, "POST", "{{base_url}}/activos-biologicos/{{id_activo_a}}/eventos/crecimiento", token="tok_admin",
        body="{\n  \"tipo_medicion\": \"PESO\",\n  \"valor_medicion\": {{biomasa_" + str(prom).replace('.', '_') + "}},\n"
             "  \"unidad_medida\": \"kg\",\n  \"tipo_agregacion\": \"PROMEDIO\",\n  \"nuevo_peso_promedio\": " + str(prom)
             + ",\n  \"cantidad_medida\": {{cantidad_actual_a}},\n  \"fecha\": \"" + fecha + "\",\n  \"descripcion\": \"QA TC-M05-017\"\n}",
        pre=[f"pm.collectionVariables.set('biomasa_{str(prom).replace('.', '_')}', ({prom} * Number(pm.collectionVariables.get('cantidad_actual_a'))).toFixed(2));"],
        tests=[f"pm.test('PREP - pesaje promedio {prom} kg registrado (200/201)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201]));",
               "if (![200, 201].includes(pm.response.code)) console.error(pm.response.text());"])
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD], tipo="POBLACIONAL", sin_ica=False),
        carpeta("1. Preparacion sobre B (pesajes promedio y consumo)", [
            pes("PREP - Pesaje promedio 1.00 kg en D-20 08:00", 1.00, "{{dia_m20}}T08:00:00-05:00"),
            consumo("PREP - Consumo 60 kg en D-3 07:00", 60, "dia_m3"),
            pes("PREP - Pesaje promedio 1.50 kg en D-1 08:00", 1.50, "{{dia_m1}}T08:00:00-05:00"),
        ]),
        carpeta("2. TC-M05-017 CA de activo POBLACIONAL", [
            calcular("TC-M05-017 - Calcular SEMANAL de B", "SEMANAL", "tok_prod", [
                "const n = Number(pm.collectionVariables.get('cantidad_actual_a'));",
                "pm.test('TC-M05-017 - HTTP 200', () => pm.response.to.have.status(200));",
                "pm.test('TC-M05-017 - estado_resultado = CALCULADO', () => pm.expect(r.estado_resultado).to.eql('CALCULADO'));",
                "pm.test('TC-M05-017 - ganancia_peso_kg = 0.5 x cantidad_actual (' + (0.5 * n) + ') (CA-6)', () => pm.expect(" + num('ganancia_peso_kg') + ").to.eql(0.5 * n));",
                "pm.test('TC-M05-017 - alimento_consumido_total_kg = 60', () => pm.expect(" + num('alimento_consumido_total_kg') + ").to.eql(60));",
                "pm.test('TC-M05-017 - ca_calculado = 60 / (0.5 x cantidad) truncado a 4 decimales', () => pm.expect(" + num('ca_calculado') + ").to.eql(Math.floor(60 / (0.5 * n) * 10000) / 10000));",
                "if (n === 100) pm.test('TC-M05-017 - con 100 individuos: ca = 1.2000 y EXCELENTE', () => { pm.expect(" + num('ca_calculado') + ").to.eql(1.2); pm.expect(r.clasificacion_ca).to.eql('EXCELENTE'); });",
            ]),
            req("TC-M05-017 - El vigente SEMANAL de B es el calculado", "GET", ICA + "/activos/{{id_activo_a}}/vigente?periodo=SEMANAL",
                token="tok_prod", tests=[
                    "pm.test('TC-M05-017 - HTTP 200', () => pm.response.to.have.status(200));",
                    "pm.test('TC-M05-017 - tiene_resultado = true y CALCULADO', () => { const v = pm.response.json(); pm.expect(v.tiene_resultado).to.eql(true); pm.expect((v.resultado || {}).estado_resultado).to.eql('CALCULADO'); });",
                ]),
        ]),
        rollback(),
    ]
    col = guardar_info(
        "RF-74 - TC-M05-G06 CA de activo POBLACIONAL",
        "Automatiza TC-M05-017 sobre el activo B (id_activo_b, POBLACIONAL, por defecto 328: 100 individuos, ciclo de una"
        " sola fase). Ganancia total = (promedio final - inicial) x cantidad_actual." + PIE, items,
        {**VARS, "id_activo_b": "328"})
    # El activo de este grupo es B: misma colección, otra variable (QA_ID_ACTIVO_A no la pisa).
    return json.loads(json.dumps(col, ensure_ascii=False).replace("id_activo_a", "id_activo_b").replace("activo A", "activo B"))


# ─────────────────────────────── G08 / G09 / G10 (RF-75, consumo de alimento) ───────────────────────────────
CONSUMO = "{{base_url}}/suministros/consumo-alimentos"
OBS_255 = "O" * 255
OBS_256 = "O" * 256
SQL_CONSUMOS_A = "SELECT count(*) AS n FROM modulo5.registros_consumo_alimentos WHERE id_activo_biologico = {{id_activo_a}}"


def post_consumo(nombre, token, *, activo="{{id_activo_a}}", tipo="{{id_tipo_alimento}}", fecha, hora, cantidad, costo,
                 obs=None, tests, guardar_id=None, pre=None):
    cuerpo = ("{\n  \"id_activo_biologico\": " + activo + ",\n  \"id_tipo_alimento\": " + tipo + ",\n  \"fecha_consumo\": \""
              + fecha + "\",\n  \"hora_suministro\": \"" + hora + "\",\n  \"cantidad_alimento\": " + str(cantidad)
              + ",\n  \"costo_unitario\": " + str(costo) + (",\n  \"observaciones\": \"" + obs + "\"" if obs is not None else "") + "\n}")
    t = ["const c = [200, 201].includes(pm.response.code) ? pm.response.json() : {};",
         "const e = pm.response.code >= 400 ? (() => { try { return pm.response.json(); } catch (x) { return {}; } })() : {};",
         "console.log(pm.response.text().slice(0, 1500));"]
    if guardar_id:
        t.append("if (c.id_consumo_alimeto) pm.collectionVariables.set('" + guardar_id + "', c.id_consumo_alimeto);")
    return req(nombre, "POST", CONSUMO, token=token, body=cuerpo, tests=t + tests, pre=pre)


def rechazo400(tc, texto=None):
    t = [f"pm.test('{tc} - HTTP 400', () => pm.response.to.have.status(400));"]
    if texto:
        t.append(f"pm.test('{tc} - mensaje: {texto[:60]}', () => pm.expect(pm.response.text()).to.include('{texto}'));")
    return t


def creado(tc, extra=None):
    return [f"pm.test('{tc} - HTTP 201', () => pm.response.to.have.status(201));",
            f"pm.test('{tc} - estado_registro = VALIDADO', () => pm.expect(c.estado_registro).to.eql('VALIDADO'));"] + (extra or [])


def codigo(tc, http, code):
    return [f"pm.test('{tc} - HTTP {http}', () => pm.response.to.have.status({http}));",
            f"pm.test('{tc} - code = {code}', () => pm.expect(e.error_code || e.code).to.eql('{code}'));"]


def contar(nombre, var=None, igual_a=None):
    t = []
    if var:
        t.append("pm.collectionVariables.set('" + var + "', filas[0].n);")
    if igual_a:
        t.append("pm.test('" + nombre.split(' - ')[0] + " - consumos de A: ' + filas[0].n + ' (esperado ' + pm.collectionVariables.get('" + igual_a[0] + "') + ' + " + str(igual_a[1]) + ")', () => pm.expect(Number(filas[0].n)).to.eql(Number(pm.collectionVariables.get('" + igual_a[0] + "')) + " + str(igual_a[1]) + "));")
    return sql(nombre, SQL_CONSUMOS_A, t)


def consumo_existente():
    """Un consumo VALIDADO real de TEST: para 405/403, que se rechazan sin tocarlo (no depende de crear uno)."""
    return req("PRE - Un consumo VALIDADO existente en TEST (para los rechazos)", "GET",
               CONSUMO + "?estado_registro=VALIDADO", token="tok_admin", tests=[
                   "pm.test('PRE - listado de consumos (200)', () => pm.response.to.have.status(200));",
                   "const it = pm.response.code === 200 ? (pm.response.json().items || []) : [];",
                   "pm.collectionVariables.set('id_consumo_existente', (it[0] || {}).id_consumo_alimeto || '');",
                   "pm.collectionVariables.set('consumo_existente', JSON.stringify(it[0] || {}));",
               ])


VARS_75 = {**VARS, "id_consumo_021": "", "id_consumo_existente": ""}


def g08():
    tc021 = post_consumo(
        "TC-M05-021 - Registrar consumo de A con costo ingresado y observaciones de 255", "tok_admin",
        fecha="{{dia_Fp1}}", hora="08:00:00", cantidad=12.5, costo=1800.50, obs=OBS_255, guardar_id="id_consumo_021",
        tests=creado("TC-M05-021", [
            "pm.test('TC-M05-021 - costo_total = 12.5 x 1800.50 = 22506.25 (costo ingresado, no el del catalogo)', () => pm.expect(Number(c.costo_total)).to.eql(22506.25));",
            "pm.test('TC-M05-021 - observacion guardada completa (255)', () => pm.expect(String(c.observacion || '').length).to.eql(255));",
            "pm.test('TC-M05-021 - fecha_registro del servidor', () => pm.expect(c.fecha_registro).to.be.a('string'));",
        ]))
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD]),
        carpeta("1. TC-M05-019 Catalogo de tipos de alimento", [
            req("TC-M05-019a - Catalogo (solo ACTIVO por defecto)", "GET", CONSUMO + "/tipos-alimento", token="tok_prod", tests=[
                "pm.test('TC-M05-019a - HTTP 200', () => pm.response.to.have.status(200));",
                "const it = pm.response.code === 200 ? pm.response.json().items : []; console.log(JSON.stringify(it));",
                "pm.test('TC-M05-019a - todos los elementos en estado ACTIVO', () => it.forEach(t => pm.expect(t.estado).to.eql('ACTIVO')));",
                "pm.test('TC-M05-019a - incluye el id 1 (kg)', () => { const t = it.find(x => x.id_tipo_alimento === 1) || {}; pm.expect(t.unidad_medida).to.eql('kg'); });",
                "pm.collectionVariables.set('n_tipos_activos', it.length);",
            ]),
            req("TC-M05-019b - Catalogo con solo_activos=false", "GET", CONSUMO + "/tipos-alimento?solo_activos=false", token="tok_prod", tests=[
                "pm.test('TC-M05-019b - HTTP 200', () => pm.response.to.have.status(200));",
                "const it = pm.response.code === 200 ? pm.response.json().items : []; console.log(JSON.stringify(it));",
                "pm.test('TC-M05-019b - incluye al menos los ACTIVO', () => pm.expect(it.length).to.be.at.least(Number(pm.collectionVariables.get('n_tipos_activos'))));",
                "pm.test('TC-M05-019b - los extra son CESADO', () => it.filter(t => t.estado !== 'ACTIVO').forEach(t => pm.expect(t.estado).to.eql('CESADO')));",
            ]),
        ]),
        carpeta("2. TC-M05-020 Fecha de consumo contra el inicio de la fase (F)", [
            contar("PRE - Consumos de A antes", var="n_cons_antes"),
            post_consumo("TC-M05-020a - fecha_consumo = F-1 -> 400", "tok_prod", fecha="{{dia_Fm1}}", hora="06:00:00",
                         cantidad=10, costo=2000, tests=codigo("TC-M05-020a", 400, "FECHA_ANTERIOR_A_FASE") + [
                "pm.test('TC-M05-020a - mensaje del E3', () => pm.expect(e.message).to.eql('La fecha de consumo ' + pm.variables.get('dia_Fm1') + ' es anterior a la fecha de inicio de la fase productiva activa del activo (' + pm.variables.get('dia_F') + '). Verifique la fecha ingresada.'));"]),
            post_consumo("TC-M05-020b - fecha_consumo = F -> 201 (primer consumo de A)", "tok_prod", fecha="{{dia_F}}",
                         hora="06:00:00", cantidad=10, costo=2000, tests=creado("TC-M05-020b", [
                "pm.test('TC-M05-020b - costo_total = 20000', () => pm.expect(Number(c.costo_total)).to.eql(20000));",
                "pm.test('TC-M05-020b - consumo_por_individuo_kg = null (INDIVIDUAL)', () => pm.expect(c.consumo_por_individuo_kg).to.eql(null));",
                "pm.test('TC-M05-020b - id_usuario del Productor', () => pm.expect(String(c.id_usuario)).to.eql(String(pm.collectionVariables.get('id_productor'))));"])),
        ]),
        carpeta("3. TC-M05-021 Consumo con costo calculado y observaciones", [
            tc021,
            req("TC-M05-021 - Aparece en el listado del activo", "GET", CONSUMO + "?id_activo_biologico={{id_activo_a}}", token="tok_admin", tests=[
                "pm.test('TC-M05-021 - HTTP 200', () => pm.response.to.have.status(200));",
                "const it = pm.response.code === 200 ? pm.response.json().items : [];",
                "pm.test('TC-M05-021 - el consumo esta en el listado', () => pm.expect(it.map(x => String(x.id_consumo_alimeto))).to.include(String(pm.collectionVariables.get('id_consumo_021'))));",
            ]),
            sql("TC-M05-021 - Fila espejo ALIMENTO en el ledger (registro_suministro, RF-78)", """
                SELECT rs.id_registro_suministro, rs.tipo_suministro::text AS tipo_suministro, rs.cantidad, rs.costo_registro
                FROM modulo5.registro_suministro rs
                JOIN modulo5.registros_consumo_alimentos c ON c.id_registro_rf75 = rs.id_registro_rf75
                WHERE c.id_consumo_alimeto = {{id_consumo_021}}
            """, ["pm.test('TC-M05-021 - 1 fila ALIMENTO en el ledger con la misma cantidad', () => { pm.expect(filas.length).to.eql(1); pm.expect(filas[0].tipo_suministro).to.eql('ALIMENTO'); pm.expect(Number(filas[0].cantidad)).to.eql(12.5); });"],
                pre=["if (!pm.collectionVariables.get('id_consumo_021')) { console.warn('TC-M05-021 no creo el consumo: no hay fila que buscar.'); pm.collectionVariables.set('id_consumo_021', 0); }"]),
        ]),
        carpeta("4. TC-M05-022 Valores limite de cantidad, costo y observaciones", [
            contar("PRE - Consumos de A antes de los limites", var="n_cons_lim"),
            post_consumo("TC-M05-022a - cantidad 0 -> 400", "tok_admin", fecha="{{dia_Fp2}}", hora="07:00:00", cantidad=0, costo=2000,
                         tests=rechazo400("TC-M05-022a", "La cantidad de alimento debe ser mayor a cero kilogramos. Valor ingresado: 0 kg.")),
            post_consumo("TC-M05-022b - cantidad -1 -> 400", "tok_admin", fecha="{{dia_Fp2}}", hora="07:10:00", cantidad=-1, costo=2000,
                         tests=rechazo400("TC-M05-022b", "La cantidad de alimento debe ser mayor a cero kilogramos. Valor ingresado: -1 kg.")),
            post_consumo("TC-M05-022c - cantidad 0.001 -> 201 (minimo de numeric(10,3))", "tok_admin", fecha="{{dia_Fp2}}", hora="07:20:00",
                         cantidad=0.001, costo=2000, tests=creado("TC-M05-022c", [
                             "pm.test('TC-M05-022c - cantidad_suministrada = 0.001', () => pm.expect(Number(c.cantidad_suministrada)).to.eql(0.001));"])),
            post_consumo("TC-M05-022d - cantidad 0.0004 -> respuesta controlada, nunca 500", "tok_admin", fecha="{{dia_Fp2}}", hora="07:30:00",
                         cantidad=0.0004, costo=2000, tests=[
                             "pm.test('TC-M05-022d - no responde 500 (HTTP ' + pm.response.code + ')', () => pm.expect(pm.response.code).to.be.below(500));",
                             "if (pm.response.code === 201) pm.test('TC-M05-022d - si se registra, no pierde la cantidad (no queda 0.000)', () => pm.expect(Number(c.cantidad_suministrada)).to.be.above(0));",
                             "pm.collectionVariables.set('n_022d', pm.response.code === 201 ? 1 : 0);"]),
            post_consumo("TC-M05-022e - costo_unitario 0 -> 400", "tok_admin", fecha="{{dia_Fp2}}", hora="07:40:00", cantidad=5, costo=0,
                         tests=rechazo400("TC-M05-022e", "El costo unitario del alimento debe ser mayor a cero.")),
            post_consumo("TC-M05-022f - observaciones de 256 caracteres -> 400", "tok_admin", fecha="{{dia_Fp2}}", hora="07:50:00",
                         cantidad=5, costo=2000, obs=OBS_256, tests=rechazo400("TC-M05-022f")),
            sql("TC-M05-022g - Ningun rechazo persiste", SQL_CONSUMOS_A, [
                "const esperado = Number(pm.collectionVariables.get('n_cons_lim')) + 1 + Number(pm.collectionVariables.get('n_022d') || 0);",
                "pm.test('TC-M05-022g - solo quedan los registros aceptados (' + esperado + ')', () => pm.expect(Number(filas[0].n)).to.eql(esperado));"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-75 - TC-M05-G08 Catalogo de alimentos, registro de consumo y valores limite",
                        "Automatiza TC-M05-019 a 022 sobre el activo A (por defecto 825, sin consumos previos). F es el dia"
                        " (Bogota) de inicio de la fase activa de A; el primer consumo va en F por la regla CA-10." + PIE.split(" Los consumos")[0],
                        items, VARS_75)


def g09():
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD]),
        carpeta("1. Preparacion (consumo de TC-M05-021 en F+1)", [
            post_consumo("PREP - Consumo 12.5 kg en F+1 08:00 (el de TC-M05-021)", "tok_admin", fecha="{{dia_Fp1}}", hora="08:00:00",
                         cantidad=12.5, costo=1800.50, guardar_id="id_consumo_021",
                         tests=["pm.test('PREP - consumo registrado (201)', () => pm.response.to.have.status(201));"]),
            consumo_existente(),
        ]),
        carpeta("2. TC-M05-023 Fecha de consumo futura", [
            post_consumo("TC-M05-023 - fecha_consumo = D+1 -> 400", "tok_admin", fecha="{{dia_p1}}", hora="10:00:00", cantidad=5,
                         costo=1000, tests=codigo("TC-M05-023", 400, "FECHA_FUTURA") + [
                "pm.test('TC-M05-023 - mensaje del E2', () => pm.expect(e.message).to.eql('La fecha de consumo ' + pm.variables.get('dia_p1') + ' es posterior a la fecha actual del sistema. No se permiten registros de consumo con fechas futuras.'));"]),
        ]),
        carpeta("3. TC-M05-024 Duplicado exacto y suministro subsecuente (CA-9, CA-10)", [
            contar("PRE - Consumos de A antes", var="n_cons_024"),
            post_consumo("TC-M05-024a - F+3 10:00, 4 kg -> 201", "tok_admin", fecha="{{dia_Fp3}}", hora="10:00:00", cantidad=4, costo=1000,
                         tests=creado("TC-M05-024a")),
            post_consumo("TC-M05-024b - Repetir F+3 10:00 -> 409 duplicado", "tok_admin", fecha="{{dia_Fp3}}", hora="10:00:00", cantidad=4,
                         costo=1000, tests=codigo("TC-M05-024b", 409, "CONSUMO_DUPLICADO") + [
                             "pm.test('TC-M05-024b - mensaje del E8 con activo, fecha y hora', () => { pm.expect(e.message).to.include('activo ' + pm.variables.get('id_activo_a')); pm.expect(e.message).to.include(pm.variables.get('dia_Fp3')); pm.expect(e.message).to.include('10:00'); });"]),
            post_consumo("TC-M05-024c - F+3 09:00 (anterior al ultimo) -> 409", "tok_admin", fecha="{{dia_Fp3}}", hora="09:00:00", cantidad=4,
                         costo=1000, tests=codigo("TC-M05-024c", 409, "CONSUMO_DUPLICADO") + [
                             "pm.test('TC-M05-024c - pide registrar despues de F+3 10:00', () => pm.expect(e.message).to.include(pm.variables.get('dia_Fp3') + ' 10:00'));"]),
            post_consumo("TC-M05-024d - F+3 11:00 (posterior) -> 201", "tok_admin", fecha="{{dia_Fp3}}", hora="11:00:00", cantidad=4, costo=1000,
                         tests=creado("TC-M05-024d")),
            sql("TC-M05-024e - Solo 2 filas nuevas VALIDADO", SQL_CONSUMOS_A, [
                "pm.test('TC-M05-024e - consumos de A = antes + 2', () => pm.expect(Number(filas[0].n)).to.eql(Number(pm.collectionVariables.get('n_cons_024')) + 2));"]),
        ]),
        carpeta("4. TC-M05-028 Inmutabilidad del consumo (405)", [
            req(f"TC-M05-028{l} - {m} sobre un consumo VALIDADO -> 405", m, CONSUMO + "/{{id_consumo_028}}", token="tok_admin",
                body=None if m == "DELETE" else "{\n  \"cantidad_alimento\": 99\n}",
                pre=["pm.collectionVariables.set('id_consumo_028', pm.collectionVariables.get('id_consumo_021') || pm.collectionVariables.get('id_consumo_existente'));"],
                tests=[f"pm.test('TC-M05-028{l} - HTTP 405', () => pm.response.to.have.status(405));",
                       "const e = (() => { try { return pm.response.json(); } catch (x) { return {}; } })(); console.log(pm.response.text());",
                       f"pm.test('TC-M05-028{l} - code = REGISTRO_INMUTABLE', () => pm.expect(e.error_code || e.code).to.eql('REGISTRO_INMUTABLE'));",
                       f"pm.test('TC-M05-028{l} - el mensaje indica anular y crear uno nuevo (E5)', () => pm.expect(String(e.message).toLowerCase()).to.match(/anul/));"])
            for l, m in (("a", "PUT"), ("b", "PATCH"), ("c", "DELETE"))
        ] + [
            req("TC-M05-028d - PUT sobre consumo inexistente -> 404", "PUT", CONSUMO + "/999999", token="tok_admin",
                body="{\n  \"cantidad_alimento\": 99\n}", tests=[
                    "pm.test('TC-M05-028d - HTTP 404', () => pm.response.to.have.status(404));",
                    "pm.test('TC-M05-028d - code = CONSUMO_NO_ENCONTRADO', () => { const e = pm.response.json(); pm.expect(e.error_code || e.code).to.eql('CONSUMO_NO_ENCONTRADO'); });"]),
            sql("TC-M05-028e - El consumo conserva cantidad, costo y estado", """
                SELECT cantidad_suministrada, costo_total, estado_registro::text AS estado_registro
                FROM modulo5.registros_consumo_alimentos WHERE id_consumo_alimeto = {{id_consumo_028}}
            """, ["pm.test('TC-M05-028e - sigue VALIDADO y sin la cantidad 99', () => { pm.expect(filas[0].estado_registro).to.eql('VALIDADO'); pm.expect(Number(filas[0].cantidad_suministrada)).to.not.eql(99); });"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-75 - TC-M05-G09 Reglas de fecha, duplicados e inmutabilidad del consumo",
                        "Automatiza TC-M05-023, 024 y 028. Si el consumo de TC-M05-021 no se puede crear, los 405 se prueban"
                        " sobre un consumo VALIDADO real de TEST (el rechazo no lo modifica)." + PIE.split(" Los consumos")[0],
                        items, VARS_75)


def g10():
    def est(i, esperado):
        return req(f"PRE - Estado actual del activo {i} (esperado {esperado})", "GET", "{{base_url}}/activos-biologicos/" + str(i),
                   token="tok_admin", tests=[f"pm.test('PRE - activo {i}: ' + (pm.response.code === 200 ? pm.response.json().nombre_estado : pm.response.code), () => pm.expect(pm.response.code === 200 ? pm.response.json().nombre_estado : null).to.eql('{esperado}'));"])

    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD, LOGIN_CONT], nivel="activo"),
        carpeta("0b. Datos de control", [est(2, "INACTIVO"), est(814, "CERRADO"), est(57, "ACTIVO"), consumo_existente(),
                                          sql("PRE - Consumos totales antes", "SELECT count(*) AS n FROM modulo5.registros_consumo_alimentos",
                                              ["pm.collectionVariables.set('n_total_antes', filas[0].n);"])]),
        carpeta("1. TC-M05-025 Activo no ACTIVO, inexistente o sin ciclo abierto", [
            post_consumo("TC-M05-025a - Activo 2 (INACTIVO) -> 422", "tok_admin", activo="2", fecha="{{dia_m1}}", hora="07:00:00",
                         cantidad=5, costo=1000, tests=codigo("TC-M05-025a", 422, "ACTIVO_ESTADO_INVALIDO") + [
                             "pm.test('TC-M05-025a - mensaje del E1 con estado INACTIVO', () => pm.expect(e.message).to.include('porque su estado actual es INACTIVO. Solo se permite el registro sobre activos en estado ACTIVO.'));"]),
            post_consumo("TC-M05-025b - Activo 814 (CERRADO) -> 422", "tok_admin", activo="814", fecha="{{dia_m1}}", hora="07:00:00",
                         cantidad=5, costo=1000, tests=codigo("TC-M05-025b", 422, "ACTIVO_ESTADO_INVALIDO") + [
                             "pm.test('TC-M05-025b - mensaje del E1 con estado CERRADO', () => pm.expect(e.message).to.include('porque su estado actual es CERRADO.'));"]),
            post_consumo("TC-M05-025c - Activo 999999 (no existe) -> 404", "tok_admin", activo="999999", fecha="{{dia_m1}}",
                         hora="07:00:00", cantidad=5, costo=1000, tests=codigo("TC-M05-025c", 404, "ACTIVO_NO_ENCONTRADO")),
            post_consumo("TC-M05-025d - Activo 57 (sin fase activa) -> 422", "tok_admin", activo="57", fecha="{{dia_m1}}", hora="07:00:00",
                         cantidad=5, costo=1000, tests=codigo("TC-M05-025d", 422, "CICLO_NO_ABIERTO")),
        ]),
        carpeta("2. TC-M05-026 Tipo de alimento inexistente o CESADO", [
            post_consumo("TC-M05-026a - id_tipo_alimento 999 -> 422", "tok_admin", tipo="999", fecha="{{dia_m1}}", hora="07:00:00",
                         cantidad=5, costo=1000, tests=codigo("TC-M05-026a", 422, "TIPO_ALIMENTO_NO_ENCONTRADO")),
            req("TC-M05-026b - Tipo de alimento CESADO: NO ejecutado", "GET", CONSUMO + "/tipos-alimento?solo_activos=false", token="tok_admin",
                tests=["pm.test('TC-M05-026b - catalogo consultado (200)', () => pm.response.to.have.status(200));",
                       "const ces = (pm.response.json().items || []).filter(t => t.estado === 'CESADO');",
                       "if (ces.length) { pm.collectionVariables.set('id_tipo_cesado', ces[0].id_tipo_alimento); }",
                       "else pm.test.skip('TC-M05-026b - BLOQUEADO: no existe ningun tipo de alimento CESADO en TEST y M05 no tiene endpoint de alta; lo debe crear el DBA', () => {});"]),
            post_consumo("TC-M05-026c - id del tipo CESADO -> 422", "tok_admin", tipo="{{id_tipo_cesado}}", fecha="{{dia_m1}}", hora="07:00:00",
                         cantidad=5, costo=1000, tests=codigo("TC-M05-026c", 422, "TIPO_ALIMENTO_INACTIVO"),
                         pre=["if (String(pm.collectionVariables.get('id_tipo_cesado')) === '0') pm.execution.skipRequest();"]),
        ]),
        carpeta("3. TC-M05-030 Permisos de registro y anulacion (recurso 47)", [
            req("TC-M05-030a - Productor intenta anular un consumo VALIDADO -> 403", "POST", CONSUMO + "/{{id_consumo_existente}}/anulacion",
                token="tok_prod", body="{\n  \"justificacion_anulacion\": \"QA TC-M05-030 intento sin permiso\"\n}",
                tests=["pm.test('TC-M05-030a - HTTP 403', () => pm.response.to.have.status(403));", "console.log(pm.response.text());"]),
            post_consumo("TC-M05-030b - Contador intenta registrar -> 403", "tok_cont", fecha="{{dia_m1}}", hora="07:00:00", cantidad=5,
                         costo=1000, tests=["pm.test('TC-M05-030b - HTTP 403', () => pm.response.to.have.status(403));"]),
            req("TC-M05-030c - Contador intenta consultar -> 403", "GET", CONSUMO, token="tok_cont",
                tests=["pm.test('TC-M05-030c - HTTP 403', () => pm.response.to.have.status(403));"]),
            post_consumo("TC-M05-030d - Sin token -> 401", None, fecha="{{dia_m1}}", hora="07:00:00", cantidad=5, costo=1000,
                         tests=["pm.test('TC-M05-030d - HTTP 401', () => pm.response.to.have.status(401));"]),
            sql("TC-M05-030e - Ningun rechazo cambio la BD", """
                SELECT (SELECT count(*) FROM modulo5.registros_consumo_alimentos) AS n,
                       (SELECT estado_registro::text FROM modulo5.registros_consumo_alimentos WHERE id_consumo_alimeto = {{id_consumo_existente}}) AS estado
            """, ["pm.test('TC-M05-030e - mismos consumos que al inicio', () => pm.expect(String(filas[0].n)).to.eql(String(pm.collectionVariables.get('n_total_antes'))));",
                  "pm.test('TC-M05-030e - el consumo que se intento anular sigue VALIDADO', () => pm.expect(filas[0].estado).to.eql('VALIDADO'));"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-75 - TC-M05-G10 Rechazos por activo, ciclo, tipo de alimento y permisos",
                        "Automatiza TC-M05-025, 026 y 030 sobre datos reales de TEST (activos 2, 814, 999999 y 57; A=825)."
                        " Son rechazos que no escriben. El paso con tipo CESADO queda bloqueado si el DBA no crea uno.",
                        items, {**VARS_75, "id_tipo_cesado": "0"})


LOGIN_GES = login("tok_ges", "correo_gestor", "contrasena_gestor", "Gestor de Granja", "id_gestor")
COSTEO = "{{base_url}}/suministros/costeo-directo"


def uuid_nuevo(var):
    return f"pm.collectionVariables.set('{var}', pm.variables.replaceIn('{{{{$guid}}}}'));"


def json_o_vacio():
    return "const e = (() => { try { return pm.response.json(); } catch (x) { return {}; } })(); console.log(pm.response.text().slice(0, 1500));"


def acumulado(nombre, var, token="tok_cont", tests=None):
    # Un ciclo sin suministros aun no tiene acumulado: 404 ACUMULADO_NO_ENCONTRADO equivale a acumulado 0.
    return req(nombre, "GET", COSTEO + "/acumulado/activo/{{id_activo_a}}", token=token, tests=[
        f"pm.test('{nombre.split(' - ')[0]} - acumulado del activo (200, o 404 ACUMULADO_NO_ENCONTRADO si el ciclo aun no tiene suministros)', () => {{ if (pm.response.code === 404) pm.expect(pm.response.json().error_code).to.eql('ACUMULADO_NO_ENCONTRADO'); else pm.response.to.have.status(200); }});",
        json_o_vacio(),
        f"pm.collectionVariables.set('{var}', JSON.stringify(pm.response.code === 200 ? e : {{acumulado_total_ciclo: 0, acumulado_por_categoria: {{}}}}));",
    ] + (tests or []))


def cat(var, categoria):
    return f"Number(((JSON.parse(pm.collectionVariables.get('{var}') || '{{}}').acumulado_por_categoria) || {{}})['{categoria}'] || 0)"


# ─────────────────────────────── G11 (RF-75, consumo POBLACIONAL) ───────────────────────────────
def g11():
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD], tipo="POBLACIONAL", sin_ica=False),
        carpeta("1. TC-M05-027a Consumo sobre B: consumo por individuo", [
            post_consumo("TC-M05-027a - 25 kg sobre B -> 201 con consumo_por_individuo_kg", "tok_admin", fecha="{{dia_m1}}",
                         hora="07:00:00", cantidad=25, costo=1000, tests=creado("TC-M05-027a", [
                             "const n = Number(pm.collectionVariables.get('cantidad_actual_a'));",
                             "pm.test('TC-M05-027a - consumo_por_individuo_kg = 25 / ' + n + ' (4 decimales; 0.2500 con 100) (CA-2)', () => pm.expect(Number(c.consumo_por_individuo_kg)).to.eql(Math.round(25 / n * 10000) / 10000));"])),
        ]),
        carpeta("2. TC-M05-027b POBLACIONAL sin individuos -> 422 (E7)", [
            req("PRE - Activo POBLACIONAL con cantidad 0/NULL ({{id_activo_pob_cero}})", "GET",
                "{{base_url}}/activos-biologicos/{{id_activo_pob_cero}}", token="tok_admin", tests=[
                    "pm.test('PRE - consultado (200)', () => pm.response.to.have.status(200));",
                    "const a = pm.response.code === 200 ? pm.response.json() : {}; const n = (a.detalle_poblacional || {}).cantidad_actual;",
                    "pm.test('PRE - es POBLACIONAL, ACTIVO y con cantidad_actual 0 o NULL (actual ' + n + ')', () => { pm.expect(a.tipo).to.eql('POBLACIONAL'); pm.expect(a.id_estado).to.eql(1); pm.expect(!n).to.eql(true); });"]),
            req("PRE - Ciclos productivos asignables", "GET", "{{base_url}}/activos-biologicos/{{id_activo_pob_cero}}/ciclos-productivos",
                token="tok_admin", tests=["pm.test('PRE - ciclos (200)', () => pm.response.to.have.status(200));",
                                          "pm.collectionVariables.set('id_ciclo_pob_cero', ((pm.response.json().items || [])[0] || {}).id_ciclo_productivo || '');"]),
            req("PRE - Abrir fase (solo dentro del sandbox: hoy no tiene y responderia CICLO_NO_ABIERTO)", "POST",
                "{{base_url}}/activos-biologicos/{{id_activo_pob_cero}}/fases", token="tok_admin",
                body="{\n  \"id_ciclo_productiva\": {{id_ciclo_pob_cero}},\n  \"fecha_inicio\": \"{{dia_m10}}T08:00:00-05:00\",\n  \"motivo_cambio\": \"QA TC-M05-027 (se revierte)\"\n}",
                tests=["pm.test('PRE - fase abierta (200/201)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201]));", "console.log(pm.response.text());"]),
            sql("PRE - Consumos del activo sin individuos antes",
                "SELECT count(*) AS n FROM modulo5.registros_consumo_alimentos WHERE id_activo_biologico = {{id_activo_pob_cero}}",
                ["pm.collectionVariables.set('n_pob_cero', filas[0].n);"]),
            post_consumo("TC-M05-027b - Consumo sobre POBLACIONAL sin individuos -> 422", "tok_admin", activo="{{id_activo_pob_cero}}",
                         fecha="{{dia_m1}}", hora="07:00:00", cantidad=25, costo=1000,
                         tests=codigo("TC-M05-027b", 422, "POBLACIONAL_SIN_CANTIDAD") + [
                             "pm.test('TC-M05-027b - mensaje del E7', () => pm.expect(String(e.message)).to.include('su cantidad actual de individuos es cero o no está definida'));"]),
            sql("TC-M05-027c - No se persiste", "SELECT count(*) AS n FROM modulo5.registros_consumo_alimentos WHERE id_activo_biologico = {{id_activo_pob_cero}}",
                ["pm.test('TC-M05-027c - mismos consumos que antes', () => pm.expect(String(filas[0].n)).to.eql(String(pm.collectionVariables.get('n_pob_cero'))));"]),
        ]),
        rollback(),
    ]
    col = guardar_info("RF-75 - TC-M05-G11 Consumo POBLACIONAL",
                       "Automatiza TC-M05-027. B (id_activo_b, por defecto 328, 100 individuos) para el consumo por individuo;"
                       " el activo id_activo_pob_cero (por defecto 462, POBLACIONAL ACTIVO con cantidad 0/NULL y sin fase) para"
                       " el E7: dentro del sandbox se le abre una fase para que el rechazo sea el del E7 y no CICLO_NO_ABIERTO.",
                       items, {**VARS_75, "id_activo_b": "328", "id_activo_pob_cero": "462"})
    return json.loads(json.dumps(col, ensure_ascii=False).replace("id_activo_a", "id_activo_b").replace("activo A", "activo B"))


# ─────────────────────────────── G12 (RF-75, anulación, consulta y auditoría) ───────────────────────────────
def g12():
    def anular(nombre, just, tests, id_var="{{id_consumo_029}}", token="tok_vet"):
        return req(nombre, "POST", CONSUMO + "/" + id_var + "/anulacion", token=token,
                   body="{\n  \"justificacion_anulacion\": \"" + just + "\"\n}", tests=[json_o_vacio()] + tests)

    filtros = [
        ("a", "por activo", "?id_activo_biologico={{id_activo_a}}", "x.id_activo_biologico === Number(pm.variables.get('id_activo_a'))"),
        ("b", "activo + rango F..F+3", "?id_activo_biologico={{id_activo_a}}&fecha_desde={{dia_F}}&fecha_hasta={{dia_Fp3}}",
         "x.fecha_consumo >= pm.variables.get('dia_F') && x.fecha_consumo <= pm.variables.get('dia_Fp3')"),
        ("c", "activo + rango + tipo_alimento=test", "?id_activo_biologico={{id_activo_a}}&fecha_desde={{dia_F}}&fecha_hasta={{dia_Fp3}}&tipo_alimento=test",
         "x.tipo_alimento === 'test'"),
        ("d", "activo + rango + tipo + estado ANULADO", "?id_activo_biologico={{id_activo_a}}&fecha_desde={{dia_F}}&fecha_hasta={{dia_Fp3}}&tipo_alimento=test&estado_registro=ANULADO",
         "x.estado_registro === 'ANULADO'"),
    ]
    consulta = [
        req(f"TC-M05-031{l} - Filtro {desc}", "GET", CONSUMO + q, token="tok_admin", tests=[
            f"pm.test('TC-M05-031{l} - HTTP 200', () => pm.response.to.have.status(200));",
            f"pm.test('TC-M05-031{l} - responde en <= 2 s (CA-8): ' + pm.response.responseTime + ' ms', () => pm.expect(pm.response.responseTime).to.be.at.most(2000));",
            "const h = pm.response.code === 200 ? pm.response.json() : {items: []}; const it = h.items || [];",
            f"pm.test('TC-M05-031{l} - total coincide con los items', () => pm.expect(h.total).to.eql(it.length));",
            f"pm.test('TC-M05-031{l} - todos cumplen el filtro', () => it.forEach(x => pm.expect({cond}, 'consumo ' + x.id_consumo_alimeto).to.eql(true)));",
            f"pm.test('TC-M05-031{l} - todos son del activo A', () => it.forEach(x => pm.expect(x.id_activo_biologico).to.eql(Number(pm.variables.get('id_activo_a')))));",
        ] + (["if (Number(pm.collectionVariables.get('anula_propio'))) pm.test('TC-M05-031d - devuelve solo el consumo anulado en TC-M05-029', () => pm.expect(it.map(x => String(x.id_consumo_alimeto))).to.eql([String(pm.collectionVariables.get('id_consumo_029'))]));",
              "else pm.test.skip('TC-M05-031d - el consumo anulado no es de A (no se pudieron crear consumos de A): no se verifica que aparezca en este filtro', () => {});"] if l == "d" else []))
        for l, desc, q, cond in filtros
    ]
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD, LOGIN_VET, LOGIN_CONT]),
        carpeta("1. Preparacion (consumos de E2 sobre A: F, F+1 y F+3 11:00)", [
            sql("PRE - Ultima auditoria antes de la corrida", "SELECT coalesce(max(id_auditoria_suministro), 0) AS m FROM modulo5.auditorias_suministros",
                ["pm.collectionVariables.set('max_auditoria', filas[0].m);"]),
            post_consumo("PREP - Consumo 10 kg en F 06:00 (Productor)", "tok_prod", fecha="{{dia_F}}", hora="06:00:00", cantidad=10, costo=2000,
                         guardar_id="id_c1", tests=["pm.test('PREP - consumo registrado (201)', () => pm.response.to.have.status(201));"]),
            post_consumo("PREP - Consumo 12.5 kg en F+1 08:00 (Administrador)", "tok_admin", fecha="{{dia_Fp1}}", hora="08:00:00", cantidad=12.5,
                         costo=1800.50, guardar_id="id_c2", tests=["pm.test('PREP - consumo registrado (201)', () => pm.response.to.have.status(201));"]),
            post_consumo("PREP - Consumo 4 kg en F+3 11:00 (el de TC-M05-024)", "tok_admin", fecha="{{dia_Fp3}}", hora="11:00:00", cantidad=4,
                         costo=1000, guardar_id="id_c3", tests=["pm.test('PREP - consumo registrado (201)', () => pm.response.to.have.status(201));"]),
            acumulado("PREP - Acumulado del ciclo de A antes de anular", "acum_antes"),
            consumo_existente(),
        ]),
        carpeta("2. TC-M05-029 Anular con justificacion y excluir de los calculos", [
            req("PRE - Consumo a anular", "GET", CONSUMO + "?id_activo_biologico={{id_activo_a}}", token="tok_admin",
                pre=["pm.collectionVariables.set('id_consumo_029', pm.collectionVariables.get('id_c3') || pm.collectionVariables.get('id_consumo_existente'));",
                     "pm.collectionVariables.set('anula_propio', pm.collectionVariables.get('id_c3') ? 1 : 0);"],
                tests=["pm.test('PRE - hay un consumo VALIDADO para anular', () => pm.expect(String(pm.collectionVariables.get('id_consumo_029'))).to.not.eql(''));",
                       "if (!pm.collectionVariables.get('id_c3')) console.warn('El consumo F+3 11:00 de A no se pudo crear: se anula el consumo VALIDADO real ' + pm.collectionVariables.get('id_consumo_029') + ' (el sandbox lo revierte).');"]),
            anular("TC-M05-029a - Justificacion de 19 caracteres -> 400", "J" * 19, codigo("TC-M05-029a", 400, "JUSTIFICACION_INSUFICIENTE")),
            anular("TC-M05-029b - Justificacion de 256 caracteres -> 400", "J" * 256, codigo("TC-M05-029b", 400, "JUSTIFICACION_MUY_LARGA")),
            anular("TC-M05-029c - Justificacion de 20 caracteres exactos -> 200", "J" * 20, [
                "pm.test('TC-M05-029c - HTTP 200', () => pm.response.to.have.status(200));",
                "pm.test('TC-M05-029c - estado ANULADO con fecha_hora_anulacion y justificacion', () => { pm.expect(e.estado_registro).to.eql('ANULADO'); pm.expect(e.fecha_hora_anulacion).to.be.a('string'); pm.expect(e.justificacion_anulacion).to.eql('" + "J" * 20 + "'); });"]),
            sql("TC-M05-029d - CORRECCION por -costo en el ledger (RF-78)", """
                SELECT corr.tipo_operacion::text AS tipo_operacion, corr.costo_registro, orig.costo_registro AS costo_original
                FROM modulo5.registro_suministro orig
                JOIN modulo5.registros_consumo_alimentos c ON c.id_registro_rf75 = orig.id_registro_rf75
                JOIN modulo5.registro_suministro corr ON corr.id_registro_original = orig.id_registro_suministro
                WHERE c.id_consumo_alimeto = {{id_consumo_029}}
            """, ["pm.test('TC-M05-029d - 1 CORRECCION por -costo del consumo', () => { pm.expect(filas.length).to.eql(1); pm.expect(filas[0].tipo_operacion).to.eql('CORRECCION'); pm.expect(Number(filas[0].costo_registro)).to.eql(-Number(filas[0].costo_original)); });"],
                pre=["if (!pm.collectionVariables.get('id_consumo_029')) pm.collectionVariables.set('id_consumo_029', 0);"]),
            acumulado("TC-M05-029e - El acumulado del ciclo baja el costo anulado", "acum_despues", tests=[
                "if (Number(pm.collectionVariables.get('anula_propio'))) pm.test('TC-M05-029e - ALIMENTO baja 4000 (4 kg x 1000)', () => pm.expect(" + cat("acum_despues", "ALIMENTO") + ").to.eql(" + cat("acum_antes", "ALIMENTO") + " - 4000));",
                "else pm.test.skip('TC-M05-029e - el consumo anulado no es de A: el acumulado de A no debe cambiar por esta anulacion', () => {});"]),
            anular("TC-M05-029f - Anular de nuevo -> 409", "J" * 20, codigo("TC-M05-029f", 409, "CONSUMO_YA_ANULADO")),
            anular("TC-M05-029g - Anular el consumo 4 (ya ANULADO en TEST) -> 409", "J" * 20, codigo("TC-M05-029g", 409, "CONSUMO_YA_ANULADO"), id_var="4"),
            anular("TC-M05-029h - Anular el id 999999 -> 404", "J" * 20, codigo("TC-M05-029h", 404, "CONSUMO_NO_ENCONTRADO"), id_var="999999"),
        ]),
        carpeta("3. TC-M05-031 Consulta de consumos con filtros", consulta),
        carpeta("4. TC-M05-032 Auditoria del registro y la anulacion", [
            sql("TC-M05-032 - auditorias_suministros de los consumos de A en esta corrida", """
                SELECT entidad_afectada, tipo_operacion::text AS tipo_operacion, id_usuario, datos_anteriores, datos_nuevos,
                       hash_integridad, resultado::text AS resultado
                FROM modulo5.auditorias_suministros
                WHERE entidad_afectada = 'registros_consumo_alimentos'
                  AND coalesce(datos_nuevos->>'id_activo_biologico', datos_anteriores->>'id_activo_biologico') = '{{id_activo_a}}'
                  AND id_auditoria_suministro > {{max_auditoria}}
                ORDER BY fecha_evento, id_auditoria_suministro
            """, [
                "const j = v => typeof v === 'string' ? JSON.parse(v) : (v || {});",
                "const ins = filas.filter(f => f.tipo_operacion === 'INSERT'), upd = filas.filter(f => f.tipo_operacion === 'UPDATE');",
                "const creados = ['id_c1', 'id_c2', 'id_c3'].map(k => pm.collectionVariables.get(k)).filter(Boolean);",
                "pm.test('TC-M05-032 - 1 INSERT por cada consumo creado (' + creados.length + ' de 3 se crearon)', () => { pm.expect(creados.length, 'consumos creados').to.eql(3); pm.expect(ins.length).to.eql(3); });",
                "pm.test('TC-M05-032 - los INSERT llevan el usuario que registro (Productor y Administrador)', () => pm.expect(ins.map(f => String(f.id_usuario)).sort()).to.eql([pm.collectionVariables.get('id_admin'), pm.collectionVariables.get('id_admin'), pm.collectionVariables.get('id_productor')].map(String).sort()));",
                "pm.test('TC-M05-032 - 1 UPDATE por la anulacion: VALIDADO -> ANULADO con justificacion', () => { pm.expect(upd.length).to.eql(1); const a = j(upd[0] && upd[0].datos_anteriores), n = j(upd[0] && upd[0].datos_nuevos); pm.expect(a.estado_registro).to.eql('VALIDADO'); pm.expect(n.estado_registro).to.eql('ANULADO'); pm.expect(n.justificacion_anulacion).to.eql('" + "J" * 20 + "'); });",
                "pm.test('TC-M05-032 - hash_integridad y resultado EXITOSO en todas', () => filas.forEach(f => { pm.expect(f.hash_integridad).to.not.eql(null); pm.expect(f.resultado).to.eql('EXITOSO'); }));",
            ]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-75 - TC-M05-G12 Anulacion, consulta y auditoria de consumos",
                        "Automatiza TC-M05-029, 031 y 032 sobre A (825). La preparacion recrea en esta corrida los consumos de E2"
                        " (F, F+1 y F+3 11:00). Justificacion: el codigo y la BD usan minimo 20 (el RF dice 50 en la Restriccion 5).",
                        items, VARS_75)


# ─────────────────────────────── G26 / G27 / G28 (RF-78, costeo directo) ───────────────────────────────
def post_costeo(nombre, token, *, uuid_var, campos, tests, pre=None, conservar_uuid=False):
    lineas = ['  "id_activo_biologico": {{id_activo_a}}', '  "id_idempotencia": "{{' + uuid_var + '}}"']
    lineas += [f'  "{k}": ' + json.dumps(v, ensure_ascii=False) for k, v in campos.items()]
    cuerpo = "{\n" + ",\n".join(lineas) + "\n}"
    pasos = list(pre or []) + ([] if conservar_uuid else [uuid_nuevo(uuid_var)])
    return req(nombre, "POST", COSTEO, token=token, body=cuerpo, pre=pasos, tests=[json_o_vacio()] + tests)


SERV = {"tipo_suministro": "SERVICIO_VETERINARIO", "cantidad": 1, "unidad_medida": "servicio", "precio_unitario": 150000,
        "fecha_aplicacion": "{{dia_m2}}", "justificacion_precio": "Tarifa de la factura del veterinario externo"}
SQL_LEDGER_GF = """
SELECT tipo_suministro::text AS tipo, sum(costo_registro) AS total FROM modulo5.registro_suministro
WHERE id_gestion_fases = {{id_fase_activa}} GROUP BY 1
"""


def g26():
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD, LOGIN_CONT, LOGIN_GES]),
        carpeta("1. Preparacion (consumos de E2/E3 sobre A y una anulacion)", [
            post_consumo("PREP - Consumo 10 kg x 2000 en F 06:00", "tok_admin", fecha="{{dia_F}}", hora="06:00:00", cantidad=10, costo=2000,
                         guardar_id="id_c1", tests=["pm.test('PREP - consumo registrado (201)', () => pm.response.to.have.status(201));"]),
            post_consumo("PREP - Consumo 4 kg x 1000 en F+3 11:00", "tok_admin", fecha="{{dia_Fp3}}", hora="11:00:00", cantidad=4, costo=1000,
                         guardar_id="id_c2", tests=["pm.test('PREP - consumo registrado (201)', () => pm.response.to.have.status(201));"]),
            req("PREP - Anular el consumo de F+3 (CORRECCION negativa)", "POST", CONSUMO + "/{{id_c2}}/anulacion", token="tok_admin",
                body="{\n  \"justificacion_anulacion\": \"QA TC-M05-033 anulacion de prueba\"\n}",
                pre=["if (!pm.collectionVariables.get('id_c2')) pm.collectionVariables.set('id_c2', 0);"],
                tests=["pm.test('PREP - consumo anulado (200)', () => pm.response.to.have.status(200));"]),
        ]),
        carpeta("2. TC-M05-033 Los consumos de RF-75 se acumulan solos (ALIMENTO)", [
            req("TC-M05-033 - Control: acumulado de A como Administrador", "GET", COSTEO + "/acumulado/activo/{{id_activo_a}}", token="tok_admin", tests=[
                json_o_vacio(),
                "pm.test('TC-M05-033 - control Administrador: ve el ciclo de A (200, o 404 ACUMULADO_NO_ENCONTRADO si aun no hay suministros; nunca CICLO_NO_ACTIVO)', () => pm.expect(e.error_code || 'OK').to.not.eql('CICLO_NO_ACTIVO'));"]),
            acumulado("TC-M05-033a - Acumulado del activo A (Contador)", "acum_033", tests=[
                "pm.test('TC-M05-033a - id_gestion_fases = GF_A y estado ACTIVO', () => { pm.expect(String(e.id_gestion_fases)).to.eql(String(pm.collectionVariables.get('id_fase_activa'))); pm.expect(e.estado).to.eql('ACTIVO'); });"]),
            sql("TC-M05-033b - ALIMENTO = suma de los consumos VALIDADOS (los anulados descontados)", """
                SELECT coalesce(sum(costo_total) FILTER (WHERE estado_registro::text = 'VALIDADO'), 0) AS validados,
                       count(*) AS n_consumos
                FROM modulo5.registros_consumo_alimentos WHERE id_activo_biologico = {{id_activo_a}}
            """, ["pm.test('TC-M05-033b - ALIMENTO del acumulado = ' + filas[0].validados, () => pm.expect(" + cat("acum_033", "ALIMENTO") + ").to.eql(Number(filas[0].validados)));",
                  "pm.test('TC-M05-033b - se crearon los 2 consumos de la preparacion', () => pm.expect(Number(filas[0].n_consumos)).to.eql(2));"]),
            sql("TC-M05-033c - Una fila REGISTRO ALIMENTO por consumo y una CORRECCION por la anulacion", """
                SELECT tipo_suministro::text AS tipo, tipo_operacion::text AS op, costo_registro, id_registro_rf75
                FROM modulo5.registro_suministro WHERE id_activo_biologico = {{id_activo_a}} AND tipo_suministro::text = 'ALIMENTO'
            """, ["pm.test('TC-M05-033c - 2 REGISTRO con id_registro_rf75', () => pm.expect(filas.filter(f => f.op === 'REGISTRO' && f.id_registro_rf75).length).to.eql(2));",
                  "pm.test('TC-M05-033c - 1 CORRECCION por -4000', () => { const c = filas.filter(f => f.op === 'CORRECCION'); pm.expect(c.length).to.eql(1); pm.expect(Number((c[0] || {}).costo_registro)).to.eql(-4000); });"]),
        ]),
        carpeta("3. TC-M05-034 SERVICIO_VETERINARIO e INSEMINACION con precio manual", [
            sql("PRE - Ultima auditoria", "SELECT coalesce(max(id_auditoria_suministro), 0) AS m FROM modulo5.auditorias_suministros",
                ["pm.collectionVariables.set('max_auditoria', filas[0].m);"]),
            post_costeo("TC-M05-034a - SERVICIO_VETERINARIO 1 x 150000 (Gestor de Granja)", "tok_ges", uuid_var="uuid_1", campos=SERV, tests=[
                "pm.test('TC-M05-034a - HTTP 200 (CA-14)', () => pm.response.to.have.status(200));",
                "const r = e.registro || {};",
                "pm.test('TC-M05-034a - estado REGISTRADO, costo 150000, MANUAL, REGISTRO, GF_A', () => { pm.expect(e.estado).to.eql('REGISTRADO'); pm.expect(Number(r.costo_registro)).to.eql(150000); pm.expect(r.origen_precio).to.eql('MANUAL'); pm.expect(r.tipo_operacion).to.eql('REGISTRO'); pm.expect(String(r.id_gestion_fases)).to.eql(String(pm.collectionVariables.get('id_fase_activa'))); });",
                "pm.collectionVariables.set('id_reg_serv', e.id_registro_suministro || '');",
                "pm.collectionVariables.set('body_034a', pm.request.body.raw);"]),
            post_costeo("TC-M05-034b - INSEMINACION 2 x 45000.50 (Gestor de Granja)", "tok_ges", uuid_var="uuid_2",
                        campos={**SERV, "tipo_suministro": "INSEMINACION", "cantidad": 2, "unidad_medida": "dosis", "precio_unitario": 45000.50,
                                "fecha_aplicacion": "{{dia_m1}}"}, tests=[
                "pm.test('TC-M05-034b - HTTP 200', () => pm.response.to.have.status(200));",
                "pm.test('TC-M05-034b - estado REGISTRADO y costo 90001', () => { pm.expect(e.estado).to.eql('REGISTRADO'); pm.expect(Number((e.registro || {}).costo_registro)).to.eql(90001); });"]),
            acumulado("TC-M05-034c - El acumulado sube esos valores", "acum_034", tests=[
                "pm.test('TC-M05-034c - SERVICIO_VETERINARIO sube 150000', () => pm.expect(" + cat("acum_034", "SERVICIO_VETERINARIO") + ").to.eql(" + cat("acum_033", "SERVICIO_VETERINARIO") + " + 150000));",
                "pm.test('TC-M05-034c - INSEMINACION sube 90001', () => pm.expect(" + cat("acum_034", "INSEMINACION") + ").to.eql(" + cat("acum_033", "INSEMINACION") + " + 90001));",
                "pm.test('TC-M05-034c - version_acumulado aumenta', () => pm.expect(Number(e.version_acumulado)).to.be.above(Number((JSON.parse(pm.collectionVariables.get('acum_033') || '{}')).version_acumulado || 0)));"]),
            sql("TC-M05-034d - SUMINISTRO_REGISTRADO en auditorias_suministros", """
                SELECT tipo_operacion::text AS op, resultado::text AS res FROM modulo5.auditorias_suministros
                WHERE id_auditoria_suministro > {{max_auditoria}} AND tipo_operacion::text = 'SUMINISTRO_REGISTRADO'
            """, ["pm.test('TC-M05-034d - 2 eventos SUMINISTRO_REGISTRADO', () => pm.expect(filas.length).to.eql(2));"]),
        ]),
        carpeta("4. TC-M05-035 Formula del acumulado total y por categoria (CA-3)", [
            req("TC-M05-035a - Acumulado del ciclo GF_A", "GET", COSTEO + "/acumulado/ciclo/{{id_fase_activa}}", token="tok_cont", tests=[
                "pm.test('TC-M05-035a - HTTP 200', () => pm.response.to.have.status(200));", json_o_vacio(),
                "pm.collectionVariables.set('acum_035', JSON.stringify(e));"]),
            sql("TC-M05-035b - Suma del ledger por categoria = acumulado", SQL_LEDGER_GF, [
                "const a = JSON.parse(pm.collectionVariables.get('acum_035') || '{}'); const cats = a.acumulado_por_categoria || {};",
                "const ledger = Object.fromEntries(filas.map(f => [f.tipo, Number(f.total)]));",
                "pm.test('TC-M05-035b - cada categoria = suma de sus registros', () => Object.keys(ledger).forEach(k => pm.expect(Number(cats[k] || 0), k).to.be.closeTo(ledger[k], 0.005)));",
                "pm.test('TC-M05-035b - total = suma de las categorias', () => pm.expect(Number(a.acumulado_total_ciclo)).to.be.closeTo(Object.values(cats).reduce((s, v) => s + Number(v), 0), 0.005));",
                "pm.test('TC-M05-035b - total = suma del ledger', () => pm.expect(Number(a.acumulado_total_ciclo)).to.be.closeTo(Object.values(ledger).reduce((s, v) => s + v, 0), 0.005));"]),
            sql("TC-M05-035c - Fila de modulo5.acumulado_ciclo", """
                SELECT acumulado_total_ciclo, acumulado_por_categoria FROM modulo5.acumulado_ciclo WHERE id_gestion_fases = {{id_fase_activa}}
            """, ["const a = JSON.parse(pm.collectionVariables.get('acum_035') || '{}');",
                  "pm.test('TC-M05-035c - la BD coincide con la API al centavo', () => pm.expect(Number((filas[0] || {}).acumulado_total_ciclo)).to.be.closeTo(Number(a.acumulado_total_ciclo), 0.005));"]),
        ]),
        carpeta("5. TC-M05-036 Precision del precio del ledger frente al costo del consumo", [
            post_consumo("TC-M05-036a - Consumo 3 kg x 1234.5678 (posterior al ultimo)", "tok_admin", fecha="{{dia_m0}}", hora="06:00:00",
                         cantidad=3, costo=1234.5678, guardar_id="id_c036", tests=creado("TC-M05-036a", [
                             "pm.test('TC-M05-036a - costo_total = 3703.7034', () => pm.expect(Number(c.costo_total)).to.eql(3703.7034));"])),
            sql("TC-M05-036b - El ledger acumula el mismo costo que el consumo", """
                SELECT c.costo_total, rs.precio_unitario_resuelto, rs.costo_registro
                FROM modulo5.registros_consumo_alimentos c JOIN modulo5.registro_suministro rs ON rs.id_registro_rf75 = c.id_registro_rf75
                WHERE c.id_consumo_alimeto = {{id_c036}}
            """, ["const f = filas[0] || {}; console.log('precio_unitario_resuelto=' + f.precio_unitario_resuelto);",
                  "pm.test('TC-M05-036b - costo_registro del ledger (' + f.costo_registro + ') = costo_total del consumo (' + f.costo_total + ')', () => pm.expect(Number(f.costo_registro)).to.eql(Number(f.costo_total)));"],
                pre=["if (!pm.collectionVariables.get('id_c036')) pm.collectionVariables.set('id_c036', 0);"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-78 - TC-M05-G26 Acumulacion del ciclo desde RF-75 y por registro directo",
                        "Automatiza TC-M05-033 a 036 sobre A (825) y su ciclo GF_A (fase activa). La preparacion recrea en esta corrida"
                        " los consumos de E2/E3 y una anulacion. Precio siempre MANUAL (no existe M40).", items,
                        {**VARS_75, "uuid_1": "", "uuid_2": ""})


def g27():
    def rech(tc, desc, campos, http, code, token="tok_ges"):
        return post_costeo(f"{tc} - {desc} -> {http}", token, uuid_var="uuid_r", campos=campos,
                           tests=codigo(tc, http, code) if code else [f"pm.test('{tc} - HTTP {http}', () => pm.response.to.have.status({http}));"])

    sin = lambda *ks: {k: v for k, v in SERV.items() if k not in ks}
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_GES, LOGIN_CONT]),
        carpeta("0b. Referencias", [
            acumulado("PRE - Acumulado de A antes de los rechazos", "acum_antes"),
            sql("PRE - Registros del ledger de A antes", "SELECT count(*) AS n FROM modulo5.registro_suministro WHERE id_activo_biologico = {{id_activo_a}}",
                ["pm.collectionVariables.set('n_ledger_antes', filas[0].n);"]),
        ]),
        carpeta("1. TC-M05-037 Validaciones del registro directo", [
            rech("TC-M05-037a", "tipo VACUNA (fuera del catalogo)", {**SERV, "tipo_suministro": "VACUNA"}, 422, "TIPO_SUMINISTRO_NO_CONFIGURADO"),
            rech("TC-M05-037b", "fecha_aplicacion F-1", {**SERV, "fecha_aplicacion": "{{dia_Fm1}}"}, 422, "FECHA_FUERA_DE_RANGO"),
            rech("TC-M05-037c", "fecha_aplicacion D+1", {**SERV, "fecha_aplicacion": "{{dia_p1}}"}, 422, "FECHA_FUERA_DE_RANGO"),
            rech("TC-M05-037d", "sin precio_unitario", sin("precio_unitario"), 422, "DATOS_SUMINISTRO_INCOMPLETOS"),
            rech("TC-M05-037e", "sin justificacion_precio", sin("justificacion_precio"), 422, "JUSTIFICACION_PRECIO_REQUERIDA"),
            rech("TC-M05-037f", "justificacion de 19 caracteres", {**SERV, "justificacion_precio": "J" * 19}, 422, "JUSTIFICACION_PRECIO_REQUERIDA"),
            rech("TC-M05-037g", "precio_unitario 0", {**SERV, "precio_unitario": 0}, 422, "COSTO_REGISTRO_INVALIDO"),
            rech("TC-M05-037h", "cantidad -1", {**SERV, "cantidad": -1}, 422, "COSTO_REGISTRO_INVALIDO"),
        ]),
        carpeta("2. TC-M05-038 Unidad de medida distinta a la de M09 (CA-13)", [
            # cantidad 7: si el sistema lo acepta (brecha), no debe chocar con el registro de TC-M05-034 (cantidad 1).
            post_costeo("TC-M05-038 - SERVICIO_VETERINARIO con unidad kg", "tok_ges", uuid_var="uuid_r", campos={**SERV, "unidad_medida": "kg", "cantidad": 7}, tests=[
                "pm.test('TC-M05-038 - Segun el RF: 422 por unidad distinta a la configurada en M09 (HTTP ' + pm.response.code + ')', () => pm.response.to.have.status(422));",
                "pm.test('TC-M05-038 - mensaje de unidad no coincidente', () => pm.expect(String(e.message)).to.include('no coincide con la unidad configurada'));"]),
        ]),
        carpeta("3. TC-M05-039 Duplicado por contenido e idempotencia", [
            post_costeo("PREP - Peticion 1 de TC-M05-034 (UUID-1)", "tok_ges", uuid_var="uuid_1", campos=SERV, tests=[
                "pm.test('PREP - registrada (200 REGISTRADO)', () => { pm.response.to.have.status(200); pm.expect(e.estado).to.eql('REGISTRADO'); });",
                "pm.collectionVariables.set('id_reg_serv', e.id_registro_suministro || '');"]),
            acumulado("PRE - Acumulado tras la peticion 1", "acum_039"),
            post_costeo("TC-M05-039a - Reenviar con el mismo UUID-1 -> 200 YA_PROCESADO", "tok_ges", uuid_var="uuid_1", campos=SERV,
                        conservar_uuid=True, tests=[
                "pm.test('TC-M05-039a - HTTP 200', () => pm.response.to.have.status(200));",
                "pm.test('TC-M05-039a - estado YA_PROCESADO con el mismo id_registro_suministro', () => { pm.expect(e.estado).to.eql('YA_PROCESADO'); pm.expect(String(e.id_registro_suministro)).to.eql(String(pm.collectionVariables.get('id_reg_serv'))); });"]),
            rech("TC-M05-039b", "mismo contenido con UUID nuevo", SERV, 409, "SUMINISTRO_DUPLICADO"),
            rech("TC-M05-039c", "mismo contenido con precio 150000.004", {**SERV, "precio_unitario": 150000.004}, 409, "SUMINISTRO_DUPLICADO"),
            acumulado("TC-M05-039d - El acumulado no cambio con los reintentos", "acum_039b", tests=[
                "pm.test('TC-M05-039d - total igual al de despues de la peticion 1', () => pm.expect(Number(e.acumulado_total_ciclo)).to.eql(Number((JSON.parse(pm.collectionVariables.get('acum_039') || '{}')).acumulado_total_ciclo)));"]),
        ]),
        carpeta("4. TC-M05-040 Referencias de ALIMENTO y MEDICAMENTO al ledger", [
            sql("PRE - Un id_registro_rf75 de A", """
                SELECT id_registro_rf75 FROM modulo5.registro_suministro
                WHERE id_activo_biologico = {{id_activo_a}} AND tipo_suministro::text = 'ALIMENTO' AND id_registro_rf75 IS NOT NULL
            """, ["pm.collectionVariables.set('rf75_a', (filas[0] || {}).id_registro_rf75 || '');",
                  "if (!filas.length) pm.test.skip('TC-M05-040a - A no tiene filas ALIMENTO en el ledger (sus consumos no se pueden crear hoy)', () => {});"]),
            post_costeo("TC-M05-040a - ALIMENTO con el id_registro_rf75 de A -> 200 YA_ACUMULADO", "tok_ges", uuid_var="uuid_r",
                        campos={"tipo_suministro": "ALIMENTO", "id_registro_rf75": "{{rf75_a}}"},
                        pre=["if (!pm.collectionVariables.get('rf75_a')) pm.execution.skipRequest();"], tests=[
                "pm.test('TC-M05-040a - HTTP 200 y YA_ACUMULADO', () => { pm.response.to.have.status(200); pm.expect(e.estado).to.eql('YA_ACUMULADO'); });"]),
            rech("TC-M05-040b", "ALIMENTO con UUID inexistente", {"tipo_suministro": "ALIMENTO", "id_registro_rf75": "00000000-0000-4000-8000-000000000075"}, 422, "REGISTRO_RF75_INVALIDO"),
            rech("TC-M05-040c", "ALIMENTO con el UUID del consumo del activo 57", {"tipo_suministro": "ALIMENTO", "id_registro_rf75": "511b18be-01d6-4a9e-8dec-bcfba3e2f5f9"}, 422, "REGISTRO_RF75_INVALIDO"),
            rech("TC-M05-040d", "MEDICAMENTO con UUID inexistente", {"tipo_suministro": "MEDICAMENTO", "id_registro_rf76": "00000000-0000-4000-8000-000000000076"}, 422, "REGISTRO_RF76_INVALIDO"),
        ]),
        carpeta("5. Ningun rechazo movio el acumulado", [
            sql("TC-M05-037i - Registros del ledger de A despues", "SELECT count(*) AS n FROM modulo5.registro_suministro WHERE id_activo_biologico = {{id_activo_a}}", [
                "const extra = pm.collectionVariables.get('id_reg_serv') ? 1 : 0;",
                "pm.test('TC-M05-037i - solo se agrego la peticion 1 (y la de unidad kg, si se acepto)', () => pm.expect(Number(filas[0].n)).to.be.within(Number(pm.collectionVariables.get('n_ledger_antes')) + extra, Number(pm.collectionVariables.get('n_ledger_antes')) + extra + 1));"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-78 - TC-M05-G27 Validaciones del registro directo, unidad M09, duplicados e idempotencia",
                        "Automatiza TC-M05-037 a 040 sobre A (825). La peticion 1 de TC-M05-034 se repite aqui como preparacion"
                        " (UUID-1) porque el sandbox revierte G26.", items, {**VARS_75, "uuid_1": "", "uuid_r": "", "rf75_a": ""})


def g28():
    def corr(tc, desc, original, campos, tests=None, token="tok_cont", pre=None):
        cuerpo = {"id_idempotencia": "{{uuid_c}}", "cantidad": 1, "precio_unitario": -30000,
                  "justificacion_precio": "Descuento acordado en la factura", "motivo_correccion": "Ajuste por descuento comercial de la factura"}
        cuerpo.update(campos)
        return req(f"{tc} - {desc}", "POST", COSTEO + "/" + original + "/correccion", token=token,
                   body=json.dumps(cuerpo, ensure_ascii=False, indent=2), pre=(pre or []) + [uuid_nuevo("uuid_c")],
                   tests=[json_o_vacio()] + tests)

    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_GES, LOGIN_CONT]),
        carpeta("1. Preparacion (registro SERVICIO_VETERINARIO de TC-M05-034)", [
            post_costeo("PREP - SERVICIO_VETERINARIO 1 x 150000", "tok_ges", uuid_var="uuid_1", campos=SERV, tests=[
                "pm.test('PREP - registrado (200)', () => pm.response.to.have.status(200));",
                "pm.collectionVariables.set('id_reg_serv', e.id_registro_suministro || '');"]),
            acumulado("PREP - Acumulado antes de corregir", "acum_antes"),
            sql("PRE - Un REGISTRO real de un ciclo ACTIVO (para los rechazos 042d y 042e)", """
                SELECT rs.id_registro_suministro::text AS id FROM modulo5.registro_suministro rs
                JOIN modulo5.acumulado_ciclo ac ON ac.id_gestion_fases = rs.id_gestion_fases
                WHERE rs.tipo_operacion::text = 'REGISTRO' AND ac.estado::text = 'ACTIVO'
                ORDER BY rs.fecha_registro DESC
            """, ["pm.collectionVariables.set('id_reg_real', (filas[0] || {}).id || '');",
                  "pm.collectionVariables.set('id_reg_obj', pm.collectionVariables.get('id_reg_serv') || (filas[0] || {}).id || '');"]),
        ]),
        carpeta("2. TC-M05-041 Correccion aditiva y negativa", [
            corr("TC-M05-041a", "Correccion -30000 sobre el SERVICIO_VETERINARIO (Contador) -> 200", "{{id_reg_serv}}", {}, [
                "pm.test('TC-M05-041a - HTTP 200', () => pm.response.to.have.status(200));",
                "const r = e.registro || {};",
                "pm.test('TC-M05-041a - fila CORRECCION con id_registro_original, motivo y costo -30000', () => { pm.expect(r.tipo_operacion).to.eql('CORRECCION'); pm.expect(String(r.id_registro_original)).to.eql(String(pm.collectionVariables.get('id_reg_serv'))); pm.expect(r.motivo_correccion).to.eql('Ajuste por descuento comercial de la factura'); pm.expect(Number(r.costo_registro)).to.eql(-30000); });"],
                pre=["if (!pm.collectionVariables.get('id_reg_serv')) pm.collectionVariables.set('id_reg_serv', '00000000-0000-4000-8000-000000000000');"]),
            acumulado("TC-M05-041b - SERVICIO_VETERINARIO y total bajan 30000", "acum_041", tests=[
                "pm.test('TC-M05-041b - SERVICIO_VETERINARIO baja 30000', () => pm.expect(" + cat("acum_041", "SERVICIO_VETERINARIO") + ").to.eql(" + cat("acum_antes", "SERVICIO_VETERINARIO") + " - 30000));",
                "pm.test('TC-M05-041b - total baja 30000', () => pm.expect(Number(e.acumulado_total_ciclo)).to.eql(Number((JSON.parse(pm.collectionVariables.get('acum_antes') || '{}')).acumulado_total_ciclo) - 30000));"]),
            sql("TC-M05-041c - El registro original no cambio y hay SUMINISTRO_CORREGIDO", """
                SELECT (SELECT costo_registro FROM modulo5.registro_suministro WHERE id_registro_suministro::text = '{{id_reg_serv}}') AS costo_original,
                       (SELECT count(*) FROM modulo5.auditorias_suministros WHERE tipo_operacion::text = 'SUMINISTRO_CORREGIDO'
                          AND id_activo_biologico = {{id_activo_a}}) AS corregidos
            """, ["pm.test('TC-M05-041c - el original sigue en 150000', () => pm.expect(Number(filas[0].costo_original)).to.eql(150000));",
                  "pm.test('TC-M05-041c - SUMINISTRO_CORREGIDO en auditoria', () => pm.expect(Number(filas[0].corregidos)).to.be.at.least(1));"]),
            corr("TC-M05-041d", "Correccion -99999999 (dejaria el total negativo) -> 422", "{{id_reg_serv}}", {"precio_unitario": -99999999}, [
                "pm.test('TC-M05-041d - HTTP 422 (FA-09)', () => pm.response.to.have.status(422));"]),
            acumulado("TC-M05-041e - Nada cambio con el rechazo", "acum_041e", tests=[
                "pm.test('TC-M05-041e - total igual al de TC-M05-041b', () => pm.expect(Number(e.acumulado_total_ciclo)).to.eql(Number((JSON.parse(pm.collectionVariables.get('acum_041') || '{}')).acumulado_total_ciclo)));"]),
        ]),
        carpeta("3. TC-M05-042 Rechazos de la correccion", [
            corr("TC-M05-042a", "Original inexistente -> 422", "00000000-0000-4000-8000-000000000042", {}, codigo("TC-M05-042a", 422, "REGISTRO_ORIGINAL_INVALIDO")),
            corr("TC-M05-042b", "Original que ya es CORRECCION (ciclo 33) -> 422", "7579506c-bbfa-42d6-a0cf-e185f0bbc409", {}, codigo("TC-M05-042b", 422, "CORRECCION_SOBRE_CORRECCION")),
            corr("TC-M05-042c", "REGISTRO del ciclo 33 (cerrado y CONSOLIDADO) -> 409", "d4738b05-e5a8-47ab-ae53-afa50c8d1d39", {}, codigo("TC-M05-042c", 409, "CICLO_NO_ACTIVO")),
            corr("TC-M05-042d", "Motivo de 19 caracteres -> 400", "{{id_reg_obj}}", {"motivo_correccion": "M" * 19}, token="tok_admin", tests=[
                "pm.test('TC-M05-042d - HTTP 400', () => pm.response.to.have.status(400));"]),
            corr("TC-M05-042e", "precio_unitario 0 sobre el registro de A -> 422", "{{id_reg_serv}}", {"precio_unitario": 0},
                 codigo("TC-M05-042e", 422, "CORRECCION_INVALIDA"),
                 pre=["if (!pm.collectionVariables.get('id_reg_serv') || pm.collectionVariables.get('id_reg_serv').startsWith('00000000')) {",
                      "  console.warn('TC-M05-042e BLOQUEADO: el registro SERVICIO_VETERINARIO de A no se pudo crear; con un registro ajeno el rechazo seria otro (CICLO_NO_ACTIVO).');",
                      "  pm.execution.skipRequest();",
                      "}"]),
            req("TC-M05-042e - Estado del caso", "GET", COSTEO + "/acumulado/ciclo/{{id_fase_activa}}", token="tok_admin", tests=[
                "if (!pm.collectionVariables.get('id_reg_serv') || pm.collectionVariables.get('id_reg_serv').startsWith('00000000')) pm.test.skip('TC-M05-042e - BLOQUEADO: requiere el registro SERVICIO_VETERINARIO de A, que hoy responde 500', () => {});"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-78 - TC-M05-G28 Correcciones del ledger y sus rechazos",
                        "Automatiza TC-M05-041 y 042 sobre A (825). El registro SERVICIO_VETERINARIO de TC-M05-034 se crea en esta"
                        " misma corrida. Los UUID del ciclo 33 (activo 57) son datos reales de TEST; los rechazos no escriben.",
                        items, {**VARS_75, "uuid_1": "", "uuid_c": "", "id_reg_serv": ""})


LOGIN_REV = login("tok_rev", "correo_revisor", "contrasena_revisor", "Revisor Fiscal", "id_revisor")
NIC41 = "{{base_url}}/suministros/nic41"
SIN_CODIGOS = ("pm.test('{tc} - el mensaje visible no muestra codigos internos (RF-xx), regla de textos visibles de CLAUDE.md', "
               "() => pm.expect(String(e.message || '')).to.not.match(/\\bRF-?\\d+/));")


def sin_codigos(tc):
    return SIN_CODIGOS.replace("{tc}", tc)


# ─────────────────────────────── G29 (RF-78) ───────────────────────────────
def g29():
    def acceso(tc, rol, token, esperado, uuid_var="uuid_p"):
        # Cantidad distinta por rol: si un rol pasa la autorizacion, el siguiente no debe chocar con su registro (409 duplicado).
        cant = {"tok_prod": 1, "tok_vet": 2, "tok_ing": 3}.get(token, 4)
        return post_costeo(f"{tc} - {rol} registra costeo -> {esperado} (segun el RF)", token, uuid_var=uuid_var, campos={**SERV, "cantidad": cant}, tests=[
            f"pm.test('{tc} - {rol}: HTTP {esperado} segun el RNF-05 (actual ' + pm.response.code + ')', () => pm.response.to.have.status({esperado}));"])

    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD, LOGIN_VET, LOGIN_ING, LOGIN_CONT, LOGIN_GES, LOGIN_REV], nivel="activo"),
        carpeta("1. TC-M05-043 Ciclo inexistente o inactivo", [
            req("TC-M05-043a - Registrar costeo sobre el activo 57 (sin fase activa) -> 409", "POST", COSTEO, token="tok_ges",
                body=json.dumps({"id_activo_biologico": 57, "id_idempotencia": "{{uuid_57}}", **{k: v for k, v in SERV.items()}}, ensure_ascii=False, indent=2),
                pre=[uuid_nuevo("uuid_57")], tests=[json_o_vacio()] + codigo("TC-M05-043a", 409, "CICLO_NO_ACTIVO") + [
                    "pm.test('TC-M05-043a - mensaje del E1', () => pm.expect(String(e.message)).to.include('No existe un ciclo productivo activo para el activo 57'));"]),
            req("TC-M05-043b - Acumulado del activo 57 -> 404", "GET", COSTEO + "/acumulado/activo/57", token="tok_cont",
                tests=[json_o_vacio()] + codigo("TC-M05-043b", 404, "CICLO_NO_ACTIVO")),
            req("TC-M05-043c - Acumulado del ciclo 33 (cerrado y consolidado) -> 200", "GET", COSTEO + "/acumulado/ciclo/33", token="tok_cont", tests=[
                json_o_vacio(), "pm.test('TC-M05-043c - HTTP 200', () => pm.response.to.have.status(200));",
                "pm.test('TC-M05-043c - estado CONSOLIDADO', () => pm.expect(e.estado).to.eql('CONSOLIDADO'));",
                "pm.test('TC-M05-043c - acumulado_total_ciclo 120000.0100 (valor en TEST el 2026-11-05)', () => pm.expect(Number(e.acumulado_total_ciclo)).to.eql(120000.01));"]),
            req("TC-M05-043d - Acumulado del ciclo 999999 -> 404", "GET", COSTEO + "/acumulado/ciclo/999999", token="tok_cont",
                tests=[json_o_vacio()] + codigo("TC-M05-043d", 404, "ACUMULADO_NO_ENCONTRADO")),
        ]),
        carpeta("2. TC-M05-044 Permisos del costeo por rol (recurso 55)", [
            acceso("TC-M05-044a", "Productor", "tok_prod", 403),
            acceso("TC-M05-044b", "Veterinario", "tok_vet", 403),
            acceso("TC-M05-044c", "Ingeniero de Campo", "tok_ing", 403),
            req("TC-M05-044d - Productor corrige -> 403", "POST", COSTEO + "/00000000-0000-4000-8000-000000000044/correccion", token="tok_prod",
                body=json.dumps({"id_idempotencia": "{{uuid_p}}", "cantidad": 1, "precio_unitario": -10,
                                 "justificacion_precio": "Descuento acordado en la factura",
                                 "motivo_correccion": "Ajuste por descuento comercial de la factura"}, indent=2),
                pre=[uuid_nuevo("uuid_p")], tests=["pm.test('TC-M05-044d - HTTP 403', () => pm.response.to.have.status(403));"]),
            req("TC-M05-044e - Revisor Fiscal consulta el acumulado -> 200", "GET", COSTEO + "/acumulado/ciclo/33", token="tok_rev",
                tests=["pm.test('TC-M05-044e - HTTP 200', () => pm.response.to.have.status(200));"]),
            acceso("TC-M05-044f", "Revisor Fiscal", "tok_rev", 403),
        ]),
        carpeta("3. TC-M05-045 Bloqueo tras el cierre del ciclo", [
            req("TC-M05-045a - Cerrar el ciclo de A (TC-M05-052, se revierte con el sandbox)", "POST",
                "{{base_url}}/activos-biologicos/{{id_activo_a}}/cierre", token="tok_admin",
                body="{\n  \"fecha_cierre\": \"{{dia_m0}}\",\n  \"motivo_cierre\": \"venta\",\n  \"descripcion_cierre\": \"QA TC-M05-045\"\n}",
                tests=["pm.test('TC-M05-045a - cierre aceptado (200/201)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201]));",
                       "pm.collectionVariables.set('a_cerrado', [200, 201].includes(pm.response.code) ? 1 : 0); console.log(pm.response.text());"]),
            post_costeo("TC-M05-045b - Registrar costeo sobre A cerrado -> 409", "tok_ges", uuid_var="uuid_p", campos=SERV,
                        pre=["if (!Number(pm.collectionVariables.get('a_cerrado'))) pm.execution.skipRequest();"],
                        tests=codigo("TC-M05-045b", 409, "CICLO_NO_ACTIVO")),
            req("TC-M05-045c - Correccion y anulacion sobre A cerrado", "GET", COSTEO + "/acumulado/ciclo/33", token="tok_cont", tests=[
                "if (!Number(pm.collectionVariables.get('a_cerrado'))) pm.test.skip('TC-M05-045b/c - BLOQUEADO: el cierre del ciclo de A responde 500 y sin registros propios no hay INSEMINACION ni consumo de A que corregir o anular', () => {});",
                "else pm.test.skip('TC-M05-045c - BLOQUEADO: no hay registro INSEMINACION ni consumo VALIDADO de A (su creacion responde 500)', () => {});"]),
            req("TC-M05-045d - Anular el consumo 31 (ciclo 33 cerrado) -> 409", "POST", CONSUMO + "/31/anulacion", token="tok_admin",
                body="{\n  \"justificacion_anulacion\": \"QA TC-M05-045 ciclo ya consolidado\"\n}", tests=[json_o_vacio()] + codigo("TC-M05-045d", 409, "CICLO_CERRADO") + [
                    "pm.test('TC-M05-045d - pide solicitar la correccion del reporte consolidado', () => pm.expect(String(e.message)).to.include('solicite la corrección del reporte consolidado'));",
                    sin_codigos("TC-M05-045d")]),
            req("TC-M05-045e - El acumulado CONSOLIDADO del ciclo 33 no cambio", "GET", COSTEO + "/acumulado/ciclo/33", token="tok_cont", tests=[
                json_o_vacio(), "pm.test('TC-M05-045e - sigue CONSOLIDADO en 120000.01', () => { pm.expect(e.estado).to.eql('CONSOLIDADO'); pm.expect(Number(e.acumulado_total_ciclo)).to.eql(120000.01); });"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-78 - TC-M05-G29 Ciclo inactivo, permisos y bloqueo tras el cierre",
                        "Automatiza TC-M05-043, 044 y 045. Datos reales de TEST: activo 57 sin fase activa y ciclo 33 cerrado y"
                        " CONSOLIDADO (consumo 31). El cierre de A se hace dentro del sandbox (se revierte). TC-M05-044 verifica lo que"
                        " pide el RNF-05 (Productor y Veterinario 403), aunque en TEST el recurso 55 les da C.", items,
                        {**VARS_75, "uuid_p": "", "uuid_57": "", "a_cerrado": "0"})


# ─────────────────────────────── G30 (RF-78) ───────────────────────────────
def g30():
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_GES, LOGIN_CONT]),
        carpeta("1. Preparacion (registros de TC-M05-034 y una correccion)", [
            sql("PRE - Ultima auditoria", "SELECT coalesce(max(id_auditoria_suministro), 0) AS m FROM modulo5.auditorias_suministros",
                ["pm.collectionVariables.set('max_auditoria', filas[0].m);"]),
            post_costeo("PREP - SERVICIO_VETERINARIO 1 x 150000", "tok_ges", uuid_var="uuid_1", campos=SERV, tests=[
                "pm.test('PREP - registrado (200)', () => pm.response.to.have.status(200));",
                "pm.collectionVariables.set('id_reg_serv', e.id_registro_suministro || ''); pm.collectionVariables.set('t_reg', Date.now());"]),
            req("PREP - Correccion -30000", "POST", COSTEO + "/{{id_reg_serv}}/correccion", token="tok_cont",
                body=json.dumps({"id_idempotencia": "{{uuid_c}}", "cantidad": 1, "precio_unitario": -30000,
                                 "justificacion_precio": "Descuento acordado en la factura",
                                 "motivo_correccion": "Ajuste por descuento comercial de la factura"}, indent=2),
                pre=[uuid_nuevo("uuid_c"), "if (!pm.collectionVariables.get('id_reg_serv')) pm.execution.skipRequest();"],
                tests=["pm.test('PREP - correccion registrada (200)', () => pm.response.to.have.status(200));"]),
        ]),
        carpeta("2. TC-M05-046 Auditoria de registros y correcciones del costeo", [
            sql("TC-M05-046 - Eventos del ciclo GF_A en esta corrida", """
                SELECT tipo_operacion::text AS op, id_usuario, costo_afectado, id_gestion_fases, fecha_evento, resultado::text AS res
                FROM modulo5.auditorias_suministros
                WHERE id_gestion_fases = {{id_fase_activa}} AND id_auditoria_suministro > {{max_auditoria}}
                ORDER BY fecha_evento
            """, [
                "const reg = filas.filter(f => f.op === 'SUMINISTRO_REGISTRADO'), cor = filas.filter(f => f.op === 'SUMINISTRO_CORREGIDO');",
                "pm.test('TC-M05-046 - 1 SUMINISTRO_REGISTRADO por el registro', () => pm.expect(reg.length).to.eql(1));",
                "pm.test('TC-M05-046 - 1 SUMINISTRO_CORREGIDO por la correccion', () => pm.expect(cor.length).to.eql(1));",
                "pm.test('TC-M05-046 - usuario y costo del registro (Gestor, 150000)', () => { pm.expect(String((reg[0] || {}).id_usuario)).to.eql(String(pm.collectionVariables.get('id_gestor'))); pm.expect(Number((reg[0] || {}).costo_afectado)).to.eql(150000); });",
                "pm.test('TC-M05-046 - fecha_evento informada en cada evento del registro', () => reg.forEach(f => pm.expect(f.fecha_evento).to.be.a('string')));"]),
            # Dentro del sandbox now() queda fijo, asi que el <= 2 s se mide sobre los registros REALES de TEST
            # (hechos fuera del sandbox): lectura de datos ya confirmados, no escribe nada.
            sql("TC-M05-046b - fecha_evento <= 2 s de la operacion, medido en los registros reales de TEST (fuera del sandbox)", """
                SELECT a.tipo_operacion::text AS op, count(*) AS n, count(d.seg) AS emparejados,
                       coalesce(max(d.seg), 0) AS seg_max, count(*) FILTER (WHERE d.seg > 2) AS mas_de_2s
                FROM modulo5.auditorias_suministros a
                LEFT JOIN LATERAL (SELECT abs(extract(epoch FROM a.fecha_evento - r.fecha_registro)) AS seg
                                   FROM modulo5.registro_suministro r
                                   WHERE r.id_activo_biologico = a.id_activo_biologico AND r.costo_registro = a.costo_afectado
                                   ORDER BY 1 LIMIT 1) d ON true
                WHERE a.tipo_operacion::text IN ('SUMINISTRO_REGISTRADO', 'SUMINISTRO_CORREGIDO')
                  AND a.id_auditoria_suministro <= {{max_auditoria}}
                GROUP BY 1
            """, [
                "const reg = filas.find(f => f.op === 'SUMINISTRO_REGISTRADO') || {}, cor = filas.find(f => f.op === 'SUMINISTRO_CORREGIDO') || {};",
                "console.log('TC-M05-046b - reales: ' + reg.n + ' SUMINISTRO_REGISTRADO y ' + cor.n + ' SUMINISTRO_CORREGIDO; desfase maximo ' + reg.seg_max + ' s / ' + cor.seg_max + ' s');",
                "pm.test('TC-M05-046b - hay registros y correcciones reales para medir', () => { pm.expect(Number(reg.n)).to.be.above(0); pm.expect(Number(cor.n)).to.be.above(0); });",
                "pm.test('TC-M05-046b - cada evento real tiene su registro en el ledger', () => filas.forEach(f => pm.expect(Number(f.emparejados)).to.eql(Number(f.n))));",
                "pm.test('TC-M05-046b - ningun evento real a mas de 2 s de su operacion (RNF-06)', () => filas.forEach(f => pm.expect(Number(f.mas_de_2s), f.op).to.eql(0)));"]),
        ]),
        carpeta("3. TC-M05-047 Concurrencia", [
            # Las rafagas se ejecutaron FUERA del sandbox el 2026-11-09 con autorizacion del DBA (en el sandbox llegan
            # serializadas): aqui se verifica en lectura lo que quedo en la BD. Los codigos HTTP de cada envio no quedan en
            # la BD; se toman de evidencia_TC-M05-047_fuera_sandbox.txt.
            sql("TC-M05-047 - Registros de las rafagas concurrentes (activo A, precio 4321)", """
                SELECT count(*) AS registros, count(DISTINCT id_idempotencia) AS uuids, coalesce(sum(costo_registro), 0) AS suma,
                       count(*) FILTER (WHERE id_idempotencia::text = '{{uuid_rafaga2}}') AS con_uuid_rafaga2,
                       count(*) FILTER (WHERE cantidad BETWEEN 1 AND 20) AS rafaga1
                FROM modulo5.registro_suministro
                WHERE id_activo_biologico = {{id_activo_a}} AND precio_unitario_resuelto = 4321 AND tipo_operacion::text = 'REGISTRO'
            """, [
                "const f = filas[0] || {};",
                "pm.test('TC-M05-047a - rafaga 1: los 20 registros simultaneos distintos quedaron guardados (20 UUID)', () => pm.expect(Number(f.rafaga1)).to.eql(20));",
                "pm.test('TC-M05-047a - rafaga 1: las 20 respuestas fueron 200 REGISTRADO, ninguna 500', () => pm.expect(Number(pm.collectionVariables.get('r1_200'))).to.eql(20));",
                "pm.test('TC-M05-047b - rafaga 2: exactamente 1 registro con el UUID repetido 20 veces', () => pm.expect(Number(f.con_uuid_rafaga2)).to.eql(1));",
                "pm.test('TC-M05-047 - ledger sin duplicados: 21 registros, 21 UUID, suma 998151 (4321 x 231)', () => { pm.expect(Number(f.registros)).to.eql(21); pm.expect(Number(f.uuids)).to.eql(21); pm.expect(Number(f.suma)).to.eql(998151); });",
                "pm.test('TC-M05-047b - rafaga 2: las 19 replicas responden 200 YA_PROCESADO (real: ' + pm.collectionVariables.get('r2_ya_procesado') + ' YA_PROCESADO y ' + pm.collectionVariables.get('r2_409') + ' 409 RECURSO_DUPLICADO; INC-M05-341-G30)', () => pm.expect(Number(pm.collectionVariables.get('r2_ya_procesado'))).to.eql(19));"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-78 - TC-M05-G30 Auditoria y concurrencia del costeo",
                        "Automatiza TC-M05-046 (auditoria de los registros y correcciones hechos en la misma corrida; el"
                        " <= 2 s se mide en los registros reales). TC-M05-047 se ejecuto FUERA del sandbox el 2026-11-09 con"
                        " autorizacion del DBA (2 rafagas de 20 POST simultaneos sobre A, precio 4321); aqui se verifica en"
                        " lectura y los codigos HTTP de cada envio vienen de evidencia_TC-M05-047_fuera_sandbox.txt.", items,
                        {**VARS_75, "uuid_1": "", "uuid_c": "", "id_reg_serv": "",
                         "uuid_rafaga2": "8469a9ce-0a52-47fd-9f72-753a6c0c8fb2", "r1_200": "20", "r2_ya_procesado": "16", "r2_409": "3"})


# ─────────────────────────────── G32 (RF-79) ───────────────────────────────
def g32():
    def nic(tc, desc, metodo, ruta, token, esperado, body=None, code=None, extra=None):
        return req(f"{tc} - {desc}", metodo, NIC41 + ruta, token=token, body=body,
                   tests=[json_o_vacio()] + (codigo(tc, esperado, code) if code else [f"pm.test('{tc} - HTTP {esperado}', () => pm.response.to.have.status({esperado}));"]) + (extra or []))

    corr_body = "{\n  \"motivo_correccion\": \"Correccion solicitada por auditoria externa\"\n}"
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_PROD, LOGIN_VET, LOGIN_CONT, LOGIN_REV]),
        carpeta("0b. Referencias", asignar_finca_de(2) + asignar_finca_de(57) + [
            sql("PRE - Ultima provision NIC-41 (id_v1) y reportes antes", """
                SELECT (SELECT max(id_provision) FROM modulo5.provision_nic41) AS id_v1, (SELECT count(*) FROM modulo5.provision_nic41) AS n
            """, ["pm.collectionVariables.set('id_v1', filas[0].id_v1); pm.collectionVariables.set('n_prov_antes', filas[0].n);"]),
        ]),
        carpeta("1. TC-M05-049 Rechazos del consolidado", [
            nic("TC-M05-049a", "Consolidar el ciclo de A (GF_A, activo) -> 409", "POST", "/ciclo/{{id_fase_activa}}/consolidar", "tok_cont", 409,
                code="CICLO_ACTIVO", extra=[
                    "pm.test('TC-M05-049a - mensaje del E2', () => pm.expect(e.message).to.eql('El ciclo ' + pm.collectionVariables.get('id_fase_activa') + ' está activo. El reporte consolidado solo está disponible tras el cierre del ciclo por RF-41.'));",
                    sin_codigos("TC-M05-049a")]),
            nic("TC-M05-049b", "Consolidar el ciclo 12 (fase activa del activo 2) -> 409", "POST", "/ciclo/12/consolidar", "tok_cont", 409, code="CICLO_ACTIVO"),
            nic("TC-M05-049c", "Consolidar el ciclo 999999 -> 404", "POST", "/ciclo/999999/consolidar", "tok_cont", 404, code="CICLO_NO_ENCONTRADO"),
            nic("TC-M05-049d", "Consultar la provision 999999 -> 404", "GET", "/999999", "tok_cont", 404, code="PROVISION_NO_ENCONTRADA"),
            sql("TC-M05-049e - No se creo ningun reporte", "SELECT count(*) AS n FROM modulo5.provision_nic41", [
                "pm.test('TC-M05-049e - mismas provisiones que antes', () => pm.expect(String(filas[0].n)).to.eql(String(pm.collectionVariables.get('n_prov_antes'))));"]),
        ]),
        carpeta("2. TC-M05-057 Permisos NIC-41 por rol (recurso 56)", [
            *[nic(f"TC-M05-057{l}", f"{rol} consolida -> 403", "POST", "/ciclo/33/consolidar", tok, 403) for l, rol, tok in
              (("a", "Productor", "tok_prod"), ("b", "Veterinario", "tok_vet"), ("c", "Revisor Fiscal", "tok_rev"))],
            *[nic(f"TC-M05-057{l}", f"{rol} corrige -> 403", "POST", "/{{id_v1}}/correccion", tok, 403, body=corr_body) for l, rol, tok in
              (("d", "Productor", "tok_prod"), ("e", "Veterinario", "tok_vet"), ("f", "Revisor Fiscal", "tok_rev"))],
            nic("TC-M05-057g", "Revisor Fiscal consulta id_v1 -> 200", "GET", "/{{id_v1}}", "tok_rev", 200),
            nic("TC-M05-057h", "Productor consulta id_v1 -> 200", "GET", "/{{id_v1}}", "tok_prod", 200),
            nic("TC-M05-057i", "Veterinario consulta id_v1 -> 403", "GET", "/{{id_v1}}", "tok_vet", 403),
            sql("TC-M05-057j - Ningun rechazo creo reportes", "SELECT count(*) AS n FROM modulo5.provision_nic41", [
                "pm.test('TC-M05-057j - mismas provisiones que antes', () => pm.expect(String(filas[0].n)).to.eql(String(pm.collectionVariables.get('n_prov_antes'))));"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-79 - TC-M05-G32 Rechazos del consolidado y permisos NIC-41",
                        "Automatiza TC-M05-049 y 057. id_v1 = la provision NIC-41 mas reciente de TEST. Ciclo 12 = fase activa del"
                        " activo 2; ciclo 33 = cerrado y consolidado (activo 57).", items, {**VARS_75, "id_v1": ""})


# ─────────────────────────────── G33 (RF-79, provisión incremental hacia M06) ───────────────────────────────
def g33():
    outbox = """
        SELECT id_outbox_provision_m06::text AS id_evento, modalidad::text AS modalidad, estado::text AS estado,
               numero_intentos, json_contenido, fecha_creacion, fecha_entrega
        FROM modulo5.outbox_provisiones_m06 WHERE id_gestion_fases = {{id_fase_activa}} ORDER BY fecha_creacion
    """
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_GES, LOGIN_CONT]),
        carpeta("1. Preparacion (costos de E4 sobre A: registro y correccion)", [
            post_costeo("PREP - SERVICIO_VETERINARIO 1 x 150000", "tok_ges", uuid_var="uuid_1", campos=SERV, tests=[
                "pm.test('PREP - registrado (200)', () => pm.response.to.have.status(200));",
                "pm.collectionVariables.set('id_reg_serv', e.id_registro_suministro || '');"]),
            req("PREP - Correccion -30000", "POST", COSTEO + "/{{id_reg_serv}}/correccion", token="tok_cont",
                body=json.dumps({"id_idempotencia": "{{uuid_c}}", "cantidad": 1, "precio_unitario": -30000,
                                 "justificacion_precio": "Descuento acordado en la factura",
                                 "motivo_correccion": "Ajuste por descuento comercial de la factura"}, indent=2),
                pre=[uuid_nuevo("uuid_c"), "if (!pm.collectionVariables.get('id_reg_serv')) pm.execution.skipRequest();"],
                tests=["pm.test('PREP - correccion registrada (200)', () => pm.response.to.have.status(200));"]),
            sql("PREP - Movimientos de A en el ledger", "SELECT count(*) AS n FROM modulo5.registro_suministro WHERE id_gestion_fases = {{id_fase_activa}}",
                ["pm.collectionVariables.set('n_movimientos', filas[0].n);"]),
        ]),
        carpeta("2. TC-M05-050 Evento INCREMENTAL por cada costo del ciclo", [
            sql("TC-M05-050 - Outbox de GF_A", outbox, [
                "const j = v => typeof v === 'string' ? JSON.parse(v) : (v || {});",
                "const inc = filas.filter(f => f.modalidad === 'INCREMENTAL');",
                "pm.test('TC-M05-050 - 1 evento INCREMENTAL por movimiento del ledger (' + pm.collectionVariables.get('n_movimientos') + ')', () => { pm.expect(Number(pm.collectionVariables.get('n_movimientos')), 'movimientos de A').to.be.above(0); pm.expect(inc.length).to.eql(Number(pm.collectionVariables.get('n_movimientos'))); });",
                "pm.test('TC-M05-050 - id_evento_provision distinto en cada evento', () => pm.expect(new Set(inc.map(f => f.id_evento)).size).to.eql(inc.length));",
                "pm.test('TC-M05-050 - el evento trae schema_version, activo, ciclo, tipo, costo y acumulados', () => inc.forEach(f => { const c = j(f.json_contenido); ['schema_version', 'id_activo', 'id_ciclo', 'id_tipo_suministro', 'costo_registro', 'acumulado_total_ciclo', 'acumulado_por_categoria'].forEach(k => pm.expect(c, k).to.have.property(k)); }));",
                "pm.test('TC-M05-050 - el evento trae la fecha del consumo/aplicacion (schema 1.1; la nota del equipo dice que no)', () => inc.forEach(f => pm.expect(j(f.json_contenido)).to.have.property('fecha_aplicacion')));"]),
        ]),
        carpeta("3. TC-M05-051 y TC-M05-060 Entrega a M06 y conversion contable", [
            # El despachador a M06 no ve la transaccion del sandbox: la entrega y la conversion se verifican sobre
            # los eventos REALES de TEST (hechos fuera del sandbox), en solo lectura.
            sql("TC-M05-051 - Entrega a M06 en <= 5 s y ACK, medido en los eventos reales de TEST (fuera del sandbox)", """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE estado::text = 'ENTREGADO') AS entregados,
                       count(*) FILTER (WHERE estado::text = 'ENTREGADO' AND fecha_entrega - fecha_creacion <= interval '5 seconds') AS en_5s,
                       round(max(extract(epoch FROM fecha_entrega - fecha_creacion))::numeric, 2) AS seg_max,
                       (SELECT count(*) FROM modulo5.auditorias_suministros a
                         WHERE a.tipo_operacion::text = 'PROVISION_INCREMENTAL_ENTREGADA' AND a.id_auditoria_suministro <= {{max_auditoria}}) AS acks
                FROM modulo5.outbox_provisiones_m06
                WHERE modalidad::text = 'INCREMENTAL' AND id_gestion_fases IS DISTINCT FROM {{id_fase_activa}}
            """, [
                "const f = filas[0] || {}, pct = Number(f.en_5s) * 100 / Math.max(Number(f.entregados), 1);",
                "console.log('TC-M05-051 - reales: ' + f.entregados + '/' + f.total + ' entregados, ' + f.en_5s + ' en <= 5 s (' + pct.toFixed(1) + '%), maximo ' + f.seg_max + ' s, ' + f.acks + ' ACK');",
                "pm.test('TC-M05-051 - hay eventos reales y todos quedaron ENTREGADO', () => { pm.expect(Number(f.total)).to.be.above(0); pm.expect(Number(f.entregados)).to.eql(Number(f.total)); });",
                "pm.test('TC-M05-051 - cada evento entregado tiene su ACK PROVISION_INCREMENTAL_ENTREGADA', () => pm.expect(Number(f.acks)).to.be.at.least(Number(f.entregados)));",
                "pm.test('TC-M05-051 - al menos el 99% entregado en <= 5 s (CA-1); el tiempo se mide desde el inicio de la transaccion del registro, no desde su commit', () => pm.expect(pct).to.be.at.least(99));"]),
            sql("PREP - Eventos INCREMENTAL reales del activo de referencia de M06 ({{id_activo_ref_m06}})", """
                SELECT id_outbox_provision_m06::text AS id_evento, costo_registro, json_contenido->>'fecha_aplicacion' AS fecha
                FROM modulo5.outbox_provisiones_m06
                WHERE id_activo_biologico = {{id_activo_ref_m06}} AND modalidad::text = 'INCREMENTAL' AND estado::text = 'ENTREGADO'
            """, ["pm.collectionVariables.set('eventos_ref_m06', JSON.stringify(filas));",
                  "pm.test('PREP - el activo de referencia tiene eventos entregados', () => pm.expect(filas.length).to.be.above(0));"]),
            req("TC-M05-060 - M06 convirtio cada evento real en un costo con su fecha y su linea contable", "GET",
                "{{base_url}}/finanzas/costos?id_activo_biologico={{id_activo_ref_m06}}", token="tok_admin", tests=[
                "pm.test('TC-M05-060 - HTTP 200', () => pm.response.to.have.status(200));",
                "const costos = pm.response.json() || [], eventos = JSON.parse(pm.collectionVariables.get('eventos_ref_m06') || '[]');",
                "console.log('TC-M05-060 - ' + eventos.length + ' eventos del activo ' + pm.collectionVariables.get('id_activo_ref_m06') + ' y ' + costos.length + ' costos en M06');",
                "eventos.forEach(ev => { const c = costos.find(x => x.id_origen_m05 === ev.id_evento) || {};"
                " pm.test('TC-M05-060 - evento ' + ev.id_evento.slice(0, 8) + ': costo en M06 con el mismo monto, la fecha de aplicacion y ASIENTO_NIC41', () => {"
                " pm.expect(c.id_registro_costo, 'costo con id_origen_m05').to.not.be.undefined;"
                " pm.expect(Number(c.monto_costo)).to.eql(Math.abs(Number(ev.costo_registro)));"
                " pm.expect(c.fecha_costo).to.eql(ev.fecha); pm.expect(c.vehiculo_contable).to.eql('ASIENTO_NIC41'); }); });"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-79 - TC-M05-G33 Provision incremental hacia M06",
                        "Automatiza TC-M05-050 dentro del sandbox. TC-M05-051 y 060 se verifican en solo lectura sobre los"
                        " eventos reales de TEST, porque el despachador a M06 no ve la transaccion del sandbox. Activo de"
                        " referencia de M06: 943 (QA-M06-BOV-01, con periodo contable). El outbox se lee con /test-control/query.", items,
                        {**VARS_75, "uuid_1": "", "uuid_c": "", "id_reg_serv": "", "id_activo_ref_m06": "943", "eventos_ref_m06": ""})


# ─────────────────────────────── G34 (RF-79, consolidado al cierre) ───────────────────────────────
def g34():
    def prov(tc, desc, q, token="tok_cont", tests=None):
        return req(f"{tc} - {desc}", "GET", NIC41 + "/{{id_prov}}" + q, token=token, tests=[json_o_vacio()] + (tests or []))

    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_CONT]),
        carpeta("0b. Alcance del Contador sobre el ciclo 33 (activo 57)", asignar_finca_de(57)),
        carpeta("1. TC-M05-052 Cierre del ciclo de A genera el consolidado v1", [
            req("TC-M05-052a - Cerrar el ciclo de A (Administrador, se revierte con el sandbox)", "POST",
                "{{base_url}}/activos-biologicos/{{id_activo_a}}/cierre", token="tok_admin",
                body="{\n  \"fecha_cierre\": \"{{dia_m0}}\",\n  \"motivo_cierre\": \"finalizacion_lote\",\n  \"descripcion_cierre\": \"Cierre de prueba QA M05\"\n}",
                tests=["pm.test('TC-M05-052a - cierre aceptado (200/201)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201]));",
                       "console.log(pm.response.text());"]),
            req("TC-M05-052b - Versiones del consolidado de GF_A", "GET", NIC41 + "/ciclo/{{id_fase_activa}}/versiones", token="tok_admin", tests=[
                json_o_vacio(), "const v = (e.versiones || [])[0] || {};",
                "pm.test('TC-M05-052b - 1 reporte v1 CONSOLIDADO, GENERADO, sin anterior y con hash', () => { pm.expect(e.total).to.eql(1); pm.expect(v.version_reporte).to.eql(1); pm.expect(v.id_reporte_anterior).to.eql(null); pm.expect(v.modalidad).to.eql('CONSOLIDADO'); pm.expect(v.estado).to.eql('GENERADO'); pm.expect(v.hash_integridad).to.match(/^[0-9a-f]{64}$/); });"]),
        ]),
        carpeta("2. TC-M05-053 Contenido y paginacion (sobre la ultima provision real: ciclo 33)", [
            sql("PRE - Provision a revisar (la mas reciente del ciclo 33)", "SELECT max(id_provision) AS id FROM modulo5.provision_nic41 WHERE id_gestion_fases = 33",
                ["pm.collectionVariables.set('id_prov', filas[0].id);",
                 "console.warn('El ciclo de A no se puede cerrar hoy (500): TC-M05-053/054 se verifican sobre la provision ' + filas[0].id + ' del ciclo 33.');"]),
            prov("TC-M05-053a", "pagina=1, por_pagina=200 (todo)", "?pagina=1&por_pagina=200", tests=[
                "pm.test('TC-M05-053a - HTTP 200', () => pm.response.to.have.status(200));",
                "pm.collectionVariables.set('prov_full', JSON.stringify(e));",
                "const suma = o => Object.values(o || {}).reduce((s, x) => s + Number(x), 0);",
                "pm.test('TC-M05-053a - monto_provision = suma del desglose por categoria (CA-4)', () => pm.expect(Number(e.monto_provision)).to.be.closeTo(suma(e.desglose_categoria), 0.005));",
                "pm.test('TC-M05-053a - monto_provision = suma de costo_registro de la lista (CA-6)', () => pm.expect(Number(e.monto_provision)).to.be.closeTo((e.lista_registros || []).reduce((s, r) => s + Number(r.costo_registro), 0), 0.005));",
                "pm.test('TC-M05-053a - la lista trae todos los registros (total_registros)', () => pm.expect((e.lista_registros || []).length).to.eql(e.total_registros));"]),
            sql("TC-M05-053b - El monto coincide con el acumulado del ciclo", "SELECT acumulado_total_ciclo FROM modulo5.acumulado_ciclo WHERE id_gestion_fases = 33", [
                "const p = JSON.parse(pm.collectionVariables.get('prov_full') || '{}');",
                "pm.test('TC-M05-053b - monto_provision (' + p.monto_provision + ') = acumulado_total_ciclo (' + (filas[0] || {}).acumulado_total_ciclo + ')', () => pm.expect(Number(p.monto_provision)).to.be.closeTo(Number((filas[0] || {}).acumulado_total_ciclo), 0.005));"]),
            *[prov(f"TC-M05-053{l}", f"pagina={pg}, por_pagina=2", f"?pagina={pg}&por_pagina=2", tests=[
                f"pm.test('TC-M05-053{l} - HTTP 200', () => pm.response.to.have.status(200));",
                f"pm.collectionVariables.set('pag_{pg}', JSON.stringify((e.lista_registros || []).map(r => r.id_registro_suministro)));"])
              for l, pg in (("c", 1), ("d", 2), ("e", 3))],
            sql("TC-M05-053f - Las paginas no repiten ni omiten registros", "SELECT 1 AS ok", [
                "const ids = [1, 2, 3].flatMap(p => JSON.parse(pm.collectionVariables.get('pag_' + p) || '[]'));",
                "const todos = (JSON.parse(pm.collectionVariables.get('prov_full') || '{}').lista_registros || []).map(r => r.id_registro_suministro);",
                "pm.test('TC-M05-053f - sin repetidos', () => pm.expect(new Set(ids).size).to.eql(ids.length));",
                "pm.test('TC-M05-053f - las paginas juntas = la lista completa', () => pm.expect(ids.slice().sort()).to.eql(todos.slice().sort()));"]),
            prov("TC-M05-053g", "por_pagina=0 -> 400", "?por_pagina=0", tests=["pm.test('TC-M05-053g - HTTP 400', () => pm.response.to.have.status(400));"]),
            prov("TC-M05-053h", "por_pagina=201 -> 400", "?por_pagina=201", tests=["pm.test('TC-M05-053h - HTTP 400', () => pm.response.to.have.status(400));"]),
        ]),
        carpeta("3. TC-M05-054 Hash de integridad estable", [
            *[prov(f"TC-M05-054{l}", f"consulta {n}", "", tests=[
                f"pm.test('TC-M05-054{l} - HTTP 200', () => pm.response.to.have.status(200));",
                f"pm.collectionVariables.set('hash_{n}', e.hash_integridad || '');"]) for l, n in (("a", 1), ("b", 2), ("c", 3))],
            sql("TC-M05-054d - Hash en BD", "SELECT hash_integridad FROM modulo5.provision_nic41 WHERE id_provision = {{id_prov}}", [
                "const h = [1, 2, 3].map(n => pm.collectionVariables.get('hash_' + n));",
                "pm.test('TC-M05-054d - SHA-256 (64 hex)', () => pm.expect(h[0]).to.match(/^[0-9a-f]{64}$/));",
                "pm.test('TC-M05-054d - mismo hash en las 3 consultas y en la BD', () => { pm.expect(h[1]).to.eql(h[0]); pm.expect(h[2]).to.eql(h[0]); pm.expect((filas[0] || {}).hash_integridad).to.eql(h[0]); });",
            ]),
            # Formula publicada en RFC-025 C25.3 (ADR-M05-02, aprobado 2026-11-08): SHA-256 hex de los pares nombre='valor'
            # (jsonb_each_text) ordenados por nombre y unidos con ' & ', sin hash_integridad, creado_en ni id_registro_suministro.
            sql("TC-M05-054e - Recalculo del hash por el auditor (formula de RFC-025 / ADR-M05-02)", """
                SELECT id_provision, hash_integridad = encode(digest(
                         (SELECT string_agg(format('%I=%L', key, value), ' & ' ORDER BY key)
                            FROM jsonb_each_text(to_jsonb(p) - 'hash_integridad' - 'creado_en' - 'id_registro_suministro')),
                         'sha256'), 'hex') AS integro
                FROM modulo5.provision_nic41 p ORDER BY id_provision
            """, [
                "console.log(JSON.stringify(filas));",
                "pm.test('TC-M05-054e - hay provisiones para recalcular', () => pm.expect(filas.length).to.be.above(0));",
                "pm.test('TC-M05-054e - la provision consultada ({{id_prov}}) recalcula al mismo hash', () => pm.expect((filas.find(f => String(f.id_provision) === String(pm.variables.get('id_prov'))) || {}).integro).to.eql(true));",
                "pm.test('TC-M05-054e - todas las provisiones recalculan al mismo hash (CA-3)', () => filas.forEach(f => pm.expect(f.integro, 'provision ' + f.id_provision).to.eql(true)));"]),
        ]),
        carpeta("4. TC-M05-055 Correccion del consolidado", [
            req("TC-M05-055a - Correccion de la provision (Contador) -> 201 v2", "POST", NIC41 + "/{{id_prov}}/correccion", token="tok_cont",
                body="{\n  \"motivo_correccion\": \"Revisión del contador por ajuste de cierre\"\n}", tests=[
                    json_o_vacio(), "pm.test('TC-M05-055a - HTTP 201', () => pm.response.to.have.status(201));",
                    "pm.test('TC-M05-055a - version N+1 enlazada a la anterior', () => { pm.expect(e.id_reporte_anterior).to.eql(Number(pm.collectionVariables.get('id_prov'))); pm.expect(e.motivo_correccion).to.eql('Revisión del contador por ajuste de cierre'); });"]),
            req("TC-M05-055b - Motivo de 19 caracteres -> 400", "POST", NIC41 + "/{{id_prov}}/correccion", token="tok_cont",
                body="{\n  \"motivo_correccion\": \"" + "M" * 19 + "\"\n}", tests=["pm.test('TC-M05-055b - HTTP 400', () => pm.response.to.have.status(400));"]),
            req("TC-M05-055c - Motivo de 501 caracteres -> 400", "POST", NIC41 + "/{{id_prov}}/correccion", token="tok_cont",
                body="{\n  \"motivo_correccion\": \"" + "M" * 501 + "\"\n}", tests=["pm.test('TC-M05-055c - HTTP 400', () => pm.response.to.have.status(400));"]),
            req("TC-M05-055d - Provision 999999 -> 404", "POST", NIC41 + "/999999/correccion", token="tok_cont",
                body="{\n  \"motivo_correccion\": \"Revisión del contador por ajuste de cierre\"\n}", tests=[json_o_vacio()] + codigo("TC-M05-055d", 404, "PROVISION_NO_ENCONTRADA")),
        ]),
        rollback(),
    ]
    return guardar_info("RF-79 - TC-M05-G34 Consolidado al cierre: contenido, hash y correccion",
                        "Automatiza TC-M05-052 a 055. El cierre de A se hace dentro del sandbox (se revierte). Como hoy el cierre"
                        " responde 500, el contenido, la paginacion, el hash y la correccion se verifican sobre la provision"
                        " real mas reciente del ciclo 33 (activo 57).", items, {**VARS_75, "id_prov": ""})


# ─────────────────────────────── G35 (RF-79, versiones e inmutabilidad) ───────────────────────────────
def g35():
    items = [
        precondiciones([LOGIN_ADMIN, LOGIN_CONT], nivel="activo"),
        carpeta("1. TC-M05-056 Cadena de versiones del ciclo 33", [
            req("TC-M05-056a - Versiones del ciclo 33", "GET", NIC41 + "/ciclo/33/versiones", token="tok_cont", tests=[
                json_o_vacio(), "pm.test('TC-M05-056a - HTTP 200', () => pm.response.to.have.status(200));",
                "const v = (e.versiones || []).slice().sort((a, b) => a.version_reporte - b.version_reporte);",
                "console.log(JSON.stringify(v.map(x => ({id: x.id_provision, version: x.version_reporte, anterior: x.id_reporte_anterior, estado: x.estado, incompleto: x.es_reporte_potencialmente_incompleto}))));",
                "pm.test('TC-M05-056a - v1 -> v2 -> v3 enlazadas por id_reporte_anterior', () => { pm.expect(v.length).to.eql(3); pm.expect(v[0].id_reporte_anterior).to.eql(null); pm.expect(v[1].id_reporte_anterior).to.eql(v[0].id_provision); pm.expect(v[2].id_reporte_anterior).to.eql(v[1].id_provision); });",
                "pm.test('TC-M05-056a - solo la ultima esta GENERADO; las anteriores SUPERADO (estados: ' + v.map(x => x.estado).join(', ') + ')', () => { pm.expect(v[0].estado).to.eql('SUPERADO'); pm.expect(v[1].estado).to.eql('SUPERADO'); pm.expect(v[2].estado).to.eql('GENERADO'); });",
                "pm.test('TC-M05-056a - es_reporte_potencialmente_incompleto (actual: ' + v.map(x => x.es_reporte_potencialmente_incompleto).join(', ') + ')', () => v.forEach(x => pm.expect(x.es_reporte_potencialmente_incompleto, 'v' + x.version_reporte).to.eql(false)));"]),
            *[req(f"TC-M05-056{l} - GET /nic41/{i}", "GET", NIC41 + f"/{i}", token="tok_cont", tests=[
                json_o_vacio(), f"pm.test('TC-M05-056{l} - HTTP 200', () => pm.response.to.have.status(200));",
                f"pm.test('TC-M05-056{l} - es la version {i} del ciclo 33', () => {{ pm.expect(e.version_reporte).to.eql({i}); pm.expect(e.id_gestion_fases).to.eql(33); }});"])
              for l, i in (("b", 1), ("c", 2), ("d", 3))],
        ]),
        carpeta("2. TC-M05-058 Inmutabilidad del reporte en BD", [
            sql("TC-M05-058a - Existe proteccion contra UPDATE/DELETE sobre provision_nic41", """
                SELECT t.tgname, pg_get_triggerdef(t.oid) AS def FROM pg_trigger t
                WHERE t.tgrelid = 'modulo5.provision_nic41'::regclass AND NOT t.tgisinternal
            """, ["const prot = filas.filter(f => /BEFORE (UPDATE OR DELETE|DELETE OR UPDATE|UPDATE|DELETE)/i.test(f.def));",
                  "console.log(JSON.stringify(filas));",
                  "pm.test('TC-M05-058a - hay un trigger BEFORE UPDATE/DELETE sobre provision_nic41', () => pm.expect(prot.length).to.be.above(0));",
                  "pm.test.skip('TC-M05-058b - UPDATE y DELETE reales: BLOQUEADO, /test-control/query es de solo lectura y member_qa no escribe; lo debe ejecutar el DBA', () => {});"]),
        ]),
        rollback(),
    ]
    return guardar_info("RF-79 - TC-M05-G35 Integridad de versiones existentes e inmutabilidad",
                        "Automatiza TC-M05-056 (solo lectura sobre las provisiones reales del ciclo 33) y la parte verificable de"
                        " TC-M05-058 (existencia del trigger de inmutabilidad; el UPDATE/DELETE real lo hace el DBA).", items, VARS_75)

def main() -> None:
    grupos = (("RF-74", "G01", g01), ("RF-74", "G02", g02), ("RF-74", "G03", g03), ("RF-74", "G04", g04), ("RF-74", "G05", g05),
              ("RF-74", "G06", g06), ("RF-75", "G08", g08), ("RF-75", "G09", g09), ("RF-75", "G10", g10),
              ("RF-75", "G11", g11), ("RF-75", "G12", g12), ("RF-78", "G26", g26), ("RF-78", "G27", g27), ("RF-78", "G28", g28),
              ("RF-78", "G29", g29), ("RF-78", "G30", g30), ("RF-79", "G32", g32),
              ("RF-79", "G33", g33), ("RF-79", "G34", g34), ("RF-79", "G35", g35))
    for rf, g, fn in grupos:
        destino = AQUI.parent / rf / f"TC-M05-{g}" / f"tc-m05-{g.lower()}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(fn(), ensure_ascii=False, indent=2), encoding="utf-8")
        print("escrito", destino.relative_to(AQUI.parent))


if __name__ == "__main__":
    main()
