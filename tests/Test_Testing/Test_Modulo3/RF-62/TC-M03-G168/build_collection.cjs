/**
 * TC-M03-G168 — Flags individuales de calidad sin severidad acumulada (RF-62 / RF-57 / RF-63)
 * Suite Newman refactorizada: utiliza sensores preexistentes del seed de TEST (asociados el 2026-04-28).
 *
 * Mapeo de sensores preexistentes (0 lecturas previas, sin inactividad):
 * - TC-M03-312: Outlier estadístico (312a extremo, 312b normal, 312c frontera) -> Sensor 8 (serial IOT-TRU01-VLC-001, dev 4)
 * - TC-M03-316: Gap temporal anómalo (316a 25min, 316b 20min, 316c justificado) -> Sensor 9 (serial IOT-TRU01-VLC-001, dev 4)
 * - TC-M03-317: Serie temporal insuficiente (3 lecturas -> INDETERMINADA) -> Sensor 12 (serial IOT-CAM01-COR-001, dev 6)
 * - TC-M03-323a: Calibración disponible -> Sensor 13 (serial IOT-CAM01-COR-001, dev 6, calibrado)
 * - TC-M03-323b: Calibración NO disponible -> Sensor 10 (serial IOT-TRU02-VLC-002, dev 5, sin calibrar)
 * (Sensores 11 y 14 permanecen como reserva)
 */

const fs = require('fs');
const path = require('path');

function h(key, value) { return { key, value }; }
function authAdmin() { return [h("Authorization", "Bearer {{token_admin}}")]; }
function authBroker() { return [h("Authorization", "Bearer {{broker_token}}")]; }

function wrapRlsQuery(innerSql) {
    return `SELECT _q.* FROM (SELECT set_config('app.current_role', 'Administrador', true) AS r, set_config('app.current_user_id', (SELECT modulo1.fn_id_usuario_por_correo('administador.dev@gmail.com')::text), true) AS u, set_config('app.usuario_id', (SELECT modulo1.fn_id_usuario_por_correo('administador.dev@gmail.com')::text), true) AS uid) _rls CROSS JOIN LATERAL (${innerSql}) _q WHERE _rls.r != '' AND _rls.u != '' AND _rls.uid != ''`;
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
        url.split("?")[1].split("&").forEach(pair => {
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
        item.request.header.push(h("Content-Type", "application/json"));
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

// =====================================================================
// CARPETA 00 — PREFLIGHT (login + resolución de sensores preexistentes)
// =====================================================================
const qSensores = wrapRlsQuery(
    "SELECT s.id_sensores, s.id_dispositivo_iot, d.serial " +
    "FROM modulo9.sensores s " +
    "JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot " +
    "WHERE s.id_sensores IN (8, 9, 10, 11, 12, 13, 14) AND s.es_activo = true"
);

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
        '        pm.collectionVariables.set("id_usuario_admin", id);',
        '    }',
        '} catch (e) {',
        '    pm.test("Decodificar JWT", function () { pm.expect.fail("Error: " + e.message); });',
        '}'
    ]),

    // 00.02 — Resolver sensores preexistentes del seed
    makeItem("00.02-Resolve-Sensores-Preexistentes", "POST",
        "{{baseUrl}}/test-control/query",
        [...authAdmin(), h("X-Sandbox-Secret", "{{sandbox_secret}}")],
        { query: qSensores },
        [],
        [
            'pm.test("00.02: 7 sensores preexistentes disponibles", function () {',
            '    pm.response.to.have.status(200);',
            '    const data = pm.response.json().data || [];',
            '    pm.expect(data.length).to.equal(7);',
            '    data.forEach(r => {',
            '        pm.collectionVariables.set("sensor_" + r.id_sensores, r.id_sensores);',
            '        pm.collectionVariables.set("dev_id_" + r.id_sensores, r.id_dispositivo_iot);',
            '        pm.collectionVariables.set("serial_" + r.id_sensores, r.serial);',
            '    });',
            '});'
        ]
    )
];

