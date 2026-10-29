import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// Validación local previa a credenciales, RUN o red. Utilidad sin lógica de G87.
export function contextoEjecucion(argumentos, { grupo, casos, directorio, modoEnsayo = false }) {
  const a = argumentos;
  const valor = (k) => a.includes(k) ? a[a.indexOf(k) + 1] : undefined;
  const operacion = valor('--operacion');
  if (!['evaluar', 'reintentar', 'reevaluar', 'recuperar'].includes(operacion)) throw new Error('Operación inválida.');
  const version = Number(valor('--version'));
  const intento = Number(valor('--intento'));
  const runId = valor('--run-id');
  const objetivo = valor('--run-objetivo');
  const referencia = valor('--autorizacion');
  const archivo = valor('--contexto');
  const ensayo = modoEnsayo && /^ENSAYO-G127-\d{8}-\d{6}-[a-z0-9_]+$/.test(runId ?? '');
  if (!Number.isInteger(version) || version < 1 || version > 99 || !Number.isInteger(intento) || intento < 1
    || !(new RegExp(`^RUN-${grupo}-V${version}-\\d{8}-\\d{6}$`).test(runId ?? '') || ensayo)
    || !referencia || !archivo || !path.isAbsolute(archivo)) throw new Error('Argumentos del contrato incompletos.');
  if (operacion === 'reevaluar' ? version < 2 : operacion !== 'recuperar' && version < 1) throw new Error('Versión incompatible.');
  if (operacion === 'recuperar' && objetivo !== runId) throw new Error('RUN objetivo incoherente.');
  if (operacion !== 'recuperar' && objetivo) throw new Error('RUN objetivo inesperado.');
  const esperado = path.join(version === 1 ? path.join(directorio, 'Resultados')
    : path.join(directorio, `EvaluacionV${version}`, 'Resultados'), runId);
  const ruta = path.resolve(archivo);
  const temp = path.resolve(os.tmpdir());
  const directorioEnsayo = path.dirname(ruta);
  if (ensayo && (!['evaluar', 'reintentar'].includes(operacion) || !directorioEnsayo.startsWith(temp + path.sep)
    || path.basename(ruta) !== 'contexto_operacion.json')) throw new Error('Ensayo fuera de temporal.');
  if ((!ensayo && path.dirname(ruta) !== esperado) || !(operacion === 'recuperar'
    ? /^recuperacion-\d{14}\.contexto\.json$/.test(path.basename(ruta))
    : path.basename(ruta) === 'contexto_operacion.json')
    || !fs.statSync(ruta).isFile() || fs.lstatSync(ruta).isSymbolicLink()) throw new Error('Ruta de contexto fuera del RUN.');
  const c = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (c.grupo !== grupo || c.version !== version || c.intento !== intento || c.run_id !== runId
    || c.operacion !== operacion.toUpperCase() || c.referencia !== referencia
    || JSON.stringify(c.casos) !== JSON.stringify(casos)
    || (operacion === 'recuperar' && c.run_objetivo !== objetivo)) throw new Error('Contexto incoherente.');
  if (operacion === 'reevaluar' && (!c.alcance_reevaluacion || c.version_anterior !== version - 1))
    throw new Error('Falta alcance de reevaluación.');
  return { operacion, version, intento, runId, objetivo, referencia, contexto: c,
    directorio: ensayo ? directorioEnsayo : esperado, ensayo };
}


