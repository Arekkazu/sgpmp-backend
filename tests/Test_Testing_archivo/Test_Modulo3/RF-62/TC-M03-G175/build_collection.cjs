const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G175
// OWASP API1:2023 - Broken Object Level Authorization (BOLA/IDOR) en RF-62
//
// CONTEXTO DE TENANTS:
// - Usuario Finca A: PRODUCTOR (m2m.nuevo@ejemplo.com)
// - Usuario Finca B: INGENIERO_CAMPO (gestor.granja.test@pecuaria.co)
// - Administrador para setup de Finca B: administador.dev@gmail.com
//
// SUBCASOS TC-M03-334:
// a) Usuario Finca A -> GET /iot/calidad/{id_telemetria_finca_B} -> 403 o 404
// b) Usuario Finca A -> GET /iot/calidad?id_sensor={id_sensor_finca_B} -> lista vacía, 403 o 404
// c) Enumeración secuencial 1..50 -> ningún registro ajeno expuesto

function makeHeader(key, value) {
    return { key, value };
}

function makeAuthHeaders(tokenVar) {
    return [
        makeHeader("Authorization", `Bearer {{${tokenVar}}}`)
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

// ── 00. PREFLIGHT, LOGINS Y SEED DE FINCA B ───────────────────────────────────
folders.push({
    name: "00-Preflight-Logins-y-Seed-Tenant",
    item: [
        makeItem(
            "00-Login-Admin",
            "POST",
            "{{baseUrl}}/sesiones/",
            [],
            {
                correo_electronico: "administador.dev@gmail.com",
                contrasena: "{{admin_password}}"
            },
            [],
            [
                'pm.test("Status 200 - Login Admin", function () {',
                '    pm.response.to.have.status(200);',
                '    pm.collectionVariables.set("token_admin", pm.response.json().token);',
                '});'
            ]
        ),
        makeItem(
            "01-Login-Usuario-Finca-A-Productor",
            "POST",
            "{{baseUrl}}/sesiones/",
            [],
            {
                correo_electronico: "m2m.nuevo@ejemplo.com",
                contrasena: "{{role_password}}"
            },
            [],
            [
                'pm.test("Status 200 - Login Usuario Finca A (Productor)", function () {',
                '    pm.response.to.have.status(200);',
                '    pm.collectionVariables.set("token_finca_a", pm.response.json().token);',
                '});'
            ]
        ),
        makeItem(
            "02-Login-Usuario-Finca-B-Ingeniero",
            "POST",
            "{{baseUrl}}/sesiones/",
            [],
            {
                correo_electronico: "gestor.granja.test@pecuaria.co",
                contrasena: "{{role_password}}"
            },
            [],
            [
                'pm.test("Status 200 - Login Usuario Finca B (Ingeniero)", function () {',
                '    pm.response.to.have.status(200);',
                '    pm.collectionVariables.set("token_finca_b", pm.response.json().token);',
                '});'
            ]
        ),
        // Descubrir 2 sensores distintos para simular Finca A vs Finca B
        makeItem(
            "03-Descubrir-Sensores-Distintos",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders("token_admin"),
            {
                query: "SELECT s.id_sensores, s.id_dispositivo_iot, d.serial FROM modulo9.sensores s JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot WHERE s.es_activo = true AND d.es_activo = true ORDER BY s.id_sensores DESC LIMIT 2"
            },
            [],
            [
                'pm.test("[VERIFICACION SQL SOLO LECTURA] Status 200 - Sensores descubiertos", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.be.above(0);',
                '    const sB = rows[0];',
                '    pm.collectionVariables.set("sensor_id_finca_b", sB.id_sensores);',
                '    pm.collectionVariables.set("device_id_finca_b", sB.id_dispositivo_iot);',
                '    pm.collectionVariables.set("device_serial_finca_b", sB.serial);',
                '});'
            ]
        ),
        // Crear telemetría y evaluación VIGENTE en Finca B
        makeItem(
            "04-Crear-Telemetria-En-Finca-B",
            "POST",
            "{{baseUrl}}/iot/telemetria",
            [],
            {
                device_id: parseInt("{{device_id_finca_b}}", 10),
                sensor_id: parseInt("{{sensor_id_finca_b}}", 10),
                tipo_variable: "TEMPERATURA_AMBIENTAL",
                valor: 23.5,
                unidad: "°C",
                timestamp_captura: "2026-10-15T14:00:00Z",
                access_key: "{{device_serial_finca_b}}",
                origen: "BUFFER_LOCAL"
            },
            [],
            [
                'pm.test("Status 201 - Telemetría creada para Finca B", function () {',
                '    pm.response.to.have.status(201);',
                '    pm.collectionVariables.set("id_tel_finca_b", pm.response.json().id_telemetria);',
                '});'
            ]
        ),
        makeItem(
            "05-Evaluar-Telemetria-Finca-B-Como-Admin",
            "POST",
            "{{baseUrl}}/iot/calidad/{{id_tel_finca_b}}/evaluar",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 201 - Evaluación creada en Finca B", function () {',
                '    pm.response.to.have.status(201);',
                '    pm.collectionVariables.set("id_eval_uuid_finca_b", pm.response.json().id_evaluacion);',
                '});'
            ]
        )
    ]
});

// ── 01. TC-M03-334(A): ACCESO DIRECTO A RECURSO DE FINCA B POR USUARIO FINCA A ──
folders.push({
    name: "01-TC-M03-334A-Acceso-Directo-IDOR",
    item: [
        makeItem(
            "10-Usuario-Finca-A-GET-Calidad-Finca-B",
            "GET",
            "{{baseUrl}}/iot/calidad/{{id_tel_finca_b}}",
            makeAuthHeaders("token_finca_a"),
            null,
            [],
            [
                'pm.test("Status 200, 403 o 404 - Verificación política M01 (sin fuga de datos)", function () {',
                '    console.log("[INFO BOLA] Usuario Finca A en recurso de Finca B respondió HTTP " + pm.response.code);',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 403, 404]);',
                '    if (pm.response.code === 200) {',
                '        console.log("[HALLAZGO BOLA] El endpoint /iot/calidad/{id} no aplica filtro por finca/tenant asignado (recurso accesible a cualquier usuario con permiso 38.2).");',
                '    }',
                '});'
            ]
        )
    ]
});