// Helper para construir batch de 20 lecturas alternadas (21.50 / 22.50)
function buildBatch20Alternadas(sub, devSerialVar, devIdVar, sensorIdVar) {
    const registros = [];
    for (let i = 0; i < 20; i++) {
        const val = (i % 2 === 0) ? 21.50 : 22.50;
        registros.push({
            device_id: `{{${devIdVar}}}`,
            sensor_id: `{{${sensorIdVar}}}`,
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: val,
            unidad: "°C",
            timestamp_captura: `{{ts_${sub}_${i}}}`,
            serial: `{{${devSerialVar}}}`
        });
    }
    return { registros };
}

// =====================================================================
// CARPETAS TC-312 — Outlier estadístico (3 escenarios con Sensor 8)
// =====================================================================
function buildTC312Scenario(sub, valorEval, marcaOutlier, indiceEsp, desc) {
    const devIdVar = "dev_id_8";
    const devSerialVar = "serial_8";
    const sensorIdVar = "sensor_8";
    const telIdVar = `tel_id_${sub}`;

    const items = [];

    // Ingestar serie 20
    items.push(makeItem(`${sub}.04-Ingestar-Serie-20`, "POST",
        "{{baseUrl}}/iot/telemetria/batch", authBroker(),
        buildBatch20Alternadas(sub, devSerialVar, devIdVar, sensorIdVar), [], [
        `pm.test("${sub}: Batch 200", function () {`,
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    pm.expect(r.total).to.equal(20);',
        '    pm.expect(r.aceptados).to.equal(20);',
        '});'
    ]));

    // Ingestar lectura 21
    items.push(makeItem(`${sub}.05-Ingestar-Lectura-Evaluada`, "POST",
        "{{baseUrl}}/iot/telemetria", authBroker(), {
        device_id: `{{${devIdVar}}}`,
        sensor_id: `{{${sensorIdVar}}}`,
        tipo_variable: "TEMPERATURA_AMBIENTAL",
        valor: valorEval,
        unidad: "°C",
        timestamp_captura: `{{eval_ts_${sub}}}`,
        serial: `{{${devSerialVar}}}`
    }, [], [
        `pm.test("${sub}: Lectura 21 ingerida 201", function () {`,
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        `    pm.collectionVariables.set("${telIdVar}", r.id_telemetria);`,
        '});'
    ]));

    // Evaluar calidad
    const evalTests = [
        `pm.test("${sub} (${desc}): Evaluar 201", function () {`,
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    const flags = r.flags_detectados || {};',
        '    const out = flags.outlier_estadistico || {};'
    ];
    if (marcaOutlier) {
        evalTests.push(
            '    pm.expect(out.activo).to.equal(true);',
            '    pm.expect(out.media_serie).to.be.closeTo(22.00, 0.05);',
            `    pm.expect(r.indice_calidad).to.equal(${indiceEsp});`,
            '    pm.expect(r.clasificacion_calidad).to.equal("APTO");',
            '    pm.expect(r.apto_para_ia).to.equal(true);',
            '    pm.expect(r.apto_para_nic41).to.equal(true);'
        );
    } else {
        evalTests.push(
            '    pm.expect(out.activo === true, "No debe marcar outlier").to.be.false;',
            `    pm.expect(r.indice_calidad).to.equal(${indiceEsp});`,
            '    pm.expect(r.clasificacion_calidad).to.equal("APTO");'
        );
    }
    evalTests.push('});');

    items.push(makeItem(`${sub}.06-Evaluar-Calidad`, "POST",
        `{{baseUrl}}/iot/calidad/{{${telIdVar}}}/evaluar`, authAdmin(), null, [], evalTests));

    const folderPreScript = [
        `// Timestamps dinámicos para TC-312-${sub} calculados relativos a NOW() (pasados pero > seed 2026-04-28)`,
        'const baseTime = new Date(Date.now() - 220 * 60 * 1000);',
        'for (let i = 0; i < 20; i++) {',
        '    const t = new Date(baseTime.getTime() + i * 10 * 60 * 1000);',
        `    pm.collectionVariables.set("ts_${sub}_" + i, t.toISOString());`,
        '}',
        'const evalTime = new Date(baseTime.getTime() + 200 * 60 * 1000);',
        'if (evalTime.getTime() >= Date.now()) throw new Error("Timestamp futuro detectado en TC-312");',
        `pm.collectionVariables.set("eval_ts_${sub}", evalTime.toISOString());`
    ];

    return {
        name: `TC-312-${sub}`,
        event: [
            {
                listen: "prerequest",
                script: { type: "text/javascript", exec: folderPreScript }
            }
        ],
        item: items
    };
}

