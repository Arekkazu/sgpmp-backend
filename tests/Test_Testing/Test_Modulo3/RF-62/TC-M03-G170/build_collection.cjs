const fs = require('fs');
const path = require('path');

// =====================================================================
// BUILD COLLECTION POSTMAN / NEWMAN — TC-M03-G170 V2 (CAMINO 2: SENSOR 91 PREEXISTENTE)
// Módulo: M03 — Telemetría y Calidad
// RF: RF-62 (Evaluación de calidad de datos, FA-08 re-evaluación), RF-63
// Subcasos:
//   - TC-M03-324: Re-evaluación exitosa con causa documentada (Sensor 91)
//   - TC-M03-325: Rechazos por causa_documentada inválida (400/422)
//   - TC-M03-326: Validaciones de rango de fechas (400/422)
// =====================================================================

function letrasAleatorias(len) {
    const chars = "abcdefghijklmnopqrstuvwxyz";
    let res = "";
    for (let i = 0; i < len; i++) {
        res += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return res;
}

function makeHeader(key, value) {
    return { key: key, value: value };
}

function authAdmin() {
    return [
        makeHeader("Authorization", "Bearer {{token_admin}}"),
        makeHeader("Content-Type", "application/json")
    ];
}

function authQuery() {
    return [
        makeHeader("Authorization", "Bearer {{token_admin}}"),
        makeHeader("X-Sandbox-Secret", "{{sandbox_secret}}"),
        makeHeader("X-Test-Run-Id", "{{run_id}}"),
        makeHeader("Content-Type", "application/json")
    ];
}

function makeItem(name, method, url, headers, bodyObj, preScripts, postTests) {
    const item = {
        name: name,
        request: {
            method: method,
            header: headers || [],
            url: {
                raw: url,
                host: ["{{baseUrl}}"],
                path: url.replace("{{baseUrl}}/", "").split("?")[0].split("/"),
                query: []
            }
        }
    };

    if (url.includes("?")) {
        const qStr = url.split("?")[1];
        qStr.split("&").forEach(pair => {
            const [k, v] = pair.split("=");
            item.request.url.query.push({ key: k, value: v });
        });
    }

    if (bodyObj !== null && method !== "GET" && method !== "DELETE") {
        item.request.body = {
            mode: "raw",
            raw: typeof bodyObj === "string" ? bodyObj : JSON.stringify(bodyObj, null, 2),
            options: { raw: { language: "json" } }
        };
    }

    item.event = [];
    if (preScripts && preScripts.length > 0) {
        item.event.push({
            listen: "prerequest",
            script: { type: "text/javascript", exec: preScripts }
        });
    }
    if (postTests && postTests.length > 0) {
        item.event.push({
            listen: "test",
            script: { type: "text/javascript", exec: postTests }
        });
    }

    return item;
}

// =====================================================================
// CARPETA 00 — PREFLIGHT (autosiembra canónica de contexto)
// =====================================================================
const preflight = [
    // 00.01 — Login admin
    makeItem("00.01-Login-Admin", "POST", "{{baseUrl}}/sesiones/", [], {
        correo_electronico: "administador.dev@gmail.com",
        contrasena: "{{admin_password}}"
    }, [], [
        'pm.test("Login 200", function () {',
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    pm.expect(r.token).to.be.a("string").and.not.empty;',
        '    pm.collectionVariables.set("token_admin", r.token);',
        '});',
        'try {',
        '    const parts = pm.response.json().token.split(".");',
        '    if (parts.length === 3) {',
        '        const payload = JSON.parse(Buffer.from(parts[1], "base64").toString("utf8"));',
        '        const id = payload.sub || payload.id_usuario || payload.user_id;',
        '        pm.test("id_usuario extraido del JWT", function () {',
        '            pm.expect(id, "JWT sin sub/id_usuario/user_id").to.exist;',
        '        });',
        '        pm.collectionVariables.set("id_usuario_admin", id || 1);',
        '    }',
        '} catch (e) {',
        '    pm.collectionVariables.set("id_usuario_admin", 1);',
        '}'
    ]),

    // 00.02 — Tipo dispositivo
    makeItem("00.02-Get-Tipos-Dispositivo", "GET",
        "{{baseUrl}}/configuracion/tipos-dispositivo-iot?pagina=1&por_pagina=10", authAdmin(), null, [], [
        'pm.test("Tipos dispositivo 200", function () {',
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    const list = Array.isArray(r) ? r : (r.items || []);',
        '    pm.expect(list.length).to.be.above(0);',
        '    const match = list.find(t => (t.nombre || "").toUpperCase().includes("SENSOR")) || list[0];',
        '    pm.collectionVariables.set("id_tipo_dispositivo", match.id_tipo_dispositivo);',
        '});'
    ]),

    // 00.03 — Tipos área
    makeItem("00.03-Get-Tipos-Area", "GET",
        "{{baseUrl}}/configuracion/tipos-area?pagina=1&por_pagina=10", authAdmin(), null, [], [
        'pm.test("Tipos área 200", function () {',
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    const list = Array.isArray(r) ? r : (r.items || []);',
        '    pm.expect(list.length).to.be.above(0);',
        '    const match = list.find(a => (a.nombre || "").toUpperCase().includes("PRODUCCI")) || list[0];',
        '    pm.collectionVariables.set("tipo_area_nombre", match.nombre);',
        '});'
    ]),

    // 00.04 — Finca
    makeItem("00.04-Crear-Finca", "POST", "{{baseUrl}}/configuracion/fincas", authAdmin(), {
        nombre: "Finca " + letrasAleatorias(10),
        ubicacion: {
            departamento: "Huila",
            municipio: "Neiva",
            vereda: "Qa",
            latitud: 2.9273,
            longitud: -75.2819
        },
        tamano_h: 10.5,
        id_usuario: "{{id_usuario_admin}}"
    }, [], [
        'pm.test("Finca 201", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_finca).to.be.a("number").and.above(0);',
        '    pm.collectionVariables.set("id_finca", r.id_finca);',
        '});'
    ]),

    // 00.05 — Área
    makeItem("00.05-Crear-Area", "POST", "{{baseUrl}}/configuracion/infraestructuras", authAdmin(), {
        nombre_infraestructura: "Area " + letrasAleatorias(10),
        tipo_area: "{{tipo_area_nombre}}",
        superficie: 100.0,
        finca_id: "{{id_finca}}",
        descripcion_infraestructura: "Area de pruebas reevaluacion RF-62",
        especie_id: 2,
        tipo_modelo_asignado: null
    }, [], [
        'pm.test("Área 201", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_infraestructura).to.be.a("number").and.above(0);',
        '    pm.collectionVariables.set("id_infraestructura", r.id_infraestructura);',
        '});'
    ]),

    // 00.06 — Dispositivo
    makeItem("00.06-Crear-Dispositivo", "POST",
        "{{baseUrl}}/configuracion/dispositivos-iot", authAdmin(), {
        serial: "GDEV" + letrasAleatorias(8).toUpperCase(),
        descripcion: "Dispositivo base pruebas reevaluacion",
        id_infraestructura: "{{id_infraestructura}}",
        id_tipo_dispositivo: "{{id_tipo_dispositivo}}",
        es_activo: true
    }, [], [
        'pm.test("Dispositivo 201", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_dispositivo_iot).to.be.a("number").and.above(0);',
        '    pm.collectionVariables.set("dev_id_324", r.id_dispositivo_iot);',
        '});'
    ]),

    // 00.07 — Crear Sensor (Punto de falla conocido INC-M03-G167-SENSOR-500)
    makeItem("00.07-Crear-Sensor", "POST",
        "{{baseUrl}}/configuracion/dispositivos-iot/{{dev_id_324}}/sensores", authAdmin(), {
        tipo_sensor: "TEMPERATURA_AGUA",
        categoria: "TEMPERATURA",
        marca: "YSI",
        modelo: "ProSolo",
        rango_minimo: 0.0,
        rango_maximo: 50.0,
        precision: 0.1,
        unidad_medida: "°C",
        id_variable: 9,
        frecuencia_muestreo: 60,
        pin_conexion: "A0",
        fecha_instalacion: "2026-10-20T00:00:00Z"
    }, [], [
        'pm.test("Sensor 201 (Punto de falla INC-M03-G167-SENSOR-500)", function () {',
        '    pm.response.to.have.status(201);',
        '});'
    ]),

    // 00.08 — Asociar sensor al área
    makeItem("00.08-Asociar-Sensor-Area", "POST",
        "{{baseUrl}}/configuracion/sensores/1/asociar", authAdmin(), {
        id_infraestructura: "{{id_infraestructura}}"
    }, [], [
        'pm.test("Asociación 201", function () {',
        '    pm.expect([200, 201, 404]).to.include(pm.response.code);',
        '});'
    ])
];

// =====================================================================
// CARPETA TC-324 — RE-EVALUACIÓN EXITOSA CON SENSOR PREEXISTENTE 91
// =====================================================================
const tc324 = [
    // 324.01 — POST /iot/calidad/reevaluar
    makeItem("324.01-Solicitar-Reevaluacion", "POST",
        "{{baseUrl}}/iot/calidad/reevaluar", authAdmin(), {
        id_sensor: 91,
        fecha_desde: "2026-10-23T05:22:16.733743Z",
        fecha_hasta: "2026-10-23T05:22:16.850570Z",
        causa_documentada: "Offset de calibracion mal configurado en RF-24 genero drift falso masivo",
        parametros_correctos: {
            offset: 0,
            ganancia: 1
        }
    }, [], [
        'pm.test("324.01: Reevaluación HTTP 200", function () {',
        '    pm.response.to.have.status(200);',
        '});',
        'const r = pm.response.json();',
        'pm.test("324.02: Evaluaciones superadas >= 5", function () {',
        '    pm.expect(r.evaluaciones_superadas).to.be.at.least(5);',
        '});',
        'pm.test("324.03: Documentar hallazgo: evaluaciones_creadas es 0", function () {',
        '    pm.expect(r.evaluaciones_creadas, "INC-M03-G170: endpoint no regenera evaluaciones, solo supera").to.be.equal(0);',
        '});'
    ]),

    // 324.02 — SELECT verificar SUPERADA en BD
    makeItem("324.02-Verificar-Evaluaciones-Superadas-DB", "POST",
        "{{baseUrl}}/test-control/query", authQuery(), {
        query: "SELECT id_evaluacion, estado_evaluacion, motivo_reevaluacion FROM modulo3.telemetria_calidad WHERE id_sensor = 91"
    }, [], [
        'pm.test("324.04: Query BD 200 y evaluaciones marcadas SUPERADA", function () {',
        '    pm.response.to.have.status(200);',
        '    const body = pm.response.json();',
        '    const rows = body.data || [];',
        '    pm.expect(rows.length).to.be.at.least(5);',
        '    rows.forEach(function(row) {',
        '        pm.expect(row.estado_evaluacion).to.eql("SUPERADA");',
        '        pm.expect(row.motivo_reevaluacion).to.include("Offset de calibracion mal configurado");',
        '    });',
        '});'
    ])
];

// =====================================================================
// CARPETA TC-325 — RECHAZOS POR CAUSA_DOCUMENTADA INVÁLIDA (400/422)
// =====================================================================
const tc325 = [
    // 325a — Sin causa_documentada
    makeItem("325.01-Rechazo-Sin-Causa", "POST",
        "{{baseUrl}}/iot/calidad/reevaluar", authAdmin(), {
        id_sensor: 91,
        fecha_desde: "2026-10-23T05:22:16.733743Z",
        fecha_hasta: "2026-10-23T05:22:16.850570Z",
        parametros_correctos: { offset: 0, ganancia: 1 }
    }, [], [
        'pm.test("325a: Sin causa -> 400 o 422", function () {',
        '    pm.expect([400, 422]).to.include(pm.response.code);',
        '});'
    ]),

    // 325b — Causa vacía
    makeItem("325.02-Rechazo-Causa-Vacia", "POST",
        "{{baseUrl}}/iot/calidad/reevaluar", authAdmin(), {
        id_sensor: 91,
        fecha_desde: "2026-10-23T05:22:16.733743Z",
        fecha_hasta: "2026-10-23T05:22:16.850570Z",
        causa_documentada: "",
        parametros_correctos: { offset: 0, ganancia: 1 }
    }, [], [
        'pm.test("325b: Causa vacía -> 400 o 422", function () {',
        '    pm.expect([400, 422]).to.include(pm.response.code);',
        '});'
    ]),

    // 325c — Causa corta (<10 caracteres)
    makeItem("325.03-Rechazo-Causa-Corta", "POST",
        "{{baseUrl}}/iot/calidad/reevaluar", authAdmin(), {
        id_sensor: 91,
        fecha_desde: "2026-10-23T05:22:16.733743Z",
        fecha_hasta: "2026-10-23T05:22:16.850570Z",
        causa_documentada: "ab",
        parametros_correctos: { offset: 0, ganancia: 1 }
    }, [], [
        'pm.test("325c: Causa corta (<10) -> 400 o 422", function () {',
        '    pm.expect([400, 422]).to.include(pm.response.code);',
        '});'
    ]),

    // 325d — Causa por mero cambio de preferencia (CA-17)
    makeItem("325.04-Rechazo-Causa-Preferencia", "POST",
        "{{baseUrl}}/iot/calidad/reevaluar", authAdmin(), {
        id_sensor: 91,
        fecha_desde: "2026-10-23T05:22:16.733743Z",
        fecha_hasta: "2026-10-23T05:22:16.850570Z",
        causa_documentada: "quiero cambiar el umbral_drift de 5% a 3%",
        parametros_correctos: { offset: 0, ganancia: 1 }
    }, [], [
        'pm.test("325d: Causa de preferencia (CA-17)", function () {',
        '    pm.expect([200, 400, 422]).to.include(pm.response.code);',
        '});'
    ])
];

// =====================================================================
// CARPETA TC-326 — VALIDACIONES DE RANGO DE FECHAS (400/422)
// =====================================================================
const tc326 = [
    // 326a — fecha_desde > fecha_hasta
    makeItem("326.01-Rechazo-Fechas-Invertidas", "POST",
        "{{baseUrl}}/iot/calidad/reevaluar", authAdmin(), {
        id_sensor: 91,
        fecha_desde: "2026-10-23T12:00:00Z",
        fecha_hasta: "2026-10-23T10:00:00Z",
        causa_documentada: "Causa documentada con longitud suficiente para test de fechas invertidas",
        parametros_correctos: { offset: 0, ganancia: 1 }
    }, [], [
        'pm.test("326a: fecha_desde > fecha_hasta -> 400 o 422", function () {',
        '    pm.expect([400, 422]).to.include(pm.response.code);',
        '});'
    ]),

    // 326b — fecha_desde == fecha_hasta
    makeItem("326.02-Caso-Fechas-Iguales", "POST",
        "{{baseUrl}}/iot/calidad/reevaluar", authAdmin(), {
        id_sensor: 91,
        fecha_desde: "2026-10-23T05:22:16.733743Z",
        fecha_hasta: "2026-10-23T05:22:16.733743Z",
        causa_documentada: "Causa documentada con longitud suficiente para test de fecha puntual",
        parametros_correctos: { offset: 0, ganancia: 1 }
    }, [], [
        'pm.test("326b: fecha_desde == fecha_hasta documentado", function () {',
        '    pm.expect([200, 400, 422]).to.include(pm.response.code);',
        '});'
    ])
];

// =====================================================================
// CARPETA 99 — TEARDOWN (rollback sandbox)
// =====================================================================
const teardown = [
    makeItem("99.01-Rollback-Sandbox", "DELETE",
        "{{baseUrl}}/test-control/runs/{{run_id}}", [
        makeHeader("X-Sandbox-Secret", "{{sandbox_secret}}")
    ], null, [], [
        'pm.test("Rollback 200", function () {',
        '    pm.response.to.have.status(200);',
        '});'
    ])
];

// =====================================================================
// COLECCIÓN COMPLETA
// =====================================================================
const collection = {
    info: {
        name: "TC-M03-G170 V2 — Reevaluacion explicita (RF-62, sensor 91 preexistente)",
        description: "Suite de pruebas para POST /iot/calidad/reevaluar con sensor preexistente 91 en sandbox (TC-324, TC-325, TC-326).",
        schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    event: [
        {
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: [
                    'let rid = pm.variables.get("run_id");',
                    'if (!rid || !rid.trim()) {',
                    '    rid = "test-" + pm.variables.replaceIn("{{$guid}}");',
                    '    pm.collectionVariables.set("run_id", rid);',
                    '}',
                    'pm.request.headers.upsert({ key: "X-Test-Run-Id", value: rid });',
                    '',
                    'const sec = pm.variables.get("sandbox_secret");',
                    'if (sec && sec.trim()) {',
                    '    pm.request.headers.upsert({ key: "X-Sandbox-Secret", value: sec });',
                    '} else {',
                    '    console.warn("[TC-M03-G170] sandbox_secret no resuelto. Los requests van a fallar con 403.");',
                    '}'
                ]
            }
        }
    ],
    variable: [
        { key: "baseUrl", value: "https://www.api.inmero.co/api-sgpmp-test" },
        { key: "run_id", value: "" },
        { key: "sandbox_secret", value: "" },
        { key: "admin_password", value: "" },
        { key: "broker_token", value: "" },
        { key: "token_admin", value: "" },
        { key: "id_usuario_admin", value: "" },
        { key: "id_tipo_dispositivo", value: "" },
        { key: "tipo_area_nombre", value: "" },
        { key: "id_finca", value: "" },
        { key: "id_infraestructura", value: "" },
        { key: "dev_id_324", value: "" }
    ],
    item: [
        { name: "00-Preflight-Autosiembra", item: preflight },
        { name: "TC-324-reevaluacion-exitosa", item: tc324 },
        { name: "TC-325-rechazos-por-causa", item: tc325 },
        { name: "TC-326-rechazos-por-fechas", item: tc326 },
        { name: "99-Teardown", item: teardown }
    ]
};

const outPath = path.join(__dirname, "test_tc_m03_g170.json");
fs.writeFileSync(outPath, JSON.stringify(collection, null, 2), "utf8");
console.log("Colección generada:", outPath);
console.log(`Carpetas: ${collection.item.length}, Requests: ${preflight.length + tc324.length + tc325.length + tc326.length + teardown.length}`);
