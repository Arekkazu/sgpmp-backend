const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G176
// OWASP API8:2023 Security Misconfiguration & API10:2023 Unsafe Consumption of APIs
// Fuzzing e Inyección sobre RF-62 (/iot/calidad y /iot/calidad/reevaluar)
//
// 9 PAYLOADS ANÓMALOS + RECHAZO CONTENT-TYPE + COMPROBACIÓN NO-DEGRADACIÓN:
// 1. GET /iot/calidad?id_sensor=abc
// 2. GET /iot/calidad?pagina=-1
// 3. GET /iot/calidad?por_pagina=99999
// 4. GET /iot/calidad?fecha_desde=not-a-date
// 5. GET /iot/calidad?clasificacion=<script>alert(1)</script> (Sin XSS reflejado)
// 6. POST /iot/calidad/reevaluar {id_sensor: [], fecha_desde: 123}
// 7. GET /iot/calidad con unicode especial (\u0000, emojis, RTL)
// 8. GET /iot/calidad?fecha_desde=9999-12-31T23:59:59Z
// 9. GET /iot/calidad?pagina=99999999999999999999
// 10. POST /iot/calidad/reevaluar con Content-Type: text/plain
// 11. GET /iot/calidad válido para confirmar servicio sin degradación

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
        // Agregar Content-Type solo si no viene explícito
        if (!headers || !headers.some(h => h.key.toLowerCase() === "content-type")) {
            item.request.header.push(makeHeader("Content-Type", "application/json"));
        }
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

// ── 00. LOGIN BASELINE ────────────────────────────────────────────────────────
folders.push({
    name: "00-Preflight-Login-Admin",
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
                'pm.test("Status 200 - Login exitoso", function () {',
                '    pm.response.to.have.status(200);',
                '    pm.collectionVariables.set("token_admin", pm.response.json().token);',
                '});'
            ]
        )
    ]
});

// Aserciones comunes de Fuzzing: 400 o 422, NUNCA 500, SIN stack trace
const fuzzAssertions = [
    'pm.test("Rechazo controlado 400 o 422 (Nunca 500)", function () {',
    '    pm.expect(pm.response.code).to.be.oneOf([400, 422]);',
    '});',
    'pm.test("Sin stack trace ni exposición de código interno", function () {',
    '    const t = pm.response.text().toLowerCase();',
    '    pm.expect(t).to.not.include("traceback");',
    '    pm.expect(t).to.not.include("file \"");',
    '    pm.expect(t).to.not.include("sqlalchemy.");',
    '});'
];

// ── 01. BATERÍA DE 9 PAYLOADS ANÓMALOS + CONTENT-TYPE MISMATCH ────────────────
const fuzzItems = [
    // 1. String en entero
    makeItem(
        "01-Fuzz-id_sensor-String",
        "GET",
        "{{baseUrl}}/iot/calidad?id_sensor=abc",
        makeAuthHeaders(),
        null,
        [],
        fuzzAssertions
    ),
    // 2. Página negativa
    makeItem(
        "02-Fuzz-pagina-Negativa",
        "GET",
        "{{baseUrl}}/iot/calidad?pagina=-1",
        makeAuthHeaders(),
        null,
        [],
        fuzzAssertions
    ),
    // 3. Por página excesivo (límite le=200)
    makeItem(
        "03-Fuzz-por_pagina-Excesivo",
        "GET",
        "{{baseUrl}}/iot/calidad?por_pagina=99999",
        makeAuthHeaders(),
        null,
        [],
        fuzzAssertions
    ),
    // 4. Fecha inválida
    makeItem(
        "04-Fuzz-fecha_desde-NoFecha",
        "GET",
        "{{baseUrl}}/iot/calidad?fecha_desde=not-a-date",
        makeAuthHeaders(),
        null,
        [],
        fuzzAssertions
    ),
    // 5. Inyección XSS en clasificación (sin reflejo)
    makeItem(
        "05-Fuzz-XSS-En-Filtro",
        "GET",
        "{{baseUrl}}/iot/calidad?clasificacion=<script>alert(1)</script>",
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("Rechazo controlado o lista vacía (Sin 500)", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 400, 422]);',
            '});',
            'pm.test("Sin XSS reflejado en cuerpo de respuesta", function () {',
            '    pm.expect(pm.response.text()).to.not.include("<script>alert(1)</script>");',
            '});'
        ]
    ),
    // 6. Body malformado en POST /reevaluar
    makeItem(
        "06-Fuzz-Body-Tipos-Incorrectos-Reevaluar",
        "POST",
        "{{baseUrl}}/iot/calidad/reevaluar",
        makeAuthHeaders(),
        {
            id_sensor: ["no_es_entero"],
            fecha_desde: 12345,
            fecha_hasta: "invalida",
            causa_documentada: 999
        },
        [],
        fuzzAssertions
    ),
    // 7. Unicode especial, NUL byte y Emojis en query params
    makeItem(
        "07-Fuzz-Unicode-Emojis-NulByte",
        "GET",
        "{{baseUrl}}/iot/calidad?clasificacion=%00%F0%9F%94%A5%E2%80%AEtest",
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("Respuesta segura ante Unicode/NUL byte (Sin 500)", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 400, 422]);',
            '});'
        ]
    ),
    // 8. Fecha hiper-futura
    makeItem(
        "08-Fuzz-Fecha-HiperFutura",
        "GET",
        "{{baseUrl}}/iot/calidad?fecha_desde=9999-12-31T23:59:59Z",
        makeAuthHeaders(),
        null,
        [],
        [
            'pm.test("Respuesta segura ante fecha extrema (200 vacía o 400/422, sin 500)", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 400, 422]);',
            '});'
        ]
    ),
    // 9. Overflow de entero en página
    makeItem(
        "09-Fuzz-Overflow-Pagina",
        "GET",
        "{{baseUrl}}/iot/calidad?pagina=99999999999999999999",
        makeAuthHeaders(),
        null,
        [],
        fuzzAssertions
    ),
    // 10. Content-Type mismatch: text/plain en endpoint que espera application/json
    makeItem(
        "10-Fuzz-ContentType-Mismatch",
        "POST",
        "{{baseUrl}}/iot/calidad/reevaluar",
        [
            makeHeader("Authorization", "Bearer {{token_admin}}"),
            makeHeader("Content-Type", "text/plain")
        ],
        "esto_es_texto_plano_no_json",
        [],
        [
            'pm.test("Rechazo ante Content-Type text/plain (400, 415 o 422, nunca 500)", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([400, 415, 422]);',
            '});'
        ]
    )
];

folders.push({
    name: "01-Bateria-Fuzzing-OWASP",
    item: fuzzItems
});

// ── 02. COMPROBACIÓN FINAL DE NO-DEGRADACIÓN ─────────────────────────────────
folders.push({
    name: "02-Comprobacion-No-Degradacion",
    item: [
        makeItem(
            "20-GET-Calidad-Valido-Post-Fuzzing",
            "GET",
            "{{baseUrl}}/iot/calidad?pagina=1&por_pagina=10",
            makeAuthHeaders(),
            null,
            [],
            [
                'pm.test("Status 200 - Servicio completamente operativo y sin degradación tras fuzzing", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.items).to.be.an("array");',
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
        _postman_id: "tc-m03-g176-fuzzing-v1",
        name: "TC-M03-G176 - Fuzzing e Inyeccion OWASP API8/API10 RF-62",
        description: "Suite automatizada Newman para TC-M03-G176 (RF-62). Verifica resiliencia ante datos malformados, inyección XSS y robustez de Content-Type sin degradación del servicio.",
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
        { key: "token_admin", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g176.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G176 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