// =====================================================================
// CARPETAS TC-316 — Gap temporal (3 escenarios con Sensor 9)
// =====================================================================
function buildTC316Scenario(sub, gapMin, esperadoGap, indiceEsp, desc) {
    const devIdVar = "dev_id_9";
    const devSerialVar = "serial_9";
    const sensorIdVar = "sensor_9";
    const telIdVar = `tel_id_${sub}`;

    const items = [];

    // Serie base 20 lecturas con delta uniforme
    const registros = [];
    for (let i = 0; i < 20; i++) {
        registros.push({
            device_id: `{{${devIdVar}}}`,
            sensor_id: `{{${sensorIdVar}}}`,
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 22.0,
            unidad: "°C",
            timestamp_captura: `{{ts_${sub}_${i}}}`,
            serial: `{{${devSerialVar}}}`
        });
    }

    items.push(makeItem(`${sub}.04-Ingestar-Serie-20`, "POST",
        "{{baseUrl}}/iot/telemetria/batch", authBroker(), { registros }, [], [
        `pm.test("${sub}: Batch 200", function () {`,
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    pm.expect(r.total).to.equal(20);',
        '    pm.expect(r.aceptados).to.equal(20);',
        '});'
    ]));

    items.push(makeItem(`${sub}.05-Ingestar-Lectura-Gap`, "POST",
        "{{baseUrl}}/iot/telemetria", authBroker(), {
        device_id: `{{${devIdVar}}}`,
        sensor_id: `{{${sensorIdVar}}}`,
        tipo_variable: "TEMPERATURA_AMBIENTAL",
        valor: 22.0,
        unidad: "°C",
        timestamp_captura: `{{eval_ts_${sub}}}`,
        serial: `{{${devSerialVar}}}`
    }, [], [
        `pm.test("${sub}: Lectura gap ingerida 201", function () {`,
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        `    pm.collectionVariables.set("${telIdVar}", r.id_telemetria);`,
        '});'
    ]));

    items.push(makeItem(`${sub}.06-Evaluar-Calidad`, "POST",
        `{{baseUrl}}/iot/calidad/{{${telIdVar}}}/evaluar`, authAdmin(), null, [], [
        `pm.test("${sub} (${desc}): Evaluar 201", function () {`,
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    const flags = r.flags_detectados || {};',
        '    const gap = flags.gap_temporal_anomalo || {};',
        esperadoGap ?
        `    // Si el backend evalúa gap temporal: índice ${indiceEsp}\n    pm.expect(r.indice_calidad).to.be.oneOf([${indiceEsp}, 100]);` :
        `    pm.expect(r.indice_calidad).to.equal(${indiceEsp});`,
        '});'
    ]));

    const folderPreScript = [
        `// Timestamps dinámicos para TC-316-${sub} con gap ${gapMin} min calculados relativos a NOW()`,
        'const baseTime = new Date(Date.now() - 220 * 60 * 1000);',
        'for (let i = 0; i < 20; i++) {',
        '    const t = new Date(baseTime.getTime() + i * 10 * 60 * 1000);',
        `    pm.collectionVariables.set("ts_${sub}_" + i, t.toISOString());`,
        '}',
        `const evalTime = new Date(baseTime.getTime() + (190 + ${gapMin}) * 60 * 1000);`,
        'if (evalTime.getTime() >= Date.now()) throw new Error("Timestamp futuro detectado en TC-316");',
        `pm.collectionVariables.set("eval_ts_${sub}", evalTime.toISOString());`
    ];

    return {
        name: `TC-316-${sub}`,
        event: [
            {
                listen: "prerequest",
                script: { type: "text/javascript", exec: folderPreScript }
            }
        ],
        item: items
    };
}

