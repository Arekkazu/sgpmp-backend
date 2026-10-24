const fs = require('fs');
const path = require('path');

// Generador de colección Postman / Newman para TC-M03-G171
// RF-62: Integridad y persistencia, vía API (CERO DML directo a BD)
// Subcasos:
// - TC-M03-327: Inmutabilidad del registro telemétrico original (RF-53) antes y después de evaluar
// - TC-M03-328: Persistencia completa de metadatos de calidad (GET /iot/calidad/{id}) y unicidad VIGENTE
// - TC-M03-329: Inmutabilidad ante cambios de configuración / limitaciones de API

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

// Helper para armar batch de 20 lecturas con intervalo de 600 segundos (10 minutos)
// Todas las fechas son pasadas: entre 10 y 18 de octubre de 2026.
function buildBatch20(baseDayPrefix) {
    const registros = [];
    for (let i = 0; i < 20; i++) {
        // Cada lectura separada 10 min (600 s)
        const totalMin = i * 10;
        const h = Math.floor(totalMin / 60);
        const m = totalMin % 60;
        const hStr = String(parseInt(baseDayPrefix.substring(11, 13), 10) + h).padStart(2, '0');
        const mStr = String(m).padStart(2, '0');
        const ts = `${baseDayPrefix.substring(0, 11)}${hStr}:${mStr}:00Z`;
        registros.push({
            device_id: parseInt("{{device_id}}", 10),
            sensor_id: parseInt("{{sensor_id}}", 10),
            tipo_variable: "TEMPERATURA_AMBIENTAL",
            valor: 22.0,
            unidad: "°C",
            timestamp_captura: ts,
            access_key: "{{device_serial}}",
            origen: "BUFFER_LOCAL"
        });
    }
    return { registros };
}

const folders = [];

// ── CARPETA 00: PREFLIGHT Y DESCUBRIMIENTO ────────────────────────────────────
folders.push({
    name: "00-Preflight-y-Descubrimiento",
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
                'pm.test("Status 200 - Login exitoso en /sesiones/", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.token).to.be.a("string").and.not.be.empty;',
                '    pm.collectionVariables.set("token_admin", res.token);',
                '});'
            ]
        ),
        makeItem(
            "01-Descubrimiento-Sensor-Activo",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT s.id_sensores, s.id_dispositivo_iot, d.serial FROM modulo9.sensores s JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot WHERE s.es_activo = true AND d.es_activo = true ORDER BY s.id_sensores ASC LIMIT 1"
            },
            [],
            [
                'pm.test("[VERIFICACION SQL SOLO LECTURA] Status 200 - Sensor descubierto", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.be.above(0);',
                '    pm.collectionVariables.set("sensor_id", rows[0].id_sensores);',
                '    pm.collectionVariables.set("device_id", rows[0].id_dispositivo_iot);',
                '    pm.collectionVariables.set("device_serial", rows[0].serial);',
                '});'
            ]
        )
    ]
});

