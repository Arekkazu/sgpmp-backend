# | Fecha      | Nombre           | Que se hizo                                                        |
# |------------|------------------|--------------------------------------------------------------------|
# | 2026-11-19 | Juan Manuel      | TC-M08-G001..G005 RF-103: colecciones con sandbox (dashboard v6)   |
# | 2026-11-19 | Juan Manuel      | TC-M08-001 fuera del sandbox (el sandbox no admite peticiones en paralelo) |
"""Genera las colecciones Newman de RF-103 (dashboard por widgets, M08; grupos G001 a G005).

Uso (desde esta carpeta):  python construir_colecciones_rf103.py
Escribe TC-M08-Gnnn/tc-m08-gnnn.json. Se ejecutan desde Test_Modulo8 con:
    .\\correr_newman_m08.ps1 -Caso G001 -Rf RF-103

Todo corre en el sandbox transaccional del DBA (una transacción por corrida que el último paso revierte con
DELETE /test-control/runs/{run_id}). Sin `sandbox_secret` las peticiones se desvían a 127.0.0.1:9.

Ajustes frente a la ficha (lanzamiento v6/v7, rc.78/rc.79):
- Los datos de cada widget salen de GET /dashboard/widgets/{clave}?id_finca= (uno por petición). El
  GET /configuracion/personalizacion/dashboard/datos que nombra la ficha está deprecated; se consulta igual.
- Cuentas y datos del DBA (2026-11-19): finca 494 «Finca Reportes Integrados Qa», finca ajena 495, cuentas
  qa.m08.* (176 Productor, 177 Veterinario, 178 Contador, 179 Ingeniero). Las cuentas viejas de la ficha
  (m2m.nuevo, admin@pecuaria.co, gestor.granja.test) ya no entran en TEST.
- TC-011: el usuario con 2 fincas y el usuario sin finca se arman dentro del sandbox con
  PUT /usuarios/{id}/fincas sobre el Productor 176 (se revierte al final).
- TC-001 (carga en paralelo, ≤ 3 s) va FUERA del sandbox: solo login y lecturas. Dentro del sandbox toda la
  corrida es una sola transacción y las peticiones simultáneas responden 500 (verificado el 2026-11-19: fuera
  del sandbox los mismos widgets en paralelo responden 200). En G004/G005 los widgets se piden en serie.
- Lo que solo se ve en el navegador (refresco cada 30 s, modo offline, selector de finca) no está aquí.
"""
from __future__ import annotations

import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BASE_URL = "https://api.inmero.co/api-sgpmp-test"
ROLLBACK = "ROLLBACK - Revertir la transacción de la corrida"
W = "{{base_url}}/dashboard/widgets/"

PRE_COLECCION = [
    "// Sandbox transaccional de TEST (DBA): toda la corrida va en una transaccion que NUNCA se confirma y el",
    "// ultimo paso la revierte (DELETE /test-control/runs/{run_id}). El secreto no se guarda en este archivo.",
    "const secreto = pm.variables.get('sandbox_secret');",
    "if (pm.request.headers.has('X-Fuera-Sandbox')) {",
    "  pm.request.headers.remove('X-Fuera-Sandbox');  // TC-001: solo login y lecturas, fuera del sandbox",
    "} else if (!secreto) {",
    "  console.error('Falta sandbox_secret: peticion desviada, no se envia a TEST.');",
    "  pm.request.url.update('http://127.0.0.1:9/falta-sandbox_secret');",
    "} else {",
    "  if (!pm.collectionVariables.get('run_id')) { pm.collectionVariables.set('run_id', 'test-' + pm.variables.replaceIn('{{$guid}}')); }",
    "  pm.request.headers.upsert({ key: 'X-Test-Run-Id', value: pm.collectionVariables.get('run_id') });",
    "  pm.request.headers.upsert({ key: 'X-Sandbox-Secret', value: secreto });",
    "}",
    "pm.request.headers.upsert({ key: 'X-Zona-Horaria', value: 'America/Bogota' });",
    "// Si el login de ese rol fallo, la peticion no se envia (el fallo queda en el test del login).",
    "const auth = (pm.request.headers.get('Authorization') || '').match(/\\{\\{(tok_\\w+)\\}\\}/);",
    "if (auth && !pm.collectionVariables.get(auth[1])) { console.warn('Sin ' + auth[1] + ': se omite ' + pm.info.requestName); pm.execution.skipRequest(); }",
]

# Funciones JS que usan los scripts que piden varios widgets en paralelo (como el frontend, CA-8).
JS_COMUN = [
    "const H = (tok, fuera) => [{ key: 'Authorization', value: 'Bearer ' + pm.collectionVariables.get(tok) },",
    "  { key: 'X-Zona-Horaria', value: 'America/Bogota' }, { key: 'Content-Type', value: 'application/json' }].concat(fuera ? [] : [",
    "  { key: 'X-Test-Run-Id', value: pm.collectionVariables.get('run_id') || '' },",
    "  { key: 'X-Sandbox-Secret', value: pm.variables.get('sandbox_secret') || '' }]);",
    "const pedir = (metodo, ruta, tok, fuera) => new Promise(ok => pm.sendRequest({ url: pm.variables.replaceIn('{{base_url}}') + ruta,",
    "  method: metodo, header: H(tok, fuera) }, (e, r) => ok({ e, r, json: (() => { try { return r.json(); } catch (x) { return null; } })() })));",
    "const cat = JSON.parse(pm.collectionVariables.get('catalogo') || '{}');",
    "// En serie dentro del sandbox (una sola transaccion por corrida no admite peticiones simultaneas).",
    "const enSerie = (claves, f) => claves.reduce((p, k) => p.then(acc => f(k).then(x => acc.concat([x]))), Promise.resolve([]));",
]

ESTADOS_RF60 = ["ACTIVO", "BUFFER_ACTIVO", "SIN_SEÑAL", "INACTIVO", "EN_MANTENIMIENTO"]
WIDGETS_CONTADOR = ["periodos_abiertos", "reconocimientos_pendientes", "integraciones_fallidas", "precios_por_vencer"]
WIDGETS_PRODUCTOR = ["semaforo_areas", "inventario_especies", "ultimos_eventos", "conversion_alimenticia",
                     "temp_galpon", "hum_galpon"]
WIDGETS_VETERINARIO = ["riesgo_sanitario_alto", "distribucion_riesgo", "retroalimentacion_pendiente", "alertas_sanitarias"]
WIDGETS_TECNICOS_IOT = ["estado_iot", "cal_sensores", "cfg_pendiente", "dispositivos_sin_senal"]


# ─────────────────────────────── helpers ───────────────────────────────
def req(nombre, metodo, url, *, token="tok_admin", body=None, tests=None, pre=None, descripcion=None, fuera=False):
    headers = [{"key": "X-Fuera-Sandbox", "value": "1"}] if fuera else []
    if token:
        headers.append({"key": "Authorization", "value": "Bearer {{" + token + "}}"})
    item = {"name": nombre, "event": [], "request": {"method": metodo, "header": headers, "url": url}}
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


