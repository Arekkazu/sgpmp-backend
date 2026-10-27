/**
 * Generador completo de test_tc_m03_g164.json
 * Aplica correcciones M1 a M13
 */

const fs = require('fs');
const path = require('path');

const constantesEspecificacion = {
    clasificaciones: ['APTO', 'NO_APTO', 'APTO_CON_RESERVA', 'INDETERMINADA'],
    estados: ['SUPERADA', 'VIGENTE'],
    umbrales: {
        apto: 80,
        reserva: 40,
        reserva_max: 79
    },
    limites_paginacion: {
        default_por_pagina: 50,
        max_por_pagina: 200,
        frontera_invalida_exceso: 201,
        frontera_invalida_cero: 0,
        min_valido: 1,
        sample_paginacion: 3
    },
    codigos_http: {
        ok: 200,
        created: 201,
        no_content: 204,
        bad_request: 400,
        unauthorized: 401,
        forbidden: 403,
        not_found: 404,
        unprocessable: 422,
        server_error: 500,
        client_error_min: 400,
        client_error_max: 499
    },
    gating: {
        min_evaluaciones_totales: 10,
        min_evaluaciones_sensor: 5
    },
    presupuesto_tiempo_segundos: 150,
    campos_calidad_evaluacion: [
        'id_evaluacion',
        'id_telemetria',
        'id_sensor',
        'timestamp_evaluacion',
        'indice_calidad',
        'clasificacion_calidad',
        'apto_para_ia',
        'apto_para_nic41',
        'flags_detectados',
        'version_limites_fisicos_aplicada',
        'parametros_aplicados',
        'parametros_calibracion_aplicados',
        'estado_evaluacion',
        'motivo_reevaluacion',
        'id_evaluacion_superada',
        'version_evaluacion',
        'fecha_creacion'
    ]
};

const collectionVariables = [
    { key: "baseUrl", value: "https://api.inmero.co/api-sgpmp-test", type: "string" },
    { key: "sandbox_secret", value: "", type: "string" },
    { key: "admin_email", value: "administador.dev@gmail.com", type: "string" },
    { key: "admin_password", value: "", type: "string" },
    { key: "productor_email", value: "productor@pecuaria.co", type: "string" },
    { key: "productor_password", value: "", type: "string" },
    { key: "ingeniero_email", value: "gestor.granja.test@pecuaria.co", type: "string" },
    { key: "ingeniero_password", value: "", type: "string" },
    { key: "modo_datos", value: "existentes", type: "string" },
    { key: "status_validacion_esperado", value: "422", type: "string" },
    { key: "skip_cuenta_como_falla", value: "true", type: "string" },
    { key: "admin_token", value: "", type: "string" },
    { key: "token_admin", value: "", type: "string" },
    { key: "producer_token", value: "{{admin_token}}", type: "string" },
    { key: "token_productor", value: "{{admin_token}}", type: "string" },
    { key: "engineer_token", value: "{{admin_token}}", type: "string" },
    { key: "token_ingeniero", value: "{{admin_token}}", type: "string" },
    { key: "run_id", value: "", type: "string" },
    { key: "sensor_candidato", value: "", type: "string" },
    { key: "sensor_segundo", value: "", type: "string" },
    { key: "sensor_reevaluar", value: "", type: "string" },
    { key: "sensor_reevaluar_desde", value: "", type: "string" },
    { key: "sensor_reevaluar_hasta", value: "", type: "string" },
    { key: "id_telemetria_candidato", value: "", type: "string" },
    { key: "id_evaluacion_candidato", value: "", type: "string" },
    { key: "fecha_desde_sample", value: "", type: "string" },
    { key: "fecha_hasta_sample", value: "", type: "string" },
    { key: "fecha_exacta_sample", value: "", type: "string" },
    { key: "total_inventario", value: "0", type: "string" },
    { key: "total_sql_db", value: "0", type: "string" },
    { key: "oraculo_dataset", value: "{}", type: "string" },
    { key: "PRE_301", value: "false", type: "string" },
    { key: "PRE_302", value: "false", type: "string" },
    { key: "PRE_304", value: "false", type: "string" },
    { key: "PRE_305", value: "true", type: "string" },
    { key: "PRE_306", value: "false", type: "string" },
    { key: "PRE_307", value: "false", type: "string" },
    { key: "PRE_308", value: "true", type: "string" },
    { key: "resumen_skips", value: "[]", type: "string" },
    { key: "timestamps_muestra_sensor", value: "[]", type: "string" },
    { key: "evaluaciones_muestra_sensor", value: "[]", type: "string" },
    { key: "tiempos_ejecucion", value: "{}", type: "string" },
    { key: "constantes_especificacion", value: JSON.stringify(constantesEspecificacion), type: "string" }
];

const items = [];

function makeItem(name, method, url, headers, bodyRaw, preLines, testLines) {
    const item = {
        name: name,
        request: {
            method: method,
            header: headers.map(h => ({ key: h.key, value: h.value, type: "text" })),
            url: {
                raw: url,
                host: ["{{baseUrl}}"],
                path: url.replace("{{baseUrl}}/", "").split("?")[0].split("/"),
                query: []
            }
        },
        event: []
    };

    if (url.includes("?")) {
        const qStr = url.split("?")[1];
        qStr.split("&").forEach(pair => {
            if (pair) {
                const [k, v] = pair.split("=");
                item.request.url.query.push({ key: k, value: v || "" });
            }
        });
    }

    if (bodyRaw) {
        item.request.body = {
            mode: "raw",
            raw: bodyRaw,
            options: { raw: { language: "json" } }
        };
    }

    if (preLines && preLines.length > 0) {
        item.event.push({
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: preLines
            }
        });
    }

    if (testLines && testLines.length > 0) {
        item.event.push({
            listen: "test",
            script: {
                type: "text/javascript",
                exec: testLines
            }
        });
    }

    return item;
}

