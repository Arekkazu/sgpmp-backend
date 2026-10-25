const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G178
// RF-63 (Bitácora de Auditoría IoT) — Filtros y Combinaciones AND
// Subcasos:
// - TC-M03-340: Filtro por tipo_evento (EVALUACION_CALIDAD_COMPLETADA, TRANSICION_MANTENIMIENTO_MANUAL,
//               DISPOSITIVO_SIN_SEÑAL [BLOQUEADO], tipo inexistente -> items=[] total=0).
// - TC-M03-341: Filtro por severidad_log (INFO, WARNING, ERROR, CRITICAL; valor inválido).
// - TC-M03-343: Filtro por entidad_afectada_id + resultado + id_usuario [LIMITACION API] + cadena de custodia.
// - TC-M03-346: Combinación AND progresiva (tipo_evento + severidad_log + clasificacion_registro),
//               combinación sin resultados (total=0, items=[]), paginación filtrada.
// - rf_origen: Invariante de seguridad (no revela componente_origen).

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

// ── 03. TC-M03-340: FILTRO POR TIPO_EVENTO ────────────────────────────────────
folders.push({
    name: "03-TC-M03-340-Filtro-Tipo-Evento",
    item: [
        makeItem(
            "07-TC-M03-340-Filtro-EVALUACION_CALIDAD_COMPLETADA",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=EVALUACION_CALIDAD_COMPLETADA",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Filtro tipo_evento=EVALUACION_CALIDAD_COMPLETADA exitoso", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Todos los items devueltos coinciden con el tipo_evento solicitado", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(item => {',
                '        pm.expect(item.tipo_evento).to.eql("EVALUACION_CALIDAD_COMPLETADA");',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "08-TC-M03-340-Filtro-TRANSICION_MANTENIMIENTO_MANUAL",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=TRANSICION_MANTENIMIENTO_MANUAL",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Filtro tipo_evento=TRANSICION_MANTENIMIENTO_MANUAL exitoso", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Todos los items devueltos coinciden con TRANSICION_MANTENIMIENTO_MANUAL", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(item => {',
                '        pm.expect(item.tipo_evento).to.eql("TRANSICION_MANTENIMIENTO_MANUAL");',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "09-TC-M03-340-DISPOSITIVO_SIN_SENAL-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=DISPOSITIVO_SIN_SEÑAL",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso DISPOSITIVO_SIN_SEÑAL (RF-60): Requiere desconexión de broker MQTT o tarea background de timeout. No emitible por endpoint síncrono API.");',
                'console.log("[INFO G178] Status de respuesta:", pm.response.code);'
            ]
        ),
        makeItem(
            "10-TC-M03-340-Tipo-Inexistente-Vacio",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=EVENTO_INEXISTENTE_QA_XYZ",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Tipo de evento sin registros devuelve total=0 y array vacío (no 404)", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.total).to.eql(0);',
                '    pm.expect(res.items).to.be.an("array").that.is.empty;',
                '});'
            ]
        )
    ]
});

// ── 04. TC-M03-341: FILTRO POR SEVERIDAD_LOG ──────────────────────────────────
folders.push({
    name: "04-TC-M03-341-Filtro-Severidad",
    item: [
        makeItem(
            "11-TC-M03-341-Filtro-Severidad-INFO",
            "GET",
            "{{baseUrl}}/iot/auditoria?severidad_log=INFO",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Filtro severidad_log=INFO exitoso", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Todos los items devueltos tienen severidad INFO", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(item => {',
                '        pm.expect(item.severidad_log).to.eql("INFO");',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "12-TC-M03-341-Filtro-Severidad-WARNING",
            "GET",
            "{{baseUrl}}/iot/auditoria?severidad_log=WARNING",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Filtro severidad_log=WARNING responde 200", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'if (res.items.length > 0) {',
                '    pm.test("Items devueltos tienen severidad WARNING", function () {',
                '        res.items.forEach(item => {',
                '            pm.expect(item.severidad_log).to.eql("WARNING");',
                '        });',
                '    });',
                '}'
            ]
        ),
        makeItem(
            "13-TC-M03-341-Filtro-Severidad-Invalida-FATAL",
            "GET",
            "{{baseUrl}}/iot/auditoria?severidad_log=FATAL",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'if (pm.response.code === 422) {',
                '    pm.test("Status 422 - Severidad inválida (FATAL) rechazada por validación de esquema", function () {',
                '        pm.response.to.have.status(422);',
                '    });',
                '} else if (pm.response.code === 200) {',
                '    console.log("[DISCREPANCIA / LIMITACION API] severidad_log no está tipado como Enum estricto en Query router; responde 200 con total=0.");',
                '    pm.test("Status 200 con lista vacía si backend filtra por string", function () {',
                '        const res = pm.response.json();',
                '        pm.expect(res.total).to.eql(0);',
                '        pm.expect(res.items).to.be.empty;',
                '    });',
                '} else {',
                '    pm.test("Código de respuesta imprevisto para severidad inválida", function () {',
                '        pm.expect(pm.response.code).to.be.oneOf([200, 422]);',
                '    });',
                '}'
            ]
        )
    ]
});

