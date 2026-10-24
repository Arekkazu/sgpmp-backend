const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G173
// OWASP API2: Broken Authentication & Token Verification (RF-62)
// Endpoints evaluados:
// 1. GET  /iot/calidad
// 2. GET  /iot/calidad/1
// 3. POST /iot/calidad/1/evaluar
// 4. POST /iot/calidad/reevaluar
//
// Subcasos:
// - TC-M03-331: Ausencia y malformación de cabecera Authorization (sin header, vacío forzado, Bearer solo) -> HTTP 401
// - TC-M03-332: Manipulación de tokens JWT (expirado [BLOQUEADO puro sin secret], alg=none, payload alterado, firma clave incorrecta)

function makeHeader(key, value) {
    return { key, value };
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

// ── CARPETA 00: PREFLIGHT Y BASELINE LOGIN ────────────────────────────────────
folders.push({
    name: "00-Preflight-y-Baseline-Token",
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
                'pm.test("Status 200 - Login exitoso para generar token base", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.token).to.be.a("string").and.not.be.empty;',
                '    pm.collectionVariables.set("token_admin", res.token);',
                '});'
            ]
        )
    ]
});

// Helper para validación estándar de respuesta 401
const common401Assertions = [
    'pm.test("Status 401 - No autorizado", function () {',
    '    pm.response.to.have.status(401);',
    '});',
    'pm.test("Estructura de error 401 conforme a estándar", function () {',
    '    const b = pm.response.json();',
    '    pm.expect(b.error_code).to.be.a("string");',
    '    pm.expect(b.message).to.be.a("string");',
    '    pm.expect(b.message.toLowerCase()).to.not.include("traceback");',
    '    pm.expect(b.message.toLowerCase()).to.not.include("sql");',
    '    pm.expect(b.message.toLowerCase()).to.not.include("line ");',
    '});'
];

// ── CARPETA 01: TC-M03-331 SIN CABECERA O MALFORMADA ──────────────────────────
const endpoints = [
    { name: "Listar-Calidad", method: "GET", url: "{{baseUrl}}/iot/calidad", body: null },
    { name: "Obtener-Calidad-Por-ID", method: "GET", url: "{{baseUrl}}/iot/calidad/1", body: null },
    { name: "Evaluar-Calidad-Lectura", method: "POST", url: "{{baseUrl}}/iot/calidad/1/evaluar", body: {} },
    {
        name: "Reevaluar-Calidad",
        method: "POST",
        url: "{{baseUrl}}/iot/calidad/reevaluar",
        body: {
            id_sensor: 1,
            fecha_desde: "2026-10-10T00:00:00Z",
            fecha_hasta: "2026-10-10T12:00:00Z",
            causa_documentada: "Error justificado de configuracion en sensor ambiental"
        }
    }
];

const folder331Items = [];
endpoints.forEach(ep => {
    // 1. Sin header
    folder331Items.push(makeItem(
        `331-SinHeader-${ep.name}`,
        ep.method,
        ep.url,
        [],
        ep.body,
        [],
        common401Assertions
    ));

    // 2. Header Authorization vacío (se usa espacio explícito " " para forzar a Postman/Newman a emitir el header sin omitirlo)
    folder331Items.push(makeItem(
        `331-HeaderVacio-${ep.name}`,
        ep.method,
        ep.url,
        [makeHeader("Authorization", " ")],
        ep.body,
        [],
        common401Assertions
    ));

    // 3. Header Bearer sin token
    folder331Items.push(makeItem(
        `331-BearerSinToken-${ep.name}`,
        ep.method,
        ep.url,
        [makeHeader("Authorization", "Bearer ")],
        ep.body,
        [],
        common401Assertions
    ));
});

folders.push({
    name: "01-TC-M03-331-Sin-Cabecera-O-Malformada",
    item: folder331Items
});

