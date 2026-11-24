// | Fecha      | Nombre                   | Que se hizo |
// |------------|--------------------------|-------------|
// | 2026-11-20 | Juan Sebastian Gutierrez | Ronda 1: convertir_json_g018.py (Python, se corrio aparte despues de la corrida) |
// | 2026-11-23 | Juan Sebastian Gutierrez | Reintento 1: misma conversion en Node, la llama el runner dentro de la corrida; 12 checkpoints con lista explicita; el SHA de origen cubre trazas, checkpoints y HTML |
//
// Convierte el staging de una corrida de TC-M08-G018 (trazas + checkpoints de Newman) al JSON propio del manual 2.1.
// No hace peticiones ni lee .env.test. Uso: node convertir_json_g018.mjs <carpeta run-...> <reintento> <run_id>
// Salida 0: JSON escrito. Cualquier otra salida: no se escribe JSON y el motivo va por stderr (el runner marca la corrida invalida).
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const [run, reintentoTxt, runId] = process.argv.slice(2);
if (!run || reintentoTxt === undefined || !runId) { console.error('uso: node convertir_json_g018.mjs <run> <reintento> <run_id>'); process.exit(2); }
const reintento = Number.parseInt(reintentoTxt, 10);
if (!Number.isInteger(reintento) || reintento < 0) { console.error(`reintento invalido: ${reintentoTxt}`); process.exit(2); }
const suf = reintento > 0 ? `_reintento${reintento}` : '';
const tc = 'TC-M08-G018';
const ESPERADOS = ['CP-01', 'CP-02', 'CP-04', 'CP-05', 'CP-06a', 'CP-06b', 'CP-07a', 'CP-07b', 'CP-08', 'CP-09a', 'CP-10', 'CP-11'];
const caso = (cp) => (cp === 'CP-11' ? 'TC-M08-059' : 'TC-M08-047');
const salir = (motivo) => { console.error(motivo); process.exit(3); };

const leer = (n) => readFileSync(join(run, n), 'utf8').replace(/^﻿/, '');
const campos = (linea) => {
  // tipo|id|esperado=...|obtenido=... (puede contener |)|estado=...|req=...
  const p = linea.split('|');
  return {
    tipo: p[0], id: p[1], esperado: p[2].replace(/^esperado=/, ''),
    obtenido: p.slice(3, -2).join('|').replace(/^obtenido=/, ''),
    estado: p.at(-2).replace(/^estado=/, ''), req: p.at(-1).replace(/^req=/, ''),
  };
};

const nTrazas = `trazas_${tc}${suf}.txt`, nCps = `checkpoints_${tc}${suf}.txt`, nHtml = `resultado_${tc}${suf}.html`;
for (const n of [nTrazas, nCps, nHtml]) if (!existsSync(join(run, n))) salir(`falta ${n}`);
const trazas = leer(nTrazas).split(/\r?\n/).filter((l) => l.trim());
const nombres = {};
for (const l of leer(nCps).split(/\r?\n/)) {
  const m = l.match(/^(OK|FALLA)\s+\|\s+(CP-\S+)\s+(.*?)\s+\|\| esperado: /);
  if (m) {
    if (nombres[m[2]]) salir(`checkpoint repetido en ${nCps}: ${m[2]}`);
    nombres[m[2]] = [m[1], m[3]];
  }
}

const cps = [], obs = [], pre = [];
for (const l of trazas) {
  if (l.startsWith('CP|')) {
    const c = campos(l);
    if (!nombres[c.id]) salir(`la traza ${c.id} no tiene asercion en ${nCps}`);
    const [estadoNewman, nombre] = nombres[c.id];
    if (estadoNewman !== c.estado) salir(`INCOHERENTE: ${c.id} trazas=${c.estado} checkpoints=${estadoNewman}`);
    if (c.estado !== 'OK' && c.estado !== 'FALLA') salir(`estado invalido en ${c.id}: ${c.estado}`);
    const fuente = nombre.match(/\(([^()]*)\)\s*$/);
    cps.push({ paso: `${c.id} ${nombre}`, caso: caso(c.id), esperado: c.esperado, fuente: fuente ? fuente[1] : '',
      obtenido: c.obtenido, estado: c.estado, x_request_id: c.req });
  } else if (l.startsWith('OBS|')) {
    const c = campos(l);
    obs.push({ id: c.id, obtenido: c.obtenido, x_request_id: c.req });
  } else if (/^(PRE|ABORT|RETIRADO|CIERRE)\|/.test(l)) {
    pre.push(l);
  }
}

const ids = cps.map((c) => c.paso.split(' ')[0]);
if (JSON.stringify(ids) !== JSON.stringify(ESPERADOS)) salir(`CHECKPOINTS DISTINTOS DEL DISENO: ${ids.join(',')}`);
if (Object.keys(nombres).length !== ESPERADOS.length) salir(`${nCps} tiene ${Object.keys(nombres).length} aserciones, se esperaban ${ESPERADOS.length}`);
if (pre.some((l) => /^(ABORT|RETIRADO)\|/.test(l))) salir('La corrida tiene ABORT o RETIRADO: no se genera JSON');
const cierre = pre.filter((l) => l.startsWith('CIERRE|'));
const ok = cps.filter((c) => c.estado === 'OK').length;
const falla = cps.length - ok;
const sha = (n) => createHash('sha256').update(readFileSync(join(run, n))).digest('hex').toUpperCase();
const doc = {
  tc, reintento,
  summary: { total: cps.length, ok, falla, veredicto: falla ? 'Rechazado' : 'Aprobado' },
  checkpoints: cps,
  observaciones: obs,
  retirados: [],
  runs: [{ run_id: runId, rollback: cierre.length ? cierre[0] : 'no encontrado' }],
  precondiciones: pre.filter((l) => l.startsWith('PRE|')),
  origen: {
    herramienta: 'Newman + htmlextra; JSON generado por el runner con convertir_json_g018.mjs desde el mismo staging',
    sha256: Object.fromEntries([nTrazas, nCps, nHtml].map((n) => [n, sha(n)])),
  },
};
const salida = join(run, `resultado_${tc}${suf}.json`);
if (existsSync(salida)) salir(`ya existe ${salida}`);
writeFileSync(salida, `${JSON.stringify(doc, null, 2)}\n`.replace(/\n/g, '\r\n'), 'utf8');
console.log(`${salida}: total=${cps.length} ok=${ok} falla=${falla} observaciones=${obs.length}`);
