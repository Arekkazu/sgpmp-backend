/**
 * TC-M03-G167 — Detección de drift (RF-62 / RF-57 / RF-63)
 * Suite Newman con Sensor Pre-existente 536 (Fase 3: Sin aprovisionamiento en caliente).
 *
 * Configuración:
 * - Sensor: 536 (QA-SEMILLA-ADM-M03-CAL-01), Dispositivo: 346, Área: 347
 * - Calibración fija en BD: offset = -3.0000, ganancia = 1.0000, valor_referencia = 25.0000
 * - fecha_asociacion: 2026-10-11T22:38:44Z (< 2026-10-19)
 * - fecha_calibracion: 2026-10-16T22:38:44Z (< 2026-10-19)
 * - N_LECTURAS: 22 (N=20 + 2 extras simétricos)
 * - media_ultimas_N: semántica calibrada = mean(calibrados) = Xbar * 1.0 + (-3.0) = Xbar - 3.0
 * - valor_calibrado_esperado: 25.0 (referencia de calibración vigente al timestamp_captura)
 */

const fs = require('fs');
const path = require('path');

function h(key, value) { return { key, value }; }
function authAdmin() { return [h("Authorization", "Bearer {{token_admin}}")]; }
function authBroker() { return [h("Authorization", "Bearer {{broker_token}}")]; }

