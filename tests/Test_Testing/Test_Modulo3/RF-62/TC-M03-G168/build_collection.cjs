const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G168
// RF-62: Flags individuales sin escala de severidad (Outlier, Gap, Serie insuficiente, Calibración no disponible)
//
// REGLAS Y REQUISITOS IMPLEMENTADOS:
// 1. SANDBOX: Pre-request a nivel de colección genera run_id ("test-" + {{$guid}}) si está vacío,
//    e inyecta X-Test-Run-Id y X-Sandbox-Secret en cada request.
// 2. LOGIN: POST /sesiones/ con correo_electronico y contrasena; captura token en res.token.
// 3. SERIES: Siembra por POST /iot/telemetria/batch (BUFFER_LOCAL) con intervalo de 10 min.
//    Lecturas evaluadas entran por POST /iot/telemetria individual.
// 4. AISLAMIENTO DE VENTANA: Cada lectura evaluada posee su propio bloque limpio de 20 lecturas base,
//    separados temporalmente (+1 día por bloque / fecha distinta).
// 5. SENSORES GARANTIZADOS: S1 (Outlier y Gaps), S2 (Serie insuficiente, 3 lecturas), S3 (Sin calibración),
//    S4 (Con calibración). Descubrimiento dinámico de hasta 4 sensores o reasignación transparente.
// 6. TC-312: 25.50 (activo=true), 23.50 (activo=false), 23.51 (activo=true, señalando discrepancia
//    σ muestral vs poblacional si falla). Aserciones con closeTo (media ±0.01, k ±0.01, mag ±0.05).
// 7. TC-316: frecuencia_muestreo removida del body; UPDATE en modulo9.sensores / configuracion.
//    Subcasos: (a) gap 25 min -> [DEFECTO CONOCIDO RF-62 Fase 5]; (b) 20 min -> sin flag (100);
//    (c) inactividad RF-60 -> BLOQUEADO (solo console.log, sin pm.test).
// 8. TC-317: S2 con 3 lecturas previas -> serie_insuficiente=true, INDETERMINADA, índice=null.
//    apto_para_ia y apto_para_nic41 solo console.log sin pm.expect.
// 9. TC-323: S3 sin calibración (calibracion_no_disponible=true) y S4 con calibración. Ambos índice 80
//    y comparación de igualdad explícita.
// 10. D7: SELECT final por evaluación importante confirmando exactamente una VIGENTE con [DEFECTO CONOCIDO].
// 11. TEARDOWN: DELETE /test-control/runs/{{run_id}}.

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

// Genera un batch payload de 20 lecturas con intervalo de 10 min
// baseDayStr: "2026-10-20T08"
function buildBatch20Alternada(sensorVar, deviceVar, serialVar, baseDateStr) {
    // 20 lecturas alternadas 21.50 y 22.50 con intervalo de 10 minutos (0 min, 10 min, ... 190 min)
    const registros = [];
    const baseDate = new Date(baseDateStr);
    for (let i = 0; i < 20; i++) {
        const val = (i % 2 === 0) ? 21.5 : 22.5;
        const lecturaDate = new Date(baseDate.getTime() + i * 10 * 60 * 1000);
        registros.push({
            device_id: parseInt(`{{${deviceVar}}}`, 10),
            sensor_id: parseInt(`{{${sensorVar}}}`, 10),
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: val,
            unidad: "°C",
            timestamp_captura: lecturaDate.toISOString(),
            access_key: `{{${serialVar}}}`,
            origen: "BUFFER_LOCAL"
        });
    }
    return { registros };
}

const folders = [];

