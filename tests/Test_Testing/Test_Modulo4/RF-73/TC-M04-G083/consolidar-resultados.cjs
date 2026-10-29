const fs = require('fs');
const path = require('path');

const TC_ID = 'TC-M04-G083';
const BASE_DIR = __dirname;
const RESULTADOS_DIR = path.join(BASE_DIR, 'resultados');

const [, , argRaw, argOut] = process.argv;
const RAW_NEWMAN = argRaw ? path.resolve(argRaw) : path.join(RESULTADOS_DIR, '_raw_newman_reintento1.json');
const JSON_OUT = argOut ? path.resolve(argOut) : path.join(RESULTADOS_DIR, `resultado_${TC_ID}_reintento1.json`);

if (!fs.existsSync(RESULTADOS_DIR)) {
    fs.mkdirSync(RESULTADOS_DIR, { recursive: true });
}

let checkpoints = [];
let stats = { tests: 0, passes: 0, failures: 0 };

if (fs.existsSync(RAW_NEWMAN)) {
    try {
        const raw = JSON.parse(fs.readFileSync(RAW_NEWMAN, 'utf8'));
        const executions = (raw.run && raw.run.executions) ? raw.run.executions : [];
        executions.forEach(e => {
            const asserts = e.assertions || [];
            asserts.forEach(a => {
                checkpoints.push({
                    paso: a.assertion,
                    esperado: 'PASSED',
                    obtenido: a.error ? 'FAILED' : 'PASSED',
                    estado: a.error ? 'FALLA' : 'OK'
                });
            });
        });
        const total = checkpoints.length;
        const ok = checkpoints.filter(c => c.estado === 'OK').length;
        const falla = checkpoints.filter(c => c.estado === 'FALLA').length;
        stats = { tests: total, passes: ok, failures: falla };
    } catch (e) {
        console.warn('No se pudo parsear raw newman JSON:', e.message);
    }
}

const total = checkpoints.length;
const ok = checkpoints.filter(c => c.estado === 'OK').length;
const falla = checkpoints.filter(c => c.estado === 'FALLA').length;
const veredicto = total === 0 ? 'PENDIENTE' : (falla === 0 ? 'APROBADO' : 'RECHAZADO');

const resultado = {
    tc: TC_ID,
    rf: 'RF-73',
    titulo: 'TC-M04-G083: Distribución OTA e integridad',
    summary: { total, ok, falla, veredicto },
    stats: stats,
    checkpoints: checkpoints
};

fs.writeFileSync(JSON_OUT, JSON.stringify(resultado, null, 2), 'utf8');
console.log(`[CONSOLIDAR] Reporte JSON generado en ${JSON_OUT} → total=${total} ok=${ok} falla=${falla} veredicto=${veredicto}`);
