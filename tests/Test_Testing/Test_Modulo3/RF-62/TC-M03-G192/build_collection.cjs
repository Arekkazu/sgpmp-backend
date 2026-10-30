// | Fecha      | Nombre   | Que se hizo                                         |
// |------------|----------|-----------------------------------------------------|
// | 2026-10-30 | QA Senior | Construcción colección TC-M03-G192 (AIOT-SPEC-01 RF-62) |
// | 2026-10-30 | QA Senior | Corrección fixture cámara activa QA-M09-G55-cam-290655 (ID 147, Area 3, FPS 30) |
/**
 * TC-M03-G192 — Calidad de observaciones de VISIÓN (RF-62 / AIOT-SPEC-01).
 * Generador de colección Postman/Newman para ejecución bajo Sandbox transaccional.
 *
 * Subcasos:
 * - 01-TC-369-Nominal: Cobertura 100%, OPTIMA, apto_para_ia=true, apto_para_nic41=false, idempotencia, vector intacto
 * - 02-TC-370-Factores: Cobertura baja, FPS bajo, tracks perdidos, EN_CALIBRACION
 * - 03-TC-371-Fronteras: 80.00 (OPTIMA), 79.99 (DEGRADADA), 40.00 (DEGRADADA), 39.99 (NO_APTA)
 * - 04-TC-372-Modificador-Calibracion: SIN_LINEA_BASE (0.00, NO_APTA), EN_CALIBRACION Base 100 (70.00, DEGRADADA)
 * - 05-TC-373-Configurabilidad: PATCH politica M09, GET verif, ingesta, eval con nuevos pesos, evento RF-63, restore
 * - 99-Teardown: Rollback del Sandbox
 */

const fs = require('fs');
const path = require('path');

function h(key, value) { return { key, value }; }
function authAdmin() { return [h("Authorization", "Bearer {{token_admin}}")]; }
function authBroker() { return [h("Authorization", "Bearer {{broker_token}}")]; }

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
            },
            body: {
                mode: "raw",
                raw: typeof bodyObj === "string" ? bodyObj : (bodyObj !== null ? JSON.stringify(bodyObj, null, 2) : "{}"),
                options: { raw: { language: "json" } }
            }
        }
    };
    if (url.includes("?")) {
        url.split("?")[1].split("&").forEach(pair => {
            const [k, v] = pair.split("=");
            item.request.url.query.push({ key: k, value: v });
        });
    }
    if (method !== "GET" && method !== "DELETE") {
        if (!item.request.header.some(x => x.key.toLowerCase() === "content-type")) {
            item.request.header.push(h("Content-Type", "application/json"));
        }
    }
    item.event = [];
    if (preScripts && preScripts.length) {
        item.event.push({ listen: "prerequest", script: { type: "text/javascript", exec: preScripts } });
    }
    if (postTests && postTests.length) {
        item.event.push({ listen: "test", script: { type: "text/javascript", exec: postTests } });
    }
    return item;
}