// ── 00. PREFLIGHT Y DESCUBRIMIENTO DE SENSORES S1..S4 ─────────────────────────
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
        "01-Descubrimiento-Sensores-S1-a-S4",
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: "SELECT s.id_sensores, s.id_dispositivo_iot, d.serial FROM modulo9.sensores s JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot WHERE s.es_activo = true AND d.es_activo = true ORDER BY s.id_sensores ASC LIMIT 4"
        },
        [],
        [
            'pm.test("Status 200 - Descubrimiento de sensores realizado", function () {',
            '    pm.response.to.have.status(200);',
            '    const rows = pm.response.json().data || pm.response.json().rows || [];',
            '    pm.expect(rows.length).to.be.above(0);',
            '    ',
            '    // S1: Outliers y Gaps',
            '    pm.collectionVariables.set("s1_sensor_id", rows[0].id_sensores);',
            '    pm.collectionVariables.set("s1_device_id", rows[0].id_dispositivo_iot);',
            '    pm.collectionVariables.set("s1_device_serial", rows[0].serial);',
            '    ',
            '    // S2: Serie corta (<20)',
            '    const r1 = rows[1] || rows[0];',
            '    pm.collectionVariables.set("s2_sensor_id", r1.id_sensores);',
            '    pm.collectionVariables.set("s2_device_id", r1.id_dispositivo_iot);',
            '    pm.collectionVariables.set("s2_device_serial", r1.serial);',
            '    ',
            '    // S3: Sin calibración',
            '    const r2 = rows[2] || rows[1] || rows[0];',
            '    pm.collectionVariables.set("s3_sensor_id", r2.id_sensores);',
            '    pm.collectionVariables.set("s3_device_id", r2.id_dispositivo_iot);',
            '    pm.collectionVariables.set("s3_device_serial", r2.serial);',
            '    ',
            '    // S4: Con calibración',
            '    const r3 = rows[3] || rows[2] || rows[0];',
            '    pm.collectionVariables.set("s4_sensor_id", r3.id_sensores);',
            '    pm.collectionVariables.set("s4_device_id", r3.id_dispositivo_iot);',
            '    pm.collectionVariables.set("s4_device_serial", r3.serial);',
            '    ',
            '    if (rows.length < 4) {',
            '        console.log("[TENTATIVO] Se descubrieron menos de 4 sensores independientes. Algunos sensores se reasignan en ventanas aisladas.");',
            '    }',
            '});'
        ]
    ),
    makeItem(
        "02-Verificar-Sin-Lecturas-Posteriores-S1",
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: "SELECT COUNT(*) AS total FROM modulo3.telemetrias WHERE id_sensor = {{s1_sensor_id}} AND timestamp_captura >= '2026-10-20T00:00:00Z'"
        },
        [],
        [
            'pm.test("Status 200 - Ventana de prueba S1 limpia", function () {',
            '    pm.response.to.have.status(200);',
            '    const rows = pm.response.json().data || pm.response.json().rows || [];',
            '    const total = parseInt((rows[0] && rows[0].total) || 0, 10);',
            '    pm.expect(total).to.equal(0);',
            '});'
        ]
    )
];

folders.push({
    name: "00-Preflight-y-Descubrimiento",
    item: folder0Items
});

// ── 01. TC-M03-312: OUTLIER ESTADÍSTICO (BLOQUES LIMPIOS POR LECTURA) ───────────

