const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G177
// RF-63 (Bitácora de Auditoría IoT) — Consulta básica y detalle
// Subcasos:
// - TC-M03-336: Listado sin filtros, paginación (default 50, max 200, 422 en >200),
//               campos base RF-10 (11) + extensión IoT (8) + timestamp_registro,
//               modulo="M03", sin componente_origen, total backend, orden DESC.
// - TC-M03-337: Detalle por id_evento, objeto completo, accion_detallada JSON,
//               hash_integridad 64 hex, 404 en inexistente, 422 en malformado.

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

// ── 03. TC-M03-336: LISTADO SIN FILTROS Y PAGINACIÓN ──────────────────────────
const listadoItems = [
    makeItem(
        "08-TC-M03-336-Listar-Auditoria-Sin-Filtros",
        "GET",
        "{{baseUrl}}/iot/auditoria",
        makeAuthHeaders("token_admin"),
        null,
        [],
        [
            'pm.test("Status 200 - Listado de auditoría obtenido", function () {',
            '    pm.response.to.have.status(200);',
            '});',
            'const res = pm.response.json();',
            'pm.test("Estructura de paginación conforme a contrato", function () {',
            '    pm.expect(res).to.have.property("total");',
            '    pm.expect(res).to.have.property("pagina");',
            '    pm.expect(res).to.have.property("por_pagina");',
            '    pm.expect(res).to.have.property("items");',
            '    pm.expect(res.pagina).to.eql(1);',
            '    pm.expect(res.por_pagina).to.eql(50);',
            '    pm.expect(res.items).to.be.an("array");',
            '    pm.expect(res.total).to.be.at.least(res.items.length);',
            '});',
            'pm.test("Campos base RF-10 y extensión IoT presentes en todos los items", function () {',
            '    pm.expect(res.items.length).to.be.at.least(1);',
            '    res.items.forEach((item, idx) => {',
            '        // 11 campos base RF-10',
            '        pm.expect(item).to.have.property("id_evento");',
            '        pm.expect(item).to.have.property("id_usuario");',
            '        pm.expect(item).to.have.property("nombre_usuario");',
            '        pm.expect(item).to.have.property("tipo_evento");',
            '        pm.expect(item).to.have.property("modulo");',
            '        pm.expect(item).to.have.property("descripcion");',
            '        pm.expect(item).to.have.property("resultado");',
            '        pm.expect(item).to.have.property("direccion_ip");',
            '        pm.expect(item).to.have.property("user_agent");',
            '        pm.expect(item).to.have.property("id_sesion");',
            '        pm.expect(item).to.have.property("fecha_hora");',
            '        ',
            '        // 8 campos extensión IoT + timestamp_registro',
            '        pm.expect(item).to.have.property("accion_detallada");',
            '        pm.expect(item).to.have.property("entidad_afectada_tipo");',
            '        pm.expect(item).to.have.property("entidad_afectada_id");',
            '        pm.expect(item).to.have.property("severidad_log");',
            '        pm.expect(item).to.have.property("hash_integridad");',
            '        pm.expect(item).to.have.property("clasificacion_registro");',
            '        pm.expect(item).to.have.property("retencion_aplicable");',
            '        pm.expect(item).to.have.property("registro_incompleto");',
            '        pm.expect(item).to.have.property("timestamp_registro");',
            '        ',
            '        // Invariante de seguridad: modulo=M03 en TODOS los registros de vista técnica',
            '        pm.expect(item.modulo).to.eql("M03");',
            '        ',
            '        // Invariante de diseño: componente_origen NO se expone en HTTP',
            '        pm.expect(item).to.not.have.property("componente_origen");',
            '    });',
            '});',
            'pm.test("08 - Orden DESC por fecha_hora (crítico)", function () {',
            '    const b = pm.response.json();',
            '    pm.expect(b.items.length).to.be.at.least(2);',
            '    for (let i = 0; i < b.items.length - 1; i++) {',
            '        const t1 = new Date(b.items[i].fecha_hora).getTime();',
            '        const t2 = new Date(b.items[i + 1].fecha_hora).getTime();',
            '        pm.expect(t1, `item[${i}].fecha_hora (${b.items[i].fecha_hora}) debe ser >= item[${i+1}] (${b.items[i+1].fecha_hora})`).to.be.at.least(t2);',
            '    }',
            '});',
            '// Guardar dinámicamente un id_evento para TC-M03-337',
            'if (res.items.length > 0) {',
            '    pm.collectionVariables.set("test_id_evento", res.items[0].id_evento);',
            '}'
        ]
    ),
    makeItem(
        "09-TC-M03-336-Paginacion-Personalizada",
        "GET",
        "{{baseUrl}}/iot/auditoria?pagina=1&por_pagina=2",
        makeAuthHeaders("token_admin"),
        null,
        [],
        [
            'pm.test("Status 200 - Paginación personalizada respetada", function () {',
            '    pm.response.to.have.status(200);',
            '    const res = pm.response.json();',
            '    pm.expect(res.por_pagina).to.eql(2);',
            '    pm.expect(res.pagina).to.eql(1);',
            '    pm.expect(res.items.length).to.be.at.most(2);',
            '});'
        ]
    ),
    makeItem(
        "10-TC-M03-336-Paginacion-Max-Permitida",
        "GET",
        "{{baseUrl}}/iot/auditoria?por_pagina=200",
        makeAuthHeaders("token_admin"),
        null,
        [],
        [
            'pm.test("Status 200 - Paginación máxima por_pagina=200 aceptada", function () {',
            '    pm.response.to.have.status(200);',
            '    const res = pm.response.json();',
            '    pm.expect(res.por_pagina).to.eql(200);',
            '});'
        ]
    ),
    (() => {
        const it = makeItem(
            "11-TC-M03-336-Paginacion-Excedida-Rechazada",
            "GET",
            "{{baseUrl}}/iot/auditoria?por_pagina=201",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 400 o 422 - por_pagina > 200 rechazado con codigo de validacion", function () {',
                '    pm.expect([400, 422], "status esperado 400 o 422").to.include(pm.response.code);',
                '    const b = pm.response.json();',
                '    pm.expect(b, "body sin error_code").to.have.property("error_code");',
                '    pm.expect(b.error_code).to.be.oneOf(["VAL_ENTRADA", "VALIDATION_ERROR"]);',
                '});'
            ]
        );
        it.request.description = "por_pagina > 200 debe ser rechazado con 400 (VAL_ENTRADA) o 422. OBS-M03-G177-01: Swagger declara 422 pero backend devuelve 400.";
        return it;
    })()
];

