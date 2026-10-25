const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G167
// RF-62 / RF-57 / RF-63: Detección de drift — fronteras de porcentaje
//
// CAMBIOS Y REGLAS DE ARQUITECTURA QA:
// 1. SANDBOX: Pre-request a nivel de colección genera run_id si está vacío e inyecta
//    X-Test-Run-Id y X-Sandbox-Secret en cada request.
// 2. LOGIN: POST /sesiones/ con correo_electronico y contrasena; token extraído de res.token.
// 3. COBERTURA: 7 escenarios (5%, 7%, 9.99%, 10.00%, 15%, 20.01%, 25%).
// 4. TIMEOUT / ESTRUCTURA: Modularizada en carpetas por escenario. 20 lecturas sembradas con
//    POST /iot/telemetria/batch (BUFFER_LOCAL) en 1 solo request por escenario; lectura 21 vía
//    POST /iot/telemetria individual.
// 5. SENSOR: Descubrimiento con verificación de que no tenga lecturas posteriores a las de la serie.
// 6. ASERCIONES: pm.expect(v).to.be.closeTo(exp, tol). Media_ultimas_N es la media de las 20 lecturas
//    previas (excluye lectura evaluada según telemetria_repository.py:124 timestamp_captura < ts).
// 7. RF-57: Escenario >20% consulta modulo3.alertas vía SELECT con prefijo [DEFECTO CONOCIDO RF-57].
// 8. TEARDOWN: DELETE /test-control/runs/{{run_id}} al final de la suite.

function makeHeader(key, value) {
    return { key, value };
}