// Bloque 1A: Lectura 25.50 (Día 2026-10-20, lecturas 00:00 a 03:10 -> lectura evaluada 03:20)
const batchOutlier1A = buildBatch20Alternada("s1_sensor_id", "s1_device_id", "s1_device_serial", "2026-10-20T00:00:00Z");
const folderOutlierItems = [
    // Subcaso 25.50: Outlier activo (> 3 sigma)
    makeItem(
        "10-E1A-Siembra-Batch-20-Lecturas-Base-25.50",
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        [],
        batchOutlier1A,
        [],
        [
            'pm.test("Status 200 - Batch 20 lecturas base 1A", function () {',
            '    pm.response.to.have.status(200);',
            '    const res = pm.response.json();',
            '    pm.expect(res.aceptados).to.equal(20);',
            '});'
        ]
    ),
    makeItem(
        "11-E1A-Ingesta-Lectura-Evaluada-25.50",
        "POST",
        "{{baseUrl}}/iot/telemetria",
        [],
        {
            device_id: "{{s1_device_id}}",
            sensor_id: "{{s1_sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 25.50,
            unidad: "°C",
            timestamp_captura: "2026-10-20T03:20:00Z",
            access_key: "{{s1_device_serial}}",
            origen: "BUFFER_LOCAL"
        },
        [],
        [
            'pm.test("Status 201 - Ingesta lectura 25.50", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    pm.collectionVariables.set("id_tel_outlier_2550", res.id_telemetria);',
            '});'
        ]
    ),
    makeItem(
        "12-E1A-Evaluar-Outlier-25.50-Activo",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_outlier_2550}}/evaluar",
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("Status 201 - Outlier 25.50 activo: Descuento -20, Índice 80, APTO", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    const flags = res.flags_detectados || {};',
            '    const outlier = flags.outlier_estadistico || {};',
            '    pm.expect(outlier.activo).to.equal(true);',
            '    pm.expect(outlier.causa).to.equal("ESTADISTICO");',
            '    pm.expect(outlier.media_serie).to.be.closeTo(22.0, 0.01);',
            '    pm.expect(outlier.k_utilizado).to.be.closeTo(3.0, 0.01);',
            '    pm.expect(outlier.magnitud_desviacion).to.be.closeTo(6.82, 0.05);',
            '    pm.expect(res.indice_calidad).to.equal(80);',
            '    pm.expect(res.clasificacion_calidad).to.equal("APTO");',
            '    pm.expect(res.apto_para_ia).to.equal(true);',
            '    pm.expect(res.apto_para_nic41).to.equal(true);',
            '    pm.expect(res.estado_evaluacion).to.equal("VIGENTE");',
            '});'
        ]
    ),

    // Bloque 1B: Lectura 23.50 (Día 2026-10-21, bloque completamente separado)
    makeItem(
        "13-E1B-Siembra-Batch-20-Lecturas-Base-23.50",
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        [],
        buildBatch20Alternada("s1_sensor_id", "s1_device_id", "s1_device_serial", "2026-10-21T00:00:00Z"),
        [],
        [
            'pm.test("Status 200 - Batch 20 lecturas base 1B", function () {',
            '    pm.response.to.have.status(200);',
            '    pm.expect(pm.response.json().aceptados).to.equal(20);',
            '});'
        ]
    ),
    makeItem(
        "14-E1B-Ingesta-Lectura-Evaluada-23.50",
        "POST",
        "{{baseUrl}}/iot/telemetria",
        [],
        {
            device_id: "{{s1_device_id}}",
            sensor_id: "{{s1_sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 23.50,
            unidad: "°C",
            timestamp_captura: "2026-10-21T03:20:00Z",
            access_key: "{{s1_device_serial}}",
            origen: "BUFFER_LOCAL"
        },
        [],
        [
            'pm.test("Status 201 - Ingesta lectura frontera 23.50", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    pm.collectionVariables.set("id_tel_frontera_2350", res.id_telemetria);',
            '});'
        ]
    ),
    makeItem(
        "15-E1B-Evaluar-Frontera-23.50-Inactivo",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_frontera_2350}}/evaluar",
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("Status 201 - Frontera 23.50 inactiva: Índice 100, APTO", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    const flags = res.flags_detectados || {};',
            '    const outlier = flags.outlier_estadistico || {};',
            '    pm.expect(outlier.activo).to.be.oneOf([false, undefined]);',
            '    pm.expect(res.indice_calidad).to.equal(100);',
            '    pm.expect(res.clasificacion_calidad).to.equal("APTO");',
            '    pm.expect(res.estado_evaluacion).to.equal("VIGENTE");',
            '});'
        ]
    ),

    // Bloque 1C: Lectura 23.51 (Día 2026-10-22, bloque limpio separado)
    makeItem(
        "16-E1C-Siembra-Batch-20-Lecturas-Base-23.51",
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        [],
        buildBatch20Alternada("s1_sensor_id", "s1_device_id", "s1_device_serial", "2026-10-22T00:00:00Z"),
        [],
        [
            'pm.test("Status 200 - Batch 20 lecturas base 1C", function () {',
            '    pm.response.to.have.status(200);',
            '    pm.expect(pm.response.json().aceptados).to.equal(20);',
            '});'
        ]
    ),
    makeItem(
        "17-E1C-Ingesta-Lectura-Evaluada-23.51",
        "POST",
        "{{baseUrl}}/iot/telemetria",
        [],
        {
            device_id: "{{s1_device_id}}",
            sensor_id: "{{s1_sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 23.51,
            unidad: "°C",
            timestamp_captura: "2026-10-22T03:20:00Z",
            access_key: "{{s1_device_serial}}",
            origen: "BUFFER_LOCAL"
        },
        [],
        [
            'pm.test("Status 201 - Ingesta lectura frontera 23.51", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    pm.collectionVariables.set("id_tel_frontera_2351", res.id_telemetria);',
            '});'
        ]
    ),
    makeItem(
        "18-E1C-Evaluar-Frontera-23.51-Outlier",
        "POST",
        `{{baseUrl}}/iot/calidad/{{id_tel_frontera_2351}}/evaluar`,
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("[DISCREPANCIA RF-62 σ muestral vs poblacional] Lectura 23.51 activa outlier estadístico", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    const flags = res.flags_detectados || {};',
            '    const outlier = flags.outlier_estadistico || {};',
            '    console.log("[LOG TC-312] σ aplicado:", outlier.desviacion_estandar, "media:", outlier.media_serie, "magnitud:", outlier.magnitud_desviacion);',
            '    // NOTA NORMATIVA TC-312: El caso exige activo=true (asumiendo σ poblacional = 0.50 -> 22 + 3*0.50 = 23.50).',
            '    // Con statistics.stdev (σ muestral = 0.51299), el umbral es 23.539 -> 23.51 resulta inactivo.',
            '    // La prueba exige activo=true evidenciando la discrepancia.',
            '    pm.expect(outlier.activo, "Discrepancia: 23.51 no supera 3*s_muestral (23.539) pero sí 3*sigma_poblacional (23.500)").to.equal(true);',
            '    pm.expect(res.indice_calidad).to.equal(80);',
            '});'
        ]
    ),
    makeItem(
        "19-E1-Documentar-Sigma-Aplicado",
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: "SELECT id_evaluacion, flags_detectados->'outlier_estadistico' AS outlier FROM modulo3.telemetria_calidad WHERE id_telemetria = {{id_tel_outlier_2550}}"
        },
        [],
        [
            'pm.test("Status 200 - Documentación de sigma estadístico en base de datos", function () {',
            '    pm.response.to.have.status(200);',
            '    const rows = pm.response.json().data || pm.response.json().rows || [];',
            '    pm.expect(rows.length).to.be.above(0);',
            '    console.log("[AUDITORIA ESTADISTICA] Flags outlier:", JSON.stringify(rows[0].outlier));',
            '});'
        ]
    )
];

