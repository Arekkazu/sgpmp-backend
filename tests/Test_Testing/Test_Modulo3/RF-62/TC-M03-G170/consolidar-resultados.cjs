// | Fecha      | Nombre     | Que se hizo                                                    |
// |------------|------------|----------------------------------------------------------------|
// | 2026-10-30 | Juansegutt | Script consolidador normativo de checkpoints para TC-M03-G170  |

/**
 * Consolidar resultados de Newman para TC-M03-G170 (RF-62).
 * Transforma el JSON raw de Newman en el formato normativo con checkpoints
 * reconocido por el QA Dashboard (§5.1.1 de la Guía de Pruebas).
 *
 * Uso:
 *   node consolidar-resultados.cjs [--input <raw.json>] [--output <consolidado.json>]
 */

const fs = require('fs');
const path = require('path');

const TC_ID = 'TC-M03-G170';
const dirActual = __dirname;
const defaultFile = path.join(dirActual, 'resultados', `resultado_${TC_ID}_reintento1.json`);

const args = process.argv.slice(2);
function getArg(flag) {
  const idx = args.indexOf(flag);
  return idx !== -1 && idx + 1 < args.length ? args[idx + 1] : null;
}

const inputPath = getArg('--input') || defaultFile;
const outputPath = getArg('--output') || defaultFile;

if (!fs.existsSync(inputPath)) {
  console.error(`[CONSOLIDATOR ERROR] Archivo de entrada no encontrado: ${inputPath}`);
  process.exit(1);
}

const rawData = JSON.parse(fs.readFileSync(inputPath, 'utf8'));

// Si ya fue consolidado previamente (tiene checkpoints)
if (rawData.checkpoints && Array.isArray(rawData.checkpoints)) {
  console.log(`[CONSOLIDATOR INFO] El archivo ${inputPath} ya tiene estructura de checkpoints.`);
  process.exit(0);
}

if (!rawData.run || !rawData.run.executions) {
  console.error(`[CONSOLIDATOR ERROR] Estructura inválida en ${inputPath}. Se esperaba 'run.executions'.`);
  process.exit(1);
}

const checkpoints = [];

(rawData.run.executions || []).forEach(exec => {
  const itemName = exec.item ? exec.item.name : 'Unknown';

  if (exec.assertions && exec.assertions.length > 0) {
    exec.assertions.forEach(a => {
      const isFailed = !!a.error;
      const errMsg = isFailed ? a.error.message : '';
      checkpoints.push({
        paso: `${itemName} -> ${a.assertion}`,
        esperado: 'PASSED',
        obtenido: isFailed ? `FALLA: ${errMsg.slice(0, 140)}` : 'PASSED',
        estado: isFailed ? 'FALLA' : 'OK'
      });
    });
  } else {
    // Si no hay asertos en la ejecucion
    const statusCode = exec.response ? exec.response.code : 0;
    checkpoints.push({
      paso: itemName,
      esperado: 'HTTP 200',
      obtenido: `HTTP ${statusCode}`,
      estado: (statusCode >= 200 && statusCode < 400) ? 'OK' : 'FALLA'
    });
  }
});

const total = checkpoints.length;
const passed = checkpoints.filter(c => c.estado === 'OK').length;
const failed = checkpoints.filter(c => c.estado === 'FALLA').length;

const consolidado = {
  tc: TC_ID,
  corrida: 'reintento1',
  summary: {
    total: total,
    passed: passed,
    failed: failed,
    veredicto: failed > 0 ? 'RECHAZADO' : (total > 0 ? 'APROBADO' : 'PENDIENTE')
  },
  checkpoints: checkpoints
};

fs.writeFileSync(outputPath, JSON.stringify(consolidado, null, 2), 'utf8');
console.log(`[CONSOLIDATOR OK] Consolidado generado en: ${outputPath}`);
console.log(`Total checkpoints: ${total} (OK: ${passed}, FALLA: ${failed}) -> Veredicto: ${consolidado.summary.veredicto}`);

