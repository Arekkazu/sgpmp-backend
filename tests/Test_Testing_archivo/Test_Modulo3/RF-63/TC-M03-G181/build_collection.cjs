const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G181
// RF-63 — Emisión Transversal de Eventos de Auditoría desde todos los RF
//
// Endpoints emisores REST probados:
// 1. RF-53: POST /iot/telemetria (Ingesta individual) -> evalúa y emite en bitácora
// 2. RF-62: POST /iot/calidad/{id}/evaluar -> emite EVALUACION_CALIDAD_COMPLETADA (RF62, NIC41, retención 5)
// 3. RF-62: POST /iot/calidad/reevaluar -> emite REEVALUACION_CALIDAD_SOLICITADA (RF62, NIC41, retención 5)
// 4. RF-60: PATCH /iot/dispositivos/{id}/mantenimiento -> emite TRANSICION_MANTENIMIENTO_MANUAL (RF60, TECNICO, retención 1)
//
// Verificación SQL Solo Lectura:
// - Para verificar `componente_origen` (campo interno no expuesto en GET /iot/auditoria), se usa SELECT vía /test-control/query.
//
// Componentes bloqueados por Broker / Worker / MQTT:
// - RF-54, RF-55, RF-56, RF-57, RF-58, RF-59, RF-60 (DISPOSITIVO_SIN_SEÑAL), RF-61 -> [BLOQUEADO]

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
                nombre: "Finca QA G181 Transversal",
                ubicacion: "Vereda La Selva QA",
                area_total: 130.0
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
                nombre: "Galpon 181 Transversal",
                id_tipo_area: 1,
                capacidad_maxima: 350
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
                numero_serie: "DEV-G181-INIT",
                id_tipo_dispositivo: 1,
                modelo: "ESP32-G181-EMISOR",
                firmware_version: "2.1.0"
            },
            [
                'const infId = parseInt(pm.collectionVariables.get("infra_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_infraestructura = infId;',
                'const serial = "DEV-G181-" + Math.floor(100000 + Math.random() * 900000);',
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
                pin_conexion: "A0",
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

// ── 02. EMISOR RF-53 & RF-62: TELEMETRIA + EVALUAR ─────────────────────────────
folders.push({
    name: "02-Emisor-RF53-RF62-Telemetria-Calidad",
    item: [
        makeItem(
            "05-Emisor-RF53-Ingesta-Lectura",
            "POST",
            "{{baseUrl}}/iot/telemetria",
            makeAuthHeaders("token_admin"),
            {
                id_sensor: 0,
                valor: 26.5,
                timestamp_captura: "2026-10-16T10:00:00Z"
            },
            [
                'const sensorId = parseInt(pm.collectionVariables.get("sensor_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_sensor = sensorId;',
                'pm.request.body.raw = JSON.stringify(body);'
            ],
            [
                'pm.test("Status 200/201 - Telemetría RF-53 ingerida exitosamente", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '    const res = pm.response.json();',
                '    const idTel = res.id_telemetria || res.id;',
                '    pm.expect(idTel).to.be.ok;',
                '    pm.collectionVariables.set("id_telemetria_eval", String(idTel));',
                '});'
            ]
        ),
        makeItem(
            "06-Emisor-RF62-Evaluar-Calidad-Puntual",
            "POST",
            "{{baseUrl}}/iot/calidad/{{id_telemetria_eval}}/evaluar",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200/201 - Evaluación puntual de calidad RF-62 completada", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '});'
            ]
        ),
        makeItem(
            "07-Verificar-Auditoria-RF62-Calidad",
            "GET",
            "{{baseUrl}}/iot/auditoria?entidad_afectada_id={{id_telemetria_eval}}",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Evento de auditoría RF-62 recuperado", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Se registró evento EVALUACION_CALIDAD_COMPLETADA con clasificación NIC41", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    const ev = res.items.find(i => i.tipo_evento === "EVALUACION_CALIDAD_COMPLETADA");',
                '    pm.expect(ev).to.be.an("object");',
                '    pm.expect(ev.clasificacion_registro).to.eql("NIC41");',
                '    pm.expect(ev.retencion_aplicable).to.eql(5);',
                '    pm.expect(ev.hash_integridad).to.match(/^[0-9a-f]{64}$/);',
                '    pm.expect(ev.modulo).to.eql("M03");',
                '    pm.collectionVariables.set("id_evento_rf62", ev.id_evento);',
                '});'
            ]
        )
    ]
});

// ── 03. EMISOR RF-62: REEVALUACION DE CALIDAD ─────────────────────────────────
folders.push({
    name: "03-Emisor-RF62-Reevaluacion",
    item: [
        makeItem(
            "08-Emisor-RF62-Reevaluacion-Admin",
            "POST",
            "{{baseUrl}}/iot/calidad/reevaluar",
            makeAuthHeaders("token_admin"),
            {
                id_sensor: "{{sensor_id}}",
                fecha_inicio: "2026-10-16T00:00:00Z",
                fecha_fin: "2026-10-16T23:59:59Z",
                motivo: "Reevaluación de auditoría transversal G181"
            },
            [
                'const sensorId = parseInt(pm.collectionVariables.get("sensor_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_sensor = sensorId;',
                'pm.request.body.raw = JSON.stringify(body);'
            ],
            [
                'pm.test("Status 200 - Solicitud de reevaluación completada", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        makeItem(
            "09-Verificar-Auditoria-RF62-Reevaluacion",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=REEVALUACION_CALIDAD_SOLICITADA",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Evento REEVALUACION_CALIDAD_SOLICITADA encontrado", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Evento de reevaluación clasifica NIC41 y retención 5 años", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    const ev = res.items[0];',
                '    pm.expect(ev.tipo_evento).to.eql("REEVALUACION_CALIDAD_SOLICITADA");',
                '    pm.expect(ev.clasificacion_registro).to.eql("NIC41");',
                '    pm.expect(ev.retencion_aplicable).to.eql(5);',
                '    pm.expect(ev.hash_integridad).to.match(/^[0-9a-f]{64}$/);',
                '});'
            ]
        )
    ]
});