folders.push({
    name: "01-TC-M03-312-Outlier-Estadistico",
    item: folderOutlierItems
});

// ── 02. TC-M03-316: GAP TEMPORAL ANÓMALO (BLOQUES LIMPIOS A 10 MIN) ─────────────
const folderGapItems = [
    // Subcaso (a): Gap 25 min (Día 2026-10-23, serie 00:00 a 03:10 -> lectura evaluada 03:35 -> +25 min)
    makeItem(
        "20-E2A-Siembra-Batch-20-Lecturas-Base-Gap25",
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        [],
        buildBatch20Alternada("s1_sensor_id", "s1_device_id", "s1_device_serial", "2026-10-23T00:00:00Z"),
        [],
        [
            'pm.test("Status 200 - Batch 20 lecturas base 2A", function () {',
            '    pm.response.to.have.status(200);',
            '    pm.expect(pm.response.json().aceptados).to.equal(20);',
            '});'
        ]
    ),
    makeItem(
        "21-E2A-Ingesta-Lectura-Evaluada-Gap-25min",
        "POST",
        "{{baseUrl}}/iot/telemetria",
        [],
        {
            device_id: "{{s1_device_id}}",
            sensor_id: "{{s1_sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 22.0,
            unidad: "°C",
            timestamp_captura: "2026-10-23T03:35:00Z", // 25 min tras las 03:10 (lectura 20)
            access_key: "{{s1_device_serial}}",
            origen: "BUFFER_LOCAL"
        },
        [],
        [
            'pm.test("Status 201 - Ingesta lectura gap 25 min", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    pm.collectionVariables.set("id_tel_gap_25", res.id_telemetria);',
            '});'
        ]
    ),
    makeItem(
        "22-E2A-Evaluar-Gap-25min-Defecto-Conocido",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_gap_25}}/evaluar",
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("[DEFECTO CONOCIDO RF-62 Fase 5] Gap temporal anómalo activo: gap_real=25, esperado=10, índice 90", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    const flags = res.flags_detectados || {};',
            '    const gap = flags.gap_temporal_anomalo || {};',
            '    // NOTA NORMATIVA: En EvaluarCalidadTelemetriaUseCase:195 la Fase 5 no está conectada.',
            '    // El test exige la detección para evidenciar el defecto conocido en la Fase 5.',
            '    pm.expect(gap.activo, "Defecto Fase 5: Motor de calidad no evalúa gap temporal").to.equal(true);',
            '    pm.expect(gap.gap_real_minutos).to.equal(25);',
            '    pm.expect(gap.gap_esperado_minutos).to.equal(10);',
            '    pm.expect(res.indice_calidad).to.equal(90);',
            '});'
        ]
    ),

    // Subcaso (b): Gap normal 20 min (Día 2026-10-24, serie 00:00 a 03:10 -> lectura evaluada 03:30 -> +20 min, <= 2x esperado)
    makeItem(
        "23-E2B-Siembra-Batch-20-Lecturas-Base-Gap20",
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        [],
        buildBatch20Alternada("s1_sensor_id", "s1_device_id", "s1_device_serial", "2026-10-24T00:00:00Z"),
        [],
        [
            'pm.test("Status 200 - Batch 20 lecturas base 2B", function () {',
            '    pm.response.to.have.status(200);',
            '    pm.expect(pm.response.json().aceptados).to.equal(20);',
            '});'
        ]
    ),
    makeItem(
        "24-E2B-Ingesta-Lectura-Evaluada-Gap-20min",
        "POST",
        "{{baseUrl}}/iot/telemetria",
        [],
        {
            device_id: "{{s1_device_id}}",
            sensor_id: "{{s1_sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 22.0,
            unidad: "°C",
            timestamp_captura: "2026-10-24T03:30:00Z", // 20 min tras las 03:10
            access_key: "{{s1_device_serial}}",
            origen: "BUFFER_LOCAL"
        },
        [],
        [
            'pm.test("Status 201 - Ingesta lectura gap 20 min", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    pm.collectionVariables.set("id_tel_gap_20", res.id_telemetria);',
            '});'
        ]
    ),
    makeItem(
        "25-E2B-Evaluar-Gap-20min-Sin-Flag",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_gap_20}}/evaluar",
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("Status 201 - Intervalo normal (20 min <= 2x): Sin flag gap, Índice 100", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    const flags = res.flags_detectados || {};',
            '    const gap = flags.gap_temporal_anomalo || {};',
            '    pm.expect(gap.activo).to.be.oneOf([false, undefined]);',
            '    pm.expect(res.indice_calidad).to.equal(100);',
            '    pm.expect(res.clasificacion_calidad).to.equal("APTO");',
            '});'
        ]
    ),

    // Subcaso (c): Período de inactividad RF-60 (BLOQUEADO: sin pm.test, solo console.log)
    makeItem(
        "26-E2C-Subcaso-Inactividad-RF60-BLOQUEADO",
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: "SELECT 1 AS bloqueado"
        },
        [],
        [
            '// SUB-CASO BLOQUEADO: No contiene pm.test para no alterar el cómputo de pruebas aprobadas en el scanner.',
            'console.log("[BLOQUEADO] TC-M03-316(c): El motor de calidad no consulta períodos de inactividad de RF-60 en Fase 5. Sub-caso bloqueado por falta de implementación.");'
        ]
    )
];

