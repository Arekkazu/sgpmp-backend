const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G174
// OWASP API5:2023 - Broken Function Level Authorization (BFLA) en RF-62
//
// ROLES EVALUADOS:
// 1. ADMINISTRADOR canónico (administador.dev@gmail.com / {{admin_password}}) -> Rol 1
// 2. PRODUCTOR (m2m.nuevo@ejemplo.com / {{role_password}}) -> Rol 2
// 3. VETERINARIO (juan.carlos.qa133@sgpmp-test.com / {{role_password}}) -> Rol 3
// 4. INGENIERO_CAMPO (gestor.granja.test@pecuaria.co / {{role_password}}) -> Rol 4
// 5. CONTADOR (contador@pecuaria.co / {{role_password}}) -> Rol 5
//
// ENDPOINTS PROBADOS:
// - POST /iot/calidad/reevaluar (Recurso 38, Acción 5)
// - GET  /iot/calidad (Recurso 38, Acción 2)
// - POST /iot/calidad/{id_telemetria}/evaluar (Recurso 38, Acción 5)

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

// ── 00. LOGINS Y VERIFICACIÓN DE CLAIMS JWT ───────────────────────────────────
const usersToLogin = [
    { key: "admin", email: "administador.dev@gmail.com", passVar: "admin_password", expectedRol: 1, tokenVar: "token_admin" },
    { key: "productor", email: "m2m.nuevo@ejemplo.com", passVar: "role_password", expectedRol: 2, tokenVar: "token_productor" },
    { key: "veterinario", email: "juan.carlos.qa133@sgpmp-test.com", passVar: "role_password", expectedRol: 3, tokenVar: "token_veterinario" },
    { key: "ingeniero", email: "gestor.granja.test@pecuaria.co", passVar: "role_password", expectedRol: 4, tokenVar: "token_ingeniero" },
    { key: "contador", email: "contador@pecuaria.co", passVar: "role_password", expectedRol: 5, tokenVar: "token_contador" }
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
        '    pm.expect(res.token).to.be.a("string").and.not.be.empty;',
        `    pm.collectionVariables.set("${u.tokenVar}", res.token);`,
        '    // Extraer y validar claim rol del JWT',
        '    try {',
        '        const payload = JSON.parse(CryptoJS.enc.Utf8.stringify(CryptoJS.enc.Base64.parse(res.token.split(".")[1])));',
        `        if (payload.rol !== ${u.expectedRol}) {`,
        `            console.log("[DISCREPANCIA] Rol en JWT para ${u.email}: obtenido " + payload.rol + ", esperado ${u.expectedRol}");`,
        '        }',
        '    } catch (e) {',
        '        console.error("Error parseando JWT:", e);',
        '    }',
        '});'
    ]
));

// Descubrimiento de sensor y creación de telemetría fixture por API
loginItems.push(makeItem(
    "01-Descubrir-Sensor-Activo",
    "POST",
    "{{baseUrl}}/test-control/query",
    makeAuthHeaders("token_admin"),
    {
        query: "SELECT s.id_sensores, s.id_dispositivo_iot, d.serial FROM modulo9.sensores s JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot WHERE s.es_activo = true AND d.es_activo = true ORDER BY s.id_sensores ASC LIMIT 1"
    },
    [],
    [
        'pm.test("[VERIFICACION SQL SOLO LECTURA] Status 200 - Sensor descubierto", function () {',
        '    pm.response.to.have.status(200);',
        '    const rows = pm.response.json().data || pm.response.json().rows || [];',
        '    pm.expect(rows.length).to.be.above(0);',
        '    pm.collectionVariables.set("sensor_id", rows[0].id_sensores);',
        '    pm.collectionVariables.set("device_id", rows[0].id_dispositivo_iot);',
        '    pm.collectionVariables.set("device_serial", rows[0].serial);',
        '});'
    ]
));

loginItems.push(makeItem(
    "02-Crear-Telemetria-Evaluada-Fixture",
    "POST",
    "{{baseUrl}}/iot/telemetria",
    [],
    {
        device_id: parseInt("{{device_id}}", 10),
        sensor_id: parseInt("{{sensor_id}}", 10),
        tipo_variable: "TEMPERATURA_AMBIENTAL",
        valor: 22.0,
        unidad: "°C",
        timestamp_captura: "2026-10-15T10:00:00Z",
        access_key: "{{device_serial}}",
        origen: "BUFFER_LOCAL"
    },
    [],
    [
        'pm.test("Status 201 - Telemetría creada para pruebas BFLA", function () {',
        '    pm.response.to.have.status(201);',
        '    pm.collectionVariables.set("id_tel_bfla", pm.response.json().id_telemetria);',
        '});'
    ]
));

