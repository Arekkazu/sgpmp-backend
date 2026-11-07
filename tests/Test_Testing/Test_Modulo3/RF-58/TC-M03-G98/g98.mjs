#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto } from './lib/seguridad.mjs';
import { pulirInforme } from './lib/g98_informe_pulido.mjs';
import { PRESUPUESTO, CASO, ORACULO, CAPACIDADES, evaluarPanel, precondicion, riesgoE7,
  SEMILLA_G98, GRADOS_SEMILLA, normalizarTipoVariable, elegirTernaSemilla, cuerpoSemilla } from './lib/g98_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G98.postman_collection.json');
const BACKEND = 'código local consultado; despliegue no verificado';
const FRONTEND = 'PR #456 informado por Desarrollo; despliegue no verificado';
const escribir = (p, o) => fs.writeFileSync(p, JSON.stringify(o, null, 2));

export function leerEnv(proceso = process.env, archivo = path.join(RAIZ, '.env.qa')) {
  const v = {};
  if (archivo && fs.existsSync(archivo)) for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);
    if (m) v[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  Object.assign(v, proceso);
  v.QA_AUTORIZADO = proceso.QA_AUTORIZADO;
  return v;
}
export function preflight(c, env, ensayo = false) {
  const claves = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD'];
  const barreras = claves.filter(k => !String(env[k] ?? '').trim());
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API) barreras.push('API_NO_CANONICA');
  if (c.version < CAPACIDADES.versiones.min || c.version > CAPACIDADES.versiones.max
    || !CAPACIDADES.operaciones.includes(c.operacion)) barreras.push('VERSION_U_OPERACION_NO_ADMITIDA');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G98', run_id: c.runId, version: c.version, barreras,
    variables: claves.map(nombre => ({ nombre, presente: !!env[nombre] })),
    efectos_declarados: ['login_productor_y_auditoria_fuera_run', 'lecturas_dashboard_y_posible_correo_E7',
      'hasta_tres_POST_alertas_ACTIVA_en_sandbox_con_rollback_DELETE'],
    presupuesto: PRESUPUESTO, ok: barreras.length === 0 };
}
export function resolverNewman() {
  let pkg;
  try { pkg = require.resolve('newman/package.json', { paths: [RAIZ] }); }
  catch {
    const carpeta = String(process.env.PATH ?? '').split(path.delimiter)
      .find(p => fs.existsSync(path.join(p, 'node_modules', 'newman', 'package.json')));
    if (!carpeta) throw Error('NEWMAN_NO_RESUELTO');
    pkg = path.join(carpeta, 'node_modules', 'newman', 'package.json');
  }
  return path.join(path.dirname(pkg), 'bin', 'newman.js');
}
export function prevalidarNewman(ensayo = false) {
  try {
    if (ensayo) {
      const pkg = require(path.join(path.dirname(resolverNewman()), '..', 'package.json'));
      return { ok: true, version: pkg.version, error: null };
    }
    const p = spawnSync(process.execPath, [resolverNewman(), '--version'],
      { encoding: 'utf8', shell: false, timeout: 30000 });
    return { ok: p.status === 0 && !p.error, version: String(p.stdout ?? '').trim().match(/\d+\.\d+\.\d+/)?.[0] ?? null,
      error: p.error?.code ?? null };
  } catch (e) { return { ok: false, version: null, error: e.code ?? e.message }; }
}
export function comprobar() {
  const archivos = ['README.md', 'g98.mjs', 'G98.postman_collection.json', 'lib/contrato_ejecutor.mjs',
    'lib/seguridad.mjs', 'lib/g98_escenario.mjs', 'lib/g98_informe_pulido.mjs', 'lib/g98_presupuesto.cjs', 'pruebas/g98.test.mjs', 'pruebas/g98_ensayo.mjs',
    'pruebas/registro_qa.mjs', 'pruebas/validar_semilla_g98.py'];
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2', 'EvaluacionV3'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`)));
  const faltantes = archivos.filter(x => !fs.existsSync(path.join(DIR, x)));
  const inesperados = presentes.filter(x => !archivos.includes(x));
  let sintaxis = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const e of col.item.flatMap(i => i.event ?? [])) new vm.Script((e.script?.exec ?? []).join('\n'));
    sintaxis = col.item.length === 1 && col.item[0].request.method === 'GET'
      && JSON.stringify(col).includes('API-191-01');
  } catch { /* se informa abajo */ }
  const oficiales = [
    path.join(DIR, 'EvaluacionV2/Resultados/RUN-G98-V2-20261031-183417/TC-M03-G98_reevaluacion_V2.md'),
    path.join(DIR, 'EvaluacionV3/Resultados/RUN-G98-V3-20261031-185044/TC-M03-G98_reevaluacion_V3.md') ];
  const fuentes = [...archivos.map(x => path.join(DIR, x)), ...oficiales].filter(x => fs.existsSync(x));
  const rutasTecnicas = /EvaluacionV2[\\/]Resultados[\\/]RUN-G98-V2-20261031-(?:165339|172140|182607)(?:[\\/]|\b)/i;
  const dependenciasTecnicas = fuentes.filter(x => rutasTecnicas.test(fs.readFileSync(x, 'utf8')))
    .map(x => path.relative(DIR, x).replaceAll('\\', '/'));
  const ok = !faltantes.length && !inesperados.length && sintaxis && CAPACIDADES.contrato === 'sigab-qa-ejecutor/1'
    && dependenciasTecnicas.length === 0
    && !fs.existsSync(path.join(DIR, 'informe.md')) && (!fs.existsSync(path.join(DIR, 'Resultados'))
      || !fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md')));
  console.log(JSON.stringify({ grupo: 'G98', ok, faltantes, inesperados, sintaxis, dependenciasTecnicas, presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
async function pedir(api, metodo, ruta, { token, secreto, runId, cuerpo, bitacora, timeout = 30000, deadline } = {}) {
  if (runId && bitacora?.filter(x => x.en_run).length >= PRESUPUESTO.solicitudes_en_run)
    throw Error('PRESUPUESTO_SOLICITUDES_AGOTADO');
  if (deadline && Date.now() >= deadline) throw Error('PRESUPUESTO_TIEMPO_AGOTADO');
  const headers = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (secreto) headers['X-Sandbox-Secret'] = secreto;
  if (runId) headers['X-Test-Run-Id'] = runId;
  if (cuerpo) headers['Content-Type'] = 'application/json';
  let http = null, eco = false;
  try {
    const r = await fetch(api + ruta, { method: metodo, headers, body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      redirect: 'manual', signal: AbortSignal.timeout(deadline ? Math.max(1, Math.min(timeout, deadline - Date.now())) : timeout) });
    http = r.status; eco = r.headers.get('X-Test-Run-Id') === runId;
    return { http, eco, cuerpo: await r.json().catch(() => null) };
  } finally { bitacora?.push({ metodo, ruta, http, en_run: !!runId, eco: runId ? eco : null }); }
}
function soloIds(items, clave) { return Array.isArray(items) ? items.map(x => Number(x?.[clave])).filter(x => Number.isInteger(x) && x > 0) : []; }
export async function descubrir(api, token, env, c, r) {
  const unidades = [];
  const h = { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora,
    deadline: Date.parse(r.inicio) + PRESUPUESTO.duracion_segundos * 1000 };
  const rutaSemilla = `/configuracion/infraestructuras?finca_id=${SEMILLA_G98.id_finca}&solo_activas=true`;
  const infraSemilla = await pedir(api, 'GET', rutaSemilla, h);
  if (infraSemilla.http === 200 && infraSemilla.eco
    && soloIds(infraSemilla.cuerpo?.items, 'id_infraestructura').includes(SEMILLA_G98.id_infraestructura)) {
    unidades.push(SEMILLA_G98.id_infraestructura);
  } else r.observaciones.push(`Área ${SEMILLA_G98.id_infraestructura} (${SEMILLA_G98.nombre}): no visible con 200 y eco para finca ${SEMILLA_G98.id_finca}; continúa descubrimiento normal`);
  const fincas = await pedir(api, 'GET', '/configuracion/fincas?solo_activas=true', h);
  if (fincas.http !== 200 || !fincas.eco) throw Error('DESCUBRIMIENTO_FINCAS_SIN_200_ECO');
  for (const id of soloIds(fincas.cuerpo?.items, 'id_finca').slice(0, PRESUPUESTO.fincas_descubrimiento)) {
    const inf = id === SEMILLA_G98.id_finca ? infraSemilla
      : await pedir(api, 'GET', `/configuracion/infraestructuras?finca_id=${id}&solo_activas=true`, h);
    if (inf.http !== 200 || !inf.eco) { r.observaciones.push(`Infraestructuras finca ${id}: sin 200 y eco`); continue; }
    for (const unidad of soloIds(inf.cuerpo?.items, 'id_infraestructura'))
      if (!unidades.includes(unidad) && unidades.length < PRESUPUESTO.unidades_candidatas) unidades.push(unidad);
  }
  r.unidades = unidades;
  let reserva = null;
  for (const unidad of unidades) {
    const lista = await pedir(api, 'GET', `/iot/alertas?estado=ACTIVA&id_infraestructura=${unidad}&pagina=1&por_pagina=${PRESUPUESTO.alertas_por_pagina}`, h);
    const items = lista.cuerpo?.items;
    const total = lista.cuerpo?.total;
    if (lista.http !== 200 || !lista.eco || !Array.isArray(items) || !Number.isInteger(total) || total > PRESUPUESTO.alertas_por_pagina) {
      r.observaciones.push(`Área ${unidad}: listado ACTIVA no verificable`); continue;
    }
    if (!items.every(x => x?.estado_alerta === 'ACTIVA' && x?.id_infraestructura === unidad)) {
      r.observaciones.push(`Área ${unidad}: listado público no acreditó estado ACTIVA y alcance`); continue;
    }
    if (!precondicion(items)) { r.observaciones.push(`Área ${unidad}: faltan tres severidades ACTIVA en sensores distintos`); continue; }
    const canario = await pedir(api, 'GET', `/iot/monitoreo/dashboard/${unidad}?pagina=1&por_pagina=${PRESUPUESTO.canario_por_pagina}`, h);
    if (canario.http !== 200 || !canario.eco || riesgoE7(canario.cuerpo)) {
      r.observaciones.push(`Área ${unidad}: canario E7 no apto o sin 200 y eco`); continue;
    }
    const datos = { unidad, total, ids: new Set(items.map(x => x.id_alerta)),
      con_activo: items.every(x => Number.isInteger(x.id_activo_biologico) && x.id_activo_biologico > 0),
      items: items.map(x => ({ id_alerta: x.id_alerta, id_sensor: x.id_sensor,
        id_activo_biologico: x.id_activo_biologico, severidad: x.severidad })) };
    r.observaciones.push(`Área ${unidad}: precondición mixta y canario E7 aptos; activo vinculado=${datos.con_activo}`);
    if (datos.con_activo) return datos;
    reserva ??= datos;
  }
  return reserva;
}
const idValido = x => Number.isInteger(x) && x > 0;
function fechaBogota(d) { return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota',
  year: 'numeric', month: '2-digit', day: '2-digit' }).format(d); }
export async function descubrirSemilla(api, token, env, c, r, rol) {
  const h = { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora,
    deadline: Date.parse(r.inicio) + PRESUPUESTO.duracion_segundos * 1000 };
  const dispositivos = await pedir(api, 'GET', '/configuracion/dispositivos-iot?solo_activos=true', h);
  if (dispositivos.http !== 200 || !dispositivos.eco || !Array.isArray(dispositivos.cuerpo?.items)) {
    r.observaciones.push(`${rol}: dispositivos activos no verificables`); return null;
  }
  let historiales = 0;
  for (const unidad of r.unidades) {
    const activos = await pedir(api, 'GET', `/activos-biologicos?id_infraestructura=${unidad}&pagina=1&page_size=100`, h);
    const registros = activos.cuerpo?.registros;
    if (activos.http !== 200 || !activos.eco || !Array.isArray(registros)
      || activos.cuerpo.total_registros > 100) { r.observaciones.push(`Área ${unidad}: activos no verificables`); continue; }
    const idsActivos = new Set(registros.filter(x => x.id_infraestructura === unidad && idValido(x.id_activo_biologico))
      .map(x => x.id_activo_biologico));
    if (!idsActivos.size) { r.observaciones.push(`Área ${unidad}: sin activo biológico vinculado`); continue; }
    const candidatos = [];
    const devices = dispositivos.cuerpo.items.filter(x => x.id_infraestructura === unidad && x.es_activo === true
      && idValido(x.id_dispositivo_iot) && typeof x.serial === 'string' && x.serial.length > 0)
      .sort((a, b) => (b.id_dispositivo_iot === SEMILLA_G98.id_dispositivo_iot && unidad === SEMILLA_G98.id_infraestructura)
        - (a.id_dispositivo_iot === SEMILLA_G98.id_dispositivo_iot && unidad === SEMILLA_G98.id_infraestructura))
      .slice(0, PRESUPUESTO.dispositivos_por_area);
    for (const device of devices) {
      const sensores = await pedir(api, 'GET', `/configuracion/dispositivos-iot/${device.id_dispositivo_iot}/sensores`, h);
      if (sensores.http !== 200 || !sensores.eco || !Array.isArray(sensores.cuerpo?.items)) continue;
      const sensoresOrdenados = [...sensores.cuerpo.items].sort((a, b) =>
        (SEMILLA_G98.sensores.includes(b.id_sensores) && unidad === SEMILLA_G98.id_infraestructura)
        - (SEMILLA_G98.sensores.includes(a.id_sensores) && unidad === SEMILLA_G98.id_infraestructura));
      for (const sensor of sensoresOrdenados) {
        if (historiales >= PRESUPUESTO.historiales_maximos) break;
        if (sensor.es_activo !== true || sensor.id_dispositivo_iot !== device.id_dispositivo_iot
          || !idValido(sensor.id_sensores)) continue;
        const fin = new Date(); const inicio = new Date(fin.getTime() - 89 * 86400000);
        const ruta = `/iot/monitoreo/historial?fecha_inicio=${fechaBogota(inicio)}&fecha_fin=${fechaBogota(fin)}`
          + `&sensor_id=${sensor.id_sensores}&pagina=1&por_pagina=100`;
        const historial = await pedir(api, 'GET', ruta, h); historiales++;
        r.historial_http ??= { consultas: 0, errores: 0 };
        r.historial_http.consultas++;
        if (historial.http !== 200) {
          r.historial_http.errores++;
          const recibido = historial.cuerpo?.code ?? historial.cuerpo?.error_code ?? historial.cuerpo?.error?.code;
          const codigo = typeof recibido === 'string' && /^[A-Z][A-Z0-9_]{0,79}$/.test(recibido)
            ? recibido : 'SIN_CODIGO';
          const motivo = `HISTORIAL_HTTP_${historial.http ?? 'SIN_RESPUESTA'}_${codigo}`;
          r.observaciones.push(`Área ${unidad}, sensor ${sensor.id_sensores}: historial HTTP ${historial.http ?? 'sin respuesta'}, código ${codigo}`);
          if (!r.problemas_tecnicos.includes(motivo)) r.problemas_tecnicos.push(motivo);
          continue;
        }
        if (!historial.eco || !Array.isArray(historial.cuerpo?.items)) continue;
        const lecturas = historial.cuerpo.items.filter(x => x.id_sensor === sensor.id_sensores
          && x.id_infraestructura === unidad && idsActivos.has(x.id_activo_biologico)
          && idValido(x.id_telemetria));
        const desconocidas = lecturas.filter(x => !normalizarTipoVariable(x.tipo_variable)).length;
        if (desconocidas) r.observaciones.push(`Área ${unidad}, sensor ${sensor.id_sensores}: ${desconocidas} lectura(s) con nombre de variable de historial no reconocido; descartadas`);
        const lectura = lecturas.find(x => normalizarTipoVariable(x.tipo_variable));
        if (lectura) candidatos.push({ id_sensor: sensor.id_sensores, id_dispositivo_iot: device.id_dispositivo_iot,
          serial: device.serial, id_telemetria: lectura.id_telemetria,
          id_activo_biologico: lectura.id_activo_biologico, tipo_variable: normalizarTipoVariable(lectura.tipo_variable) });
        const terna = elegirTernaSemilla(candidatos);
        if (terna) {
          const canario = await pedir(api, 'GET', `/iot/monitoreo/dashboard/${unidad}?pagina=1&por_pagina=1`, h);
          if (canario.http === 200 && canario.eco && !riesgoE7(canario.cuerpo))
            return { unidad, terna, rol, token };
          r.observaciones.push(`Área ${unidad}: canario E7 no apto para creación`);
          break;
        }
      }
    }
    r.observaciones.push(`Área ${unidad}: sin terna apta de sensores, variables y lecturas vinculadas`);
  }
  return null;
}

export async function crearSemilla(api, semilla, env, c, r) {
  if (!env.BROKER_SERVICE_TOKEN) throw Error('SEMILLA_TOKEN_BROKER_NO_DISPONIBLE');
  const h = { secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora,
    deadline: Date.parse(r.inicio) + PRESUPUESTO.duracion_segundos * 1000 };
  const ids = r.ids_creados;
  for (const [indice, sensor] of semilla.terna.entries()) {
    const severidad = GRADOS_SEMILLA[indice];
    const cuerpo = cuerpoSemilla(sensor, severidad);
    const post = await pedir(api, 'POST', '/iot/alertas', { ...h, token: env.BROKER_SERVICE_TOKEN, cuerpo });
    const id = post.cuerpo?.id_alerta;
    if (post.http === 201 && idValido(id) && post.cuerpo?.es_duplicado === false) ids.push(id);
    if (post.http !== 201 || !post.eco || !idValido(id) || post.cuerpo?.es_duplicado !== false)
      throw Error(`SEMILLA_POST_${severidad}_HTTP_${post.http}_O_DUPLICADO`);
    if (new Set(ids).size !== ids.length || post.cuerpo.severidad !== severidad)
      throw Error(`SEMILLA_POST_${severidad}_ID_O_SEVERIDAD`);
    const detalle = await pedir(api, 'GET', `/iot/alertas/${id}`, { ...h, token: semilla.token });
    if (detalle.http !== 200 || !detalle.eco || detalle.cuerpo?.estado_alerta !== 'ACTIVA'
      || detalle.cuerpo?.severidad !== severidad || detalle.cuerpo?.id_sensor !== sensor.id_sensor
      || detalle.cuerpo?.id_activo_biologico !== sensor.id_activo_biologico
      || detalle.cuerpo?.id_infraestructura !== semilla.unidad)
      throw Error(`SEMILLA_DETALLE_${severidad}_INCOHERENTE`);
  }
  const lista = await pedir(api, 'GET', `/iot/alertas?estado=ACTIVA&id_infraestructura=${semilla.unidad}&pagina=1&por_pagina=${PRESUPUESTO.alertas_por_pagina}`,
    { ...h, token: semilla.token });
  const items = lista.cuerpo?.items; const total = lista.cuerpo?.total;
  if (lista.http !== 200 || !lista.eco || !Array.isArray(items) || !Number.isInteger(total)
    || total < 3 || total > PRESUPUESTO.alertas_por_pagina || items.length !== total
    || !items.every(x => x.estado_alerta === 'ACTIVA' && x.id_infraestructura === semilla.unidad)
    || !ids.every(id => items.some(x => x.id_alerta === id))) throw Error('SEMILLA_LISTADO_ACTIVA_INCOHERENTE');
  return { unidad: semilla.unidad, total, ids: new Set(items.map(x => x.id_alerta)), con_activo: true,
    items: items.map(x => ({ id_alerta: x.id_alerta, id_sensor: x.id_sensor,
      id_activo_biologico: x.id_activo_biologico, severidad: x.severidad })) };
}
function runProceso(comando, argumentos, opciones) {
  return new Promise(resolve => {
    const p = spawn(comando, argumentos, { ...opciones, shell: false, windowsHide: true });
    let salida = '', error = '', agotado = false;
    const reloj = setTimeout(() => { agotado = true; p.kill(); }, 90000);
    p.stdout.on('data', x => { salida += x.toString().slice(0, 10000); });
    p.stderr.on('data', x => { error += x.toString().slice(0, 10000); });
    p.on('error', e => { clearTimeout(reloj); resolve({ status: null, error: e.code ?? e.message, salida, stderr: error }); });
    p.on('close', code => { clearTimeout(reloj); resolve({ status: code, error: agotado ? 'TIMEOUT' : null, salida, stderr: error }); });
  });
}
function leerPagina(ex, runId, esperado, inicioRun, respuestaCliente) {
  const url = ex.request?.url;
  const u = String(url?.raw ?? url ?? '');
  const m = u.match(/\/dashboard\/(\d+)\?pagina=(\d+)/);
  const partes = Array.isArray(url?.path) ? url.path.map(String) : [];
  const id = m ? Number(m[1]) : Number(partes.at(-1));
  const q = Array.isArray(url?.query) ? url.query.find(x => x.key === 'pagina')?.value : null;
  const pagina = m ? Number(m[2]) : Number(q);
  const headers = ex.response?.header ?? ex.response?.headers ?? [];
  const eco = headers.some(h => String(h.key ?? '').toLowerCase() === 'x-test-run-id' && h.value === runId);
  const fechaRespuesta = Date.parse(headers.find(h => String(h.key ?? '').toLowerCase() === 'date')?.value ?? '');
  const respuesta = Number.isFinite(fechaRespuesta) ? fechaRespuesta : respuestaCliente;
  let body = null;
  try { body = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { /* sin JSON */ }
  const panel = ex.response?.code === 200 ? evaluarPanel(body, { esperado, unidad: id,
    inicioRun: Date.parse(inicioRun), ahora: respuesta }) : null;
  return { unidad: Number.isInteger(id) && id > 0 ? id : null,
    pagina: Number.isInteger(pagina) && pagina > 0 ? pagina : null,
    http: ex.response?.code ?? null, eco, total_sensores: body?.total ?? null,
    sensores_en_pagina: Array.isArray(body?.sensores) ? body.sensores.length : null,
    sensores_alerta: Array.isArray(body?.sensores) ? body.sensores.filter(x => x?.id_alerta != null)
      .map(x => ({ id_sensor: x.id_sensor, id_alerta: x.id_alerta, severidad_alerta: x.severidad_alerta })) : [],
    activos_panel: Array.isArray(body?.panel_alertas_activas?.alertas)
      ? body.panel_alertas_activas.alertas.map(x => ({ id_alerta: x.id_alerta,
        id_activo_biologico: x.id_activo_biologico, identificador_activo_presente: typeof x.identificador_activo === 'string' && !!x.identificador_activo.trim() })) : [],
    conteo_semaforo: body?.conteo_semaforo ?? null,
    alertas_detectadas: Number(body?.panel_alertas_activas?.total) > 0,
    estructura: body && typeof body === 'object' ? Object.keys(body) : [],
    conteos_unidad: Array.isArray(body?.resumen_unidades) ? body.resumen_unidades.map(x => ({
      id_infraestructura: x?.id_infraestructura, alertas_activas_count: x?.alertas_activas_count })) : [],
    severidades_sensor: Array.isArray(body?.sensores) ? body.sensores.filter(x => x?.id_alerta != null).map(x => x.severidad_alerta) : [],
    panel };
}
export function fallosNewman(reporte) {
  return (reporte.run?.failures ?? []).map(f => ({
    tipo: String(f?.error?.name ?? '').slice(0, 120),
    test: String(f?.error?.test ?? '').slice(0, 200),
    item: String(f?.source?.name ?? '').slice(0, 120),
    mensaje: String(f?.error?.message ?? '').slice(0, 200),
    at: String(f?.at ?? '').slice(0, 120),
  }));
}
export async function ejecutarNewman(c, { api, token, env, esperado, secretos, inicioRun, ensayo = false }) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g98-newman-'));
  try {
    const salida = path.join(c.directorio, 'newman'); fs.mkdirSync(salida, { recursive: true });
    const variables = { autorizado_run: 'SI', base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
      token, unidad: String(esperado.unidad), expected_total: String(esperado.total),
      expected_ids: JSON.stringify([...esperado.ids]), inicio_run: inicioRun,
      ensayo_loopback: ensayo ? 'SI' : 'NO' };
    const envPath = path.join(temp, 'env.json');
    escribir(envPath, { values: Object.entries(variables).map(([key, value]) => ({ key, value, enabled: true })) });
    const reporte = path.join(temp, 'reporte.json');
    const p = ensayo ? await new Promise(resolve => {
      const newman = require(path.join(path.dirname(resolverNewman()), '..'));
      newman.run({ collection: COLECCION, environment: envPath, reporters: ['json'],
        reporter: { json: { export: reporte } }, timeoutRequest: 30000 }, (error, summary) =>
        resolve({ status: error || summary?.run?.failures?.length ? 1 : 0,
          error: error?.message ?? null, salida: '', stderr: '' }));
    }) : await runProceso(process.execPath, [resolverNewman(), 'run', COLECCION, '-e', envPath,
      '--reporters', 'json', '--reporter-json-export', reporte, '--timeout-request', '30000', '--color', 'off'],
    { cwd: DIR, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    if (!fs.existsSync(reporte)) return { proceso: p, paginas: [], fallos: [], artefactos: [], error: 'SIN_REPORTE' };
    const raw = fs.readFileSync(reporte, 'utf8');
    fs.writeFileSync(path.join(salida, 'newman-G98.json'), sanearArtefacto(raw, secretos));
    const report = JSON.parse(raw);
    const respuestaCliente = Number(report.environment?.values?.find(x => x.key === 'respuesta_cliente_ms')?.value);
    const paginas = (report.run?.executions ?? []).map(x => leerPagina(x, c.runId, esperado, inicioRun,
      Number.isFinite(respuestaCliente) && respuestaCliente > 0 ? respuestaCliente : NaN));
    const fallos = fallosNewman(report);
    const filas = paginas.map(x => `<tr><td>${x.unidad ?? '?'}</td><td>${x.pagina ?? '?'}</td><td>${x.http ?? 'sin respuesta'}</td><td>${x.eco ? 'sí' : 'no'}</td></tr>`).join('');
    fs.writeFileSync(path.join(salida, 'newman-G98.html'),
      `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G98</title><h1>Newman G98</h1><table><tr><th>Unidad</th><th>Página</th><th>HTTP</th><th>Eco</th></tr>${filas}</table></html>`);
    return { proceso: p, paginas, fallos, artefactos: ['newman/newman-G98.json', 'newman/newman-G98.html'] };
  } finally {
    if (!path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
    fs.rmSync(temp, { recursive: true, force: true });
  }
}
export function evaluarNewman(n) {
  const paginas = n.paginas ?? [];
  const falloFuncional = (n.fallos ?? []).some(f => f.tipo === 'AssertionError'
    && f.test.startsWith('[TC-M03-191][ASSERT][API-191-01]') && f.item === 'API-191-01');
  const problemasTecnicos = [];
  if (n.error || n.proceso?.error || !n.artefactos?.length) problemasTecnicos.push(n.error ?? n.proceso?.error ?? 'SIN_REPORTE');
  if ((n.fallos ?? []).some(f => !(f.tipo === 'AssertionError' && f.test.startsWith('[TC-M03-191][ASSERT][API-191-01]') && f.item === 'API-191-01')
    && !(f.tipo === 'AssertionError' && /\[PRE\]|\[INFO\]/.test(f.test)))) problemasTecnicos.push('NEWMAN_ERROR_SCRIPT_O_TRANSPORTE');
  if (n.proceso?.status != null && n.proceso.status !== 0 && !falloFuncional && !(n.fallos ?? []).length)
    problemasTecnicos.push('NEWMAN_SALIDA_NO_EXPLICADA');
  if (paginas.length > PRESUPUESTO.paginas_dashboard) problemasTecnicos.push('PRESUPUESTO_EXCEDIDO');
  const errorPeticion = problemasTecnicos.includes('NEWMAN_ERROR_SCRIPT_O_TRANSPORTE');
  const validas = errorPeticion ? [] : paginas.filter(p => p.http === 200 && p.eco && p.panel);
  const elegida = validas.find(p => p.alertas_detectadas && p.panel.estado === 'RECHAZADO')
    ?? validas.find(p => p.panel.estado === 'RECHAZADO')
    ?? validas.find(p => p.alertas_detectadas) ?? validas[0];
  let datos;
  if (errorPeticion) datos = { estado: 'NO_CONCLUYENTE', motivo: 'Error de script o transporte Newman; respuesta no evaluable' };
  else if (elegida) datos = { estado: elegida.panel.estado, motivo: elegida.panel.motivo };
  else if (paginas.some(p => p.http >= 500)) datos = { estado: 'BLOQUEADO', motivo: 'Dashboard respondió 5xx' };
  else datos = { estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta 200 con eco del dashboard' };
  if (elegida && falloFuncional && datos.estado === 'APROBADO') {
    datos = { estado: 'NO_CONCLUYENTE', motivo: 'Los oráculos de Newman y del ejecutor discrepan; requiere revisión técnica QA' };
    problemasTecnicos.push('ORACULOS_DIVERGENTES');
  }
  if (!errorPeticion && !elegida && paginas.some(p => p.http === 200 && !p.eco)) datos = { estado: 'NO_CONCLUYENTE', motivo: 'Respuesta 200 sin eco del RUN' };
  return { datos, problemasTecnicos, elegida };
}
export function esOficial(estado, r, evidenciasOk) {
  return ['APROBADO', 'RECHAZADO'].includes(estado) && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado && evidenciasOk && r.problemas_tecnicos.length === 0
    && CAPACIDADES.comprobaciones_obligatorias[CASO].API.every(id => r.comprobaciones.some(x => x.id === id
      && x.tipo === 'ASSERT' && ['APROBADO', 'RECHAZADO'].includes(x.estado)));
}
function informeV3(r) {
  const caso = r.casos[CASO];
  const panel = r.paginas[0]?.panel;
  const pre = r.precondicion;
  const confirmado = r.oficial && caso.estado === 'APROBADO';
  const severidadV3 = panel?.panel?.presente ? 'MEDIA' : 'ALTA';
  const impactoV3 = panel?.panel?.presente
    ? 'impacto parcial en el panel presente' : 'panel relevante ausente, sin alternativa en el dashboard';
  const discrepancia = r.oficial && caso.estado === 'RECHAZADO'
    ? `Nueva discrepancia funcional observada en API pública: ${caso.motivo}. Certeza CONFIRMADA en este RUN; equipo inicial Desarrollo por la respuesta del dashboard, sin atribuir causa raíz. Severidad ${severidadV3}: ${impactoV3}; confirmar el alcance antes de asignar un ticket definitivo.`
    : 'No se confirma una nueva incidencia de producto en este RUN.';
  const filas = r.comprobaciones.map(x => `| ${x.id} | ${x.fuente} | ${x.estado} | ${x.motivo} | ${x.evidencia ?? 'sin evidencia'} |`).join('\n');
  const paginas = r.paginas.map(x => `| ${x.unidad ?? 'sin área'} | ${x.http ?? 'sin respuesta'} | ${x.eco ? 'sí' : 'no'} | ${x.panel?.estado ?? 'sin evaluación'} | ${x.panel?.motivo ?? 'sin panel'} |`).join('\n') || '| sin área | sin respuesta | no | sin evaluación | sin página |';
  const observaciones = r.observaciones.join('; ') || 'Sin observaciones adicionales.';
  const evidencias = r.evidencias.join(', ') || 'sin artefactos';
  const ids = (pre?.ids ?? []).join(', ') || 'no acreditados';
  const creados = (r.ids_creados ?? []).join(', ') || 'ninguno';
  const falta = confirmado ? 'Nada para decidir TC-M03-191 por API; la navegación visual no forma parte de esta comprobación Postman/Newman.'
    : r.oficial ? 'Corregir o explicar la discrepancia observada y obtener un nuevo RUN autorizado.'
      : 'Acreditar una ejecución oficial completa, incluido cierre y rollback, antes de decidir el caso.';
  return `# TC-M03-G98 — ${caso.estado}\n\n## 1. Identificación\n\nGrupo G98; caso TC-M03-191; RF-58/CU04, Salida 2 y CA-11; versión V3; operación ${r.operacion.toUpperCase()}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${r.autorizacion}; backend ${BACKEND}; frontend ${FRONTEND}; commit TEST no verificado. Node ${process.version}; Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}; Postman y Cypress no ejecutados. Contrato API.\n\n## 2. Resumen de veredictos y comparación V1 → V2 → V3\n\nV1 RUN-G98-V1-20261026-181259: RECHAZADO por ausencia del panel. V2 RUN-G98-V2-20261031-183417: RECHAZADO oficial por el oráculo de tiempo automatizado; la respuesta real ya tenía total 3, orden CRITICO (1385, NH3) → MODERADO (1386, PH_AGUA) → LEVE (1387, TEMP_CORPORAL), tipo, variable, campos de activo 928 e identificador. API-191-02, API-191-03 y API-191-04 fueron APROBADO. V3 ${r.run_id}: **${caso.estado}**, ${r.oficial ? 'oficial' : 'no oficial'}; ${caso.motivo}.\n\n## 3. Detalle por caso y comprobaciones API/UI\n\n### TC-M03-191\n\n**Objetivo:** verificar el panel de alertas activas por severidad y los identificadores de navegación al activo afectado.\n\n**Precondiciones:** alertas ACTIVA de tres severidades en sensores distintos de una misma unidad. La búsqueda prioriza la semilla persistente ${SEMILLA_G98.nombre}: finca 184, área 702, dispositivo 789, sensores 1210/1211/1212 y activo 928; los GET públicos acreditan su aptitud en cada RUN. Vía ${pre?.via ?? 'no acreditada'}, rol ${pre?.rol ?? 'no seleccionado'}, área ${pre?.unidad ?? 'no seleccionada'}, total ACTIVA ${pre?.total ?? 'no acreditado'}, activo vinculado ${pre?.activo_vinculado == null ? 'no acreditado' : pre.activo_vinculado ? 'sí' : 'no'}.\n\n**Pasos:** iniciar sesión; comprobar área, activo, sensores y lecturas; reutilizar o crear hasta tres alertas en el sandbox; ejecutar el canario E7; consultar una vez el dashboard por Newman; comparar total, orden, campos, tiempo e identificadores; cerrar el RUN y comprobar rollback.\n\n**Entradas:** área ${pre?.unidad ?? 'no seleccionada'}; alertas ACTIVA ${ids}; alertas creadas dentro del sandbox ${creados}; inicio del RUN ${r.inicio ?? 'no registrado'}.\n\n**Esperado:** «${ORACULO}» Para el tiempo, cada valor debe ser entero y caer entre el inicio del RUN menos 120 s y la recepción, con un minuto de tolerancia por extremo; fecha_generacion no puede superar la recepción más 60 s. Escala RF-57 aceptada: CRITICO > MODERADO > LEVE.\n\n**Observado:** ${r.paginas.length} respuesta(s) Newman; ${panel?.motivo ?? 'sin panel evaluable'}. ${observaciones}\n\n**Decisión con porqué:** **${caso.estado}**. ${caso.motivo}. ${r.oficial ? 'La decisión se apoya en las comprobaciones y evidencias del RUN.' : 'Aún no existe evidencia suficiente para un veredicto oficial de V3.'}\n\n**Qué falta:** ${falta}\n\n| Comprobación | Fuente | Estado | Motivo | Evidencia |\n| --- | --- | --- | --- | --- |\n${filas}\n\n| Área | HTTP | Eco | Panel | Motivo |\n| --- | --- | --- | --- | --- |\n${paginas}\n\nLa API comprueba los identificadores de navegación; no se ejecutó navegación visual, que no es obligatoria para este caso API Postman/Newman.\n\n## 4. Incidencias y observaciones\n\nINC-M03-191-G98-02: **ANULADA**. Fue un falso positivo del oráculo automatizado de V2 por el reloj fijo del sandbox, clasificado como problema técnico QA y no como incidencia de producto. INC-M03-191-G98-01: **${confirmado ? 'CORREGIDA' : 'PENDIENTE DE CONFIRMACIÓN EN V3'}**; V2 ya mostró el panel con total, orden, campos y activo correctos, pero la confirmación requiere V3 oficial APROBADO. ${discrepancia}\n\nProblemas técnicos QA de V3: ${r.problemas_tecnicos.join('; ') || 'ninguno'}.\n\n## 5. Análisis de causas y certeza\n\nEl código local consultado en src/telemetry/infrastructure/repositories/indicadores_alertas_repository.py:70 calcula minutos_transcurridos con floor(extract(epoch FROM now() - al.fecha_generacion) / 60)::int. src/telemetry/application/use_cases/alertas/generar_alerta_use_case.py:110 toma datetime.now(timezone.utc) al crear la alerta. En la única transacción del sandbox, now() queda fijado al inicio; las alertas creadas después pueden mostrar -1. Esta inferencia explica el falso RECHAZADO de V2 sin atribuir un defecto del producto. El RUN V2 registró fecha_generacion entre 18:34:26.98Z y 18:34:27.70Z, respuesta 18:34:30Z e inicio 18:34:17.5Z. La causa del oráculo QA es CONFIRMADA por la comparación entre código local y esas evidencias; el despliegue TEST no se infiere solo del código.\n\n## 6. Conclusión y acciones\n\n${caso.estado}: ${caso.motivo}. ${confirmado ? 'Conservar la evidencia oficial de V3 y cerrar la corrección de INC-M03-191-G98-01.' : falta} INC-M03-191-G98-02 permanece anulada como problema técnico QA.\n\n## 7. Evidencias, herramientas, cierre y rollback\n\nPresupuesto: ${PRESUPUESTO.solicitudes_en_run} solicitudes directas, máximo ${PRESUPUESTO.escrituras_alerta} POST de alerta, ${PRESUPUESTO.margen_cierre} DELETE y ${PRESUPUESTO.lecturas_cierre} GET posteriores. Bitácora: ${r.bitacora.map(x => `${x.metodo} ${x.ruta} HTTP ${x.http ?? 'sin respuesta'} eco ${x.eco ?? 'no aplica'}`).join('; ') || 'sin peticiones'}. Evidencias reales: ${evidencias}. Cierre DELETE HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback: ${r.cierre.rollback.verificado ? r.cierre.rollback.motivo : `NO VERIFICADO: ${r.cierre.rollback.motivo}`}. Login y posibles efectos E7 no se declaran revertidos.\n`;
}
function informeBase(r, directorio = null) {
  if (r.version === 3) return pulirInforme(informeV3(r), r, directorio);
  const estado = r.casos[CASO].estado;
  const comp = r.comprobaciones;
  const evidencia = r.evidencias.join(', ') || 'sin artefactos';
  const datos = r.precondicion;
  const panel = r.paginas[0]?.panel;
  const panelPresente = panel?.panel?.presente === true;
  const correccion = !r.oficial ? 'NO DETERMINADA (sin RUN oficial)' : panelPresente ? 'CORREGIDA' : 'NO CORREGIDA';
  const incidenteId = panelPresente ? 'INC-M03-191-G98-02' : 'INC-M03-191-G98-01';
  const severidad = panelPresente ? 'MEDIA' : 'ALTA';
  const impacto = panelPresente ? 'El panel existe, pero el dato, orden o vínculo observado incumple parcialmente el resultado esperado.'
    : 'La funcionalidad relevante del panel integrado sigue ausente, sin alternativa dentro del dashboard.';
  const incidente = estado === 'RECHAZADO' && r.oficial
    ? `### ${incidenteId} — reevaluación V2\n\nPrimera discrepancia: ${r.casos[CASO].motivo}. Equipo inicial: **Desarrollo**, por incumplimiento comprobado en la API pública del dashboard. Severidad **${severidad}**: ${impacto} Certeza **CONFIRMADA** por respuesta TEST del RUN; causa raíz **NO DETERMINADA**. Evidencia: newman/newman-G98.json y resultado.json. Reproducir con el GET filtrado del área ${datos?.unidad ?? 'no identificada'} y comprobar total, lista, severidad, campos y activo. Desarrollo debe revisar la respuesta desplegada; QA repetirá la comprobación tras corrección.`
    : 'Ninguna incidencia de producto confirmada por esta reevaluación.';
  const filas = comp.map(x => `| ${x.id} | ${x.fuente} | ${x.tipo} | ${x.estado} | ${x.motivo} | ${x.evidencia ?? 'sin evidencia'} |`).join('\n');
  const intentoV2 = r.operacion === 'reintentar'
    ? ` Intento ${r.intento}; intento técnico anterior de V2: RUN-G98-V2-20261031-172140 (no oficial).`
    : '';
  const paginas = r.paginas.map(x => `| ${x.unidad ?? '?'} | ${x.http ?? 'sin respuesta'} | ${x.eco ? 'sí' : 'no'} | ${x.panel?.estado ?? 'sin evaluación'} | ${x.panel?.motivo ?? 'sin panel'} |`).join('\n') || '| — | sin respuesta | no | sin evaluación | sin página |';
  const semillaInforme = `La búsqueda prioriza la semilla persistente ${SEMILLA_G98.nombre}: finca ${SEMILLA_G98.id_finca}, área ${SEMILLA_G98.id_infraestructura}, dispositivo ${SEMILLA_G98.id_dispositivo_iot}, sensores ${SEMILLA_G98.sensores.join('/')}, activo biológico ${SEMILLA_G98.id_activo_biologico}. Su aptitud se acredita por GET públicos del RUN. Las alertas se crean y revierten solo dentro del sandbox del RUN.`;
  return `# TC-M03-G98 — ${estado}\n\n## 1. Identificación\n\nGrupo G98; caso TC-M03-191; RF-58/CU04, Salida 2 y CA-11; versión V${r.version}; operación ${r.operacion.toUpperCase()}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${r.autorizacion}; backend ${BACKEND}; frontend ${FRONTEND}; commit TEST no verificado (referencia informada por orden: edc7593e). Node ${process.version}; Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}; Postman y Cypress no ejecutados. Contrato API.${intentoV2}\n\n## 2. Resumen ejecutivo y decisión del grupo\n\n**${estado}**. ${r.casos[CASO].motivo}. Oficial: ${r.oficial ? 'SÍ' : 'NO'}. Newman: ${r.paginas.length ? 'una ejecución' : 'sin ejecución comprobable'}.\n\n## 3. Detalle por caso y comprobaciones API/UI\n\n### TC-M03-191\n\n**Objetivo:** comprobar el panel integrado de alertas activas ordenado por severidad y la navegación al activo biológico.\n\n**Precondiciones:** tres alertas ACTIVA de severidades CRITICO, MODERADO y LEVE sobre sensores distintos de una misma unidad. ${semillaInforme} Vía elegida: ${datos?.via ?? 'ninguna acreditada'}; rol ${datos?.rol ?? 'no seleccionado'}; área ${datos?.unidad ?? 'no seleccionada'}; total ACTIVA según GET público ${datos?.total ?? 'no acreditado'}; activo biológico vinculado ${datos?.activo_vinculado == null ? 'no acreditado' : datos.activo_vinculado ? 'sí' : 'no'}. Canario E7 con por_pagina=1 previo al dashboard completo. IDs creados en sandbox: ${JSON.stringify(r.ids_creados ?? [])}.\n\n**Pasos:** iniciar sesión Productor y, si hace falta, Administrador; listar fincas e infraestructuras visibles; GET /iot/alertas?estado=ACTIVA&id_infraestructura=<área>&pagina=1&por_pagina=200; si falta área apta, comprobar activo, dispositivos, sensores y lecturas reales por GET públicos, crear hasta tres alertas con POST /iot/alertas y verificar cada detalle; canario GET /iot/monitoreo/dashboard/<área>?pagina=1&por_pagina=1; una ejecución Newman con GET /iot/monitoreo/dashboard/<área>?pagina=1&por_pagina=50; cotejar total, lista, IDs, estado, finca autorizada por alcance de rol, severidad, recencia, campos y activo.\n\n**Entradas:** área ${datos?.unidad ?? 'no seleccionada'}; IDs ACTIVA ${JSON.stringify(datos?.ids ?? [])}; credenciales de rol ${datos?.rol ?? 'no seleccionado'} del lanzador, sin guardarlas en el informe.\n\n**Esperado:** resultado esperado de TC-M03-191: «${ORACULO}» La escala implementada y aceptada por decisión QA es RF-57: CRITICO > MODERADO > LEVE.\n\n**Observado:** ${r.paginas.length} página(s) Newman; ${panel?.motivo ?? 'sin panel evaluable'}. El listado público ACTIVA del área y el canario constan en la bitácora saneada.\n\n**Decisión del caso:** **${estado}**. ${r.casos[CASO].motivo}.\n\n| Comprobación | Fuente | Tipo | Estado | Motivo | Evidencia |\n| --- | --- | --- | --- | --- | --- |\n${filas}\n\n| Área | HTTP | Eco | Estado del panel | Motivo |\n| --- | --- | --- | --- | --- |\n${paginas}\n\nLa API acredita únicamente los identificadores para navegación; no se ejecutó una navegación UI. La ausencia de activo vinculado queda NO_CONCLUYENTE en API-191-03.\n\n## 4. Incidencias y observaciones\n\n${incidente}\n\nV1 → V2: V1 rechazó el panel ausente (INC-M03-191-G98-01, Desarrollo, ALTA) y observó severidad_alerta=null. En este RUN, INC-M03-191-G98-01: **${correccion}**. ${r.observaciones.join(' ') || 'Sin observaciones adicionales.'}\n\nProblemas técnicos QA: ${r.problemas_tecnicos.join('; ') || 'ninguno'}.\n\n## 5. Análisis de fallos\n\nLa primera discrepancia se deriva por la respuesta API observada; la causa raíz no se atribuye por lectura de código. Rutas de código consultadas en preparación: src/configuration/infrastructure/routers/dispositivo_iot_router.py, src/configuration/application/use_cases/dispositivos_iot/consultar_dispositivos_iot_use_case.py y src/configuration/infrastructure/repositories/dispositivo_iot_repository.py. El listado local de dispositivos usa .all(), sin paginación ni filtro por infraestructura; el ejecutor prioriza el dispositivo 789 dentro de la respuesta visible, sin otro GET. El despliegue TEST se decide por este RUN.\n\n## 6. Conclusiones y acciones\n\n${estado}: ${r.casos[CASO].motivo}. ${estado === 'APROBADO' ? 'Conservar evidencia y cerrar el caso.' : estado === 'RECHAZADO' && r.oficial ? 'Derivar respuesta saneada a Desarrollo y reevaluar tras corrección.' : 'Resolver el impedimento documentado antes de otra ejecución autorizada.'}\n\n## 7. Herramientas, evidencias, bitácora y rollback\n\nPresupuesto: hasta ${PRESUPUESTO.solicitudes_en_run} solicitudes directas en RUN, ${PRESUPUESTO.escrituras_alerta} POST /iot/alertas dentro de ese límite, ${PRESUPUESTO.margen_cierre} DELETE de cierre, ${PRESUPUESTO.lecturas_cierre} GET posteriores y ${PRESUPUESTO.duracion_segundos} s. Bitácora: ${r.bitacora.map(x => `${x.metodo} ${x.ruta} HTTP ${x.http ?? 'sin respuesta'} eco ${x.eco ?? 'no aplica'}`).join('; ') || 'sin peticiones'}. Evidencias reales: ${evidencia}. Cierre DELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback: ${r.cierre.rollback.verificado ? r.cierre.rollback.motivo : `NO VERIFICADO: ${r.cierre.rollback.motivo}`}. El login puede producir auditoría y el canario o dashboard puede activar E7; esos efectos externos no se declaran revertidos.\n`;
}
export function informe(r, directorio = null) {
  const base = informeBase(r, directorio);
  return r.version === 3 ? base : pulirInforme(base, r, directorio);
}
function finalizar(c, r, secretos) {
  const rechazo = r.comprobaciones.find(x => x.estado === 'RECHAZADO');
  const pendiente = r.comprobaciones.find(x => CAPACIDADES.comprobaciones_obligatorias[CASO].API.includes(x.id)
    && !['APROBADO', 'RECHAZADO'].includes(x.estado));
  const sinRollback = r.ids_creados?.length && !r.cierre.rollback.verificado;
  const estado = sinRollback ? 'NO_CONCLUYENTE' : rechazo ? 'RECHAZADO' : pendiente ? pendiente.estado : 'APROBADO';
  r.casos[CASO] = { estado, motivo: sinRollback ? r.cierre.rollback.motivo
    : rechazo?.motivo ?? pendiente?.motivo ?? 'Comprobaciones acreditadas' };
  const nombre = c.version === 1 ? 'TC-M03-G98_resultado.md' : `TC-M03-G98_reevaluacion_V${c.version}.md`;
  if (fs.readdirSync(c.directorio).some(x => x.endsWith('.md') && x !== nombre))
    r.problemas_tecnicos.push('RUN_CON_MARKDOWN_ADICIONAL');
  r.evidencias = [...new Set([...r.evidencias, 'resultado.json', nombre])];
  const evidenciasOk = r.evidencias.every(x => typeof x === 'string' && !x.includes('..') && !path.isAbsolute(x)
    && (x === nombre || x === 'resultado.json' || fs.existsSync(path.join(c.directorio, x))));
  r.oficial = esOficial(estado, r, evidenciasOk);
  r.fin = new Date().toISOString();
  escribir(path.join(c.directorio, 'resultado.json'), r);
  fs.writeFileSync(path.join(c.directorio, nombre), sanearArtefacto(informe(r, c.directorio), secretos));
}
export async function evaluar(c, { env = leerEnv(), ensayo = false } = {}) {
  if (!fs.existsSync(c.directorio)) throw Error('RUN_NO_CREADO_POR_LANZADOR');
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G98', run_id: c.runId, version: c.version, intento: c.intento, operacion: c.operacion,
    autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST', oficial: false,
    consume_version: false, casos: { [CASO]: { estado: 'NO_CONCLUYENTE', motivo: 'Sin ejecución' } },
    comprobaciones: ['API-191-01', 'API-191-02', 'API-191-03', 'API-191-04'].map(id =>
      ({ caso: CASO, fuente: 'API', id, tipo: 'ASSERT', estado: 'NO_CONCLUYENTE', motivo: 'Sin comprobación', evidencia: null })),
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [], bitacora: [],
    paginas: [], unidades: [], ids_creados: [], observaciones: [], problemas_tecnicos: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'RUN no cerrado' } },
    inicio: new Date().toISOString() };
  const secretos = [env.QA_SANDBOX_SECRET, env.BROKER_SERVICE_TOKEN, env.QA_PROD_PASSWORD, env.QA_PROD_EMAIL,
    env.QA_ADMIN_PASSWORD, env.QA_ADMIN_EMAIL].filter(Boolean);
  let abierto = false;
  let tokenCierre = null;
  try {
    const pre = preflight(c, env, ensayo); escribir(path.join(c.directorio, 'preflight.json'), pre);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    r.preflight_herramientas.newman = prevalidarNewman(ensayo);
    if (!r.preflight_herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    const login = await pedir(api, 'POST', '/sesiones/', { cuerpo: {
      correo_electronico: env.QA_PROD_EMAIL, contrasena: env.QA_PROD_PASSWORD }, bitacora: r.bitacora });
    if (login.http !== 200 || !login.cuerpo?.token) throw Error(`LOGIN_PRODUCTOR_HTTP_${login.http}`);
    secretos.push(login.cuerpo.token);
    tokenCierre = login.cuerpo.token;
    abierto = true; r.consume_version = true;
    let seleccionado = await descubrir(api, login.cuerpo.token, env, c, r);
    const unidadesProductor = [...r.unidades];
    let unidadesAdmin = [];
    let tokenAdmin = null;
    let tokenDashboard = login.cuerpo.token;
    let rol = 'Productor';
    if ((!seleccionado || !seleccionado.con_activo) && env.QA_ADMIN_EMAIL && env.QA_ADMIN_PASSWORD) {
      const admin = await pedir(api, 'POST', '/sesiones/', { cuerpo: {
        correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD }, bitacora: r.bitacora });
      if (admin.http === 200 && admin.cuerpo?.token) {
        secretos.push(admin.cuerpo.token, env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD);
        tokenAdmin = admin.cuerpo.token;
        const alternativa = await descubrir(api, admin.cuerpo.token, env, c, r);
        unidadesAdmin = [...r.unidades];
        if (alternativa?.con_activo || (!seleccionado && alternativa)) {
          seleccionado = alternativa; tokenDashboard = admin.cuerpo.token; rol = 'Administrador';
        }
      } else r.observaciones.push('Login Administrador opcional no disponible');
    }
    if (!seleccionado?.con_activo) {
      let semilla = null;
      r.unidades = unidadesProductor;
      semilla = await descubrirSemilla(api, login.cuerpo.token, env, c, r, 'Productor');
      if (!semilla && tokenAdmin) {
        r.unidades = unidadesAdmin;
        semilla = await descubrirSemilla(api, tokenAdmin, env, c, r, 'Administrador');
      }
      if (semilla) {
        tokenCierre = semilla.token;
        seleccionado = await crearSemilla(api, semilla, env, c, r);
        tokenDashboard = semilla.token; rol = semilla.rol;
        r.observaciones.push(`Semilla: ${r.ids_creados.length} alertas ACTIVA comprobadas por detalle y listado público`);
      } else seleccionado = null;
    }
    if (!seleccionado) {
      const historialFallido = r.historial_http?.consultas > 0
        && r.historial_http.errores === r.historial_http.consultas;
      r.comprobaciones[0].estado = historialFallido ? 'NO_CONCLUYENTE' : 'BLOQUEADO';
      r.comprobaciones[0].motivo = historialFallido
        ? `Todas las ${r.historial_http.consultas} consultas de historial fallaron por HTTP; la semilla no es evaluable`
        : 'Sin área con activo, tres sensores activos de variables distintas y lecturas reales vinculadas; no se puede formar la precondición';
      r.comprobaciones[1].estado = r.comprobaciones[0].estado;
      r.comprobaciones[1].motivo = r.comprobaciones[0].motivo;
      r.observaciones.push('No se hicieron POST /iot/alertas: faltaron recursos públicos verificables para la semilla.');
      return r;
    }
    r.precondicion = { via: r.ids_creados.length ? 'CREACION_SANDBOX' : 'REUTILIZACION_GET_PUBLICOS', rol, unidad: seleccionado.unidad, total: seleccionado.total,
      ids: [...seleccionado.ids], alertas: seleccionado.items, activo_vinculado: seleccionado.con_activo };
    r.comprobaciones[1] = { ...r.comprobaciones[1], estado: 'APROBADO', motivo: 'Tres severidades RF-57 ACTIVA y sensores distintos; área segura', evidencia: 'resultado.json' };
    if (Date.now() > Date.parse(r.inicio) + PRESUPUESTO.duracion_segundos * 1000 - 90000)
      throw Error('PRESUPUESTO_TIEMPO_SIN_MARGEN_NEWMAN');
    const n = await ejecutarNewman(c, { api, token: tokenDashboard, env, esperado: seleccionado,
      secretos, inicioRun: r.inicio, ensayo });
    r.evidencias.push(...n.artefactos);
    r.paginas = n.paginas;
    r.observaciones.push(...n.paginas.flatMap(p => p.panel?.observaciones ?? []));
    for (const p of n.paginas) r.bitacora.push({ metodo: 'GET',
      ruta: `/iot/monitoreo/dashboard/${p.unidad}?pagina=${p.pagina}&por_pagina=${PRESUPUESTO.por_pagina}`,
      http: p.http, en_run: true, eco: p.eco });
    const { datos, problemasTecnicos, elegida } = evaluarNewman(n);
    r.comprobaciones[0] = { ...r.comprobaciones[0], ...datos, evidencia: n.artefactos[0] ?? null };
    const activos = elegida?.activos_panel ?? [];
    const activosEsperados = new Map(seleccionado.items.map(x => [x.id_alerta, x.id_activo_biologico]));
    const navegacion = seleccionado.con_activo && activos.length > 0 && activos.every(x => Number.isInteger(x.id_activo_biologico)
      && x.id_activo_biologico > 0 && x.id_activo_biologico === activosEsperados.get(x.id_alerta)
      && x.identificador_activo_presente);
    r.comprobaciones[2] = { ...r.comprobaciones[2], estado: !elegida || !seleccionado.con_activo ? 'NO_CONCLUYENTE' : navegacion ? 'APROBADO' : 'RECHAZADO',
      motivo: !elegida ? 'Sin respuesta Newman 200 con eco y sin error técnico; navegación no concluyente'
        : !seleccionado.con_activo ? 'Ninguna unidad hallada tiene todas las alertas vinculadas a activo biológico; navegación no concluyente'
        : navegacion ? 'Cada alerta del panel tiene id_activo_biologico e identificador_activo' : 'Panel sin identificadores de activo biológico en todas las alertas',
      evidencia: n.artefactos[0] ?? null };
    const sensoresConAlerta = elegida?.sensores_alerta ?? [];
    const sensoresSinSeveridad = sensoresConAlerta.filter(x => x.severidad_alerta == null);
    r.comprobaciones[3] = { ...r.comprobaciones[3], estado: !sensoresConAlerta.length ? 'NO_CONCLUYENTE' : sensoresSinSeveridad.length ? 'RECHAZADO' : 'APROBADO',
      motivo: !sensoresConAlerta.length ? 'Ningún sensor con id_alerta en la página; observación no concluyente' : sensoresSinSeveridad.length ? 'Sensor con id_alerta y severidad_alerta null' : 'Sensores con id_alerta tienen severidad_alerta',
      evidencia: n.artefactos[0] ?? null };
    r.problemas_tecnicos.push(...problemasTecnicos);
  } catch (e) {
    const motivo = String(e.message).slice(0, 180);
    r.problemas_tecnicos.push(motivo);
    if (r.comprobaciones[0].motivo === 'Sin comprobación') r.comprobaciones[0].motivo = `Ejecución no completada: ${motivo}`;
  } finally {
    if (abierto) try {
      const cierre = await pedir(api, 'DELETE', `/test-control/runs/${c.runId}`,
        { secreto: env.QA_SANDBOX_SECRET, bitacora: r.bitacora });
      r.cierre.run.cierre_http = cierre.http;
       const dentro = r.bitacora.filter(x => x.en_run);
       const soloLectura = dentro.length > 0 && dentro.every(x => x.metodo === 'GET' && x.eco === true);
       if (r.ids_creados.length) {
         const comprobados = [];
         for (const id of r.ids_creados) {
           try {
             const detalle = await pedir(api, 'GET', `/iot/alertas/${id}`, { token: tokenCierre, bitacora: r.bitacora });
             comprobados.push({ id_alerta: id, http: detalle.http, estado: detalle.cuerpo?.estado_alerta ?? null,
               revertida: detalle.http === 404 || (detalle.http === 200 && detalle.cuerpo?.estado_alerta !== 'ACTIVA') });
           } catch { comprobados.push({ id_alerta: id, http: null, revertida: false }); }
         }
         r.cierre.rollback.alertas = comprobados;
         r.cierre.rollback.verificado = cierre.http === 200 && comprobados.length === r.ids_creados.length
           && comprobados.every(x => x.revertida);
         r.cierre.rollback.motivo = r.cierre.rollback.verificado
           ? `${comprobados.length} IDs ausentes o no ACTIVOS tras DELETE 200`
           : `Rollback no verificado: DELETE HTTP ${cierre.http}; ${comprobados.filter(x => !x.revertida).length} IDs sin reversión comprobada`;
       } else {
         r.cierre.rollback.verificado = cierre.http === 200 && soloLectura;
         r.cierre.rollback.motivo = r.cierre.rollback.verificado
           ? `SIN_ESCRITURAS_QUE_REVERTIR: ${dentro.length} GET con eco; DELETE 200`
           : `Sin verificación conjunta: GET con eco=${soloLectura}; DELETE HTTP ${cierre.http}`;
       }
    } catch (e) { r.cierre.rollback.motivo = `Cierre sin respuesta: ${String(e.message).slice(0, 100)}`;
      r.problemas_tecnicos.push('CIERRE_NO_ACREDITADO'); }
    finalizar(c, r, secretos);
  }
  return r;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else {
    try {
      const ensayo = process.argv.includes('--ensayo-loopback');
      const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G98', casos: [CASO], directorio: DIR, modoEnsayo: ensayo });
      const env = ensayo ? { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: process.env.G98_ENSAYO_BASE,
        QA_SANDBOX_SECRET: 'ENSAYO_SECRET', QA_PROD_EMAIL: 'productor@example.test', QA_PROD_PASSWORD: 'ENSAYO_PASS',
        BROKER_SERVICE_TOKEN: 'TOKEN_BROKER_SINTETICO' }
        : leerEnv();
      const r = await evaluar(c, { env, ensayo });
      console.log(JSON.stringify({ run_id: r.run_id, estado: r.casos[CASO].estado, oficial: r.oficial }));
      if (r.problemas_tecnicos.length) process.exitCode = 2;
    } catch (e) { console.error(`G98: ${e.message}`); process.exitCode = 2; }
  }
}
