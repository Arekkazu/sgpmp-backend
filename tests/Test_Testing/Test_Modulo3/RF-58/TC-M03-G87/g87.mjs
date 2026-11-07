#!/usr/bin/env node
// TC-M03-G87 (RF-58) — evaluación completa API + UI con un solo comando.
//
//   node g87.mjs --comprobar                                  local: archivos, configuración y versión; sin red
//   node g87.mjs --autorizacion "<ref>" [--tipo evaluacion|reintento]
//
// Requiere QA_AUTORIZADO=SI (variable del proceso o .env.qa) y una referencia de autorización.
//
// Datos: no crea sensores ni dispositivos. Usa un área persistente de la finca compartida con especie y
// umbral RF-17 de Temperatura Ambiental, un sensor existente calibrado (S1) y uno sin calibración (S2).
// Dentro de un RUN del sandbox los reasigna a esa área (RF-22) y les envía lecturas por la ingesta
// oficial (RF-53); al cerrar el RUN todo se revierte y se comprueba por API.
//
// Identidades: el Administrador solo lee fuera del RUN (descubrimiento y verificación del rollback);
// Productor e Ingeniero operan dentro del RUN (Newman); las cuentas UI solo las usa Cypress. Ninguna
// identidad que haya operado dentro del RUN vuelve a usarse fuera de él antes del cierre.

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { createHash } from 'node:crypto';
import { sanearArtefacto } from './lib/g87_seguridad.mjs';
import { valoresS1, uiHabilitada, comprobacionesUiFaltantes, indicadorCalibracion, estadoGrupoG87 } from './lib/g87_preparacion.mjs';
import { chromeLocal, ejecutarCypressControlado, TIMEOUT_UI_MS } from './lib/g87_cypress_runner.mjs';
import { cerrarYVerificar, cierreUnico, instalarSenales, estadoMarcador } from './lib/g87_cierre.mjs';
import { generarInforme, oficialidad, validarResultadoLocal, requeridasFaltantes, problemaCypress } from './lib/g87_informe.mjs';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '..', '..', '..', '..', '..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const API_FRONT = 'https://api.inmero.co/api-sgpmp-test';
const FRONT = 'https://api.inmero.co/sigab-test';
const dirResultados = (version) => version === 1 ? path.join(DIR, 'Resultados') : path.join(DIR, `EvaluacionV${version}`, 'Resultados');
const nombreInforme = (version) => version === 1 ? 'TC-M03-G87_resultado.md' : `TC-M03-G87_reevaluacion_V${version}.md`;
const VARIABLE = { nombre: 'TEMPERATURA_AMBIENTAL', id: 9 };
const NUEVOS_SENSORES = 1; // cupo mínimo para S2; S1 necesita un cupo adicional
function gitLocal() {
  // Metadatos locales en modo lectura; no ejecuta Git ni infiere el commit desplegado.
  try {
    const git = path.join(RAIZ, '.git');
    const head = fs.readFileSync(path.join(git, 'HEAD'), 'utf8').trim();
    const ref = /^ref: (refs\/heads\/[\w./-]+)$/.exec(head);
    const commit = ref ? fs.readFileSync(path.join(git, ref[1]), 'utf8').trim() : head;
    return { rama: ref ? ref[1].slice('refs/heads/'.length) : 'HEAD separado',
      commit: /^[a-f0-9]{40}$/i.test(commit) ? commit : 'sin determinar' };
  } catch { return { rama: 'sin determinar', commit: 'sin determinar' }; }
}

export function regenerarInforme(runNombre, salidaSolicitada) {
  globalThis.fetch = () => { throw new Error('sin red en --regenerar-informe'); };
  const m = /^RUN-G87-V(\d+)-\d{8}-\d{6}$/.exec(runNombre ?? '');
  if (!m || !salidaSolicitada) throw new Error('Indique RUN-id válido y --salida.');
  const salida = path.resolve(salidaSolicitada);
  const dirSalida = fs.realpathSync(path.dirname(salida));
  if (![fs.realpathSync(DIR), path.join(fs.realpathSync(DIR), '_paquete_responsables')].includes(dirSalida)
    || path.extname(salida) !== '.md')
    throw new Error('La salida debe ser un Markdown nuevo en la raíz del grupo o _paquete_responsables, fuera de Resultados y EvaluacionVn.');
  const dir = path.join(dirResultados(Number(m[1])), runNombre);
  const realDir = fs.realpathSync(dir);
  const informeOriginal = path.join(realDir, nombreInforme(Number(m[1])));
  const r = JSON.parse(fs.readFileSync(path.join(realDir, 'resultado.json'), 'utf8'));
  if (r.run_id !== runNombre || r.version !== Number(m[1]) || r.grupo !== 'TC-M03-G87')
    throw new Error('Los identificadores de resultado.json no coinciden con el RUN.');
  const archivos = r.evidencias ?? [];
  if (!archivos.includes('resultado.json') || !archivos.some((x) => x.startsWith('newman/') && x.endsWith('.json'))
    || !archivos.some((x) => x.startsWith('cypress/') && x.endsWith('.png')))
    throw new Error('Faltan referencias a evidencias Newman o Cypress.');
  for (const nombre of archivos) {
    const real = fs.realpathSync(path.join(realDir, nombre));
    if (!real.startsWith(realDir + path.sep)) throw new Error('Evidencia fuera del RUN.');
  }
  for (const nombre of archivos.filter((x) => x.startsWith('newman/') && x.endsWith('.json')))
    JSON.parse(fs.readFileSync(path.join(realDir, nombre), 'utf8'));
  const hashOriginal = createHash('sha256').update(fs.readFileSync(informeOriginal)).digest('hex');
  // El borrador se instala dentro del RUN: los enlaces deben ser relativos a ese destino.
  const prefijoEvidencia = '';
  const rutaMarcador = path.join(realDir, 'run-pendiente.json');
  const marcadorOriginal = fs.existsSync(rutaMarcador) ? JSON.parse(fs.readFileSync(rutaMarcador, 'utf8')) : null;
  const anterior = fs.readFileSync(informeOriginal, 'utf8');
  const metadatos = /Rama local: ([^;\n]+); commit local: ([^\.\n]+)\./.exec(anterior);
  const gitAnterior = metadatos ? { rama: metadatos[1], commit: metadatos[2] } : { rama: 'sin determinar', commit: 'sin determinar' };
  const texto = generarInforme(r, CASOS, { hashOriginal, gitLocal: gitAnterior, prefijoEvidencia, marcadorOriginal });
  const errores = validarResultadoLocal(r, [...archivos, nombreInforme(r.version)], null, texto);
  if (errores.length) throw new Error(`Resultado incoherente: ${errores.join('; ')}`);
  fs.writeFileSync(salida, texto, { flag: 'wx' });
  return salida;
}
function reporterHtmlDisponible() {
  return fs.existsSync(path.join(path.dirname(process.execPath), 'node_modules', 'newman-reporter-htmlextra'));
}
const newmanDisponible = () => fs.existsSync(path.join(path.dirname(process.execPath), 'node_modules', 'newman'));
export function versionNewmanLocal() {
  try {
    const paquete = JSON.parse(fs.readFileSync(path.join(path.dirname(process.execPath), 'node_modules', 'newman', 'package.json'), 'utf8'));
    return /^\d+\.\d+\.\d+/.test(paquete.version) ? paquete.version : null;
  } catch { return null; }
}
export function alcanceV2(contrato) {
  if (!contrato || contrato.version < 2 || !contrato.contexto?.alcance_reevaluacion) return null;
  const alcance = contrato.contexto.alcance_reevaluacion;
  return { ...(typeof alcance === 'object' ? alcance : { descripcion: alcance }),
    version_anterior: alcance.version_anterior ?? contrato.contexto.version_anterior ?? null };
}

// Comprobaciones de los casos originales (Casos_Prueba(Modulo3 Agrupado).csv, fila TC-M03-G87).
const CASOS = {
  'TC-M03-168': { titulo: 'Última lectura válida de cada sensor activo, ignorando una lectura posterior FUERA_DE_RANGO', ui: false,
    esperado: 'HTTP 200; ultimo_valor, ultima_unidad y ultimo_timestamp_captura de la última LECTURA_VALIDA, no de la posterior inválida.' },
  'TC-M03-177': { titulo: 'La lectura FUERA_DE_RANGO no es valor operativo del Productor y la anomalía sigue visible', ui: true,
    esperado: 'Se conserva la última LECTURA_VALIDA (25) como referencia y la anomalía permanece visible (ROJO/ícono).' },
  'TC-M03-178': { titulo: 'Presentación de ERROR_CALIBRACION diferenciada entre Productor e Ingeniero de Campo', ui: true,
    esperado: 'Productor: no es lectura operativa, sin alerta ni datos técnicos. Ingeniero: identifica el error y ve que requiere calibración. Sensor visible.' },
};

// ---------------------------------------------------------------------------
// Configuración, versión y barrera (sin red)
// ---------------------------------------------------------------------------