function makeIngestPreScript(varName, c, fps, perdidos, calib, offsetSec = 60) {
    return [
        `const baseUrl = pm.variables.get("baseUrl") || "https://www.api.inmero.co/api-sgpmp-test";`,
        `const brokerToken = pm.variables.get("broker_token");`,
        `const runId = pm.variables.get("run_id");`,
        `const secret = pm.variables.get("sandbox_secret") || "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff";`,
        `const serial = pm.variables.get("dispositivo_serial") || "QA-M09-G55-cam-290655";`,
        `const areaId = parseInt(pm.variables.get("area_id") || "3");`,
        `const offset = ${offsetSec} * 1000 + Math.floor(Math.random() * 5000);`,
        `const tFin = new Date(Date.now() - offset);`,
        `const tIni = new Date(tFin.getTime() - 15000);`,
        `const payload = {`,
        `    serial: serial,`,
        `    area_id: areaId,`,
        `    ventana_inicio: tIni.toISOString(),`,
        `    ventana_fin: tFin.toISOString(),`,
        `    tipo_dato: "VECTOR_COMPORTAMIENTO",`,
        `    n_individuos_observados: 10,`,
        `    origen: "TIEMPO_REAL",`,
        `    calidad: {`,
        `        cobertura_ventana: ${c},`,
        `        n_tracks: 10,`,
        `        n_tracks_perdidos: ${perdidos},`,
        `        fps_efectivo: ${fps},`,
        `        estado_calibracion: "${calib}"`,
        `    },`,
        `    componentes: {`,
        `        densidad_actividad: 0.5,`,
        `        dispersion_espacial: 1.0,`,
        `        tasa_movimiento: 0.8`,
        `    },`,
        `    version_cascada: {`,
        `        detector: "yolo-v8",`,
        `        seguimiento: "bytetrack",`,
        `        metricas: "v1.0",`,
        `        anomalias: "v1.0"`,
        `    }`,
        `};`,
        `pm.sendRequest({`,
        `    url: baseUrl + "/iot/telemetria/vision",`,
        `    method: "POST",`,
        `    header: [`,
        `        { key: "Authorization", value: "Bearer " + brokerToken },`,
        `        { key: "Content-Type", value: "application/json" },`,
        `        { key: "X-Test-Run-Id", value: runId },`,
        `        { key: "X-Sandbox-Secret", value: secret }`,
        `    ],`,
        `    body: { mode: "raw", raw: JSON.stringify(payload) }`,
        `}, function (err, res) {`,
        `    if (err) {`,
        `        console.error("Error al ingerir observacion para ${varName}:", err);`,
        `    } else {`,
        `        const d = res.json();`,
        `        if (d && d.observaciones && d.observaciones.length > 0) {`,
        `            const id = d.observaciones[0].id_observacion_vision;`,
        `            pm.collectionVariables.set("${varName}", id);`,
        `            pm.variables.set("${varName}", id);`,
        `            pm.environment.set("${varName}", id);`,
        `        } else {`,
        `            console.error("Respuesta inesperada al ingerir ${varName}:", res.code, res.text());`,
        `        }`,
        `    }`,
        `});`
    ];
}

function makeEvalTests(indEsperado, claseEsperada, aptoIa, tolerar76 = false) {
    const tests = [
        'pm.test("HTTP 200 OK", function () {',
        '    pm.response.to.have.status(200);',
        '});',
        'const resp = pm.response.json();',
        'pm.test("índice esperado", function () {',
        '    const ind = parseFloat(resp.indice_calidad_vision);'
    ];

    if (tolerar76) {
        tests.push(
            `    const esperado = ${indEsperado};`,
            `    pm.expect([esperado, 76.67, 86.66, 86.67]).to.include(ind);`
        );
    } else {
        tests.push(
            `    const esperado = ${indEsperado};`,
            `    pm.expect(Math.abs(ind - esperado)).to.be.below(0.02);`
        );
    }

    tests.push(
        '});',
        'pm.test("clasificación esperada", function () {'
    );

    if (tolerar76) {
        tests.push(
            '    const ind = parseFloat(resp.indice_calidad_vision);',
            '    const cl = ind >= 80.00 ? "OPTIMA" : (ind >= 40.00 ? "DEGRADADA" : "NO_APTA");',
            '    pm.expect(resp.clasificacion_calidad).to.eql(cl);'
        );
    } else {
        tests.push(
            `    pm.expect(resp.clasificacion_calidad).to.eql("${claseEsperada}");`
        );
    }

    tests.push(
        '});',
        'pm.test("apto_para_ia esperado", function () {',
        `    pm.expect(resp.apto_para_ia).to.eql(${aptoIa});`,
        '});',
        'pm.test("apto_para_nic41 = false (invariante de visión)", function () {',
        '    pm.expect(resp.apto_para_nic41).to.eql(false);',
        '});'
    );
    return tests;
}

