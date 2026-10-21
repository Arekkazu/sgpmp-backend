// Biblioteca local del grupo (copia propia de la carpeta; no se importa desde
// otros grupos). Funciones genéricas parametrizadas por el catálogo del grupo
// (gXX_casos.mjs): carga segura de .env.qa, barrera de autorización, bloqueo de
// red, cliente HTTP con sandbox, sanitización de evidencias, numeración
// histórica de evaluaciones, veredictos por caso y borrador de informe.
//
// Solo lee, fuera de la carpeta del grupo, sgpmp-backend/.env.qa (configuración
// compartida autorizada).

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const ESTADOS = Object.freeze({
  APROBADO: 'APROBADO',
  RECHAZADO: 'RECHAZADO',
  BLOQUEADO: 'BLOQUEADO',
  NO_EJECUTADO: 'NO EJECUTADO',
  PENDIENTE: 'PENDIENTE DE EJECUCIÓN',
});

// ---------------------------------------------------------------------------
// Rutas del grupo
// ---------------------------------------------------------------------------

/**
 * Rutas del grupo. `dirGrupo` es la carpeta del propio runner; los nombres de
 * archivo se derivan del identificador del grupo (TC-M03-GXX).
 */
export function rutasGrupo(grupo, dirGrupo) {
  // TC-M03-GXX -> RF-5X -> Test_Modulo3 -> Test_Testing -> tests -> sgpmp-backend
  const raizBackend = path.resolve(dirGrupo, '..', '..', '..', '..', '..');
  const corto = grupo.corto.toLowerCase();
  return {
    dirGrupo,
    raizBackend,
    envQa: path.join(raizBackend, '.env.qa'),
    coleccion: path.join(dirGrupo, `${grupo.id}.postman_collection.json`),
    cypressConfig: path.join(dirGrupo, 'cypress.config.cjs'),
    cypressSpec: path.join(dirGrupo, `tc_m03_${corto}.cy.js`),
    pruebasLocales: path.join(dirGrupo, `validar_local_${corto}.mjs`),
  };
}

// ---------------------------------------------------------------------------
// Configuración .env.qa (lectura segura, sin tocar process.env)
// ---------------------------------------------------------------------------

export const CLAVES_SECRETAS = Object.freeze([
  'QA_COMMON_PASSWORD',
  'QA_SETUP_PASSWORD',
  'QA_PROD_PASSWORD',
  'QA_ENG_PASSWORD',
  'QA_SANDBOX_SECRET',
]);

const CLAVES_CONOCIDAS = Object.freeze([
  'SIGAB_FRONT_TEST_URL',
  'SIGAB_API_TEST_BASE',
  'SIGAB_BROKER_TEST_URL',
  'SIGAB_FRONT_DEV_URL',
  'SIGAB_API_DEV_BASE',
  'SIGAB_BROKER_DEV_URL',
  'SIGAB_API_BASE',
  'SIGAB_FRONT_URL',
  'QA_ADMIN_EMAIL',
  'QA_SETUP_EMAIL',
  'QA_PROD_EMAIL',
  'QA_ENG_EMAIL',
  'QA_DEVICE_PREFIX',
  'QA_TIPO_VARIABLE',
  'QA_AUTORIZADO',
  ...CLAVES_SECRETAS,
]);

/** Interpreta el texto de un archivo .env (KEY=VALUE; ignora comentarios). */
export function parsearEnv(texto) {
  const salida = {};
  for (const linea of texto.split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$/);
    if (!m) continue;
    let valor = m[2].trim();
    if ((valor.startsWith('"') && valor.endsWith('"')) || (valor.startsWith("'") && valor.endsWith("'"))) {
      valor = valor.slice(1, -1);
    }
    salida[m[1]] = valor;
  }
  return salida;
}

/**
 * Carga .env.qa. Las variables de entorno del proceso (PowerShell) tienen
 * prioridad, como documenta el propio .env.qa. No modifica process.env.
 */
export function cargarConfiguracion(rutaEnv, entorno = process.env) {
  if (!fs.existsSync(rutaEnv)) {
    return { ok: false, motivo: `No existe ${path.basename(rutaEnv)} en la raíz del backend.`, valores: {} };
  }
  const archivo = parsearEnv(fs.readFileSync(rutaEnv, 'utf8'));
  const valores = {};
  for (const clave of CLAVES_CONOCIDAS) {
    const v = entorno[clave] !== undefined && entorno[clave] !== '' ? entorno[clave] : archivo[clave];
    valores[clave] = v === undefined ? '' : String(v);
  }
  return { ok: true, valores };
}

export function claveDe(valores, rol) {
  const especifica = { setup: 'QA_SETUP_PASSWORD', prod: 'QA_PROD_PASSWORD', eng: 'QA_ENG_PASSWORD' }[rol];
  return (especifica && valores[especifica]) || valores.QA_COMMON_PASSWORD || '';
}

/** Resumen apto para evidencias: nunca contiene valores secretos. */
export function resumenConfiguracion(valores) {
  const r = {};
  for (const [k, v] of Object.entries(valores)) {
    r[k] = CLAVES_SECRETAS.includes(k) ? (v ? '[DEFINIDA]' : '[VACÍA]') : v;
  }
  return r;
}

// ---------------------------------------------------------------------------
// Barrera de autorización y bloqueo de red
// ---------------------------------------------------------------------------

const RE_DEV = /(^|[-/.])dev([-/.]|$)/i;

/**
 * Resuelve los destinos TEST a partir de las variables canónicas
 * (SIGAB_API_TEST_BASE, SIGAB_FRONT_TEST_URL) y de sus alias de compatibilidad
 * (SIGAB_API_BASE, SIGAB_FRONT_URL), sin modificar .env.qa.
 * Si canónica y alias existen y difieren, no se elige ninguno.
 */