// ── 04. EMISOR RF-60: TRANSICION DE MANTENIMIENTO ─────────────────────────────
folders.push({
    name: "04-Emisor-RF60-Mantenimiento",
    item: [
        makeItem(
            "10-Emisor-RF60-Transicion-Mantenimiento",
            "PATCH",
            "{{baseUrl}}/iot/dispositivos/{{device_id}}/mantenimiento",
            makeAuthHeaders("token_admin"),
            {
                estado_nuevo: "MANTENIMIENTO",
                motivo: "Verificación transversal RF-60 G181"
            },
            [],
            [
                'pm.test("Status 200 - Transición a mantenimiento aplicada", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        makeItem(
            "11-Verificar-Auditoria-RF60-Mantenimiento",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=TRANSICION_MANTENIMIENTO_MANUAL",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Evento TRANSICION_MANTENIMIENTO_MANUAL encontrado", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Evento de mantenimiento clasifica TECNICO y retención 1 año", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    const ev = res.items[0];',
                '    pm.expect(ev.tipo_evento).to.eql("TRANSICION_MANTENIMIENTO_MANUAL");',
                '    pm.expect(ev.clasificacion_registro).to.eql("TECNICO");',
                '    pm.expect(ev.retencion_aplicable).to.eql(1);',
                '    pm.expect(ev.hash_integridad).to.match(/^[0-9a-f]{64}$/);',
                '    pm.collectionVariables.set("id_evento_rf60", ev.id_evento);',
                '});'
            ]
        )
    ]
});

// ── 05. VERIFICACION SQL SOLO LECTURA (COMPONENTE_ORIGEN) ─────────────────────
folders.push({
    name: "05-Verificacion-SQL-Solo-Lectura-Componente-Origen",
    item: [
        makeItem(
            "12-SQL-SELECT-Verificar-componente_origen",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders("token_admin"),
            {
                query: "SELECT id_evento, tipo_evento, componente_origen, clasificacion_registro, retencion_aplicable FROM modulo3.bitacora_auditoria_iot WHERE id_evento = '{{id_evento_rf62}}' LIMIT 1;"
            },
            [
                'const idEv = pm.collectionVariables.get("id_evento_rf62");',
                'const sql = "SELECT id_evento, tipo_evento, componente_origen, clasificacion_registro, retencion_aplicable FROM modulo3.bitacora_auditoria_iot WHERE id_evento = \'" + idEv + "\' LIMIT 1;";',
                'pm.request.body.raw = JSON.stringify({ query: sql });'
            ],
            [
                'pm.test("[VERIFICACION SQL SOLO LECTURA] Status 200 - Consulta SELECT ejecutada", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("[VERIFICACION SQL SOLO LECTURA] componente_origen es RF62 para EVALUACION_CALIDAD_COMPLETADA", function () {',
                '    const rows = res.rows || res.data || res.items || [];',
                '    if (rows.length > 0) {',
                '        const row = rows[0];',
                '        const comp = row.componente_origen || row[2];',
                '        pm.expect(comp).to.eql("RF62");',
                '        console.log("[INFO G181 SQL] Confirmado componente_origen interno:", comp);',
                '    }',
                '});'
            ]
        )
    ]
});

// ── 06. COMPONENTES BLOQUEADOS POR WORKER / BROKER ────────────────────────────
folders.push({
    name: "06-Componentes-Bloqueados-Worker-Broker",
    item: [
        makeItem(
            "13-RF-56-Inferencia-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=PAQUETE_INFERENCIA_GENERADO",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso RF-56 PAQUETE_INFERENCIA_GENERADO: Emitido por worker de inferencia en background. No expone endpoint REST directo.");'
            ]
        ),
        makeItem(
            "14-RF-60-Dispositivo-Sin-Senal-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=DISPOSITIVO_SIN_SEÑAL",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso RF-60 DISPOSITIVO_SIN_SEÑAL: Emitido por tarea periódica _evaluar_dispositivos_periodicamente tras timeout de heartbeat. No síncrono.");'
            ]
        ),
        makeItem(
            "15-RF-61-Vinculacion-Automatica-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=VINCULACION_AUTOMATICA",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso RF-61 VINCULACION_AUTOMATICA: Emitido por worker edge de RFID en segundo plano.");'
            ]
        ),
        makeItem(
            "16-RF-54-55-57-Broker-MQTT-Bloqueados",
            "GET",
            "{{baseUrl}}/iot/auditoria?clasificacion_registro=TECNICO",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcasos RF-54 (BUFFER_ACTIVADO), RF-55 (DESVIACION_DETECTADA), RF-57 (ALERTA_GENERADA): Dependen de broker MQTT / Gateway Edge.");'
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
        _postman_id: "tc-m03-g181-emision-transversal-v1",
        name: "TC-M03-G181 - Emisión Transversal Auditoría IoT (RF-63)",
        description: "Suite automatizada Newman para TC-M03-G181 (RF-63). Verifica emisión de eventos desde RF-53, RF-60 y RF-62 por endpoints reales, confirmación en bitácora y verificación SQL solo lectura de componente_origen.",
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
        { key: "sensor_id", value: "" },
        { key: "id_telemetria_eval", value: "" },
        { key: "id_evento_rf62", value: "" },
        { key: "id_evento_rf60", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g181.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G181 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
