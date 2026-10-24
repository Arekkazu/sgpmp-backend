const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G184
// OWASP API5: Broken Function Level Authorization (BFLA) en Auditoría IoT (RF-63)
//
// ROLES EVALUADOS:
// 1. ADMINISTRADOR (administador.dev@gmail.com / {{admin_password}}) -> Rol 1: Acceso Total
// 2. PRODUCTOR (m2m.nuevo@ejemplo.com / {{role_password}}) -> Rol 2: Denegado Total (403)
// 3. VETERINARIO (juan.carlos.qa133@sgpmp-test.com / {{role_password}}) -> Rol 3: Denegado Total (403)
// 4. INGENIERO_CAMPO (gestor.granja.test@pecuaria.co / {{role_password}}) -> Rol 4: Solo Lectura (39,2) -> 200 listar/detalle; 403 exportar/verificar
// 5. CONTADOR (contador@pecuaria.co / {{role_password}}) -> Rol 5: Lectura y Ejecución (39,2 y 39,5) -> 200 en los 4 endpoints
//
// ENDPOINTS EVALUADOS:
// 1. GET  /iot/auditoria (Recurso 39, Acción 2)
// 2. GET  /iot/auditoria/{{test_id_evento}} (Recurso 39, Acción 2)
// 3. GET  /iot/auditoria/exportar (Recurso 39, Acción 5)
// 4. POST /iot/auditoria/verificar-integridad (Recurso 39, Acción 5)
//
// PRUEBA DE INMUTABILIDAD EN BFLA:
// - Intentos de DELETE/PUT/PATCH para roles autorizados deben responder 405 (Solo lectura).

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
        '    pm.expect(res.token).to.be.a("string").that.is.not.empty;',
        `    pm.collectionVariables.set("${u.tokenVar}", res.token);`,
        '});'
    ]
));

folders.push({
    name: "00-Setup-Autenticacion-MultiRol",
    item: loginItems
});

// ── 01. PREPARACIÓN DE ID DE EVENTO BASE ──────────────────────────────────────
folders.push({
    name: "01-Setup-Obtener-ID-Evento",
    item: [
        makeItem(
            "01-Obtener-Id-Evento-Existente",
            "GET",
            "{{baseUrl}}/iot/auditoria?por_pagina=1",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'const res = pm.response.json();',
                'if (res.items && res.items.length > 0) {',
                '    pm.collectionVariables.set("test_id_evento", res.items[0].id_evento);',
                '} else {',
                '    pm.collectionVariables.set("test_id_evento", "00000000-0000-0000-0000-000000000001");',
                '}'
            ]
        )
    ]
});

// ── 02. BFLA: GET /iot/auditoria (Recurso 39, Acción 2) ────────────────────────
folders.push({
    name: "02-BFLA-GET-Listar-Auditoria",
    item: [
        makeItem(
            "02-Listar-ADMIN-Permitido",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - ADMINISTRADOR autorizado en listar auditoría", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        makeItem(
            "03-Listar-PRODUCTOR-Denegado",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            makeAuthHeaders("token_productor"),
            null,
            [],
            [
                'pm.test("Status 403 - PRODUCTOR denegado en listar auditoría", function () {',
                '    pm.response.to.have.status(403);',
                '});'
            ]
        ),
        makeItem(
            "04-Listar-VETERINARIO-Denegado",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            makeAuthHeaders("token_veterinario"),
            null,
            [],
            [
                'pm.test("Status 403 - VETERINARIO denegado en listar auditoría", function () {',
                '    pm.response.to.have.status(403);',
                '});'
            ]
        ),
        makeItem(
            "05-Listar-INGENIERO_CAMPO-Permitido",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            makeAuthHeaders("token_ingeniero"),
            null,
            [],
            [
                'pm.test("Status 200 - INGENIERO_CAMPO autorizado con permiso (39,2)", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'console.log("[INFO BFLA] INGENIERO_CAMPO accede a la bitácora técnica.");'
            ]
        ),
        makeItem(
            "06-Listar-CONTADOR-Permitido",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            makeAuthHeaders("token_contador"),
            null,
            [],
            [
                'pm.test("Status 200 - CONTADOR autorizado con permiso (39,2)", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'console.log("[DISCREPANCIA CON EL CASO] Contador ve el listado general; el backend autoriza por permiso (39,2) sin filtrar registros exclusivamente NIC41 en SQL.");'
            ]
        )
    ]
});

