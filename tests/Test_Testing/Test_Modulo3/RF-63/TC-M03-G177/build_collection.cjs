// | Fecha      | Nombre     | Que se hizo                                                                           |
// |------------|------------|---------------------------------------------------------------------------------------|
// | 2026-10-26 | HulkyZeus  | TC-M03-G177 RF-63: aviso, la coleccion paso a solo lectura y este generador quedo atras |
// AVISO: la coleccion vigente (test_tc_m03_g177.json) se actualizo a mano (sin pasos de escritura). Regenerarla con este
// script restauraria la preparacion anterior, que ya no funciona; ver DISENO_Y_PRECONDICIONES.md.
const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G177
// RF-63 (Bitácora de Auditoría IoT) — Consulta básica y detalle
// Subcasos:
// - TC-M03-336: Listado sin filtros, paginación (default 50, max 200, 422 en >200),
//               campos base RF-10 (11) + extensión IoT (8) + timestamp_registro,
//               modulo="M03", sin componente_origen, total backend.
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

// ── 01. SETUP SINTÉTICO (CATÁLOGO EN SANDBOX) ─────────────────────────────────
const setupItems = [
    makeItem(
        "01-Crear-Finca-Sintetica",
        "POST",
        "{{baseUrl}}/configuracion/fincas",
        makeAuthHeaders("token_admin"),
        {
            nombre: "Finca QA G177 Audit",
            ubicacion: "Vereda Central QA",
            area_total: 150.0
        },
        [],
        [
            'pm.test("Status 201/200 - Finca creada en sandbox", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
            '    const res = pm.response.json();',
            '    const idFinca = res.id_finca || (res.finca && res.finca.id_finca) || res.id;',
            '    pm.expect(idFinca).to.be.ok;',
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
            nombre: "Galpón 177 Auditoría",
            id_tipo_area: 1,
            capacidad_maxima: 500
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
            '    pm.expect(idInfra).to.be.ok;',
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
            numero_serie: "DEV-G177-INIT",
            id_tipo_dispositivo: 1,
            modelo: "ESP32-G177-AUDIT",
            firmware_version: "2.1.0"
        },
        [
            'const infId = parseInt(pm.collectionVariables.get("infra_id"), 10);',
            'const body = JSON.parse(pm.request.body.raw);',
            'body.id_infraestructura = infId;',
            'const serial = "DEV-G177-" + Math.floor(100000 + Math.random() * 900000);',
            'body.numero_serie = serial;',
            'pm.collectionVariables.set("device_serial", serial);',
            'pm.request.body.raw = JSON.stringify(body);'
        ],
        [
            'pm.test("Status 201/200 - Dispositivo creado en sandbox", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
            '    const res = pm.response.json();',
            '    const idDev = res.id_dispositivo_iot || res.id_dispositivo || res.id;',
            '    pm.expect(idDev).to.be.ok;',
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
            '    pm.expect(idSen).to.be.ok;',
            '    pm.collectionVariables.set("sensor_id", String(idSen));',
            '});'
        ]
    )
];

folders.push({
    name: "01-Setup-Sintetico-Catalogo",
    item: setupItems
});