function makeAuthHeaders() {
    return [
        makeHeader("Authorization", "Bearer {{token_admin}}")
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

    if (bodyObj !== null && method !== "GET") {
        item.request.body = {
            mode: "raw",
            raw: typeof bodyObj === "string" ? bodyObj : JSON.stringify(bodyObj, null, 2),
            options: { raw: { language: "json" } }
        };
        item.request.header.push(makeHeader("Content-Type", "application/json"));
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

// Helper para construir el batch payload de 20 lecturas para un escenario
function buildBatchPayload(prefixTime, baseVal, deltas) {
    // deltas: array de 5 deltas que se repite 4 veces = 20 lecturas
    const registros = [];
    let idx = 0;
    for (let rep = 0; rep < 4; rep++) {
        for (let d = 0; d < deltas.length; d++) {
            const minStr = String(idx * 2).padStart(2, '0');
            registros.push({
                device_id: parseInt("{{device_id}}", 10),
                sensor_id: parseInt("{{sensor_id}}", 10),
                tipo_variable: "TEMPERATURA_AMBIENTAL",
                valor: Number((baseVal + deltas[d]).toFixed(4)),
                unidad: "°C",
                timestamp_captura: `${prefixTime}:${minStr}:00Z`,
                access_key: "{{device_serial}}",
                origen: "BUFFER_LOCAL"
            });
            idx++;
        }
    }
    return { registros };
}

// Estructura de carpetas Postman
const folders = [];

// ── CARPETA 0: PREFLIGHT Y DESCUBRIMIENTO ──────────────────────────────────────
const folder0Items = [
    makeItem(
        "00-Preflight-Login-Admin",
        "POST",
        "{{baseUrl}}/sesiones/",
        [],
        {
            correo_electronico: "administador.dev@gmail.com",
            contrasena: "{{admin_password}}"
        },
        [],
        [
            'pm.test("Status 200 - Login exitoso en /sesiones/", function () {',
            '    pm.response.to.have.status(200);',
            '    const res = pm.response.json();',
            '    pm.expect(res.token).to.be.a("string").and.not.be.empty;',
            '    pm.collectionVariables.set("token_admin", res.token);',
            '});'
        ]
    ),
    makeItem(
        "01-Descubrimiento-Sensor-Ambiental",
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: "SELECT s.id_sensores, s.id_dispositivo_iot, d.serial, s.categoria FROM modulo9.sensores s JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot WHERE s.es_activo = true AND d.es_activo = true ORDER BY s.id_sensores ASC LIMIT 5"
        },
        [],
        [
            'pm.test("Status 200 - Sensor ambiental descubierto", function () {',
            '    pm.response.to.have.status(200);',
            '    const rows = pm.response.json().data || pm.response.json().rows || [];',
            '    pm.expect(rows.length).to.be.above(0);',
            '    const s = rows[0];',
            '    pm.collectionVariables.set("sensor_id", s.id_sensores);',
            '    pm.collectionVariables.set("device_id", s.id_dispositivo_iot);',
            '    pm.collectionVariables.set("device_serial", s.serial);',
            '});'
        ]
    ),
    makeItem(
        "02-Verificar-Sin-Lecturas-Posteriores",
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: "SELECT COUNT(*) AS total_posteriores FROM modulo3.telemetrias WHERE id_sensor = {{sensor_id}} AND timestamp_captura >= '2026-10-19T00:00:00Z'"
        },
        [],
        [
            'pm.test("Status 200 - Ventana temporal verificada sin lecturas intrusas", function () {',
            '    pm.response.to.have.status(200);',
            '    const rows = pm.response.json().data || pm.response.json().rows || [];',
            '    const count = parseInt((rows[0] && rows[0].total_posteriores) || 0, 10);',
            '    pm.expect(count).to.equal(0);',
            '});'
        ]
    )
];

folders.push({
    name: "00-Preflight-y-Descubrimiento",
    item: folder0Items
});

// Definición de los 7 escenarios de prueba
const deltasSimetricos = [-0.2, -0.1, 0.0, 0.1, 0.2];

const escenarios = [
    {
        num: "1A",
        name: "Escenario-1A-Drift-5.00pct-Inactivo",
        subcaso: "TC-M03-313",
        driftPct: 5.00,
        m: 21.000,
        offset: -1.000,
        esperado: 20.000,
        timePrefix: "2026-10-19T01",
        timeEvaluada: "2026-10-19T01:45:00Z",
        idVarName: "id_tel_eval_1a",
        activo: false,
        indice: 100,
        clasificacion: "APTO",
        aptoIA: true,
        aptoNIC41: true,
        descuento: 0,
        descr: "Drift 5.00% (<= 5.0% umbral) -> Inactivo, Descuento 0, Índice 100, APTO, NIC41=true"
    },
    {
        num: "1B",
        name: "Escenario-1B-Drift-7.00pct-Activo-Menor10",
        subcaso: "TC-M03-313",
        driftPct: 7.00,
        m: 21.400,
        offset: -1.400,
        esperado: 20.000,
        timePrefix: "2026-10-19T02",
        timeEvaluada: "2026-10-19T02:45:00Z",
        idVarName: "id_tel_eval_1b",
        activo: true,
        indice: 90,
        clasificacion: "APTO",
        aptoIA: true,
        aptoNIC41: true,
        descuento: 10,
        descr: "Drift 7.00% (>5.0% y <10%) -> Activo, Descuento -10, Índice 90, APTO, NIC41=true"
    },
    {
        num: "1C",
        name: "Escenario-1C-Drift-9.99pct-Frontera-Superior-Menor10",
        subcaso: "TC-M03-313",
        driftPct: 9.99,
        m: 21.998,
        offset: -1.998,
        esperado: 20.000,
        timePrefix: "2026-10-19T03",
        timeEvaluada: "2026-10-19T03:45:00Z",
        idVarName: "id_tel_eval_1c",
        activo: true,
        indice: 90,
        clasificacion: "APTO",
        aptoIA: true,
        aptoNIC41: true,
        descuento: 10,
        descr: "Drift 9.99% (Frontera <10%) -> Activo, Descuento -10, Índice 90, APTO, NIC41=true"
    },
    {
        num: "2A",
        name: "Escenario-2A-Drift-10.00pct-Frontera-Inferior-10a20",
        subcaso: "TC-M03-314",
        driftPct: 10.00,
        m: 22.000,
        offset: -2.000,
        esperado: 20.000,
        timePrefix: "2026-10-19T04",
        timeEvaluada: "2026-10-19T04:45:00Z",
        idVarName: "id_tel_eval_2a",
        activo: true,
        indice: 75,
        clasificacion: "APTO_CON_RESERVA",
        aptoIA: true,
        aptoNIC41: false,
        descuento: 25,
        descr: "Drift 10.00% (Frontera exacta 10-20%) -> Activo, Descuento -25, Índice 75, APTO_CON_RESERVA, NIC41=false"
    },
    {
        num: "2B",
        name: "Escenario-2B-Drift-15.00pct-Intermedio-10a20",
        subcaso: "TC-M03-314",
        driftPct: 15.00,
        m: 23.000,
        offset: -3.000,
        esperado: 20.000,
        timePrefix: "2026-10-19T05",
        timeEvaluada: "2026-10-19T05:45:00Z",
        idVarName: "id_tel_eval_2b",
        activo: true,
        indice: 75,
        clasificacion: "APTO_CON_RESERVA",
        aptoIA: true,
        aptoNIC41: false,
        descuento: 25,
        descr: "Drift 15.00% (10-20%) -> Activo, Descuento -25, Índice 75, APTO_CON_RESERVA, NIC41=false"
    },
    {
        num: "3A",
        name: "Escenario-3A-Drift-20.01pct-Frontera-Superior-Mayor20",
        subcaso: "TC-M03-315",
        driftPct: 20.01,
        m: 24.002,
        offset: -4.002,
        esperado: 20.000,
        timePrefix: "2026-10-19T06",
        timeEvaluada: "2026-10-19T06:45:00Z",
        idVarName: "id_tel_eval_3a",
        activo: true,
        indice: 60,
        clasificacion: "APTO_CON_RESERVA",
        aptoIA: true,
        aptoNIC41: false,
        descuento: 40,
        descr: "Drift 20.01% (Frontera >20%) -> Activo, Descuento -40, Índice 60, APTO_CON_RESERVA, NIC41=false"
    },
    {
        num: "3B",
        name: "Escenario-3B-Drift-25.00pct-Severo-Mayor20",
        subcaso: "TC-M03-315",
        driftPct: 25.00,
        m: 25.000,
        offset: -5.000,
        esperado: 20.000,
        timePrefix: "2026-10-19T07",
        timeEvaluada: "2026-10-19T07:45:00Z",
        idVarName: "id_tel_eval_3b",
        activo: true,
        indice: 60,
        clasificacion: "APTO_CON_RESERVA",
        aptoIA: true,
        aptoNIC41: false,
        descuento: 40,
        descr: "Drift 25.00% (>20%) -> Activo, Descuento -40, Índice 60, APTO_CON_RESERVA, NIC41=false"
    }
];

escenarios.forEach((esc, escIdx) => {
    const escFolderItems = [];

    // 1. Configurar calibración vía INSERT en modulo9.calibraciones
    escFolderItems.push(makeItem(
        `${esc.num}-01-Configurar-Calibracion`,
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: `INSERT INTO modulo9.calibraciones (id_dispositivo_iot, id_sensor, ganancia, offset_calibracion, fecha_calibracion, valor_referencia, id_usuario) VALUES ({{device_id}}, {{sensor_id}}, 1.0, ${esc.offset.toFixed(4)}, NOW() + INTERVAL '${escIdx + 1} second', 20.00, 1)`
        },
        [],
        [
            `pm.test("Status 200 - Calibración ${esc.driftPct}% configurada", function () {`,
            '    pm.response.to.have.status(200);',
            '});'
        ]
    ));

    // 2. Ingestar serie de 20 lecturas mediante 1 solo request batch
    const batchBody = buildBatchPayload(esc.timePrefix, esc.m, deltasSimetricos);
    escFolderItems.push(makeItem(
        `${esc.num}-02-Ingesta-Batch-Serie-20-Lecturas`,
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        [],
        batchBody,
        [],
        [
            'pm.test("Status 200 - Ingesta batch de 20 lecturas", function () {',
            '    pm.response.to.have.status(200);',
            '    const res = pm.response.json();',
            '    pm.expect(res.total).to.equal(20);',
            '    pm.expect(res.aceptados).to.equal(20);',
            '    pm.expect(res.rechazados).to.equal(0);',
            '});'
        ]
    ));

    // 3. Ingestar lectura 21 (evaluada) vía POST /iot/telemetria individual
    escFolderItems.push(makeItem(
        `${esc.num}-03-Ingesta-Lectura-Evaluada`,
        "POST",
        "{{baseUrl}}/iot/telemetria",
        [],
        {
            device_id: "{{device_id}}",
            sensor_id: "{{sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: Number(esc.m.toFixed(4)),
            unidad: "°C",
            timestamp_captura: esc.timeEvaluada,
            access_key: "{{device_serial}}",
            origen: "BUFFER_LOCAL"
        },
        [],
        [
            `pm.test("Status 201 - Ingesta lectura evaluada ${esc.num}", function () {`,
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    pm.expect(res.id_telemetria).to.be.a("number").and.above(0);',
            `    pm.collectionVariables.set("${esc.idVarName}", res.id_telemetria);`,
            '});'
        ]
    ));

    // 4. Evaluar calidad puntual POST /iot/calidad/{id}/evaluar
    const evalTests = [
        `pm.test("Status 201 - ${esc.descr}", function () {`,
        '    pm.response.to.have.status(201);',
        '    const res = pm.response.json();',
        '    const flags = res.flags_detectados || {};',
        '    const drift = flags.posible_drift || {};',
        `    const expActivo = ${esc.activo};`
    ];

    if (!esc.activo) {
        evalTests.push(
            '    pm.expect(drift.activo).to.be.oneOf([false, undefined]);',
            `    pm.expect(res.indice_calidad).to.equal(${esc.indice});`,
            `    pm.expect(res.clasificacion_calidad).to.equal("${esc.clasificacion}");`,
            `    pm.expect(res.apto_para_ia).to.equal(${esc.aptoIA});`,
            `    pm.expect(res.apto_para_nic41).to.equal(${esc.aptoNIC41});`,
            '    pm.expect(res.estado_evaluacion).to.equal("VIGENTE");'
        );
    } else {
        evalTests.push(
            '    pm.expect(drift.activo).to.equal(true);',
            `    pm.expect(drift.magnitud_drift_porcentaje).to.be.closeTo(${esc.driftPct.toFixed(4)}, 0.01);`,
            `    pm.expect(drift.media_ultimas_N).to.be.closeTo(${esc.m.toFixed(4)}, 0.05);`,
            `    pm.expect(drift.valor_calibrado_esperado).to.be.closeTo(${esc.esperado.toFixed(4)}, 0.05);`,
            '    pm.expect(drift.P_lecturas_consistentes).to.be.at.least(3);',
            `    pm.expect(res.indice_calidad).to.equal(${esc.indice});`,
            `    pm.expect(res.clasificacion_calidad).to.equal("${esc.clasificacion}");`,
            `    pm.expect(res.apto_para_ia).to.equal(${esc.aptoIA});`,
            `    pm.expect(res.apto_para_nic41).to.equal(${esc.aptoNIC41});`,
            '    pm.expect(res.estado_evaluacion).to.equal("VIGENTE");'
        );
    }
    evalTests.push('});');

    escFolderItems.push(makeItem(
        `${esc.num}-04-Disparar-Evaluacion-Calidad`,
        "POST",
        `{{baseUrl}}/iot/calidad/{{${esc.idVarName}}}/evaluar`,
        makeAuthHeaders(),
        null,
        [],
        evalTests
    ));

    // 5. Verificaciones transversales para escenarios > 20% (RF-57, Bitácora RF-63, Invariante VIGENTE D7)
    if (esc.num === "3A" || esc.num === "3B") {
        // RF-57: Alerta técnica exigida para documentar defecto Fase 8
        escFolderItems.push(makeItem(
            `${esc.num}-05-Verificar-Alerta-Tecnica-RF57`,
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: `SELECT id_alerta, tipo_alerta, severidad, estado_alerta, id_telemetria FROM modulo3.alertas WHERE id_telemetria = {{${esc.idVarName}}}`
            },
            [],
            [
                'pm.test("[DEFECTO CONOCIDO RF-57] Alerta técnica por drift severo emitida en modulo3.alertas", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    // NOTA NORMATIVA: En Fase 8 de EvaluarCalidadTelemetriaUseCase la llamada a RF-57 no está conectada.',
                '    // Este test exige la alerta para evidenciar el defecto conocido en Newman / Scanner.',
                '    pm.expect(rows.length, "Defecto conocido RF-57: EvaluarCalidadTelemetriaUseCase no genera alerta en modulo3.alertas").to.be.above(0);',
                '    if (rows.length > 0) {',
                '        pm.expect(rows[0].tipo_alerta).to.equal("TECNICA");',
                '    }',
                '});'
            ]
        ));

        // Bitácora RF-63
        escFolderItems.push(makeItem(
            `${esc.num}-06-Verificar-Bitacora-Auditoria-RF63`,
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: `SELECT tipo_evento, componente_origen, severidad_log FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id = '{{${esc.idVarName}}}' ORDER BY id_evento DESC LIMIT 1`
            },
            [],
            [
                'pm.test("Status 200 - Evento en bitácora RF-63 registrado", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.be.above(0);',
                '    pm.expect(rows[0].tipo_evento).to.equal("EVALUACION_CALIDAD_COMPLETADA");',
                '    pm.expect(rows[0].componente_origen).to.equal("RF-62");',
                '});'
            ]
        ));

        // Invariante D7: Máximo una evaluación VIGENTE por lectura
        escFolderItems.push(makeItem(
            `${esc.num}-07-Verificar-Invariante-VIGENTE-D7`,
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: `SELECT COUNT(*) AS total_vigentes FROM modulo3.telemetria_calidad WHERE id_telemetria = {{${esc.idVarName}}} AND estado_evaluacion = 'VIGENTE'`
            },
            [],
            [
                'pm.test("Invariante D7: Exactamente una evaluación VIGENTE para la lectura", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    const vigentes = parseInt((rows[0] && rows[0].total_vigentes) || 0, 10);',
                '    pm.expect(vigentes).to.equal(1);',
                '});'
            ]
        ));
    }

    folders.push({
        name: esc.name,
        item: escFolderItems
    });
});

