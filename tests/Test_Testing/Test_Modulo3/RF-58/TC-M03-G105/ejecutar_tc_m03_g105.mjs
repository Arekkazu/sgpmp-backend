#!/usr/bin/env node
// TC-M03-205 (RF-58, usabilidad): un usuario Productor interpreta el estado de una variable en ≤ 5 s,
// sin requerir información técnica del sensor.
//
// La matriz lo define como PRUEBA MANUAL CONTROLADA con usuarios reales o representativos del
// perfil Productor y cronómetro. Ninguna automatización puede sustituir la interpretación humana:
// este ejecutor no usa Newman ni Cypress ni se conecta al API. Asiste a la sesión moderada:
// - `--ejecutar` cronometra cada ensayo desde la terminal del moderador (Enter al mostrar la
//   variable, Enter cuando el participante responde) y registra la respuesta;
// - `--ejecutar --registro <archivo.json>` evalúa un registro completado en papel con la plantilla;
// - en ambos casos valida las precondiciones del panel, evalúa cada ensayo y genera el informe y
//   `evidencia.json` versionados. No se registran datos personales: solo códigos de participante.
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { leerEnv, autorizar, version, carpetaResultados, runId, nombreInforme, argumentos, sello, redactor, informe, veredictoCasos } from './monitoreo_lib.mjs';

export const GRUPO = 'TC-M03-G105';
export const CASOS = ['TC-M03-205'];
export const ESTADOS = ['VERDE', 'AMARILLO', 'ROJO', 'GRIS'];
export const LIMITE_S = 5;
/** Cada estado debe presentarse y ser interpretado correctamente al menos una vez. */
export const REQUERIDAS = { 'TC-M03-205': ESTADOS.map(x => `UI-205-01@${x}`) };

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const PLANTILLA = path.join(DIR, 'plantilla_registro_g105.json');

const CODIGO = /^P\d{2,3}$/;
const PERSONALES = /@|\b(nombre|apellido|cedula|c[eé]dula|documento|telefono|tel[eé]fono|correo|email)\b/i;

/**
 * Precondiciones del escenario (las declara el moderador y se comprueban antes de evaluar):
 * panel con los cuatro estados y al menos una alerta activa visible, participantes Productor sin
 * conocimiento técnico, cada estado presentado al menos una vez y ensayos completos.
 */
export function precondiciones(r) {
  const p = [];
  const add = (variante, nombre, ok, detalle) => p.push({ caso: 'TC-M03-205', tipo: 'PRE', id: null, variante, nombre: `[TC-M03-205][PRE]${variante ? `[V:${variante}]` : ''} ${nombre}`, ok: !!ok, evidencia: false, error: ok ? undefined : detalle });
  const presentes = new Set(r?.panel?.estados_presentes || []);
  for (const e of ESTADOS) add(e, `el panel presenta variables en ${e}`, presentes.has(e), 'el moderador no confirmó ese estado en el panel');
  add(null, 'el panel muestra al menos una condición con alerta activa', r?.panel?.alerta_activa_visible === true, 'alerta activa no confirmada');
  const participantes = r?.participantes || [];
  add(null, 'participantes con perfil Productor y sin conocimiento técnico', participantes.length > 0 && participantes.every(x => CODIGO.test(x.codigo || '') && x.perfil_productor === true && x.conocimiento_tecnico === false), 'participantes ausentes, sin código Pxx o fuera del perfil');
  add(null, 'registro sin datos personales (solo códigos de participante)', !PERSONALES.test(JSON.stringify({ participantes, ensayos: r?.ensayos || [] })), 'el registro contiene datos personales: use solo códigos Pxx');
  const codigos = new Set(participantes.map(x => x.codigo));
  const ensayos = r?.ensayos || [];
  const completo = e => codigos.has(e.participante) && ESTADOS.includes(e.estado_presentado) && typeof e.variable === 'string' && e.variable.trim() && (e.estado_identificado === null || typeof e.estado_identificado === 'string') && Number.isFinite(e.tiempo_s) && e.tiempo_s >= 0 && typeof e.requirio_informacion_tecnica === 'boolean';
  add(null, 'ensayos completos (participante, variable, estado presentado e identificado, tiempo e información técnica)', ensayos.length > 0 && ensayos.every(completo), 'hay ensayos incompletos o de participantes no registrados');
  for (const e of ESTADOS) add(e, `se presentó al menos un ensayo en ${e}`, ensayos.some(x => x.estado_presentado === e), 'estado sin ensayos');
  return p;
}
/** Aserción por ensayo: estado correcto, en ≤ 5 s y sin requerir información técnica. */
export function evaluarEnsayo(e) {
  const motivos = [];
  if (String(e.estado_identificado || '').toUpperCase() !== e.estado_presentado) motivos.push(`identificó ${e.estado_identificado ?? 'nada'} (presentado ${e.estado_presentado})`);
  if (!(e.tiempo_s <= LIMITE_S)) motivos.push(`${e.tiempo_s} s > ${LIMITE_S} s`);
  if (e.requirio_informacion_tecnica) motivos.push('requirió información técnica');
  return { caso: 'TC-M03-205', tipo: 'ASSERT', id: 'UI-205-01', variante: e.estado_presentado, nombre: `[TC-M03-205][ASSERT][UI-205-01][V:${e.estado_presentado}] ${e.participante} · ${e.variable}: ${e.tiempo_s} s`, ok: !motivos.length, evidencia: true, error: motivos.join('; ') || undefined };
}
export function evaluarRegistro(r) {
  const pre = precondiciones(r);
  const validos = pre.filter(a => a.variante === null).every(a => a.ok);
  const aserciones = validos ? (r.ensayos || []).map(evaluarEnsayo) : [];
  const tiempos = (r?.ensayos || []).map(e => e.tiempo_s).filter(Number.isFinite).sort((a, b) => a - b);
  return { aserciones: [...pre, ...aserciones], resumen: { participantes: (r?.participantes || []).length, ensayos: (r?.ensayos || []).length, superados: aserciones.filter(a => a.ok).length, tiempo_max_s: tiempos.at(-1) ?? null, limite_s: LIMITE_S } };
}