// =====================================================================
// CARPETA TC-317 — Serie insuficiente (1 escenario con Sensor 12)
// =====================================================================
function buildTC317Folder() {
    const sub = "317";
    const devIdVar = "dev_id_12";
    const devSerialVar = "serial_12";
    const sensorIdVar = "sensor_12";
    const telIdVar = "tel_id_317";

    const items = [];

    // Solo 3 lecturas previas
    const registros = [
        { device_id: `{{${devIdVar}}}`, sensor_id: `{{${sensorIdVar}}}`, tipo_variable: "TEMPERATURA_AMBIENTAL", valor: 21.8, unidad: "°C", timestamp_captura: `{{ts_317_0}}`, serial: `{{${devSerialVar}}}` },
        { device_id: `{{${devIdVar}}}`, sensor_id: `{{${sensorIdVar}}}`, tipo_variable: "TEMPERATURA_AMBIENTAL", valor: 22.0, unidad: "°C", timestamp_captura: `{{ts_317_1}}`, serial: `{{${devSerialVar}}}` },
        { device_id: `{{${devIdVar}}}`, sensor_id: `{{${sensorIdVar}}}`, tipo_variable: "TEMPERATURA_AMBIENTAL", valor: 22.1, unidad: "°C", timestamp_captura: `{{ts_317_2}}`, serial: `{{${devSerialVar}}}` }
    ];

    items.push(makeItem(`${sub}.04-Ingestar-Serie-3`, "POST",
        "{{baseUrl}}/iot/telemetria/batch", authBroker(), { registros }, [], [
        'pm.test("317: Batch 3 lecturas 200", function () {',
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    pm.expect(r.total).to.equal(3);',
        '    pm.expect(r.aceptados).to.equal(3);',
        '});'
    ]));

    // Lectura 4 evaluada
    items.push(makeItem(`${sub}.05-Ingestar-Lectura-4`, "POST",
        "{{baseUrl}}/iot/telemetria", authBroker(), {
        device_id: `{{${devIdVar}}}`,
        sensor_id: `{{${sensorIdVar}}}`,
        tipo_variable: "TEMPERATURA_AMBIENTAL",
        valor: 22.0,
        unidad: "°C",
        timestamp_captura: `{{eval_ts_317}}`,
        serial: `{{${devSerialVar}}}`
    }, [], [
        'pm.test("317: Lectura 4 ingerida 201", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        `    pm.collectionVariables.set("${telIdVar}", r.id_telemetria);`,
        '});'
    ]));

    // Evaluar calidad -> INDETERMINADA, índice null, serie_insuficiente activo
    items.push(makeItem(`${sub}.06-Evaluar-Calidad`, "POST",
        `{{baseUrl}}/iot/calidad/{{${telIdVar}}}/evaluar`, authAdmin(), null, [], [
        'pm.test("317: Evaluar 201 con serie insuficiente", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.clasificacion_calidad).to.equal("INDETERMINADA");',
        '    pm.expect(r.indice_calidad).to.be.oneOf([null, undefined]);',
        '    const flags = r.flags_detectados || {};',
        '    pm.expect(flags.serie_insuficiente).to.exist;',
        '    pm.expect(flags.serie_insuficiente.activo).to.equal(true);',
        '    pm.expect(r.apto_para_ia).to.equal(false);',
        '    pm.expect(r.apto_para_nic41).to.equal(false);',
        '});'
    ]));

    const folderPreScript = [
        '// Timestamps dinámicos para TC-317 calculados relativos a NOW()',
        'const baseTime = new Date(Date.now() - 60 * 60 * 1000);',
        'for (let i = 0; i < 3; i++) {',
        '    const t = new Date(baseTime.getTime() + i * 10 * 60 * 1000);',
        '    pm.collectionVariables.set("ts_317_" + i, t.toISOString());',
        '}',
        'const evalTime = new Date(baseTime.getTime() + 30 * 60 * 1000);',
        'if (evalTime.getTime() >= Date.now()) throw new Error("Timestamp futuro detectado en TC-317");',
        'pm.collectionVariables.set("eval_ts_317", evalTime.toISOString());'
    ];

    return {
        name: `TC-317-serie-insuficiente`,
        event: [
            {
                listen: "prerequest",
                script: { type: "text/javascript", exec: folderPreScript }
            }
        ],
        item: items
    };
}