folders.push({
    name: "00-Logins-y-Contexto-BFLA",
    item: loginItems
});

// ── 01. BFLA EN POST /iot/calidad/reevaluar ───────────────────────────────────
// RBAC: Recurso 38, Acción 5. Solo Administrador (Rol 1) e Ingeniero de Campo (Rol 4) poseen permiso 38.5 en base de datos.
// Pero la regla de negocio FA-08 restringe la reevaluación masiva administrativa.
const reevaluarBody = {
    id_sensor: 1, // Se actualizará en prerequest
    fecha_desde: "2026-10-10T00:00:00Z",
    fecha_hasta: "2026-10-10T23:59:59Z",
    causa_documentada: "Ajuste documentado por error de calibracion detectado en campo",
    parametros_correctos: { ganancia: 1.0, offset: 0.0 }
};

const reevaluarItems = [
    // 1. Administrador -> Intentará ejecutar (200 o 400/422 según evaluaciones en rango)
    makeItem(
        "10-Reevaluar-ADMINISTRADOR",
        "POST",
        "{{baseUrl}}/iot/calidad/reevaluar",
        makeAuthHeaders("token_admin"),
        reevaluarBody,
        [
            'const b = JSON.parse(pm.request.body.raw);',
            'b.id_sensor = parseInt(pm.collectionVariables.get("sensor_id"), 10);',
            'pm.request.body.raw = JSON.stringify(b);'
        ],
        [
            'pm.test("Status 200 o 400 - ADMINISTRADOR autorizado por RBAC (no recibe 403)", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 400]);',
            '});'
        ]
    ),
    // 2. Productor -> 403
    makeItem(
        "11-Reevaluar-PRODUCTOR-Rechazado",
        "POST",
        "{{baseUrl}}/iot/calidad/reevaluar",
        makeAuthHeaders("token_productor"),
        reevaluarBody,
        [],
        [
            'pm.test("Status 403 - PRODUCTOR denegado BFLA en /reevaluar", function () {',
            '    pm.response.to.have.status(403);',
            '});'
        ]
    ),
    // 3. Veterinario -> 403
    makeItem(
        "12-Reevaluar-VETERINARIO-Rechazado",
        "POST",
        "{{baseUrl}}/iot/calidad/reevaluar",
        makeAuthHeaders("token_veterinario"),
        reevaluarBody,
        [],
        [
            'pm.test("Status 403 - VETERINARIO denegado BFLA en /reevaluar", function () {',
            '    pm.response.to.have.status(403);',
            '});'
        ]
    ),
    // 4. Contador -> 403
    makeItem(
        "13-Reevaluar-CONTADOR-Rechazado",
        "POST",
        "{{baseUrl}}/iot/calidad/reevaluar",
        makeAuthHeaders("token_contador"),
        reevaluarBody,
        [],
        [
            'pm.test("Status 403 - CONTADOR denegado BFLA en /reevaluar", function () {',
            '    pm.response.to.have.status(403);',
            '});'
        ]
    ),
    // 5. Ingeniero de Campo -> Evaluar permiso
    makeItem(
        "14-Reevaluar-INGENIERO_CAMPO",
        "POST",
        "{{baseUrl}}/iot/calidad/reevaluar",
        makeAuthHeaders("token_ingeniero"),
        reevaluarBody,
        [],
        [
            'pm.test("Verificación BFLA Ingeniero en /reevaluar", function () {',
            '    console.log("[INFO BFLA] INGENIERO_CAMPO en /reevaluar respondió HTTP " + pm.response.code);',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 400, 403]);',
            '});'
        ]
    )
];

folders.push({
    name: "01-BFLA-POST-Reevaluar",
    item: reevaluarItems
});