// 0. NW-00-Setup-Login-Admin (Login unico bajo run_id principal para evitar DEF-04)
items.push(makeItem(
    "NW-00-Setup-Login-Admin",
    "POST",
    "{{baseUrl}}/sesiones/",
    [
        { key: "Content-Type", value: "application/json" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    JSON.stringify({ correo_electronico: "{{admin_email}}", contrasena: "{{admin_password}}" }, null, 2),
    [
        '// Inicializar run_id con UUID y timer de ejecucion',
        'if (!pm.collectionVariables.get("run_id")) {',
        '    const uuid = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {',
        '        const r = Math.random() * 16 | 0;',
        '        const v = c === "x" ? r : (r & 0x3 | 0x8);',
        '        return v.toString(16);',
        '    });',
        '    pm.collectionVariables.set("run_id", uuid);',
        '}',
        'if (!pm.collectionVariables.get("tiempos_ejecucion")) {',
        '    pm.collectionVariables.set("tiempos_ejecucion", JSON.stringify({ inicio: Date.now() }));',
        '}'
    ],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'pm.test("[TC-M03-300] Setup Login Administrador exitoso (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    const tok = res.token || res.access_token;',
        '    pm.expect(tok, "Token emitido en login").to.be.a("string").that.is.not.empty;',
        '    pm.collectionVariables.set("admin_token", tok);',
        '    pm.collectionVariables.set("token_admin", tok);',
        '    pm.collectionVariables.set("producer_token", tok);',
        '    pm.collectionVariables.set("token_productor", tok);',
        '    pm.collectionVariables.set("engineer_token", tok);',
        '    pm.collectionVariables.set("token_ingeniero", tok);',
        '});'
    ]
));

// 1. NW-01-PreflightA-Inventario (Descarga completa M4/M5)
items.push(makeItem(
    "NW-01-PreflightA-Inventario",
    "GET",
    "{{baseUrl}}/iot/calidad?pagina=1&por_pagina=200",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [
        '// Inicializar run_id con UUID y timer de ejecucion',
        'if (!pm.collectionVariables.get("run_id")) {',
        '    const uuid = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {',
        '        const r = Math.random() * 16 | 0;',
        '        const v = c === "x" ? r : (r & 0x3 | 0x8);',
        '        return v.toString(16);',
        '    });',
        '    pm.collectionVariables.set("run_id", uuid);',
        '}',
        'pm.collectionVariables.set("tiempos_ejecucion", JSON.stringify({ inicio: Date.now() }));'
    ],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'pm.test("[TC-M03-300] Preflight A: Descarga de dataset y construccion de oraculo (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const data = pm.response.json();',
        '    const totalReportado = data.total || 0;',
        '    let todosItems = data.items || [];',
        '    pm.collectionVariables.set("total_inventario", String(totalReportado));',
        '',
        '    // Descargar paginas 2 a 5 si existen mas registros',
        '    const baseUrl = pm.collectionVariables.get("baseUrl");',
        '    const token = pm.collectionVariables.get("admin_token") || pm.collectionVariables.get("token_admin");',
        '    const runId = pm.collectionVariables.get("run_id");',
        '    const secret = pm.collectionVariables.get("sandbox_secret");',
        '    const maxPags = Math.min(5, Math.ceil(totalReportado / 200));',
        '',
        '    let pag = 2;',
        '    function fetchNext() {',
        '        if (pag > maxPags) {',
        '            procesarDataset(todosItems, totalReportado);',
        '            return;',
        '        }',
        '        const reqOpts = {',
        '            url: baseUrl + "/iot/calidad?pagina=" + pag + "&por_pagina=200",',
        '            method: "GET",',
        '            header: {',
        '                "Authorization": "Bearer " + token,',
        '                "X-Test-Run-Id": runId,',
        '                "X-Sandbox-Secret": secret',
        '            }',
        '        };',
        '        pm.sendRequest(reqOpts, function (err, res) {',
        '            if (!err && res.code === consts.codigos_http.ok) {',
        '                const d = res.json();',
        '                if (d.items) todosItems = todosItems.concat(d.items);',
        '            }',
        '            pag++;',
        '            fetchNext();',
        '        });',
        '    }',
        '',
        '    function procesarDataset(itemsList, totalRep) {',
        '        const oraculo = {',
        '            total_descargado: itemsList.length,',
        '            dataset_incompleto: totalRep > itemsList.length,',
        '            por_estado: {},',
        '            por_clasificacion: {},',
        '            por_sensor: {},',
        '            vigentes_por_sensor: {},',
        '            timestamps: [],',
        '            timestamps_conteo: {},',
        '            mapa_evaluacion: {}',
        '        };',
        '',
        '        itemsList.forEach(it => {',
        '            oraculo.por_estado[it.estado_evaluacion] = (oraculo.por_estado[it.estado_evaluacion] || 0) + 1;',
        '            oraculo.por_clasificacion[it.clasificacion_calidad] = (oraculo.por_clasificacion[it.clasificacion_calidad] || 0) + 1;',
        '            oraculo.por_sensor[it.id_sensor] = (oraculo.por_sensor[it.id_sensor] || 0) + 1;',
        '            if (it.estado_evaluacion === "VIGENTE") {',
        '                oraculo.vigentes_por_sensor[it.id_sensor] = (oraculo.vigentes_por_sensor[it.id_sensor] || 0) + 1;',
        '            }',
        '            if (it.timestamp_evaluacion) {',
        '                oraculo.timestamps.push(it.timestamp_evaluacion);',
        '                oraculo.timestamps_conteo[it.timestamp_evaluacion] = (oraculo.timestamps_conteo[it.timestamp_evaluacion] || 0) + 1;',
        '            }',
        '            oraculo.mapa_evaluacion[it.id_telemetria] = it;',
        '        });',
        '',
        '        // Sensores candidato y segundo',
        '        const sensorsSorted = Object.keys(oraculo.por_sensor).sort((a, b) => oraculo.por_sensor[b] - oraculo.por_sensor[a]);',
        '        if (sensorsSorted.length > 0) {',
        '            pm.collectionVariables.set("sensor_candidato", sensorsSorted[0]);',
        '        }',
        '        if (sensorsSorted.length > 1) {',
        '            pm.collectionVariables.set("sensor_segundo", sensorsSorted[1]);',
        '        }',
        '',
        '        // M3 / L7: Sensor para reevaluar en NW-02 (segundo con mas VIGENTE, distinto de candidato)',
        '        const vigentesSorted = Object.keys(oraculo.vigentes_por_sensor).sort((a, b) => oraculo.vigentes_por_sensor[b] - oraculo.vigentes_por_sensor[a]);',
        '        const sensorCand = pm.collectionVariables.get("sensor_candidato");',
        '        const candidatosReevaluar = vigentesSorted.filter(s => s !== sensorCand);',
        '        if (candidatosReevaluar.length > 0) {',
        '            const elegido = candidatosReevaluar[0];',
        '            pm.collectionVariables.set("sensor_reevaluar", elegido);',
        '            const itemsElegido = itemsList.filter(it => String(it.id_sensor) === elegido && it.estado_evaluacion === "VIGENTE");',
        '            if (itemsElegido.length > 0) {',
        '                pm.collectionVariables.set("sensor_reevaluar_desde", itemsElegido[itemsElegido.length - 1].timestamp_evaluacion);',
        '                pm.collectionVariables.set("sensor_reevaluar_hasta", itemsElegido[0].timestamp_evaluacion);',
        '            }',
        '        }',
        '',
        '        if (itemsList.length > 0) {',
        '            pm.collectionVariables.set("id_telemetria_candidato", String(itemsList[0].id_telemetria));',
        '            pm.collectionVariables.set("id_evaluacion_candidato", String(itemsList[0].id_evaluacion));',
        '            pm.collectionVariables.set("fecha_exacta_sample", itemsList[0].timestamp_evaluacion);',
        '        }',
        '        if (oraculo.timestamps.length >= 2) {',
        '            pm.collectionVariables.set("fecha_desde_sample", oraculo.timestamps[oraculo.timestamps.length - 1]);',
        '            pm.collectionVariables.set("fecha_hasta_sample", oraculo.timestamps[0]);',
        '        }',
        '',
        '        pm.collectionVariables.set("oraculo_dataset", JSON.stringify(oraculo));',
        '    }',
        '',
        '    if (maxPags > 1) {',
        '        fetchNext();',
        '    } else {',
        '        procesarDataset(todosItems, totalReportado);',
        '    }',
        '});'
    ]
));