export function resolverDestinos(valores) {
  const motivos = [];
  const resolver = (canonica, alias, devs, etiqueta) => {
    const c = valores[canonica] || '';
    const a = valores[alias] || '';
    if (c && a && normalizarUrl(c) !== normalizarUrl(a)) {
      motivos.push(`${canonica} y su alias ${alias} apuntan a destinos distintos; no se elige ninguno.`);
      return '';
    }
    const url = String(c || a).trim().replace(/\/+$/, '');
    if (!url) { motivos.push(`Falta el destino ${etiqueta} (${canonica} o ${alias}).`); return ''; }
    if (!/^https:\/\//i.test(url)) motivos.push(`El destino ${etiqueta} debe ser HTTPS.`);
    const esperado = canonica === 'SIGAB_API_TEST_BASE' ? 'https://www.api.inmero.co/api-sgpmp-test' : 'https://api.inmero.co/sigab-test';
    if (normalizarUrl(url) !== esperado) motivos.push(`El destino ${etiqueta} no coincide con la URL oficial de TEST.`);
    if (devs.some((d) => d && normalizarUrl(d) === normalizarUrl(url)) || RE_DEV.test(url)) {
      motivos.push(`El destino ${etiqueta} corresponde a DEV; solo se admite TEST.`);
    }
    return url;
  };
  const api = resolver('SIGAB_API_TEST_BASE', 'SIGAB_API_BASE', [valores.SIGAB_API_DEV_BASE], 'API TEST');
  const front = resolver('SIGAB_FRONT_TEST_URL', 'SIGAB_FRONT_URL', [valores.SIGAB_FRONT_DEV_URL], 'frontend TEST');
  return { api, front, motivos };
}

/**
 * Prefijo de seriales QA. QA_DEVICE_PREFIX es opcional: si está vacío se usa
 * un prefijo automático; si tiene un valor con formato inválido, no se usa.
 */
export const PREFIJO_AUTOMATICO = 'QAAUTO';
export function prefijoSeriales(valores) {
  const p = String(valores.QA_DEVICE_PREFIX || '').trim();
  if (!p) return { prefijo: PREFIJO_AUTOMATICO, origen: 'automático (QA_DEVICE_PREFIX vacío)', valido: true };
  if (/^[A-Za-z0-9][A-Za-z0-9_-]{1,19}$/.test(p)) return { prefijo: p, origen: 'QA_DEVICE_PREFIX', valido: true };
  return { prefijo: '', origen: 'QA_DEVICE_PREFIX', valido: false };
}

/** Serial único del dispositivo del RUN (máximo 50 caracteres, como exige M09). */
export function serialDispositivo(prefijo, corto, sello) {
  return `${prefijo}-${corto}-${sello}`.slice(0, 50);
}

/**
 * Decide si se permite una ejecución remota. Requiere TODAS las condiciones:
 *  - QA_AUTORIZADO=SI (valor exacto; nunca lo modifica esta automatización),
 *  - referencia verificable de la autorización de Desarrollo (--autorizacion),
 *  - ambiente TEST explícito y destinos TEST resueltos sin ambigüedad ni DEV,
 *  - credenciales y secreto del sandbox presentes,
 *  - aceptación expresa de los efectos persistentes conocidos (--aceptar-efectos).
 */
export function evaluarAutorizacion(valores, opciones, efectosConocidos = []) {
  const motivos = [];
  if (valores.QA_AUTORIZADO !== 'SI') motivos.push(`QA_AUTORIZADO=${valores.QA_AUTORIZADO || '(vacío)'}; se requiere SI.`);
  const ref = (opciones.autorizacion || '').trim();
  if (ref.length < 8) motivos.push('Falta --autorizacion con la referencia verificable de la autorización de Desarrollo.');
  if (opciones.ambiente !== 'TEST') motivos.push(`Ambiente solicitado "${opciones.ambiente || ''}"; solo se admite TEST.`);
  const destinos = resolverDestinos(valores);
  motivos.push(...destinos.motivos);
  for (const rol of opciones.actores ?? ['setup', 'prod', 'eng']) {
    if (!claveDe(valores, rol)) motivos.push(`Falta la contraseña del rol ${rol} (QA_COMMON_PASSWORD o específica).`);
  }
  if (!valores.QA_SANDBOX_SECRET) motivos.push('Falta QA_SANDBOX_SECRET.');
  for (const k of ['QA_SETUP_EMAIL', 'QA_PROD_EMAIL', 'QA_ENG_EMAIL']) if (!valores[k]) motivos.push(`Falta ${k}.`);
  if (!prefijoSeriales(valores).valido) motivos.push('QA_DEVICE_PREFIX tiene un formato inválido (2-20 caracteres alfanuméricos, guion o guion bajo).');
  const aceptados = new Set(opciones.efectosAceptados ?? []);
  for (const e of efectosConocidos) {
    if (!aceptados.has(e.id)) motivos.push(`Efecto persistente no aislado sin aceptar: ${e.id} — ${e.descripcion} (usar --aceptar-efectos ${e.id}).`);
  }
  return { autorizado: motivos.length === 0, motivos, referencia: ref, destinos };
}

export function normalizarUrl(u) {
  return String(u || '').trim().replace(/\/+$/, '').toLowerCase();
}

let redHabilitada = false;
const fetchOriginal = globalThis.fetch;

/** Sustituye fetch por una función que siempre falla. Se llama al iniciar. */
export function bloquearRed() {
  redHabilitada = false;
  globalThis.fetch = async () => {
    throw new Error('BLOQUEO_RED: solicitud remota bloqueada (sin autorización de ejecución).');
  };
}

/** Solo el runner la invoca, y únicamente con una autorización ya evaluada como válida. */
export function habilitarRed(autorizacion) {
  if (!autorizacion || autorizacion.autorizado !== true) {
    throw new Error('BLOQUEO_RED: habilitarRed() exige una autorización válida.');
  }
  redHabilitada = true;
  globalThis.fetch = fetchOriginal;
}

export function redEstaHabilitada() {
  return redHabilitada;
}

// ---------------------------------------------------------------------------
// Sanitización de evidencias
// ---------------------------------------------------------------------------

const CLAVES_REDACTAR = /^(authorization|x-sandbox-secret|contrasena|password|token|access_token|refresh_token|sso_token|qa_sandbox_secret|sandbox_secret|cookie|set-cookie)$/i;
const CLAVES_IOT = /^(access_key|serial)$/i;
const RE_JWT = /eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}/g;

export function enmascararClaveIot(valor) {
  const s = String(valor ?? '');
  if (s.length <= 6) return '***';
  return `${s.slice(0, 4)}…${s.slice(-2)}`;
}

/** Redacta secretos conocidos dentro de un texto. */
export function redactarTexto(texto, secretos = []) {
  let s = String(texto);
  const lista = [...new Set(secretos.filter((x) => typeof x === 'string' && x.length >= 4))].sort((a, b) => b.length - a.length);
  for (const sec of lista) s = s.split(sec).join('[REDACTADO]');
  return s.replace(RE_JWT, '[JWT_REDACTADO]');
}

/** Copia profunda sanitizada de un objeto para evidencias. */
export function sanitizar(valor, secretos = [], clave = '') {
  if (CLAVES_REDACTAR.test(clave)) return valor == null ? valor : '[REDACTADO]';
  if (CLAVES_IOT.test(clave)) return valor == null ? valor : enmascararClaveIot(valor);
  if (Array.isArray(valor)) return valor.map((v) => sanitizar(v, secretos, ''));
  if (valor && typeof valor === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(valor)) out[k] = sanitizar(v, secretos, k);
    return out;
  }
  if (typeof valor === 'string') return redactarTexto(valor, secretos);
  return valor;
}

const EXT_TEXTO = new Set(['.json', '.md', '.html', '.htm', '.txt', '.xml', '.log', '.csv']);

/**
 * Recorre los artefactos de un RUN y redacta cualquier secreto o JWT que haya
 * quedado en archivos de texto (por ejemplo, reportes de Newman/Cypress).
 */
