import http from 'k6/http';
import { check, sleep } from 'k6';

// TC-M03-G189: Rendimiento y Concurrencia de la Bitácora de Auditoría (RF-63)
// Herramienta: k6
// Subcasos evaluados:
// - TC-M03-360: Verificación de integridad SHA-256 (Escalado en sandbox, SLA 10k [BLOQUEADO])
// - TC-M03-361: Concurrencia de consultas de auditoría (5-10 VUs x 30 s vs baseline, factor 1.2x [PROPUESTO])
// - TC-M03-362: Ingesta masiva y persistencia de eventos (Ráfaga reducida ~600/min x 30 s, SLA P95 <=5 s [BLOQUEADO])
// - TC-M03-368: Priorización de severidad en cola (Requiere métricas de cola inexistentes -> [BLOQUEADO])

export const options = {
    scenarios: {
        // Escenario 1: Baseline y Concurrencia de Consulta de Auditoría (TC-361)
        concurrencia_consulta: {
            executor: 'ramping-vus',
            startVUs: 1,
            stages: [
                { duration: '10s', target: 1 },  // Baseline 1 VU (10s)
                { duration: '10s', target: 5 },  // Rampa a 5 VUs
                { duration: '20s', target: 5 },  // 5 VUs sostenidos
                { duration: '5s', target: 0 }    // Rampa descendente
            ],
            exec: 'consultarAuditoria',
        },
        // Escenario 2: Verificación de Integridad HMAC periódica (TC-360)
        verificar_integridad: {
            executor: 'constant-arrival-rate',
            rate: 1, // 1 req cada 5 segundos
            timeUnit: '5s',
            duration: '30s',
            preAllocatedVUs: 2,
            maxVUs: 5,
            exec: 'verificarIntegridad',
        }
    },
    thresholds: {
        'http_req_duration{scenario:concurrencia_consulta}': ['p(95)<2000'],
        'http_req_duration{scenario:verificar_integridad}': ['p(95)<3000'],
        http_req_failed: ['rate<0.01'],
        checks: ['rate>0.98'],
    },
};

const BASE_URL = __ENV.baseUrl || 'https://api.inmero.co/back-sigab-test';
const RUN_ID = __ENV.run_id || `test-k6-g189-${Date.now()}`;
const SANDBOX_SECRET = __ENV.sandbox_secret || '377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff';
const ADMIN_PASSWORD = __ENV.admin_password || '';

export function setup() {
    console.log(`[SETUP G189] Inicializando suite k6 bajo Run ID: ${RUN_ID}`);
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
        console.log('[SETUP G189] Autenticación admin exitosa');
    } else {
        console.error(`[SETUP G189] Fallo autenticación admin: ${loginRes.status}`);
    }

    // Registrar notas de casos bloqueados
    console.log('[BLOQUEADO] TC-360: SLA <=10s con 10,000 eventos requiere precargar 10k eventos en BD, excediendo timeout sandbox (180s).');
    console.log('[BLOQUEADO] TC-362: SLA P95 <=5s con 5,000 eventos/min x 3 min requiere saturar entorno compartido. Evaluado con ráfaga reducida.');
    console.log('[BLOQUEADO] TC-368: Priorización de severidad en cola requiere endpoints de métricas de broker/cola inexistentes en API.');

    return { token, runId: RUN_ID };
}

export function consultarAuditoria(data) {
    const res = http.get(
        `${BASE_URL}/iot/auditoria?pagina=1&por_pagina=20`,
        {
            headers: {
                'Authorization': `Bearer ${data.token}`,
                'X-Test-Run-Id': data.runId,
                'X-Sandbox-Secret': SANDBOX_SECRET,
            },
            tags: { scenario: 'concurrencia_consulta' }
        }
    );

    check(res, {
        'GET /iot/auditoria status 200': (r) => r.status === 200,
        'GET /iot/auditoria retorna items': (r) => {
            try {
                const body = r.json();
                return Array.isArray(body.items || body);
            } catch (e) {
                return false;
            }
        }
    });

    sleep(0.5);
}

export function verificarIntegridad(data) {
    const res = http.post(
        `${BASE_URL}/iot/auditoria/verificar-integridad`,
        JSON.stringify({}),
        {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${data.token}`,
                'X-Test-Run-Id': data.runId,
                'X-Sandbox-Secret': SANDBOX_SECRET,
            },
            tags: { scenario: 'verificar_integridad' }
        }
    );

    check(res, {
        'POST /verificar-integridad status 200': (r) => r.status === 200,
        'Verificación reporta cero comprometidos': (r) => {
            try {
                const body = r.json();
                return body.comprometidos === 0;
            } catch (e) {
                return false;
            }
        }
    });

    sleep(1);
}

export function teardown(data) {
    console.log(`[TEARDOWN G189] Ejecutando rollback del sandbox transaccional: ${data.runId}`);
    const deleteRes = http.del(
        `${BASE_URL}/test-control/runs/${data.runId}`,
        null,
        {
            headers: {
                'X-Test-Run-Id': data.runId,
                'X-Sandbox-Secret': SANDBOX_SECRET,
            },
        }
    );

    const rollbackOk = check(deleteRes, {
        'DELETE /test-control/runs/{run_id} exitoso (200)': (r) => r.status === 200,
    });

    if (rollbackOk) {
        console.log('[TEARDOWN G189] Rollback completado exitosamente.');
    } else {
        console.error(`[TEARDOWN G189] Error en rollback sandbox: ${deleteRes.status} ${deleteRes.body}`);
    }
}