// ── 02. SETUP GENERACIÓN DE EVENTOS POR API ───────────────────────────────────
// Para que la bitácora RF-63 contenga eventos que auditar, ejecutamos:
// 1. Ingesta batch de telemetría (POST /iot/telemetria/batch) -> genera eventos EVALUACION_CALIDAD_COMPLETADA (RF-62, NIC41, retencion 5)
// 2. Transición de mantenimiento de dispositivo (PATCH /iot/dispositivos/{id}/mantenimiento) -> genera TRANSICION_MANTENIMIENTO_MANUAL (RF-60, TECNICO, retencion 1)
// 3. Re-evaluación de calidad (POST /iot/calidad/reevaluar) -> genera REEVALUACION_CALIDAD_SOLICITADA (RF-62, NIC41, retencion 5)
const genEventsItems = [
    makeItem(
        "05-Ingesta-Batch-Telemetria",
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
            '// 20 lecturas pasadas (12-oct-2026), espaciadas cada 10 min (600s)',
            'const baseEpoch = 1791792000; // 2026-10-12T08:00:00Z',
            'for (let i = 0; i < 20; i++) {',
            '    const dt = new Date((baseEpoch + (i * 600)) * 1000).toISOString();',
            '    lecturas.push({',
            '        id_sensor: sensorId,',
            '        valor: 24.5 + (i * 0.1),',
            '        timestamp_captura: dt',
            '    });',
            '}',
            'pm.request.body.raw = JSON.stringify({ origen: "BUFFER_LOCAL", lecturas: lecturas });'
        ],
        [
            'pm.test("Status 200/201 - Batch ingerido exitosamente", function () {',
            '    pm.expect(pm.response.code).to.be.oneOf([200, 201]);',
            '    const res = pm.response.json();',
            '    const total = res.total_procesadas || res.procesadas || (res.items && res.items.length) || 0;',
            '    pm.expect(total).to.be.at.least(1);',
            '    if (res.items && res.items.length > 0) {',
            '        const idTel = res.items[0].id_telemetria || res.items[0].id;',
            '        if (idTel) pm.collectionVariables.set("id_telemetria_eval", String(idTel));',
            '    }',
            '});'
        ]
    ),
    makeItem(
        "06-Transicion-Mantenimiento-Dispositivo",
        "PATCH",
        "{{baseUrl}}/iot/dispositivos/{{device_id}}/mantenimiento",
        makeAuthHeaders("token_admin"),
        {
            estado_nuevo: "MANTENIMIENTO",
            motivo: "Inspeccion tecnica semestral QA G177"
        },
        [],
        [
            'pm.test("Status 200 - Transición manual a mantenimiento aplicada", function () {',
            '    pm.response.to.have.status(200);',
            '    const res = pm.response.json();',
            '    pm.expect(res.estado_actual).to.eql("MANTENIMIENTO");',
            '});'
        ]
    ),
    makeItem(
        "07-Solicitar-Reevaluacion-Calidad",
        "POST",
        "{{baseUrl}}/iot/calidad/reevaluar",
        makeAuthHeaders("token_admin"),
        {
            id_sensor: "{{sensor_id}}",
            fecha_inicio: "2026-10-12T00:00:00Z",
            fecha_fin: "2026-10-12T23:59:59Z",
            motivo: "Re-evaluacion auditoria G177"
        },
        [
            'const sensorId = parseInt(pm.collectionVariables.get("sensor_id"), 10);',
            'const body = JSON.parse(pm.request.body.raw);',
            'body.id_sensor = sensorId;',
            'pm.request.body.raw = JSON.stringify(body);'
        ],
        [
            'pm.test("Status 200 - Reevaluación de calidad ejecutada", function () {',
            '    pm.response.to.have.status(200);',
            '});'
        ]
    )
];

folders.push({
    name: "02-Setup-Generacion-Eventos",
    item: genEventsItems
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
    makeItem(
        "11-TC-M03-336-Paginacion-Excedida-Rechazada",
        "GET",
        "{{baseUrl}}/iot/auditoria?por_pagina=201",
        makeAuthHeaders("token_admin"),
        null,
        [],
        [
            'pm.test("Status 422 - por_pagina > 200 rechazado con Unprocessable Entity", function () {',
            '    pm.response.to.have.status(422);',
            '});'
        ]
    )
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
    makeItem(
        "13-TC-M03-337-Verificar-Integridad-Bitacora-Backend",
        "POST",
        "{{baseUrl}}/iot/auditoria/verificar-integridad",
        makeAuthHeaders("token_admin"),
        null,
        [],
        [
            'pm.test("Status 200 - Verificación de integridad SHA-256 exitosa en backend", function () {',
            '    pm.response.to.have.status(200);',
            '    const res = pm.response.json();',
            '    pm.expect(res.total_verificados).to.be.at.least(1);',
            '    pm.expect(res.comprometidos).to.eql(0);',
            '    pm.expect(res.ids_comprometidos).to.eql([]);',
            '});'
        ]
    ),
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
    makeItem(
        "15-TC-M03-337-UUID-Malformado-Responde-422",
        "GET",
        "{{baseUrl}}/iot/auditoria/uuid-invalido-12345",
        makeAuthHeaders("token_admin"),
        null,
        [],
        [
            'pm.test("Status 422 - UUID malformado responde Unprocessable Entity", function () {',
            '    pm.response.to.have.status(422);',
            '});'
        ]
    )
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