function wrapRlsQuery(innerSql) {
    return `SELECT _q.* FROM (SELECT set_config('app.current_role', 'Administrador', true) AS r, set_config('app.current_user_id', (SELECT modulo1.fn_id_usuario_por_correo('administador.dev@gmail.com')::text), true) AS u) _rls CROSS JOIN LATERAL (${innerSql}) _q WHERE _rls.r != '' AND _rls.u != ''`;
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
// CONSTANTES DE FIXTURE PRE-EXISTENTE (Sensor QA 536)
// =====================================================================
const SENSOR_ID = 536;
const DISPOSITIVO_ID = 346;
const AREA_ID = 347;
const DEVICE_SERIAL = "QA-SEMILLA-ADM-M03-CAL-01";
const CAL_OFFSET = -3.0;
const CAL_GANANCIA = 1.0;
const CAL_VALOR_REF = 25.0;
const N_LECTURAS = 22;

// =====================================================================
// ESCENARIOS (7) — Variación de Xbar (media cruda)
// =====================================================================
// NOTA (2026-11-02, post-Reintento 2 / DIAGNOSTICO_REINTENTO2.md G2):
// Los escenarios 3A y 3B usan drift NEGATIVO a propósito.
// Límite biológico del área 347 = 30.0°C (modulo9.umbrales_ambientales).
// Con sensor 536 (offset=-3, ref=25), un drift positivo ≥ 20% produce
// valor_ajustado = 25 × 1.20 = 30.0°C → FUERA_DE_RANGO → CA-9 omite drift.
// Con drift negativo (calibrado < ref), el valor se mantiene bajo el límite.
// RF-62 usa valor absoluto → el drift detectado es idéntico.
const escenarios = [
    { num: "1A", subcaso: "TC-M03-313", drift: 5.00, Xbar: 29.2500, varName: "id_tel_1a", activo: false, indice: 100, clas: "APTO", ia: true, nic41: true, alerta_rf57: null, desc: "5.00% borde estricto — sin flag" },
    { num: "1B", subcaso: "TC-M03-313", drift: 7.00, Xbar: 29.7500, varName: "id_tel_1b", activo: true, indice: 90, clas: "APTO", ia: true, nic41: true, alerta_rf57: "registrar", desc: "7.00% <10%" },
    { num: "1C", subcaso: "TC-M03-313", drift: 9.99, Xbar: 30.4975, varName: "id_tel_1c", activo: true, indice: 90, clas: "APTO", ia: true, nic41: true, alerta_rf57: "registrar", desc: "9.99% frontera <10%" },
    { num: "2A", subcaso: "TC-M03-314", drift: 10.00, Xbar: 30.5000, varName: "id_tel_2a", activo: true, indice: 75, clas: "APTO_CON_RESERVA", ia: true, nic41: false, alerta_rf57: "registrar", desc: "10.00% frontera 10–20%" },
    { num: "2B", subcaso: "TC-M03-314", drift: 15.00, Xbar: 31.7500, varName: "id_tel_2b", activo: true, indice: 75, clas: "APTO_CON_RESERVA", ia: true, nic41: false, alerta_rf57: "registrar", desc: "15.00% tramo 10–20%" },
    // Drift NEGATIVO para no exceder el límite biológico 30.00°C (modulo9.umbrales_ambientales, área 347)
    // calibrado_obj = 25.0 × (1 − d/100); X̄ = calibrado_obj + 3.0
    { num: "3A", subcaso: "TC-M03-315", drift: 20.01, Xbar: 22.9975, varName: "id_tel_3a", activo: true, indice: 60, clas: "APTO_CON_RESERVA", ia: true, nic41: false, alerta_rf57: "verificar", desc: "20.01% frontera >20% (drift negativo por límite biológico)" },
    { num: "3B", subcaso: "TC-M03-315", drift: 25.00, Xbar: 21.7500, varName: "id_tel_3b", activo: true, indice: 60, clas: "APTO_CON_RESERVA", ia: true, nic41: false, alerta_rf57: "verificar", desc: "25.00% tramo >20% (drift negativo por límite biológico)" }
];

// Patrón simétrico N=22: 2 extras neutros (0.0) al inicio + 4 ciclos completos de [-0.2, -0.1, 0.0, 0.1, 0.2]
const deltas22 = [
    0.0, 0.0,
    -0.2, -0.1, 0.0, 0.1, 0.2,
    -0.2, -0.1, 0.0, 0.1, 0.2,
    -0.2, -0.1, 0.0, 0.1, 0.2,
    -0.2, -0.1, 0.0, 0.1, 0.2
];

// Verificación obligatoria de simetría en build
const sumaDeltas = deltas22.reduce((a, b) => a + b, 0);
if (Math.abs(sumaDeltas) > 1e-9) {
    throw new Error(`Patrón de deltas no simétrico: suma=${sumaDeltas}`);
}
escenarios.forEach(esc => {
    const lecturas = deltas22.map(d => esc.Xbar + d);
    const media = lecturas.reduce((a, b) => a + b, 0) / lecturas.length;
    if (Math.abs(media - esc.Xbar) > 1e-6) {
        throw new Error(`Escenario ${esc.num}: mean(${media}) ≠ Xbar(${esc.Xbar})`);
    }
});

// Aserción de build (defensiva): validar límite biológico de área 347 (30.00°C)
escenarios.forEach(esc => {
    const calibrado = esc.Xbar + CAL_OFFSET;  // offset = -3.0
    if (calibrado >= 30.0) throw new Error(`Escenario ${esc.num}: calibrado ${calibrado} >= 30.0°C`);
    if (calibrado <= 0) throw new Error(`Escenario ${esc.num}: calibrado ${calibrado} <= 0`);
});

// Timestamps: bloques de 240 minutos (4h) empezando el 2026-10-19T00:00:00Z
// Lectura batch i (0..21): inicio + i * 10 min
// Lectura evaluada: inicio + 220 min
const baseTime = new Date("2026-10-19T00:00:00Z").getTime();
function getEscenarioTimes(escIdx) {
    const inicioMs = baseTime + escIdx * 240 * 60 * 1000;
    const inicio = new Date(inicioMs);
    const evalTs = new Date(inicioMs + 220 * 60 * 1000).toISOString();
    return { inicio, evalTs };
}

// Construye payload de batch con 22 lecturas
function buildBatchPayload(inicio, xBar) {
    const registros = [];
    for (let i = 0; i < N_LECTURAS; i++) {
        const ts = new Date(inicio.getTime() + i * 10 * 60 * 1000).toISOString();
        const valor = Number((xBar + deltas22[i]).toFixed(4));
        registros.push({
            device_id: "{{device_id}}",
            sensor_id: "{{sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: valor,
            unidad: "°C",
            timestamp_captura: ts,
            serial: "{{device_serial}}"
        });
    }
    return { registros };
}

// =====================================================================
// CARPETA 00 — PREFLIGHT (Verificación obligatoria de precondiciones)
// =====================================================================
const preflight = [
    // 00.01 — Login admin único (DEF-04 §6.6)
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
        '        pm.collectionVariables.set("id_usuario_admin", id);',
        '    }',
        '} catch (e) {',
        '    console.warn("No se pudo extraer id_usuario_admin:", e.message);',
        '}',
        `pm.collectionVariables.set("device_id", ${DISPOSITIVO_ID});`,
        `pm.collectionVariables.set("device_serial", "${DEVICE_SERIAL}");`,
        `pm.collectionVariables.set("sensor_id", ${SENSOR_ID});`,
        `pm.collectionVariables.set("id_infraestructura", ${AREA_ID});`
    ]),

    // 00.02 — Verificar Dispositivo 346 activo
    makeItem("00.02-Verificar-Dispositivo-346", "GET",
        `{{baseUrl}}/configuracion/dispositivos-iot/${DISPOSITIVO_ID}`, authAdmin(), null, [], [
        'pm.test("Preflight: Dispositivo 346 existe y activo", function () {',
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        `    pm.expect(r.id_dispositivo_iot).to.equal(${DISPOSITIVO_ID});`,
        '    pm.expect(r.es_activo).to.be.true;',
        '});'
    ]),

    // 00.03 — Verificar Sensor 536 activo
    makeItem("00.03-Verificar-Sensor-536", "GET",
        `{{baseUrl}}/configuracion/dispositivos-iot/${DISPOSITIVO_ID}/sensores`, authAdmin(), null, [], [
        'pm.test("Preflight: Sensor 536 existe y activo", function () {',
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    const items = r.items || r.sensores || (Array.isArray(r) ? r : []);',
        `    const s536 = items.find(x => x.id_sensores === ${SENSOR_ID} || x.id_sensor === ${SENSOR_ID});`,
        '    pm.expect(s536, "Sensor 536 no encontrado en dispositivo").to.exist;',
        '    pm.expect(s536.es_activo, "Sensor 536 debe ser activo").to.be.true;',
        '});'
    ]),

    // 00.04 — Verificar Precondiciones SQL (asociación, calibración y no-contaminación)
    makeItem("00.04-Verificar-Precondiciones-Fixture", "POST",
        "{{baseUrl}}/test-control/query", authAdmin(), {
        query: wrapRlsQuery(`
            SELECT
                (SELECT count(*) FROM modulo9.sensores_areas_asociadas WHERE id_sensor=${SENSOR_ID} AND fecha_asociacion < '2026-10-19 00:00:00+00') as asoc_ok,
                (SELECT count(*) FROM modulo9.calibraciones WHERE id_sensor=${SENSOR_ID} AND fecha_calibracion < '2026-10-19 00:00:00+00' AND offset_calibracion=${CAL_OFFSET.toFixed(1)} AND ganancia=${CAL_GANANCIA.toFixed(1)} AND valor_referencia=${CAL_VALOR_REF.toFixed(1)}) as cal_ok,
                (SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=${SENSOR_ID} AND timestamp_captura >= '2026-10-18 00:00:00+00' AND timestamp_captura < '2026-10-21 00:00:00+00') as contaminacion
        `.trim().replace(/\s+/g, ' '))
    }, [], [
        'pm.test("Preflight: Fixture SQL válido y libre de contaminación", function () {',
        '    pm.response.to.have.status(200);',
        '    const rows = pm.response.json().data || [];',
        '    pm.expect(rows.length, "Consulta SQL debe retornar 1 fila").to.be.above(0);',
        '    const r = rows[0];',
        '    pm.expect(Number(r.asoc_ok), "Sensor 536 asociado antes del 2026-10-19").to.be.at.least(1);',
        '    pm.expect(Number(r.cal_ok), "Sensor 536 calibrado (offset=-3, ganancia=1, ref=25) antes del 2026-10-19").to.be.at.least(1);',
        '    pm.expect(Number(r.contaminacion), "Sin lecturas contaminantes en ventana [2026-10-18, 2026-10-21) — si falla: BLOQUEADO_POR_SEED").to.equal(0);',
        '});'
    ])
];