folders.push({
    name: "02-TC-M03-316-Gap-Temporal-Anomalo",
    item: folderGapItems
});

// ── 03. TC-M03-317: SERIE INSUFICIENTE (< 20 LECTURAS) ──────────────────────────
const folderSerieCortaItems = [
    // Siembra de solo 3 lecturas en S2 mediante batch
    makeItem(
        "30-E3-Siembra-Batch-3-Lecturas-S2",
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        [],
        {
            registros: [
                {
                    device_id: parseInt("{{s2_device_id}}", 10),
                    sensor_id: parseInt("{{s2_sensor_id}}", 10),
                    tipo_variable: "TEMPERATURA_AMBIENTAL",
                    valor: 20.1,
                    unidad: "°C",
                    timestamp_captura: "2026-10-25T01:00:00Z",
                    access_key: "{{s2_device_serial}}",
                    origen: "BUFFER_LOCAL"
                },
                {
                    device_id: parseInt("{{s2_device_id}}", 10),
                    sensor_id: parseInt("{{s2_sensor_id}}", 10),
                    tipo_variable: "TEMPERATURA_AMBIENTAL",
                    valor: 20.2,
                    unidad: "°C",
                    timestamp_captura: "2026-10-25T01:10:00Z",
                    access_key: "{{s2_device_serial}}",
                    origen: "BUFFER_LOCAL"
                },
                {
                    device_id: parseInt("{{s2_device_id}}", 10),
                    sensor_id: parseInt("{{s2_sensor_id}}", 10),
                    tipo_variable: "TEMPERATURA_AMBIENTAL",
                    valor: 20.3,
                    unidad: "°C",
                    timestamp_captura: "2026-10-25T01:20:00Z",
                    access_key: "{{s2_device_serial}}",
                    origen: "BUFFER_LOCAL"
                }
            ]
        },
        [],
        [
            'pm.test("Status 200 - Batch 3 lecturas en S2", function () {',
            '    pm.response.to.have.status(200);',
            '    pm.expect(pm.response.json().aceptados).to.equal(3);',
            '});'
        ]
    ),
    makeItem(
        "31-E3-Ingesta-Lectura-Evaluada-S2",
        "POST",
        "{{baseUrl}}/iot/telemetria",
        [],
        {
            device_id: "{{s2_device_id}}",
            sensor_id: "{{s2_sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 20.4,
            unidad: "°C",
            timestamp_captura: "2026-10-25T01:30:00Z",
            access_key: "{{s2_device_serial}}",
            origen: "BUFFER_LOCAL"
        },
        [],
        [
            'pm.test("Status 201 - Ingesta lectura evaluada S2", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    pm.collectionVariables.set("id_tel_s2_eval", res.id_telemetria);',
            '});'
        ]
    ),
    makeItem(
        "32-E3-Evaluar-Serie-Insuficiente-INDETERMINADA",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_s2_eval}}/evaluar",
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("Status 201 - Serie insuficiente: Clasificación INDETERMINADA, Índice null, sin flags de anomalía", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    const flags = res.flags_detectados || {};',
            '    ',
            '    // Aserciones estrictas requeridas por TC-317',
            '    pm.expect(flags.serie_insuficiente && flags.serie_insuficiente.activo).to.equal(true);',
            '    pm.expect(res.clasificacion_calidad).to.equal("INDETERMINADA");',
            '    pm.expect(res.indice_calidad).to.equal(null);',
            '    ',
            '    // Sin flags de anomalía calculados',
            '    pm.expect(flags.sensor_congelado).to.be.undefined;',
            '    pm.expect(flags.outlier_estadistico).to.be.undefined;',
            '    pm.expect(flags.posible_drift).to.be.undefined;',
            '    pm.expect(flags.gap_temporal_anomalo).to.be.undefined;',
            '    ',
            '    // Aptitud IA y NIC41: Solo console.log del valor observado sin pm.expect',
            '    console.log("[OBSERVACION TC-317] Aptitud IA observada:", res.apto_para_ia, "Aptitud NIC41 observada:", res.apto_para_nic41);',
            '});'
        ]
    )
];

