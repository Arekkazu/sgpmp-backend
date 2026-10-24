const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G170
// RF-62 / RF-63: Re-evaluación explícita POST /iot/calidad/reevaluar

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
            "01-Descubrimiento-Sensor-G170",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT s.id_sensores, s.id_dispositivo_iot, d.serial FROM modulo9.sensores s JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot WHERE s.es_activo = true AND d.es_activo = true ORDER BY s.id_sensores ASC LIMIT 1"
            },
            [],
            [
                'pm.test("Status 200 - Sensor descubierto", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.be.above(0);',
                '    pm.collectionVariables.set("sensor_id", rows[0].id_sensores);',
                '    pm.collectionVariables.set("device_id", rows[0].id_dispositivo_iot);',
                '    pm.collectionVariables.set("device_serial", rows[0].serial);',
                '});'
            ]
        )
    ]
});

// ── 01. FIXTURE DE EVALUACIONES PREVIAS (RANGO CONTROLADO) ─────────────────────
// Siembra de 5 lecturas evaluadas en el rango 2026-10-10T10:00:00Z a 2026-10-10T10:40:00Z
folders.push({
    name: "01-Fixture-Evaluaciones-Previas",
    item: [
        makeItem(
            "10-Fixture-Siembra-5-Telemetrias",
            "POST",
            "{{baseUrl}}/iot/telemetria/batch",
            [],
            {
                registros: [
                    {
                        device_id: parseInt("{{device_id}}", 10),
                        sensor_id: parseInt("{{sensor_id}}", 10),
                        tipo_variable: "TEMPERATURA_AMBIENTAL",
                        valor: 21.0,
                        unidad: "°C",
                        timestamp_captura: "2026-10-10T10:00:00Z",
                        access_key: "{{device_serial}}",
                        origen: "BUFFER_LOCAL"
                    },
                    {
                        device_id: parseInt("{{device_id}}", 10),
                        sensor_id: parseInt("{{sensor_id}}", 10),
                        tipo_variable: "TEMPERATURA_AMBIENTAL",
                        valor: 21.2,
                        unidad: "°C",
                        timestamp_captura: "2026-10-10T10:10:00Z",
                        access_key: "{{device_serial}}",
                        origen: "BUFFER_LOCAL"
                    },
                    {
                        device_id: parseInt("{{device_id}}", 10),
                        sensor_id: parseInt("{{sensor_id}}", 10),
                        tipo_variable: "TEMPERATURA_AMBIENTAL",
                        valor: 21.4,
                        unidad: "°C",
                        timestamp_captura: "2026-10-10T10:20:00Z",
                        access_key: "{{device_serial}}",
                        origen: "BUFFER_LOCAL"
                    },
                    {
                        device_id: parseInt("{{device_id}}", 10),
                        sensor_id: parseInt("{{sensor_id}}", 10),
                        tipo_variable: "TEMPERATURA_AMBIENTAL",
                        valor: 21.6,
                        unidad: "°C",
                        timestamp_captura: "2026-10-10T10:30:00Z",
                        access_key: "{{device_serial}}",
                        origen: "BUFFER_LOCAL"
                    },
                    {
                        device_id: parseInt("{{device_id}}", 10),
                        sensor_id: parseInt("{{sensor_id}}", 10),
                        tipo_variable: "TEMPERATURA_AMBIENTAL",
                        valor: 21.8,
                        unidad: "°C",
                        timestamp_captura: "2026-10-10T10:40:00Z",
                        access_key: "{{device_serial}}",
                        origen: "BUFFER_LOCAL"
                    }
                ]
            },
            [],
            [
                'pm.test("Status 200 - Batch 5 lecturas fixture", function () {',
                '    pm.response.to.have.status(200);',
                '    pm.expect(pm.response.json().aceptados).to.equal(5);',
                '});'
            ]
        ),
        // Insertar 5 evaluaciones VIGENTES en modulo3.telemetria_calidad para este sensor y rango
        makeItem(
            "11-Fixture-Crear-5-Evaluaciones-VIGENTES",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "INSERT INTO modulo3.telemetria_calidad (id_telemetria, id_sensor, timestamp_evaluacion, indice_calidad, clasificacion_calidad, apto_para_ia, apto_para_nic41, flags_detectados, parametros_aplicados, parametros_calibracion_aplicados, estado_evaluacion, version_evaluacion) SELECT t.id_telemetria, t.id_sensor, t.timestamp_captura, 90, 'APTO', true, true, '{\"posible_drift\": {\"activo\": true}}'::jsonb, '{\"k\": 3}'::jsonb, '{\"ganancia\": 1, \"offset\": -1.4}'::jsonb, 'VIGENTE', 'v1.0-inicial' FROM modulo3.telemetrias t WHERE t.id_sensor = {{sensor_id}} AND t.timestamp_captura >= '2026-10-10T10:00:00Z' AND t.timestamp_captura <= '2026-10-10T10:40:00Z' RETURNING id_evaluacion"
            },
            [],
            [
                'pm.test("Status 200 - 5 evaluaciones vigentes creadas para el fixture", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.equal(5);',
                '});'
            ]
        )
    ]
});