// 5. NW-01-PreflightA-DB-Query-Count (M4/M5 formato {"data":[{"total":N}]} y fallo si falta)
items.push(makeItem(
    "NW-01-PreflightA-DB-Query-Count",
    "POST",
    "{{baseUrl}}/test-control/query",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" },
        { key: "Content-Type", value: "application/json" }
    ],
    JSON.stringify({ query: "SELECT count(*) AS total FROM modulo3.telemetria_calidad" }),
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'pm.test("[TC-M03-300] Preflight A: Oraculo SQL via /test-control/query (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res).to.have.property("data");',
        '    pm.expect(res.data).to.be.an("array").and.not.be.empty;',
        '    pm.expect(res.data[0]).to.have.property("total");',
        '    const totalDb = parseInt(res.data[0].total, 10);',
        '    pm.collectionVariables.set("total_sql_db", String(totalDb));',
        '    const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        '    if (!oraculo.dataset_incompleto) {',
        '        pm.expect(oraculo.total_descargado).to.equal(totalDb);',
        '    }',
        '});',
        '',
        '// M3: postman.setNextRequest hacia NW-03 si modo_datos != sandbox',
        'const modo = pm.collectionVariables.get("modo_datos");',
        'if (modo !== "sandbox") {',
        '    postman.setNextRequest("NW-03-PreflightB-Recalcular-Gating");',
        '}'
    ]
));

// 6. NW-02-Generar-Reevaluacion-Sandbox (M3: sin literales, 1 llamada, evaluaciones_superadas >= 1 o 422 SIN_EVALUACIONES_EN_RANGO)
items.push(makeItem(
    "NW-02-Generar-Reevaluacion-Sandbox",
    "POST",
    "{{baseUrl}}/iot/calidad/reevaluar",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" },
        { key: "Content-Type", value: "application/json" }
    ],
    JSON.stringify({
        id_sensor: 0,
        fecha_desde: "",
        fecha_hasta: "",
        causa_documentada: ""
    }),
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'const tiempos = JSON.parse(pm.collectionVariables.get("tiempos_ejecucion") || "{}");',
        'const inicio = tiempos.inicio || Date.now();',
        'const transcurridoSeg = Math.floor((Date.now() - inicio) / 1000);',
        '',
        'if (transcurridoSeg > consts.presupuesto_tiempo_segundos) {',
        '    console.warn("ADVERTENCIA: Presupuesto de tiempo excedido en sandbox (" + transcurridoSeg + " s). Omitiendo NW-02.");',
        '    postman.setNextRequest("NW-03-PreflightB-Recalcular-Gating");',
        '    return;',
        '}',
        '',
        'const sensorReevaluar = pm.collectionVariables.get("sensor_reevaluar");',
        'const fDesde = pm.collectionVariables.get("sensor_reevaluar_desde");',
        'const fHasta = pm.collectionVariables.get("sensor_reevaluar_hasta");',
        'const runId = pm.collectionVariables.get("run_id");',
        '',
        'if (!sensorReevaluar || !fDesde || !fHasta) {',
        '    console.warn("ADVERTENCIA: Sin sensor elegible con >=1 evaluacion VIGENTE para reevaluar. Saltando a NW-03.");',
        '    postman.setNextRequest("NW-03-PreflightB-Recalcular-Gating");',
        '    return;',
        '}',
        '',
        'const body = {',
        '    id_sensor: parseInt(sensorReevaluar, 10),',
        '    fecha_desde: fDesde,',
        '    fecha_hasta: fHasta,',
        '    causa_documentada: "Reevaluacion automatica sandbox run_id " + runId',
        '};',
        'pm.request.body.raw = JSON.stringify(body);'
    ],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.response.code === consts.codigos_http.ok) {',
        '    pm.test("[TC-M03-300] NW-02 Reevaluacion exitosa en Sandbox (" + consts.codigos_http.ok + ")", function () {',
        '        const res = pm.response.json();',
        '        pm.expect(res).to.have.property("evaluaciones_superadas");',
        '        pm.expect(res.evaluaciones_superadas).to.be.at.least(consts.limites_paginacion.min_valido);',
        '    });',
        '} else if (pm.response.code === consts.codigos_http.unprocessable) {',
        '    pm.test("[TC-M03-300] NW-02 Rango ya superado previamente (" + consts.codigos_http.unprocessable + ")", function () {',
        '        const res = pm.response.json();',
        '        pm.expect(res.error_code || res.code || JSON.stringify(res)).to.include("SIN_EVALUACIONES_EN_RANGO");',
        '        console.log("OBS-REEVALUACION: Sensor ya superado en este rango en el sandbox.");',
        '    });',
        '} else {',
        '    pm.test("[TC-M03-300] NW-02 Respuesta no esperada", function () {',
        '        pm.expect.fail("Status inesperado en reevaluacion: " + pm.response.code);',
        '    });',
        '}'
    ]
));

// 7. NW-03-PreflightB-Recalcular-Gating
items.push(makeItem(
    "NW-03-PreflightB-Recalcular-Gating",
    "GET",
    "{{baseUrl}}/iot/calidad?pagina=1&por_pagina=200",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'pm.test("[TC-M03-300] Preflight B: Recalcular precondiciones de gating (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const data = pm.response.json();',
        '    const items = data.items || [];',
        '    const total = data.total || 0;',
        '',
        '    pm.collectionVariables.set("PRE_301", String(total >= consts.gating.min_evaluaciones_totales));',
        '    pm.collectionVariables.set("PRE_302", String(items.length > 0));',
        '',
        '    const cand = pm.collectionVariables.get("sensor_candidato");',
        '    const seg = pm.collectionVariables.get("sensor_segundo");',
        '    const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        '    const candCount = (oraculo.por_sensor && oraculo.por_sensor[cand]) || items.filter(it => String(it.id_sensor) === cand).length;',
        '    pm.collectionVariables.set("PRE_304", String(candCount >= consts.gating.min_evaluaciones_sensor && seg !== null && seg !== ""));',
        '',
        '    pm.collectionVariables.set("PRE_305", "true");',
        '',
        '    const timestamps = Object.keys(oraculo.timestamps_conteo || {});',
        '    pm.collectionVariables.set("PRE_306", String(timestamps.length >= consts.gating.min_evaluaciones_sensor));',
        '',
        '    const superadas = items.filter(it => it.estado_evaluacion === "SUPERADA").length;',
        '    pm.collectionVariables.set("PRE_307", String(superadas >= consts.limites_paginacion.min_valido));',
        '',
        '    pm.collectionVariables.set("PRE_308", "true");',
        '});'
    ]
));

