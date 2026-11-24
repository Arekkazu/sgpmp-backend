# | Fecha      | Nombre           | Que se hizo                                                        |
# |------------|------------------|--------------------------------------------------------------------|
# | 2026-11-19 | Juan Manuel      | TC-M08-G013..G017 RF-105: colecciones con sandbox (bandeja v6)     |
# | 2026-11-21 | Juan Manuel      | TC-M08 RF-105: re-ejecucion rc.85, informativa del Productor y llaves|
# | 2026-11-21 | Juan Manuel      | TC-M08-G015 RF-105: alerta real con token del broker, fuera del sandbox|
# | 2026-11-21 | Juan Manuel      | TC-M08-G015 RF-105: nodos temporales sin historial y su desactivacion  |
# | 2026-11-22 | Juan Manuel      | TC-M08-015 RF-105: INC-394 aceptada por Desarrollo, queda como observacion |
"""Genera las colecciones Newman de RF-105 (bandeja y ciclo de vida de notificaciones, M08; G013 a G017).

Uso (desde esta carpeta):  python construir_colecciones_rf105.py
Escribe TC-M08-Gnnn/tc-m08-gnnn.json. Se ejecutan desde Test_Modulo8 con:
    .\\correr_newman_m08.ps1 -Caso G013 -Rf RF-105

Reutiliza los ayudantes de ../RF-103/construir_colecciones_rf103.py (sandbox, logins, rollback).

Ajustes frente a la ficha (lanzamiento v6, rc.78): la bandeja ya tiene nivel, estado (NUEVA, LEIDA, ATENDIDA,
DESCARTADA), PATCH /notificaciones/{id}/atendida y /descartada y filtros nivel, estado, modulo e
incluir_archivadas. Cuentas: Administrador admin.rol@gmail.com (las críticas de su bandeja) y Productor
qa.m08.productor@sgpmp-test.com (bandeja de 463). Las cuentas viejas de la ficha ya no entran en TEST.
Todo cambio de estado ocurre dentro del sandbox y se revierte al final.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("rf103", AQUI.parent / "RF-103" / "construir_colecciones_rf103.py")
rf103 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rf103)
req, carpeta, login, coleccion, JS_COMUN = rf103.req, rf103.carpeta, rf103.login, rf103.coleccion, rf103.JS_COMUN
L_ADMIN, L_PROD = rf103.L_ADMIN, rf103.L_PROD
# Cuenta 182 del DBA: bandeja de más de 500 notificaciones, para el tiempo de carga de TC-M08-013 (RNF-03).
L_BANDEJA = ("tok_bandeja", "correo_bandeja", "contrasena_bandeja", "Productor (bandeja 182)", "id_bandeja")
# Desde rc.80 los inicios de sesión ya no van a la bandeja: el Administrador se quedó sin informativas, así que la
# INFORMATIVA de TC-M08-017 se toma del Productor (sus avisos de reportes y suministros).

N = "{{base_url}}/notificaciones"


def esc(x):
    """Escapa las comillas simples para meter el texto dentro de un pm.test('...')."""
    return x.replace("'", "\\'")

RANGO = "const rango = n => ({ CRITICA: 0, ADVERTENCIA: 1, INFORMATIVA: 2 })[n.nivel];"
# Orden del RF: crítica > advertencia > informativa y, dentro de cada nivel, de la más reciente a la más vieja.
ORDEN = [RANGO,
         "const ordenada = it => it.every((n, k) => k === 0 || rango(it[k - 1]) < rango(n) ||"
         " (rango(it[k - 1]) === rango(n) && Date.parse(it[k - 1].fecha_envio) >= Date.parse(n.fecha_envio)));"]


def pre(logins):
    return carpeta("0. Precondiciones (logins dentro del sandbox)", [login(*l) for l in logins])


def lista(nombre, tok, q, tests, guardar=None):
    t = ["const b = pm.response.json() || {}; const it = b.items || [];",
         "console.log(JSON.stringify({ total: b.total, no_leidas: b.no_leidas, criticas_pendientes: b.criticas_pendientes, pagina: b.pagina, tamano: b.tamano, n: it.length }));"]
    if guardar:
        t.append(f"pm.collectionVariables.set('{guardar}', pm.response.text());")
    return req(nombre, "GET", N + q, token=tok, tests=t + tests)


def patch_n(nombre, tok, ruta, tests, body=None):
    return req(nombre, "PATCH", N + ruta, token=tok, body=body,
               tests=["console.log(pm.response.text().slice(0, 600));"] + tests)


# Consulta de solo lectura dentro del run, con la identidad del Administrador (dueño de las filas por la RLS).
PRE_IDENTIDAD_SQL = [
    "if (pm.variables.get('sandbox_secret') && pm.collectionVariables.get('run_id')) {",
    "  pm.sendRequest({ url: pm.variables.replaceIn('{{base_url}}/sesiones/'), method: 'POST',",
    "    header: [{ key: 'Content-Type', value: 'application/json' },",
    "             { key: 'X-Test-Run-Id', value: pm.collectionVariables.get('run_id') },",
    "             { key: 'X-Sandbox-Secret', value: pm.variables.get('sandbox_secret') }],",
    "    body: { mode: 'raw', raw: JSON.stringify({ correo_electronico: pm.variables.get('correo_admin'),",
    "                                               contrasena: pm.variables.get('contrasena_admin') }) } },",
    "    (e, r) => { if (e || !r || r.code !== 200) { console.warn('Identidad para la consulta: login fallo'); return; }",
    "      pm.collectionVariables.set('tok_admin', r.json().token); });",
    "}",
]


def sql(nombre, consulta, tests):
    return req(nombre, "POST", "{{base_url}}/test-control/query", token=None, pre=PRE_IDENTIDAD_SQL,
               body=json.dumps({"query": " ".join(consulta.split())}, ensure_ascii=False),
               tests=[f"pm.test('{nombre.split(' - ')[0]} - consulta respondida (200)', () => pm.response.to.have.status(200));",
                      "const filas = (pm.response.json() || {}).data || []; console.log(JSON.stringify(filas));"] + tests)


# ─────────────────────────────── G013 ───────────────────────────────
def g013():
    t13, t14, t15 = "TC-M08-013", "TC-M08-014", "TC-M08-015"
    items = [
        pre([L_ADMIN, L_PROD, L_BANDEJA]),
        carpeta("1. TC-M08-013 Bandeja propia con contador de no leídas", [
            lista(f"{t13} - {rol} GET /notificaciones?pagina=1&tamano=50", tok, "?pagina=1&tamano=50", ORDEN + [
                f"pm.test('{t13} - {rol}: bandeja (200) en ≤ 2 s (RNF-03): ' + pm.response.responseTime + ' ms con ' + b.total + ' notificaciones', () => {{"
                " pm.response.to.have.status(200); pm.expect(pm.response.responseTime).to.be.at.most(2000); });",
                f"pm.test('{t13} - {rol}: trae total, no_leidas y los items', () => {{ pm.expect(b.total).to.be.a('number'); pm.expect(b.no_leidas).to.be.a('number').and.at.most(b.total); pm.expect(it.length).to.be.above(0); }});",
                f"pm.test('{t13} - {rol}: orden crítica > advertencia > informativa y de la más reciente a la más antigua', () => pm.expect(ordenada(it)).to.be.true);",
                f"if (b.total <= 500) console.warn('DATO: la bandeja del {rol} tiene ' + b.total + ' notificaciones; RNF-03 pide más de 500 (cuenta 182 del DBA).');",
            ]) for rol, tok in (("Productor", "tok_prod"), ("Administrador", "tok_admin"), ("Productor (bandeja 182)", "tok_bandeja"))
        ]),
        carpeta("2. TC-M08-014 Paginación de la bandeja", [
            lista(f"{t14} - tamano=50", "tok_prod", "?pagina=1&tamano=50", [
                f"pm.test('{t14} - tamano=50: 200 con 50 items', () => {{ pm.response.to.have.status(200); pm.expect(it.length).to.equal(Math.min(50, b.total)); }});",
                "pm.collectionVariables.set('total_prod', String(b.total));"]),
            lista(f"{t14} - tamano=51", "tok_prod", "?pagina=1&tamano=51", [
                f"pm.test('{t14} - tamano=51: 400 VAL_ENTRADA', () => {{ pm.response.to.have.status(400); pm.expect(pm.response.json().error_code).to.equal('VAL_ENTRADA'); }});"]),
            lista(f"{t14} - pagina=0", "tok_prod", "?pagina=0&tamano=50", [
                f"pm.test('{t14} - pagina=0: 400 VAL_ENTRADA', () => {{ pm.response.to.have.status(400); pm.expect(pm.response.json().error_code).to.equal('VAL_ENTRADA'); }});"]),
            lista(f"{t14} - sin tamano", "tok_prod", "?pagina=1", [
                f"pm.test('{t14} - sin tamano: 200', () => pm.response.to.have.status(200));",
                f"pm.test('{t14} - sin tamano: 50 por página, como pide el RF (R7, R10); hoy trae ' + it.length, () => pm.expect(it.length).to.equal(Math.min(50, b.total)));"]),
            req(f"{t14} - última página y recorrido completo sin repetir ni saltar", "GET", N + "?pagina=1&tamano=50", token="tok_prod",
                tests=JS_COMUN + [
                    "const total = pm.response.json().total; const paginas = Math.ceil(total / 50);",
                    "const nums = Array.from({ length: paginas }, (_, k) => k + 1);",
                    "enSerie(nums, p => pedir('GET', '/notificaciones?pagina=' + p + '&tamano=50', 'tok_prod')).then(rs => {",
                    "  const ult = (rs[rs.length - 1].json || {}).items || [];",
                    "  const ids = [].concat(...rs.map(x => ((x.json || {}).items || []).map(n => n.id_notificacion)));",
                    "  console.log('total ' + total + ', páginas ' + paginas + ', última ' + ult.length + ', ids ' + ids.length + ' (únicos ' + new Set(ids).size + ')');",
                    f"  pm.test('{t14} - la última página (' + paginas + ') trae solo el resto: ' + (total - 50 * (paginas - 1)), () => pm.expect(ult.length).to.equal(total - 50 * (paginas - 1)));",
                    f"  pm.test('{t14} - recorrer todas las páginas da el total sin repetir ni saltar notificaciones', () => {{ pm.expect(ids.length).to.equal(total); pm.expect(new Set(ids).size).to.equal(total); }});",
                    "});",
                ]),
        ]),
        carpeta("3. TC-M08-015 Marcar una como leída y marcar todas", [
            lista(f"{t15} - Productor GET una no leída", "tok_prod", "?solo_no_leidas=true&tamano=1", [
                f"pm.test('{t15} - el Productor tiene notificaciones sin leer', () => pm.expect(it.length).to.equal(1));",
                "pm.collectionVariables.set('id_n', String(it[0].id_notificacion)); pm.collectionVariables.set('no_leidas_0', String(b.no_leidas));"]),
            patch_n(f"{t15} - PATCH /notificaciones/{{{{id_n}}}}/leida", "tok_prod", "/{{id_n}}/leida", [
                "const n = pm.response.json();",
                f"pm.test('{t15} - 200 con es_leido=true y estado LEIDA', () => {{ pm.response.to.have.status(200); pm.expect(n.es_leido).to.be.true; pm.expect(n.estado).to.equal('LEIDA'); }});",
                "pm.collectionVariables.set('fecha_lectura', String(n.fecha_lectura));"]),
            lista(f"{t15} - GET después de marcar una", "tok_prod", "?tamano=1", [
                f"pm.test('{t15} - no_leidas baja en 1', () => pm.expect(b.no_leidas).to.equal(Number(pm.collectionVariables.get('no_leidas_0')) - 1));"]),
            patch_n(f"{t15} - PATCH la misma otra vez", "tok_prod", "/{{id_n}}/leida", [
                "const n = pm.response.json();",
                f"pm.test('{t15} - repetir responde 200 sin cambios (misma fecha de lectura)', () => {{ pm.response.to.have.status(200); pm.expect(n.estado).to.equal('LEIDA');"
                " pm.expect(String(n.fecha_lectura)).to.equal(pm.collectionVariables.get('fecha_lectura')); });"]),
            lista(f"{t15} - GET después de repetir", "tok_prod", "?tamano=1", [
                f"pm.test('{t15} - repetir no cambia no_leidas', () => pm.expect(b.no_leidas).to.equal(Number(pm.collectionVariables.get('no_leidas_0')) - 1));"]),
            lista(f"{t15} - GET las que quedan sin leer (con sus ocurrencias agrupadas)", "tok_prod", "?solo_no_leidas=true&tamano=50", [
                "const ocurr = it.reduce((a, n) => a + (n.ocurrencias || 1), 0);",
                "pm.collectionVariables.set('sin_leer_visibles', String(b.no_leidas)); pm.collectionVariables.set('sin_leer_ocurrencias', String(ocurr));",
                "console.log('sin leer en la bandeja: ' + b.no_leidas + ' avisos, ' + ocurr + ' con las ocurrencias agrupadas');",
                f"pm.test('{t15} - quedan avisos sin leer para marcar todas', () => pm.expect(b.no_leidas).to.be.above(0));"]),
            patch_n(f"{t15} - PATCH /notificaciones/leidas", "tok_prod", "/leidas", [
                "const vis = Number(pm.collectionVariables.get('sin_leer_visibles')), occ = Number(pm.collectionVariables.get('sin_leer_ocurrencias'));",
                "const m = (pm.response.json() || {}).marcadas;",
                f"pm.test('{t15} - marcar todas responde 200', () => pm.response.to.have.status(200));",
                f"pm.test('{t15} - marcar todas alcanza al menos a los ' + vis + ' avisos sin leer de la bandeja (responde ' + m + ')', () => pm.expect(m).to.be.at.least(vis));",
                # INC-M08-394: Desarrollo no la corrige; la diferencia queda a la vista en el reporte como observación.
                f"pm.test('{t15} - OBSERVACIÓN (comportamiento aceptado por Desarrollo, INC-M08-394 no se corrige): marcadas = ' + m + ', bandeja sin leer = ' + vis + ' avisos (' + occ + ' con las agrupadas); el conteo incluye avisos que la bandeja no muestra', () => pm.expect(m).to.be.a('number'));"]),
            lista(f"{t15} - GET al final", "tok_prod", "?tamano=1", [
                f"pm.test('{t15} - no_leidas = 0', () => pm.expect(b.no_leidas).to.equal(0));"]),
        ]),
    ]
    return coleccion("TC-M08-G013 Bandeja, paginación y lectura (RF-105)",
                     "TC-M08-013, 014 y 015. Productor qa.m08.productor y Administrador admin.rol. Corre en el sandbox.", items)


# ─────────────────────────────── G014 ───────────────────────────────
ACCIONES = [("'ok' (2 caracteres)", "ok"), ("20 espacios", " " * 20), ("20 letras repetidas", "a" * 20),
            ("'Se revisó el galpón' (19 caracteres)", "Se revisó el galpón")]


def g014():
    t16, t17 = "TC-M08-016", "TC-M08-017"
    rechazo_ajena = ["const r = pm.response.json() || {};",
                     f"pm.test('{t16} - la notificación ajena se rechaza (403/404)', () => pm.expect(pm.response.code).to.be.oneOf([403, 404]));"]
    items = [
        pre([L_ADMIN, L_PROD]),
        carpeta("1. TC-M08-016 Nadie cambia notificaciones de otro usuario", [
            lista(f"{t16} - Administrador GET una no leída suya", "tok_admin", "?solo_no_leidas=true&tamano=1", [
                f"pm.test('{t16} - el Administrador tiene una no leída', () => pm.expect(it.length).to.equal(1));",
                "pm.collectionVariables.set('id_ajena', String(it[0].id_notificacion));"]),
            patch_n(f"{t16} - Productor PATCH leida sobre la del Administrador", "tok_prod", "/{{id_ajena}}/leida", rechazo_ajena + [
                f"pm.test('{t16} - mensaje del RF: «No tiene permisos para modificar notificaciones de otros usuarios» (hoy: ' + r.message + ')', () => pm.expect(r.message).to.match(/no tiene permisos para modificar notificaciones de otros usuarios/i));"]),
            patch_n(f"{t16} - Productor PATCH atendida sobre la del Administrador", "tok_prod", "/{{id_ajena}}/atendida", rechazo_ajena,
                    body='{\n  "accion_documentada": "Intento de atender una notificacion ajena QA"\n}'),
            patch_n(f"{t16} - Productor PATCH descartada sobre la del Administrador", "tok_prod", "/{{id_ajena}}/descartada", rechazo_ajena),
            lista(f"{t16} - Administrador GET su notificación después de los intentos", "tok_admin", "?solo_no_leidas=true&tamano=1", [
                f"pm.test('{t16} - la notificación del Administrador sigue sin leer (NUEVA)', () => {{ pm.expect(String(it[0].id_notificacion)).to.equal(pm.collectionVariables.get('id_ajena')); pm.expect(it[0].estado).to.equal('NUEVA'); }});"]),
            patch_n(f"{t16} - PATCH /notificaciones/999999999/leida", "tok_prod", "/999999999/leida", [
                f"pm.test('{t16} - inexistente: 404 NOTIFICACION_NO_ENCONTRADA', () => {{ pm.response.to.have.status(404); pm.expect(pm.response.json().error_code).to.equal('NOTIFICACION_NO_ENCONTRADA'); }});"]),
            req(f"{t16} - GET /notificaciones sin token", "GET", N, token=None, tests=[
                f"pm.test('{t16} - sin token: 401', () => pm.response.to.have.status(401));"]),
            req(f"{t16} - PATCH leida sin token", "PATCH", N + "/{{id_ajena}}/leida", token=None, tests=[
                f"pm.test('{t16} - PATCH sin token: 401', () => pm.response.to.have.status(401));"]),
        ]),
        carpeta("2. TC-M08-017 Atender una crítica con acción documentada y bloquear su descarte", [
            lista(f"{t17} - Administrador GET una CRÍTICA nueva", "tok_admin", "?nivel=CRITICA&estado=NUEVA&tamano=1", [
                f"pm.test('{t17} - hay una notificación CRÍTICA nueva', () => pm.expect(it.length).to.equal(1));",
                "pm.collectionVariables.set('id_crit', String(it[0].id_notificacion));",
                f"pm.test('{t17} - la crítica no ofrece Descartar (puede_descartarse=false) y sí Atender', () => {{ pm.expect(it[0].puede_descartarse).to.be.false; pm.expect(it[0].puede_atenderse).to.be.true; }});"]),
            patch_n(f"{t17} - forzar Descartar la crítica", "tok_admin", "/{{id_crit}}/descartada", [
                f"pm.test('{t17} - descartar una crítica: 422 CRITICA_NO_DESCARTABLE con mensaje', () => {{ pm.response.to.have.status(422);"
                " pm.expect(pm.response.json().error_code).to.equal('CRITICA_NO_DESCARTABLE'); pm.expect(pm.response.json().message).to.be.a('string').and.not.empty; });"]),
            *[patch_n(f"{t17} - Atender con {n}", "tok_admin", "/{{id_crit}}/atendida", [
                f"pm.test('{t17} - acción {esc(n)} rechazada (400 VAL_ENTRADA)', () => {{ pm.response.to.have.status(400); pm.expect(pm.response.json().error_code).to.equal('VAL_ENTRADA'); }});"],
                body=json.dumps({"accion_documentada": v}, ensure_ascii=False)) for n, v in ACCIONES],
            lista(f"{t17} - la crítica sigue activa tras los 4 rechazos", "tok_admin", "?nivel=CRITICA&estado=NUEVA&tamano=50", [
                f"pm.test('{t17} - la crítica sigue NUEVA', () => pm.expect(it.map(n => String(n.id_notificacion))).to.include(pm.collectionVariables.get('id_crit')));"]),
            patch_n(f"{t17} - Atender con 'Se revisó el galpón.' (20 caracteres)", "tok_admin", "/{{id_crit}}/atendida", [
                "const n = pm.response.json();",
                f"pm.test('{t17} - 20 caracteres con sentido: ATENDIDA con la acción y la hora guardadas', () => {{ pm.response.to.have.status(200);"
                " pm.expect(n.estado).to.equal('ATENDIDA'); pm.expect(n.accion_documentada).to.equal('Se revisó el galpón.'); pm.expect(Date.parse(n.fecha_atencion)).to.not.be.NaN; });"],
                body=json.dumps({"accion_documentada": "Se revisó el galpón."}, ensure_ascii=False)),
            patch_n(f"{t17} - Atender otra vez la ya atendida", "tok_admin", "/{{id_crit}}/atendida", [
                f"pm.test('{t17} - una atendida no se vuelve a cerrar (422 NOTIFICACION_CERRADA)', () => {{ pm.response.to.have.status(422); pm.expect(pm.response.json().error_code).to.equal('NOTIFICACION_CERRADA'); }});"],
                body=json.dumps({"accion_documentada": "Se revisó el galpón otra vez."}, ensure_ascii=False)),
            *[x for nivel, tk, quien in (("ADVERTENCIA", "tok_admin", "Administrador"), ("INFORMATIVA", "tok_prod", "Productor")) for x in (
                lista(f"{t17} - {quien} GET una {nivel} nueva", tk, f"?nivel={nivel}&estado=NUEVA&tamano=1", [
                    f"pm.test('{t17} - hay una {nivel} nueva que se puede descartar', () => {{ pm.expect(it.length).to.equal(1); pm.expect(it[0].puede_descartarse).to.be.true; }});",
                    f"pm.collectionVariables.set('id_{nivel.lower()}', String(it[0].id_notificacion));"]),
                patch_n(f"{t17} - Descartar la {nivel}", tk, f"/{{{{id_{nivel.lower()}}}}}/descartada", [
                    f"pm.test('{t17} - la {nivel} queda DESCARTADA (200)', () => {{ pm.response.to.have.status(200); pm.expect(pm.response.json().estado).to.equal('DESCARTADA'); }});"]),
                lista(f"{t17} - historial: la {nivel} descartada se sigue consultando", tk, f"?nivel={nivel}&estado=DESCARTADA&tamano=50", [
                    f"pm.test('{t17} - la {nivel} descartada sigue en el historial', () => pm.expect(it.map(n => String(n.id_notificacion))).to.include(pm.collectionVariables.get('id_{nivel.lower()}')));"]),
            )],
            lista(f"{t17} - panel principal sin las cerradas", "tok_admin", "?tamano=50&nivel=CRITICA", [
                f"pm.test('{t17} - la crítica atendida sale del panel principal', () => pm.expect(it.map(n => String(n.id_notificacion))).to.not.include(pm.collectionVariables.get('id_crit')));"]),
        ]),
    ]
    return coleccion("TC-M08-G014 Propiedad y ciclo de vida de las notificaciones (RF-105)",
                     "TC-M08-016 y 017. Críticas y advertencias de la bandeja del Administrador; todo se revierte con el sandbox.", items)


# ─────────────────────────────── G015 ───────────────────────────────
# Fuera del sandbox (autorizado por el usuario el 2026-11-21): la alerta la genera el worker post-commit, que no ve
# la transacción del sandbox. Se crean dos dispositivos con su sensor, SIN historial, en el área 1468 (ya está en
# rojo): con los sensores sembrados (inactivos desde hace días) la calidad RF-62 se traba con
# SOLAPAMIENTO_INACTIVIDAD_PENDIENTE y nunca hay alerta. Al final se descartan las alertas y se desactivan los dos
# dispositivos, para no tocar los datos de los demás. La especie 722 no tenía umbral de temperatura: se crea uno.
L_OTRA = ("tok_otra", "correo_otra_finca", "contrasena_otra_finca", "Productor de otra finca", "id_otra")
SENSOR_A = {"device_id": "{{dev_a}}", "sensor_id": "{{sen_a}}", "serial": "{{serial_a}}"}
SENSOR_B = {"device_id": "{{dev_b}}", "sensor_id": "{{sen_b}}", "serial": "{{serial_b}}"}
AREA_G015 = 1468
UMBRAL_722 = {"id_especie": 722, "id_variable_ambiental": 9, "valor_min": 0, "valor_max": 50, "niveles": [
    {"nivel": "normal", "limite_inferior": 0, "limite_superior": 28},
    {"nivel": "precaucion", "limite_inferior": 28, "limite_superior": 34},
    {"nivel": "critico", "limite_inferior": 34, "limite_superior": 50}]}
DESTINOS = [("Productor", "tok_prod", True), ("Veterinario", "tok_vet", True), ("Ingeniero de Campo", "tok_ing", True),
            ("Contador", "tok_cont", False), ("Productor de otra finca", "tok_otra", False)]
TODOS = DESTINOS + [("Administrador", "tok_admin", None)]

# Ayudantes JS (fuera del sandbox): pedir, esperar y buscar las críticas nuevas de telemetría de una bandeja.
JS_G015 = [
    "const H = tok => [{ key: 'Authorization', value: 'Bearer ' + pm.collectionVariables.get(tok) }, { key: 'X-Zona-Horaria', value: 'America/Bogota' }];",
    "const pedir = (ruta, tok) => new Promise(ok => pm.sendRequest({ url: pm.variables.replaceIn('{{base_url}}') + ruta, method: 'GET', header: H(tok) },",
    "  (e, r) => ok((() => { try { return r.json(); } catch (x) { return null; } })())));",
    "const dormir = ms => new Promise(ok => setTimeout(ok, ms));",
    "const base = tok => JSON.parse(pm.collectionVariables.get('base_' + tok) || '[]');",
    "// Críticas de telemetría de la bandeja (nuevas o leídas) que no estaban antes de la corrida.",
    "const nuevas = async tok => { const b = await pedir('/notificaciones?nivel=CRITICA&modulo=telemetria&tamano=50', tok);",
    "  const ya = base(tok), t = Date.parse(pm.collectionVariables.get('t_inicio'));",
    "  return ((b || {}).items || []).filter(n => !ya.includes(n.id_notificacion) || Date.parse(n.fecha_ultima_ocurrencia || 0) >= t); };",
    "const esperarNuevas = async (tok, minimo, maxMs) => { const t0 = Date.now(); let l = [];",
    "  while (Date.now() - t0 < maxMs) { l = await nuevas(tok); if (l.length >= minimo) break; await dormir(5000); }",
    "  return { l, ms: Date.now() - t0 }; };",
    "const sumar = l => l.reduce((a, n) => a + (n.ocurrencias || 1), 0);",
    "const delArea = (l, nombre) => l.filter(n => (n.mensaje || '').includes(nombre));",
]
# Los dos sensores están en la misma área: las notificaciones se distinguen por el nombre del sensor del mensaje.
A_JS, B_JS = "pm.collectionVariables.get('nombre_sen_a')", "pm.collectionVariables.get('nombre_sen_b')"


def alta_sensor(x):
    """Dispositivo + sensor de temperatura + asociación al área + calibración (Administrador), sin historial."""
    d = "{{base_url}}/configuracion/dispositivos-iot"
    return [
        req(f"PRE - Crear el dispositivo {x.upper()} en el área 1468", "POST", d, token="tok_admin", fuera=True,
            pre=["if (!pm.collectionVariables.get('sufijo')) pm.collectionVariables.set('sufijo', Date.now().toString(36).toUpperCase());",
                 f"pm.collectionVariables.set('serial_{x}', 'QA-M08-G015-{x.upper()}-' + pm.collectionVariables.get('sufijo'));"],
            body="{\n  \"serial\": \"{{serial_" + x + "}}\",\n  \"descripcion\": \"Nodo temporal TC-M08-G015 (se desactiva al terminar)\",\n"
                 "  \"id_infraestructura\": " + str(AREA_G015) + ",\n  \"id_tipo_dispositivo\": 3,\n  \"es_activo\": true\n}",
            tests=["console.log(pm.response.text().slice(0, 300));",
                   f"pm.test('PRE - dispositivo {x.upper()} creado (201)', () => pm.response.to.have.status(201));",
                   f"pm.collectionVariables.set('dev_{x}', String((pm.response.json() || {{}}).id_dispositivo_iot || ''));"]),
        req(f"PRE - Crear el sensor de temperatura {x.upper()}", "POST", d + "/{{dev_" + x + "}}/sensores", token="tok_admin", fuera=True,
            body="{\n  \"nombre\": \"QA M08 G015 sensor " + x.upper() + " {{sufijo}}\",\n  \"categoria\": \"TEMPERATURA\"\n}",
            tests=["console.log(pm.response.text().slice(0, 300));",
                   f"pm.test('PRE - sensor {x.upper()} creado (201)', () => pm.response.to.have.status(201));",
                   "const r = pm.response.json() || {};",
                   f"pm.collectionVariables.set('sen_{x}', String(r.id_sensores || r.id_sensor || ''));",
                   f"pm.collectionVariables.set('nombre_sen_{x}', r.nombre || '');"]),
        req(f"PRE - Asociar el sensor {x.upper()} al área 1468", "POST", "{{base_url}}/configuracion/sensores/{{sen_" + x + "}}/asociar",
            token="tok_admin", fuera=True,
            body="{\n  \"id_dispositivo_iot\": {{dev_" + x + "}},\n  \"id_infraestructura\": " + str(AREA_G015) + ",\n  \"punto_instalacion\": \"Punto central (prueba QA)\"\n}",
            tests=["console.log(pm.response.text().slice(0, 300));",
                   f"pm.test('PRE - sensor {x.upper()} asociado (200/201)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201]));"]),
        req(f"PRE - Calibrar el sensor {x.upper()}", "POST", "{{base_url}}/configuracion/sensores/{{sen_" + x + "}}/calibrar",
            token="tok_admin", fuera=True, pre=["pm.collectionVariables.set('t_calib', new Date(Date.now() - 120000).toISOString());"],
            body="{\n  \"id_dispositivo_iot\": {{dev_" + x + "}},\n  \"id_infraestructura\": " + str(AREA_G015) + ",\n  \"valor_referencia\": 25.0,\n"
                 "  \"ganancia\": 1.0,\n  \"offset\": 0.0,\n  \"fecha_calibracion\": \"{{t_calib}}\",\n  \"modo_calibracion\": \"SENSOR\"\n}",
            tests=["console.log(pm.response.text().slice(0, 300));",
                   f"pm.test('PRE - sensor {x.upper()} calibrado (200/201)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201]));"]),
    ]


def lectura(nombre, sensor, valor, tests, pre_extra=None, reintentar=False):
    body = ("{\n  \"device_id\": " + str(sensor["device_id"]) + ",\n  \"sensor_id\": " + str(sensor["sensor_id"]) +
            ",\n  \"serial\": \"" + sensor["serial"] + "\",\n  \"tipo_variable\": \"TEMPERATURA_AMBIENTAL\",\n  \"valor\": " + str(valor) +
            ",\n  \"unidad\": \"°C\",\n  \"timestamp_captura\": \"{{ahora}}\"\n}")
    tc = nombre.split(" - ")[0]
    item = req(nombre, "POST", "{{base_url}}/iot/telemetria", token=None, fuera=True, body=body,
               pre=(pre_extra or []) + ["// 30 s atrás: el reloj de la PC puede ir adelantado y la BD rechaza capturas futuras (ERROR_TIEMPO).",
                     "pm.collectionVariables.set('ahora', new Date(Date.now() - 30000).toISOString());"],
               tests=["console.log(pm.response.text().slice(0, 500));"] + ([
                   "// Un nodo recién creado tarda en aceptar lecturas (401 «Dispositivo o sensor no encontrado o inactivo»):",
                   "// se reintenta cada 10 s, hasta 12 veces, antes de dar la lectura por fallida.",
                   "const n = Number(pm.collectionVariables.get('intentos_l1') || 0);",
                   "if (pm.response.code === 401 && n < 12) { pm.collectionVariables.set('intentos_l1', String(n + 1));",
                   "  console.log('Nodo aún no habilitado (intento ' + (n + 1) + '): se reintenta en 10 s');",
                   "  setTimeout(() => {}, 10000); pm.execution.setNextRequest(pm.info.requestName); return; }",
                   "console.log('Primera lectura aceptada tras ' + n + ' reintentos');",
               ] if reintentar else []) + [
                      f"pm.test('{tc} - lectura aceptada por la ingesta (201, LECTURA_VALIDA)', () => {{ pm.response.to.have.status(201);"
                      " pm.expect((pm.response.json() || {}).estado_calidad).to.equal('LECTURA_VALIDA'); });"] + tests)
    item["request"]["header"].append({"key": "Authorization", "value": "Bearer {{broker_token}}"})
    return item


def espera(nombre, segundos_desde, var_t0):
    """Espera hasta que pasen `segundos_desde` segundos desde la marca `var_t0`."""
    return req(nombre, "GET", "{{base_url}}/health", token=None, fuera=True, pre=[
        f"const falta = Number(pm.collectionVariables.get('{var_t0}')) + {segundos_desde * 1000} - Date.now();",
        "console.log('Esperando ' + Math.max(0, Math.round(falta / 1000)) + ' s');",
        "if (falta > 0) setTimeout(() => {}, falta);"], tests=["pm.test('espera - API viva (200)', () => pm.response.to.have.status(200));"])


def registrar_alertas(var):
    sensor_id = "' + pm.collectionVariables.get('" + var + "') + '"
    return [
        f"  const al = (await pedir('/iot/alertas?id_sensor={sensor_id}&fecha_desde=' + encodeURIComponent(pm.collectionVariables.get('t_inicio')), 'tok_admin') || {{}}).items || [];",
        "  const ya = JSON.parse(pm.collectionVariables.get('alertas_creadas') || '[]');",
        "  pm.collectionVariables.set('alertas_creadas', JSON.stringify([...new Set(ya.concat(al.map(a => a.id_alerta)))]));",
        f"  console.log('Alertas del sensor {sensor_id} desde el inicio: ' + JSON.stringify(al.map(a => ({{ id: a.id_alerta, sev: a.severidad, estado: a.estado_alerta, tipo: a.tipo_alerta }}))));",
    ]


def g015():
    t18, t19, t24 = "TC-M08-018", "TC-M08-019", "TC-M08-024"
    logins = [login(*l, fuera=True) for l in (L_ADMIN, L_PROD, rf103.L_VET, rf103.L_CONT, rf103.L_ING, L_OTRA)]
    prep = [
        req("PRE - Umbral de temperatura ambiental de la especie 722 (se crea si no existe)", "GET",
            "{{base_url}}/configuracion/umbrales?id_especie=722", token="tok_admin", fuera=True, tests=[
                "const it = (pm.response.json() || {}).items || [];",
                "const u = it.find(x => x.id_variable_ambiental === 9);",
                "pm.collectionVariables.set('hay_umbral', u ? '1' : '');",
                "console.log(u ? 'Ya existe el umbral ' + u.id_umbral_ambiental : 'No hay umbral de temperatura para la especie 722: se crea');",
                "pm.test('PRE - consulta de umbrales (200)', () => pm.response.to.have.status(200));"]),
        req("PRE - Crear el umbral (normal 0-28, precaución 28-34, crítico 34-50 °C; contiguos desde el mínimo)", "POST",
            "{{base_url}}/configuracion/umbrales", token="tok_admin", fuera=True, body=UMBRAL_722,
            pre=["if (pm.collectionVariables.get('hay_umbral')) { console.log('Umbral ya creado: se omite'); pm.execution.skipRequest(); }"],
            tests=["console.log(pm.response.text().slice(0, 400));",
                   "pm.test('PRE - umbral creado (201)', () => pm.response.to.have.status(201));"]),
        *alta_sensor("a"), *alta_sensor("b"),
        req("PRE - Bandejas antes de la corrida (críticas de telemetría de cada usuario)", "GET", "{{base_url}}/health", token=None, fuera=True,
            tests=JS_G015 + [
                "(async () => {",
                f"  for (const tok of {json.dumps([t for _, t, _ in TODOS])}) {{",
                "    const b = await pedir('/notificaciones?nivel=CRITICA&modulo=telemetria&tamano=50', tok);",
                "    pm.collectionVariables.set('base_' + tok, JSON.stringify(((b || {}).items || []).map(n => n.id_notificacion)));",
                "    console.log(tok + ': ' + (((b || {}).items || []).length) + ' críticas de telemetría antes');",
                "  }",
                "  pm.collectionVariables.set('t_inicio', new Date(Date.now() - 60000).toISOString());",
                "})();",
                "pm.test('PRE - API viva (200)', () => pm.response.to.have.status(200));"]),
        req(f"{t24} - Ingeniero registra un token de push inválido", "POST", "{{base_url}}/usuarios/me/fcm-token", token="tok_ing", fuera=True,
            body='{\n  "token": "token-invalido-qa"\n}', tests=[
                "console.log(pm.response.text().slice(0, 400));",
                f"pm.test('{t24} - el token se registra sin error para el usuario (200)', () => pm.response.to.have.status(200));"]),
    ]
    c18 = [
        lectura(f"{t18} - Lectura crítica 45 °C en el sensor A (área 1468)", SENSOR_A, 45.0,
                ["if (pm.response.code === 201) pm.collectionVariables.set('t_l1', String(Date.now()));"], reintentar=True),
        req(f"{t18} - La alerta crítica se genera y llega a la bandeja de quien corresponde", "GET", "{{base_url}}/health",
            token=None, fuera=True, tests=JS_G015 + [
                "(async () => {",
                "  // La bandeja del Productor marca el tiempo de entrega (hasta 90 s); el resto se lee enseguida.",
                "  const p = await esperarNuevas('tok_prod', 1, 90000);",
                "  const r = { tok_prod: p };",
                "  // La entrega va en serie por destinatario: a los que deben recibirla se les espera hasta 60 s cada uno.",
                f"  for (const tok of {json.dumps([t for _, t, d in DESTINOS if d and t != 'tok_prod'])}) r[tok] = await esperarNuevas(tok, 1, 60000);",
                f"  for (const tok of {json.dumps([t for _, t, d in TODOS if not d])}) r[tok] = {{ l: await nuevas(tok), ms: 0 }};",
                *registrar_alertas("sen_a"),
                f"  pm.test('{t18} - la lectura de 45 °C genera una alerta CRÍTICA', () => pm.expect(al.some(a => a.severidad === 'CRITICO')).to.be.true);",
                f"  pm.test('{t18} - llega a la bandeja del Productor al instante (' + Math.round(p.ms / 1000) + ' s)', () => pm.expect(p.l.length).to.be.above(0));",
                *[f"  pm.test('{t18} - {rol}: ' + (r['{tok}'].l.length ? 'la recibe' : 'no la recibe') + ' en la bandeja ({'debe recibirla' if debe else 'no debe recibirla'})', () => pm.expect(r['{tok}'].l.length > 0).to.equal({str(debe).lower()}));"
                  for rol, tok, debe in DESTINOS],
                "  console.log('Administrador: ' + r.tok_admin.l.length + ' críticas nuevas (el RF lo pone solo si el área no tiene destinatarios)');",
                "  const m = (p.l[0] || {});",
                "  console.log('Notificación del Productor: ' + JSON.stringify({ id: m.id_notificacion, nivel: m.nivel, estado: m.estado, ocurrencias: m.ocurrencias, mensaje: m.mensaje }));",
                "  console.warn('NO VERIFICABLE: push en ≤ 60 s y correo en ≤ 5 min. Las cuentas qa.m08 son @sgpmp-test.com (sin buzón) y no hay un navegador con push suscrito (bloqueo de terceros, no incidencia).');",
                "})();"]),
    ]
    c19 = [
        espera(f"{t19} - Esperar 1 minuto desde la primera lectura", 60, "t_l1"),
        lectura(f"{t19} - Paso 1: la misma lectura crítica 1 minuto después (mismo sensor)", SENSOR_A, 45.5, []),
        req(f"{t19} - Paso 1: sigue habiendo una sola notificación de ese evento", "GET", "{{base_url}}/health", token=None, fuera=True, tests=JS_G015 + [
            "(async () => {",
            "  await dormir(30000);",
            f"  const l = delArea(await nuevas('tok_prod'), {A_JS});",
            "  console.log('Productor tras la 2ª lectura: ' + JSON.stringify(l.map(n => ({ id: n.id_notificacion, ocurrencias: n.ocurrencias, fecha: n.fecha_envio }))));",
            "  pm.collectionVariables.set('ocurr_paso1', String(sumar(l)));",
            f"  pm.test('{t19} - mismo evento y sensor en < 5 min: una sola notificación (avisos ' + l.length + ', ocurrencias ' + sumar(l) + ')', () => {{ pm.expect(l.length).to.equal(1); pm.expect(sumar(l)).to.equal(1); }});",
            *registrar_alertas("sen_a"),
            "})();"]),
        lectura(f"{t19} - Paso 3: lectura crítica del mismo tipo en otro sensor (B, otro nodo de la finca) en < 5 min", SENSOR_B, 46.0, []),
        req(f"{t19} - Paso 3: el evento del otro sensor llega como notificación aparte", "GET", "{{base_url}}/health", token=None, fuera=True, tests=JS_G015 + [
            "(async () => {",
            "  const { l } = await esperarNuevas('tok_prod', 2, 90000);",
            f"  const a = delArea(l, {A_JS}), b = delArea(l, {B_JS});",
            "  console.log('Productor: ' + JSON.stringify(l.map(n => ({ id: n.id_notificacion, ocurrencias: n.ocurrencias, mensaje: (n.mensaje || '').slice(0, 110) }))));",
            f"  pm.test('{t19} - mismo tipo en otro sensor en < 5 min: una notificación por cada sensor (A: ' + a.length + ', B: ' + b.length + ')', () => {{ pm.expect(a.length).to.equal(1); pm.expect(b.length).to.equal(1); }});",
            "  // La entrega a cada destinatario va en serie: se espera hasta 60 s la del Ingeniero (token de push inválido).",
            f"  let ing = []; const ti = Date.now(); while (Date.now() - ti < 60000) {{ ing = delArea(await nuevas('tok_ing'), {B_JS}); if (ing.length) break; await dormir(5000); }}",
            f"  pm.test('{t24} - con el token de push inválido, el Ingeniero recibe en la bandeja la notificación generada después de registrarlo (' + ing.length + ')', () => pm.expect(ing.length).to.equal(1));",
            "  console.warn('BLOQUEADO (sin acceso): el log técnico con el fallo del push y sus reintentos (1, 5 y 15 min) no se puede revisar sin los logs del backend de TEST.');",
            *registrar_alertas("sen_b"),
            "})();"]),
        espera(f"{t19} - Esperar a que pasen 6 minutos desde la primera lectura", 370, "t_l1"),
        lectura(f"{t19} - Paso 2: la misma lectura crítica pasados 6 minutos (mismo sensor)", SENSOR_A, 46.5, []),
        req(f"{t19} - Paso 2: pasados 5 minutos llega una segunda notificación independiente", "GET", "{{base_url}}/health", token=None, fuera=True, tests=JS_G015 + [
            "(async () => {",
            "  const antes = Number(pm.collectionVariables.get('ocurr_paso1'));",
            "  let l = []; const t0 = Date.now();",
            f"  while (Date.now() - t0 < 90000) {{ l = delArea(await nuevas('tok_prod'), {A_JS}); if (sumar(l) > antes) break; await dormir(5000); }}",
            "  console.log('Productor (sensor A): ' + JSON.stringify(l.map(n => ({ id: n.id_notificacion, ocurrencias: n.ocurrencias, fecha: n.fecha_envio }))));",
            f"  pm.test('{t19} - pasados 5 minutos el mismo evento genera otra notificación (ocurrencias ' + antes + ' → ' + sumar(l) + ')', () => pm.expect(sumar(l)).to.equal(antes + 1));",
            *registrar_alertas("sen_a"),
            "})();"]),
    ]
    limpieza = [
        req("LIMPIEZA - Cerrar las alertas creadas por la corrida (descartar, o atender y resolver)", "GET", "{{base_url}}/health", token=None, fuera=True,
            tests=JS_G015 + [
                "const ids = JSON.parse(pm.collectionVariables.get('alertas_creadas') || '[]');",
                "const patch = (id, estado) => new Promise(ok => pm.sendRequest({ url: pm.variables.replaceIn('{{base_url}}') + '/iot/alertas/' + id + '/estado', method: 'PATCH',",
                "  header: H('tok_admin').concat([{ key: 'Content-Type', value: 'application/json' }]),",
                "  body: { mode: 'raw', raw: JSON.stringify({ nuevo_estado: estado, motivo: 'Prueba QA TC-M08-G015: lectura simulada, se cierra al terminar.' }) } }, (e, r) => ok(r ? r.code : 0)));",
                "(async () => {",
                "  const res = [];",
                "  for (const id of ids) {",
                "    const a = await pedir('/iot/alertas/' + id, 'tok_admin') || {};",
                "    if (['VENCIDA', 'RESUELTA', 'DESCARTADA'].includes(a.estado_alerta)) { res.push(id + ':' + a.estado_alerta); continue; }",
                "    let c = await patch(id, 'DESCARTADA'); if (c !== 200) { await patch(id, 'EN_ATENCION'); c = await patch(id, 'RESUELTA'); }",
                "    res.push(id + ':' + (c === 200 ? 'CERRADA' : 'ERROR ' + c)); }",
                "  console.log('Alertas cerradas: ' + res.join(', '));",
                "  pm.test('LIMPIEZA - ninguna alerta creada queda activa (' + (res.join(', ') || 'ninguna') + ')', () => pm.expect(res.every(x => !x.includes('ERROR'))).to.be.true);",
                "})();"]),
        *[req(f"LIMPIEZA - Desactivar el dispositivo temporal {x.upper()}", "PATCH",
              "{{base_url}}/configuracion/dispositivos-iot/{{dev_" + x + "}}/desactivar", token="tok_admin", fuera=True,
              pre=[f"if (!pm.collectionVariables.get('dev_{x}')) {{ console.log('No se creó el dispositivo {x.upper()}'); pm.execution.skipRequest(); }}"],
              tests=["console.log(pm.response.text().slice(0, 300));",
                     f"pm.test('LIMPIEZA - dispositivo {x.upper()} desactivado (200)', () => pm.response.to.have.status(200));"])
          for x in ("a", "b")],
    ]
    col = coleccion("TC-M08-G015 Canales, destinatarios y duplicados (RF-105)",
                    "TC-M08-018, 019 y 024 FUERA del sandbox (el worker post-commit no ve la transacción del sandbox). Autorizado por el usuario el "
                    "2026-11-21. Dos nodos temporales sin historial en el área 1468; al final se descartan las alertas y se desactivan. "
                    "Push, correo y logs técnicos no son verificables en TEST.",
                    [carpeta("0. Precondiciones (fuera del sandbox)", logins + prep),
                     carpeta("1. TC-M08-018 Canales y destinatarios de una alerta crítica", c18),
                     carpeta("2. TC-M08-019 y 024 Duplicados en 5 minutos y push inválido", c19),
                     carpeta("9. Limpieza", limpieza)])
    col["item"] = [x for x in col["item"] if not x["name"].startswith("9. Rollback")]
    col["variable"] += [{"key": k, "value": ""} for k in ("tok_otra", "ahora", "t_l1", "t_inicio", "alertas_creadas", "hay_umbral", "ocurr_paso1", "sufijo", "t_calib",
                                                     "dev_a", "sen_a", "serial_a", "nombre_sen_a", "dev_b", "sen_b", "serial_b", "nombre_sen_b", "intentos_l1")]
    return col


# ─────────────────────────────── G016 ───────────────────────────────
# Lo que no debe aparecer en un texto visible (CLAUDE.md, «Textos visibles»): códigos RF/RFC/Mnn, enums crudos,
# ids con «#», «None»/«null» y áreas por número. Los códigos van sueltos: «M05» dentro de un nombre que eligió el
# usuario (activo QA-M05-BOV-ICA-CRIT, área QA-M05-C1) no es un código del sistema.
CODIGOS = r"/((?<![\w-])RFC?-\d+(?![\w-])|(?<![\w-])M0\d(?![\w-])|\b[A-Z]{2,}_[A-Z_]{2,}\b|#\d+|\bNone\b|\bnull\b|\bÁrea \d+\b)/"


def g016():
    t20, t21, t22 = "TC-M08-020", "TC-M08-021", "TC-M08-022"
    filtro = lambda q, campo, valor, tok="tok_admin": lista(f"{t21} - filtro {q}", tok, "?" + q + "&tamano=50", [
        f"pm.test('{t21} - {q}: 200 y solo devuelve {campo} = {valor}', () => {{ pm.response.to.have.status(200); it.forEach(n => pm.expect(n.{campo}).to.equal('{valor}')); }});",
        f"if (!it.length) console.warn('DATO: {q} no tiene filas en esta bandeja');"])
    malo = lambda q: lista(f"{t21} - filtro fuera de catálogo {q}", "tok_admin", "?" + q, [
        f"pm.test('{t21} - {q}: 400 VAL_ENTRADA', () => {{ pm.response.to.have.status(400); pm.expect(pm.response.json().error_code).to.equal('VAL_ENTRADA'); }});"])
    todas = lambda nombre, tok, q, tests: req(nombre, "GET", N + "?pagina=1&tamano=50" + q, token=tok, tests=JS_COMUN + [
        "const total = pm.response.json().total; const nums = Array.from({ length: Math.ceil(total / 50) }, (_, k) => k + 1);",
        f"enSerie(nums, p => pedir('GET', '/notificaciones?tamano=50&pagina=' + p + '{q}', '{tok}')).then(rs => {{",
        "  const it = [].concat(...rs.map(x => (x.json || {}).items || []));",
        "  const dias = n => (Date.now() - Date.parse(n.fecha_envio)) / 86400e3;",
        "  console.log('total ' + total + ', leídas ' + it.length + ', la más antigua de ' + Math.round(Math.max(0, ...it.map(dias))) + ' días');",
    ] + tests + ["});"])
    items = [
        pre([L_ADMIN, L_PROD]),
        carpeta("1. TC-M08-020 Mensajes claros, sin códigos internos", [
            lista(f"{t20} - Administrador GET {nivel}", "tok_admin", f"?nivel={nivel}&tamano=50", [
                f"const malos = it.filter(n => {CODIGOS}.test(n.mensaje)).map(n => n.id_notificacion + ': ' + n.mensaje);",
                "console.log(JSON.stringify(it.map(n => n.mensaje)));",
                f"pm.test('{t20} - {nivel}: ningún mensaje trae códigos internos, enums ni ids (' + malos.length + ' con códigos)', () => pm.expect(malos).to.eql([]));",
                f"pm.test('{t20} - {nivel}: cada mensaje tiene texto', () => it.forEach(n => pm.expect(n.mensaje.trim()).to.not.be.empty));",
            ]) for nivel in ("CRITICA", "ADVERTENCIA")
        ]),
        carpeta("2. TC-M08-021 Filtros, orden por prioridad y agrupamiento", [
            filtro("nivel=CRITICA", "nivel", "CRITICA"),
            filtro("estado=LEIDA", "estado", "LEIDA", tok="tok_prod"),
            filtro("modulo=telemetria", "modulo", "telemetria"),
            lista(f"{t21} - filtros combinados nivel=CRITICA&modulo=telemetria", "tok_admin", "?nivel=CRITICA&modulo=telemetria&tamano=50", [
                f"pm.test('{t21} - combinados (AND): solo críticas de telemetría', () => {{ pm.response.to.have.status(200); it.forEach(n => {{ pm.expect(n.nivel).to.equal('CRITICA'); pm.expect(n.modulo).to.equal('telemetria'); }}); }});"]),
            malo("nivel=XYZ"), malo("estado=XYZ"), malo("modulo=xyz"),
            lista(f"{t21} - orden de una bandeja mezclada (Administrador)", "tok_admin", "?tamano=50", ORDEN + [
                "console.log(JSON.stringify(it.map(n => n.nivel + ' ' + n.fecha_envio)));",
                f"pm.test('{t21} - primero críticas, luego advertencias e informativas; dentro de cada nivel de la más reciente a la más antigua', () => pm.expect(ordenada(it)).to.be.true);",
                f"pm.test('{t21} - cada notificación trae su contador de ocurrencias (agrupamiento)', () => it.forEach(n => pm.expect(n.ocurrencias).to.be.a('number').and.at.least(1)));",
                "const grupos = it.filter(n => n.ocurrencias > 1); console.log('Agrupadas: ' + JSON.stringify(grupos.map(n => [n.id_notificacion, n.ocurrencias])));",
                "if (!grupos.length) console.warn('DATO: ninguna notificación agrupada en esta bandeja; agruparlas exige generar la misma alerta del mismo activo (TC-019, bloqueado).');",
            ]),
        ]),
        carpeta("3. TC-M08-022 Historial de 90 días y borrado de informativas a los 30 días", [
            todas(f"{t22} - Productor: panel principal completo", "tok_prod", "", [
                f"  pm.test('{t22} - el panel principal no trae notificaciones de más de 90 días', () => pm.expect(it.filter(n => dias(n) > 90).map(n => n.id_notificacion)).to.eql([]));",
                "  pm.collectionVariables.set('total_principal', String(total));",
            ]),
            todas(f"{t22} - Productor: con incluir_archivadas=true", "tok_prod", "&incluir_archivadas=true", [
                f"  pm.test('{t22} - incluir_archivadas trae al menos lo del panel principal', () => pm.expect(total).to.be.at.least(Number(pm.collectionVariables.get('total_principal'))));",
                "  const viejas = it.filter(n => dias(n) > 90); console.log('Archivadas (> 90 días): ' + viejas.length);",
                "  if (!viejas.length) console.warn('DATO: la bandeja no tiene notificaciones de más de 90 días (las fronteras 89/90/91 están en la cuenta 182 del DBA).');",
            ]),
            *[todas(f"{t22} - Productor: informativas {e} con archivadas", "tok_prod", f"&nivel=INFORMATIVA&estado={e}&incluir_archivadas=true", [
                f"  pm.test('{t22} - no quedan informativas {e} de más de 30 días (purga diaria)', () => pm.expect(it.filter(n => dias(n) > 31).map(n => n.id_notificacion + ' (' + Math.round(dias(n)) + ' d)')).to.eql([]));",
            ]) for e in ("LEIDA", "DESCARTADA")],
        ]),
    ]
    return coleccion("TC-M08-G016 Contenido, filtros e historial de la bandeja (RF-105)",
                     "TC-M08-020, 021 y 022. Bandejas del Administrador y del Productor qa.m08. Corre en el sandbox.", items)


# ─────────────────────────────── G017 ───────────────────────────────
def g017():
    t = "TC-M08-023"
    consulta = lambda: (
        "SELECT n.id_notificacion, n.id_notificacion_canal AS canal, n.estado_envio::text AS estado_envio, n.estado, n.es_leido,"
        " n.fecha_envio, n.fecha_lectura, n.id_usuario, e.id_evento, e.tipo_evento, e.modulo, e.id_usuario AS usuario_evento"
        " FROM modulo1.notificaciones n JOIN modulo1.eventos e ON e.id_evento = n.id_evento"
        " WHERE n.id_evento = {{id_evento}} ORDER BY n.id_notificacion")
    items = [
        pre([L_ADMIN]),
        carpeta("1. TC-M08-023 Trazabilidad de una notificación hasta su evento, canal y estado", [
            lista(f"{t} - Administrador GET una alerta sin leer de su bandeja", "tok_admin", "?nivel=CRITICA&estado=NUEVA&tamano=1", [
                f"pm.test('{t} - hay una alerta sin leer', () => pm.expect(it.length).to.equal(1));",
                "pm.collectionVariables.set('id_n', String(it[0].id_notificacion)); pm.collectionVariables.set('id_evento', String(it[0].id_evento));"]),
            sql(f"{t} - SQL notificaciones del evento (antes)", consulta(), [
                "const mia = filas.filter(f => String(f.id_notificacion) === pm.collectionVariables.get('id_n'));",
                f"pm.test('{t} - la notificación apunta a su evento de origen, con usuario y módulo', () => {{ pm.expect(mia.length).to.equal(1); pm.expect(mia[0].id_evento).to.be.a('number'); pm.expect(mia[0].modulo).to.be.a('string').and.not.empty; pm.expect(mia[0].id_usuario).to.be.a('number'); }});",
                f"pm.test('{t} - cada envío por correo o push tiene su registro en la bandeja (canal 2) del mismo usuario', () => filas.filter(f => f.canal !== 2).forEach(f => pm.expect(filas.some(g => g.canal === 2 && g.id_usuario === f.id_usuario), 'notificación ' + f.id_notificacion).to.be.true));",
                f"pm.test('{t} - el estado de envío es en_cola, enviado o fallido', () => filas.forEach(f => pm.expect(f.estado_envio).to.be.oneOf(['en_cola', 'enviado', 'fallido'])));",
            ]),
            patch_n(f"{t} - Administrador marca la notificación como leída", "tok_admin", "/{{id_n}}/leida", [
                f"pm.test('{t} - marcada como leída (200)', () => pm.response.to.have.status(200));"]),
            sql(f"{t} - SQL la notificación después de leerla", consulta(), [
                "const mia = filas.find(f => String(f.id_notificacion) === pm.collectionVariables.get('id_n')) || {};",
                f"pm.test('{t} - queda LEIDA con su fecha de lectura', () => {{ pm.expect(mia.estado).to.equal('LEIDA'); pm.expect(mia.fecha_lectura).to.not.be.null; }});"]),
            sql(f"{t} - SQL evento de auditoría del cambio a leída (tipo 46)",
                "SELECT id_evento, tipo_evento, modulo, fecha_evento, detalle, hash_integridad FROM modulo1.eventos"
                " WHERE tipo_evento = 46 AND detalle->>'id_notificacion' = '{{id_n}}' ORDER BY id_evento DESC", [
                    f"pm.test('{t} - el cambio a leída deja su propio registro con fecha (evento 46)', () => {{ pm.expect(filas.length).to.be.at.least(1);"
                    " pm.expect(filas[0].detalle.accion).to.equal('LEIDA'); pm.expect(filas[0].fecha_evento).to.be.a('string'); });",
                    f"pm.test('{t} - el registro tiene hash de integridad', () => pm.expect(filas[0] && filas[0].hash_integridad).to.be.a('string'));"]),
        ]),
    ]
    return coleccion("TC-M08-G017 Trazabilidad de las notificaciones (RF-105)",
                     "TC-M08-023. Consultas de solo lectura dentro del run con la identidad del Administrador (dueño de las filas).", items)


if __name__ == "__main__":
    for nombre, fn in (("G013", g013), ("G014", g014), ("G015", g015), ("G016", g016), ("G017", g017)):
        destino = AQUI / f"TC-M08-{nombre}" / f"tc-m08-{nombre.lower()}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(fn(), ensure_ascii=False, indent=2), encoding="utf-8")
        print("Escrito", destino.relative_to(AQUI))