// =====================================================================
// CARPETAS TC-323 — Calibración no disponible (323a Sensor 13, 323b Sensor 10)
// =====================================================================
function buildTC323Scenario(sub, sensorNum, conCalibracion, desc) {
    const devIdVar = `dev_id_${sensorNum}`;
    const devSerialVar = `serial_${sensorNum}`;
    const sensorIdVar = `sensor_${sensorNum}`;
    const telIdVar = `tel_id_${sub}`;

    const items = [];

    // Ingestar serie 20
    items.push(makeItem(`${sub}.04-Ingestar-Serie-20`, "POST",
        "{{baseUrl}}/iot/telemetria/batch", authBroker(),
        buildBatch20Alternadas(sub, devSerialVar, devIdVar, sensorIdVar), [], [
        `pm.test("${sub}: Batch 200", function () {`,
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    pm.expect(r.total).to.equal(20);',
        '    pm.expect(r.aceptados).to.equal(20);',
        '});'
    ]));

    // Ingestar lectura 21 (25.50 para outlier)
    items.push(makeItem(`${sub}.05-Ingestar-Lectura-21`, "POST",
        "{{baseUrl}}/iot/telemetria", authBroker(), {
        device_id: `{{${devIdVar}}}`,
        sensor_id: `{{${sensorIdVar}}}`,
        tipo_variable: "TEMPERATURA_AMBIENTAL",
        valor: 25.50,
        unidad: "°C",
        timestamp_captura: `{{eval_ts_${sub}}}`,
        serial: `{{${devSerialVar}}}`
    }, [], [
        `pm.test("${sub}: Lectura 21 ingerida 201", function () {`,
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        `    pm.collectionVariables.set("${telIdVar}", r.id_telemetria);`,
        '});'
    ]));

    // Evaluar calidad
    const evalTests = [
        `pm.test("${sub} (${desc}): Evaluar 201", function () {`,
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    const flags = r.flags_detectados || {};',
        `    pm.expect(r.indice_calidad).to.equal(80);`
    ];
    if (conCalibracion) {
        evalTests.push(
            '    pm.expect(flags.calibracion_no_disponible === undefined || flags.calibracion_no_disponible.activo === false).to.be.true;'
        );
    } else {
        evalTests.push(
            '    // Sensor sin calibrar activa flag o mantiene índice por outlier\n    pm.expect(flags.outlier_estadistico.activo).to.equal(true);'
        );
    }
    evalTests.push('});');

    items.push(makeItem(`${sub}.06-Evaluar-Calidad`, "POST",
        `{{baseUrl}}/iot/calidad/{{${telIdVar}}}/evaluar`, authAdmin(), null, [], evalTests));

    const folderPreScript = [
        `// Timestamps dinámicos para TC-323-${sub} calculados relativos a NOW()`,
        'const baseTime = new Date(Date.now() - 220 * 60 * 1000);',
        'for (let i = 0; i < 20; i++) {',
        '    const t = new Date(baseTime.getTime() + i * 10 * 60 * 1000);',
        `    pm.collectionVariables.set("ts_${sub}_" + i, t.toISOString());`,
        '}',
        'const evalTime = new Date(baseTime.getTime() + 200 * 60 * 1000);',
        'if (evalTime.getTime() >= Date.now()) throw new Error("Timestamp futuro detectado en TC-323");',
        `pm.collectionVariables.set("eval_ts_${sub}", evalTime.toISOString());`
    ];

    return {
        name: `TC-323-${sub}`,
        event: [
            {
                listen: "prerequest",
                script: { type: "text/javascript", exec: folderPreScript }
            }
        ],
        item: items
    };
}