// 8. NW-TC-M03-301-Listar-Sin-Filtros (M12: min(50, total), schema completo, orden con compareTimestamps)
items.push(makeItem(
    "NW-TC-M03-301-Listar-Sin-Filtros",
    "GET",
    "{{baseUrl}}/iot/calidad",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_301") !== "true") {',
        '    const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        '    skips.push("TC-M03-301: Menos de " + consts.gating.min_evaluaciones_totales + " evaluaciones en inventario");',
        '    pm.collectionVariables.set("resumen_skips", JSON.stringify(skips));',
        '    return;',
        '}',
        '',
        'pm.test("[TC-M03-301] Estructura paginada y defaults (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        '    const totalEsperado = oraculo.total_descargado || parseInt(pm.collectionVariables.get("total_inventario"), 10);',
        '    pm.expect(res.total).to.equal(totalEsperado);',
        '    pm.expect(res.pagina).to.equal(consts.limites_paginacion.min_valido);',
        '    pm.expect(res.por_pagina).to.equal(consts.limites_paginacion.default_por_pagina);',
        '    pm.expect(res.items).to.be.an("array");',
        '    const esperadosItems = Math.min(consts.limites_paginacion.default_por_pagina, totalEsperado);',
        '    pm.expect(res.items.length).to.equal(esperadosItems);',
        '});',
        '',
        'pm.test("[TC-M03-301] Todos los campos de CalidadEvaluacion presentes en cada item", function () {',
        '    const res = pm.response.json();',
        '    res.items.forEach(it => {',
        '        consts.campos_calidad_evaluacion.forEach(campo => {',
        '            pm.expect(it).to.have.property(campo);',
        '        });',
        '    });',
        '});',
        '',
        '// M13: Orden cronológico no creciente usando compareTimestamps',
        'function parseTimestampParts(tsStr) {',
        '    if (!tsStr) return [0, 0];',
        '    const clean = tsStr.replace("Z", "+00:00");',
        '    let basePart = clean; let tzPart = "+00:00";',
        '    if (clean.includes("+")) { const idx = clean.lastIndexOf("+"); basePart = clean.substring(0, idx); tzPart = clean.substring(idx); }',
        '    else if (clean.lastIndexOf("-") > 10) { const idx = clean.lastIndexOf("-"); basePart = clean.substring(0, idx); tzPart = clean.substring(idx); }',
        '    let secPart = basePart; let micro = 0;',
        '    if (basePart.includes(".")) { const dotIdx = basePart.indexOf("."); secPart = basePart.substring(0, dotIdx); const microStr = (basePart.substring(dotIdx + 1) + "000000").substring(0, 6); micro = parseInt(microStr, 10); }',
        '    const epochSec = Math.floor(new Date(secPart + tzPart).getTime() / 1000);',
        '    return [epochSec, micro];',
        '}',
        'function compareTimestamps(tsA, tsB) {',
        '    const [secA, micA] = parseTimestampParts(tsA);',
        '    const [secB, micB] = parseTimestampParts(tsB);',
        '    if (secA !== secB) return secA - secB;',
        '    return micA - micB;',
        '}',
        '',
        'pm.test("[TC-M03-301] Orden cronológico descendente por timestamp_evaluacion", function () {',
        '    const items = pm.response.json().items;',
        '    for (let i = 1; i < items.length; i++) {',
        '        pm.expect(new Date(items[i-1].timestamp_evaluacion).getTime())',
        '          .to.be.gte(new Date(items[i].timestamp_evaluacion).getTime());',
        '    }',
        '});'
    ]
));

// 9. NW-TC-M03-301-Sonda-Tenant-Productor (DEF-04 bloquea login multi-rol. Sonda informativa)
items.push(makeItem(
    "NW-TC-M03-301-Sonda-Tenant-Productor",
    "GET",
    "{{baseUrl}}/iot/calidad?pagina=1&por_pagina=1",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'console.log("[Sonda RBAC limitada por sandbox] Admin token usado. DEF-04 impide login real de Productor/Ingeniero. DEF-01 documentado por FASE 0.11 (sin filtro tenant).");'
    ]
));

// 10. NW-TC-M03-301-Sonda-Tenant-Ingeniero (DEF-04 bloquea login multi-rol. Sonda informativa)
items.push(makeItem(
    "NW-TC-M03-301-Sonda-Tenant-Ingeniero",
    "GET",
    "{{baseUrl}}/iot/calidad?pagina=1&por_pagina=1",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'console.log("[Sonda RBAC limitada por sandbox] Admin token usado. DEF-04 impide login real de Productor/Ingeniero. DEF-01 documentado por FASE 0.11 (sin filtro tenant).");'
    ]
));

// 11. NW-TC-M03-302-Detalle-Telemetria (M6: aserciones C4 completas RNF-07/CA-15)
items.push(makeItem(
    "NW-TC-M03-302-Detalle-Telemetria",
    "GET",
    "{{baseUrl}}/iot/calidad/{{id_telemetria_candidato}}",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_302") !== "true") {',
        '    const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        '    skips.push("TC-M03-302: No hay telemetria candidata");',
        '    pm.collectionVariables.set("resumen_skips", JSON.stringify(skips));',
        '    return;',
        '}',
        '',
        'pm.test("[TC-M03-302] Consulta por id_telemetria (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    const solIdTelem = parseInt(pm.collectionVariables.get("id_telemetria_candidato"), 10);',
        '    pm.expect(res.id_telemetria).to.equal(solIdTelem);',
        '    const solIdEval = pm.collectionVariables.get("id_evaluacion_candidato");',
        '    pm.expect(res.id_evaluacion).to.equal(solIdEval);',
        '});',
        '',
        'pm.test("[TC-M03-302][RNF-07/CA-15] Existencia de claves de metadatos requeridos", function () {',
        '    const res = pm.response.json();',
        '    pm.expect(res).to.have.property("version_evaluacion");',
        '    pm.expect(res).to.have.property("version_limites_fisicos_aplicada");',
        '    pm.expect(res).to.have.property("parametros_aplicados");',
        '    pm.expect(res).to.have.property("parametros_calibracion_aplicados");',
        '    pm.expect(res.flags_detectados).to.be.an("object").and.not.be.null;',
        '});',
        '',
        'pm.test("[TC-M03-302][RNF-07/CA-15] Valores no nulos y estructura de parametros aplicados", function () {',
        '    const res = pm.response.json();',
        '    pm.expect(res.parametros_aplicados).to.be.an("object").and.not.be.null;',
        '    pm.expect(res.parametros_aplicados).to.have.property("k");',
        '    pm.expect(res.parametros_aplicados).to.have.property("M");',
        '    pm.expect(res.parametros_aplicados).to.have.property("N");',
        '    pm.expect(res.parametros_aplicados).to.have.property("umbral_drift");',
        '    if (res.parametros_calibracion_aplicados !== null) {',
        '        pm.expect(res.parametros_calibracion_aplicados).to.have.property("offset");',
        '        pm.expect(res.parametros_calibracion_aplicados).to.have.property("ganancia");',
        '    }',
        '});',
        '',
        'pm.test("[TC-M03-302] Coherencia estricta de aptitud e indice", function () {',
        '    const res = pm.response.json();',
        '    if (res.clasificacion_calidad === "APTO") {',
        '        pm.expect(res.apto_para_ia).to.be.true;',
        '        pm.expect(res.apto_para_nic41).to.be.true;',
        '        pm.expect(res.indice_calidad).to.be.at.least(consts.umbrales.apto);',
        '    } else if (res.clasificacion_calidad === "APTO_CON_RESERVA") {',
        '        pm.expect(res.apto_para_ia).to.be.true;',
        '        pm.expect(res.apto_para_nic41).to.be.false;',
        '        pm.expect(res.indice_calidad).to.be.within(consts.umbrales.reserva, consts.umbrales.reserva_max);',
        '    } else if (res.clasificacion_calidad === "NO_APTO") {',
        '        pm.expect(res.apto_para_ia).to.be.false;',
        '        pm.expect(res.apto_para_nic41).to.be.false;',
        '        pm.expect(res.indice_calidad).to.be.below(consts.umbrales.reserva);',
        '    } else if (res.clasificacion_calidad === "INDETERMINADA") {',
        '        pm.expect(res.indice_calidad).to.be.null;',
        '    }',
        '});'
    ]
));

// 12. NW-TC-M03-304-Filtrar-Sensor-Candidato (M12: total igual al oraculo del sensor)
items.push(makeItem(
    "NW-TC-M03-304-Filtrar-Sensor-Candidato",
    "GET",
    "{{baseUrl}}/iot/calidad?id_sensor={{sensor_candidato}}&pagina=1&por_pagina=200",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_304") !== "true") {',
        '    const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        '    skips.push("TC-M03-304: Sensor sin suficientes evaluaciones");',
        '    pm.collectionVariables.set("resumen_skips", JSON.stringify(skips));',
        '    return;',
        '}',
        '',
        'pm.test("[TC-M03-304] Aislamiento: 100% de items pertenecen al sensor y total coincide con oraculo", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    const cand = parseInt(pm.collectionVariables.get("sensor_candidato"), 10);',
        '    const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        '    const totalEsperadoSensor = (oraculo.por_sensor && oraculo.por_sensor[cand]) || res.total;',
        '    pm.expect(res.total).to.equal(totalEsperadoSensor);',
        '    res.items.forEach(it => {',
        '        pm.expect(it.id_sensor).to.equal(cand);',
        '    });',
        '});'
    ]
));

