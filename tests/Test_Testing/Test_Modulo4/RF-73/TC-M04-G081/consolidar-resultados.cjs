const fs = require('fs');
const path = require('path');

const TC_ID = 'TC-M04-G081';
const BASE_DIR = __dirname;
const RESULTADOS_DIR = path.join(BASE_DIR, 'resultados');
const RAW_NEWMAN = path.join(RESULTADOS_DIR, '_raw_newman.json');
const JSON_OUT = path.join(RESULTADOS_DIR, `resultado_${TC_ID}.json`);

if (!fs.existsSync(RESULTADOS_DIR)) {
    fs.mkdirSync(RESULTADOS_DIR, { recursive: true });
}

const checkpoints = [];

if (fs.existsSync(RAW_NEWMAN)) {
    try {
        const raw = JSON.parse(fs.readFileSync(RAW_NEWMAN, 'utf8'));
        if (raw.run && Array.isArray(raw.run.executions)) {
            raw.run.executions.forEach(exec => {
                const itemName = (exec.item && exec.item.name) ? exec.item.name : 'Paso';
                if (Array.isArray(exec.assertions)) {
                    exec.assertions.forEach(a => {
                        const fallido = !!a.error;
                        checkpoints.push({
                            paso: `${itemName} - ${a.assertion}`,
                            esperado: 'Aserción exitosa conforme a contrato RF-73',
                            obtenido: fallido ? (a.error.message || 'Fallo en aserción') : 'OK',
                            estado: fallido ? 'FALLA' : 'OK'
                        });
                    });
                }
            });
        }
    } catch (e) {
        console.warn('No se pudo parsear _raw_newman.json:', e.message);
    }
}

const total = checkpoints.length;
const failures = checkpoints.filter(c => c.estado === 'FALLA').length;
const passes = total - failures;
const stats = { tests: total, passes: passes, failures: failures };

let estado_general = 'sin_datos';
if (total > 0) {
    estado_general = failures > 0 ? 'Rechazado' : 'Aprobado';
}

const resultado = {
    tc: TC_ID,
    rf: 'RF-73',
    titulo: 'TC-M04-G081: Registro de eventos de inferencia',
    estado_general: estado_general,
    stats: stats,
    checkpoints: checkpoints,
    bloqueados: [
        'TC-M04-250 (INFERENCIA_EJECUTADA) - Endpoint RF-66 no expuesto en backend REST',
        'TC-M04-251 (INFERENCIA_RECHAZADA) - Endpoint RF-66 no expuesto en backend REST',
        'TC-M04-252 (ALERTA_PREDICCION_GENERADA) - RF-57 no emite alerta hacia bitácora M04'
    ]
};

fs.writeFileSync(JSON_OUT, JSON.stringify(resultado, null, 2), 'utf8');
console.log(`[CONSOLIDAR] Reporte JSON generado en ${JSON_OUT} (Estado: ${estado_general}, Total: ${total}, Falla: ${failures})`);
