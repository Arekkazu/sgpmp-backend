const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G180
// RF-63 (Bitácora de Auditoría IoT) — Exportación en Formatos JSON y CSV
// Subcasos:
// - TC-M03-338: Exportación JSON (Content-Type application/json, Content-Disposition, estructura sin componente_origen,
//               respeto de filtros, SLA 10,000 registros <= 10s).
// - TC-M03-339: Exportación CSV (Content-Type text/csv, cabecera sin componente_origen, parseo de filas,
//               SLA 10,000 registros <= 10s).
// - Verificación de aislamiento Sandbox (X-Test-Run-Id) en streaming.

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

// ── 03. TC-M03-338: EXPORTACIÓN JSON ──────────────────────────────────────────
folders.push({
    name: "03-TC-M03-338-Exportacion-JSON",
    item: [
        makeItem(
            "07-TC-M03-338-Exportar-JSON-Sin-Filtros",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Exportación JSON exitosa", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'pm.test("Cabeceras Content-Type y Content-Disposition correctas para JSON", function () {',
                '    const ct = pm.response.headers.get("Content-Type");',
                '    pm.expect(ct).to.include("application/json");',
                '    const cd = pm.response.headers.get("Content-Disposition");',
                '    pm.expect(cd).to.include("attachment; filename=\\"auditoria_iot.json\\"");',
                '});',
                'const bodyData = pm.response.json();',
                'pm.test("Cuerpo es array JSON no truncado con eventos generados", function () {',
                '    pm.expect(bodyData).to.be.an("array");',
                '    pm.expect(bodyData.length).to.be.at.least(1);',
                '});',
                'pm.test("Estructura de cada evento exportado cumple esquema sin componente_origen", function () {',
                '    bodyData.forEach(ev => {',
                '        pm.expect(ev).to.have.property("id_evento");',
                '        pm.expect(ev).to.have.property("tipo_evento");',
                '        pm.expect(ev).to.have.property("fecha_hora");',
                '        pm.expect(ev).to.have.property("modulo");',
                '        pm.expect(ev.modulo).to.eql("M03");',
                '        pm.expect(ev).to.have.property("hash_integridad");',
                '        pm.expect(ev.hash_integridad).to.match(/^[0-9a-f]{64}$/);',
                '        pm.expect(ev).to.not.have.property("componente_origen");',
                '    });',
                '});',
                'console.log("[INFO G180 TC-338] Registros JSON exportados: " + bodyData.length + " | Tiempo respuesta: " + pm.response.responseTime + " ms");'
            ]
        ),
        makeItem(
            "08-TC-M03-338-Exportar-JSON-Con-Filtro-Clasificacion",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json&clasificacion_registro=NIC41",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Exportación JSON filtrada por NIC41 exitosa", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const bodyData = pm.response.json();',
                'pm.test("Todos los eventos exportados respetan el filtro clasificacion_registro=NIC41", function () {',
                '    pm.expect(bodyData.length).to.be.at.least(1);',
                '    bodyData.forEach(ev => {',
                '        pm.expect(ev.clasificacion_registro).to.eql("NIC41");',
                '        pm.expect(ev.retencion_aplicable).to.eql(5);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "09-TC-M03-338-SLA-10000-Registros",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json&fecha_desde={{sla_desde}}&fecha_hasta={{sla_hasta}}",
            makeAuthHeaders("token_admin"),
            null,
            [
                'const hasta = new Date();',
                'const desde = new Date(hasta.getTime() - 2 * 60 * 60 * 1000); // 2h',
                'const fmt = d => d.toISOString().split(".")[0] + "Z";',
                'pm.collectionVariables.set("sla_desde", fmt(desde));',
                'pm.collectionVariables.set("sla_hasta", fmt(hasta));',
                'console.log("[SLA] rango 2h: " + fmt(desde) + " -> " + fmt(hasta));'
            ],
            [
                'pm.test("09 - SLA JSON: 200, application/json, <=10000ms", function() {',
                '    pm.response.to.have.status(200);',
                '    pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json");',
                '    const tiempo = pm.response.responseTime;',
                '    console.log("[SLA] JSON 2h exportado en " + tiempo + "ms");',
                '    pm.expect(tiempo, "SLA excedido: " + tiempo + "ms > 10000ms").to.be.below(10001);',
                '});',
                'pm.test("09 - SLA JSON: respuesta con eventos", function() {',
                '    const b = pm.response.json();',
                '    pm.expect(Array.isArray(b)).to.be.true;',
                '    pm.expect(b.length).to.be.at.least(10000, "El rango no tiene >=10000 eventos: solo " + b.length);',
                '});'
            ]
        )
    ]
});

