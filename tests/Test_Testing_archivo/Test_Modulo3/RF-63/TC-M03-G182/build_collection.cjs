const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G182
// RF-63 (Bitácora de Auditoría IoT) — Retención Diferenciada y Naturaleza Append-Only
//
// Subcasos:
// - TC-M03-348: Verificación de retención aplicable (NIC41=5 años, TECNICO=1 año).
// - Inmutabilidad (Append-Only): Intentos de DELETE, PUT y PATCH contra /iot/auditoria/{id_evento}
//   deben ser terminantemente rechazados (HTTP 405 Method Not Allowed o 404/403).
// - Verificación posterior de integridad: El registro no ha sufrido alteración y su hash se mantiene idéntico.
// - Acciones bloqueadas: Eliminación directa por BD (regla CERO DML) y simulación del reloj del sistema.

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
                nombre: "Finca QA G182 Inmutable",
                ubicacion: "Vereda La Calera QA",
                area_total: 110.0
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
                nombre: "Galpon 182 Inmutable",
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
                numero_serie: "DEV-G182-INIT",
                id_tipo_dispositivo: 1,
                modelo: "ESP32-G182-APPENDONLY",
                firmware_version: "2.1.0"
            },
            [
                'const infId = parseInt(pm.collectionVariables.get("infra_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_infraestructura = infId;',
                'const serial = "DEV-G182-" + Math.floor(100000 + Math.random() * 900000);',
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
                pin_conexion: "A0",
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

// ── 02. SETUP GENERACIÓN DE EVENTOS ───────────────────────────────────────────
folders.push({
    name: "02-Setup-Generacion-Eventos",
    item: [
        makeItem(
            "05-Ingesta-Batch-Telemetria-NIC41",
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
                '// 20 lecturas pasadas (17-oct-2026), espaciadas cada 10 min (600s)',
                'const baseEpoch = 1792224000; // 2026-10-17T08:00:00Z',
                'for (let i = 0; i < 20; i++) {',
                '    const dt = new Date((baseEpoch + (i * 600)) * 1000).toISOString();',
                '    lecturas.push({',
                '        id_sensor: sensorId,',
                '        valor: 25.2 + (i * 0.1),',
                '        timestamp_captura: dt',
                '    });',
                '}',
                'pm.request.body.raw = JSON.stringify({ origen: "BUFFER_LOCAL", lecturas: lecturas });'
            ],
            [
                'pm.test("Status 200/201 - Ingesta batch completada (NIC41 generado)", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '});'
            ]
        ),
        makeItem(
            "06-Transicion-Mantenimiento-TECNICO",
            "PATCH",
            "{{baseUrl}}/iot/dispositivos/{{device_id}}/mantenimiento",
            makeAuthHeaders("token_admin"),
            {
                estado_nuevo: "MANTENIMIENTO",
                motivo: "Prueba inmutabilidad G182"
            },
            [],
            [
                'pm.test("Status 200 - Transición manual aplicada (TECNICO generado)", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        )
    ]
});