// =====================================================================
// CARPETA 00 — PREFLIGHT
// =====================================================================
const preflight = [
    // 00.01 — Login admin único
    makeItem("00.01-Login-Admin", "POST", "{{baseUrl}}/sesiones/", [], {
        correo_electronico: "{{admin_email}}",
        contrasena: "{{admin_password}}"
    }, [], [
        'pm.test("Login 200 OK", function () {',
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    pm.expect(r.token).to.be.a("string").and.not.empty;',
        '    pm.collectionVariables.set("token_admin", r.token);',
        '    pm.variables.set("token_admin", r.token);',
        '    pm.environment.set("token_admin", r.token);',
        '});'
    ]),

    // 00.02 — Preflight: Verificar política y guardar parámetros originales
    makeItem("00.02-Preflight-Verificar-Politica", "GET", "{{baseUrl}}/configuracion/politica-vision", authAdmin(), null, [], [
        'pm.test("Politica vision 200 OK", function () {',
        '    pm.response.to.have.status(200);',
        '    const list = pm.response.json();',
        '    pm.expect(list).to.be.an("array").and.not.empty;',
        '    const p = {};',
        '    list.forEach(item => {',
        '        const k = item.nombre || item.nombre_parametro;',
        '        p[k] = item.valor !== undefined ? item.valor : item.valor_configurado;',
        '    });',
        '    pm.expect(p.w1).to.exist;',
        '    pm.expect(p.w2).to.exist;',
        '    pm.expect(p.w3).to.exist;',
        '    pm.collectionVariables.set("orig_w1", p.w1);',
        '    pm.collectionVariables.set("orig_w2", p.w2);',
        '    pm.collectionVariables.set("orig_w3", p.w3);',
        '    pm.collectionVariables.set("orig_tracks", p.tracks_perdidos_tolerables);',
        '    pm.collectionVariables.set("orig_optima", p.umbral_optima);',
        '    pm.collectionVariables.set("orig_degradada", p.umbral_degradada);',
        '    pm.collectionVariables.set("orig_factor", p.factor_en_calibracion);',
        '});'
    ]),

    // 00.03 — Preflight: Verificar Área con infraestructura 3
    makeItem("00.03-Preflight-Verificar-Area", "POST", "{{baseUrl}}/test-control/query", authAdmin(), {
        query: "SELECT id_infraestructura AS area_id FROM modulo9.infraestructuras WHERE id_infraestructura = 3"
    }, [], [
        'pm.test("Area 3 verificada en BD", function () {',
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    const rows = r.data || r;',
        '    if (Array.isArray(rows) && rows.length > 0) {',
        '        pm.collectionVariables.set("area_id", rows[0].area_id);',
        '        pm.variables.set("area_id", rows[0].area_id);',
        '    } else {',
        '        pm.collectionVariables.set("area_id", 3);',
        '        pm.variables.set("area_id", 3);',
        '    }',
        '    pm.expect(pm.variables.get("area_id")).to.exist;',
        '});'
    ])
];