// =====================================================================
// CONSTRUCCIÓN DE CARPETAS DE ESCENARIOS
// =====================================================================
function buildEscenarioFolder(esc, escIdx) {
    const items = [];
    const { inicio, evalTs } = getEscenarioTimes(escIdx);

    const xBar = esc.Xbar;
    const valCalEsperado = Number((xBar * CAL_GANANCIA + CAL_OFFSET).toFixed(4));
    const driftCalculado = Number((Math.abs(valCalEsperado - CAL_VALOR_REF) / CAL_VALOR_REF * 100).toFixed(4));

    // 1. Ingestar batch de 22 lecturas crudas
    items.push(makeItem(
        `${esc.num}.01-Ingestar-Serie-22`,
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        authBroker(),
        buildBatchPayload(inicio, xBar),
        [],
        [
            `pm.test("${esc.num}: batch 200 (total=${N_LECTURAS}, aceptados=${N_LECTURAS}, rechazados=0)", function () {`,
            '    pm.response.to.have.status(200);',
            '    const r = pm.response.json();',
            `    pm.expect(r.total).to.equal(${N_LECTURAS});`,
            `    pm.expect(r.aceptados).to.equal(${N_LECTURAS});`,
            '    pm.expect(r.rechazados).to.equal(0);',
            '});'
        ]
    ));

    // 2. Ingestar lectura evaluada al timestamp evalTs
    items.push(makeItem(
        `${esc.num}.02-Ingestar-Lectura-Evaluada`,
        "POST",
        "{{baseUrl}}/iot/telemetria",
        authBroker(),
        {
            device_id: "{{device_id}}",
            sensor_id: "{{sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: Number(xBar.toFixed(4)),
            unidad: "°C",
            timestamp_captura: evalTs,
            serial: "{{device_serial}}"
        },
        [],
        [
            `pm.test("${esc.num}: lectura evaluada ingerida 201", function () {`,
            '    pm.response.to.have.status(201);',
            '    const r = pm.response.json();',
            '    pm.expect(r.id_telemetria).to.be.a("number").and.above(0);',
            `    pm.collectionVariables.set("${esc.varName}", r.id_telemetria);`,
            '});'
        ]
    ));

    // 3. Evaluar Calidad
    const evalAssert = [
        `pm.test("${esc.num} (${esc.desc}): evaluar 201 + oráculo exacto", function () {`,
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    const flags = r.flags_detectados || {};',
        '    const drift = flags.posible_drift || {};',
        `    pm.expect(r.indice_calidad).to.equal(${esc.indice});`,
        `    pm.expect(r.clasificacion_calidad).to.equal("${esc.clas}");`,
        `    pm.expect(r.apto_para_ia).to.equal(${esc.ia});`,
        `    pm.expect(r.apto_para_nic41).to.equal(${esc.nic41});`,
        '    pm.expect(r.estado_evaluacion).to.equal("VIGENTE");'
    ];

    if (!esc.activo) {
        evalAssert.push(
            '    pm.expect(drift.activo === true, "1A: No debe activarse el flag de drift (borde estricto 5.00%)").to.be.false;'
        );
    } else {
        evalAssert.push(
            '    pm.expect(drift.activo).to.equal(true);',
            `    pm.expect(drift.magnitud_drift_porcentaje).to.be.closeTo(${driftCalculado}, 0.01);`,
            `    pm.expect(drift.media_ultimas_N).to.be.closeTo(${valCalEsperado}, 0.05);`,
            `    pm.expect(drift.valor_calibrado_esperado).to.be.closeTo(${CAL_VALOR_REF.toFixed(2)}, 0.01);`,
            '    pm.expect(drift.umbral_aplicado).to.equal(5.0);',
            '    pm.expect(drift.P_lecturas_consistentes).to.be.at.least(5);'
        );
    }

    if (esc.alerta_rf57 === "registrar") {
        evalAssert.push(
            `    console.log("[INFO] Alerta RF-57 para drift ${esc.drift}%: registro informativo (no requerida <= 20%)");`
        );
    }

    evalAssert.push('});');

    items.push(makeItem(
        `${esc.num}.03-Evaluar-Calidad`,
        "POST",
        `{{baseUrl}}/iot/calidad/{{${esc.varName}}}/evaluar`,
        authAdmin(),
        null,
        [],
        evalAssert
    ));

    // Verificaciones extra para escenarios >20% (3A, 3B)
    if (esc.alerta_rf57 === "verificar") {
        // Alerta técnica RF-57
        items.push(makeItem(
            `${esc.num}.04-Verificar-Alerta-RF57`,
            "POST",
            "{{baseUrl}}/test-control/query",
            authAdmin(),
            { query: wrapRlsQuery(`SELECT id_alerta, tipo_alerta, severidad FROM modulo3.alertas WHERE id_telemetria = {{${esc.varName}}}`) },
            [],
            [
                `pm.test("${esc.num}: [RF-57] Alerta técnica consultada", function () {`,
                '    pm.response.to.have.status(200);',
                '    const rows = (pm.response.json().data || []);',
                '    if (rows.length === 0) {',
                `        console.warn("[OBSERVACION] INC-M03-RF57-NOT-EMITTED: EvaluarCalidad no emitió alerta técnica para drift ${esc.drift}%");`,
                '    } else {',
                '        pm.expect(rows[0].tipo_alerta).to.equal("TECNICA");',
                '    }',
                '});'
            ]
        ));

        // Bitácora RF-63
        items.push(makeItem(
            `${esc.num}.05-Verificar-Bitacora-RF63`,
            "POST",
            "{{baseUrl}}/test-control/query",
            authAdmin(),
            { query: wrapRlsQuery(`SELECT tipo_evento, componente_origen FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id = '{{${esc.varName}}}' ORDER BY id_evento DESC LIMIT 1`) },
            [],
            [
                `pm.test("${esc.num}: bitácora RF-63 con EVALUACION_CALIDAD_COMPLETADA", function () {`,
                '    pm.response.to.have.status(200);',
                '    const rows = (pm.response.json().data || []);',
                '    pm.expect(rows.length).to.be.above(0);',
                '    pm.expect(rows[0].tipo_evento).to.equal("EVALUACION_CALIDAD_COMPLETADA");',
                '    // El backend audita con el literal sin guión: "RF62"',
                '    pm.expect(rows[0].componente_origen).to.equal("RF62");',
                '});'
            ]
        ));

        // Transición SUPERADA / D7
        items.push(makeItem(
            `${esc.num}.06-Verificar-Transicion-SUPERADA-D7`,
            "POST",
            "{{baseUrl}}/test-control/query",
            authAdmin(),
            { query: wrapRlsQuery(`SELECT id_evaluacion, estado_evaluacion, motivo_reevaluacion, id_evaluacion_superada, version_evaluacion FROM modulo3.telemetria_calidad WHERE id_telemetria = {{${esc.varName}}} ORDER BY fecha_creacion DESC`) },
            [],
            [
                `pm.test("${esc.num}: D7 - exactamente 1 VIGENTE", function () {`,
                '    pm.response.to.have.status(200);',
                '    const rows = (pm.response.json().data || []);',
                '    const vigentes = rows.filter(r => r.estado_evaluacion === "VIGENTE");',
                '    pm.expect(vigentes.length, "COUNT(*) WHERE estado_evaluacion=\'VIGENTE\' = 1").to.equal(1);',
                '});'
            ]
        ));
    }

    return { name: `Escenario-${esc.num}-drift-${esc.drift}%`, item: items };
}