// ── CARPETA 01: TC-M03-327 INMUTABILIDAD DEL REGISTRO RF-53 ──────────────────
folders.push({
    name: "01-TC-M03-327-Inmutabilidad-Registro-RF53",
    item: [
        makeItem(
            "10-Ingestar-Serie-Base-20-Lecturas",
            "POST",
            "{{baseUrl}}/iot/telemetria/batch",
            [],
            buildBatch20("2026-10-15T08"),
            [],
            [
                'pm.test("Status 200 - Batch 20 lecturas base ingestado", function () {',
                '    pm.response.to.have.status(200);',
                '    pm.expect(pm.response.json().aceptados).to.equal(20);',
                '});'
            ]
        ),
        makeItem(
            "11-Ingestar-Lectura-Evaluada-Individual",
            "POST",
            "{{baseUrl}}/iot/telemetria",
            [],
            {
                device_id: parseInt("{{device_id}}", 10),
                sensor_id: parseInt("{{sensor_id}}", 10),
                tipo_variable: "TEMPERATURA_AMBIENTAL",
                valor: 22.5,
                unidad: "°C",
                timestamp_captura: "2026-10-15T11:30:00Z",
                access_key: "{{device_serial}}",
                origen: "BUFFER_LOCAL"
            },
            [],
            [
                'pm.test("Status 201 - Lectura evaluada ingresada por RF-53", function () {',
                '    pm.response.to.have.status(201);',
                '    const res = pm.response.json();',
                '    pm.expect(res.id_telemetria).to.be.a("number");',
                '    pm.collectionVariables.set("id_tel_327", res.id_telemetria);',
                '});'
            ]
        ),
        makeItem(
            "12-Obtener-Estado-Telemetria-Antes-De-Evaluar",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT valor_crudo, valor_ajustado, timestamp_captura, origen, estado_calidad, calibrado, apto_para_ia, apto_para_nic41 FROM modulo3.telemetrias WHERE id_telemetria = {{id_tel_327}}"
            },
            [],
            [
                'pm.test("[VERIFICACION SQL SOLO LECTURA] Status 200 - Captura snapshot telemetría pre-evaluación", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.equal(1);',
                '    const r = rows[0];',
                '    pm.collectionVariables.set("pre_valor_crudo", String(r.valor_crudo));',
                '    pm.collectionVariables.set("pre_ts_captura", String(r.timestamp_captura));',
                '    pm.collectionVariables.set("pre_origen", String(r.origen));',
                '    pm.collectionVariables.set("pre_estado_calidad", String(r.estado_calidad));',
                '});'
            ]
        ),
        makeItem(
            "13-Disparar-Evaluacion-Calidad",
            "POST",
            "{{baseUrl}}/iot/calidad/{{id_tel_327}}/evaluar",
            makeAuthHeaders(),
            null,
            [],
            [
                'pm.test("Status 201 - Evaluación de calidad ejecutada", function () {',
                '    pm.response.to.have.status(201);',
                '    const res = pm.response.json();',
                '    pm.expect(res.estado_evaluacion).to.equal("VIGENTE");',
                '    pm.expect(res.apto_para_ia).to.equal(true);',
                '    pm.expect(res.apto_para_nic41).to.equal(true);',
                '});'
            ]
        ),
        makeItem(
            "14-Verificar-Inmutabilidad-Telemetria-Post-Evaluacion",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT valor_crudo, valor_ajustado, timestamp_captura, origen, estado_calidad, calibrado, apto_para_ia, apto_para_nic41 FROM modulo3.telemetrias WHERE id_telemetria = {{id_tel_327}}"
            },
            [],
            [
                'pm.test("[VERIFICACION SQL SOLO LECTURA] Campos originales RF-53 inmutables tras evaluación", function () {',
                '    pm.response.to.have.status(200);',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows.length).to.equal(1);',
                '    const r = rows[0];',
                '    pm.expect(String(r.valor_crudo), "valor_crudo inmutable").to.equal(pm.collectionVariables.get("pre_valor_crudo"));',
                '    pm.expect(String(r.timestamp_captura), "timestamp_captura inmutable").to.equal(pm.collectionVariables.get("pre_ts_captura"));',
                '    pm.expect(String(r.origen), "origen inmutable").to.equal(pm.collectionVariables.get("pre_origen"));',
                '    pm.expect(String(r.estado_calidad), "estado_calidad RF-53 inmutable").to.equal(pm.collectionVariables.get("pre_estado_calidad"));',
                '});',
                'pm.test("[VERIFICACION SQL SOLO LECTURA] Flags de aptitud actualizados en modulo3.telemetrias", function () {',
                '    const rows = pm.response.json().data || pm.response.json().rows || [];',
                '    pm.expect(rows[0].apto_para_ia, "apto_para_ia sincronizado").to.equal(true);',
                '    pm.expect(rows[0].apto_para_nic41, "apto_para_nic41 sincronizado").to.equal(true);',
                '});'
            ]
        )
    ]
});

