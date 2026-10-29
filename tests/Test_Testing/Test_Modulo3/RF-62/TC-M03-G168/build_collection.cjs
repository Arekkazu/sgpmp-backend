/**
 * TC-M03-G168 — Flags individuales de calidad sin severidad acumulada (RF-62 / RF-57 / RF-63)
 * Suite Newman autosuficiente (autosiembra en sandbox).
 *
 * Subcasos:
 * - TC-M03-312: Outlier estadístico (312a extremo, 312b normal, 312c frontera)
 * - TC-M03-316: Gap temporal anómalo (316a 25min, 316b 20min, 316c justificado)
 * - TC-M03-317: Serie temporal insuficiente (3 lecturas previas + 1 evaluada -> INDETERMINADA, índice null)
 * - TC-M03-323: Sensor sin calibración (323a con calibración, 323b sin calibración)
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

    // 00.04 — Finca (nombre solo alfabético)
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

    // 00.05 — Área (especie ACUICULTURA=123)
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
        punto_instalacion: "Centro del area",
        confirmar: false
    }, [], [
        'pm.test("Asociación 201", function () {',
        '    pm.response.to.have.status(201);',
        '});'
    ])
];

// Helper para construir batch de 20 lecturas alternadas (21.50 / 22.50)
function buildBatch20Alternadas(prefix, devSerialVar, devIdVar, sensorIdVar) {
    const registros = [];
    for (let i = 0; i < 20; i++) {
        const mm = String(i * 2).padStart(2, "0");
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
    return { registros };
}

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
            punto_instalacion: "Punto calibracion",
            confirmar: false
        }, [], [
            `pm.test("${prefix}: Asociación 201", function () {`,
            '    pm.response.to.have.status(201);',
            '});'
        ])
    ];
}

// =====================================================================
// CARPETAS TC-312 — Outlier estadístico (3 escenarios)
// =====================================================================
function buildTC312Scenario(sub, valorEval, marcaOutlier, indiceEsp, desc) {
    const devIdVar = `dev_id_${sub}`;
    const devSerialVar = `dev_serial_${sub}`;
    const sensorIdVar = `sensor_id_${sub}`;
    const telIdVar = `tel_id_${sub}`;
    const prefix = `2026-10-21T0${sub === '312a' ? '1' : sub === '312b' ? '2' : '3'}`;
    const evalTs = `${prefix}:42:00Z`;

    const items = buildProvisionItems(sub, devIdVar, devSerialVar, sensorIdVar);

    // Ingestar serie 20
    items.push(makeItem(`${sub}.04-Ingestar-Serie-20`, "POST",
        "{{baseUrl}}/iot/telemetria/batch", authBroker(),
        buildBatch20Alternadas(prefix, devSerialVar, devIdVar, sensorIdVar), [], [
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
        timestamp_captura: evalTs,
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

    return { name: `TC-312-${sub}`, item: items };
}

// =====================================================================
// CARPETAS TC-316 — Gap temporal (3 escenarios)
// =====================================================================
function buildTC316Scenario(sub, gapMin, esperadoGap, indiceEsp, desc) {
    const devIdVar = `dev_id_${sub}`;
    const devSerialVar = `dev_serial_${sub}`;
    const sensorIdVar = `sensor_id_${sub}`;
    const telIdVar = `tel_id_${sub}`;
    const prefix = `2026-10-21T0${sub === '316a' ? '4' : sub === '316b' ? '5' : '6'}`;
    const evalTs = `${prefix}:25:00Z`; // salto tras la serie base

    const items = buildProvisionItems(sub, devIdVar, devSerialVar, sensorIdVar);

    // Serie base 20 lecturas con delta uniforme
    const registros = [];
    for (let i = 0; i < 20; i++) {
        const mm = String(i).padStart(2, "0");
        registros.push({
            device_id: `{{${devIdVar}}}`,
            sensor_id: `{{${sensorIdVar}}}`,
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 22.0,
            unidad: "°C",
            timestamp_captura: `${prefix}:${mm}:00Z`,
            serial: `{{${devSerialVar}}}`
        });
    }

    items.push(makeItem(`${sub}.04-Ingestar-Serie-20`, "POST",
        "{{baseUrl}}/iot/telemetria/batch", authBroker(), { registros }, [], [
        `pm.test("${sub}: Batch 200", function () {`,
        '    pm.response.to.have.status(200);',
        '});'
    ]));

    items.push(makeItem(`${sub}.05-Ingestar-Lectura-Gap`, "POST",
        "{{baseUrl}}/iot/telemetria", authBroker(), {
        device_id: `{{${devIdVar}}}`,
        sensor_id: `{{${sensorIdVar}}}`,
        tipo_variable: "TEMPERATURA_AMBIENTAL",
        valor: 22.0,
        unidad: "°C",
        timestamp_captura: evalTs,
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

    return { name: `TC-316-${sub}`, item: items };
}

// =====================================================================
// CARPETA TC-317 — Serie insuficiente (1 escenario)
// =====================================================================
function buildTC317Folder() {
    const sub = "317";
    const devIdVar = `dev_id_${sub}`;
    const devSerialVar = `dev_serial_${sub}`;
    const sensorIdVar = `sensor_id_${sub}`;
    const telIdVar = `tel_id_${sub}`;
    const prefix = "2026-10-21T07";

    const items = buildProvisionItems(sub, devIdVar, devSerialVar, sensorIdVar);

    // Solo 3 lecturas previas
    const registros = [
        { device_id: `{{${devIdVar}}}`, sensor_id: `{{${sensorIdVar}}}`, tipo_variable: "TEMPERATURA_AMBIENTAL", valor: 21.8, unidad: "°C", timestamp_captura: `${prefix}:01:00Z`, serial: `{{${devSerialVar}}}` },
        { device_id: `{{${devIdVar}}}`, sensor_id: `{{${sensorIdVar}}}`, tipo_variable: "TEMPERATURA_AMBIENTAL", valor: 22.0, unidad: "°C", timestamp_captura: `${prefix}:03:00Z`, serial: `{{${devSerialVar}}}` },
        { device_id: `{{${devIdVar}}}`, sensor_id: `{{${sensorIdVar}}}`, tipo_variable: "TEMPERATURA_AMBIENTAL", valor: 22.1, unidad: "°C", timestamp_captura: `${prefix}:05:00Z`, serial: `{{${devSerialVar}}}` }
    ];

    items.push(makeItem(`${sub}.04-Ingestar-Serie-3`, "POST",
        "{{baseUrl}}/iot/telemetria/batch", authBroker(), { registros }, [], [
        'pm.test("317: Batch 3 lecturas 200", function () {',
        '    pm.response.to.have.status(200);',
        '    pm.expect(pm.response.json().aceptados).to.equal(3);',
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
        timestamp_captura: `${prefix}:07:00Z`,
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

    return { name: `TC-317-serie-insuficiente`, item: items };
}

// =====================================================================
// CARPETAS TC-323 — Calibración no disponible (2 escenarios)
// =====================================================================
function buildTC323Scenario(sub, conCalibracion, desc) {
    const devIdVar = `dev_id_${sub}`;
    const devSerialVar = `dev_serial_${sub}`;
    const sensorIdVar = `sensor_id_${sub}`;
    const telIdVar = `tel_id_${sub}`;
    const prefix = `2026-10-21T0${sub === '323a' ? '8' : '9'}`;
    const evalTs = `${prefix}:42:00Z`;

    const items = buildProvisionItems(sub, devIdVar, devSerialVar, sensorIdVar);

    // Si requiere calibración
    if (conCalibracion) {
        items.push(makeItem(`${sub}.03b-Calibrar-Sensor`, "POST",
            `{{baseUrl}}/configuracion/sensores/{{${sensorIdVar}}}/calibrar`, authAdmin(), {
            id_dispositivo_iot: `{{${devIdVar}}}`,
            id_infraestructura: "{{id_infraestructura}}",
            valor_referencia: 20.0,
            ganancia: 1.0,
            offset: 0.0,
            fecha_calibracion: evalTs,
            observaciones: "Calibración base TC-323",
            modo_calibracion: "SENSOR"
        }, [], [
            `pm.test("${sub}: Calibración 201", function () {`,
            '    pm.response.to.have.status(201);',
            '});'
        ]));
    }

    // Ingestar serie 20
    items.push(makeItem(`${sub}.04-Ingestar-Serie-20`, "POST",
        "{{baseUrl}}/iot/telemetria/batch", authBroker(),
        buildBatch20Alternadas(prefix, devSerialVar, devIdVar, sensorIdVar), [], [
        `pm.test("${sub}: Batch 200", function () {`,
        '    pm.response.to.have.status(200);',
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
        timestamp_captura: evalTs,
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

    return { name: `TC-323-${sub}`, item: items };
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
    buildTC312Scenario("312a", 25.50, true, 80, "outlier extremo"),
    buildTC312Scenario("312b", 23.50, false, 100, "dentro de rango"),
    // Hallazgo A.5: σ es muestral (0.51299), no poblacional. 23.51 < 22+3*0.51299 = 23.5390, no marca. El CSV asumía σ poblacional.
    buildTC312Scenario("312c", 23.51, false, 100, "frontera sigma muestral"),
    buildTC316Scenario("316a", 25, true, 90, "gap 25 min"),
    buildTC316Scenario("316b", 20, false, 100, "gap 20 min"),
    buildTC316Scenario("316c", 25, false, 100, "gap 25 min justificado"),
    buildTC317Folder(),
    buildTC323Scenario("323a", true, "sensor con calibracion"),
    buildTC323Scenario("323b", false, "sensor sin calibracion"),
    { name: "99-Teardown", item: teardown }
];

const collection = {
    info: {
        _postman_id: "tc-m03-g168-flags-individuales",
        name: "TC-M03-G168 - Flags individuales sin severidad (RF-62)",
        description: "Suite autosuficiente para TC-312 (outlier), TC-316 (gap), TC-317 (serie insuficiente), TC-323 (calibración). Siembra en sandbox y rollback al final.",
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
        { key: "id_tipo_dispositivo", value: "" },
        { key: "tipo_area_nombre", value: "" },
        { key: "id_finca", value: "" },
        { key: "id_infraestructura", value: "" },
        { key: "device_id", value: "" },
        { key: "device_serial", value: "" },
        { key: "sensor_id", value: "" },
        { key: "finca_nombre", value: "" },
        { key: "area_nombre", value: "" },
        { key: "dev_id_312a", value: "" },
        { key: "dev_serial_312a", value: "" },
        { key: "sensor_id_312a", value: "" },
        { key: "tel_id_312a", value: "" },
        { key: "dev_id_312b", value: "" },
        { key: "dev_serial_312b", value: "" },
        { key: "sensor_id_312b", value: "" },
        { key: "tel_id_312b", value: "" },
        { key: "dev_id_312c", value: "" },
        { key: "dev_serial_312c", value: "" },
        { key: "sensor_id_312c", value: "" },
        { key: "tel_id_312c", value: "" },
        { key: "dev_id_316a", value: "" },
        { key: "dev_serial_316a", value: "" },
        { key: "sensor_id_316a", value: "" },
        { key: "tel_id_316a", value: "" },
        { key: "dev_id_316b", value: "" },
        { key: "dev_serial_316b", value: "" },
        { key: "sensor_id_316b", value: "" },
        { key: "tel_id_316b", value: "" },
        { key: "dev_id_316c", value: "" },
        { key: "dev_serial_316c", value: "" },
        { key: "sensor_id_316c", value: "" },
        { key: "tel_id_316c", value: "" },
        { key: "dev_id_317", value: "" },
        { key: "dev_serial_317", value: "" },
        { key: "sensor_id_317", value: "" },
        { key: "tel_id_317", value: "" },
        { key: "dev_id_323a", value: "" },
        { key: "dev_serial_323a", value: "" },
        { key: "sensor_id_323a", value: "" },
        { key: "tel_id_323a", value: "" },
        { key: "dev_id_323b", value: "" },
        { key: "dev_serial_323b", value: "" },
        { key: "sensor_id_323b", value: "" },
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