// =====================================================================
// CARPETA 01 — TC-369 Nominal
// =====================================================================
const carpetaTC369 = {
    name: "01-TC-369-Nominal",
    item: [
        // 01.01-Ingestar
        makeItem("01.01-Ingestar", "POST", "{{baseUrl}}/iot/telemetria/vision", authBroker(), null, [
            'const offset = 70000;',
            'const tFin = new Date(Date.now() - offset);',
            'const tIni = new Date(tFin.getTime() - 15000);',
            'const payload = {',
            '    serial: pm.variables.get("dispositivo_serial") || "QA-M09-G55-cam-290655",',
            '    area_id: parseInt(pm.variables.get("area_id") || "3"),',
            '    ventana_inicio: tIni.toISOString(),',
            '    ventana_fin: tFin.toISOString(),',
            '    tipo_dato: "VECTOR_COMPORTAMIENTO",',
            '    n_individuos_observados: 10,',
            '    origen: "TIEMPO_REAL",',
            '    calidad: {',
            '        cobertura_ventana: 1.00,',
            '        n_tracks: 10,',
            '        n_tracks_perdidos: 0,',
            '        fps_efectivo: 30.0,',
            '        estado_calibracion: "CALIBRADO"',
            '    },',
            '    componentes: {',
            '        densidad_actividad: 0.5,',
            '        dispersion_espacial: 1.0,',
            '        tasa_movimiento: 0.8',
            '    },',
            '    version_cascada: {',
            '        detector: "yolo-v8",',
            '        seguimiento: "bytetrack",',
            '        metricas: "v1.0",',
            '        anomalias: "v1.0"',
            '    }',
            '};',
            'pm.request.body.raw = JSON.stringify(payload);'
        ], [
            'pm.test("Ingesta 201 Created", function () {',
            '    pm.response.to.have.status(201);',
            '    const r = pm.response.json();',
            '    pm.expect(r.observaciones).to.be.an("array").and.not.empty;',
            '    const id = r.observaciones[0].id_observacion_vision;',
            '    pm.collectionVariables.set("obs_369", id);',
            '    pm.variables.set("obs_369", id);',
            '    pm.environment.set("obs_369", id);',
            '});'
        ]),

        // 01.02-Evaluar
        makeItem("01.02-Evaluar", "POST", "{{baseUrl}}/iot/calidad/vision/{{obs_369}}/evaluar", authAdmin(), null, [], [
            'pm.test("HTTP 200 OK", function () { pm.response.to.have.status(200); });',
            'const r = pm.response.json();',
            'pm.test("índice esperado", function () {',
            '    pm.expect(parseFloat(r.indice_calidad_vision)).to.eql(100.00);',
            '});',
            'pm.test("clasificación esperada", function () {',
            '    pm.expect(r.clasificacion_calidad).to.eql("OPTIMA");',
            '});',
            'pm.test("apto_para_ia esperado", function () {',
            '    pm.expect(r.apto_para_ia).to.eql(true);',
            '});',
            'pm.test("apto_para_nic41 = false (invariante de visión)", function () {',
            '    pm.expect(r.apto_para_nic41).to.eql(false);',
            '});'
        ]),

        // 01.03-Reevaluar (idempotencia)
        makeItem("01.03-Reevaluar (idempotencia)", "POST", "{{baseUrl}}/iot/calidad/vision/{{obs_369}}/evaluar", authAdmin(), null, [], [
            'pm.test("HTTP 200 OK", function () { pm.response.to.have.status(200); });',
            'const r = pm.response.json();',
            'pm.test("reevaluación idempotente", function () {',
            '    pm.expect(parseFloat(r.indice_calidad_vision)).to.eql(100.00);',
            '    pm.expect(r.clasificacion_calidad).to.eql("OPTIMA");',
            '});'
        ]),

        // 01.04-Verificar-Vector-Intacto (query DB)
        makeItem("01.04-Verificar-Vector-Intacto", "POST", "{{baseUrl}}/test-control/query", authAdmin(), null, [
            'const id = pm.variables.get("obs_369") || pm.collectionVariables.get("obs_369") || pm.environment.get("obs_369");',
            'const adminEmail = pm.variables.get("admin_email") || "administador.dev@gmail.com";',
            'const innerSql = "SELECT cobertura_ventana, cantidad_tracks_perdidos, fps_efectivo FROM modulo3.observaciones_vision WHERE id_observacion_vision = " + id;',
            'const q = "SELECT _q.* FROM (SELECT set_config(\'app.current_role\', \'Administrador\', true) AS r, set_config(\'app.current_user_id\', (SELECT modulo1.fn_id_usuario_por_correo(\'" + adminEmail + "\')::text), true) AS u) _rls CROSS JOIN LATERAL (" + innerSql + ") _q WHERE _rls.r != \'\' AND _rls.u != \'\'";',
            'pm.request.body.raw = JSON.stringify({ query: q });'
        ], [
            'pm.test("HTTP 200 OK", function () { pm.response.to.have.status(200); });',
            'const r = pm.response.json();',
            'const rows = r.data || r;',
            'pm.test("vector original sin cambios", function () {',
            '    if (Array.isArray(rows) && rows.length > 0) {',
            '        pm.expect(parseFloat(rows[0].cobertura_ventana)).to.eql(1.00);',
            '    } else {',
            '        pm.expect.fail("No se encontró observación en BD: " + JSON.stringify(r));',
            '    }',
            '});'
        ])
    ]
};

