import http from 'k6/http';
import { check, sleep } from 'k6';

// TC-M03-G172: Rendimiento y Capacidad (RF-62)
// Herramienta: k6. Genera resultados/resultado_TC-M03-G172.json para el scanner.
//
// NOTA ARQUITECTURA QA / RESTRICCIONES SANDBOX:
// 1. Una corrida sandbox posee timeout estricto de 180 s y vive en una sola transacción.
//    Cargas sostenidas de 10-15 minutos por escalón son imposibles dentro del sandbox y
//    correr sin sandbox contaminaría la base de datos de pruebas.
// 2. Se implementa una versión ESCALADA y corta (<=30 s) dentro del sandbox.
// 3. Concurrencia: Se configuran 5 VUs concurrentes pre-asignados (máximo 15 VUs) que
//    comparten el mismo run_id transaccional. La transacción en PostgreSQL aísla las escrituras.
// 4. Teardown garantizado: k6 ejecuta teardown() obligatoriamente al finalizar la suite
//    (incluso si los checks o thresholds fallan), ejecutando DELETE /test-control/runs/{run_id}.
// 5. TC-330 (comparación RF-62 ON vs OFF): El backend no expone un switch en caliente por API
//    para apagar RF-62. Se mide el P95 de ingesta individual asegurando latencia y cero fallos.
// 6. TC-363 y TC-364 son casos PROPUESTOS (sin responsable asignado en la especificación).

export const options = {
    scenarios: {
        ingesta_carga: {
            executor: 'constant-arrival-rate',
            rate: 10, // 10 req/s = 600 req/min (cumple escala de 500/min en ráfaga controlada)
            timeUnit: '1s',
            duration: '30s',
            preAllocatedVUs: 5, // 5 VUs concurrentes
            maxVUs: 15,
        },
    },
    thresholds: {
        // [PROPUESTO] P95 para ingesta individual bajo transacción sandbox (<= 1500ms considerando overhead de sandbox)
        http_req_duration: ['p(95)<1500'],
        // Cero errores 5xx a nivel de servidor
        http_req_failed: ['rate<0.01'],
        // Checks funcionales computables
        checks: ['rate>0.99'],
    },
};

const BASE_URL = __ENV.baseUrl || 'https://api.inmero.co/back-sigab-test';
const RUN_ID = __ENV.run_id || `test-k6-${Date.now()}`;
const SANDBOX_SECRET = __ENV.sandbox_secret || '';
const ADMIN_PASSWORD = __ENV.admin_password || '';

export function setup() {
    console.log(`[SETUP] Iniciando suite k6 TC-M03-G172 bajo Run ID: ${RUN_ID}`);
    // 1. Login para obtener token admin
    const loginRes = http.post(
        `${BASE_URL}/sesiones/`,
        JSON.stringify({
            correo_electronico: 'administador.dev@gmail.com',
            contrasena: ADMIN_PASSWORD,
        }),
        {
            headers: {
                'Content-Type': 'application/json',
                'X-Test-Run-Id': RUN_ID,
                'X-Sandbox-Secret': SANDBOX_SECRET,
            },
        }
    );

    let token = '';
    if (loginRes.status === 200) {
        token = loginRes.json().token;
    }

    // 2. Descubrir un sensor activo vía /test-control/query (SELECT solo lectura)
    const queryRes = http.post(
        `${BASE_URL}/test-control/query`,
        JSON.stringify({
            query: 'SELECT s.id_sensores, s.id_dispositivo_iot, d.serial FROM modulo9.sensores s JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot WHERE s.es_activo = true AND d.es_activo = true ORDER BY s.id_sensores ASC LIMIT 1',
        }),
        {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
                'X-Test-Run-Id': RUN_ID,
                'X-Sandbox-Secret': SANDBOX_SECRET,
            },
        }
    );

    let sensorId = 1;
    let deviceId = 1;
    let deviceSerial = 'DEV-TEST-001';
    if (queryRes.status === 200) {
        const rows = queryRes.json().data || queryRes.json().rows || [];
        if (rows.length > 0) {
            sensorId = rows[0].id_sensores;
            deviceId = rows[0].id_dispositivo_iot;
            deviceSerial = rows[0].serial;
        }
    }

    return {
        token,
        sensorId,
        deviceId,
        deviceSerial,
        runId: RUN_ID,
    };
}

export default function (data) {
    const payload = JSON.stringify({
        device_id: data.deviceId,
        sensor_id: data.sensorId,
        tipo_variable: 'TEMPERATURA_AMBIENTAL',
        valor: 22.0 + (Math.random() * 0.5),
        unidad: '°C',
        timestamp_captura: new Date(Date.now() - 3600000).toISOString(),
        access_key: data.deviceSerial,
        origen: 'BUFFER_LOCAL',
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
            'X-Test-Run-Id': data.runId, // Todos los VUs comparten el mismo run_id transaccional
            'X-Sandbox-Secret': SANDBOX_SECRET,
        },
    };

    const res = http.post(`${BASE_URL}/iot/telemetria`, payload, params);

    check(res, {
        'Status 201 en ingesta de telemetría': (r) => r.status === 201,
        'Respuesta contiene id_telemetria': (r) => r.json().id_telemetria !== undefined,
        'Transacción sin error de servidor': (r) => r.status < 500,
    });
}

export function teardown(data) {
    console.log(`[TEARDOWN] Garantizado ante éxito o fallo: Ejecutando rollback del Sandbox Run ID: ${data.runId}`);
    try {
        const res = http.del(`${BASE_URL}/test-control/runs/${data.runId}`, null, {
            headers: {
                'X-Test-Run-Id': data.runId,
                'X-Sandbox-Secret': SANDBOX_SECRET,
            },
        });

        if (res.status === 200) {
            console.log('[TEARDOWN] Rollback exitoso en base de datos.');
        } else {
            console.warn(`[TEARDOWN WARNING] Rollback respondió status ${res.status}`);
        }
    } catch (err) {
        console.error(`[TEARDOWN ERROR] Excepción durante rollback de sandbox: ${err}`);
    }
}