// ── CARPETA 99: TEARDOWN Y ROLLBACK SANDBOX ───────────────────────────────────
folders.push({
    name: "99-Teardown-Rollback",
    item: [
        makeItem(
            "99-Teardown-Rollback-Sandbox",
            "DELETE",
            "{{baseUrl}}/test-control/runs/{{run_id}}",
            [],
            null,
            [],
            [
                'pm.test("Status 200 - Rollback exitoso", function () {',
                '    pm.response.to.have.status(200);',
                '    pm.expect(pm.response.text()).to.include("Rollback exitoso");',
                '});'
            ]
        )
    ]
});

// Construcción de la colección Postman v2.1.0 con Evento Pre-request a nivel de Colección
const collection = {
    info: {
        _postman_id: "tc-m03-g167-drift-fronteras-v2",
        name: "TC-M03-G167 - Deteccion de Drift Fronteras RF-62",
        description: "Suite automatizada Newman para TC-M03-G167 (RF-62 / RF-57 / RF-63). Cobertura completa de fronteras de drift (5%, 7%, 9.99%, 10.00%, 15%, 20.01%, 25%). Aislamiento transaccional vía Sandbox X-Test-Run-Id.",
        schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    event: [
        {
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: [
                    '// Pre-request a nivel de colección:',
                    '// 1. Garantiza existencia de run_id con prefijo "test-"',
                    'let currentRunId = pm.collectionVariables.get("run_id");',
                    'if (!currentRunId || currentRunId.trim() === "") {',
                    '    currentRunId = "test-" + pm.variables.replaceIn("{{$guid}}");',
                    '    pm.collectionVariables.set("run_id", currentRunId);',
                    '}',
                    '',
                    '// 2. Inyecta cabeceras de Sandbox obligatorias en cada request',
                    'const secret = pm.collectionVariables.get("sandbox_secret");',
                    'if (currentRunId) {',
                    '    pm.request.headers.upsert({ key: "X-Test-Run-Id", value: currentRunId });',
                    '}',
                    'if (secret) {',
                    '    pm.request.headers.upsert({ key: "X-Sandbox-Secret", value: secret });',
                    '}'
                ]
            }
        }
    ],
    variable: [
        { key: "baseUrl", value: "https://api.inmero.co/back-sigab-test" },
        { key: "run_id", value: "" },
        { key: "sandbox_secret", value: "" },
        { key: "admin_password", value: "" },
        { key: "token_admin", value: "" },
        { key: "sensor_id", value: "" },
        { key: "device_id", value: "" },
        { key: "device_serial", value: "" },
        { key: "id_tel_eval_1a", value: "" },
        { key: "id_tel_eval_1b", value: "" },
        { key: "id_tel_eval_1c", value: "" },
        { key: "id_tel_eval_2a", value: "" },
        { key: "id_tel_eval_2b", value: "" },
        { key: "id_tel_eval_3a", value: "" },
        { key: "id_tel_eval_3b", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g167.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

// Conteo total de items
let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