def login(tok, var_correo, var_contrasena, rol, var_id, *, tc="PRE", pre=None, extra=None, fuera=False):
    return req(
        f"{tc} - Login {rol}" + (" (fuera del sandbox)" if fuera else ""), "POST", "{{base_url}}/sesiones/", token=None,
        pre=pre, fuera=fuera,
        body="{\n  \"correo_electronico\": \"{{" + var_correo + "}}\",\n  \"contrasena\": \"{{" + var_contrasena + "}}\"\n}",
        tests=[
            f"pm.test('{tc} - Login {rol} (200)', () => pm.response.to.have.status(200));",
            f"pm.collectionVariables.set('{tok}', '');",
            f"if (pm.response.code === 200) {{ const t = pm.response.json().token; pm.collectionVariables.set('{tok}', t);"
            f" pm.collectionVariables.set('{var_id}', JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).sub); }}",
        ] + (extra or []),
    )


L_ADMIN = ("tok_admin", "correo_admin", "contrasena_admin", "Administrador", "id_admin")
L_PROD = ("tok_prod", "correo_productor", "contrasena_productor", "Productor", "id_productor")
L_VET = ("tok_vet", "correo_veterinario", "contrasena_veterinario", "Veterinario", "id_veterinario")
L_CONT = ("tok_cont", "correo_contador", "contrasena_contador", "Contador", "id_contador")
L_ING = ("tok_ing", "correo_ingeniero", "contrasena_ingeniero", "Ingeniero de Campo", "id_ingeniero")
L_GESTOR = ("tok_gestor", "correo_gestor", "contrasena_gestor", "Gestor de Granja", "id_gestor")


def catalogo_admin():
    """Catálogo completo (id → clave) leído como Administrador, para traducir los ids del layout."""
    return req("PRE - Catálogo de widgets (Administrador)", "GET", "{{base_url}}/configuracion/personalizacion/dashboard/widgets",
               token="tok_admin", tests=[
                   "pm.test('PRE - catálogo de widgets (200)', () => pm.response.to.have.status(200));",
                   "const m = {}; (pm.response.json() || []).forEach(w => m[w.id_widget] = w.clave);",
                   "pm.collectionVariables.set('catalogo', JSON.stringify(m));",
                   "console.log('Catálogo: ' + JSON.stringify(m));",
               ])


def precondiciones(logins):
    return carpeta("0. Precondiciones (logins dentro del sandbox)", [login(*l) for l in logins] + [catalogo_admin()])


def rollback():
    return carpeta("9. Rollback del sandbox (la BD queda como estaba)", [
        req(ROLLBACK, "DELETE", "{{base_url}}/test-control/runs/{{run_id}}", token=None, tests=[
            "pm.test('ROLLBACK - sandbox revertido (200)', () => pm.response.to.have.status(200));",
            "pm.collectionVariables.unset('run_id');",
        ]),
    ])


def widget(tc, clave, tok, tests, *, finca="{{id_finca}}", guardar=None, rol=""):
    """GET de un widget con sus verificaciones; guarda la respuesta en `guardar` si se pide."""
    t = [f"const d = pm.response.json() || {{}}; const datos = d.datos || {{}};"]
    if guardar:
        t.append(f"pm.collectionVariables.set('{guardar}', JSON.stringify(d));")
    t.append("console.log(JSON.stringify(d).slice(0, 1500));")
    q = f"?id_finca={finca}" if finca else ""
    return req(f"{tc} - {rol} widget {clave}", "GET", W + clave + q, token=tok, tests=t + tests)


def ok_widget(tc, clave):
    return [f"pm.test('{tc} - {clave} responde 200 con estado OK o SIN_DATOS (no ERROR)', () => {{"
            f" pm.response.to.have.status(200); pm.expect(d.estado).to.be.oneOf(['OK', 'SIN_DATOS']); }});",
            f"pm.test('{tc} - {clave} trae la hora de su última actualización', () => pm.expect(Date.parse(d.actualizado_en)).to.be.a('number').and.not.NaN);"]


def layout(tc, tok, var, rol, fuera=False):
    return req(f"{tc} - {rol} GET layout del dashboard", "GET", "{{base_url}}/configuracion/personalizacion/dashboard",
               token=tok, fuera=fuera, tests=[
                   f"pm.test('{tc} - layout del {rol} (200)', () => pm.response.to.have.status(200));",
                   f"pm.collectionVariables.set('{var}', pm.response.text());",
                   "console.log(pm.response.text().slice(0, 1500));",
               ])


# Cuerpo del PATCH armado desde el layout guardado; `cambio` es JS que modifica `cfg` (y puede tocar `frecuencia`).
def pre_patch(var_layout, cambio):
    return [
        f"const lay = JSON.parse(pm.collectionVariables.get('{var_layout}') || '{{}}');",
        "const cat = JSON.parse(pm.collectionVariables.get('catalogo') || '{}');",
        "let cfg = (lay.grid || []).map(g => ({ id_widget: g.id_widget, posicion_fila: g.posicion_fila, posicion_columna: g.posicion_columna,",
        "  span_columnas: g.span_columnas, visible: g.visible, orden: g.orden, parametros: g.parametros || {} }));",
        "let frecuencia;",
    ] + cambio + [
        "const cuerpo = { layout_config: cfg, active_widget: cfg.map(c => cat[c.id_widget]).filter(Boolean), version_perfil: lay.version_perfil };",
        "if (frecuencia !== undefined) cuerpo.frecuencia_actualizacion = frecuencia;",
        "pm.collectionVariables.set('patch_body', JSON.stringify(cuerpo));",
    ]


def patch(nombre, tok, var_layout, cambio, tests):
    return req(nombre, "PATCH", "{{base_url}}/configuracion/personalizacion/dashboard", token=tok, body="{{patch_body}}",
               pre=pre_patch(var_layout, cambio), tests=["console.log(pm.response.text().slice(0, 800));"] + tests)