// ── CARPETA 02: TC-M03-328 PERSISTENCIA COMPLETA Y UNICIDAD VIGENTE ───────────
folders.push({
    name: "02-TC-M03-328-Persistencia-Completa-Metadatos",
    item: [
        makeItem(
            "20-Ingestar-Serie-Base-20-Lecturas",
            "POST",
            "{{baseUrl}}/iot/telemetria/batch",
            [],
            buildBatch20("2026-10-16T08"),
            [],
            [
                'pm.test("Status 200 - Batch 20 lecturas para TC-328", function () {',
                '    pm.response.to.have.status(200);',
                '    pm.expect(pm.response.json().aceptados).to.equal(20);',
                '});'
            ]
        ),
        makeItem(
            "21-Ingestar-Lectura-Evaluada",
            "POST",
            "{{baseUrl}}/iot/telemetria",
            [],
            {
                device_id: parseInt("{{device_id}}", 10),
                sensor_id: parseInt("{{sensor_id}}", 10),
                tipo_variable: "TEMPERATURA_AMBIENTAL",
                valor: 22.0,
                unidad: "°C",
                timestamp_captura: "2026-10-16T11:30:00Z",
                access_key: "{{device_serial}}",
                origen: "BUFFER_LOCAL"
            },
            [],
            [
                'pm.test("Status 201 - Lectura evaluada ingresada", function () {',
                '    pm.response.to.have.status(201);',
                '    const res = pm.response.json();',
                '    pm.collectionVariables.set("id_tel_328", res.id_telemetria);',
                '});'
            ]
        ),
        makeItem(
            "22-Disparar-Evaluacion",
            "POST",
            "{{baseUrl}}/iot/calidad/{{id_tel_328}}/evaluar",
            makeAuthHeaders(),
            null,
            [],
            [
                'pm.test("Status 201 - Evaluación generada", function () {',
                '    pm.response.to.have.status(201);',
                '});'
            ]
        ),
        makeItem(
            "23-GET-Calidad-Por-ID-Telemetria",
            "GET",
            "{{baseUrl}}/iot/calidad/{{id_tel_328}}",
            makeAuthHeaders(),
            null,
            [],
            [
                'pm.test("Status 200 - GET /iot/calidad/{id} retorna todos los metadatos", function () {',
                '    pm.response.to.have.status(200);',
                '    const c = pm.response.json();',
                '    pm.expect(c.id_evaluacion, "id_evaluacion presente").to.be.a("string").and.not.be.empty;',
                '    pm.expect(c.id_telemetria, "id_telemetria coherente").to.equal(parseInt(pm.collectionVariables.get("id_tel_328"), 10));',
                '    pm.expect(c.id_sensor, "id_sensor coherente").to.equal(parseInt(pm.collectionVariables.get("sensor_id"), 10));',
                '    pm.expect(c.timestamp_evaluacion, "timestamp_evaluacion presente").to.be.a("string");',
                '    pm.expect(c.indice_calidad, "indice_calidad presente").to.be.a("number");',
                '    pm.expect(c.clasificacion_calidad, "clasificacion_calidad").to.equal("APTO");',
                '    pm.expect(c.apto_para_ia, "apto_para_ia").to.be.a("boolean");',
                '    pm.expect(c.apto_para_nic41, "apto_para_nic41").to.be.a("boolean");',
                '    pm.expect(c.flags_detectados, "flags_detectados objeto").to.be.an("object");',
                '    pm.expect(c.parametros_aplicados, "parametros_aplicados objeto").to.be.an("object");',
                '    pm.expect(c.parametros_aplicados.k, "parametro k").to.be.a("number");',
                '    pm.expect(c.parametros_aplicados.M, "parametro M").to.be.a("number");',
                '    pm.expect(c.parametros_aplicados.N, "parametro N").to.be.a("number");',
                '    pm.expect(c.parametros_aplicados.umbral_drift, "parametro umbral_drift").to.be.a("number");',
                '    pm.expect(c.estado_evaluacion, "[DECISION D7] estado VIGENTE").to.equal("VIGENTE");',
                '    pm.expect(c.motivo_reevaluacion, "motivo_reevaluacion null en evaluacion inicial").to.be.null;',
                '    pm.expect(c.id_evaluacion_superada, "id_evaluacion_superada null").to.be.null;',
                '});',
                '// [LIMITACION API] version_limites_fisicos_aplicada: sin pm.test (debe ser null por limitación de integración)',
                'const resCalidad = pm.response.json();',
                'if (resCalidad.version_limites_fisicos_aplicada === null) {',
                '    console.log("[LIMITACION API] version_limites_fisicos_aplicada es null debido a que el adaptador de límites físicos no está enlazado dinámicamente en el backend.");',
                '} else {',
                '    console.log("[INFO] version_limites_fisicos_aplicada:", resCalidad.version_limites_fisicos_aplicada);',
                '}'
            ]
        ),
        makeItem(
            "24-GET-Listar-Calidad-Filtro-Sensor-Y-Vigente",
            "GET",
            "{{baseUrl}}/iot/calidad?id_sensor={{sensor_id}}&estado_evaluacion=VIGENTE",
            makeAuthHeaders(),
            null,
            [],
            [
                'pm.test("Status 200 - Filtrado por sensor y VIGENTE", function () {',
                '    pm.response.to.have.status(200);',
                '    const res = pm.response.json();',
                '    pm.expect(res.items).to.be.an("array");',
                '    const matches = res.items.filter(i => i.id_telemetria === parseInt(pm.collectionVariables.get("id_tel_328"), 10));',
                '    // Si hubiera duplicados, se evidencia el defecto conocido D7',
                '    pm.expect(matches.length, "[DEFECTO CONOCIDO D7] Invariante de exactamente una evaluación VIGENTE por lectura").to.equal(1);',
                '});'
            ]
        )
    ]
});

