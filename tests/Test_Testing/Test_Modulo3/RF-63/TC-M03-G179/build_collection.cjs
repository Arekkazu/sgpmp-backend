const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G179
// RF-63 (Bitácora de Auditoría IoT) — Clasificación NIC41 vs. TECNICO y Retención Legal
// Regla de negocio:
// - RF-53, RF-56, RF-61, RF-62 -> Clasificación NIC41 (Retención 5 años).
// - Resto (RF-17, RF-23, RF-54, RF-55, RF-57, RF-58, RF-59, RF-60) -> TECNICO (Retención 1 año).
// - Evento ambiguo (sin componente_origen) -> NIC41 por defecto con registro_incompleto=true.
//
// Suite COMPLETA sin acondicionamiento (16 ítems).

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

// ── 03. TC-M03-342: FILTRO POR CLASIFICACION_REGISTRO Y AMBIGÜEDAD E8 ─────────
folders.push({
    name: "03-TC-M03-342-Filtro-Clasificacion",
    item: [
        makeItem(
            "08-TC-M03-342-Filtro-NIC41-Retencion-5",
            "GET",
            "{{baseUrl}}/iot/auditoria?clasificacion_registro=NIC41&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Tipo clasificacion_registro=NIC41 es NIC41 con retencion 5", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos clasificados NIC41 en BD").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("NIC41");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(5);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "09-TC-M03-342-Filtro-TECNICO-Retencion-1",
            "GET",
            "{{baseUrl}}/iot/auditoria?clasificacion_registro=TECNICO&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Tipo clasificacion_registro=TECNICO es TECNICO con retencion 1", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos clasificados TECNICO en BD").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("TECNICO");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(1);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "10-TC-M03-342-Evento-Ambiguo-E8-RESTAURAR",
            "GET",
            "{{baseUrl}}/iot/auditoria?pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("E8 - Evento ambiguo (registro_incompleto=true) => NIC41", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    const ambiguos = (b.items || []).filter(it => it.registro_incompleto === true);',
                '    pm.expect(ambiguos.length, "Sin eventos ambiguos en la muestra de 10. El endpoint no expone query param registro_incompleto. INC: no hay forma publica de verificar E8.").to.be.at.least(1);',
                '    ambiguos.forEach((it, i) => {',
                '        pm.expect(it.clasificacion_registro, `ambiguo[${i}] clasif`).to.eql("NIC41");',
                '        pm.expect(it.retencion_aplicable, `ambiguo[${i}] ret`).to.eql(5);',
                '    });',
                '});'
            ]
        )
    ]
});

// ── 04. TC-M03-344: POSITIVOS NIC41 ───────────────────────────────────────────
folders.push({
    name: "04-TC-M03-344-Positivos-NIC41",
    item: [
        makeItem(
            "11-TC-M03-344-RF62-EVALUACION_CALIDAD_COMPLETADA",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=EVALUACION_CALIDAD_COMPLETADA&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Tipo EVALUACION_CALIDAD_COMPLETADA es NIC41 con retencion 5", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos de EVALUACION_CALIDAD_COMPLETADA en BD").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.tipo_evento, `item[${i}] tipo`).to.eql("EVALUACION_CALIDAD_COMPLETADA");',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("NIC41");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(5);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "12-TC-M03-344-RF62-REEVALUACION_CALIDAD_SOLICITADA",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=REEVALUACION_CALIDAD_SOLICITADA&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Tipo REEVALUACION_CALIDAD_SOLICITADA es NIC41 con retencion 5", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos de REEVALUACION_CALIDAD_SOLICITADA en BD").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.tipo_evento, `item[${i}] tipo`).to.eql("REEVALUACION_CALIDAD_SOLICITADA");',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("NIC41");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(5);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "13-TC-M03-344-RF56-PAQUETE_INFERENCIA_GENERADO-RESTAURAR",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=PAQUETE_INFERENCIA_GENERADO&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("RF-56 PAQUETE_INFERENCIA_GENERADO existe y es NIC41 ret 5", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "0 eventos de PAQUETE_INFERENCIA_GENERADO en BD. Backend no emite este tipo de auditoria.").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.tipo_evento, `item[${i}] tipo`).to.eql("PAQUETE_INFERENCIA_GENERADO");',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("NIC41");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(5);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "14-TC-M03-344-RF61-VINCULACION_AUTOMATICA-CON-ASSERT",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=VINCULACION_AUTOMATICA&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("RF-61 VINCULACION_AUTOMATICA es NIC41 ret 5", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos VINCULACION_AUTOMATICA").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.tipo_evento, `item[${i}] tipo`).to.eql("VINCULACION_AUTOMATICA");',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("NIC41");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(5);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "15-TC-M03-344-RF53-TELEMETRIA_VALIDADA-NUEVO",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=TELEMETRIA_VALIDADA&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Tipo TELEMETRIA_VALIDADA es NIC41 con retencion 5", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos de TELEMETRIA_VALIDADA en BD").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.tipo_evento, `item[${i}] tipo`).to.eql("TELEMETRIA_VALIDADA");',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("NIC41");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(5);',
                '    });',
                '});'
            ]
        )
    ]
});