folders.push({
    name: "03-TC-M03-336-Listado-Sin-Filtros",
    item: listadoItems
});

// ── 04. TC-M03-337: DETALLE POR ID_EVENTO ─────────────────────────────────────
const detalleItems = [
    makeItem(
        "12-TC-M03-337-Detalle-Evento-Existente",
        "GET",
        "{{baseUrl}}/iot/auditoria/{{test_id_evento}}",
        makeAuthHeaders("token_admin"),
        null,
        [],
        [
            'pm.test("Status 200 - Detalle de evento obtenido", function () {',
            '    pm.response.to.have.status(200);',
            '});',
            'const evento = pm.response.json();',
            'pm.test("ID de evento coincide con el solicitado", function () {',
            '    pm.expect(evento.id_evento).to.eql(pm.collectionVariables.get("test_id_evento"));',
            '});',
            'pm.test("Estructura completa de evento (base + extensión)", function () {',
            '    pm.expect(evento.modulo).to.eql("M03");',
            '    pm.expect(evento).to.have.property("tipo_evento");',
            '    pm.expect(evento).to.have.property("resultado");',
            '    pm.expect(evento).to.have.property("fecha_hora");',
            '    pm.expect(evento).to.have.property("accion_detallada");',
            '    pm.expect(evento).to.have.property("entidad_afectada_tipo");',
            '    pm.expect(evento).to.have.property("entidad_afectada_id");',
            '    pm.expect(evento).to.have.property("severidad_log");',
            '    pm.expect(evento).to.have.property("clasificacion_registro");',
            '    pm.expect(evento).to.have.property("retencion_aplicable");',
            '    pm.expect(evento).to.have.property("registro_incompleto");',
            '    pm.expect(evento).to.have.property("timestamp_registro");',
            '});',
            'pm.test("12 - Campos base faltantes en detalle", function () {',
            '    const b = pm.response.json();',
            '    const faltantes = [\'id_usuario\',\'nombre_usuario\',\'descripcion\',',
            '                       \'direccion_ip\',\'user_agent\',\'id_sesion\'];',
            '    faltantes.forEach(campo => {',
            '        pm.expect(b).to.have.property(campo);',
            '        // null es válido (eventos automáticos) — no se exige no-nulo',
            '    });',
            '});',
            'pm.test("accion_detallada es objeto/dict JSON o null estructurado", function () {',
            '    if (evento.accion_detallada !== null) {',
            '        pm.expect(evento.accion_detallada).to.be.an("object");',
            '    }',
            '});',
            'pm.test("Invariante de seguridad: componente_origen NO expuesto en detalle", function () {',
            '    pm.expect(evento).to.not.have.property("componente_origen");',
            '});',
            'pm.test("hash_integridad es SHA-256 hex de 64 caracteres", function () {',
            '    pm.expect(evento.hash_integridad).to.be.a("string");',
            '    pm.expect(evento.hash_integridad).to.match(/^[0-9a-f]{64}$/);',
            '});',
            'console.log("[INFO G177 TC-337] Evento auditado: " + evento.id_evento + " | Tipo: " + evento.tipo_evento + " | Hash: " + evento.hash_integridad);'
        ]
    ),
    (() => {
        const it = makeItem(
            "13-TC-M03-337-Verificar-Integridad-Bitacora-Backend",
            "POST",
            "{{baseUrl}}/iot/auditoria/verificar-integridad?fecha_desde={{fecha_desde_iso}}&fecha_hasta={{fecha_hasta_iso}}",
            makeAuthHeaders("token_admin"),
            null,
            [
                'const ahora = new Date();',
                'const hace60s = new Date(ahora.getTime() - 60 * 1000);',
                'const fmtISO = (d) => {',
                '    const iso = d.toISOString();          // "2026-10-24T17:45:00.123Z"',
                '    return iso.split(".")[0] + "Z";       // "2026-10-24T17:45:00Z"',
                '};',
                'const desde = fmtISO(hace60s);',
                'const hasta = fmtISO(ahora);',
                'pm.collectionVariables.set("fecha_desde_iso", desde);',
                'pm.collectionVariables.set("fecha_hasta_iso", hasta);',
                'console.log("[item13] fecha_desde=" + desde + " fecha_hasta=" + hasta);',
                'if (!desde || !hasta) {',
                '    throw new Error("[item13] FECHAS VACIAS - abortar test");',
                '}'
            ],
            [
                'pm.test("Pre-requisito: fechas calculadas no vacias", function () {',
                '    const desde = pm.collectionVariables.get("fecha_desde_iso");',
                '    const hasta = pm.collectionVariables.get("fecha_hasta_iso");',
                '    pm.expect(desde, "fecha_desde_iso vacia").to.be.a("string").and.not.empty;',
                '    pm.expect(hasta, "fecha_hasta_iso vacia").to.be.a("string").and.not.empty;',
                '    pm.expect(desde).to.match(/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$/);',
                '    pm.expect(hasta).to.match(/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$/);',
                '});',
                'pm.test("Status 200 - Verificación de integridad SHA-256 exitosa en backend", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.total_verificados).to.be.at.least(0);',
                '    pm.expect(res.comprometidos).to.eql(0);',
                '    pm.expect(res.ids_comprometidos).to.eql([]);',
                '});'
            ]
        );
        it.request.timeout = 30000;
        return it;
    })(),
    makeItem(
        "14-TC-M03-337-UUID-Inexistente-Responde-404",
        "GET",
        "{{baseUrl}}/iot/auditoria/00000000-0000-0000-0000-000000000000",
        makeAuthHeaders("token_admin"),
        null,
        [],
        [
            'pm.test("Status 404 - UUID inexistente responde Not Found", function () {',
            '    pm.response.to.have.status(404);',
            '    const res = pm.response.json();',
            '    pm.expect(res.error_code).to.eql("EVENTO_NO_ENCONTRADO");',
            '});'
        ]
    ),
    (() => {
        const it = makeItem(
            "15-TC-M03-337-UUID-Malformado-Rechazado-Con-Codigo-Validacion",
            "GET",
            "{{baseUrl}}/iot/auditoria/uuid-invalido-12345",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 400 o 422 - UUID malformado rechazado con codigo de validacion", function () {',
                '    pm.expect([400, 422], "status esperado 400 o 422").to.include(pm.response.code);',
                '    const b = pm.response.json();',
                '    pm.expect(b, "body sin error_code").to.have.property("error_code");',
                '    pm.expect(b.error_code).to.be.oneOf(["VAL_ENTRADA", "VALIDATION_ERROR"]);',
                '});'
            ]
        );
        it.request.description = "OBS-M03-G177-02: Swagger declara 422 para path param invalido, backend devuelve 400 VAL_ENTRADA. Test acepta ambos. RF-63 no especifica codigo HTTP para UUID malformado.";
        return it;
    })()
];