folders.push({
    name: "03-TC-M03-317-Serie-Insuficiente",
    item: folderSerieCortaItems
});

// ── 04. TC-M03-323: CALIBRACIÓN NO DISPONIBLE VS DISPONIBLE ─────────────────────
const folderCalibracionItems = [
    // Precondición S3: Limpiar calibración en modulo9.calibraciones si existiera
    makeItem(
        "40-E4A-Garantizar-S3-Sin-Calibracion",
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: "DELETE FROM modulo9.calibraciones WHERE id_sensor = {{s3_sensor_id}}"
        },
        [],
        [
            'pm.test("Status 200 - Calibraciones previas de S3 limpiadas en sandbox", function () {',
            '    pm.response.to.have.status(200);',
            '});'
        ]
    ),
    // Siembra batch 20 lecturas en S3
    makeItem(
        "41-E4A-Siembra-Batch-20-Lecturas-S3",
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        [],
        buildBatch20Alternada("s3_sensor_id", "s3_device_id", "s3_device_serial", "2026-10-26T00:00:00Z"),
        [],
        [
            'pm.test("Status 200 - Batch 20 lecturas en S3", function () {',
            '    pm.response.to.have.status(200);',
            '    pm.expect(pm.response.json().aceptados).to.equal(20);',
            '});'
        ]
    ),
    // Ingesta lectura 25.50 en S3
    makeItem(
        "42-E4A-Ingesta-Lectura-25.50-S3-Sin-Calibracion",
        "POST",
        "{{baseUrl}}/iot/telemetria",
        [],
        {
            device_id: "{{s3_device_id}}",
            sensor_id: "{{s3_sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 25.50,
            unidad: "°C",
            timestamp_captura: "2026-10-26T03:20:00Z",
            access_key: "{{s3_device_serial}}",
            origen: "BUFFER_LOCAL"
        },
        [],
        [
            'pm.test("Status 201 - Ingesta lectura 25.50 en S3", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    pm.collectionVariables.set("id_tel_s3_sin_cal", res.id_telemetria);',
            '});'
        ]
    ),
    // Evaluar calidad S3
    makeItem(
        "43-E4A-Evaluar-S3-Calibracion-No-Disponible",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_s3_sin_cal}}/evaluar",
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("Status 201 - S3 Calibración no disponible: activo=true, sin posible_drift, Índice 80", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    const flags = res.flags_detectados || {};',
            '    ',
            '    pm.expect(flags.calibracion_no_disponible && flags.calibracion_no_disponible.activo).to.equal(true);',
            '    pm.expect(flags.posible_drift).to.be.undefined;',
            '    pm.expect(res.indice_calidad).to.equal(80);',
            '    pm.collectionVariables.set("indice_s3_sin_cal", res.indice_calidad);',
            '});'
        ]
    ),

    // Precondición S4: Configurar calibración nominal (ganancia=1.0, offset=0.0)
    makeItem(
        "44-E4B-Configurar-Calibracion-S4",
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: "INSERT INTO modulo9.calibraciones (id_dispositivo_iot, id_sensor, ganancia, offset_calibracion, fecha_calibracion, valor_referencia, id_usuario) VALUES ({{s4_device_id}}, {{s4_sensor_id}}, 1.0, 0.0, NOW(), 22.0, 1)"
        },
        [],
        [
            'pm.test("Status 200 - Calibración nominal configurada para S4", function () {',
            '    pm.response.to.have.status(200);',
            '});'
        ]
    ),
    // Siembra batch 20 lecturas en S4
    makeItem(
        "45-E4B-Siembra-Batch-20-Lecturas-S4",
        "POST",
        "{{baseUrl}}/iot/telemetria/batch",
        [],
        buildBatch20Alternada("s4_sensor_id", "s4_device_id", "s4_device_serial", "2026-10-27T00:00:00Z"),
        [],
        [
            'pm.test("Status 200 - Batch 20 lecturas en S4", function () {',
            '    pm.response.to.have.status(200);',
            '    pm.expect(pm.response.json().aceptados).to.equal(20);',
            '});'
        ]
    ),
    // Ingesta lectura 25.50 en S4
    makeItem(
        "46-E4B-Ingesta-Lectura-25.50-S4-Con-Calibracion",
        "POST",
        "{{baseUrl}}/iot/telemetria",
        [],
        {
            device_id: "{{s4_device_id}}",
            sensor_id: "{{s4_sensor_id}}",
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 25.50,
            unidad: "°C",
            timestamp_captura: "2026-10-27T03:20:00Z",
            access_key: "{{s4_device_serial}}",
            origen: "BUFFER_LOCAL"
        },
        [],
        [
            'pm.test("Status 201 - Ingesta lectura 25.50 en S4", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    pm.collectionVariables.set("id_tel_s4_con_cal", res.id_telemetria);',
            '});'
        ]
    ),
    // Evaluar calidad S4 y Comparación de Igualdad de Índices
    makeItem(
        "47-E4B-Evaluar-S4-y-Comparar-Indices-Iguales",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_s4_con_cal}}/evaluar",
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("Status 201 - S4 Calibrado: calibracion_no_disponible=false, Índice 80 idéntico a S3", function () {',
            '    pm.response.to.have.status(201);',
            '    const res = pm.response.json();',
            '    const flags = res.flags_detectados || {};',
            '    ',
            '    const calNoDisp = flags.calibracion_no_disponible || {};',
            '    pm.expect(calNoDisp.activo).to.be.oneOf([false, undefined]);',
            '    pm.expect(res.indice_calidad).to.equal(80);',
            '    ',
            '    // Comparación explícita de igualdad de índices entre S3 y S4',
            '    const idxS3 = parseInt(pm.collectionVariables.get("indice_s3_sin_cal"), 10);',
            '    pm.expect(res.indice_calidad, "Índice de sensor calibrado vs no calibrado debe ser idéntico (80)").to.equal(idxS3);',
            '});'
        ]
    )
];

