/**
 * TC-M03-G169 — Estados de calidad heredados de RF-53 (RF-62 / RF-53 / RF-63)
 * Suite Newman con sensores preexistentes (Reintento 1).
 * Reporte objetivo: resultado_TC-M03-G169_reintento1.json / .html
 *
 * Subcasos:
 * - TC-M03-321: Lectura FUERA_DE_RANGO heredada (índice 0, NO_APTO, fuera_de_rango_rf53=true)
 *   Sensor 552 (serial QA-G87-S1-20261023063513-c84150, calibrado, fecha_asociacion=2026-04-28)
 * - TC-M03-322: Lectura ERROR_CALIBRACION heredada + anomalías múltiples (índice 70 CSV / 80 real)
 *   Sensor 15 (serial IOT-CAM02-COR-002, no calibrado, fecha_asociacion=2026-04-28)
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
// CARPETA 00 — PREFLIGHT (login único)
// =====================================================================
const preflight = [
    // 00.01 — Login admin + extracción de sub (id_usuario_admin)
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
    ])
];

// =====================================================================
// CARPETA TC-321 — FUERA_DE_RANGO (Heredado de RF-53)
// =====================================================================
function buildTC321Folder() {
    const sub = "321";
    const devIdVar = `device_id_${sub}`;
    const devSerialVar = `serial_${sub}`;
    const sensorIdVar = `sensor_id_${sub}`;
    const telIdVar = `tel_id_${sub}`;

    const items = [];

    // 321.04 — Ingestar valor 50.00 °C (> umbral max 40 °C de especie 2, dentro de rango físico 100 °C)
    // Se usa timestamp dinámico relativo a NOW() (hace 60 segundos)
    items.push(makeItem(`${sub}.04-Ingestar-Lectura-Fuera-Rango`, "POST",
        "{{baseUrl}}/iot/telemetria", authBroker(), {
        device_id: `{{${devIdVar}}}`,
        sensor_id: `{{${sensorIdVar}}}`,
        tipo_variable: "TEMPERATURA_AMBIENTAL",
        valor: 50.00,
        unidad: "°C",
        timestamp_captura: "{{ts_321}}",
        serial: `{{${devSerialVar}}}`
    }, [
        'const nowMs = Date.now();',
        'const ts321 = new Date(nowMs - 60 * 1000).toISOString().slice(0, 19) + "Z";',
        'pm.collectionVariables.set("ts_321", ts321);'
    ], [
        'pm.test("321: Ingesta 201 con FUERA_DE_RANGO", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_telemetria).to.be.a("number").and.above(0);',
        '    pm.expect(r.estado_calidad).to.equal("FUERA_DE_RANGO");',
        `    pm.collectionVariables.set("${telIdVar}", r.id_telemetria);`,
        '    pm.collectionVariables.set("id_telemetria_321", r.id_telemetria);',
        '});'
    ]));

    // 321.05 — Evaluar calidad -> Fase 0 aborta a NO_APTO, índice 0, fuera_de_rango_rf53 activo
    items.push(makeItem(`${sub}.05-Evaluar-Calidad`, "POST",
        `{{baseUrl}}/iot/calidad/{{${telIdVar}}}/evaluar`, authAdmin(), null, [], [
        'pm.test("321: Evaluar 201 -> NO_APTO, índice 0, fuera_de_rango_rf53 activo", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.indice_calidad).to.equal(0);',
        '    pm.expect(r.clasificacion_calidad).to.equal("NO_APTO");',
        '    pm.expect(r.apto_para_ia).to.equal(false);',
        '    pm.expect(r.apto_para_nic41).to.equal(false);',
        '    const flags = r.flags_detectados || {};',
        '    pm.expect(flags.fuera_de_rango_rf53).to.exist;',
        '    pm.expect(flags.fuera_de_rango_rf53.activo).to.equal(true);',
        '    pm.expect(flags.sensor_congelado).to.be.undefined;',
        '    pm.expect(flags.outlier_estadistico).to.be.undefined;',
        '    pm.expect(flags.posible_drift).to.be.undefined;',
        '    pm.expect(flags.gap_temporal_anomalo).to.be.undefined;',
        '});',
        'pm.test("version_limites_fisicos_aplicada presente", () => {',
        '    const v = pm.response.json().version_limites_fisicos_aplicada;',
        '    pm.expect(v).to.not.be.undefined;',
        '    pm.expect(v).to.not.be.null;',
        '});',
        'pm.test("parametros_aplicados presente", () => {',
        '    const p = pm.response.json().parametros_aplicados;',
        '    pm.expect(p).to.not.be.undefined;',
        '    pm.expect(p).to.not.be.null;',
        '});'
    ]));

    // 321.06 — Verificar persistencia vía GET
    items.push(makeItem(`${sub}.06-Verificar-Persistencia-GET`, "GET",
        `{{baseUrl}}/iot/calidad/{{${telIdVar}}}`, authAdmin(), null, [], [
        'pm.test("321: GET calidad 200 coincide con evaluación", function () {',
        '    pm.response.to.have.status(200);',
        '    const r = pm.response.json();',
        '    pm.expect(r.indice_calidad).to.equal(0);',
        '    pm.expect(r.clasificacion_calidad).to.equal("NO_APTO");',
        '    pm.expect(r.apto_para_ia).to.equal(false);',
        '    pm.expect(r.apto_para_nic41).to.equal(false);',
        '});'
    ]));

    // Fix 6: 321.07 — Verificar inmutabilidad de RF-53 post-evaluación
    items.push(makeItem(`${sub}.07-Verificar-Inmutabilidad-RF53`, "POST",
        "{{baseUrl}}/test-control/query",
        [h("X-Sandbox-Secret", "{{sandbox_secret}}")],
        {
            query: wrapRlsQuery(`SELECT valor_crudo, unidad_medida, timestamp_captura, estado_calidad FROM modulo3.telemetrias WHERE id_telemetria = {{${telIdVar}}}`)
        },
        [],
        [
            'pm.test("TC-321: valor original en RF-53 intacto tras POST /evaluar", function () {',
            '    pm.response.to.have.status(200);',
            '    const rows = pm.response.json().data || pm.response.json().rows || [];',
            '    pm.expect(rows.length).to.be.above(0);',
            '    const row = rows[0];',
            '    pm.expect(parseFloat(row.valor_crudo !== undefined ? row.valor_crudo : row.valor)).to.equal(50.00);',
            '    pm.expect(row.unidad_medida || row.unidad).to.equal("°C");',
            '    pm.expect(row.estado_calidad).to.equal("FUERA_DE_RANGO");',
            '});'
        ]
    ));

    // 321.09 — Verificar que NO se disparó alerta técnica en RF-57 para FUERA_DE_RANGO
    items.push(makeItem(`${sub}.09-Verificar-Sin-Alerta-Tecnica`, "POST",
        "{{baseUrl}}/test-control/query",
        [h("X-Sandbox-Secret", "{{sandbox_secret}}")],
        {
            query: wrapRlsQuery(`SELECT COUNT(*) AS n FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id = '{{id_telemetria_321}}' AND tipo_evento = 'ALERTA_TECNICA_EMITIDA'`)
        },
        [],
        [
            'pm.test("NO se disparó alerta técnica en RF-57 para FUERA_DE_RANGO", () => {',
            '    const resp = pm.response.json();',
            '    const rows = resp.data || resp.rows || resp;',
            '    const n = Array.isArray(rows) ? (rows[0] ? rows[0].n : 0) : (rows.n !== undefined ? rows.n : rows);',
            '    pm.expect(parseInt(n)).to.eql(0);',
            '});'
        ]
    ));

    return { name: `TC-321-fuera-de-rango`, item: items };
}

// =====================================================================
// CARPETA TC-322 — ERROR_CALIBRACION (Heredado de RF-53 + Anomalías)
// =====================================================================
function buildTC322Folder() {
    const sub = "322";
    const devIdVar = `device_id_${sub}`;
    const devSerialVar = `serial_${sub}`;
    const sensorIdVar = `sensor_id_${sub}`;
    const telIdVar = `tel_id_${sub}`;

    const items = [];

    // Pre-request script de la serie para calcular timestamps una sola vez (cadencia 45 min, gap 95 min)
    const seriesInitScript = [
        'if (!pm.collectionVariables.get("t_series_322_initialized")) {',
        '    const nowMs = Date.now();',
        '    const MS_MIN = 60 * 1000;',
        '',
        '    // Lectura evaluada: NOW() - 5 min (lectura reciente para no disparar RF-60)',
        '    const tEvalMs = nowMs - 5 * MS_MIN;',
        '    pm.collectionVariables.set("t_eval_ts_322", new Date(tEvalMs).toISOString().slice(0, 19) + "Z");',
        '',
        '    // 20 lecturas previas: #20 en NOW() - 100 min, #1 en NOW() - 955 min',
        '    // Cadencia 45 min entre consecutivas; gap #20 -> eval = 95 min',
        '    for (let i = 0; i < 20; i++) {',
        '        const minutesBack = 955 - i * 45; // 955, 910, 865, ..., 100',
        '        const ts = new Date(nowMs - minutesBack * MS_MIN).toISOString().slice(0, 19) + "Z";',
        '        pm.collectionVariables.set("ts_prev_322_" + (i + 1), ts);',
        '    }',
        '    pm.collectionVariables.set("t_series_322_initialized", "true");',
        '}'
    ];

    // 322.04 — Ingestar lote de 20 lecturas con gap de 95 min previo a la lectura 21
    const registros = [];
    for (let i = 0; i < 20; i++) {
        const val = (i % 2 === 0) ? 21.50 : 22.50;
        registros.push({
            device_id: `{{${devIdVar}}}`,
            sensor_id: `{{${sensorIdVar}}}`,
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: val,
            unidad: "°C",
            timestamp_captura: `{{ts_prev_322_${i + 1}}}`,
            serial: `{{${devSerialVar}}}`
        });
    }

    items.push(makeItem(`${sub}.04-Ingestar-Serie-20-Con-Gap`, "POST",
        "{{baseUrl}}/iot/telemetria/batch", authBroker(), { registros }, seriesInitScript, [
        'pm.test("322: Batch 20 lecturas 200", function () {',
        '    pm.response.to.have.status(200);',
        '    pm.expect(pm.response.json().aceptados).to.equal(20);',
        '});'
    ]));

    // 322.05 — Ingestar lectura 21 evaluada (25.50 °C, salto de 95 min respecto a lectura 20)
    items.push(makeItem(`${sub}.05-Ingestar-Lectura-Evaluada`, "POST",
        "{{baseUrl}}/iot/telemetria", authBroker(), {
        device_id: `{{${devIdVar}}}`,
        sensor_id: `{{${sensorIdVar}}}`,
        tipo_variable: "TEMPERATURA_AMBIENTAL",
        valor: 25.50,
        unidad: "°C",
        timestamp_captura: "{{t_eval_ts_322}}",
        serial: `{{${devSerialVar}}}`
    }, [], [
        'pm.test("322: Lectura 21 ingerida 201 con ERROR_CALIBRACION", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_telemetria).to.be.a("number").and.above(0);',
        '    pm.expect(r.estado_calidad).to.equal("ERROR_CALIBRACION");',
        `    pm.collectionVariables.set("${telIdVar}", r.id_telemetria);`,
        '    pm.collectionVariables.set("id_telemetria_322", r.id_telemetria);',
        '});'
    ]));

    // Fix 4: 322.05b — Pre-check sensor sin calibración previa en modulo9.calibraciones
    items.push(makeItem(`${sub}.05b-Precheck-Sin-Calibracion`, "POST",
        "{{baseUrl}}/test-control/query",
        [h("X-Sandbox-Secret", "{{sandbox_secret}}")],
        {
            query: wrapRlsQuery(`SELECT COUNT(*) AS total FROM modulo9.calibraciones WHERE id_sensor = {{${sensorIdVar}}}`)
        },
        [],
        [
            'pm.test("322: Sensor sin calibración previa en modulo9.calibraciones", function () {',
            '    pm.response.to.have.status(200);',
            '    const rows = pm.response.json().data || pm.response.json().rows || [];',
            '    pm.expect(rows.length).to.be.above(0);',
            '    pm.expect(parseInt(rows[0].total)).to.equal(0);',
            '});'
        ]
    ));

    // 322.06 — Evaluar calidad
    items.push(makeItem(`${sub}.06-Evaluar-Calidad`, "POST",
        `{{baseUrl}}/iot/calidad/{{${telIdVar}}}/evaluar`, authAdmin(), null, [], [
        'pm.test("322: Evaluar 201 -> APTO_CON_RESERVA, índice 70 (oráculo CSV)", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    const flags = r.flags_detectados || {};',
        '    pm.expect(flags.calibracion_no_disponible).to.exist;',
        '    pm.expect(flags.calibracion_no_disponible.activo).to.equal(true);',
        '    pm.expect(flags.outlier_estadistico).to.exist;',
        '    pm.expect(flags.outlier_estadistico.activo).to.equal(true);',
        '    // Drift debe estar ausente / omitido por calibracion_no_disponible',
        '    pm.expect(flags.posible_drift === undefined || flags.posible_drift.activo === false).to.be.true;',
        '    // Oráculo estricto del CSV: índice 70 por acumulación outlier (-20) + gap (-10)',
        '    pm.expect(r.indice_calidad).to.equal(70);',
        '    pm.expect(r.clasificacion_calidad).to.equal("APTO_CON_RESERVA");',
        '});',
        '// Fix 5: Assert explícito gap_temporal_anomalo.activo en TC-322',
        'pm.test("TC-322: gap_temporal_anomalo.activo === true (aporta −10)", function () {',
        '    const body = pm.response.json();',
        '    pm.expect(body.flags_detectados && body.flags_detectados.gap_temporal_anomalo && body.flags_detectados.gap_temporal_anomalo.activo === true).to.equal(true);',
        '});',
        'pm.test("apto_para_ia es true", () => {',
        '    pm.expect(pm.response.json().apto_para_ia).to.eql(true);',
        '});',
        'pm.test("apto_para_nic41 es false", () => {',
        '    pm.expect(pm.response.json().apto_para_nic41).to.eql(false);',
        '});',
        'pm.test("sensor_congelado NO activo (serie alterna no dispara congelado)", () => {',
        '    const sc = pm.response.json().flags_detectados?.sensor_congelado;',
        '    pm.expect(sc?.activo ?? false).to.eql(false);',
        '});'
    ]));

    // Fix 6: 322.07 — Verificar inmutabilidad de RF-53 post-evaluación
    items.push(makeItem(`${sub}.07-Verificar-Inmutabilidad-RF53`, "POST",
        "{{baseUrl}}/test-control/query",
        [h("X-Sandbox-Secret", "{{sandbox_secret}}")],
        {
            query: wrapRlsQuery(`SELECT valor_crudo, unidad_medida, timestamp_captura, estado_calidad FROM modulo3.telemetrias WHERE id_telemetria = {{${telIdVar}}}`)
        },
        [],
        [
            'pm.test("TC-322: valor original en RF-53 intacto tras POST /evaluar", function () {',
            '    pm.response.to.have.status(200);',
            '    const rows = pm.response.json().data || pm.response.json().rows || [];',
            '    pm.expect(rows.length).to.be.above(0);',
            '    const row = rows[0];',
            '    pm.expect(parseFloat(row.valor_crudo !== undefined ? row.valor_crudo : row.valor)).to.equal(25.50);',
            '    pm.expect(row.unidad_medida || row.unidad).to.equal("°C");',
            '    pm.expect(row.estado_calidad).to.equal("ERROR_CALIBRACION");',
            '});'
        ]
    ));

    return { name: `TC-322-error-calibracion`, item: items };
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
            'pm.test("NW-Teardown: Rollback transaccional exitoso (HTTP 200)", function () {',
            '    pm.response.to.have.status(200);',
            '    const data = pm.response.json();',
            '    pm.expect(data.status).to.include("Rollback exitoso");',
            '});'
        ]
    )
];

const folders = [
    { name: "00-Preflight", item: preflight },
    buildTC321Folder(),
    buildTC322Folder(),
    { name: "99-Teardown", item: teardown }
];

const collection = {
    info: {
        _postman_id: "tc-m03-g169-estados-heredados",
        name: "TC-M03-G169 - Estados heredados de RF-53 (RF-62)",
        description: "Suite autosuficiente para TC-321 (FUERA_DE_RANGO) y TC-322 (ERROR_CALIBRACION) usando sensores preexistentes. Genera resultado_TC-M03-G169_reintento1.json.",
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
                    '    console.warn("[TC-M03-G169] sandbox_secret no resuelto. Los requests van a fallar con 403.");',
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
        { key: "sensor_id_321", value: "552" },
        { key: "device_id_321", value: "357" },
        { key: "serial_321", value: "QA-G87-S1-20261023063513-c84150" },
        { key: "dev_id_321", value: "357" },
        { key: "dev_serial_321", value: "QA-G87-S1-20261023063513-c84150" },
        { key: "tel_id_321", value: "" },
        { key: "id_telemetria_321", value: "" },
        { key: "ts_321", value: "" },
        { key: "sensor_id_322", value: "15" },
        { key: "device_id_322", value: "7" },
        { key: "serial_322", value: "IOT-CAM02-COR-002" },
        { key: "dev_id_322", value: "7" },
        { key: "dev_serial_322", value: "IOT-CAM02-COR-002" },
        { key: "tel_id_322", value: "" },
        { key: "id_telemetria_322", value: "" },
        { key: "t_eval_ts_322", value: "" },
        { key: "t_series_322_initialized", value: "" }
    ],
    item: folders
};

const target = path.join(__dirname, "test_tc_m03_g169.json");
fs.writeFileSync(target, JSON.stringify(collection, null, 2), "utf8");

let total = 0;
folders.forEach(f => total += f.item.length);
console.log(`Colección generada: ${target}`);
console.log(`Carpetas: ${folders.length}, Requests: ${total}`);