export function escanearYRedactarDirectorio(dir, secretos = []) {
  const informe = { archivos_revisados: 0, archivos_redactados: [] };
  if (!fs.existsSync(dir)) return informe;
  const pila = [dir];
  while (pila.length) {
    const actual = pila.pop();
    for (const ent of fs.readdirSync(actual, { withFileTypes: true })) {
      const p = path.join(actual, ent.name);
      if (ent.isDirectory()) { pila.push(p); continue; }
      if (!EXT_TEXTO.has(path.extname(ent.name).toLowerCase())) continue;
      informe.archivos_revisados += 1;
      const original = fs.readFileSync(p, 'utf8');
      const limpio = redactarTexto(original, secretos);
      if (limpio !== original) {
        fs.writeFileSync(p, limpio, 'utf8');
        informe.archivos_redactados.push(path.relative(dir, p));
      }
    }
  }
  return informe;
}

// ---------------------------------------------------------------------------
// Cliente HTTP (solo con red habilitada) y sandbox
// ---------------------------------------------------------------------------

export class ClienteSigab {
  constructor({ base, runId, sandboxSecret, secretos, bitacora }) {
    this.base = String(base).replace(/\/+$/, '');
    this.runId = runId;
    this.sandboxSecret = sandboxSecret;
    this.secretos = secretos;
    this.bitacora = bitacora; // array de intercambios sanitizados
  }

  /**
   * sandbox=true      -> X-Test-Run-Id + X-Sandbox-Secret (petición dentro de la transacción del RUN)
   * soloSecreto=true  -> solo X-Sandbox-Secret (rutas de control /test-control/runs/*)
   * sandbox=false     -> petición normal fuera del sandbox (salud y contrato)
   */
  async solicitar(metodo, ruta, { token, cuerpo, sandbox = true, soloSecreto = false, runId, etiqueta, timeoutMs = 30000 } = {}) {
    if (!redEstaHabilitada()) throw new Error('BLOQUEO_RED: la red no está habilitada.');
    const headers = { Accept: 'application/json' };
    if (cuerpo !== undefined) headers['Content-Type'] = 'application/json';
    if (token) headers.Authorization = `Bearer ${token}`;
    if (soloSecreto) {
      sandbox = false;
      headers['X-Sandbox-Secret'] = this.sandboxSecret;
    } else if (sandbox) {
      headers['X-Test-Run-Id'] = runId || this.runId;
      headers['X-Sandbox-Secret'] = this.sandboxSecret;
    }
    const inicio = Date.now();
    const control = new AbortController();
    const temporizador = setTimeout(() => control.abort(), timeoutMs);
    let status = 0;
    let texto = '';
    let eco = null;
    let error = null;
    try {
      const resp = await fetch(`${this.base}${ruta}`, {
        method: metodo,
        headers,
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
        redirect: 'manual',
        signal: control.signal,
      });
      status = resp.status;
      eco = resp.headers.get('x-test-run-id');
      texto = await resp.text();
    } catch (e) {
      error = e.name === 'AbortError' ? `TIMEOUT ${timeoutMs} ms` : String(e.message || e);
    } finally {
      clearTimeout(temporizador);
    }
    let json = null;
    try { json = texto ? JSON.parse(texto) : null; } catch { json = null; }
    const registro = {
      etiqueta: etiqueta || `${metodo} ${ruta}`,
      metodo,
      ruta,
      sandbox: soloSecreto ? 'control' : sandbox,
      run_id_enviado: sandbox ? (runId || this.runId) : null,
      run_id_devuelto: eco,
      status,
      duracion_ms: Date.now() - inicio,
      error,
      cuerpo_enviado: cuerpo === undefined ? undefined : sanitizar(cuerpo, this.secretos),
      respuesta: sanitizar(json ?? recortar(texto, 600), this.secretos),
    };
    this.bitacora.push(registro);
    return { status, json, texto, eco, error };
  }
}

function recortar(s, n) {
  const t = String(s ?? '');
  return t.length > n ? `${t.slice(0, n)}…[${t.length - n} caracteres omitidos]` : t;
}

/** Literal SQL seguro para /test-control/query (solo enteros y texto alfanumérico). */
export function literalSql(valor) {
  if (typeof valor === 'number' && Number.isInteger(valor)) return String(valor);
  const s = String(valor);
  if (!/^[A-Za-z0-9 _.:-]{1,80}$/.test(s)) throw new Error(`Literal SQL no permitido: ${s}`);
  return `'${s}'`;
}

// ---------------------------------------------------------------------------
// Numeración histórica de evaluaciones (V1, V2, V3, ...)
// ---------------------------------------------------------------------------

export const ESTADOS_RUN = Object.freeze({
  EN_CURSO: 'EN_CURSO',
  CONCLUIDA: 'CONCLUIDA',
  ABORTADA_PREFLIGHT: 'ABORTADA_PREFLIGHT',
  INTERRUMPIDA: 'INTERRUMPIDA',
});

export function dirResultadosVersion(dirGrupo, version) {
  return version === 1
    ? path.join(dirGrupo, 'RESULTADOS')
    : path.join(dirGrupo, `EvaluacionV${version}`, 'RESULTADOS');
}

export function nombreInforme(grupoId, version) {
  return version === 1 ? `${grupoId}_resultado.md` : `${grupoId}_reevaluacion_V${version}.md`;
}

export function generarRunId(corto, version, fecha = new Date()) {
  const p = (n) => String(n).padStart(2, '0');
  const sello = `${fecha.getFullYear()}${p(fecha.getMonth() + 1)}${p(fecha.getDate())}-` +
    `${p(fecha.getHours())}${p(fecha.getMinutes())}${p(fecha.getSeconds())}`;
  return version === 1 ? `${corto}-EVAL-V1-${sello}` : `${corto}-REEVAL-V${version}-${sello}`;
}