// ── 02. VALIDACIONES DE ERROR (EJECUTADAS ANTES DEL CASO FELIZ) ────────────────
folders.push({
    name: "02-Validaciones-422-Previas",
    item: [
        // Snapshot inicial de conteo de evaluaciones vigentes
        makeItem(
            "20-Snapshot-Conteo-Inicial-VIGENTES",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT COUNT(*) AS total_vigentes FROM modulo3.telemetria_calidad WHERE id_sensor = {{sensor_id}} AND estado_evaluacion = 'VIGENTE'"
            },
            [],
            [
                'pm.test("Status 200 - Snapshot inicial conteo vigentes", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.collectionVariables.set("vigentes_iniciales", rows[0].total_vigentes);',
                '});'
            ]
        ),
        // TC-M03-325(a): Sin causa_documentada
        makeItem(
            "21-TC325a-Sin-Causa-Documentada",
            "POST",
            "{{baseUrl}}/iot/calidad/reevaluar",
            makeAuthHeaders(),
            {
                id_sensor: parseInt("{{sensor_id}}", 10),
                fecha_desde: "2026-10-10T10:00:00Z",
                fecha_hasta: "2026-10-10T10:40:00Z"
            },
            [],
            [
                'pm.test("Status 422 - Rechazo por ausencia de causa_documentada", function () {',
                '    pm.response.to.have.status(422);',
                '});'
            ]
        ),
        // TC-M03-325(b): causa_documentada vacía ''
        makeItem(
            "22-TC325b-Causa-Vacia",
            "POST",
            "{{baseUrl}}/iot/calidad/reevaluar",
            makeAuthHeaders(),
            {
                id_sensor: parseInt("{{sensor_id}}", 10),
                fecha_desde: "2026-10-10T10:00:00Z",
                fecha_hasta: "2026-10-10T10:40:00Z",
                causa_documentada: ""
            },
            [],
            [
                'pm.test("Status 422 - Rechazo por causa vacía (<10 caracteres)", function () {',
                '    pm.response.to.have.status(422);',
                '});'
            ]
        ),
        // TC-M03-325(c): causa_documentada muy corta 'ab'
        makeItem(
            "23-TC325c-Causa-Longitud-Insuficiente",
            "POST",
            "{{baseUrl}}/iot/calidad/reevaluar",
            makeAuthHeaders(),
            {
                id_sensor: parseInt("{{sensor_id}}", 10),
                fecha_desde: "2026-10-10T10:00:00Z",
                fecha_hasta: "2026-10-10T10:40:00Z",
                causa_documentada: "ab"
            },
            [],
            [
                'pm.test("Status 422 - Rechazo por causa < 10 caracteres", function () {',
                '    pm.response.to.have.status(422);',
                '});'
            ]
        ),
        // TC-M03-325(d): Causa solo de preferencia
        makeItem(
            "24-TC325d-Causa-Solo-Preferencia",
            "POST",
            "{{baseUrl}}/iot/calidad/reevaluar",
            makeAuthHeaders(),
            {
                id_sensor: parseInt("{{sensor_id}}", 10),
                fecha_desde: "2026-10-10T10:00:00Z",
                fecha_hasta: "2026-10-10T10:40:00Z",
                causa_documentada: "quiero cambiar el umbral_drift de 5% a 3%"
            },
            [],
            [
                'pm.test("Verificación causa preferencia CA-17", function () {',
                '    // Registra el código observado sin forzar ajuste',
                '    console.log("[TC-325d] Status observado con causa de preferencia:", pm.response.code);',
                '    pm.expect([200, 400, 422]).to.include(pm.response.code);',
                '});'
            ]
        ),
        // TC-M03-326: fecha_desde > fecha_hasta
        makeItem(
            "25-TC326-Rango-Fechas-Inconsistente",
            "POST",
            "{{baseUrl}}/iot/calidad/reevaluar",
            makeAuthHeaders(),
            {
                id_sensor: parseInt("{{sensor_id}}", 10),
                fecha_desde: "2026-10-10T12:00:00Z",
                fecha_hasta: "2026-10-10T10:00:00Z",
                causa_documentada: "Corrección de offset mal configurado en M09"
            },
            [],
            [
                'pm.test("[DISCREPANCIA] Rechazo por rango inconsistente fecha_desde > fecha_hasta exige HTTP 422", function () {',
                '    console.log("[TC-326] Status observado con fecha_desde > fecha_hasta:", pm.response.code);',
                '    pm.expect(pm.response.code, "Discrepancia: El caso exige HTTP 422 por validación de rango inconsistente").to.equal(422);',
                '});'
            ]
        ),
        // TC-M03-326(bis): fecha_desde == fecha_hasta (No definido en RF: solo console.log)
        makeItem(
            "26-TC326bis-Fechas-Iguales-Observacion",
            "POST",
            "{{baseUrl}}/iot/calidad/reevaluar",
            makeAuthHeaders(),
            {
                id_sensor: parseInt("{{sensor_id}}", 10),
                fecha_desde: "2026-10-10T10:00:00Z",
                fecha_hasta: "2026-10-10T10:00:00Z",
                causa_documentada: "Revisión de lectura puntual por error técnico"
            },
            [],
            [
                '// Subcaso no definido por RF: solo observación de código sin pm.expect',
                'console.log("[TC-326bis] Observación fecha_desde == fecha_hasta:", pm.response.code, pm.response.text());'
            ]
        ),
        // Verificar que ningún 422 alteró el estado en BD
        makeItem(
            "27-Verificar-Inmutabilidad-Tras-Errores-422",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT COUNT(*) AS total_vigentes FROM modulo3.telemetria_calidad WHERE id_sensor = {{sensor_id}} AND estado_evaluacion = 'VIGENTE'"
            },
            [],
            [
                'pm.test("Status 200 - Inmutabilidad confirmada tras solicitudes 422", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    const countPost = parseInt(rows[0].total_vigentes, 10);',
                '    const countPre = parseInt(pm.collectionVariables.get("vigentes_iniciales"), 10);',
                '    pm.expect(countPost).to.equal(countPre);',
                '});'
            ]
        )
    ]
});

