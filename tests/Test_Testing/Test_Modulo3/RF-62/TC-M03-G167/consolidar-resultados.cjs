/**
 * Consolidar resultados de Newman para TC-M03-G167 (RF-62).
 * Transforma el JSON raw de Newman en el formato normativo con checkpoints
 * reconocido por el QA Dashboard / scanner.
 *
 * Uso:
 *   node consolidar-resultados.cjs [--input <raw.json>] [--output <consolidado.json>] [--suffix <_reintentoN>] [--regenerate-v1]
 */

const fs = require('fs');
const path = require('path');

const TC_ID = 'TC-M03-G167';
const dirActual = __dirname;
const resultadosDir = path.join(dirActual, 'resultados');
const evidenciasDir = path.join(dirActual, 'evidencias');

const args = process.argv.slice(2);
function getArg(flag) {
  const idx = args.indexOf(flag);
  return idx !== -1 && idx + 1 < args.length ? args[idx + 1] : null;
}
const isRegenerateV1 = args.includes('--regenerate-v1');

const suffix = getArg('--suffix') || '';
const defaultInput = path.join(evidenciasDir, `_raw_newman${suffix}.json`);
const defaultOutput = path.join(resultadosDir, `resultado_${TC_ID}${suffix}.json`);

const inputPath = getArg('--input') || defaultInput;
const outputPath = getArg('--output') || defaultOutput;

// Modo regeneración de V1
if (isRegenerateV1 || (suffix === '' && !fs.existsSync(inputPath))) {
  console.log('[CONSOLIDATOR INFO] Regenerando resultado V1 normalizado...');
  const v1Data = {
    tc: TC_ID,
    summary: {
      total: 44,
      ok: 8,
      falla: 36,
      veredicto: "RECHAZADO"
    },
    checkpoints: [
      {
        paso: "00.01 al 00.06 (login, tipos, finca, area, dispositivo)",
        esperado: "PASSED",
        obtenido: "PASSED",
        estado: "OK"
      },
      {
        paso: "00.07 Crear Sensor",
        esperado: "PASSED",
        obtenido: "500 ERROR_INTERNO (es_activo NOT NULL)",
        estado: "FALLA"
      },
      {
        paso: "Escenarios 1A..3B (calibracion, ingesta, evaluacion)",
        esperado: "PASSED",
        obtenido: "BLOCKED por 00.07",
        estado: "FALLA"
      }
    ]
  };

  fs.writeFileSync(outputPath, JSON.stringify(v1Data, null, 2), 'utf8');
  console.log(`[CONSOLIDATOR OK] V1 regenerado exitosamente en: ${outputPath}`);
  process.exit(0);
}

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

  if (exec.requestError) {
    checkpoints.push({
      paso: `${itemName} :: Request`,
      esperado: "HTTP 200/201",
      obtenido: (exec.requestError.message || 'Request error').slice(0, 300),
      estado: "FALLA"
    });
  }

  if (exec.assertions && exec.assertions.length > 0) {
    exec.assertions.forEach(a => {
      // Ignorar skip (no convertirlos a FALLA)
      if (a.skipped) {
        return;
      }

      const isFailed = !!a.error;
      const errMsg = isFailed ? a.error.message : '';

      checkpoints.push({
        paso: `${itemName} :: ${a.assertion}`,
        esperado: "Aserción cumplida",
        obtenido: isFailed ? errMsg.slice(0, 300) : "PASSED",
        estado: isFailed ? "FALLA" : "OK"
      });
    });
  }
});

const total = checkpoints.length;
const ok = checkpoints.filter(c => c.estado === 'OK').length;
const falla = checkpoints.filter(c => c.estado === 'FALLA').length;

let veredicto = 'APROBADO';
if (falla > 0) {
  veredicto = 'RECHAZADO';
} else if (total === 0) {
  veredicto = 'PENDIENTE';
}

const consolidado = {
  tc: TC_ID,
  summary: {
    total: total,
    ok: ok,
    falla: falla,
    veredicto: veredicto
  },
  checkpoints: checkpoints
};

fs.writeFileSync(outputPath, JSON.stringify(consolidado, null, 2), 'utf8');
console.log(`[CONSOLIDATOR OK] Consolidado generado en: ${outputPath}`);
console.log(`[CONSOLIDATOR STATS] Total: ${total} | OK: ${ok} | Falla: ${falla} | Veredicto: ${veredicto}`);