/** Lee el historial oficial del grupo sin modificar nada. */
export function inspeccionarHistorial(dirGrupo) {
  const versiones = new Map();
  const anomalias = [];
  const registrar = (n, dirRes) => {
    if (!fs.existsSync(dirRes)) return;
    const runs = [];
    for (const ent of fs.readdirSync(dirRes, { withFileTypes: true })) {
      if (!ent.isDirectory()) continue;
      const dirRun = path.join(dirRes, ent.name);
      const ev = path.join(dirRun, 'evidencia.json');
      let estado = null;
      let resultados = null;
      if (fs.existsSync(ev)) {
        try {
          const j = JSON.parse(fs.readFileSync(ev, 'utf8'));
          estado = j?.ejecucion?.estado ?? null;
          resultados = j?.resultado_propuesto ?? null;
          if (j?.ejecucion?.version !== undefined && j.ejecucion.version !== n) {
            anomalias.push(`El RUN ${ent.name} declara versión ${j.ejecucion.version} pero está en la carpeta de V${n}.`);
          }
        } catch {
          anomalias.push(`evidencia.json ilegible en ${path.relative(dirGrupo, dirRun)}.`);
        }
      } else {
        anomalias.push(`RUN sin evidencia.json (origen desconocido): ${path.relative(dirGrupo, dirRun)}.`);
      }
      runs.push({ runId: ent.name, dir: dirRun, estado, resultados });
    }
    runs.sort((a, b) => a.runId.localeCompare(b.runId));
    versiones.set(n, { version: n, dirResultados: dirRes, runs });
  };

  registrar(1, path.join(dirGrupo, 'RESULTADOS'));
  if (fs.existsSync(dirGrupo)) {
    for (const ent of fs.readdirSync(dirGrupo, { withFileTypes: true })) {
      const m = ent.isDirectory() && ent.name.match(/^EvaluacionV(\d+)$/);
      if (!m) continue;
      const n = Number(m[1]);
      if (n < 2) { anomalias.push(`Carpeta ${ent.name} no válida (las reevaluaciones empiezan en V2).`); continue; }
      registrar(n, path.join(dirGrupo, ent.name, 'RESULTADOS'));
      if (!versiones.has(n)) versiones.set(n, { version: n, dirResultados: path.join(dirGrupo, ent.name, 'RESULTADOS'), runs: [] });
    }
  }
  const lista = [...versiones.values()].filter((v) => v.runs.length > 0 || v.version > 1).sort((a, b) => a.version - b.version);
  const maxima = lista.length ? lista[lista.length - 1].version : 0;
  for (let n = 1; n < maxima; n += 1) {
    const v = versiones.get(n);
    if (!v || v.runs.length === 0) anomalias.push(`Hay evaluaciones hasta V${maxima} pero falta evidencia de V${n}.`);
  }
  return { versiones: lista, maxima, anomalias };
}

/**
 * Determina la versión de evaluación para una ejecución oficial.
 *  tipo = 'evaluacion' -> primera evaluación o reevaluación autorizada
 *  tipo = 'reintento'  -> reintento técnico dentro de la evaluación vigente
 * versionConfirmada (opcional) = versión confirmada por QA ante ambigüedad.
 */
export function resolverVersion(historial, { tipo, versionConfirmada } = {}) {
  const { versiones, maxima, anomalias } = historial;
  const actual = versiones.find((v) => v.version === maxima);
  const estados = actual ? actual.runs.map((r) => r.estado) : [];
  const hayConcluida = estados.includes(ESTADOS_RUN.CONCLUIDA);
  const hayInterrumpida = estados.some((e) => e === ESTADOS_RUN.INTERRUMPIDA || e === ESTADOS_RUN.EN_CURSO || e === null);

  const validarConfirmada = (candidatas) => {
    if (versionConfirmada === undefined || versionConfirmada === null) return null;
    const n = Number(versionConfirmada);
    if (!candidatas.includes(n)) {
      return { ok: false, motivo: `--version ${versionConfirmada} no es coherente con el historial (válidas: ${candidatas.join(', ')}).` };
    }
    return { ok: true, version: n, motivo: `Versión V${n} confirmada explícitamente por QA (--version).` };
  };

  if (tipo === 'reintento') {
    if (maxima === 0) return { ok: false, motivo: 'No existe ninguna evaluación previa: un reintento técnico no aplica.' };
    const c = validarConfirmada([maxima]);
    if (c) return c;
    return { ok: true, version: maxima, motivo: `Reintento técnico dentro de V${maxima} (nuevo RUN_ID).` };
  }
  if (tipo !== 'evaluacion') return { ok: false, motivo: `Tipo de ejecución desconocido: ${tipo}.` };

  if (anomalias.length > 0) {
    const c = validarConfirmada(maxima === 0 ? [1] : [maxima, maxima + 1]);
    if (c) return c;
    return { ok: false, ambiguo: true, motivo: `Historial ambiguo: ${anomalias.join(' ')} Confirmar la versión con QA (--version N).` };
  }
  if (maxima === 0) return validarConfirmada([1]) || { ok: true, version: 1, motivo: 'Primera evaluación oficial (V1).' };
  if (hayConcluida) {
    return validarConfirmada([maxima + 1]) || { ok: true, version: maxima + 1, motivo: `V${maxima} concluida; reevaluación autorizada V${maxima + 1}.` };
  }
  if (hayInterrumpida) {
    const c = validarConfirmada([maxima, maxima + 1]);
    if (c) return c;
    return {
      ok: false,
      ambiguo: true,
      motivo: `V${maxima} tiene ejecuciones interrumpidas sin concluir. Confirmar con QA si es reintento (--version ${maxima}) o nueva evaluación (--version ${maxima + 1}).`,
    };
  }
  // Solo ejecuciones abortadas antes de los escenarios: la versión no se consumió.
  return validarConfirmada([maxima]) || { ok: true, version: maxima, motivo: `V${maxima} solo tiene ejecuciones abortadas en preflight; se mantiene V${maxima}.` };
}

/** Crea el directorio del RUN; falla si ya existe (nunca sobrescribe). */
export function crearDirectorioRun(dirGrupo, version, runId) {
  const base = dirResultadosVersion(dirGrupo, version);
  fs.mkdirSync(base, { recursive: true });
  const dirRun = path.join(base, runId);
  fs.mkdirSync(dirRun, { recursive: false }); // EEXIST si ya existe
  return dirRun;
}

/** Escribe un archivo nuevo; falla si existe (protege evidencias previas). */
export function escribirNuevo(ruta, contenido) {
  fs.writeFileSync(ruta, contenido, { encoding: 'utf8', flag: 'wx' });
}

// ---------------------------------------------------------------------------
// Resultados por aserción y veredictos
// ---------------------------------------------------------------------------

const RE_NOMBRE = /^\[(TC-M03-\d{3})\]\[(PRE|ASSERT|INFO)\]\[([A-Z0-9-]+)\]\s*(.*)$/;
const RE_SETUP = /^\[SETUP\]\s*(.*)$/;

// Naturaleza de un fallo: distingue el incumplimiento del producto de los
// errores del ejecutor y de la infraestructura (estos nunca producen RECHAZADO).
export const NATURALEZA = Object.freeze({
  PRODUCTO: 'PRODUCTO',
  AUTOMATIZACION: 'AUTOMATIZACION',
  INFRAESTRUCTURA: 'INFRAESTRUCTURA',
});

export function parsearNombreSetup(nombre) {
  const m = String(nombre).match(RE_SETUP);
  return m ? m[1] : null;
}

export function parsearNombreAsercion(nombre) {
  const m = String(nombre).match(RE_NOMBRE);
  if (!m) return null;
  return { caso: m[1], tipo: m[2], id: m[3], texto: m[4] };
}