/**
 * Captura moderada desde la terminal. `leer` devuelve la siguiente línea; `reloj` da milisegundos.
 * Por ensayo: código de participante, variable y estado presentado; Enter al mostrarla; Enter cuando
 * el participante responde; estado identificado; si requirió información técnica (s/n).
 */
export async function capturar({ leer, escribir, reloj }) {
  const r = { sesion: {}, panel: {}, participantes: [], ensayos: [] };
  escribir('Condiciones de la sesión (fecha y lugar, dispositivo y ancho, conexión, URL de la vista):');
  r.sesion.condiciones = (await leer()).trim();
  escribir(`Estados presentes en el panel, separados por coma (${ESTADOS.join(',')}):`);
  r.panel.estados_presentes = (await leer()).split(',').map(x => x.trim().toUpperCase()).filter(Boolean);
  escribir('¿Hay al menos una condición con alerta activa visible? (s/n):');
  r.panel.alerta_activa_visible = /^s/i.test((await leer()).trim());
  for (;;) {
    escribir('Código del participante (Pxx) o vacío para terminar:');
    const codigo = (await leer()).trim();
    if (!codigo) break;
    escribir('¿Perfil Productor sin conocimiento técnico? (s/n):');
    const perfil = /^s/i.test((await leer()).trim());
    r.participantes.push({ codigo, perfil_productor: perfil, conocimiento_tecnico: !perfil });
    for (;;) {
      escribir(`[${codigo}] Variable y estado presentado "variable;ESTADO" o vacío para el siguiente participante:`);
      const linea = (await leer()).trim();
      if (!linea) break;
      const [variable, estado] = linea.split(';').map(x => x.trim());
      escribir('Enter al mostrar la variable…'); await leer(); const t0 = reloj();
      escribir('Enter cuando el participante indique el estado…'); await leer(); const t1 = reloj();
      escribir('Estado identificado por el participante (vacío si no lo identificó):');
      const identificado = (await leer()).trim().toUpperCase() || null;
      escribir('¿Requirió información técnica del sensor? (s/n):');
      const tecnica = /^s/i.test((await leer()).trim());
      r.ensayos.push({ participante: codigo, variable, estado_presentado: String(estado || '').toUpperCase(), estado_identificado: identificado, tiempo_s: Math.round((t1 - t0) / 10) / 100, requirio_informacion_tecnica: tecnica, cronometro: 'terminal del moderador' });
    }
  }
  return r;
}

