/**
 * TC-M03-G167 — Detección de drift (RF-62 / RF-57 / RF-63)
 * Suite Newman autosuficiente (autosiembra en sandbox).
 *
 * Cambios respecto a la versión anterior (ver DIAGNOSTICO en DISENO_Y_PRECONDICIONES.md):
 * 1. baseUrl correcto: https://www.api.inmero.co/api-sgpmp-test
 * 2. Endpoint de calibración: POST /configuracion/sensores/{id}/calibrar
 *    (NO INSERT SQL; INSERT vía /test-control/query está bloqueado con 403).
 * 3. Autosiembra: finca → área → dispositivo → sensor → asociación,
 *    todo dentro del run_id (rollback al final).
 * 4. Ingesta: campo `serial` (no `access_key`, renombrado en commit 1d503b5).
 * 5. Ingesta: Authorization: Bearer {{broker_token}} (obligatorio).
 * 6. Batch: sin parseInt sobre {{device_id}} (Pydantic coacciona).
 * 7. Nombres únicos por run_id para evitar colisiones en re-ejecuciones.
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
// CARPETA 00 — PREFLIGHT (autosiembra en sandbox)
// =====================================================================
// Genera N letras aleatorias a-z (solo letras, sin tildes, sin ñ, sin dígitos)
function letrasAleatorias(n) {
    const abc = "abcdefghijklmnopqrstuvwxyz";
    let s = "";
    for (let i = 0; i < n; i++) s += abc[Math.floor(Math.random() * abc.length)];
    return s;
}

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

    // 00.02 — Tipo dispositivo SENSOR
    makeItem("00.02-Descubrir-Tipo-Dispositivo", "GET",
        "{{baseUrl}}/configuracion/tipos-dispositivo-iot", authAdmin(), null, [], [
        'pm.test("Tipo SENSOR disponible", function () {',
        '    pm.response.to.have.status(200);',
        '    const items = pm.response.json().items || [];',
        '    const sensor = items.find(x => x.categoria === "SENSOR");',
        '    pm.expect(sensor, "No hay tipo_dispositivo SENSOR").to.exist;',
        '    pm.collectionVariables.set("id_tipo_dispositivo", sensor.id_tipo_dispositivo);',
        '});'
    ]),

    // 00.03 — Tipo área "Galpón"
    makeItem("00.03-Descubrir-Tipo-Area", "GET",
        "{{baseUrl}}/configuracion/tipos-area?solo_activos=true", authAdmin(), null, [], [
        'pm.test("Tipo área Galpón disponible", function () {',
        '    pm.response.to.have.status(200);',
        '    const items = pm.response.json().items || [];',
        '    const galpon = items.find(x => /galp[oó]n/i.test(x.nombre));',
        '    pm.expect(galpon, "No hay tipo_area Galpón").to.exist;',
        '    pm.collectionVariables.set("tipo_area_nombre", galpon.nombre);',
        '});'
    ]),

    // 00.04 — Finca (SOLO LETRAS Y ESPACIOS)
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
        '    pm.collectionVariables.set("finca_nombre", r.nombre);',
        '});'
    ]),

    // 00.05 — Área (SOLO LETRAS Y ESPACIOS, especie ACUICULTURA=123)
    makeItem("00.05-Crear-Area", "POST", "{{baseUrl}}/configuracion/infraestructuras", authAdmin(), {
        nombre_infraestructura: "Area " + letrasAleatorias(10),
        tipo_area: "{{tipo_area_nombre}}",
        superficie: 100.0,
        finca_id: "{{id_finca}}",
        descripcion_infraestructura: "Area de pruebas de calidad",
        especie_id: 123,
        tipo_modelo_asignado: "MODELO_ACUICULTURA"
    }, [], [
        'pm.test("Área 201", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_infraestructura).to.be.a("number").and.above(0);',
        '    pm.collectionVariables.set("id_infraestructura", r.id_infraestructura);',
        '    pm.collectionVariables.set("area_nombre", r.nombre_infraestructura);',
        '});'
    ]),

    // 00.06 — Dispositivo (serial solo alfanumérico mayúsculas)
    makeItem("00.06-Crear-Dispositivo", "POST",
        "{{baseUrl}}/configuracion/dispositivos-iot", authAdmin(), {
        serial: "GDEV" + letrasAleatorias(10).toUpperCase(),
        descripcion: "Dispositivo de pruebas de calidad",
        id_infraestructura: "{{id_infraestructura}}",
        id_tipo_dispositivo: "{{id_tipo_dispositivo}}",
        es_activo: true
    }, [], [
        'pm.test("Dispositivo 201", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_dispositivo_iot).to.be.a("number").and.above(0);',
        '    pm.collectionVariables.set("device_id", r.id_dispositivo_iot);',
        '    pm.collectionVariables.set("device_serial", r.serial);',
        '    pm.collectionVariables.set("device_nombre", r.serial);',
        '});'
    ]),

    // 00.07 — Sensor (categoria TEMPERATURA, nombre solo letras)
    makeItem("00.07-Crear-Sensor", "POST",
        "{{baseUrl}}/configuracion/dispositivos-iot/{{device_id}}/sensores", authAdmin(), {
        nombre: "Sensor " + letrasAleatorias(10),
        categoria: "TEMPERATURA"
    }, [], [
        'pm.test("Sensor 201", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_sensores).to.be.a("number").and.above(0);',
        '    pm.collectionVariables.set("sensor_id", r.id_sensores);',
        '});'
    ]),

    // 00.08 — Asociar sensor al área
    makeItem("00.08-Asociar-Sensor-Area", "POST",
        "{{baseUrl}}/configuracion/sensores/{{sensor_id}}/asociar", authAdmin(), {
        id_dispositivo_iot: "{{device_id}}",
        id_infraestructura: "{{id_infraestructura}}",
        punto_instalacion: "Centro del area",
        confirmar: false
    }, [], [
        'pm.test("Asociación 201", function () {',
        '    pm.response.to.have.status(201);',
        '});'
    ])
];

// =====================================================================
// ESCENARIOS (7)
// =====================================================================
const deltas = [-0.2, -0.1, 0.0, 0.1, 0.2];

const escenarios = [
    { num: "1A", subcaso: "TC-M03-313", drift: 5.00,  m: 21.000, offset: -1.000, prefix: "2026-10-19T01", evalTs: "2026-10-19T01:45:00Z", varName: "id_tel_1a", activo: false, indice: 100, clas: "APTO",            ia: true,  nic41: true,  desc: "5.00% (borde estricto, sin flag)" },
    { num: "1B", subcaso: "TC-M03-313", drift: 7.00,  m: 21.400, offset: -1.400, prefix: "2026-10-19T02", evalTs: "2026-10-19T02:45:00Z", varName: "id_tel_1b", activo: true,  indice: 90,  clas: "APTO",            ia: true,  nic41: true,  desc: "7.00% (tramo <10%)" },
    { num: "1C", subcaso: "TC-M03-313", drift: 9.99,  m: 21.998, offset: -1.998, prefix: "2026-10-19T03", evalTs: "2026-10-19T03:45:00Z", varName: "id_tel_1c", activo: true,  indice: 90,  clas: "APTO",            ia: true,  nic41: true,  desc: "9.99% (frontera <10%)" },
    { num: "2A", subcaso: "TC-M03-314", drift: 10.00, m: 22.000, offset: -2.000, prefix: "2026-10-19T04", evalTs: "2026-10-19T04:45:00Z", varName: "id_tel_2a", activo: true,  indice: 75,  clas: "APTO_CON_RESERVA", ia: true,  nic41: false, desc: "10.00% (frontera 10-20%)" },
    { num: "2B", subcaso: "TC-M03-314", drift: 15.00, m: 23.000, offset: -3.000, prefix: "2026-10-19T05", evalTs: "2026-10-19T05:45:00Z", varName: "id_tel_2b", activo: true,  indice: 75,  clas: "APTO_CON_RESERVA", ia: true,  nic41: false, desc: "15.00% (tramo 10-20%)" },
    { num: "3A", subcaso: "TC-M03-315", drift: 20.01, m: 24.002, offset: -4.002, prefix: "2026-10-19T06", evalTs: "2026-10-19T06:45:00Z", varName: "id_tel_3a", activo: true,  indice: 60,  clas: "APTO_CON_RESERVA", ia: true,  nic41: false, desc: "20.01% (frontera >20%)" },
    { num: "3B", subcaso: "TC-M03-315", drift: 25.00, m: 25.000, offset: -5.000, prefix: "2026-10-19T07", evalTs: "2026-10-19T07:45:00Z", varName: "id_tel_3b", activo: true,  indice: 60,  clas: "APTO_CON_RESERVA", ia: true,  nic41: false, desc: "25.00% (tramo >20%)" }
];

// Construye el payload del batch (20 lecturas crudas)
function buildBatchPayload(prefix, m) {
    const registros = [];
    let idx = 0;
    for (let rep = 0; rep < 4; rep++) {
        for (let d = 0; d < deltas.length; d++) {
            const mm = String(idx * 2).padStart(2, "0");
            registros.push({
                device_id: "{{device_id}}",
                sensor_id: "{{sensor_id}}",
                tipo_variable: "TEMPERATURA_AMBIENTAL",
                valor: Number((m + deltas[d]).toFixed(4)),
                unidad: "°C",
                timestamp_captura: `${prefix}:${mm}:00Z`,
                serial: "{{device_serial}}"
            });
            idx++;
        }
    }
    return { registros };
}

// Construye la carpeta de un escenario
function buildEscenarioFolder(esc) {
    const items = [];

    // A. Calibrar
    items.push(makeItem(
        `${esc.num}.01-Calibrar`,
        "POST",
        "{{baseUrl}}/configuracion/sensores/{{sensor_id}}/calibrar",
        authAdmin(),
        {
            id_dispositivo_iot: "{{device_id}}",
            id_infraestructura: "{{id_infraestructura}}",
            valor_referencia: 20.0,
            ganancia: 1.0,
            offset: esc.offset,
            fecha_calibracion: esc.evalTs,
            observaciones: `Calibración G167 ${esc.num} (drift ${esc.drift}%)`,
            modo_calibracion: "SENSOR"
        },
        [],
        [
            `pm.test("${esc.num}: calibración 201", function () {`,
            '    pm.response.to.have.status(201);',
            '    const r = pm.response.json();',
            '    pm.expect(r.id_calibracion).to.be.a("number").and.above(0);',
            `    pm.expect(r.offset).to.be.closeTo(${esc.offset.toFixed(4)}, 0.0001);`,
            '    pm.expect(r.ganancia).to.equal(1);',
            '});'
        ]
    ));

    // B. Batch 20 lecturas
    items.push(makeItem(
        `${esc.num}.02-Ingestar-Serie-20`,
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        authBroker(),
        buildBatchPayload(esc.prefix, esc.m),
        [],
        [
            `pm.test("${esc.num}: batch 200 (total=20, aceptados=20, rechazados=0)", function () {`,
            '    pm.response.to.have.status(200);',
            '    const r = pm.response.json();',
            '    pm.expect(r.total).to.equal(20);',
            '    pm.expect(r.aceptados).to.equal(20);',
            '    pm.expect(r.rechazados).to.equal(0);',
            '});'
        ]
    ));

    // C. Lectura evaluada
    items.push(makeItem(
        `${esc.num}.03-Ingestar-Lectura-Evaluada`,
        "POST",
        "{{baseUrl}}/iot/telemetria",
        authBroker(),
        {
            device_id: "{{device_id}}",
            sensor_id: "{{sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: Number(esc.m.toFixed(4)),
            unidad: "°C",
            timestamp_captura: esc.evalTs,
            serial: "{{device_serial}}"
        },
        [],
        [
            `pm.test("${esc.num}: lectura 21 ingerida 201", function () {`,
            '    pm.response.to.have.status(201);',
            '    const r = pm.response.json();',
            '    pm.expect(r.id_telemetria).to.be.a("number").and.above(0);',
            `    pm.collectionVariables.set("${esc.varName}", r.id_telemetria);`,
            '});'
        ]
    ));

    // D. Evaluar calidad
    const evalAssert = [
        `pm.test("${esc.num} (${esc.desc}): evaluar 201 + oráculo exacto", function () {`,
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    const flags = r.flags_detectados || {};',
        '    const drift = flags.posible_drift || {};'
    ];
    if (!esc.activo) {
        evalAssert.push(
            '    pm.expect(drift.activo === true, "No debe activarse el flag de drift").to.be.false;',
            `    pm.expect(r.indice_calidad).to.equal(${esc.indice});`,
            `    pm.expect(r.clasificacion_calidad).to.equal("${esc.clas}");`,
            `    pm.expect(r.apto_para_ia).to.equal(${esc.ia});`,
            `    pm.expect(r.apto_para_nic41).to.equal(${esc.nic41});`,
            '    pm.expect(r.estado_evaluacion).to.equal("VIGENTE");'
        );
    } else {
        evalAssert.push(
            '    pm.expect(drift.activo).to.equal(true);',
            `    pm.expect(drift.magnitud_drift_porcentaje).to.be.closeTo(${esc.drift.toFixed(4)}, 0.01);`,
            `    pm.expect(drift.media_ultimas_N).to.be.closeTo(${esc.m.toFixed(4)}, 0.05);`,
            `    pm.expect(drift.valor_calibrado_esperado).to.be.closeTo(20.0000, 0.05);`,
            '    pm.expect(drift.P_lecturas_consistentes).to.be.at.least(3);',
            `    pm.expect(r.indice_calidad).to.equal(${esc.indice});`,
            `    pm.expect(r.clasificacion_calidad).to.equal("${esc.clas}");`,
            `    pm.expect(r.apto_para_ia).to.equal(${esc.ia});`,
            `    pm.expect(r.apto_para_nic41).to.equal(${esc.nic41});`,
            '    pm.expect(r.estado_evaluacion).to.equal("VIGENTE");'
        );
    }
    evalAssert.push('});');

    items.push(makeItem(
        `${esc.num}.04-Evaluar-Calidad`,
        "POST",
        `{{baseUrl}}/iot/calidad/{{${esc.varName}}}/evaluar`,
        authAdmin(),
        null,
        [],
        evalAssert
    ));

    // E. Verificaciones extra para escenarios >20%
    if (esc.num === "3A" || esc.num === "3B") {
        // RF-57: alerta técnica exigida por el requerimiento. Documenta INC-M03-RF57-NOT-EMITTED.
        items.push(makeItem(
            `${esc.num}.05-Verificar-Alerta-RF57`,
            "POST",
            "{{baseUrl}}/test-control/query",
            authAdmin(),
            { query: `SELECT id_alerta, tipo_alerta, severidad FROM modulo3.alertas WHERE id_telemetria = {{${esc.varName}}}` },
            [],
            [
                `pm.test("${esc.num}: [INC-M03-RF57] alerta técnica emitida (esperada)", function () {`,
                '    pm.response.to.have.status(200);',
                '    const rows = (pm.response.json().data || []);',
                '    pm.expect(rows.length, "INC-M03-RF57-NOT-EMITTED: EvaluarCalidad no emite alerta técnica al superar 20%").to.be.above(0);',
                '});'
            ]
        ));

        // RF-63: bitácora
        items.push(makeItem(
            `${esc.num}.06-Verificar-Bitacora-RF63`,
            "POST",
            "{{baseUrl}}/test-control/query",
            authAdmin(),
            { query: `SELECT tipo_evento, componente_origen FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id = '{{${esc.varName}}}' ORDER BY id_evento DESC LIMIT 1` },
            [],
            [
                `pm.test("${esc.num}: bitácora RF-63 con EVALUACION_CALIDAD_COMPLETADA", function () {`,
                '    pm.response.to.have.status(200);',
                '    const rows = (pm.response.json().data || []);',
                '    pm.expect(rows.length).to.be.above(0);',
                '    pm.expect(rows[0].tipo_evento).to.equal("EVALUACION_CALIDAD_COMPLETADA");',
                '    pm.expect(rows[0].componente_origen).to.equal("RF-62");',
                '});'
            ]
        ));

        // D7: un solo VIGENTE por lectura
        items.push(makeItem(
            `${esc.num}.07-Verificar-D7`,
            "POST",
            "{{baseUrl}}/test-control/query",
            authAdmin(),
            { query: `SELECT COUNT(*) AS n FROM modulo3.telemetria_calidad WHERE id_telemetria = {{${esc.varName}}} AND estado_evaluacion = 'VIGENTE'` },
            [],
            [
                `pm.test("${esc.num}: D7 (exactamente 1 VIGENTE)", function () {`,
                '    pm.response.to.have.status(200);',
                '    const rows = (pm.response.json().data || []);',
                '    pm.expect(parseInt(rows[0].n, 10)).to.equal(1);',
                '});'
            ]
        ));
    }

    return { name: `Escenario-${esc.num}-drift-${esc.drift}%`, item: items };
}

const folders = [
    { name: "00-Preflight-Autosiembra", item: preflight },
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
        _postman_id: "tc-m03-g167-v3-autosiembra",
        name: "TC-M03-G167 - Drift fronteras RF-62 (autosiembra)",
        description: "Suite autosuficiente. Crea finca/área/dispositivo/sensor en sandbox, calibra por escenario, ingesta 20 lecturas + 1 evaluada, evalúa y verifica oráculo. Rollback al final.",
        schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    event: [
        {
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: [
                    '// Pre-request de colección: resuelve run_id y sandbox_secret desde CUALQUIER scope',
                    '// (env, collection, global). Usar pm.variables.get() en lugar de pm.collectionVariables.get()',
                    '// porque --env-var escribe en el scope Environment, no en Collection.',
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
        { key: "id_tipo_dispositivo", value: "" },
        { key: "tipo_area_nombre", value: "" },
        { key: "id_finca", value: "" },
        { key: "id_infraestructura", value: "" },
        { key: "device_id", value: "" },
        { key: "device_serial", value: "" },
        { key: "sensor_id", value: "" },
        { key: "id_tel_1a", value: "" },
        { key: "id_tel_1b", value: "" },
        { key: "id_tel_1c", value: "" },
        { key: "id_tel_2a", value: "" },
        { key: "id_tel_2b", value: "" },
        { key: "id_tel_3a", value: "" },
        { key: "id_tel_3b", value: "" },
        { key: "finca_nombre", value: "" },
        { key: "area_nombre", value: "" },
        { key: "device_nombre", value: "" }
    ],
    item: folders
};

const target = path.join(__dirname, "test_tc_m03_g167.json");
fs.writeFileSync(target, JSON.stringify(collection, null, 2), "utf8");

let total = 0;
folders.forEach(f => total += f.item.length);
console.log(`Colección generada: ${target}`);
console.log(`Carpetas: ${folders.length}, Requests: ${total}`);
