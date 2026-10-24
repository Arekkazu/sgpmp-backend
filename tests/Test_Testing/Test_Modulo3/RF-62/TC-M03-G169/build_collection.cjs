const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G169
// RF-62 / RF-63: Comportamiento según estado heredado de RF-53 (FUERA_DE_RANGO y ERROR_CALIBRACION)

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
function buildBatch20Alternada(sensorVar, deviceVar, serialVar, baseDateStr) {
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

// ── 00. PREFLIGHT Y DESCUBRIMIENTO ─────────────────────────────────────────────
folders.push({
    name: "00-Preflight-y-Descubrimiento",
    item: [
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
            "01-Descubrimiento-Sensores-G169",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT s.id_sensores, s.id_dispositivo_iot, d.serial FROM modulo9.sensores s JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot WHERE s.es_activo = true AND d.es_activo = true ORDER BY s.id_sensores ASC LIMIT 2"
            },
            [],
            [
                'pm.test("Status 200 - Descubrimiento de sensores realizado", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.be.above(0);',
                '    ',
                '    // S1: TC-M03-321 (FUERA_DE_RANGO)',
                '    pm.collectionVariables.set("s1_sensor_id", rows[0].id_sensores);',
                '    pm.collectionVariables.set("s1_device_id", rows[0].id_dispositivo_iot);',
                '    pm.collectionVariables.set("s1_device_serial", rows[0].serial);',
                '    ',
                '    // S2: TC-M03-322 (ERROR_CALIBRACION)',
                '    const r1 = rows[1] || rows[0];',
                '    pm.collectionVariables.set("s2_sensor_id", r1.id_sensores);',
                '    pm.collectionVariables.set("s2_device_id", r1.id_dispositivo_iot);',
                '    pm.collectionVariables.set("s2_device_serial", r1.serial);',
                '});'
            ]
        )
    ]
});