// ── 04. TC-M03-339: EXPORTACIÓN CSV ───────────────────────────────────────────
folders.push({
    name: "04-TC-M03-339-Exportacion-CSV",
    item: [
        makeItem(
            "10-TC-M03-339-Exportar-CSV-Sin-Filtros",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=csv",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Exportación CSV exitosa", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'pm.test("Cabeceras Content-Type y Content-Disposition correctas para CSV", function () {',
                '    const ct = pm.response.headers.get("Content-Type");',
                '    pm.expect(ct).to.include("text/csv");',
                '    const cd = pm.response.headers.get("Content-Disposition");',
                '    pm.expect(cd).to.include("attachment; filename=\\"auditoria_iot.csv\\"");',
                '});',
                'const csvText = pm.response.text();',
                'const lines = csvText.split(/\\r?\\n/).filter(line => line.trim().length > 0);',
                'pm.test("CSV contiene al menos cabecera y una fila de datos", function () {',
                '    pm.expect(lines.length).to.be.at.least(2);',
                '});',
                'const headerLine = lines[0];',
                'pm.test("Cabecera CSV contiene nombres de columnas del esquema", function () {',
                '    pm.expect(headerLine).to.include("id_evento");',
                '    pm.expect(headerLine).to.include("tipo_evento");',
                '    pm.expect(headerLine).to.include("modulo");',
                '    pm.expect(headerLine).to.include("hash_integridad");',
                '    pm.expect(headerLine).to.include("clasificacion_registro");',
                '});',
                'pm.test("Invariante de seguridad: componente_origen NO aparece en la cabecera CSV", function () {',
                '    pm.expect(headerLine).to.not.include("componente_origen");',
                '});',
                'pm.test("Validación de parseo de filas CSV (filas de datos = total líneas - 1)", function () {',
                '    const dataRows = lines.slice(1);',
                '    pm.expect(dataRows.length).to.be.at.least(1);',
                '    dataRows.forEach((row, i) => {',
                '        pm.expect(row).to.be.a("string").that.is.not.empty;',
                '    });',
                '});',
                'console.log("[INFO G180 TC-339] Líneas CSV totales: " + lines.length + " (Cabecera + " + (lines.length - 1) + " registros). Tiempo respuesta: " + pm.response.responseTime + " ms");'
            ]
        ),
        makeItem(
            "11-TC-M03-339-Exportar-CSV-Con-Filtro-Clasificacion",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=csv&clasificacion_registro=TECNICO",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Exportación CSV filtrada por TECNICO exitosa", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const csvText = pm.response.text();',
                'const lines = csvText.split(/\\r?\\n/).filter(line => line.trim().length > 0);',
                'pm.test("CSV filtrado por TECNICO tiene filas y respeta cabecera", function () {',
                '    pm.expect(lines.length).to.be.at.least(2);',
                '    pm.expect(lines[0]).to.include("clasificacion_registro");',
                '});'
            ]
        ),
        makeItem(
            "12-TC-M03-339-SLA-10000-Registros-CSV",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=csv&fecha_desde={{sla_desde}}&fecha_hasta={{sla_hasta}}",
            makeAuthHeaders("token_admin"),
            null,
            [
                'const hasta = new Date();',
                'const desde = new Date(hasta.getTime() - 2 * 60 * 60 * 1000); // 2h',
                'const fmt = d => d.toISOString().split(".")[0] + "Z";',
                'pm.collectionVariables.set("sla_desde", fmt(desde));',
                'pm.collectionVariables.set("sla_hasta", fmt(hasta));',
                'console.log("[SLA] rango 2h: " + fmt(desde) + " -> " + fmt(hasta));'
            ],
            [
                'pm.test("12 - SLA CSV: 200, text/csv, <=10000ms", function() {',
                '    pm.response.to.have.status(200);',
                '    pm.expect(pm.response.headers.get("Content-Type")).to.include("text/csv");',
                '    const tiempo = pm.response.responseTime;',
                '    console.log("[SLA] CSV 2h exportado en " + tiempo + "ms");',
                '    pm.expect(tiempo, "SLA excedido: " + tiempo + "ms > 10000ms").to.be.below(10001);',
                '});',
                'pm.test("12 - SLA CSV: al menos 10001 lineas (header + 10000 eventos)", function() {',
                '    const lineas = pm.response.text().split("\\n").filter(l => l.trim().length > 0);',
                '    pm.expect(lineas.length).to.be.at.least(10001, "El CSV tiene " + lineas.length + " lineas, se esperaban >=10001");',
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
        _postman_id: "tc-m03-g180-exportacion-auditoria-v1",
        name: "TC-M03-G180 - Exportación JSON y CSV Auditoría IoT (RF-63)",
        description: "Suite automatizada Newman para TC-M03-G180 (RF-63). Verifica endpoints de exportación en streaming para formatos JSON y CSV, cabeceras Content-Type/Disposition y ausencia de componente_origen.",
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
        { key: "test_id_evento", value: "" },
        { key: "sla_desde", value: "" },
        { key: "sla_hasta", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g180.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G180 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
