/**
 * Consolidar resultados de Newman para TC-M03-G169 (RF-62).
 * Transforma el JSON raw de Newman en el formato normativo con checkpoints
 * reconocido por el QA Dashboard (§5.1.1 del guide).
 *
 * Uso:
 *   node consolidar-resultados.cjs [--input <raw.json>] [--output <consolidado.json>]
 */

const fs = require('fs');
const path = require('path');

const TC_ID = 'TC-M03-G169';
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

function clasificarCausa(errMsg, respBody, statusCode) {
  const msg = (errMsg || '').toLowerCase();
  const body = (respBody || '').toLowerCase();

  if (msg.includes('psycopg2.errors') || body.includes('psycopg2.errors') || body.includes('syntax error at or near')) {
    return 'SCRIPT_QUERY';
  }
  if (msg.includes('expected null not to be null') ||
      msg.includes('expected undefined to exist') ||
      msg.includes('expected false to deeply equal true') ||
      msg.includes('expected true to deeply equal false') ||
      msg.includes('expected undefined to equal true') ||
      msg.includes('expected 70') ||
      msg.includes('apto_con_reserva') ||
      msg.includes('gap_temporal_anomalo') ||
      msg.includes('version_limites_fisicos_aplicada') ||
      msg.includes('parametros_aplicados')) {
    return 'BACKEND_CONTRATO';
  }
  if (statusCode >= 500 || msg.includes('status code') && msg.includes('50')) {
    return 'BACKEND_LATENCIA';
  }
  if (statusCode >= 400 && statusCode < 500 || msg.includes('got 40') || msg.includes('got 422')) {
    return 'SCRIPT_REQUEST';
  }
  return 'INDETERMINADA';
}

function determinarGrupo(itemName) {
  if (/^00\./.test(itemName)) return 'Preflight';
  if (/^321\./.test(itemName)) return 'TC-321';
  if (/^322\./.test(itemName)) return 'TC-322';
  if (/^99\./.test(itemName)) return 'Teardown';
  return 'General';
}

(rawData.run.executions || []).forEach(exec => {
  const itemName = exec.item ? exec.item.name : 'Unknown';
  const grupo = determinarGrupo(itemName);
  let respBody = '';
  let statusCode = 200;

  if (exec.response) {
    statusCode = exec.response.code || 200;
    if (exec.response.stream) {
      try {
        respBody = Buffer.from(exec.response.stream.data || exec.response.stream).toString('utf8');
      } catch (_) {}
    }
  }

  if (exec.assertions && exec.assertions.length > 0) {
    exec.assertions.forEach(a => {
      const isFailed = !!a.error;
      const errMsg = isFailed ? a.error.message : '';
      const causa = isFailed ? clasificarCausa(errMsg, respBody, statusCode) : null;

      checkpoints.push({
        grupo: grupo,
        paso: `${itemName} :: ${a.assertion}`,
        esperado: "Aserción cumplida",
        obtenido: isFailed ? errMsg.slice(0, 300) : "Aserción cumplida",
        estado: isFailed ? "FALLA" : "OK",
        causa: causa
      });
    });
  }
});

const total = checkpoints.length;
const ok = checkpoints.filter(c => c.estado === 'OK').length;
const falla = checkpoints.filter(c => c.estado === 'FALLA').length;

let veredicto = 'APROBADO';
if (falla > 0) {
  const fallas = checkpoints.filter(c => c.estado === 'FALLA');
  const hayBackend = fallas.some(c => c.causa === 'BACKEND_CONTRATO' || c.causa === 'BACKEND_LATENCIA');
  const todosScript = fallas.every(c => c.causa === 'SCRIPT_QUERY' || c.causa === 'SCRIPT_REQUEST');

  if (hayBackend) {
    veredicto = 'RECHAZADO';
  } else if (todosScript) {
    veredicto = 'RECHAZADO_POR_SCRIPT';
  } else {
    veredicto = 'RECHAZADO';
  }
}

const consolidado = {
  tc: TC_ID,
  titulo: "Comportamiento de RF-62 según estado heredado de RF-53",
  rf: "RF-62",
  ambiente: "TEST",
  fecha: new Date().toISOString(),
  corrida: "reintento1",
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