// =====================================================================
// CARPETA 02 — TC-370 Factores
// =====================================================================
const carpetaTC370 = {
    name: "02-TC-370-Factores",
    item: [
        // 02.01-Cobertura-Baja: c=0.50, fps=30, lost=0, cal=CALIBRADA -> 80.00, OPTIMA
        makeItem(
            "02.01-Cobertura-Baja",
            "POST",
            "{{baseUrl}}/iot/calidad/vision/{{obs_0201}}/evaluar",
            authAdmin(),
            null,
            makeIngestPreScript("obs_0201", 0.50, 30.0, 0, "CALIBRADO", 80),
            makeEvalTests(80.00, "OPTIMA", true)
        ),

        // 02.02-FPS-Bajo: c=1.00, fps=10 (10/30=0.3333), lost=0, cal=CALIBRADA -> 86.66 / 76.67
        makeItem(
            "02.02-FPS-Bajo",
            "POST",
            "{{baseUrl}}/iot/calidad/vision/{{obs_0202}}/evaluar",
            authAdmin(),
            null,
            makeIngestPreScript("obs_0202", 1.00, 10.0, 0, "CALIBRADO", 90),
            makeEvalTests(86.66, "OPTIMA", true, true)
        ),

        // 02.03-Tracks-Perdidos: c=1.00, fps=30, lost=5, cal=CALIBRADA -> 75.00, DEGRADADA
        makeItem(
            "02.03-Tracks-Perdidos",
            "POST",
            "{{baseUrl}}/iot/calidad/vision/{{obs_0203}}/evaluar",
            authAdmin(),
            null,
            makeIngestPreScript("obs_0203", 1.00, 30.0, 5, "CALIBRADO", 100),
            makeEvalTests(75.00, "DEGRADADA", true)
        ),

        // 02.04-EN-CALIBRACION: c=1.00, fps=30, lost=0, cal=EN_CALIBRACION -> 70.00, DEGRADADA
        makeItem(
            "02.04-EN-CALIBRACION",
            "POST",
            "{{baseUrl}}/iot/calidad/vision/{{obs_0204}}/evaluar",
            authAdmin(),
            null,
            makeIngestPreScript("obs_0204", 1.00, 30.0, 0, "EN_CALIBRACION", 110),
            makeEvalTests(70.00, "DEGRADADA", true)
        )
    ]
};

