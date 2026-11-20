# | Fecha      | Nombre           | Que se hizo                                                        |
# |------------|------------------|--------------------------------------------------------------------|
# | 2026-11-19 | Juan Manuel      | TC-M08-G013..G017 RF-105: colecciones con sandbox (bandeja v6)     |
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

N = "{{base_url}}/notificaciones"
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
        pre([L_ADMIN, L_PROD]),
        carpeta("1. TC-M08-013 Bandeja propia con contador de no leídas", [
            lista(f"{t13} - {rol} GET /notificaciones?pagina=1&tamano=50", tok, "?pagina=1&tamano=50", ORDEN + [
                f"pm.test('{t13} - {rol}: bandeja (200) en ≤ 2 s (RNF-03): ' + pm.response.responseTime + ' ms con ' + b.total + ' notificaciones', () => {{"
                " pm.response.to.have.status(200); pm.expect(pm.response.responseTime).to.be.at.most(2000); });",
                f"pm.test('{t13} - {rol}: trae total, no_leidas y los items', () => {{ pm.expect(b.total).to.be.a('number'); pm.expect(b.no_leidas).to.be.a('number').and.at.most(b.total); pm.expect(it.length).to.be.above(0); }});",
                f"pm.test('{t13} - {rol}: orden crítica > advertencia > informativa y de la más reciente a la más antigua', () => pm.expect(ordenada(it)).to.be.true);",
                f"if (b.total <= 500) console.warn('DATO: la bandeja del {rol} tiene ' + b.total + ' notificaciones; RNF-03 pide más de 500 (cuenta 182 del DBA).');",
            ]) for rol, tok in (("Productor", "tok_prod"), ("Administrador", "tok_admin"))
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
                " pm.expect(String(n.fecha_lectura)).to.equal(pm.collectionVariables.get('fecha_lectura')); }});"]),
            lista(f"{t15} - GET después de repetir", "tok_prod", "?tamano=1", [
                f"pm.test('{t15} - repetir no cambia no_leidas', () => pm.expect(b.no_leidas).to.equal(Number(pm.collectionVariables.get('no_leidas_0')) - 1));"]),
            patch_n(f"{t15} - PATCH /notificaciones/leidas", "tok_prod", "/leidas", [
                f"pm.test('{t15} - marcadas = las que quedaban sin leer', () => {{ pm.response.to.have.status(200); pm.expect(pm.response.json().marcadas).to.equal(Number(pm.collectionVariables.get('no_leidas_0')) - 1); }});"]),
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
                f"pm.test('{t17} - acción {n} rechazada (400 VAL_ENTRADA)', () => {{ pm.response.to.have.status(400); pm.expect(pm.response.json().error_code).to.equal('VAL_ENTRADA'); }});"],
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
            *[x for nivel in ("ADVERTENCIA", "INFORMATIVA") for x in (
                lista(f"{t17} - Administrador GET una {nivel} nueva", "tok_admin", f"?nivel={nivel}&estado=NUEVA&tamano=1", [
                    f"pm.test('{t17} - hay una {nivel} nueva que se puede descartar', () => {{ pm.expect(it.length).to.equal(1); pm.expect(it[0].puede_descartarse).to.be.true; }});",
                    f"pm.collectionVariables.set('id_{nivel.lower()}', String(it[0].id_notificacion));"]),
                patch_n(f"{t17} - Descartar la {nivel}", "tok_admin", f"/{{{{id_{nivel.lower()}}}}}/descartada", [
                    f"pm.test('{t17} - la {nivel} queda DESCARTADA (200)', () => {{ pm.response.to.have.status(200); pm.expect(pm.response.json().estado).to.equal('DESCARTADA'); }});"]),
                lista(f"{t17} - historial: la {nivel} descartada se sigue consultando", "tok_admin", f"?nivel={nivel}&estado=DESCARTADA&tamano=50", [
                    f"pm.test('{t17} - la {nivel} descartada sigue en el historial', () => pm.expect(it.map(n => String(n.id_notificacion))).to.include(pm.collectionVariables.get('id_{nivel.lower()}')));"]),
            )],
            lista(f"{t17} - panel principal sin las cerradas", "tok_admin", "?tamano=50&nivel=CRITICA", [
                f"pm.test('{t17} - la crítica atendida sale del panel principal', () => pm.expect(it.map(n => String(n.id_notificacion))).to.not.include(pm.collectionVariables.get('id_crit')));"]),
        ]),
    ]
    return coleccion("TC-M08-G014 Propiedad y ciclo de vida de las notificaciones (RF-105)",
                     "TC-M08-016 y 017. Críticas y advertencias de la bandeja del Administrador; todo se revierte con el sandbox.", items)


# ─────────────────────────────── G015 ───────────────────────────────
def g015():
    t18, t24 = "TC-M08-018", "TC-M08-024"
    items = [
        pre([L_ADMIN, L_PROD]),
        carpeta("1. TC-M08-018/019 Generar la alerta crítica (necesita el token del broker)", [
            req(f"{t18} - POST /iot/telemetria sin el token del broker", "POST", "{{base_url}}/iot/telemetria", token=None,
                body='{\n  "serial": "QA-M08-SENSOR-02",\n  "lecturas": []\n}', tests=[
                    f"pm.test('{t18} - la ingesta exige el token de servicio del broker (401/403): sin él no se puede generar la alerta', () => pm.expect(pm.response.code).to.be.oneOf([401, 403]));",
                    "console.warn('BLOQUEADO: TC-018, 019 y 024 necesitan el token del broker de TEST, push activado en el navegador, un buzón real y los logs del backend.');"]),
        ]),
        carpeta("2. TC-M08-024 Token de push inválido (preparación)", [
            req(f"{t24} - Productor registra un token de push inválido", "POST", "{{base_url}}/usuarios/me/fcm-token", token="tok_prod",
                body='{\n  "token": "token-invalido-qa"\n}', tests=[
                    "console.log(pm.response.text().slice(0, 400));",
                    f"pm.test('{t24} - el token se registra sin error para el usuario (200/201/204)', () => pm.expect(pm.response.code).to.be.oneOf([200, 201, 204]));"]),
        ]),
    ]
    return coleccion("TC-M08-G015 Canales, destinatarios y duplicados (RF-105)",
                     "TC-M08-018, 019 y 024. Bloqueados por el token del broker, push, correo y logs; solo la preparación posible. Sandbox.", items)


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
                    " pm.expect(filas[0].detalle.accion).to.equal('LEIDA'); pm.expect(filas[0].fecha_evento).to.be.a('string'); }});",
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