// ── 03. TC-M03-348: RETENCIÓN DIFERENCIADA ────────────────────────────────────
folders.push({
    name: "03-TC-M03-348-Retencion-Diferenciada",
    item: [
        makeItem(
            "07-Consultar-Retencion-NIC41",
            "GET",
            "{{baseUrl}}/iot/auditoria?clasificacion_registro=NIC41",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Eventos NIC41 obtenidos", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Todos los eventos NIC41 tienen retencion_aplicable = 5 años", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(ev => {',
                '        pm.expect(ev.retencion_aplicable).to.eql(5);',
                '    });',
                '    pm.collectionVariables.set("test_id_evento_inmutable", res.items[0].id_evento);',
                '    pm.collectionVariables.set("test_hash_original", res.items[0].hash_integridad);',
                '});'
            ]
        ),
        makeItem(
            "08-Consultar-Retencion-TECNICO",
            "GET",
            "{{baseUrl}}/iot/auditoria?clasificacion_registro=TECNICO",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Eventos TECNICO obtenidos", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Todos los eventos TECNICO tienen retencion_aplicable = 1 año", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(ev => {',
                '        pm.expect(ev.retencion_aplicable).to.eql(1);',
                '    });',
                '});'
            ]
        )
    ]
});

// ── 04. TC-M03-348: INMUTABILIDAD Y APPEND-ONLY (INTENTOS DE MODIFICACIÓN) ────
folders.push({
    name: "04-TC-M03-348-Inmutabilidad-Append-Only",
    item: [
        makeItem(
            "09-Intento-DELETE-Evento-Rechazado",
            "DELETE",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento_inmutable}}",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 405 (o 404/403) - DELETE rechazado; bitácora es inmutable", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([405, 404, 403]);',
                '});',
                'console.log("[INFO G182] Intento de DELETE respondió HTTP:", pm.response.code);'
            ]
        ),
        makeItem(
            "10-Intento-PUT-Evento-Rechazado",
            "PUT",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento_inmutable}}",
            makeAuthHeaders("token_admin"),
            {
                descripcion: "Modificación no autorizada de auditoría"
            },
            [],
            [
                'pm.test("Status 405 (o 404/403) - PUT rechazado; bitácora no admite reemplazos", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([405, 404, 403]);',
                '});',
                'console.log("[INFO G182] Intento de PUT respondió HTTP:", pm.response.code);'
            ]
        ),
        makeItem(
            "11-Intento-PATCH-Evento-Rechazado",
            "PATCH",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento_inmutable}}",
            makeAuthHeaders("token_admin"),
            {
                severidad_log: "CRITICAL"
            },
            [],
            [
                'pm.test("Status 405 (o 404/403) - PATCH rechazado; bitácora no admite ediciones parciales", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([405, 404, 403]);',
                '});',
                'console.log("[INFO G182] Intento de PATCH respondió HTTP:", pm.response.code);'
            ]
        ),
        makeItem(
            "12-Confirmar-Registro-Sigue-Intacto",
            "GET",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento_inmutable}}",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Registro sigue accesible e inalterado", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const ev = pm.response.json();',
                'pm.test("El hash de integridad se mantiene idéntico tras los intentos de mutación", function () {',
                '    pm.expect(ev.hash_integridad).to.eql(pm.collectionVariables.get("test_hash_original"));',
                '});'
            ]
        )
    ]
});

// ── 05. SUB-CASOS BLOQUEADOS (DML Y SIMULACIÓN DE RELOJ) ───────────────────────
folders.push({
    name: "05-Subcasos-Bloqueados-DML-Reloj",
    item: [
        makeItem(
            "13-Eliminar-Por-BD-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Intento de eliminación por BD: Prohibido terminantemente por Regla 2 (CERO DML a BD). No se ejecutarán sentencias DELETE vía /test-control/query.");'
            ]
        ),
        makeItem(
            "14-Simular-Reloj-Vencimiento-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Simulación de reloj del repositorio para probar expiración: No existe API ni mecanismo externo en TEST para avanzar la hora del servidor/BD.");'
            ]
        ),
        makeItem(
            "15-Consultar-Politica-Retencion-M09-Limitacion",
            "GET",
            "{{baseUrl}}/configuracion/politicas-retencion",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[LIMITACION API] Endpoint /configuracion/politicas-retencion no está expuesto en Swagger M09; se documenta como limitación de consulta.");'
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
        _postman_id: "tc-m03-g182-retencion-append-only-v1",
        name: "TC-M03-G182 - Retención Diferenciada y Append-Only Auditoría IoT (RF-63)",
        description: "Suite automatizada Newman para TC-M03-G182 (RF-63). Verifica retención legal diferenciada (NIC41=5 años, TECNICO=1 año) y la inmutabilidad absoluta de la bitácora frente a intentos de DELETE, PUT y PATCH.",
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
        { key: "sensor_id", value: "" },
        { key: "test_id_evento_inmutable", value: "" },
        { key: "test_hash_original", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g182.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G182 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
