/**
 * Consolidar resultados de Newman para TC-M03-G168 (RF-62).
 * Transforma el JSON raw de Newman en el formato normativo con checkpoints
 * reconocido por el QA Dashboard / scanner.
 *
 * Uso:
 *   node consolidar-resultados.cjs [--input <raw.json>] [--output <consolidado.json>] [--suffix <_reintentoN>]
 */

const fs = require('fs');
const path = require('path');

const TC_ID = 'TC-M03-G168';
const dirActual = __dirname;
const resultadosDir = path.join(dirActual, 'resultados');
const evidenciasDir = path.join(dirActual, 'evidencias');

const args = process.argv.slice(2);
function getArg(flag) {
  const idx = args.indexOf(flag);
  return idx !== -1 && idx + 1 < args.length ? args[idx + 1] : null;
}

const suffix = getArg('--suffix') || '';
const rawInEvidencias = path.join(evidenciasDir, `_raw_newman${suffix}.json`);
const targetInResultados = path.join(resultadosDir, `resultado_${TC_ID}${suffix}.json`);

let inputPath = getArg('--input');
if (!inputPath) {
  if (fs.existsSync(rawInEvidencias)) {
    inputPath = rawInEvidencias;
  } else if (fs.existsSync(targetInResultados)) {
    inputPath = targetInResultados;
  } else {
    inputPath = rawInEvidencias;
  }
}

const outputPath = getArg('--output') || targetInResultados;

if (!fs.existsSync(inputPath)) {
  console.error(`[CONSOLIDATOR ERROR] Archivo de entrada no encontrado: ${inputPath}`);
  process.exit(1);
}

const rawContent = fs.readFileSync(inputPath, 'utf8');
const rawData = JSON.parse(rawContent);

// Si ya fue consolidado previamente y no contiene run.executions
if (rawData.checkpoints && Array.isArray(rawData.checkpoints) && (!rawData.run || !rawData.run.executions)) {
  console.log(`[CONSOLIDATOR INFO] El archivo ${inputPath} ya tiene estructura de checkpoints.`);
  process.exit(0);
}

if (!rawData.run || !rawData.run.executions) {
  console.error(`[CONSOLIDATOR ERROR] Estructura inválida en ${inputPath}. Se esperaba 'run.executions'.`);
  process.exit(1);
}

// Si leímos directamente de resultados/resultado_...json y es el raw, respaldamos una copia en evidencias/
if (inputPath === targetInResultados && !fs.existsSync(rawInEvidencias)) {
  try {
    fs.writeFileSync(rawInEvidencias, rawContent, 'utf8');
    console.log(`[CONSOLIDATOR INFO] Copia cruda de Newman respaldada en: ${rawInEvidencias}`);
  } catch (e) {
    console.warn(`[CONSOLIDATOR WARN] No se pudo respaldar raw en evidencias: ${e.message}`);
  }
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
      // Ignorar skip (no convertirlos a FALLA ni contarlos)
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