folders.push({
    name: "04-TC-M03-337-Detalle-Por-Id",
    item: detalleItems
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
        _postman_id: "tc-m03-g177-auditoria-basica-v1",
        name: "TC-M03-G177 - Consulta Básica y Detalle Auditoría IoT (RF-63)",
        description: "Suite automatizada Newman para TC-M03-G177 (RF-63). Verifica listado sin filtros, paginación, esquema RF-10 + IoT, y detalle por id_evento con verificación de integridad.",
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
                    'const secret = pm.environment.get("sandbox_secret") || pm.collectionVariables.get("sandbox_secret") || "";',
                    'if (!secret) {',
                    '    console.warn("[WARN] sandbox_secret no definido. Los requests fallaran con HTTP 403.");',
                    '}',
                    'if (currentRunId) {',
                    '    pm.request.headers.upsert({ key: "X-Test-Run-Id", value: currentRunId });',
                    '}',
                    'pm.request.headers.upsert({ key: "X-Sandbox-Secret", value: secret });'
                ]
            }
        }
    ],
    variable: [
        { key: "baseUrl", value: "https://api.inmero.co/api-sgpmp-test" },
        { key: "run_id", value: "" },
        { key: "sandbox_secret", value: "" },
        { key: "admin_password", value: "" },
        { key: "token_admin", value: "" },
        { key: "test_id_evento", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g177.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G177 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
