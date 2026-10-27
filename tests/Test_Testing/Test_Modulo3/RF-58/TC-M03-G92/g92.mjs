#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { CASOS, CAPACIDADES, LIMITE, ORACULO, planTemporal, diagnosticarPagina, semillaEstable } from './lib/g92_escenario.mjs';
import { sanearArtefacto } from './lib/g92_seguridad.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const COLECCION = path.join(DIR, 'G92.postman_collection.json');
const json = (x) => JSON.stringify(x, null, 2);
const afirmar = (v, m) => { if (!v) throw new Error(m); };
const numero = (v, m) => { const n = Number(v); afirmar(Number.isSafeInteger(n) && n > 0, m); return n; };
const limpio = (x, secretos) => sanearArtefacto(String(x), secretos).slice(0, 400);
export function comprobar({ dir = DIR } = {}) {
  const originales = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('RED_PROHIBIDA_EN_COMPROBAR'); };
  try {
    const archivos = ['g92.mjs', 'G92.postman_collection.json', 'README.md',
      'lib/contrato_ejecutor.mjs', 'lib/g92_escenario.mjs', 'lib/g92_seguridad.mjs',
      'pruebas/g92.test.mjs'];
    const ausentes = archivos.filter((x) => !fs.existsSync(path.join(dir, x)));
    const c = JSON.parse(fs.readFileSync(path.join(dir, 'G92.postman_collection.json'), 'utf8'));
    const scripts = [...(c.event ?? []), ...(c.item ?? []).flatMap((x) => x.event ?? [])];
    for (const e of scripts) new vm.Script((e.script?.exec ?? []).join('\n'));
    const texto = json(c);
    const ids = Object.values(CAPACIDADES.comprobaciones_obligatorias).flatMap((x) => x.API);
    const valido = !ausentes.length && CAPACIDADES.contrato === 'sigab-qa-ejecutor/1'
      && ids.length === 6 && new Set(ids).size === 6 && c.item?.length === 1
      && CASOS.every((caso) => CAPACIDADES.comprobaciones_obligatorias[caso]?.API?.length > 0)
      && texto.includes('X-Test-Run-Id') && texto.includes('X-Sandbox-Secret')
      && !texto.includes('test-control/query') && !texto.includes('access_key');
    console.log(json({ comprobacion: 'G92_LOCAL_SIN_RED', valido, ausentes,
      casos: CASOS, limite: LIMITE, comprobaciones_obligatorias: CAPACIDADES.comprobaciones_obligatorias }));
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
    'QA_ADMIN_PASSWORD', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD', 'BROKER_SERVICE_TOKEN'];
  const barreras = vars.filter((x) => !env[x]);
  if (!CAPACIDADES.operaciones.includes(contrato.operacion)) barreras.push('OPERACION_NO_PUBLICADA');
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (!/^https?:\/\//.test(env.SIGAB_API_TEST_BASE ?? '')) barreras.push('BASE_TEST_INVALIDA');
  if (contrato.version > 1 && contrato.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  if (!fs.existsSync(COLECCION)) barreras.push('COLECCION_AUSENTE');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G92', run_id: contrato.runId,
    operacion: contrato.operacion, version: contrato.version,
    variables: vars.map((nombre) => ({ nombre, presente: Boolean(env[nombre]) })),
    plan: { finca_candidata: 184, area_referencia: 349, dispositivo_referencia: 357,
      areas_nuevas: 2, sensores_nuevos: 63, gateway_asignado: false,
      validacion_en_run: 'finca, alcance Productor, tipo de área/dispositivo, umbral y rango de calibración por GET' },
    limites: LIMITE, barreras, ok: barreras.length === 0 };
}
export function crearTransporte({ base, runId, secreto, bitacora, secretos, permitidos = {}, fetcher = fetch, limite = LIMITE.solicitudes_directas }) {
  let abierto = false, cerrado = false, cuenta = 0;
  const escritura = { areas: 0, dispositivos: 0, sensores: 0, asociaciones: 0,
    calibraciones: 0, telemetrias: 0, alertas: 0 };
  const patrones = [
    ['areas', /^\/configuracion\/infraestructuras$/, LIMITE.areas],
    ['dispositivos', /^\/configuracion\/dispositivos-iot$/, LIMITE.dispositivos],
    ['sensores', /^\/configuracion\/dispositivos-iot\/\d+\/sensores$/, LIMITE.sensores],
    ['asociaciones', /^\/configuracion\/sensores\/\d+\/asociar$/, LIMITE.asociaciones],
    ['calibraciones', /^\/configuracion\/sensores\/\d+\/calibrar$/, LIMITE.calibraciones],
    ['telemetrias', /^\/iot\/telemetria$/, LIMITE.telemetrias],
    ['alertas', /^\/iot\/alertas$/, LIMITE.alertas],
  ];
  const ids = { areas: permitidos.areas ?? new Set(), dispositivos: permitidos.dispositivos ?? new Map(),
    sensores: permitidos.sensores ?? new Map(), telemetrias: permitidos.telemetrias ?? new Set() };
  const mismo = (a, b) => Number(a) === Number(b);
  function comprobarDestino(tipo, pathname, cuerpo) {
    afirmar(cuerpo && typeof cuerpo === 'object', 'CUERPO_AUSENTE');
    if (tipo === 'areas') afirmar(mismo(cuerpo.finca_id, 184) && mismo(cuerpo.especie_id, 126), 'ID_FUERA_LISTA_BLANCA');
    if (tipo === 'dispositivos') afirmar(ids.areas.has(Number(cuerpo.id_infraestructura)), 'ID_FUERA_LISTA_BLANCA');
    if (tipo === 'sensores') afirmar(ids.dispositivos.has(Number(pathname.split('/')[3])), 'ID_FUERA_LISTA_BLANCA');
    if (tipo === 'asociaciones' || tipo === 'calibraciones') {
      const sensor = ids.sensores.get(Number(pathname.split('/')[3]));
      afirmar(sensor && mismo(sensor.dispositivo, cuerpo.id_dispositivo_iot) &&
        mismo(sensor.area, cuerpo.id_infraestructura), 'ID_FUERA_LISTA_BLANCA');
    }
    if (tipo === 'telemetrias' || tipo === 'alertas') {
      const sensor = ids.sensores.get(Number(cuerpo.sensor_id));
      afirmar(sensor && mismo(sensor.dispositivo, cuerpo.device_id) &&
        cuerpo.serial === ids.dispositivos.get(sensor.dispositivo)?.serial &&
        (tipo !== 'alertas' || ids.telemetrias.has(Number(cuerpo.id_telemetria))), 'ID_FUERA_LISTA_BLANCA');
    }
  }
  async function solicitar(metodo, ruta, { token, cuerpo, cierre = false, fuera = false } = {}) {
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
        if (tipo === 'dispositivos') afirmar(cuerpo.id_dispositivo_gateway == null, 'GATEWAY_PROHIBIDO');
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
      const eco = res.headers.get('X-Test-Run-Id');
      bitacora.push({ metodo, ruta, en_run: dentro,
        http: res.status, eco_run: dentro ? eco === runId : null,
        ms: Date.now() - start, ...(pathname === '/sesiones/' ? {} :
          { respuesta: JSON.parse(sanearArtefacto(json(body), secretos)) }) });
      if (dentro) afirmar(eco === runId, 'ECO_RUN_AUSENTE');
      if (cierre && res.status === 200) { abierto = false; cerrado = true; }
      return { status: res.status, json: body };
    } catch (e) {
      bitacora.push({ metodo, ruta,
        en_run: dentro, error: limpio(e.message, secretos), ms: Date.now() - start });
      throw e;
    }
  }
  return { solicitar, abrir: () => { abierto = true; }, estado: () => ({ abierto, cuenta,
    exceso_cierre: Math.max(0, cuenta - limite), escritura }) };
}
export function ejecutarNewman({ contrato, indice, variables, secretos }) {
  afirmar(indice <= LIMITE.newman, 'LIMITE_NEWMAN');
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g92-newman-'));
  try {
    const env = path.join(temp, 'env.json'), rep = path.join(temp, 'reporte.json');
    fs.writeFileSync(env, json({ values: Object.entries(variables).map(([key, value]) =>
      ({ key, value: String(value ?? ''), enabled: true })) }), { mode: 0o600 });
    const cmd = spawnSync('newman', ['run', COLECCION, '-e', env, '--reporters', 'json',
      '--reporter-json-export', rep, '--timeout-request', '30000', '--color', 'off'],
    { encoding: 'utf8', shell: process.platform === 'win32', timeout: 45_000 });
    afirmar(fs.existsSync(rep) && !cmd.error, `NEWMAN_SIN_REPORTE_${cmd.error?.code ?? cmd.status}`);
    const bruto = JSON.parse(fs.readFileSync(rep, 'utf8'));
    const ex = bruto.run?.executions?.[0]; afirmar(ex && bruto.run.executions.length === 1, 'NEWMAN_EJECUCIONES_INVALIDAS');
    const archivo = `newman/newman-${variables.fase}.json`;
    fs.mkdirSync(path.join(contrato.directorio, 'newman'), { recursive: true });
    fs.writeFileSync(path.join(contrato.directorio, archivo), sanearArtefacto(json(bruto), secretos));
    let cuerpo = null;
    try { cuerpo = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { /* no JSON */ }
    return { archivo, cuerpo, http: ex.response?.code ?? null, proceso: cmd.status,
      eco: (ex.response?.header ?? []).some((h) => String(h.key).toLowerCase() === 'x-test-run-id'
        && h.value === variables.run_id),
      fallos: (bruto.run?.failures ?? []).map((f) => limpio(f.error?.message ?? '', secretos)),
      aserciones: bruto.run?.stats?.assertions?.total ?? 0 };
  } finally { fs.rmSync(temp, { recursive: true, force: true }); }
}
function informe(r) {
  const excluida181 = r.comprobaciones.find((x) => x.id === 'API-181-03');
  const comprobaciones = r.comprobaciones.map((x) => `| ${x.caso} | ${x.id} | ${x.tipo} | ${x.estado} | ${x.valor_observado ? JSON.stringify(x.valor_observado) : '—'} | ${x.evidencia ?? 'sin evidencia'} |`).join('\n');
  const observacion = excluida181
    ? `- API-181-03: la matriz G92, esperado 1, exige “incluyendo variables en atención/críticas” en el resumen de la unidad. Según decisión del responsable QA (2026-10-25), RF-58 no contempla esa obligación. El contrato vigente, ResumenUnidadSchema en src/telemetry/infrastructure/schema/monitoreo_schema.py:50-64 y openapi-test.json, tampoco contiene el campo. Valor observado en TEST: ${json(excluida181.valor_observado)}; evidencia: ${excluida181.evidencia ?? 'sin evidencia'}. Acción: revisión documental de la matriz por el responsable QA. Estado EXCLUIDA_DEL_ORACULO, sin incidencia de producto ni efecto en el veredicto.`
    : '- API-181-03: sin observación de TEST; pendiente del GET inicial autorizado. La discrepancia matriz–RF-58 requiere revisión documental por el responsable QA.';
  const tabla = CASOS.map((id) => `| ${id} | ${r.casos[id].veredicto ?? 'SIN VEREDICTO'} | ${r.casos[id].estado_tecnico} |`).join('\n');
  const detalle = CASOS.map((id) => `### ${id}\n\nEsperado: ${ORACULO[id]}\n\nObservado: ${json(r.casos[id].observado)}\n\nComprobaciones: ${r.casos[id].comprobaciones.map((x) => `${x.id}=${x.estado}`).join(', ') || 'ninguna'}.`).join('\n\n');
  const incidencias = r.comprobaciones.filter((x) => x.tipo === 'ASSERT' && x.estado === 'RECHAZADO'
    && r.casos[x.caso].estado_tecnico === 'OK')
    .map((x) => `- ${x.caso} ${x.id}: RF-58 CA-14/CU04, evidencia ${x.evidencias.join(', ')}; equipo inicial Desarrollo, severidad ${x.id === 'API-183-02' ? 'ALTA' : 'MEDIA'}, certeza CONFIRMADA. Causa raíz NO DETERMINADA; primera discrepancia en API pública.`).join('\n') || 'Ninguna confirmada.';
  return `# TC-M03-G92 — resultado ${r.run_id}\n\n## Identificación\n\nGrupo G92; casos ${CASOS.join(', ')}; RF-58/CU04; V${r.version}; RUN ${r.run_id}; ambiente TEST; autorización ${r.autorizacion}; commit ${r.commit}; Node ${process.version}; Newman ${r.newman.length} ejecuciones; Cypress no exigido.\n\n## Resumen de veredictos\n\n| Caso | Funcional | Técnico |\n|---|---|---|\n${tabla}\n\n## Esperado y observado por caso\n\n${detalle}\n\n## Comprobaciones API/UI\n\n| Caso | ID | Tipo | Estado | Valor observado | Evidencia |\n|---|---|---|---|---|---|\n${comprobaciones}\n\nUI no exigida por la matriz.\n\n## Observaciones documentales\n\n${observacion}\n\n## Evidencias reales\n\n${r.evidencias.map((x) => `- [${x}](${x})`).join('\n')}\n\n## Incidencias de producto\n\n${incidencias}\n\n## Incidencias técnicas QA\n\n${r.problemas_tecnicos.map((x) => `- ${x}`).join('\n') || 'Ninguna registrada.'}\n\nHistorial técnico conservado: RUN-G92-V1-20261025-072518, intento 1; GET /iot/monitoreo/dashboard?pagina=1&por_pagina=50 agotó 30 s dentro del RUN y después del DELETE. Incidencia técnica QA pendiente: esos GET globales pudieron activar el correo RF-58 E7; envío no confirmado y sin atribución al producto.\n\n## Bitácora\n\n${r.bitacora.map((x) => `- ${x.metodo} ${x.ruta}: HTTP ${x.http ?? 'ERROR'}, en RUN ${x.en_run}, eco ${x.eco_run ?? 'N/A'}`).join('\n') || 'Sin solicitudes.'}\n\n## Análisis de causas\n\nEl código local es orientación; ninguna causa raíz se atribuye sin evidencia de TEST. Los fallos de precondición, entorno o automatización no constituyen veredicto de producto.\n\n## Efectos externos potenciales\n\nEl baseline de 349 usa configuración, asociaciones, calibraciones, alertas e historial sin dashboard. Antes de cada Newman de A/B se revalida el umbral activo; LECTURA_VALIDA y un umbral no prueban el color del caché. Si algún sensor de la página está almacenado GRIS y no desactualizado, el dashboard puede auditar y enviar correo a Administradores activos; el correo no se revierte por DELETE. El historial registra auditoría incluso después de DELETE. No se da por verificada la ausencia de correos ni la reversión de esas auditorías.\n\n## Cierre y rollback\n\nDELETE: HTTP ${r.cierre.run.cierre_http ?? 'NO CONSTA'}; rollback ${r.cierre.rollback.verificado ? 'VERIFICADO' : 'NO CONFIRMADO'}. ${r.cierre.motivo} Comprobaciones: ${r.cierre.rollback.comprobaciones.length}; riesgos residuales: ${r.cierre.rollback.riesgos_residuales.join('; ') || 'ninguno registrado'}.\n\n## Conclusión y acción concreta\n\nEstado ${r.estado}. ${r.cierre.rollback.verificado ? 'Revisar incidencias funcionales y decidir cierre QA.' : 'Responsable QA debe revisar el cierre y la evidencia faltante antes de cerrar.'}\n`;
}

export async function evaluar(contrato, { env = leerEnv(), newman = ejecutarNewman,
  fetcher = fetch, limiteDirectas = LIMITE.solicitudes_directas } = {}) {
  fs.mkdirSync(contrato.directorio, { recursive: true });
  const previo = preflight(contrato, env);
  fs.writeFileSync(path.join(contrato.directorio, 'preflight.json'), json(previo));
  const secretos = [env.QA_SANDBOX_SECRET, env.BROKER_SERVICE_TOKEN,
    env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD, env.QA_PROD_EMAIL,
    env.QA_PROD_PASSWORD].filter(Boolean);
  const r = { grupo: 'G92', rf: 'RF-58', run_id: contrato.runId,
    version: contrato.version, autorizacion: contrato.referencia,
    commit: contrato.contexto?.commit ?? 'NO_VERIFICADO', oficial: false,
    consume_version: false, estado: 'NO_CONCLUYENTE',
    casos: Object.fromEntries(CASOS.map((id) => [id, { estado: 'NO_EJECUTADA',
      veredicto: null, estado_tecnico: 'NO_EJECUTADA', comprobaciones: [], observado: null }])),
     comprobaciones: [], datos: { ids_telemetria: [], ids_alerta: [], inventario: [],
      areas_creadas: [], dispositivos_creados: [], sensores_creados: [] },
    newman: [], bitacora: [], problemas_tecnicos: [],
    presupuesto: { nominal_directas: 497, maximo_directas: limiteDirectas - LIMITE.margen_cierre,
      tope_operativo_directas: limiteDirectas, margen_cierre: LIMITE.margen_cierre,
      solicitudes_directas: 0, exceso_cierre: 0 },
     cierre: { run: { cierre_http: null }, rollback: { verificado: false, semilla_intacta: false,
       comprobaciones: [], riesgos_residuales: ['No hay GET público de sensor independiente del dispositivo ni GET directo de estado actual.'] }, motivo: 'NO_EJECUTADO' },
    evidencias: ['preflight.json', 'resultado.json', contrato.version === 1
      ? 'TC-M03-G92_resultado.md' : `TC-M03-G92_reevaluacion_V${contrato.version}.md`] };
  const base = (env.SIGAB_API_TEST_BASE ?? '').replace(/\/$/, '');
  const runIdHeader = contrato.runId.slice(4);
   const permitidos = { areas: new Set(), dispositivos: new Map(), sensores: new Map(), telemetrias: new Set() };
   const transporte = crearTransporte({ base, runId: runIdHeader, secreto: env.QA_SANDBOX_SECRET,
     bitacora: r.bitacora, secretos, permitidos, fetcher, limite: limiteDirectas });
  const { solicitar } = transporte;
  let tokenAdmin, tokenProd, semillaAntes = null, A, B, dispositivoA, dispositivoB;
  let alcanceA = false, alcanceB = false;
  let serialA, serialB, tipoVariable = 'TEMPERATURA_AMBIENTAL', unidad = '°C';
  const temporal = planTemporal();
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
    const area = await get('/configuracion/infraestructuras/349');
    const dispositivo = await get('/configuracion/dispositivos-iot/357');
    const sensores = await get('/configuracion/dispositivos-iot/357/sensores');
    afirmar(!(Number.isSafeInteger(Number(sensores?.total)) &&
      Number(sensores.total) > LIMITE.sensores_referencia) &&
      !(Array.isArray(sensores?.items) && sensores.items.length > LIMITE.sensores_referencia),
      `SENSORES_357_EXCEDE_MAXIMO_${LIMITE.sensores_referencia}`);
    const umbrales = await get('/configuracion/umbrales?id_especie=126');
    const sensoresReferencia = listaCompleta(sensores, LIMITE.sensores_referencia, 'SENSORES_357');
    afirmar(Array.isArray(umbrales.items), 'SEMILLA_LECTURA_INCOMPLETA');
    afirmar(Number(dispositivo.id_infraestructura) === 349 &&
      sensoresReferencia.every((s) => Number(s.id_dispositivo_iot) === 357),
    'SEMILLA_RELACIONES_349_357_INCOMPATIBLES');
    const asociaciones = [], calibraciones = [], alertas = [];
    const fecha = temporal.inicio.slice(0, 10);
    const hastaAlerta = new Date(Date.parse(temporal.inicio) + 24 * 60 * 60 * 1000).toISOString();
    for (const sensor of sensoresReferencia) {
      const id = numero(sensor.id_sensores, 'SENSOR_REFERENCIA_SIN_ID');
      const as = await get(`/configuracion/sensores/${id}/asociaciones`);
      const cal = await get(`/configuracion/sensores/${id}/calibraciones`);
      const al = await get(`/iot/alertas?id_sensor=${id}&fecha_desde=${encodeURIComponent(temporal.ancla)}&fecha_hasta=${encodeURIComponent(hastaAlerta)}&por_pagina=200`);
      asociaciones.push([id, listaCompleta(as, 200, 'ASOCIACIONES')
        .map((v) => semillaEstable('asociacion', v))
        .sort((a, b) => Number(a.id_sensores_area_asociada) - Number(b.id_sensores_area_asociada))]);
      calibraciones.push([id, listaCompleta(cal, 200, 'CALIBRACIONES')
        .map((v) => semillaEstable('calibracion', v))
        .sort((a, b) => Number(a.id_calibracion) - Number(b.id_calibracion))]);
      alertas.push([id, listaCompleta(al, 200, 'ALERTAS').map((v) =>
        ({ id_alerta: v.id_alerta, id_sensor: v.id_sensor, id_infraestructura: v.id_infraestructura,
          estado_alerta: v.estado_alerta, severidad: v.severidad, fecha_generacion: v.fecha_generacion }))
        .sort((a, b) => Number(a.id_alerta) - Number(b.id_alerta))]);
    }
    const historial = await get(`/iot/monitoreo/historial?fecha_inicio=${fecha}&fecha_fin=${fecha}&id_infraestructura=349&por_pagina=500`);
    const lecturas = listaCompleta(historial, 500, 'HISTORIAL_349').map((v) =>
      ({ id_telemetria: v.id_telemetria, id_sensor: v.id_sensor,
        id_infraestructura: v.id_infraestructura, timestamp_captura: v.timestamp_captura }))
      .sort((a, b) => Number(a.id_telemetria) - Number(b.id_telemetria));
    return { finca: semillaEstable('finca', finca), area: semillaEstable('area', area),
      dispositivo: semillaEstable('dispositivo', dispositivo),
      sensores: sensoresReferencia.map((s) => semillaEstable('sensor', s)).sort((a, b) => a.id_sensores - b.id_sensores),
      asociaciones, calibraciones, alertas, historial: lecturas,
      umbrales: (umbrales.items ?? []).filter((u) => Number(u.id_variable_ambiental) === 1)
        .map((u) => semillaEstable('umbral', u)).sort((a, b) => Number(a.id_umbral_ambiental) - Number(b.id_umbral_ambiental)),
      originales: { finca, area, dispositivo, umbrales } };
  };
  const crearArea = async (sufijo, tipoArea) => {
    const x = await post('/configuracion/infraestructuras', {
      nombre_infraestructura: `QA G92 ${contrato.runId.slice(-15)} ${sufijo}`,
      tipo_area: tipoArea, superficie: 1, finca_id: 184, especie_id: 126 });
    const id = numero(x.id_infraestructura, 'AREA_SIN_ID'); r.datos.areas_creadas.push(id);
    permitidos.areas.add(id); inventariar('area', id, { finca: 184 });
    const visible = await get(`/configuracion/infraestructuras/${id}`, tokenProd);
    afirmar(Number(visible.id_infraestructura) === id && Number(visible.id_finca) === 184,
      'PRODUCTOR_SIN_ACCESO_AREA');
    if (sufijo === 'A') alcanceA = true;
    if (sufijo === 'B') alcanceB = true;
    return id;
  };
  const crearDispositivo = async (area, sufijo, tipo) => {
    const serial = `QA-G92-${contrato.runId.slice(-14)}-${sufijo}`;
    secretos.push(serial);
    const x = await post('/configuracion/dispositivos-iot', {
      serial, descripcion: `QA G92 ${sufijo}`, id_infraestructura: area,
      id_tipo_dispositivo: tipo, es_activo: true });
    afirmar(x.id_dispositivo_gateway == null && x.categoria === 'SENSOR', 'DISPOSITIVO_CON_GATEWAY_O_CATEGORIA');
    const id = numero(x.id_dispositivo_iot, 'DISPOSITIVO_SIN_ID');
    r.datos.dispositivos_creados.push(id); permitidos.dispositivos.set(id, { area, serial });
    inventariar('dispositivo', id, { area }); return { id, serial };
  };
  const crearSensor = async (dispositivo, area, indice) => {
    const x = await post(`/configuracion/dispositivos-iot/${dispositivo.id}/sensores`,
      { nombre: `QA G92 sensor ${indice}`, categoria: 'TEMPERATURA' });
    const id = numero(x.id_sensores, 'SENSOR_SIN_ID'); r.datos.sensores_creados.push(id);
    permitidos.sensores.set(id, { dispositivo: dispositivo.id, area });
    inventariar('sensor', id, { dispositivo: dispositivo.id });
    const as = await post(`/configuracion/sensores/${id}/asociar`, {
      id_dispositivo_iot: dispositivo.id, id_infraestructura: area,
      punto_instalacion: `QA G92 punto ${indice}` });
    afirmar(Number(as.id_sensor) === id && Number(as.id_infraestructura) === area && as.tiene_estado === true,
      'ASOCIACION_INCORRECTA');
    inventariar('asociacion', numero(as.id_sensores_area_asociada, 'ASOCIACION_SIN_ID'), { sensor: id, area });
    const cal = await post(`/configuracion/sensores/${id}/calibrar`, {
      id_dispositivo_iot: dispositivo.id, id_infraestructura: area,
      valor_referencia: 25, ganancia: 1, offset: 0,
      fecha_calibracion: temporal.ancla, modo_calibracion: 'SENSOR' });
    inventariar('calibracion', numero(cal.id_calibracion, 'CALIBRACION_SIN_ID'), { sensor: id });
    return id;
  };
  const ingestar = async (dispositivo, sensor, marca) => {
    const x = await post('/iot/telemetria', {
      device_id: dispositivo.id, sensor_id: sensor, serial: dispositivo.serial,
      tipo_variable: tipoVariable, valor: 25, unidad,
      timestamp_captura: marca, nivel_bateria: 81,
      calidad_senal_rssi: -71, calidad_senal_snr: 7.5 }, env.BROKER_SERVICE_TOKEN);
    afirmar(x.estado_calidad === 'LECTURA_VALIDA', `INGESTA_CALIDAD_${x.estado_calidad}`);
    afirmar(x.estado_semaforo !== 'GRIS' && x.sin_umbral !== true,
      'RIESGO_AVISO_SIN_UMBRAL_INGESTA');
    const id = numero(x.id_telemetria, 'TELEMETRIA_SIN_ID');
    r.datos.ids_telemetria.push(id); permitidos.telemetrias.add(id);
    inventariar('telemetria', id, { sensor }); inventariar('estado_actual', sensor, { telemetria: id }); return id;
  };
  const alertar = async (dispositivo, sensor, idTelemetria, severidad) => {
    const x = await post('/iot/alertas', {
      device_id: dispositivo.id, sensor_id: sensor, serial: dispositivo.serial,
      tipo_variable: tipoVariable, valor: 25, unidad,
      timestamp_evento: temporal.ancla, estado_dato: 'LECTURA_VALIDA',
      severidad_edge: severidad, origen_evento: 'EDGE',
      id_telemetria: idTelemetria, reglas_activadas: [] }, env.BROKER_SERVICE_TOKEN);
    afirmar(x.es_duplicado === false, 'ALERTA_DUPLICADA_ERROR_QA');
    const id = numero(x.id_alerta, 'ALERTA_SIN_ID'); r.datos.ids_alerta.push(id);
    inventariar('alerta', id, { sensor, telemetria: idTelemetria });
    const d = await get(`/iot/alertas/${id}`);
    afirmar(d.estado_alerta === 'ACTIVA' && d.severidad === severidad && Number(d.id_sensor) === sensor,
      'ALERTA_NO_ACREDITADA'); return id;
  };
  let indiceNewman = 0;
  const umbralSeguro = async () => {
    const umbrales = await get('/configuracion/umbrales?id_especie=126');
    afirmar(Array.isArray(umbrales?.items) && umbrales.items.some((x) => x.es_activo &&
      Number(x.id_variable_ambiental) === 1 && x.niveles?.some((n) =>
        n.nivel === 'normal' && Number(n.limite_inferior) <= 25 && Number(n.limite_superior) >= 25)),
    'RIESGO_AVISO_SIN_UMBRAL_ANTES_DASHBOARD');
  };
  const dashboard = async (fase, area, pagina = 1) => {
    await umbralSeguro();
    afirmar(Number.isSafeInteger(area) && area > 0, 'DASHBOARD_AREA_OBLIGATORIA');
    const consulta = `?id_infraestructura=${area}&pagina=${pagina}&por_pagina=50`;
    const inicio = Date.now();
    let n;
    try {
      n = newman({ contrato, indice: ++indiceNewman, secretos,
        variables: { qa_autorizado: 'SI', base_url: base, run_id: runIdHeader,
          sandbox_secret: env.QA_SANDBOX_SECRET, token_productor: tokenProd,
          area_a: A, area_b: B, fase, consulta } });
    } catch (e) {
      const timeout = /timeout|timed out|aborted/i.test(String(e.message));
      throw new Error(`${timeout ? 'Timeout técnico QA: ' : ''}Newman GET /iot/monitoreo/dashboard${consulta}; fase ${fase} dentro del RUN; ${Date.now() - inicio} ms (límite 30000 ms); ${limpio(e.message, secretos)}`);
    }
    r.newman.push({ fase, archivo: n.archivo, http: n.http, fallos: n.fallos, aserciones: n.aserciones });
    r.evidencias.push(n.archivo);
    r.bitacora.push({ metodo: 'GET', ruta: '/iot/monitoreo/dashboard', en_run: true,
      http: n.http, eco_run: n.eco, via: 'Newman', fase });
    if (n.http !== 200 && n.fallos?.some((x) => /timeout|timed out|aborted/i.test(x)))
      throw new Error(`Timeout técnico QA: Newman GET /iot/monitoreo/dashboard${consulta}; fase ${fase} dentro del RUN; ${Date.now() - inicio} ms (límite 30000 ms).`);
    afirmar(n.http === 200 && n.eco && n.cuerpo && n.aserciones > 0,
      `NEWMAN_CONTEXTO_INVALIDO_${fase}`);
    return n.cuerpo;
  };
  const clasificar = (caso, checks, observado, evidencias) => {
    const c = r.casos[caso]; c.observado = observado;
    for (const [id, cumple] of Object.entries(checks).filter(([id]) => id.includes(caso.slice(-3)))) {
      const archivos = evidencias[id] ?? [];
      const excluida = id === 'API-181-03';
      const check = { caso, fuente: 'API', id,
        tipo: excluida ? 'EXCLUIDA' : id.startsWith('PRE-') ? 'PRE' : 'ASSERT',
        estado: excluida ? 'EXCLUIDA_DEL_ORACULO' : cumple ? 'APROBADO' : 'RECHAZADO',
        ...(excluida ? { motivo: 'Exigencia de la matriz no contemplada en RF-58 (decisión QA 2026-10-25)',
          valor_observado: { campo: observado.variable_en_resumen, presente: cumple } } : {}),
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
    transporte.abrir();
    const apertura = await get('/usuarios/me', tokenProd); afirmar(apertura, 'APERTURA_RUN_FALLIDA');
    semillaAntes = await semilla();
    const { area: areaReferencia, dispositivo: dispositivoReferencia,
      finca: fincaProductor, umbrales } = semillaAntes.originales;
    afirmar(Number(areaReferencia.id_finca) === 184 && Number(areaReferencia.especie_id) === 126
      && areaReferencia.es_activo !== false && dispositivoReferencia.categoria === 'SENSOR'
      && Number(dispositivoReferencia.id_infraestructura) === 349
      && Number(fincaProductor.id_finca) === 184 && fincaProductor.es_activo !== false,
      'SEMILLA_REFERENCIA_INCOMPATIBLE');
    const umbral = (umbrales.items ?? []).find((x) => x.es_activo &&
      Number(x.id_variable_ambiental) === 1 && x.niveles?.some((n) =>
        n.nivel === 'normal' && Number(n.limite_inferior) <= 25 && Number(n.limite_superior) >= 25));
    afirmar(umbral, 'UMBRAL_NORMAL_25_NO_ACREDITADO');
    inventariar('finca_preexistente', 184, null);
    A = await crearArea('A', areaReferencia.tipo_area);
    B = await crearArea('B', areaReferencia.tipo_area);
    dispositivoA = await crearDispositivo(A, 'A', dispositivoReferencia.id_tipo_dispositivo);
    dispositivoB = await crearDispositivo(B, 'B', dispositivoReferencia.id_tipo_dispositivo);
    serialA = dispositivoA.serial; serialB = dispositivoB.serial;
    const sensoresB = [];
    for (let i = 1; i <= 3; i++) sensoresB.push(await crearSensor(dispositivoB, B, i));
    const telB = [];
    for (const id of sensoresB) telB.push(await ingestar(dispositivoB, id, temporal.marcas[0]));
    await alertar(dispositivoB, sensoresB[1], telB[1], 'LEVE');
    await alertar(dispositivoB, sensoresB[2], telB[2], 'CRITICO');
     const inicial = await dashboard('inicial', B);
    const inicialDiagnostico = diagnosticarPagina({ inicial, areaA: A, areaB: B });
    clasificar('TC-M03-181', inicialDiagnostico.checks, inicialDiagnostico.observado,
      Object.fromEntries(['PRE-181-01', 'API-181-01', 'API-181-02', 'API-181-03']
        .map((id) => [id, ['newman/newman-inicial.json']])));
    const sensoresA = [];
    for (let i = 1; i <= 60; i++) sensoresA.push(await crearSensor(dispositivoA, A, i + 3));
    afirmar(sensoresA.length === 60 && new Set(sensoresA).size === 60
      && sensoresA.every((x, i) => i === 0 || x > sensoresA[i - 1]), 'ORDEN_SENSORES_NO_GARANTIZADO');
    const telFinal = new Map();
    for (let i = 0; i < 60; i++) telFinal.set(sensoresA[i],
      await ingestar(dispositivoA, sensoresA[i], temporal.marcas[1]));
    await alertar(dispositivoA, sensoresA[54], telFinal.get(sensoresA[54]), 'CRITICO');
    const a1 = await dashboard('a1', A), a2 = await dashboard('a2', A, 2);
    const b1 = await dashboard('b1', B);
    const d = diagnosticarPagina({ inicial, a1, a2, b1, alcanceA, alcanceB,
      areaA: A, areaB: B, alertasActivas: 3 });
    const ev = {
      'PRE-182-01': ['newman/newman-a1.json', 'newman/newman-b1.json', 'resultado.json'],
      'API-182-01': ['newman/newman-a1.json', 'newman/newman-a2.json', 'newman/newman-b1.json'],
      'API-182-02': ['newman/newman-a1.json', 'newman/newman-b1.json'],
      'PRE-183-01': ['newman/newman-a1.json', 'newman/newman-a2.json'],
      'API-183-01': ['newman/newman-a1.json', 'newman/newman-a2.json'],
      'API-183-02': ['newman/newman-a1.json'],
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
      try {
        const c = await solicitar('DELETE', `/test-control/runs/${runIdHeader}`, { cierre: true });
        r.cierre.run.cierre_http = c.status;
        if (c.status === 200) {
          tokenAdmin = await auth('ADMIN'); tokenProd = await auth('PROD');
          const verificar = (tipo, id, x, ok) => r.cierre.rollback.comprobaciones.push({ tipo, id,
            http: x.status, coincide: x.status === 200 && ok(x.json?.data ?? x.json) });
          for (const id of r.datos.ids_alerta) {
            const x = await solicitar('GET', `/iot/alertas/${id}`, { token: tokenAdmin });
            r.cierre.rollback.comprobaciones.push({ tipo: 'alerta_ausente', id_alerta: id,
              http: x.status, coincide: x.status === 404 });
          }
          const sensoresConAlerta = r.datos.inventario.filter((x) => x.tipo === 'alerta').map((x) => x.depende_de.sensor);
          for (const id of sensoresConAlerta) {
            const x = await solicitar('GET', `/iot/alertas?id_sensor=${id}&por_pagina=200`, { token: tokenAdmin });
            verificar('alertas_por_sensor', id, x, (v) => Number(v.total) === 0 && v.items?.length === 0);
          }
          const desde = temporal.marcas[0].slice(0, 10), hasta = new Date().toISOString().slice(0, 10);
          for (const id of r.datos.sensores_creados) {
            const x = await solicitar('GET', `/iot/monitoreo/historial?fecha_inicio=${desde}&fecha_fin=${hasta}&sensor_id=${id}&por_pagina=500`, { token: tokenAdmin });
            verificar('telemetria_por_sensor', id, x, (v) => Number(v.total_encontrado ?? v.total) === 0 && v.items?.length === 0);
          }
          for (const area of r.datos.areas_creadas) {
            const x = await solicitar('GET', `/iot/monitoreo/historial?fecha_inicio=${desde}&fecha_fin=${hasta}&id_infraestructura=${area}&por_pagina=500`, { token: tokenAdmin });
            r.cierre.rollback.comprobaciones.push({ tipo: 'telemetrias_ausentes', area, http: x.status,
              coincide: x.status === 200 && Number((x.json?.data ?? x.json)?.total) === 0 &&
                Number((x.json?.data ?? x.json)?.total_encontrado ?? (x.json?.data ?? x.json)?.total) === 0 &&
                (x.json?.data ?? x.json)?.items?.length === 0 });
          }
          for (const id of r.datos.sensores_creados) {
            const cal = await solicitar('GET', `/configuracion/sensores/${id}/calibraciones`, { token: tokenAdmin });
            verificar('calibracion_por_sensor', id, cal, (v) => Number(v.total) === 0 && v.items?.length === 0);
            const as = await solicitar('GET', `/configuracion/sensores/${id}/asociaciones`, { token: tokenAdmin });
            verificar('asociacion_por_sensor', id, as, (v) => Number(v.total) === 0 && v.items?.length === 0);
          }
          for (const dispositivo of r.datos.dispositivos_creados) {
            const lista = await solicitar('GET', `/configuracion/dispositivos-iot/${dispositivo}/sensores`, { token: tokenAdmin });
            verificar('sensores_del_dispositivo', dispositivo, lista,
              (v) => Number(v.total) === 0 && v.items?.length === 0);
            const entidad = await solicitar('GET', `/configuracion/dispositivos-iot/${dispositivo}`, { token: tokenAdmin });
            r.cierre.rollback.comprobaciones.push({ tipo: 'dispositivo_ausente', id: dispositivo,
              http: entidad.status, coincide: entidad.status === 404 });
          }
          for (const area of r.datos.areas_creadas) {
            const entidad = await solicitar('GET', `/configuracion/infraestructuras/${area}`, { token: tokenAdmin });
            r.cierre.rollback.comprobaciones.push({ tipo: 'entidad_area_ausente', id: area,
              http: entidad.status, coincide: entidad.status === 404 });
            const sinSensores = r.cierre.rollback.comprobaciones.some((v) =>
              v.tipo === 'sensores_del_dispositivo' && v.coincide &&
              Number(permitidos.dispositivos.get(v.id)?.area) === area);
            afirmar(sinSensores && entidad.status === 404, 'RIESGO_AVISO_AREA_ELIMINADA_NO_ACREDITADA');
            const x = await solicitar('GET', `/iot/monitoreo/dashboard?id_infraestructura=${area}&pagina=1&por_pagina=50`, { token: tokenProd });
            const vista = x.json?.data ?? x.json;
            r.cierre.rollback.comprobaciones.push({ tipo: 'area_ausente', id: area, http: x.status,
              coincide: x.status === 200 && Number(vista?.total) === 0 && vista?.sensores?.length === 0 &&
                vista?.resumen_unidades?.length === 0 });
          }
          const semillaDespues = await semilla();
          const { originales: _a, ...antes } = semillaAntes ?? {};
          const { originales: _b, ...despues } = semillaDespues;
          r.cierre.rollback.semilla_intacta = Boolean(semillaAntes) && json(antes) === json(despues);
          r.cierre.rollback.comprobaciones.push({ tipo: 'semilla_intacta', coincide: r.cierre.rollback.semilla_intacta });
          for (const tipo of ['alertas_por_sensor', 'telemetria_por_sensor', 'calibracion_por_sensor',
            'asociacion_por_sensor', 'sensores_del_dispositivo'])
            if (r.cierre.rollback.comprobaciones.some((x) => x.tipo === tipo && x.http !== 200))
              r.cierre.rollback.riesgos_residuales.push(`${tipo}: lectura pública no disponible o denegada en cierre`);
          r.cierre.rollback.verificado = r.cierre.rollback.comprobaciones.length >= 5
            && r.cierre.rollback.comprobaciones.every((x) => x.coincide);
          r.cierre.motivo = r.cierre.rollback.verificado ? 'DELETE y GET posteriores acreditan reversión.'
            : 'DELETE ejecutado; una o más lecturas no acreditan reversión.';
        }
      } catch (e) { registrarErrorTecnico(e); r.cierre.motivo = limpio(e.message, secretos); }
    }
  }
  if (!previo.ok) r.problemas_tecnicos.push(`PREFLIGHT_LOCAL: ${previo.barreras.join(', ')}`);
  if (r.problemas_tecnicos.some((x) => x.startsWith('Timeout técnico QA:') ||
    x.includes('RIESGO_AVISO_'))) {
    for (const caso of Object.values(r.casos)) {
      caso.veredicto = null;
      caso.estado = 'NO_CONCLUYENTE';
      caso.estado_tecnico = 'NO_CONCLUYENTE';
    }
  }
  r.consume_version = r.datos.ids_telemetria.length > 0 || r.datos.ids_alerta.length > 0;
  const obligatorias = Object.values(CAPACIDADES.comprobaciones_obligatorias).flatMap((x) => x.API);
  r.oficial = obligatorias.every((id) => r.comprobaciones.some((x) => x.id === id
    && ['APROBADO', 'RECHAZADO'].includes(x.estado)))
    && CASOS.every((id) => ['APROBADO', 'RECHAZADO'].includes(r.casos[id].estado))
    && r.cierre.run.cierre_http === 200 && r.cierre.rollback.verificado;
  r.estado = r.oficial ? 'COMPLETO' : 'NO_CONCLUYENTE';
  const consumo = transporte.estado();
  r.presupuesto.solicitudes_directas = consumo.cuenta;
  r.presupuesto.exceso_cierre = consumo.exceso_cierre;
  if (r.newman.length) {
    const esc = (v) => String(v).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    const filas = r.newman.map((n) => `<tr><td>${esc(n.fase)}</td><td>${n.http}</td><td>${n.aserciones}</td><td>${n.fallos.length}</td><td><a href="${esc(path.basename(n.archivo))}">JSON saneado</a></td></tr>`).join('');
    fs.writeFileSync(path.join(contrato.directorio, 'newman', 'newman-G92-consolidado.html'),
      `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G92</title><h1>Newman G92</h1><table border="1"><tr><th>Fase</th><th>HTTP</th><th>Aserciones</th><th>Fallos</th><th>Evidencia</th></tr>${filas}</table></html>`);
    r.evidencias.push('newman/newman-G92-consolidado.html');
  }
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