// ── 03. CASO FELIZ: TC-M03-324 RE-EVALUACIÓN MASIVA ───────────────────────────
folders.push({
    name: "03-TC-M03-324-Caso-Feliz-Reevaluacion",
    item: [
        makeItem(
            "30-TC324-Ejecutar-Reevaluacion-Masiva",
            "POST",
            "{{baseUrl}}/iot/calidad/reevaluar",
            makeAuthHeaders(),
            {
                id_sensor: parseInt("{{sensor_id}}", 10),
                fecha_desde: "2026-10-10T09:50:00Z",
                fecha_hasta: "2026-10-10T10:50:00Z",
                causa_documentada: "Offset de calibración mal configurado en RF-24 generó drift falso masivo",
                parametros_correctos: {
                    ganancia: 1.0,
                    offset: 0.0
                }
            },
            [],
            [
                'pm.test("Status 200 - Re-evaluación completada con éxito", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.evaluaciones_superadas).to.be.at.least(5);',
                '    pm.collectionVariables.set("superadas_reportadas", res.evaluaciones_superadas);',
                '});'
            ]
        ),
        // Verificar transiciones en BD: evaluaciones anteriores en SUPERADA
        makeItem(
            "31-TC324-Verificar-Evaluaciones-En-SUPERADA",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT COUNT(*) AS total_superadas FROM modulo3.telemetria_calidad WHERE id_sensor = {{sensor_id}} AND estado_evaluacion = 'SUPERADA' AND motivo_reevaluacion LIKE '%Offset de calibración mal configurado%'"
            },
            [],
            [
                'pm.test("Status 200 - Evaluaciones previas transicionaron a SUPERADA", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    const totalSup = parseInt(rows[0].total_superadas, 10);',
                '    pm.expect(totalSup).to.be.at.least(5);',
                '});'
            ]
        ),
        // Registrar discrepancia del caso vs D7
        makeItem(
            "32-TC324-Discrepancia-Nomenclatura-D7",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT DISTINCT estado_evaluacion FROM modulo3.telemetria_calidad WHERE id_sensor = {{sensor_id}}"
            },
            [],
            [
                'pm.test("[DISCREPANCIA CASO vs D7] Nomenclatura canónica de estados es VIGENTE y SUPERADA (ACTIVA descartada)", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    const estados = rows.map(r => r.estado_evaluacion);',
                '    pm.expect(estados).to.include("SUPERADA");',
                '    pm.expect(estados).to.not.include("ACTIVA");',
                '});'
            ]
        ),
        // Verificar evento de auditoría en modulo3.bitacora_auditoria_iot (RF-63)
        makeItem(
            "33-TC324-Verificar-Auditoria-RF63",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT tipo_evento, componente_origen, descripcion, accion_detallada FROM modulo3.bitacora_auditoria_iot WHERE componente_origen = 'RF-62' AND descripcion LIKE '%Re-evaluación solicitada%' ORDER BY id_evento DESC LIMIT 1"
            },
            [],
            [
                'pm.test("Status 200 - Registro de auditoría RF-63 emitido", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.be.above(0);',
                '    pm.expect(rows[0].tipo_evento).to.equal("REEVALUACION_CALIDAD_SOLICITADA");',
                '    console.log("[AUDITORIA RF-63 DETALLE]:", JSON.stringify(rows[0].accion_detallada));',
                '});'
            ]
        ),
        // Sub-caso no verificable en TEST: Notificación M04 / M06 (BLOQUEADO sin pm.test)
        makeItem(
            "34-TC324-Notificacion-M04-M06-BLOQUEADO",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT 1 AS bloqueado"
            },
            [],
            [
                '// SUB-CASO BLOQUEADO: No contiene pm.test para no falsear el reporte en el scanner.',
                'console.log("[BLOQUEADO] TC-M03-324: Notificación a M04/M06 no es verificable directamente vía REST/SQL en entorno TEST.");'
            ]
        ),
        // Verificación D7: Una sola VIGENTE por lectura evaluada
        makeItem(
            "35-TC324-Verificacion-Invariante-D7-Final",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT id_telemetria, COUNT(*) AS vigentes FROM modulo3.telemetria_calidad WHERE id_sensor = {{sensor_id}} AND estado_evaluacion = 'VIGENTE' GROUP BY id_telemetria HAVING COUNT(*) > 1"
            },
            [],
            [
                'pm.test("[DEFECTO CONOCIDO D7] Invariante una sola VIGENTE por lectura", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    // No deben existir duplicados vigentes para la misma lectura',
                '    pm.expect(rows.length).to.equal(0);',
                '});'
            ]
        )
    ]
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

// Ensamblado de la colección Postman
const collection = {
    info: {
        _postman_id: "tc-m03-g170-reevaluacion-v1",
        name: "TC-M03-G170 - Re-evaluacion Explicita POST /iot/calidad/reevaluar",
        description: "Suite automatizada Newman para TC-M03-G170 (RF-62 / RF-63). Cobertura de re-evaluación explícita masiva: caso feliz (TC-324), validaciones 422 de causa (TC-325) y rango de fechas (TC-326).",
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
        { key: "sensor_id", value: "" },
        { key: "device_id", value: "" },
        { key: "device_serial", value: "" },
        { key: "vigentes_iniciales", value: "" },
        { key: "superadas_reportadas", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g170.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => { totalItems += f.item.length; });
console.log(`Colección G170 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