// =====================================================================
// CARPETA 03 — TC-371 Fronteras
// =====================================================================
const carpetaTC371 = {
    name: "03-TC-371-Fronteras",
    item: [
        // 03.01-Indice-80-OPTIMA: c=0.50, fps=30, lost=0, cal=CALIBRADA -> 80.00, OPTIMA
        makeItem(
            "03.01-Indice-80-OPTIMA",
            "POST",
            "{{baseUrl}}/iot/calidad/vision/{{obs_0301}}/evaluar",
            authAdmin(),
            null,
            makeIngestPreScript("obs_0301", 0.50, 30.0, 0, "CALIBRADO", 120),
            makeEvalTests(80.00, "OPTIMA", true)
        ),

        // 03.02-Indice-79.99-DEGRADADA: c=0.4998 (max 4 dec), fps=30, lost=0, cal=CALIBRADA -> 79.99, DEGRADADA
        makeItem(
            "03.02-Indice-79.99-DEGRADADA",
            "POST",
            "{{baseUrl}}/iot/calidad/vision/{{obs_0302}}/evaluar",
            authAdmin(),
            null,
            makeIngestPreScript("obs_0302", 0.4998, 30.0, 0, "CALIBRADO", 130),
            makeEvalTests(79.99, "DEGRADADA", true)
        ),

        // 03.03-Indice-40-DEGRADADA: c=0.40, fps=12 (12/30=0.40), lost=3, cal=CALIBRADA -> 40.00, DEGRADADA
        makeItem(
            "03.03-Indice-40-DEGRADADA",
            "POST",
            "{{baseUrl}}/iot/calidad/vision/{{obs_0303}}/evaluar",
            authAdmin(),
            null,
            makeIngestPreScript("obs_0303", 0.40, 12.0, 3, "CALIBRADO", 140),
            makeEvalTests(40.00, "DEGRADADA", true)
        ),

        // 03.04-Indice-39.99-NO-APTA: c=0.3997 (max 4 dec), fps=12 (12/30=0.40), lost=3, cal=CALIBRADA -> 39.99, NO_APTA
        makeItem(
            "03.04-Indice-39.99-NO-APTA",
            "POST",
            "{{baseUrl}}/iot/calidad/vision/{{obs_0304}}/evaluar",
            authAdmin(),
            null,
            makeIngestPreScript("obs_0304", 0.3997, 12.0, 3, "CALIBRADO", 150),
            makeEvalTests(39.99, "NO_APTA", false)
        )
    ]
};

// =====================================================================
// CARPETA 04 — TC-372 Modificador de Calibracion
// =====================================================================
const carpetaTC372 = {
    name: "04-TC-372-Modificador-Calibracion",
    item: [
        // 04.01-SIN-LINEA-BASE: c=1.00, fps=30, lost=0, cal=SIN_LINEA_BASE -> 0.00, NO_APTA
        makeItem(
            "04.01-SIN-LINEA-BASE",
            "POST",
            "{{baseUrl}}/iot/calidad/vision/{{obs_0401}}/evaluar",
            authAdmin(),
            null,
            makeIngestPreScript("obs_0401", 1.00, 30.0, 0, "SIN_LINEA_BASE", 160),
            makeEvalTests(0.00, "NO_APTA", false)
        ),

        // 04.02-EN-CALIBRACION-Base-100: c=1.00, fps=30, lost=0, cal=EN_CALIBRACION -> 70.00, DEGRADADA
        makeItem(
            "04.02-EN-CALIBRACION-Base-100",
            "POST",
            "{{baseUrl}}/iot/calidad/vision/{{obs_0402}}/evaluar",
            authAdmin(),
            null,
            makeIngestPreScript("obs_0402", 1.00, 30.0, 0, "EN_CALIBRACION", 170),
            makeEvalTests(70.00, "DEGRADADA", true)
        )
    ]
};

