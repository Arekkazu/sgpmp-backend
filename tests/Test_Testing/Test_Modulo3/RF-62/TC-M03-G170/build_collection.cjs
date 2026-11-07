// | Fecha      | Nombre     | Que se hizo                                                    |
// |------------|------------|----------------------------------------------------------------|
// | 2026-10-23 | QA Team    | Version inicial de coleccion con sensor 91 preexistente        |
// | 2026-10-30 | Juansegutt | B1-B5: eliminar auto-siembra, corregir asserts 324/325 y BD   |

const fs = require('fs');
const path = require('path');

// =====================================================================
// BUILD COLLECTION POSTMAN / NEWMAN — TC-M03-G170 V2 (SENSOR 91 PREEXISTENTE)
// Módulo: M03 — Telemetría y Calidad
// RF: RF-62 (Evaluación de calidad de datos, FA-08 re-evaluación), RF-63
// Subcasos:
//   - TC-M03-324: Re-evaluación exitosa con causa documentada (Sensor 91)
//   - TC-M03-325: Rechazos por causa_documentada inválida (400/422)
//   - TC-M03-326: Validaciones de rango de fechas (400/422)
// =====================================================================

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
// CARPETA 00 — SETUP (Autenticación sin auto-siembra)
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
        '    const token = r.token || r.access_token || (r.data && (r.data.token || r.data.access_token));',
        '    pm.expect(token).to.be.a("string").and.not.empty;',
        '    pm.collectionVariables.set("token_admin", token);',
        '});',
        'try {',
        '    const tokenVal = pm.collectionVariables.get("token_admin");',
        '    const parts = tokenVal.split(".");',
        '    if (parts.length === 3) {',
        '        const payload = JSON.parse(Buffer.from(parts[1], "base64").toString("utf8"));',
        '        const id = payload.sub || payload.id_usuario || payload.user_id;',
        '        pm.collectionVariables.set("id_usuario_admin", id || 1);',
        '    }',
        '} catch (e) {',
        '    pm.collectionVariables.set("id_usuario_admin", 1);',
        '}'
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
        'pm.test("324: Reevaluación HTTP 200", function () {',
        '    pm.response.to.have.status(200);',
        '});',
        'pm.test("324: evaluaciones_superadas > 0", () => {',
        '    pm.expect(pm.response.json().evaluaciones_superadas).to.be.greaterThan(0);',
        '});',
        'pm.test("324: evaluaciones_creadas > 0 (fix INC-M03-133-G170)", () => {',
        '    pm.expect(pm.response.json().evaluaciones_creadas).to.be.greaterThan(0);',
        '});',
        'pm.test("324: contadores coherentes (creadas >= 5)", () => {',
        '    pm.expect(pm.response.json().evaluaciones_creadas).to.be.at.least(5);',
        '});'
    ]),

    // 324.02 — Query 1: Verificar SUPERADA con id_evaluacion_superada poblado
    makeItem("324.02-Verificar-BD-Superadas", "POST",
        "{{baseUrl}}/test-control/query", authQuery(), {
        query: "SELECT COUNT(*) AS n FROM modulo3.telemetria_calidad tc WHERE tc.id_sensor = 91 AND tc.estado_evaluacion = 'SUPERADA' AND tc.id_evaluacion_superada IS NOT NULL"
    }, [], [
        'pm.test("324 BD: existen SUPERADA con id_evaluacion_superada poblado", () => {',
        '    pm.response.to.have.status(200);',
        '    const data = pm.response.json().data || pm.response.json();',
        '    pm.expect(parseInt(data[0].n)).to.be.greaterThan(0);',
        '});'
    ]),

    // 324.03 — Query 2: Cada lectura tiene exactamente 1 VIGENTE (D7 RESUELTO)
    makeItem("324.03-Verificar-BD-Vigentes", "POST",
        "{{baseUrl}}/test-control/query", authQuery(), {
        query: "SELECT COUNT(DISTINCT tc.id_telemetria) AS n_lecturas, SUM(CASE WHEN tc.estado_evaluacion = 'VIGENTE' THEN 1 ELSE 0 END) AS total_vig FROM modulo3.telemetria_calidad tc WHERE tc.id_sensor = 91"
    }, [], [
        'pm.test("324 BD: cada lectura tiene exactamente 1 VIGENTE (D7 RESUELTO)", () => {',
        '    pm.response.to.have.status(200);',
        '    const data = pm.response.json().data || pm.response.json();',
        '    const row = data[0] || {};',
        '    pm.expect(parseInt(row.total_vig)).to.eql(parseInt(row.n_lecturas));',
        '});'
    ]),

    // 324.04 — Query 3: Nuevas VIGENTE tienen motivo_reevaluacion poblado
    makeItem("324.04-Verificar-BD-Motivo", "POST",
        "{{baseUrl}}/test-control/query", authQuery(), {
        query: "SELECT COUNT(*) AS n FROM modulo3.telemetria_calidad tc WHERE tc.id_sensor = 91 AND tc.estado_evaluacion = 'VIGENTE' AND tc.motivo_reevaluacion IS NOT NULL AND tc.motivo_reevaluacion <> ''"
    }, [], [
        'pm.test("324 BD: nuevas VIGENTE tienen motivo_reevaluacion poblado", () => {',
        '    pm.response.to.have.status(200);',
        '    const data = pm.response.json().data || pm.response.json();',
        '    pm.expect(parseInt(data[0].n)).to.be.greaterThan(0);',
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
        'pm.test("325d: rechazo por preferencia (CA-17)", () => {',
        '    pm.expect(pm.response.code).to.eql(422);',
        '    pm.expect((pm.response.json().message || "").toLowerCase())',
        '        .to.satisfy(m => m.includes("error") || m.includes("document"));',
        '});'
    ]),

    // 325.05 — Verificación BD Inocuidad
    makeItem("325.05-Verificar-BD-Sin-Cambios", "POST",
        "{{baseUrl}}/test-control/query", authQuery(), {
        query: "SELECT COUNT(*) AS n FROM modulo3.telemetria_calidad tc WHERE tc.id_sensor = 91 AND tc.timestamp_evaluacion > NOW() - interval '1 min'"
    }, [], [
        'pm.test("325 BD: 0 evaluaciones creadas ni superadas en rechazo", () => {',
        '    pm.response.to.have.status(200);',
        '    const data = pm.response.json().data || pm.response.json();',
        '    pm.expect(parseInt(data[0].n)).to.eql(0);',
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
    ]),

    // 326.03 — Verificación BD Inocuidad
    makeItem("326.03-Verificar-BD-Sin-Cambios", "POST",
        "{{baseUrl}}/test-control/query", authQuery(), {
        query: "SELECT COUNT(*) AS n FROM modulo3.telemetria_calidad tc WHERE tc.id_sensor = 91 AND tc.timestamp_evaluacion > NOW() - interval '1 min'"
    }, [], [
        'pm.test("326 BD: 0 evaluaciones creadas ni superadas en rechazo fechas", () => {',
        '    pm.response.to.have.status(200);',
        '    const data = pm.response.json().data || pm.response.json();',
        '    pm.expect(parseInt(data[0].n)).to.eql(0);',
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
        { key: "token_admin", value: "" },
        { key: "id_usuario_admin", value: "" }
    ],
    item: [
        { name: "00-Setup", item: preflight },
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
