const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G186
// OWASP API4: Unrestricted Resource Consumption en Exportación de Auditoría IoT (RF-63)
//
// Subcasos:
// - TC-M03-354(a): Exportación JSON sin filtros temporales (evaluación de límites por defecto y paginación)
// - TC-M03-354(b): Exportación CSV con rango histórico ultra amplio (2020-01-01 a fecha actual)
// - TC-M03-354(c): Volumen > 10,000 registros -> [BLOQUEADO] por timeout de sandbox
// - TC-M03-354(d): Ráfaga de 5 peticiones concurrentes/consecutivas de exportación en < 60s
// - TC-M03-354(e): Verificación de no degradación del servicio tras la ráfaga (GET /iot/auditoria -> 200)

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

// ── 00. LOGIN CANÓNICO ────────────────────────────────────────────────────────
folders.push({
    name: "00-Setup-Autenticacion",
    item: [
        makeItem(
            "00-Login-ADMIN",
            "POST",
            "{{baseUrl}}/sesiones/",
            [],
            {
                correo_electronico: "administador.dev@gmail.com",
                contrasena: "{{admin_password}}"
            },
            [],
            [
                'pm.test("Status 200 - Login exitoso de ADMIN", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.token).to.be.a("string").that.is.not.empty;',
                '    pm.collectionVariables.set("token_admin", res.token);',
                '});'
            ]
        )
    ]
});

// ── 01. SETUP SINTÉTICO (CATÁLOGO EN SANDBOX) ─────────────────────────────────
folders.push({
    name: "01-Setup-Sintetico-Catalogo",
    item: [
        makeItem(
            "01-Crear-Finca-Sintetica",
            "POST",
            "{{baseUrl}}/configuracion/fincas",
            makeAuthHeaders("token_admin"),
            {
                nombre: "Finca QA G186 Consumo",
                ubicacion: "Vereda Las Huertas QA",
                area_total: 125.0
            },
            [],
            [
                'pm.test("Status 201/200 - Finca creada en sandbox", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '    const res = pm.response.json();',
                '    const idFinca = res.id_finca || (res.finca && res.finca.id_finca) || res.id;',
                '    pm.collectionVariables.set("finca_id", String(idFinca));',
                '});'
            ]
        ),
        makeItem(
            "02-Crear-Infraestructura-Sintetica",
            "POST",
            "{{baseUrl}}/configuracion/infraestructuras",
            makeAuthHeaders("token_admin"),
            {
                id_finca: "{{finca_id}}",
                nombre: "Galpon 186 Consumo",
                id_tipo_area: 1,
                capacidad_maxima: 300
            },
            [
                'const fId = parseInt(pm.collectionVariables.get("finca_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_finca = fId;',
                'pm.request.body.raw = JSON.stringify(body);'
            ],
            [
                'pm.test("Status 201/200 - Infraestructura creada en sandbox", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '    const res = pm.response.json();',
                '    const idInfra = res.id_infraestructura || (res.infraestructura && res.infraestructura.id_infraestructura) || res.id;',
                '    pm.collectionVariables.set("infra_id", String(idInfra));',
                '});'
            ]
        ),
        makeItem(
            "03-Crear-Dispositivo-Sintetico",
            "POST",
            "{{baseUrl}}/configuracion/dispositivos-iot",
            makeAuthHeaders("token_admin"),
            {
                id_infraestructura: "{{infra_id}}",
                numero_serie: "DEV-G186-INIT",
                id_tipo_dispositivo: 1,
                modelo: "ESP32-G186-API4",
                firmware_version: "2.1.0"
            },
            [
                'const infId = parseInt(pm.collectionVariables.get("infra_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_infraestructura = infId;',
                'const serial = "DEV-G186-" + Math.floor(100000 + Math.random() * 900000);',
                'body.numero_serie = serial;',
                'pm.collectionVariables.set("device_serial", serial);',
                'pm.request.body.raw = JSON.stringify(body);'
            ],
            [
                'pm.test("Status 201/200 - Dispositivo creado en sandbox", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '    const res = pm.response.json();',
                '    const idDev = res.id_dispositivo_iot || res.id_dispositivo || res.id;',
                '    pm.collectionVariables.set("device_id", String(idDev));',
                '});'
            ]
        ),
        makeItem(
            "04-Crear-Sensor-Sintetico",
            "POST",
            "{{baseUrl}}/configuracion/sensores",
            makeAuthHeaders("token_admin"),
            {
                id_dispositivo_iot: "{{device_id}}",
                id_variable: 1,
                pin_conexion: "A1",
                resolucion: 0.1,
                precision_lectura: 0.05,
                rango_minimo: -10.0,
                rango_maximo: 80.0
            },
            [
                'const devId = parseInt(pm.collectionVariables.get("device_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_dispositivo_iot = devId;',
                'pm.request.body.raw = JSON.stringify(body);'
            ],
            [
                'pm.test("Status 201/200 - Sensor creado en sandbox", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '    const res = pm.response.json();',
                '    const idSen = res.id_sensor || res.id;',
                '    pm.collectionVariables.set("sensor_id", String(idSen));',
                '});'
            ]
        )
    ]
});