// ── 01. TC-M03-321: ESTADO HEREDADO FUERA_DE_RANGO ─────────────────────────────
folders.push({
    name: "01-TC-M03-321-Estado-Heredado-FUERA_DE_RANGO",
    item: [
        // 1. Inyectar telemetría con estado_calidad = 'FUERA_DE_RANGO' y valor = 150.00
        // Columnas validadas en modulo3.telemetrias: id_sensor, id_variable, id_dispositivo_iot, valor_crudo,
        // timestamp_captura, timestamp_procesamiento, origen, estado_calidad, calibrado, categoria_variable, unidad_medida
        makeItem(
            "10-E1-Sembrar-Telemetria-FUERA_DE_RANGO",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "INSERT INTO modulo3.telemetrias (id_sensor, id_variable, id_dispositivo_iot, valor_crudo, valor_ajustado, timestamp_captura, timestamp_procesamiento, origen, estado_calidad, calibrado, categoria_variable, unidad_medida) VALUES ({{s1_sensor_id}}, 9, {{s1_device_id}}, 150.00, NULL, '2026-10-15T10:00:00Z', NOW(), 'BUFFER_LOCAL', 'FUERA_DE_RANGO', false, 'AMBIENTAL', '°C') RETURNING id_telemetria"
            },
            [],
            [
                'pm.test("Status 200 - Telemetría sembrada con FUERA_DE_RANGO", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.be.above(0);',
                '    pm.collectionVariables.set("id_tel_321", rows[0].id_telemetria);',
                '});'
            ]
        ),
        // 2. Snapshot antes de evaluar: verificar valor_crudo original
        makeItem(
            "11-E1-Snapshot-Pre-Evaluacion-RF53",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT valor_crudo, estado_calidad FROM modulo3.telemetrias WHERE id_telemetria = {{id_tel_321}}"
            },
            [],
            [
                'pm.test("Status 200 - Verificación estado inicial en RF-53", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(parseFloat(rows[0].valor_crudo)).to.equal(150.0);',
                '    pm.expect(rows[0].estado_calidad).to.equal("FUERA_DE_RANGO");',
                '});'
            ]
        ),
        // 3. Evaluar calidad puntual POST /iot/calidad/{id}/evaluar
        makeItem(
            "12-E1-Evaluar-Calidad-Lectura-FUERA_DE_RANGO",
            "POST",
            "{{baseUrl}}/iot/calidad/{{id_tel_321}}/evaluar",
            makeAuthHeaders(),
            null,
            [],
            [
                'pm.test("Status 201 - Evaluación FUERA_DE_RANGO: Índice 0, NO_APTO, fuera_de_rango_rf53 activo", function () {',
                '    pm.response.to.have.status(201);',
                '    const res = pm.response.json();',
                '    const flags = res.flags_detectados || {};',
                '    ',
                '    pm.expect(res.indice_calidad).to.equal(0);',
                '    pm.expect(res.clasificacion_calidad).to.equal("NO_APTO");',
                '    pm.expect(res.apto_para_ia).to.equal(false);',
                '    pm.expect(res.apto_para_nic41).to.equal(false);',
                '    ',
                '    // Flag hereditario',
                '    pm.expect(flags.fuera_de_rango_rf53 && flags.fuera_de_rango_rf53.activo).to.equal(true);',
                '    ',
                '    // Ausencia estricta de anomalías calculadas en Fase 1 a 5',
                '    pm.expect(flags.sensor_congelado).to.be.undefined;',
                '    pm.expect(flags.outlier_estadistico).to.be.undefined;',
                '    pm.expect(flags.posible_drift).to.be.undefined;',
                '    pm.expect(flags.gap_temporal_anomalo).to.be.undefined;',
                '});'
            ]
        ),
        // 4. GET /iot/calidad/{id_telemetria} (consulta de evaluación)
        makeItem(
            "13-E1-Consultar-Calidad-Por-IdTelemetria",
            "GET",
            "{{baseUrl}}/iot/calidad/{{id_tel_321}}",
            makeAuthHeaders(),
            null,
            [],
            [
                'pm.test("Status 200 - Consulta de calidad consistente con evaluación", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.indice_calidad).to.equal(0);',
                '    pm.expect(res.clasificacion_calidad).to.equal("NO_APTO");',
                '    pm.expect(res.apto_para_ia).to.equal(false);',
                '    pm.expect(res.apto_para_nic41).to.equal(false);',
                '});'
            ]
        ),
        // 5. Verificar que en telemetria_calidad existan metadatos mínimos
        makeItem(
            "14-E1-Verificar-Metadatos-Minimos-BD",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT parametros_aplicados, flags_detectados, estado_evaluacion FROM modulo3.telemetria_calidad WHERE id_telemetria = {{id_tel_321}}"
            },
            [],
            [
                'pm.test("Status 200 - Metadatos mínimos presentes en telemetria_calidad", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.be.above(0);',
                '    pm.expect(rows[0].parametros_aplicados).to.be.an("object");',
                '    pm.expect(rows[0].estado_evaluacion).to.equal("VIGENTE");',
                '});'
            ]
        ),
        // 6. Verificar ausencia de alerta técnica en modulo3.alertas
        makeItem(
            "15-E1-Verificar-Ausencia-Alerta-Tecnica",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT COUNT(*) AS total_alertas FROM modulo3.alertas WHERE id_telemetria = {{id_tel_321}}"
            },
            [],
            [
                'pm.test("Status 200 - Sin alerta técnica para lectura FUERA_DE_RANGO", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    const total = parseInt((rows[0] && rows[0].total_alertas) || 0, 10);',
                '    pm.expect(total).to.equal(0);',
                '});'
            ]
        ),
        // 7. Snapshot posterior: verificar que el valor original en RF-53 no cambió
        makeItem(
            "16-E1-Snapshot-Post-Evaluacion-Inmutabilidad-RF53",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT valor_crudo FROM modulo3.telemetrias WHERE id_telemetria = {{id_tel_321}}"
            },
            [],
            [
                'pm.test("Status 200 - Inmutabilidad del valor original en modulo3.telemetrias", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(parseFloat(rows[0].valor_crudo)).to.equal(150.0);',
                '});'
            ]
        )
    ]
});

