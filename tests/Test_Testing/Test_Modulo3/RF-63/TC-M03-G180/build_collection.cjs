const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G180
// RF-63 (Bitácora de Auditoría IoT) — Exportación en Formatos JSON y CSV
// Subcasos:
// - TC-M03-338: Exportación JSON (Content-Type application/json, Content-Disposition, estructura sin componente_origen,
//               respeto de filtros, SLA 10,000 registros <= 10s [BLOQUEADO por timeout sandbox]).
// - TC-M03-339: Exportación CSV (Content-Type text/csv, cabecera sin componente_origen, parseo de filas,
//               SLA 10,000 registros <= 10s [BLOQUEADO]).
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
                nombre: "Finca QA G180 Exportar",
                ubicacion: "Vereda La Vega QA",
                area_total: 160.0
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
                nombre: "Area 180 Exportacion",
                id_tipo_area: 1,
                capacidad_maxima: 600
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
                numero_serie: "DEV-G180-INIT",
                id_tipo_dispositivo: 1,
                modelo: "ESP32-G180-EXPORT",
                firmware_version: "2.1.0"
            },
            [
                'const infId = parseInt(pm.collectionVariables.get("infra_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_infraestructura = infId;',
                'const serial = "DEV-G180-" + Math.floor(100000 + Math.random() * 900000);',
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
                pin_conexion: "A3",
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

// ── 02. SETUP GENERACIÓN DE EVENTOS PARA EXPORTACIÓN ──────────────────────────
folders.push({
    name: "02-Setup-Generacion-Eventos",
    item: [
        makeItem(
            "05-Generar-Eventos-Batch-Telemetria",
            "POST",
            "{{baseUrl}}/iot/telemetria/batch",
            makeAuthHeaders("token_admin"),
            {
                origen: "BUFFER_LOCAL",
                lecturas: []
            },
            [
                'const sensorId = parseInt(pm.collectionVariables.get("sensor_id"), 10);',
                'const lecturas = [];',
                '// 20 lecturas pasadas (15-oct-2026), espaciadas cada 10 min (600s)',
                'const baseEpoch = 1792051200; // 2026-10-15T08:00:00Z',
                'for (let i = 0; i < 20; i++) {',
                '    const dt = new Date((baseEpoch + (i * 600)) * 1000).toISOString();',
                '    lecturas.push({',
                '        id_sensor: sensorId,',
                '        valor: 24.0 + (i * 0.1),',
                '        timestamp_captura: dt',
                '    });',
                '}',
                'pm.request.body.raw = JSON.stringify({ origen: "BUFFER_LOCAL", lecturas: lecturas });'
            ],
            [
                'pm.test("Status 200/201 - Ingesta batch completada para exportación", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '});'
            ]
        ),
        makeItem(
            "06-Generar-Evento-Mantenimiento-Dispositivo",
            "PATCH",
            "{{baseUrl}}/iot/dispositivos/{{device_id}}/mantenimiento",
            makeAuthHeaders("token_admin"),
            {
                estado_nuevo: "MANTENIMIENTO",
                motivo: "Preparación datos exportación QA G180"
            },
            [],
            [
                'pm.test("Status 200 - Transición a mantenimiento registrada", function () {',
                '    pm.response.to.have.status(200);',
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
                'const data = pm.response.json();',
                'pm.test("Cuerpo es array JSON no truncado con eventos generados", function () {',
                '    pm.expect(data).to.be.an("array");',
                '    pm.expect(data.length).to.be.at.least(1);',
                '});',
                'pm.test("Estructura de cada evento exportado cumple esquema sin componente_origen", function () {',
                '    data.forEach(ev => {',
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
                'console.log("[INFO G180 TC-338] Registros JSON exportados: " + data.length + " | Tiempo respuesta: " + pm.response.responseTime + " ms");'
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
                'const data = pm.response.json();',
                'pm.test("Todos los eventos exportados respetan el filtro clasificacion_registro=NIC41", function () {',
                '    pm.expect(data.length).to.be.at.least(1);',
                '    data.forEach(ev => {',
                '        pm.expect(ev.clasificacion_registro).to.eql("NIC41");',
                '        pm.expect(ev.retencion_aplicable).to.eql(5);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "09-TC-M03-338-SLA-10000-Registros-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=json",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso CA-10: Validación de exportación de 10,000 eventos en <= 10 s.");',
                'console.log("  Motivo: En el sandbox de pruebas (timeout total 180 s), generar 10,000 registros por API consumiría > 300 s.");',
                'console.log("  Medición observada con volumen actual (" + pm.response.json().length + " eventos): " + pm.response.responseTime + " ms.");',
                'console.log("  No demuestra el SLA de escala de 10,000 registros; se registra como limitación de prueba sandbox.");'
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
                '    // Cada fila tiene contenido no vacío',
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
            "12-TC-M03-339-SLA-10000-Registros-CSV-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria/exportar?formato=csv",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso CA-10 CSV: Medición de 10,000 registros en <= 10 s bloqueada por timeout sandbox.");',
                'console.log("  No se valida con pandas/excel en el runner, se valida estructura CSV y parseo de líneas en Newman.");'
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
        { key: "token_admin", value: "" },
        { key: "finca_id", value: "" },
        { key: "infra_id", value: "" },
        { key: "device_id", value: "" },
        { key: "device_serial", value: "" },
        { key: "sensor_id", value: "" }
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