// ── 02. SETUP GENERACIÓN DE EVENTOS PARA EXPORTACIÓN ──────────────────────────
folders.push({
    name: "02-Setup-Generacion-Eventos",
    item: [
        makeItem(
            "05-Generar-Batch-Telemetria",
            "POST",
            "{{baseUrl}}/iot/telemetria/batch",
            makeAuthHeaders("token_admin"),
            {
                origen: "BUFFER_LOCAL",
                lecturas: []
            },
            [
                'const sensorId = parseInt(pm.collectionVariables.get("sensor_id"), 10);',
                'const lecturas = [];',
                'const baseEpoch = 1792137600; // 2026-10-16T08:00:00Z',
                'for (let i = 0; i < 20; i++) {',
                '    const dt = new Date((baseEpoch + (i * 600)) * 1000).toISOString();',
                '    lecturas.push({',
                '        id_sensor: sensorId,',
                '        valor: 24.5 + (i * 0.1),',
                '        timestamp_captura: dt',
                '    });',
                '}',
                'pm.request.body.raw = JSON.stringify({ origen: "BUFFER_LOCAL", lecturas: lecturas });'
            ],
            [
                'pm.test("Status 200/201 - Ingesta batch completada", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '});'
            ]
        )
    ]
});

// ── 03. TC-M03-354: EVALUACIÓN DE CONSUMO IRRESTRICTO (OWASP API4) ────────────
folders.push({
    name: "03-TC-M03-354-Consumo-Irrestricto-OWASP-API4",
    item: [
        makeItem(
            "06-TC-354a-Exportar-JSON-Sin-Filtros",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Exportación sin filtros temporales", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const data = pm.response.json();',
                'console.log("[OBSERVACION POLITICA] Exportación sin filtros devolvió " + data.length + " registros en " + pm.response.responseTime + " ms.");',
                'if (data.length > 5000) {',
                '    console.log("[HALLAZGO OWASP API4] La exportación sin filtros devuelve un volumen masivo sin paginación forzada ni confirmación async.");',
                '} else {',
                '    console.log("[INFO API4] Límite interno de exportación: 10,000 registros (use_case por_pagina=10000).");',
                '}'
            ]
        ),
        makeItem(
            "07-TC-354b-Exportar-CSV-Rango-Historico-Amplio",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=csv&fecha_desde=2020-01-01T00:00:00Z&fecha_hasta=2026-10-18T23:59:59Z",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Exportación CSV con rango histórico amplio", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const lines = pm.response.text().split(/\\r?\\n/).filter(l => l.trim().length > 0);',
                'console.log("[OBSERVACION POLITICA] Rango amplio devolvió " + lines.length + " líneas CSV en " + pm.response.responseTime + " ms.");'
            ]
        ),
        makeItem(
            "08-TC-354c-Volumen-Excesivo-10000-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso Volumen > 10,000 registros: El sandbox transaccional tiene timeout de 180 s. Sembrar más de 10,000 eventos vía API causaría timeout de la sesión de pruebas.");'
            ]
        )
    ]
});

// ── 04. TC-M03-354: RÁFAGA DE EXPORTACIONES (RATE LIMITING) ───────────────────
folders.push({
    name: "04-TC-M03-354-Rafaga-Exportaciones",
    item: [
        makeItem(
            "09-Rafaga-Export-1",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[RAFAGA 1/5] Status:", pm.response.code, "| Tiempo:", pm.response.responseTime, "ms");',
                'pm.test("Ráfaga 1 responde 200 o 429", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 429]);',
                '});'
            ]
        ),
        makeItem(
            "10-Rafaga-Export-2",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[RAFAGA 2/5] Status:", pm.response.code, "| Tiempo:", pm.response.responseTime, "ms");',
                'pm.test("Ráfaga 2 responde 200 o 429", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 429]);',
                '});'
            ]
        ),
        makeItem(
            "11-Rafaga-Export-3",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[RAFAGA 3/5] Status:", pm.response.code, "| Tiempo:", pm.response.responseTime, "ms");',
                'pm.test("Ráfaga 3 responde 200 o 429", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 429]);',
                '});'
            ]
        ),
        makeItem(
            "12-Rafaga-Export-4",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[RAFAGA 4/5] Status:", pm.response.code, "| Tiempo:", pm.response.responseTime, "ms");',
                'pm.test("Ráfaga 4 responde 200 o 429", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 429]);',
                '});'
            ]
        ),
        makeItem(
            "13-Rafaga-Export-5",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[RAFAGA 5/5] Status:", pm.response.code, "| Tiempo:", pm.response.responseTime, "ms");',
                'pm.test("Ráfaga 5 responde 200 o 429", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 429]);',
                '});',
                'if (pm.response.code === 200) {',
                '    console.log("[HALLAZGO OWASP API4] La ráfaga de 5 exportaciones consecutivas fue permitida sin rate limiting HTTP 429.");',
                '}'
            ]
        ),
        makeItem(
            "14-Verificar-No-Degradacion-Servicio",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Servicio de auditoría operacional y sin degradación tras la ráfaga", function () {',
                '    pm.response.to.have.status(200);',
                '    pm.expect(pm.response.responseTime).to.be.below(2000);',
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

const collection = {
    info: {
        _postman_id: "tc-m03-g186-owasp-api4-v1",
        name: "TC-M03-G186 - OWASP API4 Consumo de Recursos en Exportación IoT (RF-63)",
        description: "Suite automatizada Newman para TC-M03-G186 (RF-63). Evalúa consumo irrestricto de recursos en exportaciones pesadas, ráfagas consecutivas y verificación de no degradación del servicio.",
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
        { key: "token_admin", value: "" },
        { key: "finca_id", value: "" },
        { key: "infra_id", value: "" },
        { key: "device_id", value: "" },
        { key: "device_serial", value: "" },
        { key: "sensor_id", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g186.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G186 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