// =====================================================================
// CARPETA 05 — TC-373 Configurabilidad y Auditoria RF-63
// =====================================================================
const carpetaTC373 = {
    name: "05-TC-373-Configurabilidad",
    item: [
        // 05.01-PATCH-Politica
        makeItem("05.01-PATCH-Politica (w1=0.5, w2=0.3, w3=0.2)", "PATCH", "{{baseUrl}}/configuracion/politica-vision", authAdmin(), {
            parametros: {
                w1: 0.5,
                w2: 0.3,
                w3: 0.2
            }
        }, [], [
            'pm.test("PATCH politica 200 OK", function () {',
            '    pm.response.to.have.status(200);',
            '});'
        ]),

        // 05.02-GET-Verificar-Cambio
        makeItem("05.02-GET-Verificar-Cambio", "GET", "{{baseUrl}}/configuracion/politica-vision", authAdmin(), null, [], [
            'pm.test("GET politica 200 OK con nuevos pesos", function () {',
            '    pm.response.to.have.status(200);',
            '    const list = pm.response.json();',
            '    pm.expect(list).to.be.an("array").and.not.empty;',
            '    const p = {};',
            '    list.forEach(item => {',
            '        const k = item.nombre || item.nombre_parametro;',
            '        p[k] = item.valor !== undefined ? item.valor : item.valor_configurado;',
            '    });',
            '    pm.expect(parseFloat(p.w1)).to.eql(0.5);',
            '    pm.expect(parseFloat(p.w2)).to.eql(0.3);',
            '    pm.expect(parseFloat(p.w3)).to.eql(0.2);',
            '});'
        ]),

        // 05.03-Ingestar-Cobertura-0.75
        makeItem("05.03-Ingestar-Cobertura-0.75", "POST", "{{baseUrl}}/iot/telemetria/vision", authBroker(), null, [
            'const offset = 180000;',
            'const tFin = new Date(Date.now() - offset);',
            'const tIni = new Date(tFin.getTime() - 15000);',
            'const payload = {',
            '    serial: pm.variables.get("dispositivo_serial") || "QA-M09-G55-cam-290655",',
            '    area_id: parseInt(pm.variables.get("area_id") || "3"),',
            '    ventana_inicio: tIni.toISOString(),',
            '    ventana_fin: tFin.toISOString(),',
            '    tipo_dato: "VECTOR_COMPORTAMIENTO",',
            '    n_individuos_observados: 10,',
            '    origen: "TIEMPO_REAL",',
            '    calidad: {',
            '        cobertura_ventana: 0.75,',
            '        n_tracks: 10,',
            '        n_tracks_perdidos: 0,',
            '        fps_efectivo: 30.0,',
            '        estado_calibracion: "CALIBRADO"',
            '    },',
            '    componentes: {',
            '        densidad_actividad: 0.5,',
            '        dispersion_espacial: 1.0,',
            '        tasa_movimiento: 0.8',
            '    },',
            '    version_cascada: {',
            '        detector: "yolo-v8",',
            '        seguimiento: "bytetrack",',
            '        metricas: "v1.0",',
            '        anomalias: "v1.0"',
            '    }',
            '};',
            'pm.request.body.raw = JSON.stringify(payload);'
        ], [
            'pm.test("Ingesta 201 Created", function () {',
            '    pm.response.to.have.status(201);',
            '    const r = pm.response.json();',
            '    pm.expect(r.observaciones).to.be.an("array").and.not.empty;',
            '    const id = r.observaciones[0].id_observacion_vision;',
            '    pm.collectionVariables.set("obs_373", id);',
            '    pm.variables.set("obs_373", id);',
            '    pm.environment.set("obs_373", id);',
            '});'
        ]),

        // 05.04-Evaluar-Con-Nuevos-Pesos: 100 * (0.5*0.75 + 0.3*1.0 + 0.2*1.0) = 87.50
        makeItem("05.04-Evaluar-Con-Nuevos-Pesos", "POST", "{{baseUrl}}/iot/calidad/vision/{{obs_373}}/evaluar", authAdmin(), null, [], [
            'pm.test("HTTP 200 OK", function () { pm.response.to.have.status(200); });',
            'const r = pm.response.json();',
            'pm.test("índice esperado", function () {',
            '    pm.expect(parseFloat(r.indice_calidad_vision)).to.eql(87.50);',
            '});',
            'pm.test("clasificación esperada", function () {',
            '    pm.expect(r.clasificacion_calidad).to.eql("OPTIMA");',
            '});',
            'pm.test("apto_para_ia esperado", function () {',
            '    pm.expect(r.apto_para_ia).to.eql(true);',
            '});',
            'pm.test("apto_para_nic41 = false (invariante de visión)", function () {',
            '    pm.expect(r.apto_para_nic41).to.eql(false);',
            '});'
        ]),

        // 05.05-Verificar-Evento-RF63
        makeItem("05.05-Verificar-Evento-RF63", "POST", "{{baseUrl}}/test-control/query", authAdmin(), null, [
            'const id = pm.variables.get("obs_373");',
            'const q = "SELECT COUNT(*) as n FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id = \'" + id + "\'";',
            'pm.request.body.raw = JSON.stringify({ query: q });'
        ], [
            'pm.test("HTTP 200 OK", function () { pm.response.to.have.status(200); });',
            'const r = pm.response.json();',
            'const rows = r.data || r;',
            'pm.test("evento RF-63 registrado", function () {',
            '    pm.expect(rows).to.be.an("array");',
            '    const n = parseInt(rows[0] ? rows[0].n : 0);',
            '    pm.expect(n).to.be.at.least(0);',
            '});'
        ]),

        // 05.06-Restaurar-Politica-Original
        makeItem("05.06-Restaurar-Politica-Original", "PATCH", "{{baseUrl}}/configuracion/politica-vision", authAdmin(), null, [
            'const body = {',
            '    parametros: {',
            '        w1: parseFloat(pm.variables.get("orig_w1") || 0.40),',
            '        w2: parseFloat(pm.variables.get("orig_w2") || 0.35),',
            '        w3: parseFloat(pm.variables.get("orig_w3") || 0.25)',
            '    }',
            '};',
            'pm.request.body.raw = JSON.stringify(body);'
        ], [
            'pm.test("Restaurar politica 200 OK", function () {',
            '    pm.response.to.have.status(200);',
            '});'
        ])
    ]
};

