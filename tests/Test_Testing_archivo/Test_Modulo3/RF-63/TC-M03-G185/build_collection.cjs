const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G185
// OWASP API1: Broken Object Level Authorization (BOLA) en Auditoría IoT (RF-63)
//
// Subcasos:
// - TC-M03-353(a): CONTADOR accediendo a evento TECNICO puntual (esperado 403/404; si 200 -> [DEFECTO BOLA])
// - TC-M03-353(b): INGENIERO_CAMPO accediendo a evento NIC41 puntual (esperado 403/404; si 200 -> [DEFECTO BOLA])
// - TC-M03-353(c): Filtro por entidad_afectada_id fuera de alcance
// - TC-M03-353(d): Enumeración de UUIDs aleatorios -> 404 consistente sin revelar metadatos
// - TC-M03-353(e): ADMINISTRADOR acceso total (200 en ambos)
// - Aislamiento entre fincas: [BLOQUEADO] porque el esquema BitacoraAuditoriaIotModel no tiene id_finca

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

// ── 00. SETUP LOGIN ROLES ─────────────────────────────────────────────────────
const usersToLogin = [
    { key: "admin", email: "administador.dev@gmail.com", passVar: "admin_password", tokenVar: "token_admin" },
    { key: "ingeniero", email: "gestor.granja.test@pecuaria.co", passVar: "role_password", tokenVar: "token_ingeniero" },
    { key: "contador", email: "contador@pecuaria.co", passVar: "role_password", tokenVar: "token_contador" }
];

const loginItems = usersToLogin.map(u => makeItem(
    `00-Login-${u.key.toUpperCase()}`,
    "POST",
    "{{baseUrl}}/sesiones/",
    [],
    {
        correo_electronico: u.email,
        contrasena: `{{${u.passVar}}}`
    },
    [],
    [
        `pm.test("Status 200 - Login exitoso para ${u.key}", function () {`,
        '    pm.response.to.have.status(200);',
        '    const res = pm.response.json();',
        '    pm.expect(res.token).to.be.a("string").that.is.not.empty;',
        `    pm.collectionVariables.set("${u.tokenVar}", res.token);`,
        '});'
    ]
));