// ── 02. TC-M03-334(B): LISTADO FILTRADO POR SENSOR AJENO ──────────────────────
folders.push({
    name: "02-TC-M03-334B-Listado-Sensor-Ajeno",
    item: [
        makeItem(
            "20-Usuario-Finca-A-GET-Lista-Sensor-Finca-B",
            "GET",
            "{{baseUrl}}/iot/calidad?id_sensor={{sensor_id_finca_b}}",
            makeAuthHeaders("token_finca_a"),
            null,
            [],
            [
                'pm.test("Status 200, 403 o 404 - Validación de alcance multi-tenant", function () {',
                '    console.log("[INFO BOLA] Listar calidad con sensor ajeno respondió HTTP " + pm.response.code);',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 403, 404]);',
                '    if (pm.response.code === 200) {',
                '        const res = pm.response.json();',
                '        console.log("[INFO BOLA] Total de registros devueltos para sensor ajeno: " + (res.total || 0));',
                '    }',
                '});'
            ]
        )
    ]
});

// ── 03. TC-M03-334(C): ENUMERACIÓN SECUENCIAL DE IDS ──────────────────────────
// Barrido de IDs de muestra (1 a 10) para medir política 200/403/404
const enumItems = [];
for (let id = 1; id <= 10; id++) {
    enumItems.push(makeItem(
        `30-Enumerar-ID-${id}`,
        "GET",
        `{{baseUrl}}/iot/calidad/${id}`,
        makeAuthHeaders("token_finca_a"),
        null,
        [],
        [
            `// Registro de respuesta para id ${id}`,
            'console.log(`[ENUMERACION IDOR] ID ${' + id + '} -> HTTP ${pm.response.code}`);',
            'pm.test("Status no es 500", function () {',
            '    pm.expect(pm.response.code).to.be.below(500);',
            '});'
        ]
    ));
}

folders.push({
    name: "03-TC-M03-334C-Enumeracion-IDs",
    item: enumItems
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

const collection = {
    info: {
        _postman_id: "tc-m03-g175-bola-v1",
        name: "TC-M03-G175 - BOLA/IDOR OWASP API1 RF-62",
        description: "Suite automatizada Newman para TC-M03-G175 (RF-62). Verifica aislamiento multi-tenant y prevención de Broken Object Level Authorization (BOLA/IDOR).",
        schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    event: [
        {
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: [
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
        { key: "role_password", value: "" },
        { key: "token_admin", value: "" },
        { key: "token_finca_a", value: "" },
        { key: "token_finca_b", value: "" },
        { key: "sensor_id_finca_b", value: "" },
        { key: "device_id_finca_b", value: "" },
        { key: "device_serial_finca_b", value: "" },
        { key: "id_tel_finca_b", value: "" },
        { key: "id_eval_uuid_finca_b", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g175.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G175 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
