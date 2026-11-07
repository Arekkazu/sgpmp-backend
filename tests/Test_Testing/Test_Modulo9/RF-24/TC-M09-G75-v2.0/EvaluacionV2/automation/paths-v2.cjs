// Adaptador de rutas de la SEGUNDA EVALUACIÓN de TC-M09-G75-v2.0.
//
// Reutiliza TAL CUAL los helpers de la primera evaluación (aritmética decimal, login,
// GET de discovery, construcción del plan, mensajes esperados del RF y sanitización):
// no se redefine ninguna regla funcional ni ningún esperado.
//
// Lo único que cambia es DÓNDE se escribe la evidencia: todo resultado del RUN va a
// EvaluacionV2/RESULTADOS/<RUN_ID>/, nunca a la carpeta de la primera evaluación.

const fs = require('fs');
const path = require('path');

// La guarda de directorio autorizado de helpers.cjs se evalúa con su propio __dirname,
// que sigue siendo TC-M09-G75-v2.0: se respeta sin copiar ni modificar el archivo.
const H0 = require('../../helpers.cjs');

const CASE_DIR = path.resolve(__dirname, '..', '..'); // TC-M09-G75-v2.0/
const EVAL_DIR = path.resolve(__dirname, '..');       // TC-M09-G75-v2.0/EvaluacionV2/

function runDir(runId, sub) {
  const d = sub
    ? path.join(EVAL_DIR, 'RESULTADOS', runId, sub)
    : path.join(EVAL_DIR, 'RESULTADOS', runId);
  fs.mkdirSync(d, { recursive: true });
  return d;
}

function save(runId, name, value) {
  const file = path.join(runDir(runId), name);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, H0.clean(JSON.stringify(value, null, 2)));
  return file;
}

module.exports = { ...H0, runDir, save, CASE_DIR, EVAL_DIR };