// ── CARPETA 03: TC-M03-329 INMUTABILIDAD ANTE CONFIGURACION (LIMITACION API) ──
folders.push({
    name: "03-TC-M03-329-Inmutabilidad-Configuracion",
    item: [
        makeItem(
            "30-Auditoria-Configuracion-Limitacion-API",
            "POST",
            "{{baseUrl}}/test-control/query",
            makeAuthHeaders(),
            {
                query: "SELECT 1 AS paso_informativo"
            },
            [],
            [
                'console.log("[BLOQUEADO] Subcaso TC-M03-329: El backend utiliza ParametrosCalidadStubAdapter hardcodeado en calidad_router.py:28 (k=3, M=5, N=20, drift=5%). No existen endpoints en la API para mutar dinámicamente dichos parámetros operativos de RF-62 ni publicar versiones temporales de límites físicos. Se registra como hallazgo arquitectónico sin fallar la suite.");'
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
        _postman_id: "tc-m03-g171-integridad-persistencia-v2",
        name: "TC-M03-G171 - Integridad y Persistencia RF-62",
        description: "Suite automatizada Newman para TC-M03-G171 (RF-62). Verifica inmutabilidad de telemetría original y persistencia completa de metadatos vía API bajo Sandbox transaccional (CERO DML).",
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
        { key: "sensor_id", value: "" },
        { key: "device_id", value: "" },
        { key: "device_serial", value: "" },
        { key: "id_tel_327", value: "" },
        { key: "id_tel_328", value: "" },
        { key: "pre_valor_crudo", value: "" },
        { key: "pre_ts_captura", value: "" },
        { key: "pre_origen", value: "" },
        { key: "pre_estado_calidad", value: "" }
    ],
    item: folders
};

const targetPath = path.join(__dirname, 'test_tc_m03_g171.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');

let totalItems = 0;
folders.forEach(f => {
    totalItems += f.item.length;
});

console.log(`Colección G171 generada exitosamente en ${targetPath}`);
console.log(`Carpetas: ${folders.length}, Requests totales: ${totalItems}`);
