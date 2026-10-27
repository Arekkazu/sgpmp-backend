// | Fecha      | Nombre     | Que se hizo                                                                           |
// |------------|------------|---------------------------------------------------------------------------------------|
// | 2026-10-26 | HulkyZeus  | TC-M03-G179 RF-63: aviso, la coleccion paso a solo lectura y este generador quedo atras |
// AVISO: la coleccion vigente (test_tc_m03_g179.json) se actualizo a mano (sin pasos de escritura). Regenerarla con este
// script restauraria la preparacion anterior, que ya no funciona; ver DISENO_Y_PRECONDICIONES.md.
const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G179
// RF-63 (Bitácora de Auditoría IoT) — Clasificación NIC41 vs. TECNICO y Retención Legal
// Regla de negocio:
// - RF-53, RF-56, RF-61, RF-62 -> Clasificación NIC41 (Retención 5 años).
// - Resto (RF-17, RF-23, RF-54, RF-55, RF-57, RF-58, RF-59, RF-60) -> TECNICO (Retención 1 año).
// - Evento ambiguo (sin componente_origen) -> NIC41 por defecto con registro_incompleto=true.
//
// Subcasos:
// - TC-M03-342: Filtro por clasificacion_registro=NIC41 y TECNICO; inyección ambigua [BLOQUEADO].
// - TC-M03-344: Positivo NIC41 (RF-62 EVALUACION_CALIDAD_COMPLETADA, REEVALUACION_CALIDAD_SOLICITADA; RF-56/RF-61 [BLOQUEADO]).
// - TC-M03-345: Negativo TECNICO (RF-60 TRANSICION_MANTENIMIENTO_MANUAL; RF-54/55/57/58/59 [BLOQUEADO]).

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
                nombre: "Finca QA G179 Clasificacion",
                ubicacion: "Vereda El Porvenir QA",
                area_total: 140.0
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
                nombre: "Pabellon 179 NIC41",
                id_tipo_area: 1,
                capacidad_maxima: 400
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
                numero_serie: "DEV-G179-INIT",
                id_tipo_dispositivo: 1,
                modelo: "ESP32-G179-NIC41",
                firmware_version: "2.1.0"
            },
            [
                'const infId = parseInt(pm.collectionVariables.get("infra_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_infraestructura = infId;',
                'const serial = "DEV-G179-" + Math.floor(100000 + Math.random() * 900000);',
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
                pin_conexion: "A2",
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

// ── 02. SETUP GENERACIÓN DE EVENTOS NIC41 Y TECNICOS ──────────────────────────
folders.push({
    name: "02-Setup-Generacion-Eventos",
    item: [
        makeItem(
            "05-Generar-Eventos-NIC41-Batch-Telemetria",
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
                '// 20 lecturas pasadas (14-oct-2026), espaciadas cada 10 min (600s)',
                'const baseEpoch = 1791964800; // 2026-10-14T08:00:00Z',
                'for (let i = 0; i < 20; i++) {',
                '    const dt = new Date((baseEpoch + (i * 600)) * 1000).toISOString();',
                '    lecturas.push({',
                '        id_sensor: sensorId,',
                '        valor: 24.8 + (i * 0.1),',
                '        timestamp_captura: dt',
                '    });',
                '}',
                'pm.request.body.raw = JSON.stringify({ origen: "BUFFER_LOCAL", lecturas: lecturas });'
            ],
            [
                'pm.test("Status 200/201 - Batch telemetría ingerido (Genera EVALUACION_CALIDAD_COMPLETADA)", function () {',
                '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
                '});'
            ]
        ),
        makeItem(
            "06-Generar-Eventos-NIC41-Reevaluacion",
            "POST",
            "{{baseUrl}}/iot/calidad/reevaluar",
            makeAuthHeaders("token_admin"),
            {
                id_sensor: "{{sensor_id}}",
                fecha_inicio: "2026-10-14T00:00:00Z",
                fecha_fin: "2026-10-14T23:59:59Z",
                motivo: "Re-evaluación clasificación NIC41 QA G179"
            },
            [
                'const sensorId = parseInt(pm.collectionVariables.get("sensor_id"), 10);',
                'const body = JSON.parse(pm.request.body.raw);',
                'body.id_sensor = sensorId;',
                'pm.request.body.raw = JSON.stringify(body);'
            ],
            [
                'pm.test("Status 200 - Reevaluación solicitada (Genera REEVALUACION_CALIDAD_SOLICITADA)", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        ),
        makeItem(
            "07-Generar-Evento-TECNICO-Mantenimiento",
            "PATCH",
            "{{baseUrl}}/iot/dispositivos/{{device_id}}/mantenimiento",
            makeAuthHeaders("token_admin"),
            {
                estado_nuevo: "MANTENIMIENTO",
                motivo: "Evento técnico RF-60 QA G179"
            },
            [],
            [
                'pm.test("Status 200 - Transición manual aplicada (Genera TRANSICION_MANTENIMIENTO_MANUAL)", function () {',
                '    pm.response.to.have.status(200);',
                '});'
            ]
        )
    ]
});

// ── 03. TC-M03-342: FILTRO POR CLASIFICACION_REGISTRO ─────────────────────────
folders.push({
    name: "03-TC-M03-342-Filtro-Clasificacion",
    item: [
        makeItem(
            "08-TC-M03-342-Filtro-NIC41-Retencion-5",
            "GET",
            "{{baseUrl}}/iot/auditoria?clasificacion_registro=NIC41",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Filtro clasificacion_registro=NIC41 exitoso", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Todos los eventos clasificados NIC41 tienen retencion_aplicable=5", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(item => {',
                '        pm.expect(item.clasificacion_registro).to.eql("NIC41");',
                '        pm.expect(item.retencion_aplicable).to.eql(5);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "09-TC-M03-342-Filtro-TECNICO-Retencion-1",
            "GET",
            "{{baseUrl}}/iot/auditoria?clasificacion_registro=TECNICO",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Filtro clasificacion_registro=TECNICO exitoso", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("Todos los eventos clasificados TECNICO tienen retencion_aplicable=1", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(item => {',
                '        pm.expect(item.clasificacion_registro).to.eql("TECNICO");',
                '        pm.expect(item.retencion_aplicable).to.eql(1);',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "10-TC-M03-342-Inyeccion-Evento-Ambiguo-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria?registro_incompleto=true",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso Inyección Evento Ambiguo: No existe endpoint público para registrar eventos de auditoría sin componente_origen. Los use cases internos siempre asignan un componente canónico.");',
                'console.log("[INFO G179] Status consulta:", pm.response.code);'
            ]
        )
    ]
});

// ── 04. TC-M03-344: POSITIVOS NIC41 ───────────────────────────────────────────
folders.push({
    name: "04-TC-M03-344-Positivos-NIC41",
    item: [
        makeItem(
            "11-TC-M03-344-Verificar-RF62-EVALUACION_CALIDAD_COMPLETADA",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=EVALUACION_CALIDAD_COMPLETADA",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Eventos EVALUACION_CALIDAD_COMPLETADA obtenidos", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("RF-62 (EVALUACION_CALIDAD_COMPLETADA) clasifica como NIC41 con retención 5 años", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(item => {',
                '        pm.expect(item.clasificacion_registro).to.eql("NIC41");',
                '        pm.expect(item.retencion_aplicable).to.eql(5);',
                '        pm.expect(item.registro_incompleto).to.be.false;',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "12-TC-M03-344-Verificar-RF62-REEVALUACION_CALIDAD_SOLICITADA",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=REEVALUACION_CALIDAD_SOLICITADA",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Eventos REEVALUACION_CALIDAD_SOLICITADA obtenidos", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("RF-62 (REEVALUACION_CALIDAD_SOLICITADA) clasifica como NIC41 con retención 5 años", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(item => {',
                '        pm.expect(item.clasificacion_registro).to.eql("NIC41");',
                '        pm.expect(item.retencion_aplicable).to.eql(5);',
                '        pm.expect(item.registro_incompleto).to.be.false;',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "13-TC-M03-344-RF56-PAQUETE_INFERENCIA_GENERADO-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=PAQUETE_INFERENCIA_GENERADO",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso RF-56 PAQUETE_INFERENCIA_GENERADO: Emitido exclusivamente por motor de IA/M04 o worker de inferencia. No expone endpoint REST directo de generación síncrona en M03.");'
            ]
        ),
        makeItem(
            "14-TC-M03-344-RF61-VINCULACION_AUTOMATICA-Bloqueado",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=VINCULACION_AUTOMATICA",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcaso RF-61 VINCULACION_AUTOMATICA: Emitido por worker de vinculación edge/RFID en segundo plano. No emitible por endpoint síncrono API.");'
            ]
        )
    ]
});

// ── 05. TC-M03-345: NEGATIVOS TECNICO ─────────────────────────────────────────
folders.push({
    name: "05-TC-M03-345-Negativos-TECNICO",
    item: [
        makeItem(
            "15-TC-M03-345-Verificar-RF60-TRANSICION_MANTENIMIENTO_MANUAL",
            "GET",
            "{{baseUrl}}/iot/auditoria?tipo_evento=TRANSICION_MANTENIMIENTO_MANUAL",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'pm.test("Status 200 - Eventos TRANSICION_MANTENIMIENTO_MANUAL obtenidos", function () {',
                '    pm.response.to.have.status(200);',
                '});',
                'const res = pm.response.json();',
                'pm.test("RF-60 (TRANSICION_MANTENIMIENTO_MANUAL) clasifica como TECNICO con retención 1 año", function () {',
                '    pm.expect(res.items.length).to.be.at.least(1);',
                '    res.items.forEach(item => {',
                '        pm.expect(item.clasificacion_registro).to.eql("TECNICO");',
                '        pm.expect(item.retencion_aplicable).to.eql(1);',
                '        pm.expect(item.registro_incompleto).to.be.false;',
                '    });',
                '});'
            ]
        ),
        makeItem(
            "16-TC-M03-345-Eventos-Broker-Worker-Bloqueados",
            "GET",
            "{{baseUrl}}/iot/auditoria?clasificacion_registro=TECNICO",
            makeAuthHeaders("token_admin"),
            null,
            [],
            [
                'console.log("[BLOQUEADO] Subcasos RF-54 (BUFFER_ACTIVADO), RF-55 (DESVIACION_DETECTADA), RF-57 (ALERTA_GENERADA), RF-58, RF-59, RF-60 (DISPOSITIVO_SIN_SEÑAL):");',
                'console.log("  Motivo: Eventos emitidos por brokers MQTT, workers periódicos o procesamiento asíncrono sin interfaz REST directa en el sandbox.");',
                'pm.test("Verificación de que eventos técnicos en sandbox cumplen retención de 1 año", function () {',
                '    const res = pm.response.json();',
                '    res.items.forEach(item => {',
                '        pm.expect(item.retencion_aplicable).to.eql(1);',
                '    });',
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

const targetPath = path.join(__dirname, 'test_tc_m03_g179.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G179 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