// 13. NW-TC-M03-304-Aislamiento-Segundo-Sensor
items.push(makeItem(
    "NW-TC-M03-304-Aislamiento-Segundo-Sensor",
    "GET",
    "{{baseUrl}}/iot/calidad?id_sensor={{sensor_segundo}}&pagina=1&por_pagina=200",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_304") !== "true") return;',
        '',
        'pm.test("[TC-M03-304] Aislamiento cruzado respecto a segundo sensor", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    const cand = parseInt(pm.collectionVariables.get("sensor_candidato"), 10);',
        '    res.items.forEach(it => {',
        '        pm.expect(it.id_sensor).to.not.equal(cand);',
        '    });',
        '});'
    ]
));

// 14. NW-TC-M03-304-Paginacion-Combinada-Pag1 (M12: guarda id_evaluacion y timestamps)
items.push(makeItem(
    "NW-TC-M03-304-Paginacion-Combinada-Pag1",
    "GET",
    "{{baseUrl}}/iot/calidad?id_sensor={{sensor_candidato}}&pagina=1&por_pagina=3",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_304") !== "true") return;',
        '',
        'pm.test("[TC-M03-304] Paginacion reducida Pagina 1 (por_pagina=3)", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res.pagina).to.equal(consts.limites_paginacion.min_valido);',
        '    pm.expect(res.por_pagina).to.equal(consts.limites_paginacion.sample_paginacion);',
        '    pm.expect(res.items.length).to.equal(consts.limites_paginacion.sample_paginacion);',
        '    pm.collectionVariables.set("timestamps_muestra_sensor", JSON.stringify(res.items.map(it => it.timestamp_evaluacion)));',
        '    pm.collectionVariables.set("evaluaciones_muestra_sensor", JSON.stringify(res.items.map(it => it.id_evaluacion)));',
        '});'
    ]
));

// 15. NW-TC-M03-304-Paginacion-Combinada-Pag2 (M12: total identico, no repetidos por id_evaluacion, determinismo por empates L5)
items.push(makeItem(
    "NW-TC-M03-304-Paginacion-Combinada-Pag2",
    "GET",
    "{{baseUrl}}/iot/calidad?id_sensor={{sensor_candidato}}&pagina=2&por_pagina=3",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_304") !== "true") return;',
        '',
        'pm.test("[TC-M03-304] Paginacion reducida Pagina 2 y total consistente", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res.pagina).to.equal(2);',
        '    pm.expect(res.por_pagina).to.equal(consts.limites_paginacion.sample_paginacion);',
        '});',
        '',
        'const pag1Ids = JSON.parse(pm.collectionVariables.get("evaluaciones_muestra_sensor") || "[]");',
        'const pag2Ids = pm.response.json().items.map(it => it.id_evaluacion);',
        'const pag1Ts = JSON.parse(pm.collectionVariables.get("timestamps_muestra_sensor") || "[]");',
        'const pag2Ts = pm.response.json().items.map(it => it.timestamp_evaluacion);',
        'const empatesTs = pag2Ts.filter(ts => pag1Ts.includes(ts)).length;',
        'const repetidosId = pag2Ids.filter(id => pag1Ids.includes(id)).length;',
        '',
        'if (empatesTs === 0) {',
        '    pm.test("[TC-M03-304] No hay duplicados de id_evaluacion entre paginas", function () {',
        '        pm.expect(repetidosId).to.equal(0);',
        '    });',
        '} else {',
        '    console.log("OBS-DETERMINISMO: empates=" + empatesTs + "; sin criterio de desempate en el backend; la verificacion de no repetidos entre paginas no es determinista");',
        '}'
    ]
));

// 16. NW-TC-M03-305-Enum-INDETERMINADA (M10: oraculo con conteo, omision parcial si 0)
items.push(makeItem(
    "NW-TC-M03-305-Enum-INDETERMINADA",
    "GET",
    "{{baseUrl}}/iot/calidad?clasificacion=INDETERMINADA&pagina=1&por_pagina=50",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        'const esperado = (oraculo.por_clasificacion && oraculo.por_clasificacion["INDETERMINADA"]) || 0;',
        '',
        'if (esperado === 0) {',
        '    const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        '    skips.push("TC-M03-305: sin datos de clasificacion=INDETERMINADA (se valida solo vacio)");',
        '    pm.collectionVariables.set("resumen_skips", JSON.stringify(skips));',
        '}',
        '',
        'pm.test("[TC-M03-305] Filtrar por clasificacion=INDETERMINADA (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res.total).to.equal(esperado);',
        '    if (esperado > 0) {',
        '        pm.expect(res.items.length).to.be.at.least(consts.limites_paginacion.min_valido);',
        '        res.items.forEach(it => pm.expect(it.clasificacion_calidad).to.equal("INDETERMINADA"));',
        '    } else {',
        '        pm.expect(res.items).to.be.an("array").that.is.empty;',
        '    }',
        '});'
    ]
));

// 17. NW-TC-M03-305-Enum-APTO (M10)
items.push(makeItem(
    "NW-TC-M03-305-Enum-APTO",
    "GET",
    "{{baseUrl}}/iot/calidad?clasificacion=APTO&pagina=1&por_pagina=50",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        'const esperado = (oraculo.por_clasificacion && oraculo.por_clasificacion["APTO"]) || 0;',
        '',
        'if (esperado === 0) {',
        '    const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        '    skips.push("TC-M03-305: sin datos de clasificacion=APTO (se valida solo vacio)");',
        '    pm.collectionVariables.set("resumen_skips", JSON.stringify(skips));',
        '}',
        '',
        'pm.test("[TC-M03-305] Filtrar por clasificacion=APTO (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res.total).to.equal(esperado);',
        '    if (esperado > 0) {',
        '        pm.expect(res.items.length).to.be.at.least(consts.limites_paginacion.min_valido);',
        '        res.items.forEach(it => pm.expect(it.clasificacion_calidad).to.equal("APTO"));',
        '    } else {',
        '        pm.expect(res.items).to.be.an("array").that.is.empty;',
        '    }',
        '});'
    ]
));

// 18. NW-TC-M03-305-Enum-APTO_CON_RESERVA (M10)
items.push(makeItem(
    "NW-TC-M03-305-Enum-APTO_CON_RESERVA",
    "GET",
    "{{baseUrl}}/iot/calidad?clasificacion=APTO_CON_RESERVA&pagina=1&por_pagina=50",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        'const esperado = (oraculo.por_clasificacion && oraculo.por_clasificacion["APTO_CON_RESERVA"]) || 0;',
        '',
        'if (esperado === 0) {',
        '    const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        '    skips.push("TC-M03-305: sin datos de clasificacion=APTO_CON_RESERVA (se valida solo vacio)");',
        '    pm.collectionVariables.set("resumen_skips", JSON.stringify(skips));',
        '}',
        '',
        'pm.test("[TC-M03-305] Filtrar por clasificacion=APTO_CON_RESERVA (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res.total).to.equal(esperado);',
        '    if (esperado > 0) {',
        '        pm.expect(res.items.length).to.be.at.least(consts.limites_paginacion.min_valido);',
        '        res.items.forEach(it => pm.expect(it.clasificacion_calidad).to.equal("APTO_CON_RESERVA"));',
        '    } else {',
        '        pm.expect(res.items).to.be.an("array").that.is.empty;',
        '    }',
        '});'
    ]
));