/** Caso al que pertenece una petición de la colección ("168 Dashboard …" -> TC-M03-168); null = preparación. */
export function casoDePeticion(nombre) {
  const m = String(nombre).match(/^(\d{3}) /);
  return m ? `TC-M03-${m[1]}` : null;
}

/** Extrae resultados por aserción de un reporte JSON de Newman. */
export function resultadosDesdeNewman(reporte) {
  const salida = [];
  for (const ex of reporte?.run?.executions ?? []) {
    const peticion = ex?.item?.name ?? '';
    const status = ex?.response?.code ?? null;
    for (const a of ex?.assertions ?? []) {
      const p = parsearNombreAsercion(a.assertion);
      if (!p) continue;
      salida.push({
        ...p,
        fuente: 'API',
        ok: !a.error,
        // Una aserción evaluada sobre una respuesta real es evidencia del producto.
        naturaleza: a.error ? (status === null ? NATURALEZA.INFRAESTRUCTURA : NATURALEZA.PRODUCTO) : null,
        detalle: a.error ? String(a.error.message || a.error) : null,
        peticion,
        http: status,
      });
    }
  }
  return salida;
}

/**
 * Incidencias de la ejecución de Newman que NO son evidencia del producto:
 * peticiones sin respuesta (infraestructura), errores de scripts (automatización)
 * y pasos [SETUP] fallidos. Devuelve { porCaso: {caso: [..]}, general: [..] }.
 */
export function incidenciasNewman(reporte) {
  const porCaso = {};
  const general = [];
  const anotar = (nombre, texto) => {
    const caso = casoDePeticion(nombre);
    if (caso) (porCaso[caso] ??= []).push(texto); else general.push(texto);
  };
  for (const ex of reporte?.run?.executions ?? []) {
    const nombre = ex?.item?.name ?? '';
    if (ex?.requestError) anotar(nombre, `${NATURALEZA.INFRAESTRUCTURA}: «${nombre}» sin respuesta (${ex.requestError.code || ex.requestError.message}).`);
    for (const a of ex?.assertions ?? []) {
      const s = parsearNombreSetup(a.assertion);
      // Un paso [SETUP] fallido (sesión, eco del sandbox) invalida el entorno del caso: nunca es evidencia del producto.
      if (s && a.error) anotar(nombre, `${NATURALEZA.INFRAESTRUCTURA}: paso de preparación «${nombre}» — ${s}: ${a.error.message || a.error}.`);
    }
  }
  for (const f of reporte?.run?.failures ?? []) {
    if (f?.error?.name && !/AssertionError/.test(f.error.name)) {
      anotar(f?.source?.name ?? '', `${NATURALEZA.AUTOMATIZACION}: error de script en «${f?.source?.name ?? 'Newman'}» (${f.at ?? ''}) — ${f.error.name}: ${f.error.message}.`);
    }
  }
  return { porCaso, general };
}

/** Clasifica el error de una prueba Cypress fallida. */
export function naturalezaErrorCypress(texto) {
  const t = String(texto || '');
  if (/cy\.(visit|request|wait)\(\) (failed|timed out)|ECONNREFUSED|ECONNRESET|ESOCKETTIMEDOUT|ENOTFOUND|net::ERR|status code 5\d\d on visit/i.test(t)) return NATURALEZA.INFRAESTRUCTURA;
  if (/\b(TypeError|ReferenceError|SyntaxError|RangeError)\b/.test(t)) return NATURALEZA.AUTOMATIZACION;
  return NATURALEZA.PRODUCTO;
}

/** Extrae resultados por aserción de la estructura devuelta por cypress.run(). */
export function resultadosDesdeCypress(resultado) {
  const salida = [];
  for (const run of resultado?.runs ?? []) {
    for (const t of run?.tests ?? []) {
      const titulo = Array.isArray(t.title) ? t.title[t.title.length - 1] : String(t.title);
      const p = parsearNombreAsercion(titulo);
      if (!p) continue;
      const estado = t.state; // passed | failed | pending | skipped
      const error = estado === 'failed' ? String(t.displayError || '').split('\n')[0] : null;
      salida.push({
        ...p,
        fuente: 'UI',
        ok: estado === 'passed' ? true : estado === 'failed' ? false : null,
        naturaleza: estado === 'failed' ? naturalezaErrorCypress(t.displayError) : null,
        detalle: error ?? (estado !== 'passed' ? `Estado Cypress: ${estado}` : null),
      });
    }
  }
  return salida;
}

/**
 * Veredicto propuesto de un caso (APROBADO / RECHAZADO / BLOQUEADO / NO EJECUTADO).
 * Prioridad:
 *  1. bloqueos del ejecutor (entorno, sandbox, preparación, herramienta) -> BLOQUEADO
 *  2. precondición incumplida (PRE) -> BLOQUEADO; si el sistema respondió en contra,
 *     se registra además como hallazgo de la funcionalidad de la que depende el caso
 *  3. criterio incumplido con evidencia del producto -> RECHAZADO
 *  4. criterio no evaluable (error de automatización/infraestructura o sin resultado) -> BLOQUEADO
 *  5. todo verificado -> APROBADO
 */
export function veredictoCaso(caso, resultados, bloqueos = []) {
  const porId = new Map();
  for (const r of resultados.filter((x) => x.caso === caso.id)) {
    if (!porId.has(r.id)) porId.set(r.id, []);
    porId.get(r.id).push(r);
  }
  const detalle = caso.aserciones.map((a) => {
    const rs = porId.get(a.id) ?? [];
    let ok = null;
    if (rs.length > 0) ok = rs.some((r) => r.ok === false) ? false : rs.every((r) => r.ok === true) ? true : null;
    const fallidas = rs.filter((r) => r.ok === false);
    const naturaleza = ok === false
      ? (fallidas.some((r) => r.naturaleza === NATURALEZA.PRODUCTO) ? NATURALEZA.PRODUCTO : fallidas[0].naturaleza ?? NATURALEZA.AUTOMATIZACION)
      : null;
    return { ...a, ok, naturaleza, observaciones: rs.filter((r) => r.detalle).map((r) => r.detalle) };
  });
  const decisivas = detalle.filter((d) => d.tipo !== 'INFO');
  const lista = (xs) => xs.map((d) => `${d.id} (${d.desc})`).join('; ');
  const preFallidas = decisivas.filter((d) => d.tipo === 'PRE' && d.ok === false);
  const incumplidas = decisivas.filter((d) => d.tipo === 'ASSERT' && d.ok === false && d.naturaleza === NATURALEZA.PRODUCTO);
  const noEvaluables = decisivas.filter((d) => d.tipo === 'ASSERT' && (d.ok === null || (d.ok === false && d.naturaleza !== NATURALEZA.PRODUCTO)));
  let estado;
  let motivo;
  if (bloqueos.length > 0) {
    estado = ESTADOS.BLOQUEADO;
    motivo = bloqueos.join(' ');
  } else if (decisivas.every((d) => d.ok === null)) {
    estado = ESTADOS.NO_EJECUTADO;
    motivo = 'Ninguna aserción del caso llegó a ejecutarse.';
  } else if (preFallidas.length) {
    estado = ESTADOS.BLOQUEADO;
    motivo = `Precondición incumplida: ${lista(preFallidas)}.`;
  } else if (incumplidas.length) {
    estado = ESTADOS.RECHAZADO;
    motivo = `Criterios incumplidos con evidencia del producto: ${lista(incumplidas)}.`;
  } else if (noEvaluables.length) {
    estado = ESTADOS.BLOQUEADO;
    motivo = `Criterios no evaluables (automatización, infraestructura o sin resultado): ${lista(noEvaluables)}.`;
  } else {
    estado = ESTADOS.APROBADO;
    motivo = 'Todas las precondiciones y criterios verificados.';
  }
  const hallazgos = detalle.filter((d) => d.ok === false).map((d) => ({
    asercion: d.id,
    tipo: d.tipo,
    naturaleza: d.naturaleza,
    lectura: d.tipo === 'PRE'
      ? (d.naturaleza === NATURALEZA.PRODUCTO
        ? 'El sistema respondió en contra de la precondición: posible incumplimiento de la funcionalidad de la que depende el caso (a confirmar por QA).'
        : 'La precondición no pudo establecerse por causas de entorno o automatización.')
      : d.tipo === 'INFO'
        ? 'Comprobación complementaria fallida (no decide el veredicto).'
        : d.naturaleza === NATURALEZA.PRODUCTO
          ? 'Incumplimiento observado del criterio del caso.'
          : 'Criterio no evaluado por error de automatización o de infraestructura.',
    observado: d.observaciones,
  }));
  return { caso: caso.id, estado, motivo, aserciones: detalle, hallazgos };
}