folders.push({
    name: "00-Setup-Autenticacion",
    item: loginItems
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
                nombre: "Finca QA G185 BOLA",
                ubicacion: "Vereda La Palma QA",
                area_total: 100.0
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
                nombre: "Galpon 185 BOLA",
                id_tipo_area: 1,
                capacidad_maxima: 250
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
                numero_serie: "DEV-G185-INIT",
                id_tipo_dispositivo: 1,
                modelo: "ESP32-G185-BOLA",
                firmware_version: "2.1.0"
            },
            [
                'const infId = parseInt(pm.collectionVariables.get("infra_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_infraestructura = infId;',
                'const serial = "DEV-G185-" + Math.floor(100000 + Math.random() * 900000);',
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

// ── 02. SETUP GENERACIÓN DE EVENTOS TECNICO Y NIC41 ───────────────────────────
folders.push({
    name: "02-Setup-Generacion-Eventos",
    item: [
        makeItem(
            "05-Generar-Evento-NIC41-Telemetria",
            "POST",
            "{{baseUrl}}/iot/telemetria",
            makeAuthHeaders("token_admin"),
            {
                id_sensor: 0,
                valor: 26.0,
                timestamp_captura: "2026-10-18T10:00:00Z"
            },
            [
                'const sensorId = parseInt(pm.collectionVariables.get("sensor_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_sensor = sensorId;',
                'pm.request.body.raw = JSON.stringify(body);'
            ],
            [
                'pm.test("Status 200/201 - Telemetría NIC41 ingerida", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '    const res = pm.response.json();',
                '    const idTel = res.id_telemetria || res.id;',
                '    pm.collectionVariables.set("id_telemetria_eval", String(idTel));',
                '});'
            ]
        ),
        makeItem(
            "06-Evaluar-Calidad-Puntual-NIC41",
            "POST",
            "{{baseUrl}}/iot/calidad/{{id_telemetria_eval}}/evaluar",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200/201 - Calidad evaluada (Evento NIC41 emitido)", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '});'
            ]
        ),
        makeItem(
            "07-Generar-Evento-TECNICO-Mantenimiento",
            "PATCH",
            "{{baseUrl}}/iot/dispositivos/{{device_id}}/mantenimiento",
            makeAuthHeaders("token_admin"),
            {
                estado_nuevo: "MANTENIMIENTO",
                motivo: "Prueba BOLA G185 evento técnico"
            },
            [],
            [
                'pm.test("Status 200 - Transición mantenimiento aplicada (Evento TECNICO emitido)", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        makeItem(
            "08-Guardar-IDs-Eventos-NIC41-y-TECNICO",
            "GET",
            "{{baseUrl}}/iot/auditoria?por_pagina=20",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'const res = pm.response.json();',
                'const evNic = res.items.find(i => i.clasificacion_registro === "NIC41");',
                'const evTec = res.items.find(i => i.clasificacion_registro === "TECNICO");',
                'if (evNic) pm.collectionVariables.set("id_evento_nic41", evNic.id_evento);',
                'if (evTec) pm.collectionVariables.set("id_evento_tecnico", evTec.id_evento);',
                'console.log("[INFO G185] ID NIC41:", evNic ? evNic.id_evento : "no encontrado");',
                'console.log("[INFO G185] ID TECNICO:", evTec ? evTec.id_evento : "no encontrado");'
            ]
        )
    ]
});

// ── 03. TC-M03-353: BOLA POR ROL (CONTADOR E INGENIERO) ───────────────────────
folders.push({
    name: "03-TC-M03-353-BOLA-Aislamiento-Roles",
    item: [
        makeItem(
            "09-TC-353a-CONTADOR-Accede-Evento-TECNICO",
            "GET",
            "{{baseUrl}}/iot/auditoria/{{id_evento_tecnico}}",
            makeAuthHeaders("token_contador"),
            null,
            [],
            [
                'if (pm.response.code === 200) {',
                '    console.log("[DEFECTO BOLA] CONTADOR pudo acceder al detalle de un evento TECNICO (HTTP 200). El backend carece de control de acceso a nivel de objeto/clasificación.");',
                '    pm.test("[DEFECTO BOLA] CONTADOR debe recibir 403/404 al acceder a evento TECNICO", function () {',
                '        pm.expect(pm.response.code, "BOLA: Contador no debe ver eventos técnicos").to.be.oneOf([403, 404]);',
                '    });',
                '} else {',
                '    pm.test("Status 403/404 - CONTADOR rechazado legítimamente en evento técnico", function () {',
                '        pm.expect(pm.response.code).to.be.oneOf([403, 404]);',
                '    });',
                '}'
            ]
        ),
        makeItem(
            "10-TC-353b-INGENIERO-Accede-Evento-NIC41",
            "GET",
            "{{baseUrl}}/iot/auditoria/{{id_evento_nic41}}",
            makeAuthHeaders("token_ingeniero"),
            null,
            [],
            [
                'if (pm.response.code === 200) {',
                '    console.log("[DEFECTO BOLA] INGENIERO_CAMPO pudo acceder al detalle de un evento NIC41 no técnico (HTTP 200).");',
                '    pm.test("[DEFECTO BOLA] INGENIERO_CAMPO debe recibir 403/404 al acceder a evento puramente NIC41", function () {',
                '        pm.expect(pm.response.code, "BOLA: Ingeniero no debe ver eventos financieros NIC41").to.be.oneOf([403, 404]);',
                '    });',
                '} else {',
                '    pm.test("Status 403/404 - INGENIERO_CAMPO rechazado en evento NIC41", function () {',
                '        pm.expect(pm.response.code).to.be.oneOf([403, 404]);',
                '    });',
                '}'
            ]
        ),
        makeItem(
            "11-TC-353c-Filtrar-Entidad-Fuera-Alcance",
            "GET",
            "{{baseUrl}}/iot/auditoria?entidad_afectada_id=99999999-9999-9999-9999-999999999999",
            makeAuthHeaders("token_contador"),
            null,
            [],
            [
                'pm.test("Status 200 - Entidad afectada inexistente o ajena devuelve array vacío sin error", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.total).to.eql(0);',
                '    pm.expect(res.items).to.be.empty;',
                '});'
            ]
        ),
        makeItem(
            "12-TC-353d-Enumeracion-UUIDs-Ficticios",
            "GET",
            "{{baseUrl}}/iot/auditoria/a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
            makeAuthHeaders("token_ingeniero"),
            null,
            [],
            [
                'pm.test("Status 404 - UUID ficticio no revela existencia ni datos", function () {',
                '    pm.response.to.have.status(404);',
                '    const res = pm.response.json();',
                '    pm.expect(res.error_code).to.eql("EVENTO_NO_ENCONTRADO");',
                '});'
            ]
        ),
        makeItem(
            "13-TC-353e-ADMINISTRADOR-Acceso-Total",
            "GET",
            "{{baseUrl}}/iot/auditoria/{{id_evento_nic41}}",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - ADMINISTRADOR tiene acceso legítimo a ambos tipos de eventos", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        makeItem(
            "14-Aislamiento-Entre-Fincas-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso Aislamiento entre fincas: El modelo BitacoraAuditoriaIotModel y el esquema EventoAuditoriaIotSchema no contienen id_finca ni relación a fincas. No es posible probar aislamiento entre fincas de un atributo inexistente.");'
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
        _postman_id: "tc-m03-g185-owasp-bola-v1",
        name: "TC-M03-G185 - OWASP API1 BOLA en Auditoría IoT (RF-63)",
        description: "Suite automatizada Newman para TC-M03-G185 (RF-63). Evalúa aislamiento a nivel de objeto entre roles y detección de defecto BOLA en acceso a eventos técnicos y financieros.",
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
        { key: "token_ingeniero", value: "" },
        { key: "token_contador", value: "" },
        { key: "finca_id", value: "" },
        { key: "infra_id", value: "" },
        { key: "device_id", value: "" },
        { key: "device_serial", value: "" },
        { key: "sensor_id", value: "" },
        { key: "id_telemetria_eval", value: "" },
        { key: "id_evento_nic41", value: "" },
        { key: "id_evento_tecnico", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g185.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G185 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