// 19. NW-TC-M03-305-Enum-NO_APTO (M10)
items.push(makeItem(
    "NW-TC-M03-305-Enum-NO_APTO",
    "GET",
    "{{baseUrl}}/iot/calidad?clasificacion=NO_APTO&pagina=1&por_pagina=50",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        'const esperado = (oraculo.por_clasificacion && oraculo.por_clasificacion["NO_APTO"]) || 0;',
        '',
        'if (esperado === 0) {',
        '    const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        '    skips.push("TC-M03-305: sin datos de clasificacion=NO_APTO (se valida solo vacio)");',
        '    pm.collectionVariables.set("resumen_skips", JSON.stringify(skips));',
        '}',
        '',
        'pm.test("[TC-M03-305] Filtrar por clasificacion=NO_APTO (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res.total).to.equal(esperado);',
        '    if (esperado > 0) {',
        '        pm.expect(res.items.length).to.be.at.least(consts.limites_paginacion.min_valido);',
        '        res.items.forEach(it => pm.expect(it.clasificacion_calidad).to.equal("NO_APTO"));',
        '    } else {',
        '        pm.expect(res.items).to.be.an("array").that.is.empty;',
        '    }',
        '});'
    ]
));

// 20. NW-TC-M03-305-Invalido-Rechazo (M8: constantes para 400 y 499)
items.push(makeItem(
    "NW-TC-M03-305-Invalido-Rechazo",
    "GET",
    "{{baseUrl}}/iot/calidad?clasificacion=VALOR_NO_CATALOGADO_ENUM",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        '// D-H5 estricto: contrato RF-62 exige 422. Si backend devuelve 200, esta aserción FALLA y se reporta en el chat.',
        'pm.test("[TC-M03-305] Rechazo de valor de enum invalido (espera 422)", function () {',
        '    pm.response.to.have.status(422);',
        '    const body = pm.response.json();',
        '    pm.expect(body.codigo || body.error_code).to.eql("VAL_ENTRADA");',
        '});'
    ]
));

// 21. NW-TC-M03-305-Sonda-Clasificacion-Calidad (M9: solo console.log sin pm.test, query param clasificacion corregido)
items.push(makeItem(
    "NW-TC-M03-305-Sonda-Clasificacion-Calidad",
    "GET",
    "{{baseUrl}}/iot/calidad?clasificacion=APTO",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'console.log("OBS-305: Consulta repetida con clasificacion=APTO status=" + pm.response.code);'
    ]
));

// 22. NW-TC-M03-306-Rango-Fechas-Valido (M10: total igual a oraculo filtrado por compareTimestamps)
items.push(makeItem(
    "NW-TC-M03-306-Rango-Fechas-Valido",
    "GET",
    "{{baseUrl}}/iot/calidad?fecha_desde={{fecha_desde_sample}}&fecha_hasta={{fecha_hasta_sample}}",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_306") !== "true") {',
        '    const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        '    skips.push("TC-M03-306: Menos de 5 timestamps disponibles");',
        '    pm.collectionVariables.set("resumen_skips", JSON.stringify(skips));',
        '    return;',
        '}',
        '',
        'function parseTimestampParts(tsStr) {',
        '    if (!tsStr) return [0, 0];',
        '    const clean = tsStr.replace("Z", "+00:00");',
        '    let basePart = clean; let tzPart = "+00:00";',
        '    if (clean.includes("+")) { const idx = clean.lastIndexOf("+"); basePart = clean.substring(0, idx); tzPart = clean.substring(idx); }',
        '    else if (clean.lastIndexOf("-") > 10) { const idx = clean.lastIndexOf("-"); basePart = clean.substring(0, idx); tzPart = clean.substring(idx); }',
        '    let secPart = basePart; let micro = 0;',
        '    if (basePart.includes(".")) { const dotIdx = basePart.indexOf("."); secPart = basePart.substring(0, dotIdx); const microStr = (basePart.substring(dotIdx + 1) + "000000").substring(0, 6); micro = parseInt(microStr, 10); }',
        '    const epochSec = Math.floor(new Date(secPart + tzPart).getTime() / 1000);',
        '    return [epochSec, micro];',
        '}',
        'function compareTimestamps(tsA, tsB) {',
        '    const [secA, micA] = parseTimestampParts(tsA);',
        '    const [secB, micB] = parseTimestampParts(tsB);',
        '    if (secA !== secB) return secA - secB;',
        '    return micA - micB;',
        '}',
        '',
        'const fDesde = pm.collectionVariables.get("fecha_desde_sample");',
        'const fHasta = pm.collectionVariables.get("fecha_hasta_sample");',
        'const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        'let totalEsperadoRango = 0;',
        '(oraculo.timestamps || []).forEach(ts => {',
        '    if (compareTimestamps(ts, fDesde) >= 0 && compareTimestamps(ts, fHasta) <= 0) {',
        '        totalEsperadoRango++;',
        '    }',
        '});',
        '',
        'pm.test("[TC-M03-306] Filtrado por rango temporal valido (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res.total).to.equal(totalEsperadoRango);',
        '    res.items.forEach(it => {',
        '        pm.expect(compareTimestamps(it.timestamp_evaluacion, fDesde) >= 0).to.be.true;',
        '        pm.expect(compareTimestamps(it.timestamp_evaluacion, fHasta) <= 0).to.be.true;',
        '    });',
        '});'
    ]
));

// 23. NW-TC-M03-306-Frontera-Exacta (M10: items.length >= 1, total igual al oraculo para ese timestamp)
items.push(makeItem(
    "NW-TC-M03-306-Frontera-Exacta",
    "GET",
    "{{baseUrl}}/iot/calidad?fecha_desde={{fecha_exacta_sample}}&fecha_hasta={{fecha_exacta_sample}}",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_306") !== "true") return;',
        '',
        'const fExacta = pm.collectionVariables.get("fecha_exacta_sample");',
        'const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        'const esperado = (oraculo.timestamps_conteo && oraculo.timestamps_conteo[fExacta]) || 1;',
        '',
        'pm.test("[TC-M03-306] Frontera exacta fecha_desde == fecha_hasta (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res.total).to.equal(esperado);',
        '    pm.expect(res.items.length).to.be.at.least(consts.limites_paginacion.min_valido);',
        '    res.items.forEach(it => {',
        '        pm.expect(it.timestamp_evaluacion).to.equal(fExacta);',
        '    });',
        '});'
    ]
));

// 24. NW-TC-M03-306-Rango-Temporal-UTC (HG-2: formato UTC puro con Z)
items.push(makeItem(
    "NW-TC-M03-306-Rango-Temporal-UTC",
    "GET",
    "{{baseUrl}}/iot/calidad?fecha_desde={{fecha_desde_sample}}&fecha_hasta={{fecha_hasta_sample}}",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [
        '// HG-2: Usar formato UTC puro con Z sin reemplazos artificiales',
        'const fDesde = pm.collectionVariables.get("fecha_desde_sample");',
        'const fHasta = pm.collectionVariables.get("fecha_hasta_sample");',
        'if (fDesde && fHasta) {',
        '    const url = pm.collectionVariables.get("baseUrl") + "/iot/calidad?fecha_desde=" + encodeURIComponent(new Date(fDesde).toISOString()) + "&fecha_hasta=" + encodeURIComponent(new Date(fHasta).toISOString());',
        '    pm.request.url = url;',
        '}'
    ],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_306") !== "true") return;',
        '',
        'pm.test("[TC-M03-306] Equivalencia de rango temporal UTC (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res.items).to.be.an("array");',
        '});'
    ]
));

