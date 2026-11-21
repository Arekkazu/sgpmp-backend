#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { CASOS, CAPACIDADES, LIMITE, ORACULO, SEMILLA, VALORES, VALORES_ALERTA, cuerpoSensor, cuerpoTelemetria, cuerpoAlerta, diagnosticarPagina, validarSemillaPersistente, registrarAlertaDeArea, estadoDashboard } from './lib/g92_escenario.mjs';
import { sanearArtefacto } from './lib/g92_seguridad.mjs';
import { generarInformeG92 } from './lib/g92_informe.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const COLECCION = path.join(DIR, 'G92.postman_collection.json');
const LIMITE_CON_CANARIOS = LIMITE.solicitudes_directas + 2;
const json = (x) => JSON.stringify(x, null, 2);
const afirmar = (v, m) => { if (!v) throw new Error(m); };
const numero = (v, m) => { const n = Number(v); afirmar(Number.isSafeInteger(n) && n > 0, m); return n; };
const limpio = (x, secretos) => sanearArtefacto(String(x), secretos).slice(0, 400);
export function umbralAmbientalSeguro(variables, umbrales) {
  const nombre = (x) => String(x ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_|_$/g, '');
  if (!Array.isArray(variables?.items) || Number(variables.total) !== variables.items.length
    || !Array.isArray(umbrales?.items)) return false;
  const temperatura = variables.items.filter((x) =>
    [x.codigo, x.nombre].some((valor) => nombre(valor) === 'TEMPERATURA_AMBIENTAL'));
  if (temperatura.length !== 1 || !Number.isSafeInteger(Number(temperatura[0].id_variable_ambiental))
    || Number(temperatura[0].id_variable_ambiental) <= 0) return false;
  const idVariable = Number(temperatura[0].id_variable_ambiental);
  return umbrales.items.some((x) => x.es_activo &&
    Number(x.id_umbral_ambiental) === 70 && Number(x.id_especie) === 126 &&
    Number(x.id_variable_ambiental) === idVariable && Number(x.valor_min) === 15 &&
    Number(x.valor_max) === 30 && x.niveles?.some((n) => n.nivel === 'normal' &&
        Number(n.limite_inferior) <= VALORES.VERDE &&
        Number(n.limite_superior) >= VALORES.VERDE) &&
      x.niveles?.some((n) => n.nivel === 'normal' &&
        Number(n.limite_inferior) <= VALORES_ALERTA.ROJO &&
        Number(n.limite_superior) >= VALORES_ALERTA.ROJO));
}
export function clasificarRollback(escritura, verificado = false) {
  return Object.values(escritura).every((cantidad) => cantidad === 0)
    ? 'SIN_ESCRITURAS_QUE_REVERTIR' : verificado ? 'VERIFICADO' : 'NO_VERIFICADO';
}
export function relojServidor({ margenMs = 42_000, ventanaMs = 18_000, pasoMs = 250,
  ahora = () => performance.now() } = {}) {
  let muestra = null, apertura = null, ultima = null;
  return {
    observar(fecha) {
      const ms = Date.parse(fecha);
      if (Number.isFinite(ms)) muestra = { ms, instante: ahora() };
    },
    instante() {
      afirmar(muestra, 'HORA_SERVIDOR_AUSENTE');
      return muestra.ms + Math.max(0, ahora() - muestra.instante);
    },
    fijarInicio(fecha) {
      const ms = Date.parse(fecha);
      afirmar(Number.isFinite(ms), 'HORA_APERTURA_RUN_AUSENTE');
      if (apertura === null) apertura = ms;
    },
    inicioRun() {
      afirmar(apertura !== null, 'HORA_APERTURA_RUN_AUSENTE');
      return apertura;
    },
    async marca({ asociacion, calibracion }) {
      afirmar(Number.isFinite(Date.parse(asociacion)) && Number.isFinite(Date.parse(calibracion)),
        'FECHAS_SENSOR_AUSENTES');
      const inicio = this.inicioRun();
      const siguiente = ultima === null ? inicio - margenMs - ventanaMs : ultima + pasoMs;
      afirmar(siguiente <= inicio - margenMs, 'VENTANA_MARCAS_AGOTADA');
      afirmar(siguiente >= Date.parse(calibracion), 'MARCA_ANTERIOR_CALIBRACION');
      afirmar(siguiente >= Date.parse(asociacion), 'MARCA_ANTERIOR_ASOCIACION');
      afirmar(siguiente > this.instante() - 72 * 3600_000, 'MARCA_FUERA_BUFFER_72H');
      ultima = siguiente;
      return new Date(siguiente).toISOString();
    },
  };
}
export function evaluarRlsSinFinca(lectura, creacion) {
  const vista = lectura.json?.data ?? lectura.json;
  const vacia = lectura.status === 200 && vista?.total != null && Number(vista.total) === 0 &&
    Array.isArray(vista.items) && vista.items.length === 0;
  const lecturaDenegada = [403, 404].includes(lectura.status) || vacia;
  const visible = lectura.status === 200 && Array.isArray(vista?.items) && vista.items.length > 0;
  const idCreado = creacion.json?.data?.id_sensores ?? creacion.json?.id_sensores;
  const creado = [200, 201].includes(creacion.status) &&
    Number.isSafeInteger(Number(idCreado)) && Number(idCreado) > 0;
  const denegado = [403, 404].includes(creacion.status) &&
    !(idCreado != null && Number(idCreado) > 0);
  const porRol = creacion.status === 403 &&
    (creacion.json?.error_code ?? creacion.json?.error) === 'ACCESO_DENEGADO';
  return { estado: visible || creado ? 'FALLA' : lecturaDenegada && denegado
    ? 'APROBADO' : 'NO_CONCLUYENTE',
    motivo: `Lectura HTTP ${lectura.status}${vacia ? ' con total 0 e items []' : ''}; creación HTTP ${creacion.status}${porRol ? ' ACCESO_DENEGADO por rol: no aísla RLS de INSERT' : ''}; UPDATE no expuesto por API pública` };
}
export function registroOficial(r, existe = () => false) {
  const ids = Object.values(CAPACIDADES.comprobaciones_obligatorias).flatMap((x) => x.API);
  const canarios = r.canarios ?? [];
  const canariosCompletos = ['previo-newman', 'cierre'].every((fase) =>
    new Set(canarios.filter((x) => x.fase === fase && x.seguro).map((x) => x.area)).size === 2)
    && canarios.every((x) => x.seguro && r.evidencias.includes(x.evidencia));
  return ids.every((id) => r.comprobaciones.some((x) => x.id === id && x.tipo === 'ASSERT'
    && ['APROBADO', 'RECHAZADO'].includes(x.estado)))
    && CASOS.every((id) => ['APROBADO', 'RECHAZADO'].includes(r.casos[id].estado))
    && r.cierre.run.cierre_http === 200 && r.cierre.rollback.verificado === true
    && r.newman.length === 1 && canariosCompletos && r.evidencias.every(existe);
}
export function diagnosticarCanario(http, cuerpo, { permitirVacia = false, area } = {}) {
  const sensores = cuerpo?.sensores;
  const sensor = Array.isArray(sensores) ? sensores[0] : null;
  const observado = sensor ? {
    id_sensor: sensor.id_sensor, id_infraestructura: sensor.id_infraestructura,
    estado_semaforo: sensor.estado_semaforo,
    dato_desactualizado: sensor.dato_desactualizado, sin_umbral: sensor.sin_umbral,
    etiqueta_sin_umbral: JSON.stringify(sensor).includes('Sin umbral configurado')
  } : null;
  let motivo = null;
  if (http !== 200 || !Array.isArray(sensores) || sensores.length > 1 ||
    !Number.isSafeInteger(Number(cuerpo?.total)) || Number(cuerpo?.total) < sensores.length ||
    (sensor && (!Number.isSafeInteger(Number(sensor.id_sensor)) || Number(sensor.id_sensor) <= 0 ||
      Number(sensor.id_infraestructura) !== Number(area))))
    motivo = 'RESPUESTA_INVALIDA';
  else if (sensor?.sin_umbral === true || observado?.etiqueta_sin_umbral ||
    (sensor?.estado_semaforo === 'GRIS' && sensor?.dato_desactualizado === false))
    motivo = 'SIN_UMBRAL';
  else if (!sensor && !(permitirVacia && Number(cuerpo?.total) === 0))
    motivo = 'SENSOR_AUSENTE';
  else if (sensor?.estado_semaforo === 'GRIS' && sensor?.dato_desactualizado !== true)
    motivo = 'GRIS_NO_CONCLUYENTE';
  return { seguro: motivo === null, motivo, sensor: observado };
}
export async function canariosAntesDashboard(areas, consultar) {
  for (const area of new Set(areas)) if (!(await consultar(area))) return false;
  return true;
}
export function comprobar({ dir = DIR } = {}) {
  const originales = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('RED_PROHIBIDA_EN_COMPROBAR'); };
  try {
    const archivos = ['g92.mjs', 'G92.postman_collection.json', 'README.md',
      'lib/contrato_ejecutor.mjs', 'lib/g92_escenario.mjs', 'lib/g92_seguridad.mjs',
      'lib/g92_informe_incidencias.mjs', 'lib/g92_informe.mjs',
       'pruebas/g92.test.mjs', 'pruebas/validar_cuerpos_g92.py'];
    const ausentes = archivos.filter((x) => !fs.existsSync(path.join(dir, x)));
    const tecnicos = ['20261025-072518', '20261025-075632', '20261031-010617',
      '20261031-011456', '20261031-012236', '20261031-013032',
      '20261031-015906', '20261031-020549', '20261031-021342'];
    const activos = [...archivos, 'BLOQUEO.md'].filter((x) => fs.existsSync(path.join(dir, x)));
    const referenciasTecnicas = activos.filter((x) => {
      if (x === 'README.md') return false; // El historial es texto documental.
      const contenido = fs.readFileSync(path.join(dir, x), 'utf8');
      return tecnicos.some((id) => contenido.includes(`RUN-G92-V1-${id}`));
    });
    const c = JSON.parse(fs.readFileSync(path.join(dir, 'G92.postman_collection.json'), 'utf8'));
    const scripts = [...(c.event ?? []), ...(c.item ?? []).flatMap((x) => x.event ?? [])];
    for (const e of scripts) new vm.Script((e.script?.exec ?? []).join('\n'));
    const texto = json(c);
    const ids = Object.values(CAPACIDADES.comprobaciones_obligatorias).flatMap((x) => x.API);
     const muestra = { comprobaciones: ids.map((id) => ({ id, tipo: 'ASSERT', estado: 'APROBADO' })),
       casos: Object.fromEntries(CASOS.map((id) => [id, { estado: 'APROBADO' }])),
       cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
       canarios: ['previo-newman', 'cierre'].flatMap((fase) => [1, 2].map((area) =>
         ({ fase, area, seguro: true, evidencia: `api/E7-CANARIO-${fase}-${area}.json` }))),
       newman: [{}], evidencias: ['resultado.json', 'TC-M03-G92_resultado.md',
         'newman/newman-TC-M03-G92.json', 'newman/newman-TC-M03-G92.html',
         ...['previo-newman', 'cierre'].flatMap((fase) => [1, 2].map((area) =>
           `api/E7-CANARIO-${fase}-${area}.json`))] };
     const evidenciasSimuladas = new Set(muestra.evidencias);
     const oficialidadEmulada = registroOficial(muestra, (x) => evidenciasSimuladas.has(x))
       && !registroOficial(muestra, (x) => x !== 'TC-M03-G92_resultado.md')
       && !registroOficial({ ...muestra, cierre: { ...muestra.cierre,
         rollback: { verificado: false } } }, (x) => evidenciasSimuladas.has(x));
    const valido = !ausentes.length && !referenciasTecnicas.length
      && CAPACIDADES.contrato === 'sigab-qa-ejecutor/1'
       && ids.length === 6 && new Set(ids).size === 6 && c.item?.length === 1
      && CASOS.every((caso) => CAPACIDADES.comprobaciones_obligatorias[caso]?.API?.length > 0)
      && texto.includes('X-Test-Run-Id') && texto.includes('X-Sandbox-Secret')
       && !texto.includes('test-control/query') && !texto.includes('access_key')
       && oficialidadEmulada
       && diagnosticarCanario(200, { total: 1, sensores: [{ id_sensor: 1, id_infraestructura: 2, estado_semaforo: 'VERDE' }] }, { area: 2 }).seguro
       && !diagnosticarCanario(200, { total: 1, sensores: [{ id_sensor: 1, id_infraestructura: 2, estado_semaforo: 'GRIS', dato_desactualizado: false }] }, { area: 2 }).seguro
       && !diagnosticarCanario(200, { total: 1, sensores: [{ id_sensor: 1, id_infraestructura: 2, sin_umbral: true }] }, { area: 2 }).seguro;
    console.log(json({ comprobacion: 'G92_LOCAL_SIN_RED', valido, ausentes, referenciasTecnicas,
      casos: CASOS, limite: { ...LIMITE, solicitudes_directas: LIMITE_CON_CANARIOS },
      comprobaciones_obligatorias: CAPACIDADES.comprobaciones_obligatorias }));
    return valido ? 0 : 2;
  } finally { globalThis.fetch = originales; }
}
function leerEnv() {
  const x = {};
  const archivo = path.join(RAIZ, '.env.qa');
  if (fs.existsSync(archivo)) for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z0-9_]+)\s*=(.*)$/);
    if (m) x[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  Object.assign(x, process.env);
  x.QA_AUTORIZADO = process.env.QA_AUTORIZADO;
  return x;
}
export function preflight(contrato, env) {
  const vars = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL',
    'QA_ADMIN_PASSWORD', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD', 'BROKER_SERVICE_TOKEN',
    'QA_G92_A_SERIAL', 'QA_G92_B_SERIAL'];
  const barreras = vars.filter((x) => !String(env[x] ?? '').trim());
  if (!CAPACIDADES.operaciones.includes(contrato.operacion)) barreras.push('OPERACION_NO_PUBLICADA');
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (!/^https?:\/\//.test(env.SIGAB_API_TEST_BASE ?? '')) barreras.push('BASE_TEST_INVALIDA');
  if (contrato.version > 1 && contrato.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  if (!fs.existsSync(COLECCION)) barreras.push('COLECCION_AUSENTE');
  const n = spawnSync('newman', ['--version'], { encoding: 'utf8',
    shell: process.platform === 'win32', timeout: 5000 });
  if (n.error || n.status !== 0) barreras.push('NEWMAN_AUSENTE');
  const global = spawnSync('npm', ['root', '-g'], { encoding: 'utf8',
    shell: process.platform === 'win32', timeout: 5000 });
  const raices = [path.join(RAIZ, 'node_modules'), path.join(DIR, 'node_modules'),
    ...(process.env.NODE_PATH ?? '').split(path.delimiter).filter(Boolean),
    ...(global.status === 0 ? [global.stdout.trim()] : [])];
  if (!raices.some((raiz) => fs.existsSync(path.join(raiz, 'newman-reporter-htmlextra'))))
    barreras.push('NEWMAN_REPORTERO_HTML_AUSENTE');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G92', run_id: contrato.runId,
    operacion: contrato.operacion, version: contrato.version,
    variables: vars.map((nombre) => ({ nombre, presente: Boolean(env[nombre]) })),
    plan: { finca: 184, areas_persistentes: SEMILLA.areas,
      dispositivos_persistentes: SEMILLA.dispositivos, sensores_persistentes: 63,
      sensores_nuevos_maximo: 2, gateway_asignado: false,
      validacion_en_run: 'GET de finca, areas, dispositivos, sensores, asociaciones, calibraciones, alertas e historial antes de escribir' },
    limites: { ...LIMITE, solicitudes_directas: LIMITE_CON_CANARIOS }, barreras, ok: barreras.length === 0 };
}
export function crearTransporte({ base, runId, secreto, bitacora, secretos, permitidos = {}, fetcher = fetch, limite = LIMITE_CON_CANARIOS }) {
  let abierto = false, cerrado = false, cuenta = 0, consecutivos5xx = 0;
  const reloj = relojServidor();
  const escritura = { sensores: 0, telemetrias: 0, alertas: 0 };
  const patrones = [
    ['sensores', /^\/configuracion\/dispositivos-iot\/\d+\/sensores$/, LIMITE.sensores],
    ['telemetrias', /^\/iot\/telemetria$/, LIMITE.telemetrias],
    ['alertas', /^\/iot\/alertas$/, LIMITE.alertas],
  ];
  const ids = { dispositivos: permitidos.dispositivos ?? new Map(),
    sensores: permitidos.sensores ?? new Map(), telemetrias: permitidos.telemetrias ?? new Set() };
  const mismo = (a, b) => Number(a) === Number(b);
  function comprobarDestino(tipo, pathname, cuerpo) {
    afirmar(cuerpo && typeof cuerpo === 'object', 'CUERPO_AUSENTE');
    if (tipo === 'sensores') afirmar(Number(pathname.split('/')[3]) === 785 &&
      ids.dispositivos.has(785), 'ID_FUERA_LISTA_BLANCA');
    if (tipo === 'telemetrias' || tipo === 'alertas') {
      const sensor = ids.sensores.get(Number(cuerpo.sensor_id));
      afirmar(sensor && mismo(sensor.dispositivo, cuerpo.device_id) &&
        cuerpo.serial === ids.dispositivos.get(sensor.dispositivo)?.serial &&
        (tipo !== 'alertas' || ids.telemetrias.has(Number(cuerpo.id_telemetria))), 'ID_FUERA_LISTA_BLANCA');
    }
  }
  async function solicitar(metodo, ruta, { token, cuerpo, cierre = false, fuera = false, negativa = false } = {}) {
    const pathname = ruta.split('?')[0];
    // El margen se reserva al cierre; este nunca se omite por el contador.
    if (!cierre && !cerrado) afirmar(cuenta < limite - LIMITE.margen_cierre,
      'LIMITE_SOLICITUDES_FUNCIONALES');
    cuenta++;
    if (fuera) afirmar(!abierto && metodo === 'POST' && pathname === '/sesiones/', 'LOGIN_DENTRO_RUN_PROHIBIDO');
    else if (cierre) afirmar(abierto && metodo === 'DELETE' && pathname === `/test-control/runs/${runId}`, 'CIERRE_NO_PERMITIDO');
    else {
      afirmar(abierto || (cerrado && metodo === 'GET'), 'PETICION_FUERA_RUN');
      if (metodo !== 'GET') {
        const regla = patrones.find(([, re]) => re.test(pathname));
        afirmar(metodo === 'POST' && regla, 'ESCRITURA_FUERA_LISTA_BLANCA');
        const [tipo, , max] = regla;
        comprobarDestino(tipo, pathname, cuerpo);
        afirmar(++escritura[tipo] <= max, `LIMITE_${tipo.toUpperCase()}`);
        if (tipo === 'telemetrias' || tipo === 'alertas') afirmar(token && !('access_key' in cuerpo)
          && Number.isInteger(Number(cuerpo.sensor_id)) && cuerpo.serial, 'BROKER_CUERPO_INVALIDO');
      }
    }
    const dentro = abierto && !fuera && !cierre;
    const headers = { Accept: 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (dentro) { headers['X-Test-Run-Id'] = runId; headers['X-Sandbox-Secret'] = secreto; }
    if (cierre) headers['X-Sandbox-Secret'] = secreto;
    if (cuerpo !== undefined) headers['Content-Type'] = 'application/json';
    const start = Date.now();
    try {
      const res = await fetcher(base + ruta, { method: metodo, headers,
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
        signal: AbortSignal.timeout(30000), redirect: 'manual' });
      const raw = await res.text(); let body;
      try { body = JSON.parse(raw); } catch { body = null; }
      const fechaServidor = res.headers.get('Date');
      if (dentro && metodo === 'GET' && pathname === '/usuarios/me' && res.status === 200 && fechaServidor)
        reloj.fijarInicio(fechaServidor);
      if (fechaServidor) reloj.observar(fechaServidor);
      else if (body?.data?.fecha_asociacion) reloj.observar(body.data.fecha_asociacion);
      else if (body?.fecha_asociacion) reloj.observar(body.fecha_asociacion);
      const eco = res.headers.get('X-Test-Run-Id');
       bitacora.push({ metodo, ruta, en_run: dentro,
        http: res.status, eco_run: dentro ? eco === runId : null,
        ms: Date.now() - start, ...(pathname === '/sesiones/' ?
          (res.status >= 400 ? { cuerpo_error: sanearArtefacto(raw, secretos),
            cuerpo_solicitud: JSON.parse(sanearArtefacto(json(cuerpo), secretos)) } : {}) :
           { respuesta: JSON.parse(sanearArtefacto(json(body), secretos)),
             ...(res.status >= 400 ? { cuerpo_error: sanearArtefacto(raw, secretos),
               ...(metodo !== 'GET' && cuerpo !== undefined ?
                 { cuerpo_solicitud: JSON.parse(sanearArtefacto(json(cuerpo), secretos)) } : {}) } : {}) }) });
       consecutivos5xx = res.status >= 500 ? consecutivos5xx + 1 : 0;
       if (consecutivos5xx >= 3) throw new Error('TRES_5XX_CONSECUTIVOS');
       if (res.status === 403 && !negativa && !cierre) throw new Error('CLAVE_O_ACCESO_403');
      if (dentro) afirmar(eco === runId, 'ECO_RUN_AUSENTE');
      if (cierre && res.status === 200) { abierto = false; cerrado = true; }
      return { status: res.status, json: body,
        ...(pathname === '/sesiones/' && (res.status !== 200 || !body?.token)
          ? { cuerpo_error: limpio(raw, secretos) } : {}) };
    } catch (e) {
      bitacora.push({ metodo, ruta,
        en_run: dentro, error: limpio(e.message, secretos), ms: Date.now() - start,
        ...(metodo !== 'GET' && cuerpo !== undefined ?
          { cuerpo_solicitud: JSON.parse(sanearArtefacto(json(cuerpo), secretos)) } : {}) });
      throw e;
    }
  }
  return { solicitar, reloj, abrir: () => { abierto = true; }, estado: () => ({ abierto, cuenta,
    exceso_cierre: Math.max(0, cuenta - limite), escritura }) };
}
export function ejecutarNewman({ contrato, variables, fases, secretos }) {
  afirmar(Array.isArray(fases) && fases.length >= 1 && fases.length <= 4, 'FASES_NEWMAN_INVALIDAS');
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g92-newman-'));
  try {
    const env = path.join(temp, 'env.json'), rep = path.join(temp, 'reporte.json');
    const datos = path.join(temp, 'fases.json');
    fs.writeFileSync(datos, json(fases));
    fs.writeFileSync(env, json({ values: Object.entries(variables).map(([key, value]) =>
      ({ key, value: String(value ?? ''), enabled: true })) }), { mode: 0o600 });
    const cmd = spawnSync('newman', ['run', COLECCION, '-e', env, '-d', datos, '--reporters', 'json,htmlextra',
       '--reporter-json-export', rep, '--reporter-htmlextra-export', path.join(temp, 'reporte.html'),
       '--timeout-request', '30000', '--color', 'off'],
    { encoding: 'utf8', shell: process.platform === 'win32', timeout: 150_000 });
    afirmar(fs.existsSync(rep) && fs.existsSync(path.join(temp, 'reporte.html')) && !cmd.error,
      `NEWMAN_SIN_REPORTE_${cmd.error?.code ?? cmd.status}`);
    const bruto = JSON.parse(fs.readFileSync(rep, 'utf8'));
    const ejecuciones = bruto.run?.executions ?? [];
    afirmar(ejecuciones.length === fases.length, 'NEWMAN_EJECUCIONES_INVALIDAS');
    const archivo = 'newman/newman-TC-M03-G92.json';
    const html = 'newman/newman-TC-M03-G92.html';
    fs.mkdirSync(path.join(contrato.directorio, 'newman'), { recursive: true });
    fs.writeFileSync(path.join(contrato.directorio, archivo), sanearArtefacto(json(bruto), secretos));
    fs.writeFileSync(path.join(contrato.directorio, html), sanearArtefacto(fs.readFileSync(path.join(temp, 'reporte.html'), 'utf8'), secretos));
    const respuestas = ejecuciones.map((ex, i) => {
      let cuerpo = null;
      try { cuerpo = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { /* no JSON */ }
      return { fase: fases[i].fase, cuerpo, http: ex.response?.code ?? null,
        eco: (ex.response?.header ?? []).some((h) => String(h.key).toLowerCase() === 'x-test-run-id'
          && h.value === variables.run_id) };
    });
    return { archivo, html, respuestas, proceso: cmd.status,
      fallos: (bruto.run?.failures ?? []).map((f) => limpio(f.error?.message ?? '', secretos)),
      aserciones: bruto.run?.stats?.assertions?.total ?? 0 };
  } finally { fs.rmSync(temp, { recursive: true, force: true }); }
}
export function informe(r) {
  return generarInformeG92(r);
}

export async function autenticarSinFinca(solicitar, env, secretos) {
  if (!env.QA_PROD_SIN_FINCA_EMAIL || !env.QA_PROD_SIN_FINCA_PASSWORD)
    return { token: null, motivo: 'Variables de cuenta sin finca ausentes' };
  try {
    const x = await solicitar('POST', '/sesiones/', { fuera: true, negativa: true,
      cuerpo: { correo_electronico: env.QA_PROD_SIN_FINCA_EMAIL,
        contrasena: env.QA_PROD_SIN_FINCA_PASSWORD } });
    if (x.status !== 200 || !x.json?.token)
      return { token: null, motivo: `Login cuenta sin finca HTTP ${x.status}; cuerpo de error saneado ${JSON.stringify(x.cuerpo_error ?? 'SIN_CUERPO')}` };
    secretos.push(x.json.token);
    return { token: x.json.token, motivo: null };
  } catch (e) {
    return { token: null, motivo: `Login cuenta sin finca HTTP no disponible; error saneado ${JSON.stringify(limpio(e.message, secretos))}` };
  }
}

export function rlsSinFincaNoConcluyente(motivo) {
  return { id: 'RLS-G92-02', estado: 'NO_CONCLUYENTE',
    motivo: `${motivo ?? 'Cuenta sin alcance no acreditada por /usuarios/me'}; UPDATE no expuesto por API pública`,
    evidencia: 'resultado.json' };
}

export async function evaluar(contrato, { env = leerEnv(), newman = ejecutarNewman,
  fetcher = fetch, limiteDirectas = LIMITE_CON_CANARIOS } = {}) {
  fs.mkdirSync(contrato.directorio, { recursive: true });
  const previo = preflight(contrato, env);
  fs.writeFileSync(path.join(contrato.directorio, 'preflight.json'), json(previo));
  const secretos = [env.QA_SANDBOX_SECRET, env.BROKER_SERVICE_TOKEN,
    env.QA_G92_A_SERIAL, env.QA_G92_B_SERIAL,
    env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD, env.QA_PROD_EMAIL,
    env.QA_PROD_PASSWORD, env.QA_PROD_SIN_FINCA_EMAIL,
    env.QA_PROD_SIN_FINCA_PASSWORD].filter(Boolean);
  const r = { grupo: 'G92', rf: 'RF-58', run_id: contrato.runId,
    version: contrato.version, autorizacion: contrato.referencia, directorio: contrato.directorio,
    commit: contrato.contexto?.commit ?? 'NO_VERIFICADO', oficial: false,
    consume_version: false, estado: 'NO_CONCLUYENTE',
    casos: Object.fromEntries(CASOS.map((id) => [id, { estado: 'NO_EJECUTADA',
      veredicto: null, estado_tecnico: 'NO_EJECUTADA', comprobaciones: [], observado: null }])),
     comprobaciones: [], datos: { ids_telemetria: [], ids_alerta: [], consolidaciones_alerta: [], inventario: [],
      sensores_creados: [] },
     newman: [], bitacora: [], problemas_tecnicos: [], comprobaciones_tecnicas: [], canarios: [],
    presupuesto: { nominal_directas: 380, maximo_directas: limiteDirectas - LIMITE.margen_cierre,
      tope_operativo_directas: limiteDirectas, margen_cierre: LIMITE.margen_cierre,
      solicitudes_directas: 0, exceso_cierre: 0 },
     cierre: { run: { cierre_http: null }, rollback: { estado: 'NO_VERIFICADO', verificado: false, semilla_intacta: false,
       comprobaciones: [], riesgos_residuales: ['Correo E7 y auditoria de GET no se revierten por DELETE.'] }, motivo: 'NO_EJECUTADO' },
    evidencias: ['preflight.json', 'resultado.json', contrato.version === 1
      ? 'TC-M03-G92_resultado.md' : `TC-M03-G92_reevaluacion_V${contrato.version}.md`] };
  const base = (env.SIGAB_API_TEST_BASE ?? '').replace(/\/$/, '');
  const runIdHeader = contrato.runId.slice(4);
   const permitidos = { dispositivos: new Map(), sensores: new Map(), telemetrias: new Set() };
   const transporte = crearTransporte({ base, runId: runIdHeader, secreto: env.QA_SANDBOX_SECRET,
     bitacora: r.bitacora, secretos, permitidos, fetcher, limite: limiteDirectas });
  const { reloj } = transporte;
  let fallosEscritura = 0;
  const solicitar = async (metodo, ruta, opciones = {}) => {
    const antes = r.bitacora.length;
    let respuesta;
    try { respuesta = await transporte.solicitar(metodo, ruta, opciones); return respuesta; }
    finally {
      if (metodo !== 'GET' && (respuesta?.status >= 400 ||
        (!respuesta && r.bitacora.length > antes))) {
        const registro = r.bitacora.slice(antes).find((x) => x.http >= 400) ?? r.bitacora.at(-1);
        const evidencia = `api/ESCRITURA-FALLIDA-${String(++fallosEscritura).padStart(3, '0')}.json`;
        fs.mkdirSync(path.join(contrato.directorio, 'api'), { recursive: true });
        fs.writeFileSync(path.join(contrato.directorio, evidencia), sanearArtefacto(json({
          metodo, ruta, cuerpo_solicitud: opciones.cuerpo, respuesta: registro,
        }), secretos));
        r.evidencias.push(evidencia);
      }
    }
  };
  let tokenAdmin, tokenProd, tokenSinFinca, motivoLoginSinFinca, semillaAntes = null, dashboardAntes = null, A, B, dispositivoA, dispositivoB;
  let e7Detenido = false;
  let alcanceA = false, alcanceB = false;
  const auth = async (rol) => {
    const x = await solicitar('POST', '/sesiones/', { fuera: true,
      cuerpo: { correo_electronico: env[`QA_${rol}_EMAIL`], contrasena: env[`QA_${rol}_PASSWORD`] } });
    afirmar(x.status === 200 && x.json?.token, `LOGIN_${rol}_HTTP_${x.status}`);
    secretos.push(x.json.token); return x.json.token;
  };
  const registrarErrorTecnico = (e) => {
    const ultimo = r.bitacora.at(-1);
    if (ultimo?.ruta?.startsWith('/iot/monitoreo/dashboard?id_infraestructura=') &&
      /timeout|timed out|aborted/i.test(String(e.message))) {
      r.problemas_tecnicos.push(`Timeout técnico QA: GET ${ultimo.ruta}; fase ${r.cierre.run.cierre_http === 200 ? 'cierre fuera del RUN' : 'preparación dentro del RUN'}; ${ultimo.ms} ms (límite 30000 ms). Funcionalidad NO_CONCLUYENTE; sin atribución al producto.`);
    } else r.problemas_tecnicos.push(limpio(e.message, secretos));
  };
  const get = async (ruta, token = tokenAdmin) => {
    const x = await solicitar('GET', ruta, { token });
    afirmar(x.status === 200, `GET_${ruta.split('?')[0]}_HTTP_${x.status}`);
    return x.json?.data ?? x.json;
  };
  const canario = async (area, fase, permitirVacia = false) => {
    if (e7Detenido) return false;
    const ruta = `/iot/monitoreo/dashboard?id_infraestructura=${area}&pagina=1&por_pagina=1`;
    let http = null, diagnostico;
    try {
      const x = await solicitar('GET', ruta, { token: tokenProd });
      http = x.status;
      diagnostico = diagnosticarCanario(http, x.json?.data ?? x.json, { permitirVacia, area });
    } catch (e) { diagnostico = { seguro: false, motivo: `PETICION_FALLIDA: ${limpio(e.message, secretos)}`, sensor: null }; }
    const evidencia = `api/E7-CANARIO-${fase}-${area}.json`;
    const registro = { fase, area, ruta, http, ...diagnostico, evidencia };
    fs.mkdirSync(path.join(contrato.directorio, 'api'), { recursive: true });
    fs.writeFileSync(path.join(contrato.directorio, evidencia), sanearArtefacto(json(registro), secretos));
    r.canarios.push(registro); r.evidencias.push(evidencia);
    if (!registro.seguro) {
      e7Detenido = true;
      r.problemas_tecnicos.push(`E7-CANARIO: ${fase}, área ${area}, ${registro.motivo}; consultas grandes restantes suspendidas; evidencia ${evidencia}`);
    }
    return registro.seguro;
  };
  const post = async (ruta, cuerpo, token = tokenAdmin) => {
    const x = await solicitar('POST', ruta, { token, cuerpo });
    afirmar(x.status === 201, `POST_${ruta}_HTTP_${x.status}`);
    return x.json?.data ?? x.json;
  };
  const inventariar = (tipo, id, depende_de) => r.datos.inventario.push({ tipo, id, depende_de });
  const listaCompleta = (x, max, nombre) => {
    afirmar(Array.isArray(x?.items) && Number.isSafeInteger(Number(x.total)) &&
      Number(x.total) === x.items.length && x.items.length <= max && x.truncado !== true,
    `BASELINE_${nombre}_INCOMPLETO`);
    return x.items;
  };
  const semilla = async () => {
    const finca = await get('/configuracion/fincas/184', tokenProd);
    const areas = [], dispositivos = [], sensores = [], asociaciones = [], calibraciones = [];
    for (let i = 0; i < 2; i++) {
      const area = SEMILLA.areas[i], dispositivo = SEMILLA.dispositivos[i];
      areas.push(await get(`/configuracion/infraestructuras/${area}`, tokenProd));
      dispositivos.push(await get(`/configuracion/dispositivos-iot/${dispositivo}`));
      const lista = await get(`/configuracion/dispositivos-iot/${dispositivo}/sensores`);
      sensores.push(listaCompleta(lista, i ? 3 : 60, `SENSORES_${area}`)
        .sort((a, b) => Number(a.id_sensores) - Number(b.id_sensores)));
    }
    const ids = [...SEMILLA.sensoresA, ...SEMILLA.sensoresB];
    for (const id of ids) {
      asociaciones.push(listaCompleta(await get(`/configuracion/sensores/${id}/asociaciones`), 2, `ASOCIACIONES_${id}`));
      calibraciones.push(listaCompleta(await get(`/configuracion/sensores/${id}/calibraciones`), 2, `CALIBRACIONES_${id}`));
    }
    const alertas = [], historial = [];
    const fechaInicio = SEMILLA.asociadaDesde.slice(0, 10);
    const fechaFin = new Date().toISOString().slice(0, 10);
    for (const area of SEMILLA.areas) {
      alertas.push(await get(`/iot/alertas?id_infraestructura=${area}&por_pagina=200`));
      historial.push(await get(`/iot/monitoreo/historial?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}&id_infraestructura=${area}&por_pagina=500`));
    }
    return { finca, areas, dispositivos, sensores, asociaciones, calibraciones, alertas, historial };
  };
  const acreditarSemilla = (datos) => {
    const errores = validarSemillaPersistente(datos,
      [env.QA_G92_A_SERIAL, env.QA_G92_B_SERIAL], reloj.inicioRun());
    afirmar(errores.length === 0, `SEMILLA_PERSISTENTE_INCOMPATIBLE:${errores.slice(0, 5).join(',')}`);
    const ids = [...SEMILLA.sensoresA, ...SEMILLA.sensoresB];
    for (const [i, id] of ids.entries()) {
      const area = i < 60 ? 697 : 698, dispositivo = i < 60 ? 785 : 786;
      fechasSensor.set(id, { asociacion: datos.asociaciones[i][0].fecha_asociacion,
        calibracion: datos.calibraciones[i][0].fecha_calibracion });
      permitidos.sensores.set(id, { dispositivo, area });
    }
    permitidos.dispositivos.set(785, { area: 697, serial: env.QA_G92_A_SERIAL });
    permitidos.dispositivos.set(786, { area: 698, serial: env.QA_G92_B_SERIAL });
    alcanceA = alcanceB = true;
  };
  const fechasSensor = new Map();
  const alertasPorArea = new Map();
  const crearSensorRls = async () => {
    const x = await post('/configuracion/dispositivos-iot/785/sensores', cuerpoSensor('RLS'));
    const id = numero(x.id_sensores, 'SENSOR_RLS_SIN_ID');
    r.datos.sensores_creados.push(id);
    inventariar('sensor', id, { dispositivo: 785 });
    return id;
  };
  const marcaActual = async (sensor) => reloj.marca(fechasSensor.get(sensor) ?? {});
  const ingestar = async (dispositivo, sensor, color = 'VERDE', valor = VALORES[color]) => {
    const x = await post('/iot/telemetria', cuerpoTelemetria({ dispositivo: dispositivo.id,
      sensor, serial: dispositivo.serial, marca: await marcaActual(sensor), color, valor }), env.BROKER_SERVICE_TOKEN);
    afirmar(x.estado_calidad === 'LECTURA_VALIDA', `INGESTA_CALIDAD_${x.estado_calidad}`);
    afirmar(x.estado_semaforo !== 'GRIS' && x.sin_umbral !== true,
      'RIESGO_AVISO_SIN_UMBRAL_INGESTA');
    const id = numero(x.id_telemetria, 'TELEMETRIA_SIN_ID');
    r.datos.ids_telemetria.push(id); permitidos.telemetrias.add(id);
    inventariar('telemetria', id, { sensor }); inventariar('estado_actual', sensor, { telemetria: id }); return id;
  };
  const alertar = async (dispositivo, sensor, idTelemetria, color) => {
    const severidad = color === 'ROJO' ? 'CRITICO' : 'LEVE';
    const x = await post('/iot/alertas', cuerpoAlerta({ dispositivo: dispositivo.id,
      sensor, serial: dispositivo.serial, marca: await marcaActual(sensor),
      telemetria: idTelemetria, color }), env.BROKER_SERVICE_TOKEN);
    const area = permitidos.sensores.get(sensor)?.area;
    const registro = registrarAlertaDeArea(x, area, alertasPorArea);
    const { id } = registro;
    if (registro.nueva) {
      r.datos.ids_alerta.push(id);
      inventariar('alerta', id, { sensor, telemetria: idTelemetria });
    } else r.datos.consolidaciones_alerta.push({ id_alerta: id, area, sensor,
      severidad, evidencia: 'resultado.json' });
    const d = await get(`/iot/alertas/${id}`);
    afirmar(d.estado_alerta === 'ACTIVA' && d.severidad === severidad &&
      Number(d.id_infraestructura) === area &&
      (registro.consolidada || Number(d.id_sensor) === sensor),
      'ALERTA_NO_ACREDITADA'); return id;
  };
  const umbralSeguro = async () => {
    const variables = await get('/configuracion/variables-ambientales');
    const umbrales = await get('/configuracion/umbrales?id_especie=126');
    afirmar(umbralAmbientalSeguro(variables, umbrales),
      'RIESGO_AVISO_SIN_UMBRAL_ANTES_DASHBOARD');
  };
  const dashboards = async (fases) => {
    await umbralSeguro();
    afirmar(fases.every((f) => Number.isSafeInteger(f.area) && f.area > 0), 'DASHBOARD_AREA_OBLIGATORIA');
    afirmar(await canariosAntesDashboard(fases.map((f) => f.area), (area) => canario(area, 'previo-newman')),
      'E7-CANARIO');
    const inicio = Date.now();
    let n;
    try {
      n = newman({ contrato, secretos,
        variables: { qa_autorizado: 'SI', base_url: base, run_id: runIdHeader,
          sandbox_secret: env.QA_SANDBOX_SECRET, token_productor: tokenProd,
          area_a: A, area_b: B },
        fases: fases.map(({ fase, area, pagina = 1 }) => ({ fase,
          consulta: `?id_infraestructura=${area}&pagina=${pagina}&por_pagina=50` })) });
    } catch (e) {
      const timeout = /timeout|timed out|aborted/i.test(String(e.message));
      throw new Error(`${timeout ? 'Timeout técnico QA: ' : ''}Newman dashboard filtrado dentro del RUN; ${Date.now() - inicio} ms; ${limpio(e.message, secretos)}`);
    }
    r.newman.push({ archivo: n.archivo, html: n.html, fallos: n.fallos,
      aserciones: n.aserciones, fases: n.respuestas.map((x) => ({ fase: x.fase, http: x.http })) });
    r.evidencias.push(n.archivo, n.html);
    for (const x of n.respuestas) r.bitacora.push({ metodo: 'GET',
      ruta: '/iot/monitoreo/dashboard', en_run: true, http: x.http,
      eco_run: x.eco, via: 'Newman', fase: x.fase });
    afirmar([0, 1].includes(n.proceso) && n.respuestas.every((x) => x.http === 200 && x.eco && x.cuerpo)
      && n.aserciones > 0,
      'NEWMAN_CONTEXTO_INVALIDO');
    return Object.fromEntries(n.respuestas.map((x) => [x.fase, x.cuerpo]));
  };
  const clasificar = (caso, checks, observado, evidencias) => {
    const c = r.casos[caso]; c.observado = observado;
    for (const [id, cumple] of Object.entries(checks).filter(([id]) => id.includes(caso.slice(-3)))) {
      const archivos = evidencias[id] ?? [];
      const check = { caso, fuente: 'API', id,
        tipo: id === 'API-181-03' ? 'OBS' : id.startsWith('PRE-') ? 'PRE' : 'ASSERT',
        estado: id === 'API-181-03' ? 'EXCLUIDA_DEL_ORACULO' : cumple ? 'APROBADO' : 'RECHAZADO',
        ...(id === 'API-181-03' ? { observado: cumple } : {}),
        ...(id === 'PRE-181-01' ? { observacion: observado.amarillo_no_construible_sandbox } : {}),
        evidencia: archivos[0] ?? null, evidencias: archivos };
      c.comprobaciones.push(check); r.comprobaciones.push(check);
    }
    const preFallido = c.comprobaciones.some((x) => x.tipo === 'PRE' && x.estado === 'RECHAZADO');
    c.estado_tecnico = preFallido ? 'NO_CONCLUYENTE' : 'OK';
    c.veredicto = preFallido ? null : c.comprobaciones.some((x) => x.tipo === 'ASSERT' && x.estado === 'RECHAZADO')
      ? 'RECHAZADO' : 'APROBADO';
    c.estado = c.veredicto ?? 'NO_CONCLUYENTE';
  };
  if (previo.ok) try {
    tokenAdmin = await auth('ADMIN'); tokenProd = await auth('PROD');
    ({ token: tokenSinFinca, motivo: motivoLoginSinFinca } =
      await autenticarSinFinca(solicitar, env, secretos));
    if (!tokenSinFinca)
      r.comprobaciones_tecnicas.push(rlsSinFincaNoConcluyente(motivoLoginSinFinca));
    transporte.abrir();
    const apertura = await get('/usuarios/me', tokenProd); afirmar(apertura, 'APERTURA_RUN_FALLIDA');
    reloj.inicioRun();
    let sinAlcance = false;
    if (tokenSinFinca) {
      const perfil = await get('/usuarios/me', tokenSinFinca);
      sinAlcance = perfil.nombre_rol === 'Productor' && Array.isArray(perfil.fincas)
        && !perfil.fincas.some((f) => Number(f.id_finca) === 184);
    }
    semillaAntes = await semilla();
    acreditarSemilla(semillaAntes);
    await umbralSeguro();
    A = 697; B = 698;
    dispositivoA = { id: 785, serial: env.QA_G92_A_SERIAL };
    dispositivoB = { id: 786, serial: env.QA_G92_B_SERIAL };
    afirmar(await canariosAntesDashboard([A, B], (area) => canario(area, 'baseline', true)),
      'E7_CANARIO_BASELINE');
    dashboardAntes = {};
    for (const area of [A, B]) {
      dashboardAntes[area] = await get(
        `/iot/monitoreo/dashboard?id_infraestructura=${area}&pagina=1&por_pagina=50`, tokenProd);
      afirmar(Number(dashboardAntes[area]?.total) === 0 &&
        dashboardAntes[area]?.sensores?.length === 0,
        `SEMILLA_ESTADOS_PREVIOS_${area}`);
    }
    const sensorRls = await crearSensorRls();
    const lecturaSensor = await get('/configuracion/dispositivos-iot/785/sensores');
    r.comprobaciones_tecnicas.push({ id: 'RLS-G92-01', estado: Array.isArray(lecturaSensor.items)
      && lecturaSensor.items.some((s) => Number(s.id_sensores) === sensorRls)
      ? 'APROBADO' : 'NO_CONCLUYENTE', motivo: 'Creacion autorizada y lectura posterior por API publica',
      evidencia: 'resultado.json' });
    if (sinAlcance) {
      const lecturaNegada = await solicitar('GET',
        '/configuracion/dispositivos-iot/785/sensores', { token: tokenSinFinca, negativa: true });
      const creacionNegada = await solicitar('POST',
        '/configuracion/dispositivos-iot/785/sensores',
        { token: tokenSinFinca, cuerpo: cuerpoSensor('sin alcance'), negativa: true });
      if (creacionNegada.status === 201) {
        const idIndebido = numero(creacionNegada.json?.data?.id_sensores ??
          creacionNegada.json?.id_sensores, 'RLS_CREACION_INDEBIDA_SIN_ID');
        r.datos.sensores_creados.push(idIndebido);
        inventariar('sensor', idIndebido, { dispositivo: 785 });
      }
      r.comprobaciones_tecnicas.push({ id: 'RLS-G92-02',
        ...evaluarRlsSinFinca(lecturaNegada, creacionNegada),
        evidencia: 'resultado.json' });
      afirmar(creacionNegada.status !== 201, 'RLS_CREACION_SIN_ALCANCE_ACEPTADA');
    } else if (tokenSinFinca)
      r.comprobaciones_tecnicas.push(rlsSinFincaNoConcluyente(motivoLoginSinFinca));
    r.comprobaciones_tecnicas.push({ id: 'RLS-G92-03', estado: 'NO_CONCLUYENTE',
      motivo: 'No existe UPDATE publico de sensor que permita probar traslado de dispositivo; SQL directa prohibida',
      evidencia: 'resultado.json' });
    const sensoresB = SEMILLA.sensoresB;
    const telB = [];
    for (const sensor of sensoresB) telB.push(await ingestar(dispositivoB, sensor, 'VERDE'));
    await alertar(dispositivoB, 1204, telB[2], 'ROJO');
    let falloA = null;
    try {
      const sensoresA = SEMILLA.sensoresA;
      let telemetria1196 = null;
      for (const sensor of sensoresA) {
        const id = await ingestar(dispositivoA, sensor, 'VERDE');
        if (sensor === 1196) telemetria1196 = id;
      }
      await alertar(dispositivoA, 1196, telemetria1196, 'ROJO');
    } catch (e) { falloA = e; registrarErrorTecnico(e); }
    const fases = [{ fase: 'inicial', area: B }];
    if (!falloA) fases.push({ fase: 'a1', area: A },
      { fase: 'a2', area: A, pagina: 2 }, { fase: 'b1', area: B });
    const { inicial, a1, a2, b1 } = await dashboards(fases);
    const inicialDiagnostico = diagnosticarPagina({ inicial, areaA: A, areaB: B });
    clasificar('TC-M03-181', inicialDiagnostico.checks, inicialDiagnostico.observado,
      Object.fromEntries(['PRE-181-01', 'API-181-01', 'API-181-02', 'API-181-03']
        .map((id) => [id, ['newman/newman-TC-M03-G92.json']])));
    if (falloA) throw new Error(`ESCENARIO_A_INCOMPLETO: ${limpio(falloA.message, secretos)}`);
    const d = diagnosticarPagina({ inicial, a1, a2, b1, alcanceA, alcanceB,
      areaA: A, areaB: B, alertasActivas: 2 });
    const ev = {
      'PRE-182-01': ['newman/newman-TC-M03-G92.json', 'resultado.json'],
      'API-182-01': ['newman/newman-TC-M03-G92.json'],
      'API-182-02': ['newman/newman-TC-M03-G92.json'],
      'PRE-183-01': ['newman/newman-TC-M03-G92.json'],
      'API-183-01': ['newman/newman-TC-M03-G92.json'],
      'API-183-02': ['newman/newman-TC-M03-G92.json'],
    };
    clasificar('TC-M03-182', d.checks, d.observado, ev);
    clasificar('TC-M03-183', d.checks, d.observado, ev);
    r.consume_version = true;
  } catch (e) {
    registrarErrorTecnico(e);
    for (const c of Object.values(r.casos)) if (c.estado_tecnico === 'NO_EJECUTADA') {
      c.estado_tecnico = String(e.message).includes('DUPLICADA') ? 'ERROR_QA' : 'NO_CONCLUYENTE';
      c.estado = c.estado_tecnico;
    }
  } finally {
    if (transporte.estado().abierto) {
      const sinEscrituras = clasificarRollback(transporte.estado().escritura) ===
        'SIN_ESCRITURAS_QUE_REVERTIR';
      r.cierre.rollback.estado = clasificarRollback(transporte.estado().escritura);
      try {
        const c = await solicitar('DELETE', `/test-control/runs/${runIdHeader}`, { cierre: true });
        r.cierre.run.cierre_http = c.status;
        if (c.status === 200) {
          tokenAdmin = await auth('ADMIN'); tokenProd = await auth('PROD');
          const comprobar = (tipo, id, ok, http = 200) =>
            r.cierre.rollback.comprobaciones.push({ tipo, id, http, coincide: Boolean(ok) });
          for (const id of r.datos.ids_alerta) {
            const x = await solicitar('GET', `/iot/alertas/${id}`, { token: tokenAdmin });
            comprobar('alerta_run_ausente', id, x.status === 404, x.status);
          }
          const inicio = SEMILLA.asociadaDesde.slice(0, 10);
          const fin = new Date().toISOString().slice(0, 10);
          for (const area of SEMILLA.areas) {
            const alertas = await solicitar('GET',
              `/iot/alertas?id_infraestructura=${area}&por_pagina=200`, { token: tokenAdmin });
            const av = alertas.json?.data ?? alertas.json;
            comprobar('alertas_area_vacias', area, alertas.status === 200 &&
              Number(av?.total) === 0 && av?.items?.length === 0, alertas.status);
            const historial = await solicitar('GET',
              `/iot/monitoreo/historial?fecha_inicio=${inicio}&fecha_fin=${fin}&id_infraestructura=${area}&por_pagina=500`,
              { token: tokenAdmin });
            const hv = historial.json?.data ?? historial.json;
            comprobar('historial_area_vacio', area, historial.status === 200 &&
              Number(hv?.total_encontrado ?? hv?.total) === 0 &&
              hv?.items?.length === 0, historial.status);
          }
          const lista = await solicitar('GET', '/configuracion/dispositivos-iot/785/sensores',
            { token: tokenAdmin });
          const lv = lista.json?.data ?? lista.json;
          comprobar('sensor_run_ausente', 785, lista.status === 200 &&
            Number(lv?.total) === 60 && lv?.items?.length === 60 &&
            r.datos.sensores_creados.every((id) =>
              !lv.items.some((s) => Number(s.id_sensores) === id)), lista.status);
          if (!sinEscrituras && dashboardAntes && !e7Detenido) {
            for (const area of SEMILLA.areas) {
              if (!await canario(area, 'cierre', true)) {
                comprobar('dashboard_restaurado', area, false, null);
                continue;
              }
              const x = await solicitar('GET',
                `/iot/monitoreo/dashboard?id_infraestructura=${area}&pagina=1&por_pagina=50`,
                { token: tokenProd });
              const antes = estadoDashboard(dashboardAntes[area]);
              const despues = estadoDashboard(x.json?.data ?? x.json);
              comprobar('dashboard_restaurado', area, x.status === 200 && antes !== null &&
                despues !== null && json(antes) === json(despues), x.status);
            }
          } else if (!sinEscrituras) comprobar('dashboard_restaurado', 'sin_baseline', false, null);
          if (semillaAntes) {
            const semillaDespues = await semilla();
            r.cierre.rollback.semilla_intacta = json(semillaAntes) === json(semillaDespues) &&
              validarSemillaPersistente(semillaDespues,
                [env.QA_G92_A_SERIAL, env.QA_G92_B_SERIAL], reloj.inicioRun()).length === 0;
            comprobar('semilla_intacta', 184, r.cierre.rollback.semilla_intacta);
          } else comprobar('semilla_intacta', 184, false, null);
          r.cierre.rollback.verificado = !sinEscrituras &&
            r.cierre.rollback.comprobaciones.length >= 8 &&
            r.cierre.rollback.comprobaciones.every((x) => x.coincide);
          r.cierre.rollback.estado = clasificarRollback(transporte.estado().escritura,
            r.cierre.rollback.verificado);
          r.cierre.motivo = sinEscrituras
            ? 'No hubo intentos de escritura en el RUN; los GET posteriores se registran por separado sin declarar rollback verificado.'
            : r.cierre.rollback.verificado
            ? 'DELETE y GET posteriores acreditan reversion sin borrar semilla persistente.'
            : 'DELETE ejecutado; faltan pruebas publicas para acreditar reversion completa.';
        }
      } catch (e) { registrarErrorTecnico(e); r.cierre.motivo = limpio(e.message, secretos); }
    }
  }
  if (!previo.ok) r.problemas_tecnicos.push(`PREFLIGHT_LOCAL: ${previo.barreras.join(', ')}`);
  const falloCreacionSensor = r.bitacora.some((x) => x.metodo === 'POST'
    && /^\/configuracion\/dispositivos-iot\/\d+\/sensores$/.test(x.ruta)
    && x.http >= 500);
  for (const id of ['RLS-G92-01', 'RLS-G92-02', 'RLS-G92-03'])
    if (!r.comprobaciones_tecnicas.some((x) => x.id === id))
      r.comprobaciones_tecnicas.push({ id,
        estado: id === 'RLS-G92-01' && falloCreacionSensor ? 'FALLA' : 'NO_CONCLUYENTE',
        motivo: id === 'RLS-G92-03' ? 'UPDATE público de sensor no disponible; SQL prohibida'
          : id === 'RLS-G92-01' && falloCreacionSensor
            ? 'POST de sensor devolvió 5xx; cuerpo saneado en bitácora; causa no determinada'
            : 'Preparación interrumpida antes de la comprobación', evidencia: 'resultado.json' });
  if (r.problemas_tecnicos.some((x) => x.startsWith('Timeout técnico QA:') ||
    x.includes('RIESGO_AVISO_'))) {
    for (const caso of Object.values(r.casos)) {
      caso.veredicto = null;
      caso.estado = 'NO_CONCLUYENTE';
      caso.estado_tecnico = 'NO_CONCLUYENTE';
    }
  }
  if (e7Detenido) for (const caso of Object.values(r.casos)) {
    caso.veredicto = null;
    caso.estado = 'ERROR_QA';
    caso.estado_tecnico = 'ERROR_QA';
  }
  r.consume_version = r.datos.ids_telemetria.length > 0 || r.datos.ids_alerta.length > 0;
  r.oficial = registroOficial(r, () => true);
  r.estado = r.oficial ? 'COMPLETO' : 'NO_CONCLUYENTE';
  const consumo = transporte.estado();
  r.presupuesto.solicitudes_directas = consumo.cuenta;
  r.presupuesto.exceso_cierre = consumo.exceso_cierre;
  fs.writeFileSync(path.join(contrato.directorio, r.evidencias[2]), informe(r));
  fs.writeFileSync(path.join(contrato.directorio, 'resultado.json'), json(r));
  r.oficial = registroOficial(r, (x) => fs.existsSync(path.join(contrato.directorio, x)));
  r.estado = r.oficial ? 'COMPLETO' : 'NO_CONCLUYENTE';
  fs.writeFileSync(path.join(contrato.directorio, r.evidencias[2]), informe(r));
  fs.writeFileSync(path.join(contrato.directorio, 'resultado.json'), json(r));
  return r.oficial ? 0 : 2;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    if (process.argv.includes('--capacidades')) console.log(json(CAPACIDADES));
    else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
    else {
      const contrato = contextoEjecucion(process.argv.slice(2), { grupo: 'G92', casos: CASOS, directorio: DIR });
      process.exitCode = await evaluar(contrato);
    }
  } catch (e) { console.error(`G92: ${String(e.message)}`); process.exitCode = 2; }
}