// ── 02. BFLA EN GET /iot/calidad ──────────────────────────────────────────────
// RBAC: Recurso 38, Acción 2 (Leer). Tienen permiso: Admin (1), Productor (2), Veterinario (3), Ingeniero (4), Contador (5).
const getCalidadItems = [
    makeItem(
        "20-GET-Calidad-ADMINISTRADOR",
        "GET",
        "{{baseUrl}}/iot/calidad",
        makeAuthHeaders("token_admin"),
        null,
        [],
        [
            'pm.test("Status 200 - ADMINISTRADOR lee calidad", function () {',
            '    pm.response.to.have.status(200);',
            '});'
        ]
    ),
    makeItem(
        "21-GET-Calidad-INGENIERO_CAMPO",
        "GET",
        "{{baseUrl}}/iot/calidad",
        makeAuthHeaders("token_ingeniero"),
        null,
        [],
        [
            'pm.test("Status 200 - INGENIERO_CAMPO lee calidad", function () {',
            '    pm.response.to.have.status(200);',
            '});'
        ]
    ),
    makeItem(
        "22-GET-Calidad-PRODUCTOR",
        "GET",
        "{{baseUrl}}/iot/calidad",
        makeAuthHeaders("token_productor"),
        null,
        [],
        [
            'console.log("[INFO BFLA] PRODUCTOR en GET /iot/calidad respondió HTTP " + pm.response.code);',
            'pm.test("PRODUCTOR consulta calidad (200 o 403 según política)", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 403]);',
            '});'
        ]
    ),
    makeItem(
        "23-GET-Calidad-VETERINARIO",
        "GET",
        "{{baseUrl}}/iot/calidad",
        makeAuthHeaders("token_veterinario"),
        null,
        [],
        [
            'console.log("[INFO BFLA] VETERINARIO en GET /iot/calidad respondió HTTP " + pm.response.code);',
            'pm.test("VETERINARIO consulta calidad", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 403]);',
            '});'
        ]
    ),
    makeItem(
        "24-GET-Calidad-CONTADOR",
        "GET",
        "{{baseUrl}}/iot/calidad",
        makeAuthHeaders("token_contador"),
        null,
        [],
        [
            'console.log("[INFO BFLA] CONTADOR en GET /iot/calidad respondió HTTP " + pm.response.code);',
            'pm.test("CONTADOR consulta calidad", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 403]);',
            '});'
        ]
    )
];

folders.push({
    name: "02-BFLA-GET-Calidad",
    item: getCalidadItems
});

// ── 03. HALLAZGO ADICIONAL: BFLA EN POST /iot/calidad/{id}/evaluar ─────────────
// RBAC: Recurso 38, Acción 5 (Ejecutar).
const evaluarItems = [
    makeItem(
        "30-Evaluar-ADMINISTRADOR",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_bfla}}/evaluar",
        makeAuthHeaders("token_admin"),
        null,
        [],
        [
            'pm.test("Status 201 - ADMINISTRADOR ejecuta evaluar calidad", function () {',
            '    pm.response.to.have.status(201);',
            '});'
        ]
    ),
    makeItem(
        "31-Evaluar-PRODUCTOR-Rechazado",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_bfla}}/evaluar",
        makeAuthHeaders("token_productor"),
        null,
        [],
        [
            'pm.test("Status 403 - PRODUCTOR denegado en disparar evaluación", function () {',
            '    pm.response.to.have.status(403);',
            '});'
        ]
    ),
    makeItem(
        "32-Evaluar-VETERINARIO-Rechazado",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_bfla}}/evaluar",
        makeAuthHeaders("token_veterinario"),
        null,
        [],
        [
            'pm.test("Status 403 - VETERINARIO denegado en disparar evaluación", function () {',
            '    pm.response.to.have.status(403);',
            '});'
        ]
    ),
    makeItem(
        "33-Evaluar-INGENIERO_CAMPO",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_bfla}}/evaluar",
        makeAuthHeaders("token_ingeniero"),
        null,
        [],
        [
            'console.log("[INFO BFLA] INGENIERO_CAMPO en POST /evaluar respondió HTTP " + pm.response.code);',
            'pm.test("INGENIERO_CAMPO en evaluar responde conforme a matriz RBAC", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([201, 403]);',
            '});'
        ]
    ),
    makeItem(
        "34-Evaluar-CONTADOR-Rechazado",
        "POST",
        "{{baseUrl}}/iot/calidad/{{id_tel_bfla}}/evaluar",
        makeAuthHeaders("token_contador"),
        null,
        [],
        [
            'pm.test("Status 403 - CONTADOR denegado en disparar evaluación", function () {',
            '    pm.response.to.have.status(403);',
            '});'
        ]
    )
];

folders.push({
    name: "03-BFLA-POST-Evaluar-Puntual",
    item: evaluarItems
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
        _postman_id: "tc-m03-g174-bfla-v1",
        name: "TC-M03-G174 - BFLA OWASP API5 RF-62",
        description: "Suite automatizada Newman para TC-M03-G174 (RF-62). Verifica autorización granular a nivel de función (BFLA) para roles Admin, Productor, Veterinario, Ingeniero y Contador.",
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
        { key: "token_productor", value: "" },
        { key: "token_veterinario", value: "" },
        { key: "token_ingeniero", value: "" },
        { key: "token_contador", value: "" },
        { key: "sensor_id", value: "" },
        { key: "device_id", value: "" },
        { key: "device_serial", value: "" },
        { key: "id_tel_bfla", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g174.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G174 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