// ── 02. TC-M03-322: SENSOR CON SERIE VÁLIDA Y LECTURA CON ERROR_CALIBRACION ────
folders.push({
    name: "02-TC-M03-322-Estado-Heredado-ERROR_CALIBRACION",
    item: [
        // 1. Configurar calibración nominal para S2 para que la serie de 20 previas sea LECTURA_VALIDA
        makeItem(
            "20-E2-Configurar-Calibracion-Base-S2",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "INSERT INTO modulo9.calibraciones (id_dispositivo_iot, id_sensor, ganancia, offset_calibracion, fecha_calibracion, valor_referencia, id_usuario) VALUES ({{s2_device_id}}, {{s2_sensor_id}}, 1.0, 0.0, NOW(), 22.0, 1)"
            },
            [],
            [
                'pm.test("Status 200 - Calibración base configurada en S2", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        // 2. Siembra batch 20 lecturas alternadas 21.50/22.50 a 10 min en S2 (Día 2026-10-16)
        makeItem(
            "21-E2-Siembra-Batch-20-Lecturas-S2",
            "POST",
            "{{baseUrl}}/iot/telemetria/batch",
            [],
            buildBatch20Alternada("s2_sensor_id", "s2_device_id", "s2_device_serial", "2026-10-16T00:00:00Z"),
            [],
            [
                'pm.test("Status 200 - Ingesta batch 20 lecturas base en S2", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.aceptados).to.equal(20);',
                '});'
            ]
        ),
        // 3. SELECT de verificación de las 20 lecturas previas: EXIGE estado_calidad = 'LECTURA_VALIDA'
        makeItem(
            "22-E2-Verificar-20-Lecturas-Base-Validas",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT estado_calidad, COUNT(*) AS total FROM modulo3.telemetrias WHERE id_sensor = {{s2_sensor_id}} AND timestamp_captura >= '2026-10-16T00:00:00Z' AND timestamp_captura <= '2026-10-16T03:10:00Z' GROUP BY estado_calidad"
            },
            [],
            [
                'pm.test("Status 200 - Exigir 20 lecturas base como LECTURA_VALIDA para alimentar la serie del motor", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.equal(1);',
                '    pm.expect(rows[0].estado_calidad).to.equal("LECTURA_VALIDA");',
                '    pm.expect(parseInt(rows[0].total, 10)).to.equal(20);',
                '});'
            ]
        ),
        // 4. Borrar la calibración de S2 justo antes de la lectura evaluada para forzar ERROR_CALIBRACION en la lectura evaluada
        makeItem(
            "23-E2-Borrar-Calibracion-S2-Pre-Evaluada",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "DELETE FROM modulo9.calibraciones WHERE id_sensor = {{s2_sensor_id}}"
            },
            [],
            [
                'pm.test("Status 200 - Calibración eliminada dentro del sandbox para lectura evaluada", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        // 5. Ingesta de lectura evaluada 25.50 llegando 25 min después de la anterior (03:10 -> 03:35) -> RF-53 le asigna ERROR_CALIBRACION
        makeItem(
            "24-E2-Ingesta-Lectura-Evaluada-25.50-Gap-25min",
            "POST",
            "{{baseUrl}}/iot/telemetria",
            [],
            {
                device_id: "{{s2_device_id}}",
                sensor_id: "{{s2_sensor_id}}",
                tipo_variable: "TEMPERATURA_AMBIENTAL",
                valor: 25.50,
                unidad: "°C",
                timestamp_captura: "2026-10-16T03:35:00Z", // 25 min de gap
                access_key: "{{s2_device_serial}}",
                origen: "BUFFER_LOCAL"
            },
            [],
            [
                'pm.test("Status 201 - Ingesta lectura evaluada 25.50 con ERROR_CALIBRACION", function () {',
                '    pm.response.to.have.status(201);',
                '    const res = pm.response.json();',
                '    pm.expect(res.estado_calidad).to.equal("ERROR_CALIBRACION");',
                '    pm.collectionVariables.set("id_tel_322", res.id_telemetria);',
                '});'
            ]
        ),
        // 6. Evaluar calidad puntual de la lectura 25.50
        makeItem(
            "25-E2-Evaluar-Calidad-S2-Error-Calibracion",
            "POST",
            "{{baseUrl}}/iot/calidad/{{id_tel_322}}/evaluar",
            makeAuthHeaders(),
            null,
            [],
            [
                'pm.test("Status 201 - TC-M03-322: calibracion_no_disponible=true, outlier=true, drift omitido", function () {',
                '    pm.response.to.have.status(201);',
                '    const res = pm.response.json();',
                '    const flags = res.flags_detectados || {};',
                '    ',
                '    // Calibración no disponible activa e informativa',
                '    pm.expect(flags.calibracion_no_disponible && flags.calibracion_no_disponible.activo).to.equal(true);',
                '    ',
                '    // Drift estrictamente omitido por no tener calibración',
                '    pm.expect(flags.posible_drift).to.be.undefined;',
                '    ',
                '    // Outlier estadístico activo (-20)',
                '    pm.expect(flags.outlier_estadistico && flags.outlier_estadistico.activo).to.equal(true);',
                '    ',
                '    // Clasificación y aptitud',
                '    pm.expect(res.clasificacion_calidad).to.equal("APTO_CON_RESERVA");',
                '    pm.expect(res.apto_para_ia).to.equal(true);',
                '    pm.expect(res.apto_para_nic41).to.equal(false);',
                '});'
            ]
        ),
        makeItem(
            "26-E2-Asercion-Defecto-Conocido-Fase5-Gap",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT flags_detectados->'gap_temporal_anomalo' AS gap, indice_calidad FROM modulo3.telemetria_calidad WHERE id_telemetria = {{id_tel_322}}"
            },
            [],
            [
                'pm.test("[DEFECTO CONOCIDO RF-62 Fase 5] Gap temporal anómalo activo e índice 70 (100 - 20 - 10)", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    const gap = rows[0] && rows[0].gap;',
                '    const idx = rows[0] && rows[0].indice_calidad;',
                '    pm.expect(gap && gap.activo, "Defecto Fase 5: Gap temporal no detectado por el backend").to.equal(true);',
                '    pm.expect(idx, "Índice esperado con gap y outlier es 70").to.equal(70);',
                '});'
            ]
        )
    ]
});