// ── CARPETA 02: TC-M03-332 MANIPULACIÓN DE TOKENS JWT ─────────────────────────
folders.push({
    name: "02-TC-M03-332-Manipulacion-Tokens-JWT",
    item: [
        // (a) Token expirado hace 1 hora (Condicionado a TEST_JWT_SECRET)
        makeItem(
            "332-A-Token-Expirado",
            "GET",
            "{{baseUrl}}/iot/calidad",
            [makeHeader("Authorization", "Bearer {{token_expirado}}")],
            null,
            [
                'const jwtSecret = pm.collectionVariables.get("jwt_secret");',
                'const baseToken = pm.collectionVariables.get("token_admin");',
                'if (!jwtSecret || jwtSecret.trim() === "") {',
                '    // [BLOQUEADO PURO]: Sin la clave secreta real para firmar con exp pasado, no se aísla el chequeo de expiración.',
                '    // Se prohíbe el uso de tokens sintéticos. Solo console.log, sin pm.test en la pestaña de tests.',
                '    console.log("[BLOQUEADO] Subcaso 332(a): TEST_JWT_SECRET no definido en el entorno. Subcaso bloqueado sin pm.test para evitar falsos positivos.");',
                '    pm.collectionVariables.set("subcaso_332a_bloqueado", "true");',
                '} else {',
                '    pm.collectionVariables.set("subcaso_332a_bloqueado", "false");',
                '    if (baseToken && baseToken.includes(".")) {',
                '        const parts = baseToken.split(".");',
                '        let payload = JSON.parse(CryptoJS.enc.Utf8.stringify(CryptoJS.enc.Base64.parse(parts[1])));',
                '        payload.exp = Math.floor(Date.now() / 1000) - 3600;',
                '        const newPayloadStr = CryptoJS.enc.Base64.stringify(CryptoJS.enc.Utf8.parse(JSON.stringify(payload))).replace(/=+$/, "");',
                '        const tokenContent = parts[0] + "." + newPayloadStr;',
                '        const hash = CryptoJS.HmacSHA256(tokenContent, jwtSecret);',
                '        const newSig = CryptoJS.enc.Base64.stringify(hash).replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/, "");',
                '        pm.collectionVariables.set("token_expirado", parts[0] + "." + newPayloadStr + "." + newSig);',
                '    }',
                '}'
            ],
            [
                'const bloqueado = pm.collectionVariables.get("subcaso_332a_bloqueado");',
                'if (bloqueado === "true") {',
                '    console.log("[BLOQUEADO] Subcaso 332(a) ignorado en ejecución de aserciones por falta de TEST_JWT_SECRET.");',
                '} else {',
                '    pm.test("Status 401 - Token expirado legítimo rechazado", function () {',
                '        pm.response.to.have.status(401);',
                '    });',
                '    pm.test("Error uniforme TOKEN_EXPIRADO", function () {',
                '        const b = pm.response.json();',
                '        pm.expect(b.error_code).to.equal("TOKEN_EXPIRADO");',
                '        pm.collectionVariables.set("msg_332a", b.message);',
                '    });',
                '}'
            ]
        ),
        // (b) Algoritmo "none"
        makeItem(
            "332-B-Token-Algoritmo-None",
            "GET",
            "{{baseUrl}}/iot/calidad",
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
                '    pm.collectionVariables.set("msg_332b", b.message);',
                '});'
            ]
        ),
        // (c) Payload alterado con firma original
        makeItem(
            "332-C-Token-Payload-Alterado",
            "GET",
            "{{baseUrl}}/iot/calidad",
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
                'pm.test("Mensaje uniforme idéntico a 332(b)", function () {',
                '    const b = pm.response.json();',
                '    pm.expect(b.error_code).to.equal("TOKEN_INVALIDO");',
                '    pm.expect(b.message).to.equal("El token es inválido o ha expirado.");',
                '    const msgB = pm.collectionVariables.get("msg_332b");',
                '    if (msgB) {',
                '        pm.expect(b.message, "Mensaje idéntico entre manipulaciones b y c").to.equal(msgB);',
                '    }',
                '});'
            ]
        ),
        // (d) Token firmado con clave incorrecta
        makeItem(
            "332-D-Token-Firma-Clave-Incorrecta",
            "GET",
            "{{baseUrl}}/iot/calidad",
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
                'pm.test("Status 401 - Firma con clave espuria rechazada", function () {',
                '    pm.response.to.have.status(401);',
                '});',
                'pm.test("Mensaje uniforme idéntico a 332(b) y 332(c)", function () {',
                '    const b = pm.response.json();',
                '    pm.expect(b.error_code).to.equal("TOKEN_INVALIDO");',
                '    pm.expect(b.message).to.equal("El token es inválido o ha expirado.");',
                '    const msgB = pm.collectionVariables.get("msg_332b");',
                '    if (msgB) {',
                '        pm.expect(b.message, "Mensaje idéntico entre manipulaciones b, c y d").to.equal(msgB);',
                '    }',
                '});'
            ]
        )
    ]
});

// ── CARPETA 99: TEARDOWN Y ROLLBACK DEL SANDBOX ───────────────────────────────
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
        _postman_id: "tc-m03-g173-owasp-api2-v2",
        name: "TC-M03-G173 - OWASP API2 Autenticación y Tokens RF-62",
        description: "Suite automatizada Newman para TC-M03-G173 (RF-62). Verifica seguridad de autenticación y tokens JWT (OWASP API2) sobre todos los endpoints de calidad.",
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
        { key: "token_expirado", value: "" },
        { key: "token_alg_none", value: "" },
        { key: "token_alterado", value: "" },
        { key: "token_clave_falsa", value: "" },
        { key: "subcaso_332a_bloqueado", value: "false" },
        { key: "msg_332b", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g173.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G173 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