folders.push({
    name: "04-TC-M03-323-Calibracion-No-Disponible",
    item: folderCalibracionItems
});

// ── 05. VERIFICACIÓN INVARIANTE VIGENTE D7 ────────────────────────────────────
const folderD7Items = [
    makeItem(
        "50-D7-Verificar-Invariante-VIGENTE-Outlier-2550",
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: "SELECT COUNT(*) AS total_vigentes FROM modulo3.telemetria_calidad WHERE id_telemetria = {{id_tel_outlier_2550}} AND estado_evaluacion = 'VIGENTE'"
        },
        [],
        [
            'pm.test("[DEFECTO CONOCIDO D7] Invariante una sola VIGENTE para lectura 25.50", function () {',
            '    pm.response.to.have.status(200);',
            '    const rows = pm.response.json().data || pm.response.json().rows || [];',
            '    const vigentes = parseInt((rows[0] && rows[0].total_vigentes) || 0, 10);',
            '    pm.expect(vigentes).to.equal(1);',
            '});'
        ]
    ),
    makeItem(
        "51-D7-Verificar-Invariante-VIGENTE-S4-Calibrado",
        "POST",
        "{{baseUrl}}/test-control/query",
        makeAuthHeaders(),
        {
            query: "SELECT COUNT(*) AS total_vigentes FROM modulo3.telemetria_calidad WHERE id_telemetria = {{id_tel_s4_con_cal}} AND estado_evaluacion = 'VIGENTE'"
        },
        [],
        [
            'pm.test("[DEFECTO CONOCIDO D7] Invariante una sola VIGENTE para lectura S4", function () {',
            '    pm.response.to.have.status(200);',
            '    const rows = pm.response.json().data || pm.response.json().rows || [];',
            '    const vigentes = parseInt((rows[0] && rows[0].total_vigentes) || 0, 10);',
            '    pm.expect(vigentes).to.equal(1);',
            '});'
        ]
    )
];