const CAMPOS_SENSOR = ['id_sensor', 'nombre_sensor', 'ultimo_valor', 'ultima_unidad', 'ultimo_timestamp_captura', 'estado_semaforo',
  'estado_calidad', 'id_alerta', 'severidad_alerta', 'nivel_bateria_pct', 'calidad_senal_rssi', 'calidad_senal_snr', 'dato_desactualizado'];
const CAMPOS_RESPUESTA = ['id_telemetria', 'estado_calidad', 'id_umbral_ambiental', 'valor_min', 'valor_max', 'estado_sincronizacion',
  'id_alerta', 'severidad', 'estado_alerta', 'es_duplicado', 'motivo_descarte', 'total', 'nombre_rol', 'code', 'message', 'detail'];

/**
 * Consolida el reporte JSON de Newman para evidencia.json: por petición,
 * método, ruta (sin base), HTTP, duración, aserciones y lo observado
 * (filas del dashboard solo de los sensores del RUN; campos clave en el resto).
 * Sustituye al JSON bruto, que no se conserva.
 */
export function resumenNewman(reporte, idsSensores = []) {
  const ids = new Set(idsSensores.map(Number));
  const peticiones = [];
  for (const ex of reporte?.run?.executions ?? []) {
    let cuerpo = null;
    const crudo = ex?.response?.stream?.data ? Buffer.from(ex.response.stream.data).toString('utf8') : ex?.response?.cuerpo;
    try { cuerpo = crudo ? JSON.parse(crudo) : null; } catch { cuerpo = null; }
    const url = ex?.request?.url;
    const ruta = typeof url === 'string' ? url : url ? `/${(url.path ?? []).join('/')}${url.query?.length ? `?${url.query.map((q) => `${q.key}=${q.value}`).join('&')}` : ''}` : null;
    let observado = null;
    if (cuerpo && Array.isArray(cuerpo.sensores)) {
      observado = {
        total: cuerpo.total,
        sensores_del_run: cuerpo.sensores.filter((s) => ids.has(Number(s.id_sensor))).map((s) => Object.fromEntries(CAMPOS_SENSOR.map((k) => [k, s[k] ?? null]))),
        sensores_del_run_ausentes: [...ids].filter((id) => !cuerpo.sensores.some((s) => Number(s.id_sensor) === id)),
      };
    } else if (cuerpo && typeof cuerpo === 'object') {
      observado = Object.fromEntries(CAMPOS_RESPUESTA.filter((k) => cuerpo[k] !== undefined).map((k) => [k, cuerpo[k]]));
    }
    peticiones.push({
      caso: casoDePeticion(ex?.item?.name ?? ''),
      peticion: ex?.item?.name ?? '',
      metodo: ex?.request?.method ?? null,
      ruta,
      http: ex?.response?.code ?? null,
      duracion_ms: ex?.response?.responseTime ?? null,
      sin_respuesta: ex?.requestError ? String(ex.requestError.code || ex.requestError.message) : undefined,
      aserciones: (ex?.assertions ?? []).map((a) => ({ nombre: a.assertion, ok: !a.error, error: a.error ? String(a.error.message || a.error) : undefined })),
      observado,
    });
  }
  const st = reporte?.run?.stats ?? {};
  return {
    estadisticas: { peticiones: st.requests?.total ?? null, aserciones: st.assertions?.total ?? null, aserciones_fallidas: st.assertions?.failed ?? null },
    peticiones,
  };
}

export function estadoGrupo(veredictos) {
  const estados = veredictos.map((v) => v.estado);
  if (estados.every((e) => e === ESTADOS.APROBADO)) return ESTADOS.APROBADO;
  if (estados.includes(ESTADOS.RECHAZADO)) return ESTADOS.RECHAZADO;
  if (estados.includes(ESTADOS.BLOQUEADO)) return ESTADOS.BLOQUEADO;
  return ESTADOS.NO_EJECUTADO;
}

// ---------------------------------------------------------------------------
// Trazabilidad del código usado
// ---------------------------------------------------------------------------

export function huellaScripts(dirGrupo, nombres) {
  const archivos = {};
  const total = crypto.createHash('sha256');
  for (const nombre of nombres) {
    const p = path.join(dirGrupo, nombre);
    if (!fs.existsSync(p)) { archivos[nombre] = null; continue; }
    const contenido = fs.readFileSync(p);
    const h = crypto.createHash('sha256').update(contenido).digest('hex');
    archivos[nombre] = h;
    total.update(`${nombre}:${h};`);
  }
  return { sha256_conjunto: total.digest('hex'), archivos };
}

// ---------------------------------------------------------------------------
// Borrador de informe (formato histórico SIGAB M02/M09)
// ---------------------------------------------------------------------------

const ICONO = { true: '✅', false: '❌', null: '⏸️' };