function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const fuente = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const plantilla = JSON.parse(fs.readFileSync(PLANTILLA, 'utf8'));
  const futuras = { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] };
  ck('Matriz: TC-M03-205 (prueba manual controlada)', CASOS.join() === 'TC-M03-205');
  ck('Criterio de la matriz: cuatro estados, alerta activa y ≤ 5 s', ESTADOS.join() === 'VERDE,AMARILLO,ROJO,GRIS' && LIMITE_S === 5);
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza la ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }, { roles: [], frontend: true }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, futuras, { roles: [], frontend: true }).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ...futuras, ambiente: 'DEV' }, { roles: [], frontend: true }).ok);
  ck('Plantilla de registro válida y sin datos personales', precondiciones(plantilla).find(a => /datos personales/.test(a.nombre))?.ok === true && Array.isArray(plantilla.ensayos));
  ck('La plantilla vacía no aprueba (bloquea)', veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true, aserciones: evaluarRegistro(plantilla).aserciones }).grupo === 'BLOQUEADO');
  ck('Sin conexiones: no usa fetch, Newman ni Cypress', !new RegExp(['fetch', 'Real', '|newman', 'Modulo|cypress', 'Modulo|sandbox\\('].join('')).test(fuente.split('function local')[0]));
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis librería', spawnSync(process.execPath, ['--check', path.join(DIR, 'monitoreo_lib.mjs')]).status === 0);
  ck('Sin carpetas RESULTADOS de construcción', !fs.existsSync(path.join(DIR, 'RESULTADOS')) && !fs.readdirSync(DIR).some(x => /^EvaluacionV\d+$/.test(x)));
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD].filter(x => x?.length > 4);
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), PLANTILLA, path.join(DIR, 'monitoreo_lib.mjs')].every(f => !secretos.some(s => fs.readFileSync(f, 'utf8').includes(s))));
  ck('Pruebas unitarias locales', spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g105.mjs')], { encoding: 'utf8' }).status === 0);
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G105 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}

async function ejecutar(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const gate = autorizar(v, a, { roles: [], frontend: true });
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.motivos.join('; ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) { console.error('Indique --tipo evaluacion|reintento'); return 2; }
  let registro;
  if (a.registro) {
    try { registro = JSON.parse(fs.readFileSync(path.resolve(a.registro), 'utf8')); } catch (e) { console.error(`Registro ilegible: ${e.message}`); return 2; }
  } else {
    const rl = readline.createInterface({ input: process.stdin });
    const it = rl[Symbol.asyncIterator]();
    registro = await capturar({ leer: async () => (await it.next()).value ?? '', escribir: x => console.log(x), reloj: () => performance.now() });
    rl.close();
  }
  const n = version(DIR, a.tipo, a.version);
  const run = runId(GRUPO, n, sello());
  const base = carpetaResultados(DIR, n), out = path.join(base, run);
  fs.mkdirSync(base, { recursive: true }); fs.mkdirSync(out);
  const limpiar = redactor([v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD]);
  const { aserciones, resumen } = evaluarRegistro(registro);
  const ev = { grupo: GRUPO, rf: 'RF-58', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'CONCLUIDA', tipo_prueba: 'manual controlada (moderada)', autorizacion: a.autorizacion, origen_registro: a.registro ? 'registro en papel transcrito a la plantilla' : 'captura cronometrada en la terminal del moderador', datos: { sesion: registro.sesion, panel: registro.panel, resumen }, registro, aserciones, bloqueos: {}, dependencias: [], sandbox: { rollback: true, nota: 'sin escrituras del ejecutor: no aplica sandbox' }, inicio: new Date().toISOString() };
  ev.veredicto = veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: ev.estado, rollback: true, aserciones, bloqueos: ev.bloqueos });
  ev.fin = new Date().toISOString();
  fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  fs.writeFileSync(path.join(out, nombreInforme(GRUPO, n)), limpiar(informe({ grupo: GRUPO, n, run, ev, casos: CASOS, extra: `\n## Sesión de usabilidad\nParticipantes: ${resumen.participantes} · Ensayos: ${resumen.ensayos} · Superados: ${resumen.superados} · Tiempo máximo: ${resumen.tiempo_max_s} s (límite ${LIMITE_S} s).\n` })));
  console.log(`${GRUPO}: ${ev.veredicto.grupo} (propuesto) — ${out}`); return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
