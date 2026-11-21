// | Fecha      | Nombre   | Que se hizo                                                 |
// |------------|----------|-------------------------------------------------------------|
// | 2026-10-30 | QA Senior | Consolidador de resultados normativos TC-M03-G192 (RF-62)    |
// | 2026-10-30 | QA Senior | Soporte por defecto para resultado_TC-M03-G192_reintento2.json|
/**
 * Consolidar resultados de Newman para TC-M03-G192 (RF-62 / AIOT-SPEC-01).
 * Transforma el JSON raw de Newman en el formato normativo con checkpoints
 * reconocido por el QA Dashboard (§5.1.1 del guide).
 *
 * Uso:
 *   node consolidar-resultados.cjs [--input <raw.json>] [--output <consolidado.json>]
 */

const fs = require('fs');
const path = require('path');

const TC_ID = 'TC-M03-G192';
const dirActual = __dirname;
const defaultFile = path.join(dirActual, 'resultados', 'resultado_TC-M03-G192_reintento1.json');

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

  if (body.includes('dispositivo_no_es_camara') ||
      body.includes('area_no_coincide') ||
      body.includes('error_autenticacion') ||
      body.includes('error_tiempo') ||
      body.includes('observacion_vision_no_encontrada') ||
      body.includes('parametro_mlops_invalido') ||
      body.includes('no es una cámara') ||
      body.includes('valor no es un entero válido') ||
      body.includes('{{obs_') ||
      msg.includes('optima') ||
      msg.includes('degradada') ||
      msg.includes('no_apta') ||
      msg.includes('indice') ||
      msg.includes('clasificacion') ||
      msg.includes('apto_para_ia') ||
      msg.includes('apto_para_nic41') ||
      msg.includes('below') ||
      msg.includes('include') ||
      msg.includes('to deeply equal') ||
      msg.includes('encontró observación en bd') ||
      msg.includes('got 400') ||
      msg.includes('got 422')) {
    return 'BACKEND_CONTRATO';
  }
  if (msg.includes('psycopg2.errors') || body.includes('psycopg2.errors') || body.includes('syntax error at or near')) {
    return 'SCRIPT_QUERY';
  }
  if (statusCode >= 500 || (msg.includes('status code') && msg.includes('50'))) {
    return 'BACKEND_LATENCIA';
  }
  if ((statusCode >= 400 && statusCode < 500) || msg.includes('got 40') || msg.includes('got 422')) {
    return 'SCRIPT_REQUEST';
  }
  return 'INDETERMINADA';
}

function determinarGrupo(itemName) {
  if (/^00\./.test(itemName)) return 'Preflight';
  if (/^01\./.test(itemName) || itemName.includes('369')) return 'TC-369';
  if (/^02\./.test(itemName) || itemName.includes('370')) return 'TC-370';
  if (/^03\./.test(itemName) || itemName.includes('371')) return 'TC-371';
  if (/^04\./.test(itemName) || itemName.includes('372')) return 'TC-372';
  if (/^05\./.test(itemName) || itemName.includes('373')) return 'TC-373';
  if (/^99\./.test(itemName) || itemName.includes('Rollback')) return 'Teardown';
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
  titulo: "Calidad de observaciones de VISIÓN (AIOT-SPEC-01)",
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
console.log(`[CONSOLIDATOR SUCCESS] Resumen: total=${total}, ok=${ok}, falla=${falla}, veredicto=${veredicto}`);