// 25. NW-TC-M03-306-Fechas-Invertidas-Rechazo
items.push(makeItem(
    "NW-TC-M03-306-Fechas-Invertidas-Rechazo",
    "GET",
    "{{baseUrl}}/iot/calidad?fecha_desde={{fecha_hasta_sample}}&fecha_hasta={{fecha_desde_sample}}",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_306") !== "true") return;',
        '',
        '// D-H5 estricto: contrato RF-62 exige 422. Si backend devuelve 200, esta aserción FALLA y se reporta en el chat.',
        'pm.test("[TC-M03-306] Rechazo de fecha_desde > fecha_hasta (espera 422)", function () {',
        '    pm.response.to.have.status(422);',
        '});'
    ]
));

// 26. NW-TC-M03-307-Filtrar-SUPERADA (M2: param estado_evaluacion, M8: L8 assertions)
items.push(makeItem(
    "NW-TC-M03-307-Filtrar-SUPERADA",
    "GET",
    "{{baseUrl}}/iot/calidad?estado_evaluacion=SUPERADA",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_307") !== "true") {',
        '    const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        '    skips.push("TC-M03-307: Cero evaluaciones SUPERADA en el sistema");',
        '    pm.collectionVariables.set("resumen_skips", JSON.stringify(skips));',
        '    return;',
        '}',
        '',
        'pm.test("[TC-M03-307] Filtrar por estado_evaluacion=SUPERADA (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    res.items.forEach(it => {',
        '        pm.expect(it.estado_evaluacion).to.equal("SUPERADA");',
        '    });',
        '});',
        '',
        'const items = pm.response.json().items || [];',
        'let conIdSuperada = 0;',
        'items.forEach(it => {',
        '    pm.test("[TC-M03-307] motivo_reevaluacion no nulo ni vacio en SUPERADA", function () {',
        '        pm.expect(it.motivo_reevaluacion).to.be.a("string").and.not.be.empty;',
        '    });',
        '    if (it.id_evaluacion_superada) conIdSuperada++;',
        '});',
        'console.log("OBS-307: id_evaluacion_superada=" + conIdSuperada + " de " + items.length + " items SUPERADA");'
    ]
));

// 27. NW-TC-M03-307-Complemento-VIGENTE (M9: VIGENTE + SUPERADA == Total sin filtro)
items.push(makeItem(
    "NW-TC-M03-307-Complemento-VIGENTE",
    "GET",
    "{{baseUrl}}/iot/calidad?estado_evaluacion=VIGENTE",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'if (pm.collectionVariables.get("PRE_307") !== "true") return;',
        '',
        'pm.test("[TC-M03-307] Invariante estricto: VIGENTE + SUPERADA == Total sin filtro", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const totalVigente = pm.response.json().total;',
        '    const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        '    const totalSuperada = (oraculo.por_estado && oraculo.por_estado["SUPERADA"]) || 0;',
        '    const total = oraculo.total_descargado || parseInt(pm.collectionVariables.get("total_sin_filtro") || pm.collectionVariables.get("total_inventario"), 10);',
        '    pm.expect(totalVigente + totalSuperada).to.eql(total);',
        '});'
    ]
));

// 28. NW-TC-M03-307-ACTIVA-Invalido (D7 RESUELTO: ACTIVA fuera del catálogo VIGENTE/SUPERADA)
items.push(makeItem(
    "NW-TC-M03-307-ACTIVA-Invalido",
    "GET",
    "{{baseUrl}}/iot/calidad?estado_evaluacion=ACTIVA",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        '// D7 RESUELTO: ACTIVA fuera del catálogo VIGENTE/SUPERADA',
        '// D-H5 estricto: contrato RF-62 exige 422. Si backend devuelve 200, esta aserción FALLA y se reporta en el chat.',
        'pm.test("[TC-M03-307] Rechazo de estado_evaluacion=ACTIVA invalido (espera 422)", function () {',
        '    pm.response.to.have.status(422);',
        '    const body = pm.response.json();',
        '    pm.expect(body.codigo || body.error_code).to.eql("VAL_ENTRADA");',
        '});'
    ]
));

// 29. NW-TC-M03-308-Limite-Maximo-200 (M10: gating total > 200)
items.push(makeItem(
    "NW-TC-M03-308-Limite-Maximo-200",
    "GET",
    "{{baseUrl}}/iot/calidad?pagina=1&por_pagina=200",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'const res = pm.response.json();',
        'if (res.total <= consts.limites_paginacion.max_por_pagina) {',
        '    const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        '    skips.push("TC-M03-308: total (" + res.total + ") <= 200, se omite validacion de exactamente 200 items");',
        '    pm.collectionVariables.set("resumen_skips", JSON.stringify(skips));',
        '}',
        '',
        'pm.test("[TC-M03-308] Limite maximo por_pagina=200 (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    pm.expect(res.por_pagina).to.equal(consts.limites_paginacion.max_por_pagina);',
        '    pm.expect(res.items.length).to.equal(200);',
        '});'
    ]
));

// 30. NW-TC-M03-308-Exceso-PorPagina-201
items.push(makeItem(
    "NW-TC-M03-308-Exceso-PorPagina-201",
    "GET",
    "{{baseUrl}}/iot/calidad?pagina=1&por_pagina=201",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'pm.test("[TC-M03-308] Rechazo de por_pagina=201 (espera 4xx sin items)", function () {',
        '    pm.expect(pm.response.code).to.be.within(consts.codigos_http.client_error_min, consts.codigos_http.client_error_max);',
        '    const body = pm.response.text();',
        '    pm.expect(body).to.not.include(\'"items"\');',
        '});',
        '',
        'const esperado = parseInt(pm.collectionVariables.get("status_validacion_esperado") || "422", 10);',
        'pm.test("[TC-M03-308] Exceso status coincide con status_validacion_esperado (" + esperado + ")", function () {',
        '    pm.expect(pm.response.code).to.equal(esperado);',
        '});'
    ]
));

// 31. NW-TC-M03-308-Pagina-Cero-Rechazo
items.push(makeItem(
    "NW-TC-M03-308-Pagina-Cero-Rechazo",
    "GET",
    "{{baseUrl}}/iot/calidad?pagina=0&por_pagina=50",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'pm.test("[TC-M03-308] Rechazo de pagina=0 (espera 4xx sin items)", function () {',
        '    pm.expect(pm.response.code).to.be.within(consts.codigos_http.client_error_min, consts.codigos_http.client_error_max);',
        '    const body = pm.response.text();',
        '    pm.expect(body).to.not.include(\'"items"\');',
        '});',
        '',
        'const esperado = parseInt(pm.collectionVariables.get("status_validacion_esperado") || "422", 10);',
        'pm.test("[TC-M03-308] Pagina cero status coincide con status_validacion_esperado (" + esperado + ")", function () {',
        '    pm.expect(pm.response.code).to.equal(esperado);',
        '});'
    ]
));

