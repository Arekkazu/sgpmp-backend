const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G183
// OWASP API2: Broken Authentication & Token Verification en Auditoría IoT (RF-63)
//
// Endpoints evaluados:
// 1. GET  /iot/auditoria
// 2. GET  /iot/auditoria/{{test_id_evento}}
// 3. GET  /iot/auditoria/exportar
// 4. POST /iot/auditoria/verificar-integridad
//
// Subcasos:
// - TC-M03-349: Ausencia y malformación de cabecera Authorization (sin header, vacío " ", Bearer solo) -> HTTP 401
// - TC-M03-350: Expiración de tokens JWT (hace 1h, hace 1s) [BLOQUEADO puro sin TEST_JWT_SECRET]
// - TC-M03-351: Manipulación de tokens JWT (alg=none, payload alterado, firma clave incorrecta) y uniformidad de mensajes

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

// ── CARPETA 00: BASELINE LOGIN Y PREPARACIÓN DE ID ────────────────────────────
folders.push({
    name: "00-Setup-Baseline-Token-y-Setup",
    item: [
        makeItem(
            "00-Login-Admin-Baseline",
            "POST",
            "{{baseUrl}}/sesiones/",
            [],
            {
                correo_electronico: "administador.dev@gmail.com",
                contrasena: "{{admin_password}}"
            },
            [],
            [
                'pm.test("Status 200 - Login exitoso para generar token base", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.token).to.be.a("string").and.not.be.empty;',
                '    pm.collectionVariables.set("token_admin", res.token);',
                '});'
            ]
        ),
        makeItem(
            "01-Setup-Obtener-ID-Evento-Base",
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

// Aserciones estándar para error 401
const common401Assertions = [
    'pm.test("Status 401 - No autorizado", function () {',
    '    pm.response.to.have.status(401);',
    '});',
    'pm.test("Estructura de error 401 estándar sin fugar trazas internas", function () {',
    '    const b = pm.response.json();',
    '    pm.expect(b.error_code).to.be.a("string");',
    '    pm.expect(b.message).to.be.a("string");',
    '    pm.expect(b.message.toLowerCase()).to.not.include("traceback");',
    '    pm.expect(b.message.toLowerCase()).to.not.include("sql");',
    '    pm.expect(b.message.toLowerCase()).to.not.include("line ");',
    '});'
];

// ── CARPETA 01: TC-M03-349 SIN CABECERA O MALFORMADA ──────────────────────────
const endpointsAudit = [
    { name: "Listar-Auditoria", method: "GET", url: "{{baseUrl}}/iot/auditoria", body: null },
    { name: "Detalle-Auditoria", method: "GET", url: "{{baseUrl}}/iot/auditoria/{{test_id_evento}}", body: null },
    { name: "Exportar-Auditoria", method: "GET", url: "{{baseUrl}}/iot/auditoria/exportar", body: null },
    { name: "Verificar-Integridad", method: "POST", url: "{{baseUrl}}/iot/auditoria/verificar-integridad", body: null }
];

const folder349Items = [];
endpointsAudit.forEach(ep => {
    // 1. Sin header
    folder349Items.push(makeItem(
        `349-SinHeader-${ep.name}`,
        ep.method,
        ep.url,
        [],
        ep.body,
        [],
        common401Assertions
    ));

    // 2. Header Authorization vacío (" ")
    folder349Items.push(makeItem(
        `349-HeaderVacio-${ep.name}`,
        ep.method,
        ep.url,
        [makeHeader("Authorization", " ")],
        ep.body,
        [],
        common401Assertions
    ));

    // 3. Header Bearer sin token
    folder349Items.push(makeItem(
        `349-BearerSinToken-${ep.name}`,
        ep.method,
        ep.url,
        [makeHeader("Authorization", "Bearer ")],
        ep.body,
        [],
        common401Assertions
    ));
});

folders.push({
    name: "01-TC-M03-349-Sin-Cabecera-O-Malformada",
    item: folder349Items
});

// ── CARPETA 02: TC-M03-350 TOKENS EXPIRADOS ───────────────────────────────────
folders.push({
    name: "02-TC-M03-350-Tokens-Expirados",
    item: [
        makeItem(
            "350-A-Token-Expirado-1-Hora",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            [makeHeader("Authorization", "Bearer {{token_expirado_1h}}")],
            null,
            [
                'const jwtSecret = pm.collectionVariables.get("jwt_secret");',
                'const baseToken = pm.collectionVariables.get("token_admin");',
                'if (!jwtSecret || jwtSecret.trim() === "") {',
                '    console.log("[BLOQUEADO] Subcaso 350(a): TEST_JWT_SECRET no definido en el entorno. Subcaso bloqueado sin pm.test.");',
                '    pm.collectionVariables.set("subcaso_350a_bloqueado", "true");',
                '} else {',
                '    pm.collectionVariables.set("subcaso_350a_bloqueado", "false");',
                '    if (baseToken && baseToken.includes(".")) {',
                '        const parts = baseToken.split(".");',
                '        let payload = JSON.parse(CryptoJS.enc.Utf8.stringify(CryptoJS.enc.Base64.parse(parts[1])));',
                '        payload.exp = Math.floor(Date.now() / 1000) - 3600;',
                '        const newPayloadStr = CryptoJS.enc.Base64.stringify(CryptoJS.enc.Utf8.parse(JSON.stringify(payload))).replace(/=+$/, "");',
                '        const tokenContent = parts[0] + "." + newPayloadStr;',
                '        const hash = CryptoJS.HmacSHA256(tokenContent, jwtSecret);',
                '        const newSig = CryptoJS.enc.Base64.stringify(hash).replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/, "");',
                '        pm.collectionVariables.set("token_expirado_1h", parts[0] + "." + newPayloadStr + "." + newSig);',
                '    }',
                '}'
            ],
            [
                'const bloqueado = pm.collectionVariables.get("subcaso_350a_bloqueado");',
                'if (bloqueado === "true") {',
                '    console.log("[BLOQUEADO] Subcaso 350(a) ignorado en ejecución de aserciones por falta de TEST_JWT_SECRET.");',
                '} else {',
                '    pm.test("Status 401 - Token expirado hace 1h rechazado", function () {',
                '        pm.response.to.have.status(401);',
                '    });',
                '    pm.test("Error uniforme TOKEN_EXPIRADO", function () {',
                '        const b = pm.response.json();',
                '        pm.expect(b.error_code).to.equal("TOKEN_EXPIRADO");',
                '        pm.collectionVariables.set("msg_350a", b.message);',
                '    });',
                '}'
            ]
        ),
        makeItem(
            "350-B-Token-Expirado-1-Segundo",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            [makeHeader("Authorization", "Bearer {{token_expirado_1s}}")],
            null,
            [
                'const jwtSecret = pm.collectionVariables.get("jwt_secret");',
                'const baseToken = pm.collectionVariables.get("token_admin");',
                'if (!jwtSecret || jwtSecret.trim() === "") {',
                '    console.log("[BLOQUEADO] Subcaso 350(b): TEST_JWT_SECRET no definido en el entorno. Subcaso bloqueado sin pm.test.");',
                '    pm.collectionVariables.set("subcaso_350b_bloqueado", "true");',
                '} else {',
                '    pm.collectionVariables.set("subcaso_350b_bloqueado", "false");',
                '    if (baseToken && baseToken.includes(".")) {',
                '        const parts = baseToken.split(".");',
                '        let payload = JSON.parse(CryptoJS.enc.Utf8.stringify(CryptoJS.enc.Base64.parse(parts[1])));',
                '        payload.exp = Math.floor(Date.now() / 1000) - 1;',
                '        const newPayloadStr = CryptoJS.enc.Base64.stringify(CryptoJS.enc.Utf8.parse(JSON.stringify(payload))).replace(/=+$/, "");',
                '        const tokenContent = parts[0] + "." + newPayloadStr;',
                '        const hash = CryptoJS.HmacSHA256(tokenContent, jwtSecret);',
                '        const newSig = CryptoJS.enc.Base64.stringify(hash).replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/, "");',
                '        pm.collectionVariables.set("token_expirado_1s", parts[0] + "." + newPayloadStr + "." + newSig);',
                '    }',
                '}'
            ],
            [
                'const bloqueado = pm.collectionVariables.get("subcaso_350b_bloqueado");',
                'if (bloqueado === "true") {',
                '    console.log("[BLOQUEADO] Subcaso 350(b) ignorado por falta de TEST_JWT_SECRET.");',
                '} else {',
                '    pm.test("Status 401 - Token con exp expirado hace 1s rechazado", function () {',
                '        pm.response.to.have.status(401);',
                '    });',
                '}'
            ]
        )
    ]
});

// ── CARPETA 03: TC-M03-351 TOKENS MANIPULADOS Y UNIFORMIDAD ───────────────────
folders.push({
    name: "03-TC-M03-351-Tokens-Manipulados-y-Uniformidad",
    item: [
        makeItem(
            "351-A-Token-Algoritmo-None",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            [makeHeader("Authorization", "Bearer {{token_alg_none}}")],
            null,
            [
                'const baseToken = pm.collectionVariables.get("token_admin");',
                'if (baseToken && baseToken.includes(".")) {',
                '    const parts = baseToken.split(".");',
                '    const headerNone = CryptoJS.enc.Base64.stringify(CryptoJS.enc.Utf8.parse(JSON.stringify({ alg: "none", typ: "JWT" }))).replace(/=+$/, "");',
                '    pm.collectionVariables.set("token_alg_none", headerNone + "." + parts[1] + ".");',
                '}'
            ],
            [
                'pm.test("Status 401 - Token con alg=none rechazado", function () {',
                '    pm.response.to.have.status(401);',
                '});',
                'pm.test("Mensaje uniforme TOKEN_INVALIDO", function () {',
                '    const b = pm.response.json();',
                '    pm.expect(b.error_code).to.equal("TOKEN_INVALIDO");',
                '    pm.expect(b.message).to.equal("El token es inválido o ha expirado.");',
                '    pm.collectionVariables.set("msg_351a", b.message);',
                '});'
            ]
        ),
        makeItem(
            "351-B-Token-Payload-Alterado",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            [makeHeader("Authorization", "Bearer {{token_alterado}}")],
            null,
            [
                'const baseToken = pm.collectionVariables.get("token_admin");',
                'if (baseToken && baseToken.includes(".")) {',
                '    const parts = baseToken.split(".");',
                '    try {',
                '        let payload = JSON.parse(CryptoJS.enc.Utf8.stringify(CryptoJS.enc.Base64.parse(parts[1])));',
                '        payload.sub = "999999";',
                '        payload.rol = 1;',
                '        const newPayloadStr = CryptoJS.enc.Base64.stringify(CryptoJS.enc.Utf8.parse(JSON.stringify(payload))).replace(/=+$/, "");',
                '        pm.collectionVariables.set("token_alterado", parts[0] + "." + newPayloadStr + "." + parts[2]);',
                '    } catch (e) {',
                '        pm.collectionVariables.set("token_alterado", baseToken);',
                '    }',
                '}'
            ],
            [
                'pm.test("Status 401 - Payload alterado rechazado por firma rota", function () {',
                '    pm.response.to.have.status(401);',
                '});',
                'pm.test("Mensaje uniforme TOKEN_INVALIDO idéntico a 351(a)", function () {',
                '    const b = pm.response.json();',
                '    pm.expect(b.error_code).to.equal("TOKEN_INVALIDO");',
                '    pm.expect(b.message).to.equal("El token es inválido o ha expirado.");',
                '    const msgA = pm.collectionVariables.get("msg_351a");',
                '    if (msgA) {',
                '        pm.expect(b.message).to.equal(msgA);',
                '    }',
                '});'
            ]
        ),
        makeItem(
            "351-C-Token-Firma-Clave-Incorrecta",
            "GET",
            "{{baseUrl}}/iot/auditoria",
            [makeHeader("Authorization", "Bearer {{token_clave_falsa}}")],
            null,
            [
                'const baseToken = pm.collectionVariables.get("token_admin");',
                'if (baseToken && baseToken.includes(".")) {',
                '    const parts = baseToken.split(".");',
                '    const tokenContent = parts[0] + "." + parts[1];',
                '    const fakeSecret = "clave_completamente_falsa_para_test_seguridad_123";',
                '    const hash = CryptoJS.HmacSHA256(tokenContent, fakeSecret);',
                '    const fakeSig = CryptoJS.enc.Base64.stringify(hash).replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/, "");',
                '    pm.collectionVariables.set("token_clave_falsa", tokenContent + "." + fakeSig);',
                '}'
            ],
            [
                'pm.test("Status 401 - Token con firma de clave ajena rechazado", function () {',
                '    pm.response.to.have.status(401);',
                '});',
                'pm.test("Mensaje genérico uniforme sin filtrar internals criptográficos", function () {',
                '    const b = pm.response.json();',
                '    pm.expect(b.error_code).to.equal("TOKEN_INVALIDO");',
                '    pm.expect(b.message).to.equal("El token es inválido o ha expirado.");',
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
        _postman_id: "tc-m03-g183-owasp-api2-v1",
        name: "TC-M03-G183 - OWASP API2 Autenticación y Tokens Auditoría IoT (RF-63)",
        description: "Suite automatizada Newman para TC-M03-G183 (RF-63). Verifica rechazo de peticiones sin token o malformadas, tokens expirados y manipulados (alg=none, firma inválida, payload alterado).",
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
        { key: "jwt_secret", value: "" },
        { key: "token_admin", value: "" },
        { key: "test_id_evento", value: "" },
        { key: "token_expirado_1h", value: "" },
        { key: "token_expirado_1s", value: "" },
        { key: "token_alg_none", value: "" },
        { key: "token_alterado", value: "" },
        { key: "token_clave_falsa", value: "" },
        { key: "subcaso_350a_bloqueado", value: "false" },
        { key: "subcaso_350b_bloqueado", value: "false" },
        { key: "msg_351a", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g183.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G183 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