def coleccion(nombre, descripcion, items, finca="494"):
    var = {"base_url": BASE_URL, "id_finca": finca, "id_finca_ajena": "495", "run_id": "", "catalogo": "", "patch_body": "",
           "tok_admin": "", "tok_prod": "", "tok_prod_real": "", "tok_admin_real": "", "tok_vet": "", "tok_cont": "", "tok_ing": "", "tok_gestor": ""}
    return {"info": {"name": nombre, "description": descripcion,
                     "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
            "event": [{"listen": "prerequest", "script": {"type": "text/javascript", "exec": PRE_COLECCION}}],
            "variable": [{"key": k, "value": v} for k, v in var.items()],
            "item": items + [rollback()]}


# ─────────────────────────────── G001 ───────────────────────────────
def carga_por_rol(tc, l, rol):
    """Login, contexto, layout, catálogo y todos los widgets del layout en paralelo; cronómetro desde el login."""
    tok = l[0] + "_real"
    l = (tok,) + tuple(l[1:])
    return [
        login(*l, tc=tc, fuera=True, pre=["pm.collectionVariables.set('t0', String(Date.now()));"]),
        req(f"{tc} - {rol} GET contexto de la interfaz", "GET", "{{base_url}}/configuracion/interfaz/contexto", token=tok, fuera=True, tests=[
            f"pm.test('{tc} - contexto del {rol} (200)', () => pm.response.to.have.status(200));",
            "const c = pm.response.json() || {};",
            f"pm.test('{tc} - el contexto trae el saludo (nombre) y la finca activa', () => {{ pm.expect(c.nombre_completo).to.be.a('string').and.not.empty;"
            " pm.expect(c.id_finca).to.be.a('number'); pm.expect(c.finca_activa).to.be.a('string').and.not.empty; });",
            f"pm.collectionVariables.set('finca_{tok}', String(c.id_finca));",
            "console.log('Contexto: ' + c.nombre_completo + ' / ' + c.nombre_rol + ' / finca ' + c.id_finca + ' ' + c.finca_activa);",
        ]),
        layout(tc, tok, f"layout_{tok}", rol, fuera=True),
        req(f"{tc} - {rol} GET catálogo de widgets del rol y carga de todos los widgets del layout (en paralelo)", "GET",
            "{{base_url}}/configuracion/personalizacion/dashboard/widgets", token=tok, fuera=True, tests=JS_COMUN + [
                f"pm.test('{tc} - catálogo del {rol} (200)', () => pm.response.to.have.status(200));",
                f"const lay = JSON.parse(pm.collectionVariables.get('layout_{tok}') || '{{}}');",
                f"const finca = pm.collectionVariables.get('finca_{tok}');",
                "// Traduccion id -> clave con el catalogo del propio rol (esta respuesta); un id que no esta en el",
                "// catalogo (widget retirado en v6, ej. prod_aves en un layout personalizado) no se dibuja.",
                "const delRol = {}; (pm.response.json() || []).forEach(w => delRol[w.id_widget] = w.clave);",
                "const claves = (lay.grid || []).map(g => delRol[g.id_widget]).filter(Boolean);",
                f"pm.test('{tc} - el layout del {rol} tiene widgets', () => pm.expect(claves.length).to.be.above(0));",
                f"Promise.all(claves.map(k => pedir('GET', '/dashboard/widgets/' + k + '?id_finca=' + finca, '{tok}', true))).then(rs => {{",
                "  const ms = Date.now() - Number(pm.collectionVariables.get('t0'));",
                "  rs.forEach((x, i) => console.log(claves[i] + ' -> ' + (x.r && x.r.code) + ' ' + (x.json && x.json.estado) + ' ' + (x.r && x.r.responseTime) + ' ms'));",
                f"  pm.test('{tc} - los ' + claves.length + ' widgets del {rol} responden 200', () => rs.forEach((x, i) => pm.expect(x.r && x.r.code, claves[i]).to.equal(200)));",
                f"  pm.test('{tc} - ningún widget del {rol} queda en ERROR', () => rs.forEach((x, i) => pm.expect(x.json && x.json.estado, claves[i]).to.be.oneOf(['OK', 'SIN_DATOS'])));",
                f"  pm.test('{tc} - {rol}: carga completa (login + contexto + layout + widgets) en ≤ 3 s (CA-1): ' + ms + ' ms', () => pm.expect(ms).to.be.at.most(3000));",
                "});",
            ]),
        req(f"{tc} - {rol} GET dashboard/datos (endpoint de la ficha, deprecated desde v6)", "GET",
            "{{base_url}}/configuracion/personalizacion/dashboard/datos", token=tok, fuera=True, tests=[
                f"pm.test('{tc} - dashboard/datos del {rol} (200)', () => pm.response.to.have.status(200));",
                "console.log(pm.response.text().slice(0, 1200));",
            ]),
    ]


def g001():
    t2 = "TC-M08-002"
    t7 = "TC-M08-007"
    cat_rol = lambda tok, rol: req(f"{t2} - {rol} GET catálogo de widgets del rol", "GET",
                                   "{{base_url}}/configuracion/personalizacion/dashboard/widgets", token=tok, tests=[
        f"pm.test('{t2} - catálogo del {rol} (200)', () => pm.response.to.have.status(200));",
        f"pm.collectionVariables.set('lista_{tok}', JSON.stringify((pm.response.json() || []).map(w => w.clave)));",
        "console.log(JSON.stringify((pm.response.json() || []).map(w => w.clave)));",
    ])
    comparar = [
        "const L = t => JSON.parse(pm.collectionVariables.get('lista_' + t) || '[]');",
        "const p = L('tok_prod'), v = L('tok_vet'), c = L('tok_cont'), i = L('tok_ing');",
        "const firma = x => x.slice().sort().join(',');",
        f"pm.test('{t2} - las 4 listas (Productor, Veterinario, Contador, Ingeniero) son distintas', () => pm.expect(new Set([p, v, c, i].map(firma)).size).to.equal(4));",
        f"pm.test('{t2} - el Productor no ve los widgets del Contador (CA-4)', () => pm.expect(p.filter(k => {json.dumps(WIDGETS_CONTADOR)}.includes(k))).to.eql([]));",
        f"pm.test('{t2} - el Contador no ve los widgets del Productor (CA-4)', () => pm.expect(c.filter(k => {json.dumps(WIDGETS_PRODUCTOR)}.includes(k))).to.eql([]));",
        f"pm.test('{t2} - el Productor no ve los widgets del Veterinario', () => pm.expect(p.filter(k => {json.dumps(WIDGETS_VETERINARIO)}.includes(k))).to.eql([]));",
        f"pm.test('{t2} - el Productor no ve widgets técnicos de IoT (RF-103, nota de separación de responsabilidades)', () => pm.expect(p.filter(k => {json.dumps(WIDGETS_TECNICOS_IOT)}.includes(k))).to.eql([]));",
    ]
    items = [
        # TC-001 va antes de cualquier login dentro del sandbox: un login de afuera del mismo usuario espera el bloqueo
        # de la sesión abierta en la transacción del run (se vio el 2026-11-19: 5 min 27 s).
        carpeta("1. TC-M08-001 Carga del dashboard después de iniciar sesión (fuera del sandbox, solo lecturas)",
                carga_por_rol("TC-M08-001", L_PROD, "Productor") + carga_por_rol("TC-M08-001", L_ADMIN, "Administrador")),
        carpeta("0. Precondiciones (logins dentro del sandbox)", [login(*L_ADMIN), catalogo_admin()]),
        carpeta("2. TC-M08-002 El dashboard se adapta al rol", [
            login(*L_PROD, tc=t2), login(*L_VET, tc=t2), login(*L_CONT, tc=t2), login(*L_ING, tc=t2),
            cat_rol("tok_prod", "Productor"), cat_rol("tok_vet", "Veterinario"), cat_rol("tok_cont", "Contador"),
            req(f"{t2} - Ingeniero GET catálogo de widgets del rol y comparación de las 4 listas", "GET",
                "{{base_url}}/configuracion/personalizacion/dashboard/widgets", token="tok_ing", tests=[
                    f"pm.test('{t2} - catálogo del Ingeniero (200)', () => pm.response.to.have.status(200));",
                    "pm.collectionVariables.set('lista_tok_ing', JSON.stringify((pm.response.json() || []).map(w => w.clave)));",
                    "console.log(JSON.stringify((pm.response.json() || []).map(w => w.clave)));",
                ] + comparar),
            layout(t2, "tok_prod", "layout_antes", "Productor"),
            patch(f"{t2} - Productor PATCH con un widget del Contador (periodos_abiertos, id 25)", "tok_prod", "layout_antes",
                  ["cfg[0].id_widget = 25; cfg[0].parametros = {};"], [
                      f"pm.test('{t2} - widget no permitido rechazado (403 WIDGET_NO_AUTORIZADO)', () => {{ pm.response.to.have.status(403);"
                      " pm.expect(pm.response.json().error_code).to.equal('WIDGET_NO_AUTORIZADO'); });"]),
            req(f"{t2} - Productor GET layout después del rechazo", "GET", "{{base_url}}/configuracion/personalizacion/dashboard",
                token="tok_prod", tests=[
                    f"pm.test('{t2} - layout después del rechazo (200)', () => pm.response.to.have.status(200));",
                    "const antes = (JSON.parse(pm.collectionVariables.get('layout_antes')).grid || []).map(g => g.id_widget);",
                    f"pm.test('{t2} - el layout no cambió', () => pm.expect(pm.response.json().grid.map(g => g.id_widget)).to.eql(antes));",
                ]),
            patch(f"{t2} - Productor PATCH con el widget técnico de IoT de la ficha (estado_iot, id 6)", "tok_prod", "layout_antes",
                  ["cfg[0].id_widget = 6; cfg[0].parametros = {};"], [
                      f"pm.test('{t2} - widget técnico de IoT rechazado al Productor (403 WIDGET_NO_AUTORIZADO)', () => pm.response.to.have.status(403));"]),
        ]),
        carpeta("3. TC-M08-007 Control de acceso al dashboard", [
            *[req(f"{t7} - sin token {n}", "GET", u, token=None, tests=[
                f"pm.test('{t7} - sin token {n} responde 401', () => pm.response.to.have.status(401));",
                f"pm.test('{t7} - sin token {n}: no devuelve widgets ni datos', () => {{ const b = pm.response.json() || {{}}; pm.expect(b).to.not.have.any.keys('grid', 'datos'); }});"])
              for n, u in [("GET dashboard", "{{base_url}}/configuracion/personalizacion/dashboard"),
                           ("GET dashboard/datos", "{{base_url}}/configuracion/personalizacion/dashboard/datos"),
                           ("GET widget semaforo_areas", W + "semaforo_areas?id_finca={{id_finca}}")]],
            *[req(f"{t7} - token alterado {n}", "GET", u, token="tok_alterado",
                  pre=["const t = pm.collectionVariables.get('tok_prod') || 'x.y.z';",
                       "pm.collectionVariables.set('tok_alterado', t.slice(0, -4) + (t.slice(-4) === 'AAAA' ? 'BBBB' : 'AAAA'));"],
                  tests=[f"pm.test('{t7} - token alterado {n} responde 401', () => pm.response.to.have.status(401));"])
              for n, u in [("GET dashboard", "{{base_url}}/configuracion/personalizacion/dashboard"),
                           ("GET dashboard/datos", "{{base_url}}/configuracion/personalizacion/dashboard/datos")]],
            login(*L_GESTOR, tc=t7),
            *[req(f"{t7} - Gestor de Granja {n}", "GET", u, token="tok_gestor", tests=[
                f"pm.test('{t7} - Gestor de Granja {n} responde 403', () => pm.response.to.have.status(403));",
                f"pm.test('{t7} - Gestor de Granja {n}: no devuelve widgets ni datos', () => pm.expect(pm.response.json() || {{}}).to.not.have.any.keys('grid', 'datos'));"])
              for n, u in [("GET dashboard", "{{base_url}}/configuracion/personalizacion/dashboard"),
                           ("GET dashboard/datos", "{{base_url}}/configuracion/personalizacion/dashboard/datos"),
                           ("GET widget semaforo_areas", W + "semaforo_areas?id_finca={{id_finca}}")]],
        ]),
    ]
    return coleccion("TC-M08-G001 Carga del dashboard por rol y control de acceso (RF-103)",
                     "TC-M08-001, 002 y 007. Finca 494 y cuentas qa.m08.* del DBA. Corre en el sandbox.", items)


# ─────────────────────────────── G002 ───────────────────────────────
def g002():
    t3, t4 = "TC-M08-003", "TC-M08-004"
    items = [
        precondiciones([L_ADMIN, L_PROD, L_VET, L_CONT, L_ING]),
        carpeta("1. TC-M08-003 Dashboard del Productor y del Veterinario según el RF", [
            req(f"{t3} - Productor GET activos biológicos de la finca (módulo de origen M02)", "GET",
                "{{base_url}}/activos-biologicos?id_finca={{id_finca}}&registros_por_pagina=100", token="tok_prod", tests=[
                    f"pm.test('{t3} - listado de activos de la finca (200)', () => pm.response.to.have.status(200));",
                    "const r = (pm.response.json() || {}).registros || []; const n = {};",
                    "r.forEach(a => { n[a.nombre_estado] = (n[a.nombre_estado] || 0) + 1; });",
                    "pm.collectionVariables.set('activos_m02', JSON.stringify(n)); console.log('M02 por estado: ' + JSON.stringify(n));",
                ]),
            widget(t3, "inventario_especies", "tok_prod", ok_widget(t3, "inventario_especies") + [
                "const n = JSON.parse(pm.collectionVariables.get('activos_m02') || '{}');",
                "const s = (datos.especies || []).reduce((a, e) => ({ ACTIVO: a.ACTIVO + e.activos, EN_TRATAMIENTO: a.EN_TRATAMIENTO + e.en_tratamiento, BAJA: a.BAJA + e.bajas }), { ACTIVO: 0, EN_TRATAMIENTO: 0, BAJA: 0 });",
                f"pm.test('{t3} - activos por estado coinciden con Activos biológicos (ACTIVO, EN_TRATAMIENTO, BAJA)', () => pm.expect(s).to.eql({{ ACTIVO: n.ACTIVO || 0, EN_TRATAMIENTO: n.EN_TRATAMIENTO || 0, BAJA: n.BAJA || 0 }}));",
            ], rol="Productor"),
            widget(t3, "semaforo_areas", "tok_prod", ok_widget(t3, "semaforo_areas") + [
                f"pm.test('{t3} - semáforo por infraestructura con VERDE/AMARILLO/ROJO (o SIN_DATOS)', () => {{ pm.expect(datos.areas).to.be.an('array').that.is.not.empty;"
                " datos.areas.forEach(a => pm.expect(a.estado).to.be.oneOf(['VERDE', 'AMARILLO', 'ROJO', 'SIN_DATOS'])); });"], rol="Productor"),
            widget(t3, "temp_galpon", "tok_prod", ok_widget(t3, "temp_galpon") + [
                f"pm.test('{t3} - temperatura por infraestructura (área y unidad en cada lectura)', () => (datos.lecturas || []).forEach(l => {{ pm.expect(l.area).to.be.a('string'); pm.expect(l.variable).to.match(/temperatura/i); }}));"], rol="Productor"),
            widget(t3, "hum_galpon", "tok_prod", ok_widget(t3, "hum_galpon") + [
                f"pm.test('{t3} - humedad por infraestructura: presente (si no hay sensores de humedad, SIN_DATOS con mensaje)', () => {{ if (d.estado === 'SIN_DATOS') pm.expect(d.mensaje).to.be.a('string').and.not.empty;"
                " else (datos.lecturas || []).forEach(l => pm.expect(l.variable).to.match(/humedad/i)); });"], rol="Productor"),
            widget(t3, "valor_inventario", "tok_cont", [
                f"pm.test('{t3} - valor del inventario leído como Contador, misma finca (200)', () => pm.response.to.have.status(200));"],
                guardar="valor_cont", rol="Contador (referencia M06)"),
            widget(t3, "valor_inventario", "tok_prod", ok_widget(t3, "valor_inventario") + [
                "const ref = JSON.parse(pm.collectionVariables.get('valor_cont') || '{}').datos || {};",
                f"pm.test('{t3} - valor total del inventario en COP', () => pm.expect(datos.moneda).to.equal('COP'));",
                f"pm.test('{t3} - el valor del Productor coincide con M06 (Contador ve ' + ref.valor_total + ' COP en ' + ref.activos + ' activos)', () => {{"
                " pm.expect(datos.valor_total).to.equal(ref.valor_total); pm.expect(datos.activos).to.equal(ref.activos); });"], rol="Productor"),
            widget(t3, "ultimos_eventos", "tok_prod", ok_widget(t3, "ultimos_eventos") + [
                f"pm.test('{t3} - últimos 5 eventos biológicos con fecha y tipo, del más reciente al más viejo', () => {{ const it = datos.items || [];"
                " pm.expect(it.length).to.be.within(1, 5); it.forEach(e => { pm.expect(Date.parse(e.fecha)).to.not.be.NaN; pm.expect(e.tipo).to.be.a('string'); });"
                " for (let k = 1; k < it.length; k++) pm.expect(Date.parse(it[k - 1].fecha)).to.be.at.least(Date.parse(it[k].fecha)); });"], rol="Productor"),
            widget(t3, "conversion_alimenticia", "tok_prod", ok_widget(t3, "conversion_alimenticia") + [
                f"pm.test('{t3} - conversión alimenticia del último período: presente (sin cálculo en la finca → SIN_DATOS con mensaje)', () => {{"
                " if (d.estado === 'SIN_DATOS') pm.expect(d.mensaje).to.be.a('string').and.not.empty; else (datos.especies || []).forEach(e => pm.expect(e.valor).to.not.be.null); });",
                "if (d.estado === 'SIN_DATOS') console.warn('DATO: la finca no tiene resultado_ica calculado; el valor no se pudo comparar con M05.');"], rol="Productor"),
            widget(t3, "riesgo_sanitario_alto", "tok_vet", ok_widget(t3, "riesgo_sanitario_alto") + [
                f"pm.test('{t3} - activos con riesgo ALTO de las últimas 24 h (lista; cada uno con patología y fecha de ≤ 24 h)', () => {{"
                " pm.expect(datos.items).to.be.an('array'); datos.items.forEach(a => pm.expect(Date.now() - Date.parse(a.fecha_inferencia)).to.be.at.most(24 * 3600e3)); });",
                "if (!(datos.items || []).length) console.warn('DATO: no hay inferencias de riesgo alto en las últimas 24 h (las de la finca 494 son del 15-11).');"], rol="Veterinario"),
            widget(t3, "distribucion_riesgo", "tok_vet", ok_widget(t3, "distribucion_riesgo") + [
                f"pm.test('{t3} - distribución de probabilidades por especie (normal, moderado, alto)', () => (datos.especies || []).forEach(e => ['normal', 'moderado', 'alto'].forEach(k => pm.expect(e[k]).to.be.a('number'))));"], rol="Veterinario"),
            widget(t3, "retroalimentacion_pendiente", "tok_vet", ok_widget(t3, "retroalimentacion_pendiente") + [
                f"pm.test('{t3} - pendientes de retroalimentación con antigüedad > 48 h', () => {{ pm.expect(datos.items).to.be.an('array').that.is.not.empty;"
                " datos.items.forEach(a => pm.expect(Date.now() - Date.parse(a.fecha_inferencia)).to.be.above(48 * 3600e3)); });"], rol="Veterinario"),
            widget(t3, "alertas_sanitarias", "tok_vet", ok_widget(t3, "alertas_sanitarias") + [
                f"pm.test('{t3} - alertas de patología activas por tipo (lista de tipos)', () => pm.expect(datos.tipos).to.be.an('array'));",
                "if (!(datos.tipos || []).length) console.warn('Sin alertas de patología de Telemetría (M04 no escribe alertas_patologicas: fuera de alcance según el lanzamiento v6/v7).');"], rol="Veterinario"),
            widget(t3, "riesgo_sanitario_alto", "tok_prod", [
                f"pm.test('{t3} - el Productor no puede leer un widget del Veterinario (403 WIDGET_NO_AUTORIZADO)', () => {{ pm.response.to.have.status(403);"
                " pm.expect(pm.response.json().error_code).to.equal('WIDGET_NO_AUTORIZADO'); });"], rol="Productor"),
        ]),
        carpeta("2. TC-M08-004 Dashboard del Contador y del Ingeniero de Campo según el RF", [
            widget(t4, "periodos_abiertos", "tok_cont", ok_widget(t4, "periodos_abiertos") + [
                f"pm.test('{t4} - períodos abiertos con fecha de cierre esperada (incluye el 636 de noviembre)', () => {{ const it = datos.items || [];"
                " pm.expect(it.map(p => p.id_periodo_contable)).to.include(636); it.forEach(p => { pm.expect(p.estado).to.be.oneOf(['ABIERTO', 'EN_CIERRE']); pm.expect(p.fecha_fin).to.be.a('string'); }); });"], rol="Contador"),
            widget(t4, "reconocimientos_pendientes", "tok_cont", ok_widget(t4, "reconocimientos_pendientes") + [
                f"pm.test('{t4} - activos pendientes de reconocimiento inicial de la finca', () => {{ pm.expect(datos.items).to.be.an('array').that.is.not.empty;"
                " datos.items.forEach(a => pm.expect(a.finca).to.equal('Finca Reportes Integrados Qa')); });"], rol="Contador"),
            widget(t4, "integraciones_fallidas", "tok_cont", ok_widget(t4, "integraciones_fallidas") + [
                f"pm.test('{t4} - exportaciones contables pendientes o fallidas (ninguna SUCCESS)', () => (datos.items || []).forEach(s => pm.expect(s.estado).to.not.equal('SUCCESS')));"], rol="Contador"),
            widget(t4, "precios_por_vencer", "tok_cont", ok_widget(t4, "precios_por_vencer") + [
                f"pm.test('{t4} - precios que vencen en los próximos 15 días', () => (datos.items || []).forEach(p => pm.expect(p.dias_restantes).to.be.within(0, 15)));"], rol="Contador"),
            widget(t4, "valor_inventario", "tok_cont", ok_widget(t4, "valor_inventario") + [
                f"pm.test('{t4} - valor del inventario por método (VALOR_RAZONABLE + COSTO = total)', () => {{ pm.expect(datos.vista).to.equal('POR_METODO');"
                " pm.expect(datos.valor_razonable + datos.valor_costo).to.be.closeTo(datos.valor_total, 0.01); });"], rol="Contador"),
            widget(t4, "semaforo_areas", "tok_cont", [
                f"pm.test('{t4} - el Contador no puede leer un widget del Productor (403)', () => pm.response.to.have.status(403));"], rol="Contador"),
            req(f"{t4} - Ingeniero GET dispositivos IoT de la finca (módulo de origen)", "GET",
                "{{base_url}}/configuracion/dispositivos-iot?id_finca={{id_finca}}", token="tok_ing", tests=[
                    f"pm.test('{t4} - dispositivos de la finca (200)', () => pm.response.to.have.status(200));",
                    "pm.collectionVariables.set('disp_m03', JSON.stringify(((pm.response.json() || {}).items || []).map(x => x.id_dispositivo_iot).sort()));",
                ]),
            widget(t4, "estado_iot", "tok_ing", ok_widget(t4, "estado_iot") + [
                f"pm.test('{t4} - estados exactos de RF-60, sin estados inventados (SIN_HEARTBEAT)', () => (datos.items || []).forEach(x => pm.expect(x.estado).to.be.oneOf({json.dumps(ESTADOS_RF60, ensure_ascii=False)})));",
                f"pm.test('{t4} - cada dispositivo de la finca aparece con su estado', () => pm.expect((datos.items || []).map(x => x.id_dispositivo_iot).sort()).to.eql(JSON.parse(pm.collectionVariables.get('disp_m03'))));",
                "console.log('Conteo por estado: ' + JSON.stringify(datos.conteo));"], rol="Ingeniero"),
            widget(t4, "dispositivos_sin_senal", "tok_ing", ok_widget(t4, "dispositivos_sin_senal") + [
                f"pm.test('{t4} - dispositivos sin señal con su última comunicación', () => (datos.items || []).forEach(x => {{ pm.expect(x.estado).to.be.oneOf(['SIN_SEÑAL', 'INACTIVO']); pm.expect(x).to.have.property('fecha_ultimo_contacto'); }}));"], rol="Ingeniero"),
            widget(t4, "lecturas_area", "tok_ing", ok_widget(t4, "lecturas_area") + [
                f"pm.test('{t4} - lecturas por sensor (sensor, variable y unidad)', () => {{ pm.expect(datos.lecturas).to.be.an('array').that.is.not.empty;"
                " datos.lecturas.forEach(l => { pm.expect(l.id_sensor).to.be.a('number'); pm.expect(l.variable).to.be.a('string'); }); });"], rol="Ingeniero"),
        ]),
    ]
    return coleccion("TC-M08-G002 Contenido del dashboard por rol frente al RF (RF-103)",
                     "TC-M08-003 y 004. Cada indicador contra su módulo de origen, finca 494. Corre en el sandbox.", items)


# ─────────────────────────────── G003 ───────────────────────────────
def g003():
    t5, t6, t11 = "TC-M08-005", "TC-M08-006", "TC-M08-011"
    alertas = lambda area, nombre: req(f"{t5} - Productor GET /iot/alertas activas del área {area} ({nombre})", "GET",
                                       "{{base_url}}/iot/alertas?id_infraestructura=" + str(area) + "&estado_alerta=ACTIVA&por_pagina=50",
                                       token="tok_prod", tests=[
        f"pm.test('{t5} - alertas activas del área {area} (200)', () => pm.response.to.have.status(200));",
        "const it = ((pm.response.json() || {}).items || []).filter(a => a.tipo_alerta !== 'TECNICA');",
        f"pm.collectionVariables.set('alertas_{area}', JSON.stringify(it.map(a => a.severidad)));",
        "console.log(JSON.stringify(it.map(a => [a.id_alerta, a.tipo_alerta, a.severidad])));",
    ])
    estado = lambda area: f"(datos.areas || []).find(a => a.id_infraestructura === {area}) || {{}}"
    items = [
        precondiciones([L_ADMIN, L_PROD, L_ING]),
        carpeta("1. TC-M08-005 Semáforo de alertas por infraestructura", [
            alertas(1468, "con alerta crítica"), alertas(1494, "solo moderadas"), alertas(1495, "sin alertas"),
            req(f"{t5} - Ingeniero GET estado de los dispositivos (para el área sin alertas)", "GET", W + "estado_iot?id_finca={{id_finca}}",
                token="tok_ing", tests=[
                    f"pm.test('{t5} - estado de dispositivos (200)', () => pm.response.to.have.status(200));",
                    "const it = ((pm.response.json() || {}).datos || {}).items || [];",
                    "pm.collectionVariables.set('disp_1495', JSON.stringify(it.filter(x => x.area === 'Corral Sin Alertas Qa').map(x => x.estado)));",
                    "console.log('Dispositivos del área 1495: ' + pm.collectionVariables.get('disp_1495'));",
                ]),
            widget(t5, "semaforo_areas", "tok_prod", ok_widget(t5, "semaforo_areas") + [
                "const sev = a => JSON.parse(pm.collectionVariables.get('alertas_' + a) || '[]');",
                f"const a1 = {estado(1468)}, a2 = {estado(1494)}, a3 = {estado(1495)};",
                "console.log(JSON.stringify([a1, a2, a3]));",
                f"pm.test('{t5} - área 1468 con alerta CRÍTICA activa → ROJO', () => {{ pm.expect(sev(1468)).to.include('CRITICO'); pm.expect(a1.estado).to.equal('ROJO'); }});",
                f"pm.test('{t5} - área 1494 solo con alertas moderadas → AMARILLO', () => {{ pm.expect(sev(1494)).to.not.include('CRITICO'); pm.expect(sev(1494).length).to.be.above(0); pm.expect(a2.estado).to.equal('AMARILLO'); }});",
                f"pm.test('{t5} - los conteos del semáforo coinciden con /iot/alertas (críticas y advertencias)', () => {{"
                " pm.expect(a1.criticas).to.equal(sev(1468).filter(s => s === 'CRITICO').length); pm.expect(a2.advertencias).to.equal(sev(1494).filter(s => s !== 'CRITICO').length); });",
                f"pm.test('{t5} - área 1495 sin alertas: no pinta ROJO ni AMARILLO', () => {{ pm.expect(sev(1495)).to.eql([]); pm.expect(a3.estado).to.be.oneOf(['VERDE', 'SIN_DATOS']); }});",
                "const caidos = JSON.parse(pm.collectionVariables.get('disp_1495') || '[]');",
                f"pm.test('{t5} - área 1495: VERDE, o «datos no disponibles» (SIN_DATOS) solo si todos sus dispositivos están caídos (R5)', () => {{"
                " if (a3.estado === 'SIN_DATOS') caidos.forEach(e => pm.expect(e).to.be.oneOf(['SIN_SEÑAL', 'EN_MANTENIMIENTO', 'INACTIVO'])); else pm.expect(a3.estado).to.equal('VERDE'); });",
                "if (a3.estado === 'SIN_DATOS') console.warn('DATO: los dispositivos del área 1495 están caídos (' + caidos.join(', ') + '); para ver VERDE hay que refrescar un heartbeat.');",
            ], rol="Productor"),
        ]),
        carpeta("2. TC-M08-006 Solo datos de las fincas asignadas", [
            req(f"{t6} - Ingeniero GET sus fincas", "GET", "{{base_url}}/usuarios/me/fincas", token="tok_ing", tests=[
                f"pm.test('{t6} - el Ingeniero tiene una sola finca (494)', () => {{ pm.response.to.have.status(200); pm.expect(pm.response.json().items.map(f => f.id_finca)).to.eql([494]); }});"]),
            # Este listado no filtra por id_finca para el Administrador (trae todos): se busca el 863 del DBA.
            req(f"{t6} - Administrador GET dispositivos IoT (existe el 863 de la finca ajena 495)", "GET",
                "{{base_url}}/configuracion/dispositivos-iot?por_pagina=1000", token="tok_admin", tests=[
                    f"pm.test('{t6} - existe en TEST el dispositivo 863 de la finca ajena', () => {{ pm.response.to.have.status(200);"
                    " pm.expect(pm.response.json().items.map(x => x.id_dispositivo_iot)).to.include(863); });"]),
            req(f"{t6} - Ingeniero GET sus dispositivos IoT (módulo de origen)", "GET",
                "{{base_url}}/configuracion/dispositivos-iot", token="tok_ing", tests=[
                    f"pm.test('{t6} - dispositivos del Ingeniero (200)', () => pm.response.to.have.status(200));",
                    "pm.collectionVariables.set('disp_propios', JSON.stringify(pm.response.json().items.map(x => x.id_dispositivo_iot)));",
                    "console.log('Propios: ' + pm.collectionVariables.get('disp_propios'));"]),
            widget(t6, "estado_iot", "tok_ing", ok_widget(t6, "estado_iot") + [
                "const propios = JSON.parse(pm.collectionVariables.get('disp_propios') || '[]');",
                "const ids = (datos.items || []).map(x => x.id_dispositivo_iot);",
                f"pm.test('{t6} - Estado Dispositivos IoT: no aparece el dispositivo 863 de la finca ajena', () => pm.expect(ids).to.not.include(863));",
                f"pm.test('{t6} - Estado Dispositivos IoT: todos los dispositivos son de la finca del Ingeniero', () => pm.expect(ids.filter(i => !propios.includes(i))).to.eql([]));"], rol="Ingeniero"),
            widget(t6, "fincas_estado", "tok_ing", ok_widget(t6, "fincas_estado") + [
                f"pm.test('{t6} - Estado de Fincas: solo la finca 494', () => pm.expect((datos.items || datos.fincas || []).map(f => f.id_finca)).to.eql([494]));"],
                finca=None, rol="Ingeniero"),
            widget(t6, "estado_iot", "tok_ing", [
                f"pm.test('{t6} - pedir la finca ajena 495 se bloquea (403 FINCA_NO_AUTORIZADA)', () => {{ pm.response.to.have.status(403);"
                " pm.expect(pm.response.json().error_code).to.equal('FINCA_NO_AUTORIZADA'); });"], finca="{{id_finca_ajena}}", rol="Ingeniero"),
        ]),
        carpeta("3. TC-M08-011 Finca no asignada, usuario con 2 fincas y usuario sin finca", [
            widget(t11, "semaforo_areas", "tok_prod", [
                f"pm.test('{t11} - finca no asignada (495) bloqueada con «No tienes permisos para esta finca» (403)', () => {{ pm.response.to.have.status(403);"
                " pm.expect(pm.response.json().message).to.equal('No tienes permisos para esta finca.'); });"], finca="{{id_finca_ajena}}", rol="Productor"),
            req(f"{t11} - PREP Administrador asigna al Productor las fincas 494 y 495 (solo dentro del sandbox)", "PUT",
                "{{base_url}}/usuarios/{{id_productor}}/fincas", token="tok_admin", body='{\n  "ids_fincas": [494, 495]\n}', tests=[
                    f"pm.test('{t11} - PREP fincas asignadas (200)', () => pm.response.to.have.status(200));",
                    "console.log(pm.response.text());"]),
            req(f"{t11} - Productor GET sus fincas (2)", "GET", "{{base_url}}/usuarios/me/fincas", token="tok_prod", tests=[
                f"pm.test('{t11} - el Productor tiene 2 fincas', () => {{ pm.response.to.have.status(200); pm.expect(pm.response.json().items.map(f => f.id_finca).sort()).to.eql([494, 495]); }});"]),
            req(f"{t11} - Productor GET contexto con 2 fincas", "GET", "{{base_url}}/configuracion/interfaz/contexto", token="tok_prod", tests=[
                f"pm.test('{t11} - con 2 fincas la finca activa sigue siendo una sola (494)', () => {{ pm.response.to.have.status(200); pm.expect(pm.response.json().id_finca).to.equal(494); }});"]),
            widget(t11, "semaforo_areas", "tok_prod", [
                f"pm.test('{t11} - semáforo de la finca 494 (200)', () => pm.response.to.have.status(200));",
                "pm.collectionVariables.set('areas_494', JSON.stringify((datos.areas || []).map(a => a.id_infraestructura)));"], rol="Productor"),
            widget(t11, "semaforo_areas", "tok_prod", [
                f"pm.test('{t11} - al cambiar a la finca 495 el widget responde (200)', () => pm.response.to.have.status(200));",
                "const a494 = JSON.parse(pm.collectionVariables.get('areas_494') || '[]');",
                f"pm.test('{t11} - la finca 495 no mezcla áreas de la 494', () => pm.expect((datos.areas || []).filter(a => a494.includes(a.id_infraestructura))).to.eql([]));"],
                finca="{{id_finca_ajena}}", rol="Productor"),
            req(f"{t11} - PREP Administrador deja al Productor sin fincas (solo dentro del sandbox)", "PUT",
                "{{base_url}}/usuarios/{{id_productor}}/fincas", token="tok_admin", body='{\n  "ids_fincas": []\n}', tests=[
                    f"pm.test('{t11} - PREP fincas retiradas (200)', () => pm.response.to.have.status(200));",
                    "console.log(pm.response.text());"]),
            req(f"{t11} - Productor GET sus fincas (ninguna)", "GET", "{{base_url}}/usuarios/me/fincas", token="tok_prod", tests=[
                f"pm.test('{t11} - el Productor no tiene fincas', () => {{ pm.response.to.have.status(200); pm.expect(pm.response.json().items).to.eql([]); }});"]),
            req(f"{t11} - Productor GET contexto sin finca", "GET", "{{base_url}}/configuracion/interfaz/contexto", token="tok_prod", tests=[
                "console.log(pm.response.text().slice(0, 600));",
                f"pm.test('{t11} - sin finca el contexto no trae finca activa (configuración pendiente)', () => {{ pm.response.to.have.status(200); pm.expect(pm.response.json().id_finca).to.be.null; }});"]),
            widget(t11, "fincas_estado", "tok_prod", [
                f"pm.test('{t11} - Estado de Fincas sin finca: SIN_DATOS «No tienes fincas asignadas.»', () => {{ pm.response.to.have.status(200);"
                " pm.expect(d.estado).to.equal('SIN_DATOS'); pm.expect(d.mensaje).to.equal('No tienes fincas asignadas.'); });"], finca=None, rol="Productor"),
            widget(t11, "semaforo_areas", "tok_prod", [
                f"pm.test('{t11} - sin finca, pedir la 494 se bloquea (403 FINCA_NO_AUTORIZADA)', () => pm.response.to.have.status(403));"], rol="Productor"),
        ]),
    ]
    return coleccion("TC-M08-G003 Semáforo y alcance de fincas (RF-103)",
                     "TC-M08-005, 006 y 011. Áreas 1468/1494/1495 de la finca 494; finca ajena 495. Corre en el sandbox.", items)


# ─────────────────────────────── G004 ───────────────────────────────
def g004():
    t8, t9 = "TC-M08-008", "TC-M08-009"

    def frec(valor, esperado):
        if esperado == 200:
            tests = [f"pm.test('{t9} - frecuencia {valor} s aceptada (200)', () => pm.response.to.have.status(200));",
                     f"pm.test('{t9} - la respuesta guarda {valor} s', () => pm.expect(pm.response.json().frecuencia_actualizacion).to.equal({valor}));",
                     "pm.collectionVariables.set('layout_prod', pm.response.text());"]
        else:
            tests = [f"pm.test('{t9} - frecuencia {valor} s rechazada (400)', () => pm.response.to.have.status(400));",
                     f"pm.test('{t9} - el rechazo de {valor} s trae un mensaje', () => pm.expect(pm.response.json().message).to.be.a('string').and.not.empty);"]
        return patch(f"{t9} - Productor PATCH frecuencia_actualizacion = {valor} s", "tok_prod", "layout_prod",
                     [f"frecuencia = {valor};"], tests)

    items = [
        precondiciones([L_ADMIN, L_PROD]),
        carpeta("1. TC-M08-008 Un widget sin datos no bloquea a los demás", [
            req(f"{t8} - Productor widgets del layout (uno sin datos y otros con datos)", "GET",
                "{{base_url}}/configuracion/personalizacion/dashboard", token="tok_prod", tests=JS_COMUN + [
                    f"pm.test('{t8} - layout del Productor (200)', () => pm.response.to.have.status(200));",
                    "const claves = (pm.response.json().grid || []).map(g => cat[g.id_widget]).filter(Boolean);",
                    "enSerie(claves, k => pedir('GET', '/dashboard/widgets/' + k + '?id_finca=494', 'tok_prod')).then(rs => {",
                    "  const est = {}; rs.forEach((x, i) => est[claves[i]] = x.json || {}); console.log(JSON.stringify(Object.keys(est).map(k => [k, est[k].estado, est[k].mensaje])));",
                    "  const vacios = claves.filter(k => est[k].estado === 'SIN_DATOS'), llenos = claves.filter(k => est[k].estado === 'OK');",
                    f"  pm.test('{t8} - hay al menos un widget sin datos y otros con datos en el mismo layout', () => {{ pm.expect(vacios.length).to.be.above(0); pm.expect(llenos.length).to.be.above(0); }});",
                    f"  pm.test('{t8} - cada widget vacío llega con SIN_DATOS y su mensaje (' + vacios.join(', ') + ')', () => vacios.forEach(k => pm.expect(est[k].mensaje, k).to.be.a('string').and.not.empty));",
                    f"  pm.test('{t8} - los demás widgets muestran sus datos normalmente (200 y OK)', () => llenos.forEach((k) => pm.expect(est[k].datos, k).to.be.an('object')));",
                    f"  pm.test('{t8} - ningún widget del layout queda en ERROR ni falla', () => rs.forEach((x, i) => pm.expect(x.r && x.r.code, claves[i]).to.equal(200)));",
                    "});",
                ]),
            req(f"{t8} - Productor GET dashboard/datos (endpoint de la ficha, deprecated): sin_datos con mensaje", "GET",
                "{{base_url}}/configuracion/personalizacion/dashboard/datos", token="tok_prod", tests=[
                    f"pm.test('{t8} - dashboard/datos (200)', () => pm.response.to.have.status(200));",
                    "const it = pm.response.json() || []; console.log(JSON.stringify(it).slice(0, 1500));",
                    f"pm.test('{t8} - los widgets sin datos traen sin_datos=true y mensaje', () => it.filter(w => w.sin_datos).forEach(w => pm.expect(w.mensaje).to.be.a('string').and.not.empty));",
                ]),
        ]),
        carpeta("2. TC-M08-009 Frecuencia de actualización (backend: valor por defecto y límites 15 a 120 s)", [
            req(f"{t9} - Productor GET layout (frecuencia por defecto)", "GET", "{{base_url}}/configuracion/personalizacion/dashboard",
                token="tok_prod", tests=[
                    f"pm.test('{t9} - layout (200)', () => pm.response.to.have.status(200));",
                    "pm.collectionVariables.set('layout_prod', pm.response.text());",
                    f"pm.test('{t9} - frecuencia por defecto 30 s', () => pm.expect(pm.response.json().frecuencia_actualizacion).to.equal(30));",
                ]),
            frec(15, 200), frec(120, 200), frec(14, 400), frec(121, 400),
            req(f"{t9} - Productor GET layout después de los rechazos", "GET", "{{base_url}}/configuracion/personalizacion/dashboard",
                token="tok_prod", tests=[
                    f"pm.test('{t9} - tras rechazar 14 y 121 queda el último valor válido (120 s)', () => {{ pm.response.to.have.status(200); pm.expect(pm.response.json().frecuencia_actualizacion).to.equal(120); }});"]),
        ]),
    ]
    return coleccion("TC-M08-G004 Resiliencia y frecuencia de actualización (RF-103)",
                     "TC-M08-008 y 009 (parte del backend). El refresco automático en pantalla y el modo offline (TC-M08-010) se prueban en el navegador. Corre en el sandbox.", items)


# ─────────────────────────────── G005 ───────────────────────────────
def g005():
    t = "TC-M08-012"

    def por_rol(tok, rol):
        return req(f"{t} - {rol}: identificador, hora y estado de cada widget del layout", "GET",
                   "{{base_url}}/configuracion/personalizacion/dashboard", token=tok, tests=JS_COMUN + [
            f"pm.test('{t} - layout del {rol} (200)', () => pm.response.to.have.status(200));",
            "const claves = (pm.response.json().grid || []).map(g => cat[g.id_widget]).filter(Boolean);",
            f"enSerie(claves, k => pedir('GET', '/dashboard/widgets/' + k + '?id_finca=494', '{tok}')).then(rs => {{",
            "  rs.forEach((x, i) => console.log(claves[i] + ' ' + JSON.stringify(x.json && { clave: x.json.clave, estado: x.json.estado, actualizado_en: x.json.actualizado_en, huella: x.json.huella })));",
            f"  pm.test('{t} - {rol}: cada widget trae su identificador (clave = la pedida)', () => rs.forEach((x, i) => pm.expect(x.json && x.json.clave, claves[i]).to.equal(claves[i])));",
            f"  pm.test('{t} - {rol}: cada widget trae la hora de su última actualización (reciente)', () => rs.forEach((x, i) => pm.expect(Math.abs(Date.now() - Date.parse(x.json && x.json.actualizado_en)), claves[i]).to.be.below(300000)));",
            f"  pm.test('{t} - {rol}: cada widget trae su estado OK / ERROR / SIN_DATOS', () => rs.forEach((x, i) => pm.expect(x.json && x.json.estado, claves[i]).to.be.oneOf(['OK', 'ERROR', 'SIN_DATOS'])));",
            "});",
        ])

    solo_lectura = [req(f"{t} - {m} /dashboard/widgets/semaforo_areas no modifica datos (405)", m,
                        W + "semaforo_areas?id_finca={{id_finca}}", token="tok_prod", body="{}" if m != "DELETE" else None, tests=[
        f"pm.test('{t} - {m} sobre un widget no está permitido (405): el widget es de solo lectura', () => pm.response.to.have.status(405));"])
        for m in ("POST", "PUT", "PATCH", "DELETE")]
    items = [
        precondiciones([L_ADMIN, L_PROD, L_VET, L_CONT, L_ING]),
        carpeta("1. TC-M08-012 Widgets de solo lectura con identificador, hora y estado",
                [por_rol("tok_prod", "Productor"), por_rol("tok_vet", "Veterinario"), por_rol("tok_cont", "Contador"),
                 por_rol("tok_ing", "Ingeniero")] + solo_lectura),
    ]
    return coleccion("TC-M08-G005 Trazabilidad y solo lectura de los widgets (RF-103)",
                     "TC-M08-012. Los botones de la pantalla se revisan en el navegador. Corre en el sandbox.", items)


if __name__ == "__main__":
    for nombre, fn in (("G001", g001), ("G002", g002), ("G003", g003), ("G004", g004), ("G005", g005)):
        destino = AQUI / f"TC-M08-{nombre}" / f"tc-m08-{nombre.lower()}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(fn(), ensure_ascii=False, indent=2), encoding="utf-8")
        print("Escrito", destino.relative_to(AQUI))