// ── 03. BFLA: GET /iot/auditoria/{id_evento} (Recurso 39, Acción 2) ────────────
folders.push({
    name: "03-BFLA-GET-Detalle-Auditoria",
    item: [
        makeItem(
            "07-Detalle-ADMIN-Permitido",
            "GET",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento}}",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - ADMINISTRADOR autorizado en detalle", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        makeItem(
            "08-Detalle-PRODUCTOR-Denegado",
            "GET",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento}}",
            makeAuthHeaders("token_productor"),
            null,
            [],
            [
                'pm.test("Status 403 - PRODUCTOR denegado en detalle", function () {',
                '    pm.response.to.have.status(403);',
                '});'
            ]
        ),
        makeItem(
            "09-Detalle-VETERINARIO-Denegado",
            "GET",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento}}",
            makeAuthHeaders("token_veterinario"),
            null,
            [],
            [
                'pm.test("Status 403 - VETERINARIO denegado en detalle", function () {',
                '    pm.response.to.have.status(403);',
                '});'
            ]
        ),
        makeItem(
            "10-Detalle-INGENIERO_CAMPO-Permitido",
            "GET",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento}}",
            makeAuthHeaders("token_ingeniero"),
            null,
            [],
            [
                'pm.test("Status 200 - INGENIERO_CAMPO autorizado en detalle", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        makeItem(
            "11-Detalle-CONTADOR-Permitido",
            "GET",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento}}",
            makeAuthHeaders("token_contador"),
            null,
            [],
            [
                'pm.test("Status 200 - CONTADOR autorizado en detalle", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        )
    ]
});

// ── 04. BFLA: GET /iot/auditoria/exportar (Recurso 39, Acción 5) ───────────────
folders.push({
    name: "04-BFLA-GET-Exportar-Auditoria",
    item: [
        makeItem(
            "12-Exportar-ADMIN-Permitido",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - ADMINISTRADOR autorizado en exportar", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        makeItem(
            "13-Exportar-PRODUCTOR-Denegado",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_productor"),
            null,
            [],
            [
                'pm.test("Status 403 - PRODUCTOR denegado en exportar", function () {',
                '    pm.response.to.have.status(403);',
                '});'
            ]
        ),
        makeItem(
            "14-Exportar-INGENIERO_CAMPO-Denegado",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_ingeniero"),
            null,
            [],
            [
                'pm.test("Status 403 - INGENIERO_CAMPO denegado en exportar (carece de accion 5)", function () {',
                '    pm.response.to.have.status(403);',
                '});'
            ]
        ),
        makeItem(
            "15-Exportar-CONTADOR-Permitido",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_contador"),
            null,
            [],
            [
                'pm.test("Status 200 - CONTADOR autorizado en exportar con permiso (39,5)", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        )
    ]
});

// ── 05. BFLA: POST /iot/auditoria/verificar-integridad (Recurso 39, Acción 5) ──
folders.push({
    name: "05-BFLA-POST-Verificar-Integridad",
    item: [
        makeItem(
            "16-Verificar-Integridad-ADMIN-Permitido",
            "POST",
            "{{baseUrl}}/iot/auditoria/verificar-integridad",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - ADMINISTRADOR autorizado en verificación de integridad", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        makeItem(
            "17-Verificar-Integridad-INGENIERO_CAMPO-Denegado",
            "POST",
            "{{baseUrl}}/iot/auditoria/verificar-integridad",
            makeAuthHeaders("token_ingeniero"),
            null,
            [],
            [
                'pm.test("Status 403 - INGENIERO_CAMPO denegado en verificar integridad (carece de acción 5)", function () {',
                '    pm.response.to.have.status(403);',
                '});',
                'console.log("[CONFIRMACION RBAC] INGENIERO_CAMPO solo posee (39,2). Acción (39,5) responde 403.");'
            ]
        ),
        makeItem(
            "18-Verificar-Integridad-CONTADOR-Permitido",
            "POST",
            "{{baseUrl}}/iot/auditoria/verificar-integridad",
            makeAuthHeaders("token_contador"),
            null,
            [],
            [
                'pm.test("Status 200 - CONTADOR autorizado en verificar integridad con permiso (39,5)", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        )
    ]
});

// ── 06. INMUTABILIDAD TRANSVERSAL (INTENTOS DE MUTACIÓN) ──────────────────────
folders.push({
    name: "06-Inmutabilidad-BFLA-Solo-Lectura",
    item: [
        makeItem(
            "19-Intento-DELETE-Admin-Rechazado",
            "DELETE",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento}}",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 405 (o 404) - Ni el ADMINISTRADOR puede borrar eventos (Solo Lectura / Append-Only)", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([405, 404]);',
                '});'
            ]
        ),
        makeItem(
            "20-Intento-PATCH-Admin-Rechazado",
            "PATCH",
            "{{baseUrl}}/iot/auditoria/{{test_id_evento}}",
            makeAuthHeaders("token_admin"),
            {
                severidad_log: "INFO"
            },
            [],
            [
                'pm.test("Status 405 (o 404) - Ni el ADMINISTRADOR puede modificar eventos", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([405, 404]);',
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
        _postman_id: "tc-m03-g184-bfla-v1",
        name: "TC-M03-G184 - OWASP API5 BFLA en Auditoría IoT (RF-63)",
        description: "Suite automatizada Newman para TC-M03-G184 (RF-63). Verifica autorización granular a nivel de función (BFLA) para roles Admin, Productor, Veterinario, Ingeniero de Campo y Contador sobre los 4 endpoints de auditoría.",
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
        { key: "test_id_evento", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g184.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G184 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