// ── 05. TC-M03-345: NEGATIVOS TECNICO ─────────────────────────────────────────
folders.push({
    name: "05-TC-M03-345-Negativos-TECNICO",
    item: [
        makeItem(
            "16-TC-M03-345-RF60-TRANSICION_MANTENIMIENTO_MANUAL",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=TRANSICION_MANTENIMIENTO_MANUAL&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Tipo TRANSICION_MANTENIMIENTO_MANUAL es TECNICO con retencion 1", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos de TRANSICION_MANTENIMIENTO_MANUAL en BD").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.tipo_evento, `item[${i}] tipo`).to.eql("TRANSICION_MANTENIMIENTO_MANUAL");',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("TECNICO");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(1);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "17-TC-M03-345-RF54-BUFFER_ACTIVADO-NUEVO",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=BUFFER_ACTIVADO&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Tipo BUFFER_ACTIVADO es TECNICO con retencion 1", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos de BUFFER_ACTIVADO en BD").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.tipo_evento, `item[${i}] tipo`).to.eql("BUFFER_ACTIVADO");',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("TECNICO");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(1);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "18-TC-M03-345-RF55-DESVIACION_DETECTADA-NUEVO",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=DESVIACION_DETECTADA&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Tipo DESVIACION_DETECTADA es TECNICO con retencion 1", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos de DESVIACION_DETECTADA en BD").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.tipo_evento, `item[${i}] tipo`).to.eql("DESVIACION_DETECTADA");',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("TECNICO");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(1);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "19-TC-M03-345-RF57-ALERTA_GENERADA-NUEVO",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=ALERTA_GENERADA&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Tipo ALERTA_GENERADA es TECNICO con retencion 1", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos de ALERTA_GENERADA en BD").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.tipo_evento, `item[${i}] tipo`).to.eql("ALERTA_GENERADA");',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("TECNICO");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(1);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "20-TC-M03-345-RF60-DISPOSITIVO_SIN_SENAL-NUEVO",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=DISPOSITIVO_SIN_SE%C3%91AL&pagina=1&por_pagina=10",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Tipo DISPOSITIVO_SIN_SEÑAL es TECNICO con retencion 1", function () {',
                '    pm.response.to.have.status(200);',
                '    const b = pm.response.json();',
                '    pm.expect(b.total, "Sin eventos de DISPOSITIVO_SIN_SEÑAL en BD").to.be.at.least(1);',
                '    b.items.forEach((it, i) => {',
                '        pm.expect(it.tipo_evento, `item[${i}] tipo`).to.eql("DISPOSITIVO_SIN_SEÑAL");',
                '        pm.expect(it.clasificacion_registro, `item[${i}] clasif`).to.eql("TECNICO");',
                '        pm.expect(it.retencion_aplicable, `item[${i}] ret`).to.eql(1);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "21-TC-M03-345-RF58-RF59-Sonda",
            "GET",
            "{{baseUrl}}/iot/auditoria?pagina=1&por_pagina=1",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[PENDIENTE] RF-58 y RF-59 sin tipo_evento definido en el spec.");'
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
        _postman_id: "tc-m03-g179-clasificacion-nic41-v1",
        name: "TC-M03-G179 - Clasificación NIC41 vs TECNICO Auditoría IoT (RF-63)",
        description: "Suite automatizada Newman para TC-M03-G179 (RF-63). Verifica reglas de negocio de clasificación NIC41 (retención 5 años) vs TECNICO (retención 1 año).",
        schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    event: [
        {
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: [
                    'const secret = pm.environment.get("sandbox_secret")',
                    '            || pm.collectionVariables.get("sandbox_secret")',
                    '            || "";',
                    'if (!secret) {',
                    '    console.warn("[WARN] sandbox_secret no definido. Los requests fallaran con HTTP 403.");',
                    '}',
                    'pm.request.headers.upsert({ key: "X-Sandbox-Secret", value: secret });',
                    '',
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

const targetPath = path.join(__dirname, 'test_tc_m03_g179.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G179 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