// ── 03. VERIFICACIÓN D7 INVARIANTE VIGENTE ────────────────────────────────────
folders.push({
    name: "03-Verificacion-Invariante-D7",
    item: [
        makeItem(
            "30-D7-Verificar-Invariante-VIGENTE-TC321",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT COUNT(*) AS total_vigentes FROM modulo3.telemetria_calidad WHERE id_telemetria = {{id_tel_321}} AND estado_evaluacion = 'VIGENTE'"
            },
            [],
            [
                'pm.test("[DEFECTO CONOCIDO D7] Invariante una sola VIGENTE para lectura 321", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    const vigentes = parseInt((rows[0] && rows[0].total_vigentes) || 0, 10);',
                '    pm.expect(vigentes).to.equal(1);',
                '});'
            ]
        ),
        makeItem(
            "31-D7-Verificar-Invariante-VIGENTE-TC322",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT COUNT(*) AS total_vigentes FROM modulo3.telemetria_calidad WHERE id_telemetria = {{id_tel_322}} AND estado_evaluacion = 'VIGENTE'"
            },
            [],
            [
                'pm.test("[DEFECTO CONOCIDO D7] Invariante una sola VIGENTE para lectura 322", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    const vigentes = parseInt((rows[0] && rows[0].total_vigentes) || 0, 10);',
                '    pm.expect(vigentes).to.equal(1);',
                '});'
            ]
        )
    ]
});

// ── 99. TEARDOWN Y ROLLBACK ───────────────────────────────────────────────────
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

// Ensamblado de colección Postman
const collection = {
    info: {
        _postman_id: "tc-m03-g169-heredado-rf53-v2",
        name: "TC-M03-G169 - Estado Heredado de RF-53 (FUERA_DE_RANGO y ERROR_CALIBRACION)",
        description: "Suite automatizada Newman para TC-M03-G169 (RF-62 / RF-63). Cobertura de estados heredados de RF-53: FUERA_DE_RANGO (TC-321) y ERROR_CALIBRACION (TC-322).",
        schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    event: [
        {
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: [
                    '// Pre-request a nivel de colección:',
                    'let currentRunId = pm.collectionVariables.get("run_id");',
                    'if (!currentRunId || currentRunId.trim() === "") {',
                    '    currentRunId = "test-" + pm.variables.replaceIn("{{$guid}}");',
                    '    pm.collectionVariables.set("run_id", currentRunId);',
                    '}',
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
        { key: "id_tel_321", value: "" },
        { key: "id_tel_322", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g169.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => { totalItems += f.item.length; });
console.log(`Colección G169 regenerada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