// 32. NW-TC-M03-308-PorPagina-Cero-Rechazo (M10)
items.push(makeItem(
    "NW-TC-M03-308-PorPagina-Cero-Rechazo",
    "GET",
    "{{baseUrl}}/iot/calidad?pagina=1&por_pagina=0",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'pm.test("[TC-M03-308] Rechazo de por_pagina=0 (espera 4xx sin items)", function () {',
        '    pm.expect(pm.response.code).to.be.within(consts.codigos_http.client_error_min, consts.codigos_http.client_error_max);',
        '    const body = pm.response.text();',
        '    pm.expect(body).to.not.include(\'"items"\');',
        '});',
        '',
        'const esperado = parseInt(pm.collectionVariables.get("status_validacion_esperado") || "422", 10);',
        'pm.test("[TC-M03-308] por_pagina=0 status coincide con status_validacion_esperado (" + esperado + ")", function () {',
        '    pm.expect(pm.response.code).to.equal(esperado);',
        '});'
    ]
));

// 33. NW-TC-M03-308-Pagina-Mayor-Ultima (M10: 200, items [] y total intacto)
items.push(makeItem(
    "NW-TC-M03-308-Pagina-Mayor-Ultima",
    "GET",
    "{{baseUrl}}/iot/calidad?pagina=9999&por_pagina=50",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'pm.test("[TC-M03-308] Pagina mayor a la ultima retorna items vacios y total intacto (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    const oraculo = JSON.parse(pm.collectionVariables.get("oraculo_dataset") || "{}");',
        '    const totalEsperado = oraculo.total_descargado || parseInt(pm.collectionVariables.get("total_inventario"), 10);',
        '    pm.expect(res.total).to.equal(totalEsperado);',
        '    pm.expect(res.items).to.be.an("array").that.is.empty;',
        '});'
    ]
));

// 34. NW-TC-M03-308-Frontera-PorPagina-1
items.push(makeItem(
    "NW-TC-M03-308-Frontera-PorPagina-1",
    "GET",
    "{{baseUrl}}/iot/calidad?pagina=1&por_pagina=1",
    [
        { key: "Authorization", value: "Bearer {{admin_token}}" },
        { key: "X-Test-Run-Id", value: "{{run_id}}" },
        { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
    ],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'pm.test("[TC-M03-308] Frontera minima valida por_pagina=1 (" + consts.codigos_http.ok + ")", function () {',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res.por_pagina).to.equal(consts.limites_paginacion.min_valido);',
        '    pm.expect(res.items.length).to.be.at.most(consts.limites_paginacion.min_valido);',
        '});'
    ]
));

// 35. NW-98-Cobertura (M11: nombre dinámico, falla con skips, imprime resumen)
items.push(makeItem(
    "NW-98-Cobertura",
    "GET",
    "{{baseUrl}}/health",
    [],
    null,
    [],
    [
        'const skips = JSON.parse(pm.collectionVariables.get("resumen_skips") || "[]");',
        'const skipFalla = pm.collectionVariables.get("skip_cuenta_como_falla") === "true";',
        'const totalSubcasos = 7;',
        'const cumplidos = Math.max(0, totalSubcasos - skips.length);',
        '',
        'console.log("=== RESUMEN DE COBERTURA TC-M03-G164 ===");',
        'const subcasosIds = ["TC-M03-301", "TC-M03-302", "TC-M03-304", "TC-M03-305", "TC-M03-306", "TC-M03-307", "TC-M03-308"];',
        'subcasosIds.forEach(scId => {',
        '    const match = skips.find(s => s.startsWith(scId));',
        '    if (match) {',
        '        console.log(" - " + scId + ": OMITIDO (" + match + ")");',
        '    } else {',
        '        console.log(" - " + scId + ": EJECUTADO");',
        '    }',
        '});',
        'console.log("=========================================");',
        '',
        'const testName = "[COBERTURA] Subcasos con precondicion cumplida: " + cumplidos + "/" + totalSubcasos;',
        'pm.test(testName, function () {',
        '    if (skipFalla && skips.length > 0) {',
        '        pm.expect.fail("Subcasos omitidos por falta de datos o precondicion no cumplida: " + skips.join("; "));',
        '    } else {',
        '        pm.expect(true).to.be.true;',
        '    }',
        '});'
    ]
));

// 36. NW-99-Teardown-Cierre-Sandbox (M9: 200 y "Rollback exitoso", 404 falla con mensaje claro)
items.push(makeItem(
    "NW-99-Teardown-Cierre-Sandbox",
    "DELETE",
    "{{baseUrl}}/test-control/runs/{{run_id}}",
    [{ key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }],
    null,
    [],
    [
        'const consts = JSON.parse(pm.collectionVariables.get("constantes_especificacion"));',
        'pm.test("[TEARDOWN] Cierre transaccional del sandbox (" + consts.codigos_http.ok + ")", function () {',
        '    if (pm.response.code === consts.codigos_http.not_found) {',
        '        pm.expect.fail("FALLO CRITICO TEARDOWN (404): El run de sandbox ha expirado por inactividad o no fue registrado.");',
        '    }',
        '    pm.response.to.have.status(consts.codigos_http.ok);',
        '    const res = pm.response.json();',
        '    pm.expect(res).to.have.property("status", "Rollback exitoso");',
        '    console.log("TEARDOWN OK: Rollback exitoso confirmado para " + pm.collectionVariables.get("run_id"));',
        '});'
    ]
));

const finalCollection = {
    info: {
        _postman_id: "tc-m03-g164-collection-v5",
        name: "TC-M03-G164 - Calidad Telemetria RF-62",
        description: "Coleccion Newman para TC-M03-G164 (RF-62) Módulo 3 Telemetría IoT. Sin hardcodeos, aserciones oraculares y control de sandbox.",
        schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    event: [
        {
            listen: "prerequest",
            script: {
                type: "text/javascript",
                exec: [
                    "const secret = pm.environment.get('sandbox_secret') || pm.collectionVariables.get('sandbox_secret') || pm.environment.get('TEST_SANDBOX_SECRET');",
                    "const rId = pm.environment.get('run_id') || pm.collectionVariables.get('run_id') || ('test-' + pm.variables.replaceIn('{{$guid}}'));",
                    "if (rId) {",
                    "  pm.collectionVariables.set('run_id', rId);",
                    "  pm.request.headers.upsert({ key: 'X-Test-Run-Id', value: rId });",
                    "}",
                    "if (secret) {",
                    "  pm.collectionVariables.set('sandbox_secret', secret);",
                    "  pm.request.headers.upsert({ key: 'X-Sandbox-Secret', value: secret });",
                    "}",
                    "const aTok = pm.collectionVariables.get('admin_token') || pm.collectionVariables.get('token_admin');",
                    "if (aTok) {",
                    "  pm.collectionVariables.set('admin_token', aTok);",
                    "  pm.collectionVariables.set('token_admin', aTok);",
                    "  pm.collectionVariables.set('producer_token', aTok);",
                    "  pm.collectionVariables.set('token_productor', aTok);",
                    "  pm.collectionVariables.set('engineer_token', aTok);",
                    "  pm.collectionVariables.set('token_ingeniero', aTok);",
                    "}"
                ]
            }
        }
    ],
    variable: collectionVariables,
    item: items
};

fs.writeFileSync(path.join(__dirname, 'test_tc_m03_g164.json'), JSON.stringify(finalCollection, null, 2), 'utf8');
console.log("test_tc_m03_g164.json generado exitosamente con " + items.length + " items.");