const folders = [
    { name: "00-Preflight-Verificacion", item: preflight },
    ...escenarios.map(buildEscenarioFolder),
    {
        name: "99-Teardown",
        item: [
            makeItem("99.01-Rollback-Sandbox", "DELETE", "{{baseUrl}}/test-control/runs/{{run_id}}", [], null, [], [
                'pm.test("Rollback 200", function () {',
                '    pm.response.to.have.status(200);',
                '    pm.expect(pm.response.text()).to.include("Rollback exitoso");',
                '});'
            ])
        ]
    }
];

const collection = {
    info: {
        _postman_id: "tc-m03-g167-v3-sensor536",
        name: "TC-M03-G167 - Drift fronteras RF-62 (sensor 536 pre-existente)",
        description: "Suite con sensor 536 pre-existente. Ingesta series con Xbar calibrada para inducir drift exacto contra referencia=25.0.",
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
                    '    console.warn("[TC-M03-G167] sandbox_secret no resuelto. Los requests van a fallar con 403.");',
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
        { key: "id_infraestructura", value: String(AREA_ID) },
        { key: "device_id", value: String(DISPOSITIVO_ID) },
        { key: "device_serial", value: DEVICE_SERIAL },
        { key: "sensor_id", value: String(SENSOR_ID) },
        { key: "id_tel_1a", value: "" },
        { key: "id_tel_1b", value: "" },
        { key: "id_tel_1c", value: "" },
        { key: "id_tel_2a", value: "" },
        { key: "id_tel_2b", value: "" },
        { key: "id_tel_3a", value: "" },
        { key: "id_tel_3b", value: "" }
    ],
    item: folders
};

const target = path.join(__dirname, "test_tc_m03_g167.json");
fs.writeFileSync(target, JSON.stringify(collection, null, 2), "utf8");

let total = 0;
folders.forEach(f => total += f.item.length);
console.log(`Colección generada: ${target}`);
console.log(`Carpetas: ${folders.length}, Requests: ${total}`);