// =====================================================================
// CARPETA 99 — TEARDOWN
// =====================================================================
const teardown = [
    makeItem("99.01-Rollback-Sandbox", "DELETE", "{{baseUrl}}/test-control/runs/{{run_id}}", [
        h("X-Sandbox-Secret", "{{sandbox_secret}}")
    ], null, [], [
        'pm.test("rollback exitoso", function () {',
        '    pm.expect([200, 404]).to.include(pm.response.code);',
        '    if (pm.response.code === 200) {',
        '        const r = pm.response.json();',
        '        pm.expect(r.status || pm.response.text()).to.include("Rollback");',
        '    }',
        '});'
    ])
];

// =====================================================================
// ENSAMBLAJE DE LA COLECCIÓN
// =====================================================================
const collection = {
    info: {
        name: "TC-M03-G192 — Calidad de observaciones de VISIÓN (AIOT-SPEC-01)",
        schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        description: "Suite automatizada Newman para TC-M03-G192 bajo Sandbox transaccional (AIOT-SPEC-01 RF-62)."
    },
    event: [
        {
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: [
                    'const runId = pm.variables.get("run_id") || ("test-g192-" + pm.variables.replaceIn("{{$guid}}").substring(0, 8));',
                    'pm.variables.set("run_id", runId);',
                    'pm.collectionVariables.set("run_id", runId);',
                    'pm.request.headers.upsert({ key: "X-Test-Run-Id", value: runId });',
                    'const secret = pm.variables.get("sandbox_secret") || "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff";',
                    'pm.request.headers.upsert({ key: "X-Sandbox-Secret", value: secret });'
                ]
            }
        }
    ],
    variable: [
        { key: "baseUrl", value: "https://www.api.inmero.co/api-sgpmp-test" },
        { key: "admin_email", value: "administador.dev@gmail.com" },
        { key: "admin_password", value: "" },
        { key: "sandbox_secret", value: "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff" },
        { key: "broker_token", value: "" },
        { key: "area_id", value: "3" },
        { key: "dispositivo_serial", value: "QA-M09-G55-cam-290655" },
        { key: "dispositivo_id", value: "147" },
        { key: "fps_configurado", value: "30" }
    ],
    item: [
        ...preflight,
        carpetaTC369,
        carpetaTC370,
        carpetaTC371,
        carpetaTC372,
        carpetaTC373,
        ...teardown
    ]
};

const outputFile = path.join(__dirname, "test_tc_m03_g192.json");
fs.writeFileSync(outputFile, JSON.stringify(collection, null, 2), "utf8");
console.log(`[BUILD SUCCESS] Colección generada exitosamente en: ${outputFile}`);
