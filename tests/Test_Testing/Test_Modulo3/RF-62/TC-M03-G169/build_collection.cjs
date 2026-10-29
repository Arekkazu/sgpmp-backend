/**
 * TC-M03-G169 — Estados de calidad heredados de RF-53 (RF-62 / RF-53 / RF-63)
 * Suite Newman autosuficiente (autosiembra en sandbox).
 *
 * Subcasos:
 * - TC-M03-321: Lectura FUERA_DE_RANGO heredada (índice 0, NO_APTO, fuera_de_rango_rf53=true)
 * - TC-M03-322: Lectura ERROR_CALIBRACION heredada + anomalías múltiples (índice 70 CSV / 80 real)
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

function letrasAleatorias(n) {
    const abc = "abcdefghijklmnopqrstuvwxyz";
    let s = "";
    for (let i = 0; i < n; i++) s += abc[Math.floor(Math.random() * abc.length)];
    return s;
}

// =====================================================================
// CARPETA 00 — PREFLIGHT (autosiembra en sandbox)
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

    // 00.04 — Finca (nombre alfabético)
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

    // 00.05 — Área (especie_id: 2 Trucha Arcoíris -> umbrales 10 a 40 °C activos en DB)
    makeItem("00.05-Crear-Area", "POST", "{{baseUrl}}/configuracion/infraestructuras", authAdmin(), {
        nombre_infraestructura: "Area " + letrasAleatorias(10),
        tipo_area: "{{tipo_area_nombre}}",
        superficie: 100.0,
        finca_id: "{{id_finca}}",
        descripcion_infraestructura: "Area de pruebas estados RF-53",
        especie_id: 2,
        tipo_modelo_asignado: null
    }, [], [
        'pm.test("Área 201", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_infraestructura).to.be.a("number").and.above(0);',
        '    pm.collectionVariables.set("id_infraestructura", r.id_infraestructura);',
        '    pm.collectionVariables.set("area_nombre", r.nombre_infraestructura);',
        '});'
    ]),

    // 00.06 — Dispositivo base
    makeItem("00.06-Crear-Dispositivo", "POST",
        "{{baseUrl}}/configuracion/dispositivos-iot", authAdmin(), {
        serial: "GDEV" + letrasAleatorias(8).toUpperCase(),
        descripcion: "Dispositivo base pruebas",
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
        '});'
    ]),

    // 00.07 — Sensor base (categoria TEMPERATURA)
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
        punto_instalacion: "Centro del estanque",
        confirmar: false
    }, [], [
        'pm.test("Asociación 201", function () {',
        '    pm.response.to.have.status(201);',
        '});'
    ])
];

// Helper para crear dispositivo + sensor dedicados
function buildProvisionItems(prefix, devIdVar, devSerialVar, sensorIdVar) {
    return [
        makeItem(`${prefix}.01-Crear-Dispositivo`, "POST",
            "{{baseUrl}}/configuracion/dispositivos-iot", authAdmin(), {
            serial: "GDEV" + letrasAleatorias(8).toUpperCase(),
            descripcion: `Dispositivo ${prefix}`,
            id_infraestructura: "{{id_infraestructura}}",
            id_tipo_dispositivo: "{{id_tipo_dispositivo}}",
            es_activo: true
        }, [], [
            `pm.test("${prefix}: Dispositivo 201", function () {`,
            '    pm.response.to.have.status(201);',
            '    const r = pm.response.json();',
            `    pm.collectionVariables.set("${devIdVar}", r.id_dispositivo_iot);`,
            `    pm.collectionVariables.set("${devSerialVar}", r.serial);`,
            '});'
        ]),
        makeItem(`${prefix}.02-Crear-Sensor`, "POST",
            `{{baseUrl}}/configuracion/dispositivos-iot/{{${devIdVar}}}/sensores`, authAdmin(), {
            nombre: "Sensor " + letrasAleatorias(10),
            categoria: "TEMPERATURA"
        }, [], [
            `pm.test("${prefix}: Sensor 201", function () {`,
            '    pm.response.to.have.status(201);',
            '    const r = pm.response.json();',
            `    pm.collectionVariables.set("${sensorIdVar}", r.id_sensores);`,
            '});'
        ]),
        makeItem(`${prefix}.03-Asociar-Sensor-Area`, "POST",
            `{{baseUrl}}/configuracion/sensores/{{${sensorIdVar}}}/asociar`, authAdmin(), {
            id_dispositivo_iot: `{{${devIdVar}}}`,
            id_infraestructura: "{{id_infraestructura}}",
            punto_instalacion: "Punto monitoreo",
            confirmar: false
        }, [], [
            `pm.test("${prefix}: Asociación 201", function () {`,
            '    pm.response.to.have.status(201);',
            '});'
        ])
    ];
}

// =====================================================================
// CARPETA TC-321 — FUERA_DE_RANGO (Heredado de RF-53)
// =====================================================================
function buildTC321Folder() {
    const sub = "321";
    const devIdVar = `dev_id_${sub}`;
    const devSerialVar = `dev_serial_${sub}`;
    const sensorIdVar = `sensor_id_${sub}`;
    const telIdVar = `tel_id_${sub}`;
    const ts = "2026-10-22T10:00:00Z";

    const items = buildProvisionItems(sub, devIdVar, devSerialVar, sensorIdVar);

    // 321.03b — Calibrar sensor para que no marque ERROR_CALIBRACION
    items.push(makeItem(`${sub}.03b-Calibrar-Sensor`, "POST",
        `{{baseUrl}}/configuracion/sensores/{{${sensorIdVar}}}/calibrar`, authAdmin(), {
        id_dispositivo_iot: `{{${devIdVar}}}`,
        id_infraestructura: "{{id_infraestructura}}",
        valor_referencia: 20.0,
        ganancia: 1.0,
        offset: 0.0,
        fecha_calibracion: ts,
        observaciones: "Calibración base TC-321",
        modo_calibracion: "SENSOR"
    }, [], [
        'pm.test("321: Calibración 201", function () {',
        '    pm.response.to.have.status(201);',
        '});'
    ]));

    // 321.04 — Ingestar valor 50.00 °C (> umbral max 40 °C de especie 2, dentro de rango físico 100 °C)
    items.push(makeItem(`${sub}.04-Ingestar-Lectura-Fuera-Rango`, "POST",
        "{{baseUrl}}/iot/telemetria", authBroker(), {
        device_id: `{{${devIdVar}}}`,
        sensor_id: `{{${sensorIdVar}}}`,
        tipo_variable: "TEMPERATURA_AMBIENTAL",
        valor: 50.00,
        unidad: "°C",
        timestamp_captura: ts,
        serial: `{{${devSerialVar}}}`
    }, [], [
        'pm.test("321: Ingesta 201 con FUERA_DE_RANGO", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_telemetria).to.be.a("number").and.above(0);',
        '    pm.expect(r.estado_calidad).to.equal("FUERA_DE_RANGO");',
        `    pm.collectionVariables.set("${telIdVar}", r.id_telemetria);`,
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

    return { name: `TC-321-fuera-de-rango`, item: items };
}

// =====================================================================
// CARPETA TC-322 — ERROR_CALIBRACION (Heredado de RF-53 + Anomalías)
// =====================================================================
function buildTC322Folder() {
    const sub = "322";
    const devIdVar = `dev_id_${sub}`;
    const devSerialVar = `dev_serial_${sub}`;
    const sensorIdVar = `sensor_id_${sub}`;
    const telIdVar = `tel_id_${sub}`;
    const prefix = "2026-10-22T11";
    const evalTs = `${prefix}:50:00Z`;

    // Dispositivo y sensor SIN calibrar
    const items = buildProvisionItems(sub, devIdVar, devSerialVar, sensorIdVar);

    // 322.04 — Ingestar lote de 20 lecturas con gap de 25 min previo a la lectura 21
    const registros = [];
    for (let i = 0; i < 20; i++) {
        const mm = String(i).padStart(2, "0");
        const val = (i % 2 === 0) ? 21.50 : 22.50;
        registros.push({
            device_id: `{{${devIdVar}}}`,
            sensor_id: `{{${sensorIdVar}}}`,
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: val,
            unidad: "°C",
            timestamp_captura: `${prefix}:${mm}:00Z`,
            serial: `{{${devSerialVar}}}`
        });
    }

    items.push(makeItem(`${sub}.04-Ingestar-Serie-20-Con-Gap`, "POST",
        "{{baseUrl}}/iot/telemetria/batch", authBroker(), { registros }, [], [
        'pm.test("322: Batch 20 lecturas 200", function () {',
        '    pm.response.to.have.status(200);',
        '    pm.expect(pm.response.json().aceptados).to.equal(20);',
        '});'
    ]));

    // 322.05 — Ingestar lectura 21 evaluada (25.50 °C, salto de 25 min respecto a minuto 20)
    items.push(makeItem(`${sub}.05-Ingestar-Lectura-Evaluada`, "POST",
        "{{baseUrl}}/iot/telemetria", authBroker(), {
        device_id: `{{${devIdVar}}}`,
        sensor_id: `{{${sensorIdVar}}}`,
        tipo_variable: "TEMPERATURA_AMBIENTAL",
        valor: 25.50,
        unidad: "°C",
        timestamp_captura: evalTs,
        serial: `{{${devSerialVar}}}`
    }, [], [
        'pm.test("322: Lectura 21 ingerida 201 con ERROR_CALIBRACION", function () {',
        '    pm.response.to.have.status(201);',
        '    const r = pm.response.json();',
        '    pm.expect(r.id_telemetria).to.be.a("number").and.above(0);',
        '    pm.expect(r.estado_calidad).to.equal("ERROR_CALIBRACION");',
        `    pm.collectionVariables.set("${telIdVar}", r.id_telemetria);`,
        '});'
    ]));

    // 322.06 — Evaluar calidad
    // El oráculo del CSV (70) asume gap implementado. En código actual gap no se detecta -> índice real 80.
    // Se deja 70 para que V2 falle honestamente (documenta INC-M03-G168-GAP-NOT-IMPLEMENTED).
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
        '});'
    ]));

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
            'pm.test("Rollback 200", function () {',
            '    pm.response.to.have.status(200);',
            '});'
        ]
    )
];

const folders = [
    { name: "00-Preflight-Autosiembra", item: preflight },
    buildTC321Folder(),
    buildTC322Folder(),
    { name: "99-Teardown", item: teardown }
];

const collection = {
    info: {
        _postman_id: "tc-m03-g169-estados-heredados",
        name: "TC-M03-G169 - Estados heredados de RF-53 (RF-62)",
        description: "Suite autosuficiente para TC-321 (FUERA_DE_RANGO) y TC-322 (ERROR_CALIBRACION). Siembra en sandbox y rollback al final.",
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
        { key: "id_tipo_dispositivo", value: "" },
        { key: "tipo_area_nombre", value: "" },
        { key: "id_finca", value: "" },
        { key: "id_infraestructura", value: "" },
        { key: "device_id", value: "" },
        { key: "device_serial", value: "" },
        { key: "sensor_id", value: "" },
        { key: "finca_nombre", value: "" },
        { key: "area_nombre", value: "" },
        { key: "dev_id_321", value: "" },
        { key: "dev_serial_321", value: "" },
        { key: "sensor_id_321", value: "" },
        { key: "tel_id_321", value: "" },
        { key: "dev_id_322", value: "" },
        { key: "dev_serial_322", value: "" },
        { key: "sensor_id_322", value: "" },
        { key: "tel_id_322", value: "" }
    ],
    item: folders
};

const target = path.join(__dirname, "test_tc_m03_g169.json");
fs.writeFileSync(target, JSON.stringify(collection, null, 2), "utf8");

let total = 0;
folders.forEach(f => total += f.item.length);
console.log(`Colección generada: ${target}`);
console.log(`Carpetas: ${folders.length}, Requests: ${total}`);