export function generarInforme(ev, historial, GRUPO, CASOS) {
  const v = ev.ejecucion.version;
  const esRe = v > 1;
  const L = [];
  L.push(`# ${GRUPO.id} — ${esRe ? `REEVALUACIÓN V${v}` : 'EVALUACIÓN V1'}`);
  L.push('');
  L.push(GRUPO.rfNombre);
  L.push(GRUPO.cuNombre);
  L.push('');
  L.push(`Grupo: ${GRUPO.titulo}`);
  L.push(`Casos: ${CASOS.map((c) => c.id).join(' · ')}`);
  L.push(`Tipo: ${GRUPO.tipo}`);
  L.push(`Herramientas: ${GRUPO.herramientas}`);
  L.push(`Responsable QA: ${GRUPO.responsable} · Prioridad: ${GRUPO.prioridad}`);
  L.push(`RUN_ID: \`${ev.ejecucion.run_id}\``);
  L.push(`Fecha: ${ev.ejecucion.inicio.slice(0, 10)}`);
  L.push('Entorno decisorio: **TEST**');
  L.push('');
  L.push('> **Estado del documento: BORRADOR TÉCNICO GENERADO AUTOMÁTICAMENTE.** Los resultados son los');
  L.push('> observados en la ejecución y el dictamen es *propuesto*. QA debe revisar las evidencias y');
  L.push('> confirmar o corregir el dictamen antes de darlo por emitido.');
  L.push('');
  L.push('---');
  L.push('');
  L.push('## DECISIÓN GENERAL (PROPUESTA)');
  L.push('');
  for (const ver of ev.resultado_propuesto.casos) {
    const c = CASOS.find((x) => x.id === ver.caso);
    L.push(`### ${ver.caso} — ${ver.estado}.`);
    L.push('');
    L.push(`${c.titulo}`);
    L.push('');
    L.push(`Motivo: ${ver.motivo}`);
    L.push('');
  }
  L.push(`### Estado general del grupo (propuesto): ${ev.resultado_propuesto.grupo}.`);
  L.push('');
  L.push('| Caso | Resultado propuesto | Ambiente |');
  L.push('| --- | --- | --- |');
  for (const ver of ev.resultado_propuesto.casos) L.push(`| ${ver.caso} | **${ver.estado}** | TEST |`);
  L.push(`| **Grupo ${GRUPO.id}** | **${ev.resultado_propuesto.grupo}** | TEST |`);
  L.push('');

  if (esRe) {
    L.push('---');
    L.push('');
    L.push('## ANTECEDENTES');
    L.push('');
    L.push('Las evaluaciones anteriores se conservan intactas y en solo lectura.');
    L.push('');
    L.push(`| Evaluación | RUN | Estado del RUN | ${CASOS.map((c) => c.id).join(' | ')} |`);
    L.push(`| --- | --- | --- | ${CASOS.map(() => '---').join(' | ')} |`);
    for (const ver of historial.versiones.filter((x) => x.version < v)) {
      for (const run of ver.runs) {
        const porCaso = (id) => run.resultados?.casos?.find((x) => x.caso === id)?.estado ?? '—';
        L.push(`| V${ver.version} | \`${run.runId}\` | ${run.estado ?? 'desconocido'} | ${CASOS.map((c) => porCaso(c.id)).join(' | ')} |`);
      }
    }
    L.push('');
    L.push('## CAMBIO QUE MOTIVA LA REEVALUACIÓN');
    L.push('');
    L.push('_Pendiente de completar por QA con la corrección reportada por Desarrollo y su verificación en código y despliegue._');
    L.push('_Una corrección solo se da por verificada con la evidencia funcional de este RUN en TEST._');
    L.push('');
    L.push('## COMPARACIÓN POR CASO');
    L.push('');
    L.push('| Caso | Evaluación anterior concluida | Esta evaluación | Lectura |');
    L.push('| --- | --- | --- | --- |');
    const previa = [...historial.versiones].filter((x) => x.version < v).reverse()
      .flatMap((x) => x.runs.filter((r) => r.estado === ESTADOS_RUN.CONCLUIDA).reverse())[0];
    for (const ver of ev.resultado_propuesto.casos) {
      const antes = previa?.resultados?.casos?.find((x) => x.caso === ver.caso)?.estado ?? '—';
      let lectura = 'Sin cambio';
      if (antes !== '—' && antes !== ver.estado) {
        lectura = ver.estado === ESTADOS.APROBADO ? 'Defecto corregido (verificar)' : antes === ESTADOS.APROBADO ? 'Posible regresión' : 'Cambio de estado';
      }
      L.push(`| ${ver.caso} | ${antes} | ${ver.estado} | ${lectura} |`);
    }
    L.push('');
  }

  L.push('---');
  L.push('');
  L.push('## OBJETIVO');
  L.push('');
  L.push(GRUPO.objetivo);
  L.push('');
  L.push('## ENTORNO');
  L.push('');
  L.push('| Elemento | Valor |');
  L.push('| --- | --- |');
  L.push(`| Ambiente decisorio | **TEST** |`);
  L.push(`| Backend | \`${ev.entorno.api_base}\` |`);
  L.push(`| Frontend | \`${ev.entorno.front_url}\` |`);
  L.push(`| Autorización de Desarrollo | ${ev.ejecucion.autorizacion} |`);
  L.push(`| Tipo de ejecución | ${ev.ejecucion.tipo} — ${ev.ejecucion.motivo_version} |`);
  L.push(`| Rama / HEAD backend | \`${ev.codigo.rama ?? '—'}\` / \`${ev.codigo.head ?? '—'}\` |`);
  L.push(`| HEAD vs origin/test | ${ev.codigo.vs_origin_test ?? '—'} |`);
  L.push(`| Huella de los scripts (sha256) | \`${ev.codigo.huella.sha256_conjunto}\` |`);
  L.push(`| Cambios locales en la carpeta del grupo | ${ev.codigo.cambios_locales_grupo ?? '—'} |`);
  L.push('');
  L.push('## ACTORES');
  L.push('');
  L.push('| Rol | Cuenta | Rol devuelto por /usuarios/me |');
  L.push('| --- | --- | --- |');
  for (const a of ev.actores ?? []) L.push(`| ${a.rol} | \`${a.correo}\` | ${a.nombre_rol ?? '—'} |`);
  L.push('');
  L.push('## PRECONDICIONES Y DATOS UTILIZADOS');
  L.push('');
  L.push(`Estrategia de alcance de finca: ${ev.datos?.estrategia_finca ?? '—'}`);
  L.push('');
  L.push('| Entidad | Identificador | Origen |');
  L.push('| --- | --- | --- |');
  for (const e of ev.datos?.entidades ?? []) L.push(`| ${e.entidad} | ${e.id} | ${e.origen} |`);
  L.push('');
  if ((ev.datos?.dependencias ?? []).length) {
    L.push('Dependencias detectadas al preparar los datos:');
    L.push('');
    for (const d of ev.datos.dependencias) L.push(`- ${d}`);
    L.push('');
  }
  if (ev.datos?.rango_operativo) {
    const r = ev.datos.rango_operativo;
    L.push('Clasificación de los valores usados (RF-53: rango físico vs. rango operativo configurado):');
    L.push('');
    L.push(`- Rango físico de la variable: [${r.fisico_min}, ${r.fisico_max}] ${r.unidad} — fuera de él el dato es físicamente imposible (ERROR_SENSOR, no se envía).`);
    L.push(`- Rango operativo: [${r.min}, ${r.max}] ${r.unidad} — fuente: ${r.fuente}.`);
    L.push(`- Valor físicamente válido y fuera del rango operativo (FUERA_DE_RANGO esperado): ${r.valor_fuera} ${r.unidad}.`);
    L.push(`- Valores válidos dentro del rango operativo: ${r.validos.join(', ')} ${r.unidad}.`);
    L.push('');
  }
  L.push('## RESULTADOS POR CASO');
  L.push('');
  for (const ver of ev.resultado_propuesto.casos) {
    const c = CASOS.find((x) => x.id === ver.caso);
    L.push(`### ${c.id}`);
    L.push('');
    L.push(`- **Objetivo:** ${c.objetivo}`);
    L.push(`- **Actor:** ${c.actor}`);
    L.push(`- **Criterios:** ${c.criterios}`);
    L.push(`- **Datos de prueba (matriz):** ${c.datos}`);
    L.push(`- **Resultado esperado (matriz):** ${c.esperado}`);
    L.push(`- **Resultado propuesto:** **${ver.estado}** — ${ver.motivo}`);
    L.push('');
    L.push('| Aserción | Tipo | Fuente | Descripción | Resultado | Naturaleza del fallo | Observado |');
    L.push('| --- | --- | --- | --- | :---: | --- | --- |');
    for (const a of ver.aserciones) {
      const obs = a.observaciones.length ? a.observaciones.join(' / ').replace(/\|/g, '\\|') : (a.ok === null ? 'No ejecutada' : '—');
      L.push(`| ${a.id} | ${a.tipo} | ${a.fuente} | ${a.desc} | ${ICONO[String(a.ok)]} | ${a.naturaleza ?? '—'} | ${obs} |`);
    }
    L.push('');
    const pets = (ev.newman?.peticiones ?? []).filter((x) => x.caso === c.id);
    if (pets.length) {
      L.push('Observado en las peticiones del caso:');
      L.push('');
      L.push('| Petición | HTTP | Observado |');
      L.push('| --- | ---: | --- |');
      for (const x of pets) L.push(`| ${x.peticion} | ${x.http ?? (x.sin_respuesta ? 'sin respuesta' : '—')} | \`${JSON.stringify(x.observado ?? {}).replace(/\|/g, '\\|')}\` |`);
      L.push('');
    }
  }
  L.push('## HALLAZGOS');
  L.push('');
  const hallazgos = ev.resultado_propuesto.casos.flatMap((ver) => (ver.hallazgos ?? []).map((h) => ({ caso: ver.caso, ...h })));
  if (!hallazgos.length) {
    L.push('No se registraron aserciones fallidas.');
  } else {
    L.push('| Caso | Aserción | Tipo | Naturaleza | Lectura preliminar |');
    L.push('| --- | --- | --- | --- | --- |');
    for (const h of hallazgos) L.push(`| ${h.caso} | ${h.asercion} | ${h.tipo} | ${h.naturaleza} | ${h.lectura} |`);
    L.push('');
    L.push('### Investigación de cada fallo (a completar por QA con la evidencia del RUN)');
    L.push('');
    L.push('| Caso | Aserción | Requerimiento afectado | Esperado | Obtenido | Posible causa raíz | Categoría oficial | Severidad | Prioridad | Equipo responsable (sustentado) | Relación con otras incidencias | Recomendación |');
    L.push('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |');
    for (const h of hallazgos) L.push(`| ${h.caso} | ${h.asercion} |  |  | ${(h.observado ?? []).join(' / ').replace(/\|/g, '\\|')} |  |  |  |  |  |  |  |`);
    L.push('');
    L.push('_Si la causa es de QA, indicar si es un error de diseño del caso oficial o de la automatización. No se asignan identificadores de incidencia de forma automática._');
  }
  L.push('');
  const inc = ev.incidencias_ejecucion ?? {};
  const listaInc = [...(inc.general ?? []), ...Object.entries(inc.porCaso ?? {}).flatMap(([k, v]) => v.map((x) => `${k}: ${x}`))];
  if (listaInc.length) {
    L.push('Incidencias de la ejecución (no son evidencia del producto):');
    L.push('');
    for (const x of listaInc) L.push(`- ${x}`);
    L.push('');
  }
  if ((ev.riesgos_conocidos ?? []).length) {
    L.push('Hipótesis previas del análisis estático (no son defectos confirmados; se contrastan con lo observado arriba):');
    L.push('');
    for (const r of ev.riesgos_conocidos) L.push(`- ${r}`);
    L.push('');
  }
  L.push('## SANDBOX Y ROLLBACK');
  L.push('');
  L.push('| Elemento | Valor |');
  L.push('| --- | --- |');
  L.push(`| Transacción | Sandbox \`X-Test-Run-Id\` = \`${ev.sandbox.run_id_sandbox ?? '—'}\` |`);
  L.push(`| Verificación de disponibilidad | ${ev.sandbox.preflight ?? '—'} |`);
  L.push(`| Aislamiento observado durante el RUN | ${ev.sandbox.aislamiento ?? '—'} |`);
  L.push(`| Peticiones de la UI dentro del sandbox | ${ev.sandbox.ui ?? '—'} |`);
  L.push(`| Cierre (DELETE /test-control/runs) | ${ev.sandbox.cierre ?? '—'} |`);
  L.push(`| Confirmación posterior del rollback | ${ev.sandbox.rollback_confirmado ?? '—'} |`);
  L.push(`| Efectos externos | ${ev.sandbox.efectos_externos ?? '—'} |`);
  L.push('');
  L.push('## EVIDENCIAS');
  L.push('');
  for (const e of ev.archivos ?? []) L.push(`- \`${e}\``);
  L.push('');
  L.push('## CONCLUSIONES Y ACCIONES RECOMENDADAS (BORRADOR)');
  L.push('');
  for (const ver of ev.resultado_propuesto.casos) {
    if (ver.estado === ESTADOS.APROBADO) L.push(`- ${ver.caso}: comportamiento esperado confirmado en TEST.`);
    else if (ver.estado === ESTADOS.RECHAZADO) L.push(`- ${ver.caso}: reportar a Desarrollo el incumplimiento observado, con las aserciones fallidas como evidencia.`);
    else if (ver.estado === ESTADOS.BLOQUEADO) L.push(`- ${ver.caso}: resolver la dependencia indicada y reejecutar como reintento técnico o nueva evaluación, según corresponda.`);
    else L.push(`- ${ver.caso}: el escenario no se inició; revisar el registro de la ejecución.`);
  }
  L.push('');
  L.push('_Conclusiones finales: a completar por QA tras revisar las evidencias._');
  L.push('');
  return L.join('\n');
}