function leerEnv() {
  const archivo = path.join(RAIZ, '.env.qa');
  const v = {};
  if (fs.existsSync(archivo)) for (const l of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = l.match(/^\s*([A-Z0-9_]+)\s*=(.*)$/);
    if (m) v[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  for (const k of Object.keys(v)) if (process.env[k]) v[k] = process.env[k];
  if (process.env.BROKER_SERVICE_TOKEN !== undefined) v.BROKER_SERVICE_TOKEN = process.env.BROKER_SERVICE_TOKEN;
  if (process.env.QA_AUTORIZADO) v.QA_AUTORIZADO = process.env.QA_AUTORIZADO;
  return v;
}
const clave = (V, k) => V[k] || V.QA_COMMON_PASSWORD || '';
const cuentas = (V) => ({
  admin: { correo: V.QA_ADMIN_EMAIL, clave: clave(V, 'QA_ADMIN_PASSWORD') },
  prod: { correo: V.QA_PROD_EMAIL, clave: V.QA_PROD_PASSWORD },
  eng: { correo: V.QA_ENG_EMAIL, clave: clave(V, 'QA_ENG_PASSWORD') },
  ui_prod: { correo: V.QA_PROD_UI_EMAIL, clave: V.QA_PROD_UI_PASSWORD },
  ui_eng: { correo: V.QA_ENG_UI_EMAIL, clave: V.QA_ENG_UI_PASSWORD },
});

export const rolesParaOperacion = (version, operacion) => operacion === 'reevaluar' && version >= 2
  ? ['admin', 'ui_prod', 'ui_eng'] : ['admin', 'prod', 'eng', 'ui_prod', 'ui_eng'];

export function alcanceCuenta(perfil, rol, finca) {
  const esperado = rol === 'prod' ? 'Productor' : 'Ingeniero de Campo';
  const nombre = String(perfil?.nombre_rol ?? '').trim();
  const rol_correcto = nombre === esperado;
  const finca_asignada = Array.isArray(perfil?.fincas)
    && perfil.fincas.some((f) => Number(f.id_finca) === Number(finca));
  return { rol_correcto, finca_asignada, motivo: !rol_correcto
    ? `/usuarios/me: se esperaba rol ${esperado}; rol observado ${nombre || 'no disponible'}.`
    : !finca_asignada ? `/usuarios/me: ${esperado} sin finca ${finca} del escenario.` : null };
}

function faltantes(V, ref, roles) {
  const m = [];
  if (V.QA_AUTORIZADO !== 'SI') m.push(`QA_AUTORIZADO=${V.QA_AUTORIZADO || '(vacío)'}; se requiere SI.`);
  if (!ref || ref.length < 8) m.push('Falta --autorizacion "<referencia>".');
  if (String(V.SIGAB_API_TEST_BASE || '').replace(/\/+$/, '') !== API) m.push('SIGAB_API_TEST_BASE no es el API de TEST.');
  if (!V.QA_SANDBOX_SECRET) m.push('Falta QA_SANDBOX_SECRET.');
  if (!V.BROKER_SERVICE_TOKEN?.trim()) m.push('BLOQUEO_DATOS: falta BROKER_SERVICE_TOKEN para Authorization Bearer de ingesta; no se enviará ninguna petición.');
  const c = cuentas(V);
  for (const rol of roles) if (!c[rol].correo || !c[rol].clave) m.push(`Faltan correo o contraseña de ${rol}.`);
  const correos = roles.map((rol) => String(c[rol].correo || '').toLowerCase());
  if (new Set(correos).size !== correos.length) m.push('Las cuentas requeridas deben ser distintas.');
  return m;
}

/** El lanzador autoriza el intento; el historial de carpetas no decide versiones. */
export function versionSiguiente(tipo) {
  if (!['evaluacion', 'reintento'].includes(tipo)) return { error: 'Tipo inválido.' };
  return { version: 1, intento: null };
}

// ---------------------------------------------------------------------------
// HTTP con bitácora saneada
// ---------------------------------------------------------------------------

const bitacora = [];
let secretos = [];
const sanear = (t) => sanearArtefacto(String(t ?? ''), secretos);
/** `run` = petición dentro del RUN; `secreto` solo = ruta de control del sandbox. */
async function api(metodo, ruta, { token, run, secreto, cuerpo, base = API, etiqueta } = {}) {
  const h = { Accept: 'application/json' };
  if (token) h.Authorization = `Bearer ${token}`;
  if (cuerpo) h['Content-Type'] = 'application/json';
  if (run) { h['X-Test-Run-Id'] = run.id; h['X-Sandbox-Secret'] = run.secreto; }
  else if (secreto) h['X-Sandbox-Secret'] = secreto;
  const inicio = Date.now();
  let status = 0; let json = null; let eco = null; let error = null;
  try {
    const r = await fetch(base + ruta, { method: metodo, headers: h, body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      redirect: 'manual', signal: AbortSignal.timeout(30000) });
    status = r.status; eco = r.headers.get('x-test-run-id');
    const t = await r.text(); try { json = JSON.parse(t); } catch { json = t.slice(0, 300); }
  } catch (e) { error = e.name === 'TimeoutError' ? 'TIMEOUT 30 s' : 'SIN RESPUESTA'; }
  bitacora.push({ etiqueta, metodo, ruta, en_run: !!run?.id, status, eco_run: run?.id ? eco === run.id : undefined,
    ms: Date.now() - inicio, error: error ?? undefined, respuesta: sanear(JSON.stringify(json)).slice(0, 600) });
  return { status, json, eco, error };
}

// ---------------------------------------------------------------------------
// Ejecución
// ---------------------------------------------------------------------------

class Detener extends Error {}

async function evaluar({ ref, tipo, contrato = null }) {
  const V = leerEnv();
  const ver = contrato ? { version: contrato.version, intento: contrato.intento } : versionSiguiente(tipo);
  if (ver.error) { console.error(ver.error); return 2; }
  const escenarioV2 = contrato?.operacion === 'reevaluar' && ver.version >= 2;
  const motivos = faltantes(V, ref, rolesParaOperacion(ver.version, contrato?.operacion));
  if (motivos.length) {
    const estado = V.QA_AUTORIZADO === 'SI' ? 'BLOQUEADO EN PRECONDICIONES' : 'NO AUTORIZADO';
    console.error(`${estado}. Ninguna solicitud remota.\n- ${motivos.join('\n- ')}`);
    return 2;
  }
  if (!newmanDisponible() || !reporterHtmlDisponible()) { console.error('Newman o su reporter HTML no disponibles; ninguna solicitud remota.'); return 2; }
  const c = cuentas(V);
  secretos = [V.QA_SANDBOX_SECRET, V.BROKER_SERVICE_TOKEN, ...Object.values(c).map((x) => x.clave)];

  const sello = new Date().toISOString().replace(/[-:]/g, '').replace('T', '-').replace(/\..*/, '');
  const runId = contrato ? contrato.runId.slice(4) : `G87-V${ver.version}-${sello}`;
  const baseResultados = dirResultados(ver.version);
  fs.mkdirSync(baseResultados, { recursive: true });
  const dir = path.join(baseResultados, `RUN-${runId}`);
  if (contrato) {
    if (dir !== contrato.directorio || !fs.existsSync(path.join(dir, 'contexto_operacion.json'))
      || fs.existsSync(path.join(dir, 'resultado.json'))) { console.error('RUN reservado incoherente o ya usado.'); return 2; }
  } else fs.mkdirSync(dir); // compatibilidad heredada
  const r = { grupo: 'TC-M03-G87', rf: 'RF-58', version: ver.version, intento: ver.intento, tipo, referencia: ref,
    run_id: `RUN-${runId}`, ambiente: 'TEST', herramientas: { node: process.version, newman: versionNewmanLocal() },
    inicio: new Date().toISOString(), operacion: contrato?.operacion?.toUpperCase() ?? tipo.toUpperCase(),
    alcance_reevaluacion: alcanceV2(contrato),
    consume_version: false, estado: 'EN_CURSO', datos: {}, comprobaciones: [], casos: {},
    cierre: {}, incidencias: [] };
  const guardar = () => fs.writeFileSync(path.join(dir, 'resultado.json'), sanear(JSON.stringify({ ...r, bitacora }, null, 2)));
  const run = { id: runId, secreto: V.QA_SANDBOX_SECRET };
  const tokens = {};
  const respuestasLoginUi = {};
  const temporales = [];
  let runAbierto = false;
  const marcadorRuta = path.join(dir, 'run-pendiente.json');
  const actualizarMarcador = (extra = {}) => fs.writeFileSync(marcadorRuta, sanear(JSON.stringify({
    run_id: r.run_id, referencia: ref, fecha_apertura: r.inicio, estado: 'PENDIENTE',
    efectos_previstos: ['reasociación de sensores existentes', 'ingesta HTTP de lecturas en RUN',
      'sesiones y notificaciones de login fuera del RUN'], datos: {
      area: r.datos.area, ocupacion_inicial: r.datos.ocupacion_inicial, s1: r.datos.s1,
      s2: r.datos.s2, bloqueo_s1: r.datos.bloqueo_s1, bloqueo_s2: r.datos.bloqueo_s2, lecturas: r.datos.lecturas,
      ids_telemetria: r.datos.ids_telemetria ?? [] }, ...extra }, null, 2)));
  const abortarUi = new AbortController();
  const cerrarSandbox = cierreUnico(async () => {
    if (!runAbierto) return;
    const cierre = await cerrarYVerificar({ runId, secreto: V.QA_SANDBOX_SECRET, datos: r.datos, tokens,
      credenciales: c, solicitar: api, onToken: (tk) => secretos.push(tk) });
    r.cierre.run = cierre.run;
    r.cierre.rollback = cierre.rollback;
    r.incidencias.push(...cierre.errores.map((x) => `ERROR_QA: ${x}`));
    if (!cierre.rollback.verificado) r.incidencias.push('Rollback NO verificado: revisar cierre.rollback.');
    const previo = JSON.parse(fs.readFileSync(marcadorRuta, 'utf8'));
    fs.writeFileSync(marcadorRuta, sanear(JSON.stringify({ ...previo, run_id: r.run_id, referencia: ref,
      estado: estadoMarcador(cierre),
      cierre_http: cierre.run.cierre_http, verificado: cierre.rollback.verificado, fecha: new Date().toISOString() }, null, 2)));
    guardar();
  });
  const retirarSenales = instalarSenales(() => { abortarUi.abort(); return cerrarSandbox(); });

  try {
    // 1. Sesiones fuera del RUN.
    const rolApi = { prod: escenarioV2 ? 'ui_prod' : 'prod', eng: escenarioV2 ? 'ui_eng' : 'eng' };
    for (const rol of escenarioV2 ? ['admin', 'ui_prod', 'ui_eng'] : ['admin', 'prod', 'eng']) {
      const l = await api('POST', '/sesiones/', { cuerpo: { correo_electronico: c[rol].correo, contrasena: c[rol].clave }, etiqueta: `Login ${rol}` });
      if (l.status !== 200 || !l.json?.token) throw new Detener(`Login ${rol}: HTTP ${l.status}${l.error ? ` (${l.error})` : ''}.`);
      tokens[rol] = l.json.token; secretos.push(l.json.token);
      if (escenarioV2 && (rol === 'ui_prod' || rol === 'ui_eng')) respuestasLoginUi[rol] = l.json;
    }
    const me = {};
    for (const rol of ['prod', 'eng']) {
      const perfil = await api('GET', '/usuarios/me', { token: tokens[rolApi[rol]], etiqueta: `Perfil ${rolApi[rol]}` });
      if (perfil.status !== 200) throw new Detener(`BLOQUEO_ENTORNO: perfil ${rol}, HTTP ${perfil.status}; alcance de fincas no verificable.`);
      me[rol] = perfil.json;
    }
    const fincas = (me.prod?.fincas ?? []).map((f) => f.id_finca);
    const fincasIngeniero = (me.eng?.fincas ?? []).map((f) => f.id_finca);
    const alcance = escenarioV2 ? { prod: alcanceCuenta(me.prod, 'prod', 184), eng: alcanceCuenta(me.eng, 'eng', 184) } : null;

    // 2. Descubrimiento (Administrador, fuera del RUN): área con umbral apto y sensores existentes.
    const leer = async (ruta, etiqueta) => {
      const respuesta = await api('GET', ruta, { token: tokens.admin, etiqueta });
      if ([401, 403].includes(respuesta.status) || respuesta.status >= 500)
        throw new Detener(`BLOQUEO_ENTORNO: ${etiqueta}, HTTP ${respuesta.status}.`);
      return respuesta;
    };
    let area = null; let umbral = null;
    for (const f of escenarioV2 ? [184] : fincas) {
      for (const a of (await leer(`/configuracion/infraestructuras?finca_id=${f}`, `Áreas de finca ${f}`)).json?.items ?? []) {
        if (!a.es_activo || !a.especie_id) continue;
        if (escenarioV2 && Number(a.id_infraestructura) !== 349) continue;
        const u = ((await leer(`/configuracion/umbrales?id_especie=${a.especie_id}`, `Umbrales especie ${a.especie_id}`)).json?.items ?? [])
          .find((x) => x.es_activo && Number(x.id_variable_ambiental) === VARIABLE.id && (escenarioV2
            ? Number(x.valor_min) === 15 && Number(x.valor_max) === 30
            : Number(x.valor_min) <= 23 && Number(x.valor_max) >= 25 && Number(x.valor_max) < 60));
        if (!u) continue;
        const ocupacion = (await leer(`/iot/monitoreo/dashboard?id_infraestructura=${a.id_infraestructura}&por_pagina=50`, `Ocupación área ${a.id_infraestructura}`)).json?.total;
        if (Number.isInteger(ocupacion) && ocupacion + NUEVOS_SENSORES <= 50) { area = { ...a, ocupacion }; umbral = u; break; }
      }
      if (area) break;
    }
    if (!area) throw new Detener(escenarioV2
      ? 'BLOQUEO_DATOS: el área 349 con umbral activo 15–30 °C y cupo no está disponible en la finca 184.'
      : `No hay área activa con especie, umbral apto de Temperatura Ambiental y cupo en el dashboard de las fincas del Productor ${JSON.stringify(fincas)}.`);
    if (escenarioV2 && Number(area.id_finca) !== 184)
      throw new Detener('BLOQUEO_DATOS: el área 349 no pertenece a la finca 184 del escenario V2.');
    const idsArea = new Set(((await leer(`/configuracion/infraestructuras?finca_id=${area.id_finca}`, 'Áreas de la finca')).json?.items ?? []).map((a) => a.id_infraestructura));
    const dispositivos = ((await leer('/configuracion/dispositivos-iot', 'Dispositivos')).json?.items ?? [])
      .filter((d) => d.es_activo && d.serial && idsArea.has(d.id_infraestructura))
      .sort((a, b) => Number(b.id_infraestructura === area.id_infraestructura) - Number(a.id_infraestructura === area.id_infraestructura)
        || a.id_dispositivo_iot - b.id_dispositivo_iot);
    // S1: calibración vigente identidad (ganancia 1, offset 0): el valor operativo mostrado es el leído (25).
    // S2: sin ninguna calibración, para que la ingesta clasifique ERROR_CALIBRACION.
    let s1 = null; let s2 = null;
    for (const d of dispositivos) {
      for (const s of ((await leer(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`, `Sensores del dispositivo ${d.id_dispositivo_iot}`)).json?.items ?? []).filter((x) => x.es_activo)) {
        if (escenarioV2 && !((Number(s.id_sensores) === 552 && Number(d.id_dispositivo_iot) === 357)
          || (Number(s.id_sensores) === 77 && Number(d.id_dispositivo_iot) === 266))) continue;
        const cals = (await leer(`/configuracion/sensores/${s.id_sensores}/calibraciones`, `Calibraciones del sensor ${s.id_sensores}`)).json;
        const vigente = (cals?.items ?? []).filter((x) => x.id_dispositivo_iot === d.id_dispositivo_iot)
          .sort((x, y) => Date.parse(y.fecha_calibracion) - Date.parse(x.fecha_calibracion))[0];
        const sensor = { id: s.id_sensores, dev: d.id_dispositivo_iot, serial: d.serial, nombre: s.nombre,
          calibracion: vigente ? { id: vigente.id_calibracion, ganancia: Number(vigente.ganancia), offset: Number(vigente.offset),
            fecha: vigente.fecha_calibracion } : null };
        if (!s1 && vigente && Number(vigente.ganancia) === 1 && Number(vigente.offset) === 0) s1 = sensor;
        else if (!s2 && cals?.total === 0) s2 = sensor;
        if (s1 && s2) break;
      }
      if (s1 && s2) break;
    }
    let bloqueoS2 = s2 ? null : `BLOQUEO_DATOS: falta sensor S2 existente sin calibración en la finca ${area.id_finca}.`;
    let bloqueoS1 = s1 ? null : 'BLOQUEO_DATOS: no se encontró sensor S1 existente con calibración identidad.';
    for (const [nombre, s] of [['S1', s1], ['S2', s2]].filter(([, sensor]) => sensor)) {
      if (typeof s.serial !== 'string' || !s.serial.trim() || s.serial.length > 100) {
        const motivo = `BLOQUEO_DATOS: falta serial válido (1–100 caracteres) del dispositivo ${s.dev} para ${nombre}; no se puede preparar la ingesta.`;
        if (nombre === 'S1') bloqueoS1 = motivo;
        else bloqueoS2 = motivo;
      }
    }
    for (const s of [s1, s2].filter(Boolean)) {
      const asoc = (await leer(`/configuracion/sensores/${s.id}/asociaciones`, `Asociación del sensor ${s.id}`)).json?.items ?? [];
      s.area_original = asoc.find((x) => !x.fecha_finalizacion)?.id_infraestructura ?? null;
      if (!s.area_original) {
        const motivo = `BLOQUEO_DATOS: sensor ${s.id} sin asociación activa verificable para comprobar el rollback.`;
        if (s === s1) bloqueoS1 = motivo;
        else bloqueoS2 = motivo;
      }
      if (typeof s.serial === 'string') secretos.push(s.serial);
    }

    // RF-53 clasifica con la infraestructura del DISPOSITIVO; la asociación del sensor
    // solo determina en qué dashboard se ve. Estas tres consultas preceden al RUN.
    if (!bloqueoS1 && area.ocupacion + 2 > 50) bloqueoS1 = `BLOQUEO_DATOS: el área ${area.id_infraestructura} no tiene cupo para visualizar S1 y S2.`;
    let idInfraDev = null; let idEspecieDev = null; let umbralDispositivo = null;
    try { if (bloqueoS1) throw new Detener(bloqueoS1);
    const detalleDev = await leer(`/configuracion/dispositivos-iot/${s1.dev}`, `Infraestructura del dispositivo S1 ${s1.dev}`);
    if (detalleDev.status !== 200) throw new Detener(`BLOQUEO_DATOS: dispositivo S1 ${s1.dev}, detalle HTTP ${detalleDev.status}; no se conoce su infraestructura.`);
    const devS1 = detalleDev.json?.data ?? detalleDev.json;
    idInfraDev = Number(devS1?.id_infraestructura);
    if (!Number.isInteger(idInfraDev) || idInfraDev <= 0)
      throw new Detener(`BLOQUEO_DATOS: dispositivo S1 ${s1.dev} sin id_infraestructura verificable.`);
    const detalleInfra = await leer(`/configuracion/infraestructuras/${idInfraDev}`, `Infraestructura del dispositivo S1 ${idInfraDev}`);
    if (detalleInfra.status !== 200) throw new Detener(`BLOQUEO_DATOS: infraestructura ${idInfraDev} del dispositivo S1 ${s1.dev}, detalle HTTP ${detalleInfra.status}.`);
    const infraDev = detalleInfra.json?.data ?? detalleInfra.json;
    idEspecieDev = Number(infraDev?.especie_id);
    if (!Number.isInteger(idEspecieDev) || idEspecieDev <= 0)
      throw new Detener(`BLOQUEO_DATOS: infraestructura ${idInfraDev} del dispositivo S1 ${s1.dev} sin especie_id verificable.`);
    const consultaUmbral = await leer(`/configuracion/umbrales?id_especie=${idEspecieDev}`, `Umbrales especie del dispositivo S1 ${idEspecieDev}`);
    if (consultaUmbral.status !== 200) throw new Detener(`BLOQUEO_DATOS: umbrales de especie ${idEspecieDev}, HTTP ${consultaUmbral.status}.`);
    const umbralS1 = (consultaUmbral.json?.items ?? []).find((x) => x.es_activo &&
      (x.id_especie == null || Number(x.id_especie) === idEspecieDev) && Number(x.id_variable_ambiental) === VARIABLE.id &&
      x.valor_min != null && x.valor_max != null && Number.isFinite(Number(x.valor_min)) && Number.isFinite(Number(x.valor_max)));
    if (!umbralS1) throw new Detener(`BLOQUEO_DATOS: especie ${idEspecieDev} de infraestructura ${idInfraDev} del dispositivo S1 ${s1.dev} sin umbral ambiental activo de TEMPERATURA_AMBIENTAL.`);
    if (escenarioV2 && (Number(umbralS1.valor_min) !== 15 || Number(umbralS1.valor_max) !== 30))
      throw new Detener('BLOQUEO_DATOS: el umbral del dispositivo S1 no corresponde a 15–30 °C del escenario V1.');
    umbralDispositivo = { id: umbralS1.id_umbral_ambiental, min: Number(umbralS1.valor_min), max: Number(umbralS1.valor_max) };
    } catch (e) { if (!(e instanceof Detener) || e.message.startsWith('BLOQUEO_ENTORNO')) throw e; bloqueoS1 = e.message; }
    r.datos = { finca: area.id_finca, area: area.id_infraestructura, especie: area.especie_id,
      visibilidad_por_rol: { prod: { finca_asignada: fincas.some((id) => Number(id) === Number(area.id_finca)),
          rol_correcto: alcance?.prod.rol_correcto ?? null },
        eng: { finca_asignada: fincasIngeniero.some((id) => Number(id) === Number(area.id_finca)),
          rol_correcto: alcance?.eng.rol_correcto ?? null } },
      umbral_dashboard: { id: umbral.id_umbral_ambiental, min: Number(umbral.valor_min), max: Number(umbral.valor_max) },
      umbral: umbralDispositivo, infraestructura_dispositivo_s1: idInfraDev, especie_dispositivo_s1: idEspecieDev,
      ocupacion_inicial: area.ocupacion, s1: s1 ? { id: s1.id, dispositivo: s1.dev, nombre: s1.nombre, area_original: s1.area_original, calibrado: true } : null,
      s2: s2 ? { id: s2.id, dispositivo: s2.dev, nombre: s2.nombre, area_original: s2.area_original, calibrado: false } : null };
    if (s1) r.datos.s1.calibracion = s1.calibracion;
    if (escenarioV2) {
      r.datos.cuentas_api = 'cuentas UI del mismo rol (Productor e Ingeniero de Campo)';
      r.datos.alcance_cuentas = alcance;
    }
    if (s1) r.datos.s1.reasociacion_necesaria = Number(s1.area_original) !== Number(area.id_infraestructura);
    if (s1) r.datos.s1.motivo_reasociacion = r.datos.s1.reasociacion_necesaria
      ? `La asociación activa del sensor apunta al área ${s1.area_original}; el Productor consulta el dashboard del área ${area.id_infraestructura}.`
      : 'La asociación activa ya apunta al área del dashboard del Productor.';
    guardar();

    // Valor anómalo: físicamente válido (la ingesta solo rechaza como ERROR_SENSOR lo que sale del rango
    // físico de modulo9.variables_ambientales) y fuera del umbral RF-17 de la especie del dispositivo.
    const t = (min) => new Date(Date.now() - min * 60000).toISOString();
    const variable = ((await leer('/configuracion/variables-ambientales', 'Rango físico de la variable')).json?.items ?? [])
      .find((x) => Number(x.id_variable_ambiental) === VARIABLE.id && x.es_activo !== false);
    const fisico = variable ? [Number(variable.valor_fisico_min), Number(variable.valor_fisico_max)] : null;
    r.datos.rango_fisico = fisico;
    let valoresS1Run = {};
    if (!bloqueoS1) try {
      valoresS1Run = valoresS1(r.datos.umbral, fisico);
      const ajustar = (x) => x * s1.calibracion.ganancia + s1.calibracion.offset;
      r.datos.valores_ajustados_s1 = Object.fromEntries(Object.entries(valoresS1Run).map(([k, v]) => [k, ajustar(v)]));
      const u = r.datos.umbral;
      if (!['v_a1', 'v_a2', 'v_a3'].every((k) => u.min <= r.datos.valores_ajustados_s1[k] && r.datos.valores_ajustados_s1[k] <= u.max)
        || (u.min <= r.datos.valores_ajustados_s1.v_fuera && r.datos.valores_ajustados_s1.v_fuera <= u.max))
        throw new Error(`BLOQUEO_DATOS: los valores ajustados de S1 no cumplen el umbral ${u.id}.`);
    } catch (e) { bloqueoS1 = e.message; }
    const valores = { ...valoresS1Run, v_c1: 21.7, v_c2: 22.3 };
    if (!Array.isArray(fisico) || ![valores.v_c1, valores.v_c2].every((x) => fisico[0] <= x && x <= fisico[1]))
      bloqueoS2 = 'BLOQUEO_DATOS: valores de S2 fuera del rango físico; no se puede acreditar ERROR_CALIBRACION.';
    if (bloqueoS1) for (const caso of ['TC-M03-168', 'TC-M03-177']) r.comprobaciones.push({ caso, tipo: 'PRE', id: `PRE-${caso.slice(-3)}-DATOS`, descripcion: 'Escenario S1 verificable', fuente: 'API', ok: false, naturaleza: 'DATOS', obtenido: bloqueoS1 });
    if (bloqueoS2) r.comprobaciones.push({ caso: 'TC-M03-178', tipo: 'PRE', id: 'PRE-178-DATOS',
      descripcion: 'Escenario S2 verificable', fuente: 'API', ok: false, naturaleza: 'DATOS', obtenido: bloqueoS2 });
    r.datos.bloqueo_s1 = bloqueoS1;
    r.datos.bloqueo_s2 = bloqueoS2;

    // 3. RUN: sandbox disponible y apertura con una lectura cuyo eco se exige antes de cualquier escritura.
    const disp = await api('DELETE', `/test-control/runs/${runId}-NO-EXISTE`, { secreto: V.QA_SANDBOX_SECRET, etiqueta: 'Sandbox disponible' });
    if (disp.status !== 404) throw new Detener(`Sandbox no disponible (HTTP ${disp.status}).`);
    if (abortarUi.signal.aborted) throw new Detener('Interrupción antes de abrir RUN.');
    runAbierto = true;
    actualizarMarcador();
    const apertura = await api('GET', '/usuarios/me', { token: tokens[rolApi.eng], run, etiqueta: 'Apertura del RUN (sin escritura)' });
    if (apertura.status !== 200 || apertura.eco !== runId) throw new Detener(`El backend no atendió la petición dentro del RUN (HTTP ${apertura.status}, eco ${apertura.eco === runId}); no se escribe nada.`);
    r.datos.lecturas = { ...valores, ts: { a1: t(6), a2: t(5), a3: t(4), fuera: t(3), c1: t(6), c2: t(5) } };
    actualizarMarcador();
    const envNewman = { qa_autorizado: 'SI', s1_ejecutar: bloqueoS1 ? 'NO' : 'SI', s2_ejecutar: bloqueoS2 ? 'NO' : 'SI', base_url: API, run_id: runId, sandbox_secret: V.QA_SANDBOX_SECRET,
      broker_service_token: V.BROKER_SERVICE_TOKEN,
      tok_admin: tokens.admin, tok_prod: tokens[rolApi.prod], tok_eng: tokens[rolApi.eng], area_id: area.id_infraestructura,
      s1_id: s1?.id ?? '', s1_dev: s1?.dev ?? '', s1_serial: s1?.serial ?? '', s1_reasociar: !bloqueoS1 && r.datos.s1.reasociacion_necesaria ? 'SI' : 'NO',
      s2_id: s2?.id ?? '', s2_dev: s2?.dev ?? '', s2_serial: s2?.serial ?? '', ...valores,
      ts_a1: r.datos.lecturas.ts.a1, ts_a2: r.datos.lecturas.ts.a2, ts_a3: r.datos.lecturas.ts.a3, ts_fuera: r.datos.lecturas.ts.fuera,
      ts_c1: r.datos.lecturas.ts.c1, ts_c2: r.datos.lecturas.ts.c2 };
    const fEnv = path.join(os.tmpdir(), `g87-${process.pid}-env.json`);
    const dirNewman = path.join(dir, 'newman');
    // Crear la carpeta solo cuando el reporte real exista.
    const fRep = path.join(dirNewman, 'newman-TC-M03-G87.json');
    const fHtml = path.join(dirNewman, 'newman-TC-M03-G87.html');
    const tmpNewman = fs.mkdtempSync(path.join(os.tmpdir(), 'g87-newman-'));
    const tmpRep = path.join(tmpNewman, 'report.json');
    const tmpHtml = path.join(tmpNewman, 'report.html');
    temporales.push(fEnv, tmpNewman);
    fs.writeFileSync(fEnv, JSON.stringify({ values: Object.entries(envNewman).map(([key, value]) => ({ key, value: String(value), enabled: true })) }), { mode: 0o600 });
    r.consume_version = true; // desde aquí se ejecutan comprobaciones funcionales
    guardar();
    const cita = (a) => (process.platform === 'win32' && /[\s"]/.test(a) ? `"${a}"` : a);
    const nw = spawnSync('newman', ['run', path.join(DIR, 'G87.postman_collection.json'), '-e', fEnv, '--reporters', 'json,htmlextra',
      '--reporter-json-export', tmpRep, '--reporter-htmlextra-export', tmpHtml,
      '--reporter-htmlextra-skipHeaders', 'Authorization,X-Sandbox-Secret',
      '--reporter-htmlextra-skipEnvironmentVars', 'sandbox_secret,broker_service_token,tok_admin,tok_prod,tok_eng,s1_serial,s2_serial',
      '--timeout-request', '30000', '--color', 'off'].map(cita),
    { encoding: 'utf8', shell: process.platform === 'win32' });
    fs.rmSync(fEnv, { force: true });
    if (!fs.existsSync(tmpRep)) throw new Detener(`Newman no produjo su informe: ${sanear(nw.stderr).slice(-500)}`);
    const rep = JSON.parse(fs.readFileSync(tmpRep, 'utf8'));
    r.newman = { solicitudes: rep.run?.executions?.length ?? 0,
      aserciones: (rep.run?.executions ?? []).reduce((n, x) => n + (x.assertions?.length ?? 0), 0),
      fallidas: rep.run?.failures?.length ?? 0 };
    fs.mkdirSync(dirNewman);
    fs.writeFileSync(fRep, sanearArtefacto(fs.readFileSync(tmpRep, 'utf8'), secretos));
    if (fs.existsSync(tmpHtml)) fs.writeFileSync(fHtml, sanearArtefacto(fs.readFileSync(tmpHtml, 'utf8'), secretos));
    else r.incidencias.push('ERROR_QA: Newman no generó el reporte HTML real.');
    fs.rmSync(tmpNewman, { recursive: true, force: true });
    for (const ex of rep.run?.executions ?? []) {
      const http = ex.response?.code ?? null;
      let cuerpo = null; try { cuerpo = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { /* sin cuerpo */ }
      if (ex.response?.code === 201 && Number.isSafeInteger(cuerpo?.id_telemetria))
        (r.datos.ids_telemetria ??= []).push(cuerpo.id_telemetria);
      if (s2 && ex.item?.name === 'Dashboard del Ingeniero de Campo' && Array.isArray(cuerpo?.sensores)) {
        const observadoS2 = cuerpo.sensores.find((x) => Number(x.id_sensor) === Number(s2.id));
        r.datos.s2.indicador_ingeniero = indicadorCalibracion(observadoS2);
      }
      const rolDashboard = ex.item?.name === 'Dashboard del Productor' ? 'prod'
        : ex.item?.name === 'Dashboard del Ingeniero de Campo' ? 'eng' : null;
      if (rolDashboard) {
        const visible = (id) => Array.isArray(cuerpo?.sensores)
          && cuerpo.sensores.some((x) => Number(x.id_sensor) === Number(id));
        r.datos.visibilidad_por_rol[rolDashboard] = { ...r.datos.visibilidad_por_rol[rolDashboard],
          http: http, s1: s1 ? visible(s1.id) : null, s2: s2 ? visible(s2.id) : null };
        const campos = ['ultimo_valor', 'ultima_unidad', 'ultimo_timestamp_captura', 'estado_calidad',
          'estado_semaforo', 'estado_calidad_valor_operativo', 'timestamp_estado_actual',
          'indicador_anomalia', 'es_valor_operativo', 'etiqueta_estado', 'id_alerta',
          'nivel_bateria_pct', 'calidad_senal_rssi', 'calidad_senal_snr'];
        const resumir = (id) => {
          const sensor = Array.isArray(cuerpo?.sensores)
            ? cuerpo.sensores.find((x) => Number(x.id_sensor) === Number(id)) : null;
          return sensor ? Object.fromEntries(campos.map((k) => [k, Object.hasOwn(sensor, k) ? sensor[k] : 'CAMPO_AUSENTE'])) : null;
        };
        (r.datos.contrato_dashboard ??= {})[rolDashboard] = { s1: s1 ? resumir(s1.id) : null, s2: s2 ? resumir(s2.id) : null };
      }
      const extracto = Array.isArray(cuerpo?.sensores)
        ? cuerpo.sensores.filter((x) => [s1?.id, s2?.id].includes(x.id_sensor)).map((x) => ({ id_sensor: x.id_sensor, ultimo_valor: x.ultimo_valor,
          ultima_unidad: x.ultima_unidad, ultimo_timestamp_captura: x.ultimo_timestamp_captura, estado_calidad: x.estado_calidad, estado_semaforo: x.estado_semaforo,
          estado_calidad_valor_operativo: x.estado_calidad_valor_operativo, timestamp_estado_actual: x.timestamp_estado_actual,
          indicador_anomalia: x.indicador_anomalia, es_valor_operativo: x.es_valor_operativo, etiqueta_estado: x.etiqueta_estado,
          id_alerta: x.id_alerta, nivel_bateria_pct: x.nivel_bateria_pct, calidad_senal_rssi: x.calidad_senal_rssi, calidad_senal_snr: x.calidad_senal_snr }))
        : cuerpo;
      bitacora.push({ etiqueta: `Newman: ${ex.item?.name}`, metodo: ex.request?.method, en_run: true, status: http, error: ex.requestError?.code,
        respuesta: sanear(JSON.stringify(extracto)).slice(0, 900) });
      for (const a of ex.assertions ?? []) registrar(r, a.assertion, 'API', a.error ? false : true,
        http === null ? 'SIN_RESPUESTA' : http === 403 || http >= 500 ? 'ENTORNO' : null,
        a.error?.message, ex.item?.name);
    }
    actualizarMarcador();
    guardar();

    // 4. UI: mismo RUN visto desde el host del frontend y Cypress.
    const rutaDashboard = `/iot/monitoreo/dashboard?id_infraestructura=${area.id_infraestructura}&por_pagina=50`;
    const frontProd = await api('GET', rutaDashboard,
      { token: tokens[rolApi.prod], run, base: API_FRONT, etiqueta: 'Host frontend Productor en RUN' });
    const frontEng = await api('GET', rutaDashboard,
      { token: tokens[rolApi.eng], run, base: API_FRONT, etiqueta: 'Host frontend Ingeniero en RUN' });
    const hostProd = frontProd.status === 200 && frontProd.eco === runId && Array.isArray(frontProd.json?.sensores);
    const hostEng = frontEng.status === 200 && frontEng.eco === runId && Array.isArray(frontEng.json?.sensores);
    const visibleProd = (id) => hostProd && frontProd.json.sensores.some((x) => Number(x.id_sensor) === Number(id));
    const visibleEng = (id) => hostEng && frontEng.json.sensores.some((x) => Number(x.id_sensor) === Number(id));
    const ui177 = (!escenarioV2 || !alcance.prod.motivo) && !bloqueoS1 && uiHabilitada(r.comprobaciones, 'TC-M03-177', ['PRE-177-01', 'PRE-177-02', 'PRE-177-03'], hostProd, visibleProd(s1.id));
    const ui178Prod = (!escenarioV2 || !alcance.prod.motivo) && !bloqueoS2 && uiHabilitada(r.comprobaciones, 'TC-M03-178', ['PRE-178-01', 'PRE-178-02'], hostProd, visibleProd(s2.id));
    const ui178Eng = (!escenarioV2 || !alcance.eng.motivo) && !bloqueoS2 && uiHabilitada(r.comprobaciones, 'TC-M03-178', ['PRE-178-01', 'PRE-178-03'], hostEng, visibleEng(s2.id));
    const motivo177 = !hostProd ? `Host frontend Productor sin eco RUN (HTTP ${frontProd.status}).`
      : bloqueoS1 ? bloqueoS1 : !visibleProd(s1.id) ? 'S1 no aparece para Productor en el host frontend.' : 'PRE-177-* o preparación S1 no aprobadas.';
    const motivo178Prod = !hostProd ? `Host frontend Productor sin eco RUN (HTTP ${frontProd.status}).`
      : bloqueoS2 ? bloqueoS2 : !visibleProd(s2.id) ? 'S2 no aparece para Productor en el host frontend.' : 'PRE-178-* o preparación S2 no aprobadas.';
    const motivo178Eng = !hostEng ? `Host frontend Ingeniero sin eco RUN (HTTP ${frontEng.status}).`
      : bloqueoS2 ? bloqueoS2 : !visibleEng(s2.id) ? 'S2 no aparece para Ingeniero en el host frontend.' : 'PRE-178-* o preparación S2 no aprobadas.';
    if (ui177 || ui178Prod || ui178Eng) {
      const fSes = path.join(os.tmpdir(), `g87-${process.pid}-sesiones-ui.json`);
      temporales.push(fSes);
       const capturas = fs.mkdtempSync(path.join(os.tmpdir(), 'g87-capturas-'));
       temporales.push(capturas);
      const chrome = chromeLocal();
      let res;
      if (!chrome.disponible) res = { status: 'failed', total_pruebas: 0, navegador: 'chrome',
        motivo: `BLOQUEO_ENTORNO: ${chrome.motivo}`, runs: [] };
       else try { res = await ejecutarCypressControlado({ timeoutMs: TIMEOUT_UI_MS, signal: abortarUi.signal, opciones: {
        config: { baseUrl: FRONT, specPattern: 'g87.cy.js', screenshotsFolder: capturas,
          downloadsFolder: path.join(os.tmpdir(), `g87-${process.pid}-dl`), trashAssetsBeforeRuns: false,
          retries: 0, defaultCommandTimeout: 15000, responseTimeout: 30000, viewportWidth: 1440, viewportHeight: 900 },
        env: { AUTORIZADO: 'SI', RUN_ID: runId, SANDBOX_SECRET: V.QA_SANDBOX_SECRET, API_BASE: API_FRONT, AREA_ID: area.id_infraestructura,
           UI_177: ui177, UI_178_PROD: ui178Prod, UI_178_ENG: ui178Eng,
           S1_NOMBRE: s1?.nombre ?? '', S2_NOMBRE: s2?.nombre ?? '', VALOR_25: valores.v_a3 ?? 25, VALOR_FUERA: valores.v_fuera ?? 0, VALORES_ERROR: [valores.v_c1, valores.v_c2],
          PROD_EMAIL: c.ui_prod.correo, PROD_PASSWORD: escenarioV2 ? null : c.ui_prod.clave,
          ENG_EMAIL: c.ui_eng.correo, ENG_PASSWORD: escenarioV2 ? null : c.ui_eng.clave,
          PROD_LOGIN: escenarioV2 ? respuestasLoginUi.ui_prod : null,
          ENG_LOGIN: escenarioV2 ? respuestasLoginUi.ui_eng : null,
           SESIONES_UI: fSes } } })
         .catch((e) => ({ status: 'failed', total_pruebas: 0, navegador: 'chrome', motivo: e.message, runs: [] }));
       } finally {
         // Conservar capturas incluso si Cypress falla, agota el tiempo o no devuelve reporte.
         if (fs.existsSync(capturas)) fs.cpSync(capturas, path.join(dir, 'cypress'), { recursive: true });
       }
      r.cypress = { navegador: 'chrome', ruta: chrome.ruta ?? null, version: res.version ?? chrome.version ?? null,
        duracion_ms: res.duracion_ms ?? 0, exit_code: res.exit_code ?? null, total_pruebas: res.total_pruebas ?? 0,
        motivo: res.motivo ?? null, reconocido_cypress: (res.total_pruebas ?? 0) > 0 };
      if (!escenarioV2 && fs.existsSync(fSes)) for (const [rol, tk] of Object.entries(JSON.parse(fs.readFileSync(fSes, 'utf8')))) { tokens[`ui_${rol}`] = tk; secretos.push(tk); }
      const problemaUi = problemaCypress(res);
      if (problemaUi) r.incidencias.push(`ERROR_QA: Cypress: ${sanear(problemaUi)}`);
      for (const t2 of (res.runs ?? []).flatMap((x) => x.tests ?? [])) {
        const titulo = t2.title.at(-1);
        registrar(r, titulo, 'UI', t2.state === 'passed' ? true : t2.state === 'failed' ? false : null,
          t2.state === 'failed' && (titulo?.includes('[PRE-UI-01]') || /ERROR_QA_EVIDENCIA|cy\.(visit|wait|screenshot)\(\)|ECONN|ESOCKET|net::ERR|BLOQUEO_G87|before all/i.test(t2.displayError || '')) ? 'AUTOMATIZACION' : null,
          t2.state === 'failed' ? String(t2.displayError || '').split('\n')[0] : t2.state !== 'passed' ? `Cypress: ${t2.state}` : null);
        if (t2.state === 'failed' && /ERROR_QA_EVIDENCIA|cy\.screenshot\(\)/.test(t2.displayError || ''))
          r.incidencias.push(`ERROR_QA: ${sanear(String(t2.displayError).split('\n')[0])}`);
      }
      if (problemaUi && !r.comprobaciones.some((x) => x.id === 'PRE-UI-01' && x.fuente === 'UI')) {
        for (const caso of [ui177 ? 'TC-M03-177' : null, ui178Prod || ui178Eng ? 'TC-M03-178' : null].filter(Boolean))
          r.comprobaciones.push({ caso, tipo: 'PRE', id: 'PRE-UI-01', descripcion: 'Navegación UI al dashboard',
            fuente: 'UI', ok: false, naturaleza: 'AUTOMATIZACION', obtenido: `Cypress: ${sanear(problemaUi)}` });
      }
       for (const [caso, ids] of [
         ui177 ? ['TC-M03-177', ['PRE-UI-01', 'UI-177-01', 'UI-177-02', 'UI-177-03']] : [null, []],
         ui178Prod ? ['TC-M03-178', ['PRE-UI-01', 'UI-178-01', 'UI-178-02', 'UI-178-03']] : [null, []],
         ui178Eng ? ['TC-M03-178', ['UI-178-04', 'UI-178-05']] : [null, []],
       ].filter(([id]) => id)) {
        for (const id of comprobacionesUiFaltantes(r.comprobaciones, caso, ids))
          r.comprobaciones.push({ caso, tipo: id.startsWith('PRE-') ? 'PRE' : 'ASSERT', id,
            descripcion: 'Comprobación UI', fuente: 'UI', ok: null, naturaleza: 'AUTOMATIZACION',
            obtenido: 'NO_EJECUTADA: Cypress no produjo esta comprobación.' });
      }
    }
     for (const [caso, ejecutarUi, ids, motivo] of [
       ['TC-M03-177', ui177, ['PRE-UI-01', 'UI-177-01', 'UI-177-02', 'UI-177-03'], motivo177],
       ['TC-M03-178', ui178Prod, ['PRE-UI-01', 'UI-178-01', 'UI-178-02', 'UI-178-03'], motivo178Prod],
       ['TC-M03-178', ui178Eng, ['UI-178-04', 'UI-178-05'], motivo178Eng],
     ]) {
      if (ejecutarUi) continue;
      for (const id of ids) r.comprobaciones.push({ caso, tipo: id.startsWith('PRE-') ? 'PRE' : 'ASSERT', id,
        descripcion: 'Comprobación UI', fuente: 'UI', ok: null, naturaleza: null,
         obtenido: `NO_EJECUTADA: ${motivo}` });
    }
    r.estado = bloqueoS1 || bloqueoS2 ? 'PARCIAL' : 'CONCLUIDA';
  } catch (e) {
    r.estado = e instanceof Detener ? (r.consume_version ? 'INTERRUMPIDA' : 'DETENIDA_EN_PRECONDICIONES') : 'ERROR_AUTOMATIZACION';
    r.incidencias.push(sanear(e instanceof Detener ? e.message : e.stack));
  } finally {
    // 5. Cierre: RUN, verificación del rollback (Administrador, fuera del RUN) y sesiones.
    try { await cerrarSandbox(); } catch (e) { r.incidencias.push(`ERROR_QA: cierre del RUN: ${sanear(e.message)}`); }
    retirarSenales();
    r.cierre.sesiones = {};
    for (const [rol, tk] of Object.entries(tokens)) {
      r.cierre.sesiones[rol] = (await api('DELETE', '/sesiones/', { token: tk, etiqueta: `Logout ${rol}` }).catch(() => ({ status: 0 }))).status;
    }
    for (const f of temporales) fs.rmSync(f, { recursive: true, force: true });
    r.fin = new Date().toISOString();
    veredictos(r);
    if (r.estado === 'CONCLUIDA' && Object.values(r.casos).some((x) => !['APROBADO', 'RECHAZADO'].includes(x.estado))) r.estado = 'PARCIAL';
    const dirCypress = path.join(dir, 'cypress');
    if (fs.existsSync(dirCypress) && fs.readdirSync(dirCypress).length === 0) fs.rmdirSync(dirCypress);
    r.evidencias = ['resultado.json', ...['newman', 'cypress'].flatMap((carpeta) => {
      const raiz = path.join(dir, carpeta);
      const recorrer = (p) => fs.existsSync(p) ? fs.readdirSync(p, { withFileTypes: true }).flatMap((e) =>
        e.isDirectory() ? recorrer(path.join(p, e.name)) : [path.relative(dir, path.join(p, e.name)).replace(/\\/g, '/')]) : [];
      return recorrer(raiz);
    })];
    r.oficial = oficialidad(r);
    r.clasificacion = r.oficial ? 'OFICIAL' : 'TECNICO';
    const informeRun = path.join(dir, nombreInforme(r.version));
    let textoInforme = sanear(generarInforme(r, CASOS, { gitLocal: gitLocal() }));
    const problemas = validarResultadoLocal(r, [...r.evidencias, nombreInforme(r.version)], null, textoInforme);
    for (const ruta of r.evidencias.filter((x) => x !== 'resultado.json'))
      if (!fs.existsSync(path.join(dir, ruta))) problemas.push(`Evidencia inexistente: ${ruta}`);
    if (problemas.length) {
      r.incidencias.push(...problemas.map((x) => `ERROR_QA: validador: ${x}`));
      r.oficial = false;
      r.clasificacion = 'TECNICO';
      textoInforme = sanear(generarInforme(r, CASOS, { gitLocal: gitLocal() }));
    }
    guardar();
    fs.writeFileSync(informeRun, textoInforme, { flag: 'wx' });
  }
  console.log(`G87 V${r.version} (intento ${r.intento}) — ${r.estado}`);
  for (const [caso, v] of Object.entries(r.casos)) console.log(`  ${caso}: ${v.estado} — ${v.motivo}`);
  console.log(`  RUN: ${JSON.stringify(r.cierre.run ?? 'no abierto')} | rollback: ${r.cierre.rollback?.verificado ?? 'n/a'}`);
  console.log(`  Evidencias: ${path.relative(DIR, dir)}`);
  return r.oficial ? 0 : 5;
}

function registrar(r, nombre, fuente, ok, naturaleza, detalle, peticion) {
  const m = String(nombre).match(/^\[(TC-M03-\d{3})\]\[(PRE|ASSERT)\]\[([A-Z0-9-]+)\]\s*(.*)$/);
  const s = String(nombre).match(/^\[SETUP\]\s*(.*)$/);
  if (m) r.comprobaciones.push({ caso: m[1], tipo: m[2], id: m[3], descripcion: m[4], fuente, ok, naturaleza, obtenido: detalle ?? (ok ? 'conforme' : null), peticion });
  else if (s) {
    const contexto = `${s[1]} ${peticion ?? ''}`;
    const casos = /S1|\b168\b|\b177\b/.test(contexto) ? ['TC-M03-168', 'TC-M03-177']
      : /S2|\b178\b|Ingeniero/.test(contexto) ? ['TC-M03-178'] : Object.keys(CASOS);
    for (const caso of casos) r.comprobaciones.push({ caso, tipo: 'SETUP', id: 'SETUP', descripcion: s[1], fuente, ok, naturaleza: ok ? null : 'PREPARACION', obtenido: detalle ?? (ok ? 'conforme' : null), peticion });
  }
}

// Precondiciones de las que depende cada criterio. Si una no se produjo, el criterio no es una
// comprobación válida: queda BLOQUEADO (se conserva lo observado). Los criterios sin dependencias
// fallidas se evalúan: si no coinciden con lo esperado, RECHAZADO.
const DEPENDE = {
  'API-168-01': ['PRE-168-03'], 'API-168-02': ['PRE-168-01', 'PRE-168-03'], 'API-168-04': ['PRE-168-01', 'PRE-168-03'],
  'API-168-03': ['PRE-168-01', 'PRE-168-02', 'PRE-168-03'], 'API-168-05': ['PRE-168-01', 'PRE-168-02', 'PRE-168-03'],
  'API-177-01': ['PRE-177-03'], 'API-177-02': ['PRE-177-01', 'PRE-177-02', 'PRE-177-03'], 'API-177-03': ['PRE-177-02', 'PRE-177-03'],
  'UI-177-01': ['PRE-UI-01'], 'UI-177-02': ['PRE-177-01', 'PRE-177-02', 'PRE-UI-01'], 'UI-177-03': ['PRE-177-02', 'PRE-UI-01'],
  'API-178-01': ['PRE-178-01', 'PRE-178-02'], 'API-178-02': ['PRE-178-01', 'PRE-178-02'], 'API-178-03': ['PRE-178-01', 'PRE-178-02'],
  'API-178-04': ['PRE-178-01', 'PRE-178-02'], 'API-178-05': ['PRE-178-01', 'PRE-178-03'], 'API-178-06': ['PRE-178-01', 'PRE-178-03'],
  'API-178-07': ['PRE-178-01', 'PRE-178-03'], 'UI-178-01': ['PRE-178-01', 'PRE-UI-01'], 'UI-178-02': ['PRE-178-01', 'PRE-UI-01'],
  'UI-178-03': ['PRE-178-01', 'PRE-UI-01'], 'UI-178-04': ['PRE-178-01', 'PRE-UI-01'], 'UI-178-05': ['PRE-178-01', 'PRE-UI-01'],
};

export function veredictos(r) {
  for (const caso of Object.keys(CASOS)) {
    const cs = r.comprobaciones.filter((x) => x.caso === caso);
    const prepFallida = cs.some((x) => x.tipo === 'SETUP' && x.ok === false);
    const preFallidas = new Set(cs.filter((x) => x.tipo === 'PRE' && x.ok !== true).map((x) => x.id));
    for (const x of cs) {
      const deps = (DEPENDE[x.id] ?? []).filter((d) => preFallidas.has(d));
      if (x.tipo === 'SETUP') { x.estado = x.ok ? 'APROBADO' : 'BLOQUEADO'; x.motivo = x.ok ? undefined : 'Preparación del escenario fallida.'; }
      else if (x.ok === null) { x.estado = x.fuente === 'UI' && deps.length ? 'BLOQUEADO' : x.fuente === 'UI' ? 'NO_EJECUTADA' : 'NO EJECUTADO'; x.motivo = deps.length ? `Depende de ${deps.join(', ')}.` : x.obtenido ?? 'Sin resultado.'; }
      else if (x.tipo === 'PRE') {
        x.estado = x.ok ? 'APROBADO' : x.naturaleza === 'AUTOMATIZACION' ? 'ERROR_QA' : 'BLOQUEADO';
        if (!x.ok) x.motivo = x.naturaleza ? `Automatización o infraestructura (${x.naturaleza}).` : 'El sistema no produjo la precondición: hallazgo de la funcionalidad de la que depende.';
      } else if (prepFallida || deps.length) {
        x.estado = 'BLOQUEADO';
        x.motivo = prepFallida ? 'Preparación del escenario fallida.' : `Depende de ${deps.join(', ')}, que no se cumplió; resultado observado conservado.`;
      } else if (x.ok) x.estado = 'APROBADO';
      else if (x.naturaleza) { x.estado = x.naturaleza === 'AUTOMATIZACION' ? 'ERROR_QA' : 'BLOQUEADO'; x.motivo = `Automatización o infraestructura (${x.naturaleza}).`; }
      else x.estado = 'RECHAZADO';
    }
    const v = r.datos?.visibilidad_por_rol;
    const alcanceV2 = r.operacion === 'REEVALUAR' && r.version >= 2 ? r.datos?.alcance_cuentas : null;
    const problemasCuenta = [alcanceV2?.prod?.motivo,
      ...(caso === 'TC-M03-178' ? [alcanceV2?.eng?.motivo] : [])].filter(Boolean);
    const sinFinca = caso === 'TC-M03-178' && v?.eng?.http === 200
      && v.eng.s2 === false && v.eng.finca_asignada === false;
    if (problemasCuenta.length) for (const x of cs.filter((c) => c.tipo === 'ASSERT')) {
      x.estado = 'NO_CONCLUYENTE';
      x.motivo = problemasCuenta.join(' ');
    }
    else if (sinFinca) for (const x of cs.filter((c) => ['API-178-05', 'API-178-06', 'API-178-07', 'UI-178-04', 'UI-178-05'].includes(c.id))) {
      x.estado = 'NO_CONCLUYENTE';
      x.motivo = `La cuenta de Ingeniero no tiene asignada por API pública la finca ${r.datos.finca}; S2 no aparece en su dashboard HTTP 200.`;
    }
    const ids = (e) => [...new Set(cs.filter((x) => x.estado === e && x.tipo !== 'SETUP').map((x) => x.id))];
    const faltaUi = CASOS[caso].ui && (!cs.some((x) => x.fuente === 'UI' && x.ok !== null)
      || !r.cypress?.total_pruebas);
    let estado; let motivo;
    if (problemasCuenta.length) { estado = 'NO_CONCLUYENTE'; motivo = `Precondición de cuenta UI para API/UI: ${problemasCuenta.join(' ')}`; }
    else if (!cs.length) { estado = r.consume_version ? 'BLOQUEADO' : 'NO EJECUTADO'; motivo = r.incidencias.join(' ') || 'Sin comprobaciones.'; }
    else if (sinFinca) { estado = 'NO_CONCLUYENTE'; motivo = `S2 no aparece para el Ingeniero: la finca ${r.datos.finca} no está asignada a su cuenta según /usuarios/me; falta una cuenta con alcance de finca para comprobar el detalle técnico.`; }
    else if (ids('RECHAZADO').length) { estado = 'RECHAZADO'; motivo = `Criterios incumplidos: ${ids('RECHAZADO').join(', ')}.`; }
    else if (ids('BLOQUEADO').length || ids('NO EJECUTADO').length || ids('NO_EJECUTADA').length || faltaUi || prepFallida) {
      estado = ids('BLOQUEADO').length || prepFallida
        || (!ids('ERROR_QA').length && !r.incidencias.some((i) => i.startsWith('ERROR_QA:')) && (ids('NO EJECUTADO').length || ids('NO_EJECUTADA').length || faltaUi))
        ? 'BLOQUEADO' : 'ERROR_QA';
      motivo = `Bloqueadas o sin ejecutar: ${[...ids('BLOQUEADO'), ...ids('NO EJECUTADO'), ...ids('NO_EJECUTADA')].join(', ') || (prepFallida ? 'preparación' : 'UI')}.`;
    } else if (ids('ERROR_QA').length) { estado = 'ERROR_QA'; motivo = `Errores de automatización: ${ids('ERROR_QA').join(', ')}.`; }
    else if (CASOS[caso].ui && r.incidencias.some((i) => i.startsWith('ERROR_QA: Cypress'))) { estado = 'ERROR_QA'; motivo = 'Evidencia UI incompleta.'; }
    else { estado = 'APROBADO'; motivo = 'Todas las comprobaciones verificadas.'; }
    if (estado === 'APROBADO') {
      const ausentes = requeridasFaltantes(r, caso);
      if (ausentes.length || (CASOS[caso].ui && !(r.cypress?.total_pruebas > 0))) {
        estado = 'ERROR_QA'; motivo = `Criterios obligatorios sin evaluar: ${ausentes.join(', ') || 'UI sin pruebas'}.`;
      }
    }
    if (ids('BLOQUEADO').length && estado === 'RECHAZADO') motivo += ` Además bloqueadas: ${ids('BLOQUEADO').join(', ')}.`;
    r.casos[caso] = { estado, motivo, aprobadas: ids('APROBADO'), rechazadas: ids('RECHAZADO'), bloqueadas: ids('BLOQUEADO') };
  }
  r.veredicto_grupo = estadoGrupoG87(r.casos);
}

// ---------------------------------------------------------------------------
// Comprobación local (sin red)
// ---------------------------------------------------------------------------

function comprobar() {
  globalThis.fetch = () => { throw new Error('sin red en --comprobar'); };
  const ok = (n, c, d = '') => console.log(`${c ? '[OK]   ' : '[FALLA]'} ${n}${d ? ` — ${d}` : ''}`) || c;
  const leerFuenteUi = (ruta) => {
    try { return fs.readFileSync(path.resolve(RAIZ, '..', 'SGPMP-FRONT-END-PWA', 'src', ruta), 'utf8'); } catch { return ''; }
  };
  const telemetria = leerFuenteUi('telemetry/pages/TelemetryPage.tsx');
  const spec = fs.readFileSync(path.join(DIR, 'g87.cy.js'), 'utf8');
  const worker = fs.readFileSync(path.join(DIR, 'lib', 'g87_cypress_worker.mjs'), 'utf8');
  const chrome = chromeLocal();
  const res = [
    ok('Colección Newman legible', (() => { try { return JSON.parse(fs.readFileSync(path.join(DIR, 'G87.postman_collection.json'), 'utf8')).item.length > 0; } catch { return false; } })()),
    ...['g87.cy.js', 'g87.cypress.config.cjs'].map((f) => ok(`Sintaxis ${f}`, (() => { try { new vm.Script(fs.readFileSync(path.join(DIR, f), 'utf8'), { filename: f }); return true; } catch { return false; } })())),
    ok('Navegación SPA directa a En vivo conserva la sesión y espera dashboard',
      telemetria.includes("label: 'En vivo', path: '/telemetria/monitoreo'")
      && spec.includes("win.history.pushState({}, '', `${BASE}/telemetria/monitoreo`)")
      && spec.includes("win.dispatchEvent(new win.PopStateEvent('popstate'))")
      && spec.includes("cy.wait('@dashboard', { requestTimeout: DASHBOARD_REQUEST_TIMEOUT })")
      && !/click\(\{ force: true \}\)/.test(spec)),
    ok('Newman disponible', newmanDisponible()),
    ok('Newman HTML (htmlextra) disponible', reporterHtmlDisponible()),
    ok('Cypress resoluble', (() => { try { createRequire(path.join(RAIZ, 'package.json')).resolve('cypress'); return true; } catch { return false; } })()),
    ok('Cypress configurado con Chrome headless, sin Electron', /browser:\s*'chrome'/.test(worker)
      && /headed:\s*false/.test(worker) && !/browser:\s*'electron'/.test(worker)),
    ok('Chrome local', chrome.disponible, chrome.disponible ? `${chrome.ruta} (${chrome.version ?? 'versión no legible'})`
      : `BLOQUEO_ENTORNO: ${chrome.motivo}`),
    ok('Comprobación estática sin leer credenciales', true),
  ];
  const v = versionSiguiente('evaluacion');
  ok('Compatibilidad heredada V1', !v.error, v.error ?? `V${v.version}; intento identificado por timestamp`);
  const reintento = versionSiguiente('reintento');
  const reintentoOk = ok('Reintento técnico conserva V1 histórica y salida Resultados/RUN-<id>', !reintento.error && reintento.version === 1
    && dirResultados(1) === path.join(DIR, 'Resultados'), reintento.error ?? `V${reintento.version}; intento identificado por timestamp`);
  const v2Ok = ok('Reevaluar V2 usa EvaluacionV2/Resultados y el informe de reevaluación',
    dirResultados(2) === path.join(DIR, 'EvaluacionV2', 'Resultados')
    && nombreInforme(2) === 'TC-M03-G87_reevaluacion_V2.md');
  return res.every(Boolean) && reintentoOk && v2Ok ? 0 : 1;
}

async function recuperar(runNombre, ref, contrato = null) {
  const V = leerEnv();
  if (V.QA_AUTORIZADO !== 'SI' || !ref || ref.length < 8) {
    console.error('Recuperación bloqueada: requiere autorización propia y QA_AUTORIZADO=SI en el proceso.'); return 2;
  }
  const m = /^RUN-G87-V(\d+)-\d{8}-\d{6}$/.exec(runNombre ?? '');
  if (!m) { console.error('RUN id inválido.'); return 2; }
  const dir = path.join(dirResultados(Number(m[1])), runNombre);
  const archivo = path.join(dir, 'run-pendiente.json');
  let marcador = null; let previo = null;
  try { if (fs.existsSync(archivo)) marcador = JSON.parse(fs.readFileSync(archivo, 'utf8')); } catch { /* estado ambiguo */ }
  try { if (fs.existsSync(path.join(dir, 'resultado.json'))) previo = JSON.parse(fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8')); } catch { /* estado ambiguo */ }
  if (!marcador && !previo) { console.error('RUN sin marcador ni resultado legible; escalar, sin DELETE.'); return 2; }
  if (marcador && ![runNombre, runNombre.slice(4)].includes(marcador.run_id)) { console.error('Marcador incoherente.'); return 2; }
  if (previo && previo.run_id !== runNombre) { console.error('Resultado incoherente.'); return 2; }
  const yaVerificado = marcador?.verificado === true || previo?.cierre?.rollback?.verificado === true;
  const quizasAbierto = !yaVerificado && (marcador?.estado === 'PENDIENTE' || previo?.estado === 'EN_CURSO'
    || previo?.cierre?.run?.cierre_http == null);
  const c = cuentas(V);
  if (!V.QA_SANDBOX_SECRET || !c.admin.correo || !c.admin.clave || String(V.SIGAB_API_TEST_BASE).replace(/\/+$/, '') !== API) {
    console.error('Recuperación bloqueada: configuración QA incompleta.'); return 2;
  }
  secretos = [V.QA_SANDBOX_SECRET, c.admin.clave];
  const tokens = {};
  const login = await api('POST', '/sesiones/', { cuerpo: { correo_electronico: c.admin.correo, contrasena: c.admin.clave },
    etiqueta: 'Login Administrador recuperación' });
  if (login.status === 200 && login.json?.token) { tokens.admin = login.json.token; secretos.push(login.json.token); }
  const cierre = await cerrarYVerificar({ runId: runNombre.slice(4), secreto: V.QA_SANDBOX_SECRET,
    datos: marcador?.datos ?? previo?.datos ?? {}, tokens, credenciales: c, solicitar: api,
    solicitarCierre: quizasAbierto, cierrePrevioHttp: previo?.cierre?.run?.cierre_http ?? marcador?.cierre_http,
    onToken: (tk) => secretos.push(tk) });
  if (tokens.admin) await api('DELETE', '/sesiones/', { token: tokens.admin, etiqueta: 'Logout recuperación' });
  const intento = { referencia_recuperacion: ref, fecha: new Date().toISOString(), run_objetivo: runNombre,
    cierre_solicitado: quizasAbierto, cierre_confirmado: cierre.run.cierre_http === 200,
    rollback_verificado: cierre.rollback.verificado, cierre,
    bitacora: bitacora.map(({ metodo, ruta, status, error }) => ({ metodo, ruta, status, error })) };
  const destino = path.join(dir, `recuperacion-${Date.now()}.json`);
  fs.writeFileSync(destino, sanear(JSON.stringify(intento, null, 2)), { flag: 'wx' });
  // Evidencia del RUN original intacta: la recuperación tiene archivo propio.
  console.log(`Recuperación: HTTP ${cierre.run.cierre_http}; verificado=${cierre.rollback.verificado}; evidencia ${destino}`);
  return cierre.rollback.verificado ? 0 : 5;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const a = process.argv.slice(2);
  const val = (k) => (a.includes(k) ? a[a.indexOf(k) + 1] : undefined);
  if (a.includes('--regenerar-informe')) {
    try { console.log(regenerarInforme(val('--regenerar-informe'), val('--salida'))); process.exit(0); }
    catch (e) { console.error(`Regeneración local rechazada: ${e.message}`); process.exit(2); }
  }
  if (a.includes('--comprobar')) process.exit(comprobar());
  if (a.includes('--capacidades')) {
    console.log(JSON.stringify({ contrato: 'sigab-qa-ejecutor/1', operaciones: ['evaluar', 'reintentar', 'reevaluar', 'recuperar'], versiones: '1..n',
      comprobaciones_obligatorias: {
        'TC-M03-168': { API: ['API-168-01', 'API-168-02', 'API-168-03', 'API-168-04', 'API-168-05'] },
        'TC-M03-177': { API: ['API-177-01', 'API-177-02', 'API-177-03'], UI: ['UI-177-01', 'UI-177-02', 'UI-177-03'] },
        'TC-M03-178': { API: ['API-178-01', 'API-178-02', 'API-178-03', 'API-178-04', 'API-178-05', 'API-178-06', 'API-178-07'],
          UI: ['UI-178-01', 'UI-178-02', 'UI-178-03', 'UI-178-04', 'UI-178-05'] },
      } }));
    process.exit(0);
  }
  if (a.includes('--operacion')) {
    let contrato;
    try { contrato = contextoEjecucion(a, { grupo: 'G87', casos: Object.keys(CASOS), directorio: DIR }); }
    catch (e) { console.error(`Contrato inválido: ${e.message}`); process.exit(2); }
    if (contrato.operacion === 'recuperar') process.exit(await recuperar(contrato.objetivo, contrato.referencia, contrato));
    process.exit(await evaluar({ ref: contrato.referencia, tipo: contrato.operacion === 'reintentar' ? 'reintento' : 'evaluacion', contrato }));
  }
  if (a.includes('--recuperar')) { console.error('Recuperación requiere contrato del lanzador y autorización propia.'); process.exit(2); }
  const tipo = val('--tipo') ?? 'evaluacion';
  if (!['evaluacion', 'reintento'].includes(tipo)) { console.error('--tipo admite evaluacion o reintento.'); process.exit(2); }
  process.exit(await evaluar({ ref: val('--autorizacion'), tipo }));
}