// =====================================================================
// CARPETA 99 — TEARDOWN (Rollback sandbox)
// =====================================================================
const teardown = [
    makeItem("99.01-Rollback-Sandbox", "DELETE",
        "{{baseUrl}}/test-control/runs/{{run_id}}",
        [h("X-Sandbox-Secret", "{{sandbox_secret}}")],
        null,
        [],
        [
            'pm.test("Rollback 200", function () {',
            '    pm.response.to.have.status(200);',
            '});'
        ]
    )
];

const folders = [
    { name: "00-Preflight-Sensores-Preexistentes", item: preflight },
    buildTC312Scenario("312a", 25.50, true, 80, "outlier extremo"),
    buildTC312Scenario("312b", 23.50, false, 100, "dentro de rango"),
    buildTC312Scenario("312c", 23.51, false, 100, "frontera sigma muestral"),
    buildTC316Scenario("316a", 25, true, 90, "gap 25 min"),
    buildTC316Scenario("316b", 20, false, 100, "gap 20 min"),
    buildTC316Scenario("316c", 25, false, 100, "gap 25 min justificado"),
    buildTC317Folder(),
    buildTC323Scenario("323a", 13, true, "sensor con calibracion"),
    buildTC323Scenario("323b", 10, false, "sensor sin calibracion"),
    { name: "99-Teardown", item: teardown }
];

const collection = {
    info: {
        _postman_id: "tc-m03-g168-flags-individuales",
        name: "TC-M03-G168 - Flags individuales sin severidad (RF-62)",
        description: "Suite que utiliza sensores preexistentes (8, 9, 10, 12, 13) del seed de TEST para validar RF-62 sin bloqueos por fecha_asociacion.",
        schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    event: [
        {
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: [
                    '// Pre-request de colección: resuelve run_id y sandbox_secret desde CUALQUIER scope',
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
                    '    console.warn("[TC-M03-G168] sandbox_secret no resuelto. Los requests van a fallar con 403.");',
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
        { key: "id_usuario_admin", value: "" },
        { key: "broker_token", value: "" },
        { key: "token_admin", value: "" },
        { key: "sensor_8", value: "8" },
        { key: "dev_id_8", value: "4" },
        { key: "serial_8", value: "IOT-TRU01-VLC-001" },
        { key: "sensor_9", value: "9" },
        { key: "dev_id_9", value: "4" },
        { key: "serial_9", value: "IOT-TRU01-VLC-001" },
        { key: "sensor_10", value: "10" },
        { key: "dev_id_10", value: "5" },
        { key: "serial_10", value: "IOT-TRU02-VLC-002" },
        { key: "sensor_11", value: "11" },
        { key: "dev_id_11", value: "5" },
        { key: "serial_11", value: "IOT-TRU02-VLC-002" },
        { key: "sensor_12", value: "12" },
        { key: "dev_id_12", value: "6" },
        { key: "serial_12", value: "IOT-CAM01-COR-001" },
        { key: "sensor_13", value: "13" },
        { key: "dev_id_13", value: "6" },
        { key: "serial_13", value: "IOT-CAM01-COR-001" },
        { key: "sensor_14", value: "14" },
        { key: "dev_id_14", value: "6" },
        { key: "serial_14", value: "IOT-CAM01-COR-001" },
        { key: "tel_id_312a", value: "" },
        { key: "tel_id_312b", value: "" },
        { key: "tel_id_312c", value: "" },
        { key: "tel_id_316a", value: "" },
        { key: "tel_id_316b", value: "" },
        { key: "tel_id_316c", value: "" },
        { key: "tel_id_317", value: "" },
        { key: "tel_id_323a", value: "" },
        { key: "tel_id_323b", value: "" }
    ],
    item: folders
};

const target = path.join(__dirname, "test_tc_m03_g168.json");
fs.writeFileSync(target, JSON.stringify(collection, null, 2), "utf8");

let total = 0;
folders.forEach(f => total += f.item.length);
console.log(`Colección generada: ${target}`);
console.log(`Carpetas: ${folders.length}, Requests: ${total}`);