folders.push({
    name: "05-Verificacion-Invariante-D7",
    item: folderD7Items
});

// ── 99. TEARDOWN Y ROLLBACK DEL SANDBOX ────────────────────────────────────────
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

// Construcción del objeto de colección Postman v2.1.0
const collection = {
    info: {
        _postman_id: "tc-m03-g168-flags-individuales-v2",
        name: "TC-M03-G168 - Flags Individuales sin Escala RF-62",
        description: "Suite automatizada Newman para TC-M03-G168 (RF-62 / RF-57 / RF-63). Cobertura de flags individuales sin escala: Outlier estadístico (TC-312), Gap temporal (TC-316), Serie insuficiente (TC-317) y Calibración no disponible (TC-323).",
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
        { key: "s1_sensor_id", value: "" },
        { key: "s1_device_id", value: "" },
        { key: "s1_device_serial", value: "" },
        { key: "s2_sensor_id", value: "" },
        { key: "s2_device_id", value: "" },
        { key: "s2_device_serial", value: "" },
        { key: "s3_sensor_id", value: "" },
        { key: "s3_device_id", value: "" },
        { key: "s3_device_serial", value: "" },
        { key: "s4_sensor_id", value: "" },
        { key: "s4_device_id", value: "" },
        { key: "s4_device_serial", value: "" },
        { key: "id_tel_outlier_2550", value: "" },
        { key: "id_tel_frontera_2350", value: "" },
        { key: "id_tel_frontera_2351", value: "" },
        { key: "id_tel_gap_25", value: "" },
        { key: "id_tel_gap_20", value: "" },
        { key: "id_tel_s2_eval", value: "" },
        { key: "id_tel_s3_sin_cal", value: "" },
        { key: "id_tel_s4_con_cal", value: "" },
        { key: "indice_s3_sin_cal", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g168.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G168 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