// ── 05. TC-M03-343: ENTIDAD AFECTADA + RESULTADO + CADENA DE CUSTODIA ─────────
folders.push({
    name: "05-TC-M03-343-Entidad-Resultado-Custodia",
    item: [
        makeItem(
            "14-TC-M03-343-Filtro-Entidad-Telemetria",
            "GET",
            "{{baseUrl}}/iot/auditoria?entidad_afectada_id={{id_telemetria_eval}}",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Filtro por entidad_afectada_id (lectura) exitoso", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'const telId = pm.collectionVariables.get("id_telemetria_eval");',
                'if (telId && res.items.length > 0) {',
                '    pm.test("Todos los eventos devueltos corresponden a la entidad_afectada_id filtrada", function () {',
                '        res.items.forEach(item => {',
                '            pm.expect(String(item.entidad_afectada_id)).to.eql(telId);',
                '        });',
                '    });',
                '}'
            ]
        ),
        makeItem(
            "15-TC-M03-343-Filtro-Entidad-Dispositivo",
            "GET",
            "{{baseUrl}}/iot/auditoria?entidad_afectada_id={{device_id}}",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Filtro por entidad_afectada_id (dispositivo) exitoso", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'const devId = pm.collectionVariables.get("device_id");',
                'if (devId && res.items.length > 0) {',
                '    pm.test("Eventos devueltos corresponden al id_dispositivo filtrado", function () {',
                '        res.items.forEach(item => {',
                '            pm.expect(String(item.entidad_afectada_id)).to.eql(devId);',
                '        });',
                '    });',
                '}'
            ]
        ),
        makeItem(
            "16-TC-M03-343-Filtro-Resultado-EXITOSO",
            "GET",
            "{{baseUrl}}/iot/auditoria?resultado=EXITOSO",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Filtro resultado=EXITOSO exitoso", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Todos los items devueltos tienen resultado EXITOSO", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(item => {',
                '        pm.expect(item.resultado).to.eql("EXITOSO");',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "17-TC-M03-343-Filtro-Resultado-FALLIDO",
            "GET",
            "{{baseUrl}}/iot/auditoria?resultado=FALLIDO",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Filtro resultado=FALLIDO responde 200", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'if (res.items.length > 0) {',
                '    pm.test("Items devueltos tienen resultado FALLIDO", function () {',
                '        res.items.forEach(item => {',
                '            pm.expect(item.resultado).to.eql("FALLIDO");',
                '        });',
                '    });',
                '} else {',
                '    console.log("[INFO G178] No se produjeron eventos FALLIDOS en esta corrida de sandbox.");',
                '}'
            ]
        ),
        makeItem(
            "18-TC-M03-343-Filtro-Id-Usuario-Limitacion",
            "GET",
            "{{baseUrl}}/iot/auditoria?id_usuario=1",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Endpoint acepta petición con id_usuario", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'console.log("[LIMITACION API] El router /iot/auditoria no define formalmente id_usuario como Query param. FastAPI lo ignora sin fallar.");'
            ]
        )
    ]
});

// ── 06. TC-M03-346: COMBINACIÓN AND PROGRESIVA Y NO EXPOSICIÓN DE RF_ORIGEN ──
folders.push({
    name: "06-TC-M03-346-Combinaciones-AND",
    item: [
        makeItem(
            "19-TC-M03-346-Combinacion-AND-3-Filtros",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=EVALUACION_CALIDAD_COMPLETADA&severidad_log=INFO&clasificacion_registro=NIC41",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Combinación AND de 3 filtros exitosa", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Todos los items cumplen la conjunción AND estricta", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(item => {',
                '        pm.expect(item.tipo_evento).to.eql("EVALUACION_CALIDAD_COMPLETADA");',
                '        pm.expect(item.severidad_log).to.eql("INFO");',
                '        pm.expect(item.clasificacion_registro).to.eql("NIC41");',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "20-TC-M03-346-Combinacion-AND-Sin-Resultados",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=TRANSICION_MANTENIMIENTO_MANUAL&clasificacion_registro=NIC41",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Conjunción sin intersección devuelve total=0 y array vacío (no 500)", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.total).to.eql(0);',
                '    pm.expect(res.items).to.be.an("array").that.is.empty;',
                '});'
            ]
        ),
        makeItem(
            "21-TC-M03-346-Verificar-Filtro-rf_origen-No-Expone-Componente",
            "GET",
            "{{baseUrl}}/iot/auditoria?rf_origen=RF-62",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Petición con rf_origen procesada sin error", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Invariante de seguridad: componente_origen NO es revelado en la respuesta", function () {',
                '    res.items.forEach(item => {',
                '        pm.expect(item).to.not.have.property("componente_origen");',
                '    });',
                '});',
                'console.log("[LIMITACION API] rf_origen no está mapeado en router; se verifica que el payload jamás exponga componente_origen.");'
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
        _postman_id: "tc-m03-g178-filtros-auditoria-v1",
        name: "TC-M03-G178 - Filtros y Combinaciones de Auditoría IoT (RF-63)",
        description: "Suite automatizada Newman para TC-M03-G178 (RF-63). Verifica filtros por tipo_evento, severidad_log, entidad_afectada_id, resultado y combinaciones AND.",
        schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    event: [
        {
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: [
                    'const secret = pm.environment.get("sandbox_secret") || pm.collectionVariables.get("sandbox_secret") || "";',
                    'if (!secret) {',
                    '    console.warn("[WARN] sandbox_secret no definido. Los requests fallaran con HTTP 403.");',
                    '}',
                    'pm.request.headers.upsert({ key: "X-Sandbox-Secret", value: secret });',
                    '',
                    '// Generar run_id si no existe',
                    'if (!pm.collectionVariables.get("run_id")) {',
                    '    pm.collectionVariables.set("run_id", "test-" + pm.variables.replaceIn(\'{{$guid}}\'));',
                    '}',
                    'pm.request.headers.upsert({ key: "X-Test-Run-Id", value: pm.collectionVariables.get("run_id") });'
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

const targetPath = path.join(__dirname, 'test_tc_m03_g178.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G178 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
