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
import { PRESUPUESTO, CASO, ORACULO, CAPACIDADES, evaluarPanel, hayAlertas } from './lib/g98_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G98.postman_collection.json');
const BACKEND = 'origin/test 5b46ca00a0ba92774f8e3d4b9eeaeec169344f17';
const FRONTEND = 'origin/test 81058af57d5d80d523fb5225f8eab48e0307ba85';
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
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G98', run_id: c.runId, version: c.version, barreras,
    variables: claves.map(nombre => ({ nombre, presente: !!env[nombre] })),
    efectos_declarados: ['login_productor_y_auditoria_fuera_run', 'lecturas_dashboard_y_posible_correo_E7'],
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
export function prevalidarNewman() {
  try {
    const p = spawnSync(process.execPath, [resolverNewman(), '--version'],
      { encoding: 'utf8', shell: false, timeout: 30000 });
    return { ok: p.status === 0 && !p.error, version: String(p.stdout ?? '').trim().match(/\d+\.\d+\.\d+/)?.[0] ?? null,
      error: p.error?.code ?? null };
  } catch (e) { return { ok: false, version: null, error: e.code ?? e.message }; }
}
export function comprobar() {
  const archivos = ['README.md', 'g98.mjs', 'G98.postman_collection.json', 'lib/contrato_ejecutor.mjs',
    'lib/seguridad.mjs', 'lib/g98_escenario.mjs', 'lib/g98_presupuesto.cjs', 'pruebas/g98.test.mjs', 'pruebas/g98_ensayo.mjs',
    'pruebas/registro_qa.mjs'];
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados'].includes(x))
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
  const ok = !faltantes.length && !inesperados.length && sintaxis && CAPACIDADES.contrato === 'sigab-qa-ejecutor/1'
    && !fs.existsSync(path.join(DIR, 'informe.md')) && (!fs.existsSync(path.join(DIR, 'Resultados'))
      || !fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md')));
  console.log(JSON.stringify({ grupo: 'G98', ok, faltantes, inesperados, sintaxis, presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
async function pedir(api, metodo, ruta, { token, secreto, runId, cuerpo, bitacora, timeout = 30000 } = {}) {
  const headers = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (secreto) headers['X-Sandbox-Secret'] = secreto;
  if (runId) headers['X-Test-Run-Id'] = runId;
  if (cuerpo) headers['Content-Type'] = 'application/json';
  let http = null, eco = false;
  try {
    const r = await fetch(api + ruta, { method: metodo, headers, body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      redirect: 'manual', signal: AbortSignal.timeout(timeout) });
    http = r.status; eco = r.headers.get('X-Test-Run-Id') === runId;
    return { http, eco, cuerpo: await r.json().catch(() => null) };
  } finally { bitacora?.push({ metodo, ruta, http, en_run: !!runId, eco: runId ? eco : null }); }
}
function soloIds(items, clave) { return Array.isArray(items) ? items.map(x => Number(x?.[clave])).filter(x => Number.isInteger(x) && x > 0) : []; }
export async function descubrir(api, token, env, c, r) {
  const unidades = [...PRESUPUESTO.unidades_conocidas];
  const h = { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora };
  const fincas = await pedir(api, 'GET', '/configuracion/fincas?solo_activas=true', h);
  if (fincas.http === 200 && fincas.eco) {
    for (const id of soloIds(fincas.cuerpo?.items, 'id_finca').slice(0, PRESUPUESTO.fincas_descubrimiento)) {
      const inf = await pedir(api, 'GET', `/configuracion/infraestructuras?finca_id=${id}&solo_activas=true`, h);
      if (inf.http === 200 && inf.eco) for (const unidad of soloIds(inf.cuerpo?.items, 'id_infraestructura')) {
        if (!unidades.includes(unidad) && unidades.length < PRESUPUESTO.unidades_conocidas.length + PRESUPUESTO.unidades_adicionales) unidades.push(unidad);
      } else r.observaciones.push(`Descubrimiento finca ${id}: HTTP ${inf.http ?? 'sin respuesta'}; eco ${inf.eco}`);
    }
  } else r.observaciones.push(`Descubrimiento fincas: HTTP ${fincas.http ?? 'sin respuesta'}; eco ${fincas.eco}`);
  return unidades;
}
function runProceso(comando, argumentos, opciones) {
  return new Promise(resolve => {
    const p = spawn(comando, argumentos, { ...opciones, shell: false, windowsHide: true });
    let salida = '', error = '', agotado = false;
    const reloj = setTimeout(() => { agotado = true; p.kill(); }, PRESUPUESTO.paginas_dashboard * 30000 + 30000);
    p.stdout.on('data', x => { salida += x.toString().slice(0, 10000); });
    p.stderr.on('data', x => { error += x.toString().slice(0, 10000); });
    p.on('error', e => { clearTimeout(reloj); resolve({ status: null, error: e.code ?? e.message, salida, stderr: error }); });
    p.on('close', code => { clearTimeout(reloj); resolve({ status: code, error: agotado ? 'TIMEOUT' : null, salida, stderr: error }); });
  });
}
function leerPagina(ex, runId) {
  const url = ex.request?.url;
  const u = String(url?.raw ?? url ?? '');
  const m = u.match(/\/dashboard\/(\d+)\?pagina=(\d+)/);
  const partes = Array.isArray(url?.path) ? url.path.map(String) : [];
  const id = m ? Number(m[1]) : Number(partes.at(-1));
  const q = Array.isArray(url?.query) ? url.query.find(x => x.key === 'pagina')?.value : null;
  const pagina = m ? Number(m[2]) : Number(q);
  const headers = ex.response?.header ?? ex.response?.headers ?? [];
  const eco = headers.some(h => String(h.key ?? '').toLowerCase() === 'x-test-run-id' && h.value === runId);
  let body = null;
  try { body = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { /* sin JSON */ }
  const panel = ex.response?.code === 200 ? evaluarPanel(body) : null;
  return { unidad: Number.isInteger(id) && id > 0 ? id : null,
    pagina: Number.isInteger(pagina) && pagina > 0 ? pagina : null,
    http: ex.response?.code ?? null, eco, total_sensores: body?.total ?? null,
    sensores_en_pagina: Array.isArray(body?.sensores) ? body.sensores.length : null,
    sensores_alerta: Array.isArray(body?.sensores) ? body.sensores.filter(x => x?.id_alerta != null)
      .map(x => ({ id_sensor: x.id_sensor, id_alerta: x.id_alerta, severidad_alerta: x.severidad_alerta })) : [],
    conteo_semaforo: body?.conteo_semaforo ?? null,
    alertas_detectadas: hayAlertas(body), estructura: body && typeof body === 'object' ? Object.keys(body) : [],
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
export async function ejecutarNewman(c, { api, token, env, unidades, secretos, ensayo = false }) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g98-newman-'));
  try {
    const salida = path.join(c.directorio, 'newman'); fs.mkdirSync(salida, { recursive: true });
    const variables = { autorizado_run: 'SI', base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
      token, unidades: JSON.stringify(unidades), unidad: String(unidades[0]), indice: '0', pagina: '1',
      por_pagina: String(PRESUPUESTO.por_pagina), paginas_usadas: '0', limite_paginas: String(PRESUPUESTO.paginas_dashboard),
      ensayo_loopback: ensayo ? 'SI' : 'NO' };
    const envPath = path.join(temp, 'env.json');
    escribir(envPath, { values: Object.entries(variables).map(([key, value]) => ({ key, value, enabled: true })) });
    const reporte = path.join(temp, 'reporte.json');
    const p = await runProceso(process.execPath, [resolverNewman(), 'run', COLECCION, '-e', envPath,
      '--reporters', 'json', '--reporter-json-export', reporte, '--timeout-request', '30000', '--color', 'off'],
    { cwd: DIR, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    if (!fs.existsSync(reporte)) return { proceso: p, paginas: [], fallos: [], artefactos: [], error: 'SIN_REPORTE' };
    const raw = fs.readFileSync(reporte, 'utf8');
    fs.writeFileSync(path.join(salida, 'newman-G98.json'), sanearArtefacto(raw, secretos));
    const report = JSON.parse(raw);
    const paginas = (report.run?.executions ?? []).map(x => leerPagina(x, c.runId));
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
  const validas = paginas.filter(p => p.http === 200 && p.eco && p.panel);
  const elegida = validas.find(p => p.alertas_detectadas && p.panel.estado === 'RECHAZADO')
    ?? validas.find(p => p.panel.estado === 'RECHAZADO')
    ?? validas.find(p => p.alertas_detectadas) ?? validas[0];
  const falloFuncional = (n.fallos ?? []).some(f => f.tipo === 'AssertionError'
    && f.test.startsWith('[TC-M03-191][ASSERT][API-191-01]') && f.item === 'API-191-01');
  const problemasTecnicos = [];
  if (n.error || n.proceso?.error || !n.artefactos?.length) problemasTecnicos.push(n.error ?? n.proceso?.error ?? 'SIN_REPORTE');
  if ((n.fallos ?? []).some(f => !(f.tipo === 'AssertionError' && f.test.startsWith('[TC-M03-191][ASSERT][API-191-01]') && f.item === 'API-191-01')
    && !(f.tipo === 'AssertionError' && /\[PRE\]|\[INFO\]/.test(f.test)))) problemasTecnicos.push('NEWMAN_ERROR_SCRIPT_O_TRANSPORTE');
  if (n.proceso?.status != null && n.proceso.status !== 0 && !falloFuncional && !(n.fallos ?? []).length)
    problemasTecnicos.push('NEWMAN_SALIDA_NO_EXPLICADA');
  if (paginas.length > PRESUPUESTO.paginas_dashboard) problemasTecnicos.push('PRESUPUESTO_EXCEDIDO');
  let datos;
  if (elegida) datos = { estado: elegida.panel.estado, motivo: elegida.panel.motivo };
  else if (paginas.some(p => p.http >= 500)) datos = { estado: 'BLOQUEADO', motivo: 'Dashboard respondió 5xx' };
  else datos = { estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta 200 con eco del dashboard' };
  if (elegida && falloFuncional && datos.estado === 'APROBADO') datos = { estado: 'RECHAZADO', motivo: 'Aserción funcional Newman incumplida en respuesta 200 con eco' };
  if (!elegida && paginas.some(p => p.http === 200 && !p.eco)) datos = { estado: 'NO_CONCLUYENTE', motivo: 'Respuesta 200 sin eco del RUN' };
  return { datos, problemasTecnicos, elegida };
}
export function esOficial(estado, r, evidenciasOk) {
  return ['APROBADO', 'RECHAZADO'].includes(estado) && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado && evidenciasOk && r.problemas_tecnicos.length === 0;
}
function incidenciaProducto(r, comp) {
  if (r.casos[CASO].estado !== 'RECHAZADO' || !r.oficial)
    return 'Ninguna incidencia de producto confirmada. La ausencia vista en código de referencia es DEFECTO_FUNCIONAL_CANDIDATO hasta observar TEST.';
  const p = r.paginas.find(x => x.http === 200 && x.eco && x.panel?.estado === 'RECHAZADO' && x.alertas_detectadas)
    ?? r.paginas.find(x => x.http === 200 && x.eco && x.panel?.estado === 'RECHAZADO');
  const sinPanel = p?.panel?.panel?.presente === false || /sin panel/i.test(comp.motivo);
  const severidad = sinPanel ? 'ALTA' : 'MEDIA';
  const titulo = sinPanel
    ? 'El dashboard de monitoreo no incluye el panel de alertas activas exigido por RF-58 (total y lista ordenada por severidad)'
    : 'El panel de alertas activas del dashboard no cumple la estructura o el orden exigidos por RF-58';
  const unidad = p?.unidad ?? 'no identificada';
  const conteos = (p?.conteos_unidad ?? []).map(x => `unidad ${x.id_infraestructura}: alertas_activas_count=${x.alertas_activas_count}`).join('; ') || 'sin conteo registrado';
  const refs = p?.sensores_alerta?.length
    ? p.sensores_alerta.map(x => `sensor ${x.id_sensor}: id_alerta=${x.id_alerta}, severidad_alerta=${x.severidad_alerta ?? 'null'}`).join('; ')
    : 'referencias de alerta no registradas en el resumen del RUN';
  const precondicion = (p?.conteos_unidad ?? []).some(x => x.alertas_activas_count > 0)
    ? `Hay al menos una alerta activa según el resumen (${conteos}).`
    : `El resumen del RUN no acredita una alerta activa (${conteos}); se comprueba el contrato del panel en una respuesta 200.`;
  const campos = JSON.stringify(p?.estructura ?? []);
  const detalles = `HTTP ${p?.http ?? 'sin respuesta'} con eco ${p?.eco ? 'del RUN' : 'no acreditado'}; total=${p?.total_sensores ?? 'no registrado'} sensores, ${p?.sensores_en_pagina ?? 'cantidad no registrada'} sensores en la página, campos raíz ${campos}; ${conteos}; conteo_semaforo=${JSON.stringify(p?.conteo_semaforo ?? 'no registrado')}; ${refs}. ${comp.motivo}.`;
  const impacto = sinPanel
    ? 'CA-11 es un criterio de aceptación de RF-58. El usuario no ve en el dashboard qué alertas están activas, su severidad ni el activo afectado y debe acudir a la página separada de Alertas; la funcionalidad relevante está bloqueada en el dashboard.'
    : 'La respuesta incumple un dato o el orden del panel exigido por CA-11; el impacto concreto depende de la discrepancia registrada arriba.';
  const observacion = p?.sensores_alerta?.some(x => x.severidad_alerta == null) ? ' Además, una referencia id_alerta llega con severidad_alerta=null; se registra aparte como observación, no como segunda incidencia.' : '';
  return `### INC-M03-191-G98-01 — ${titulo}\n\n- **ID:** INC-M03-191-G98-01; TC-M03-191; discrepancia CONFIRMADA por API en TEST, RUN ${r.run_id} (${r.autorizacion}). Causa raíz NO DETERMINADA; el ID no es un ticket definitivo.\n- **Equipo:** Desarrollo. Primer contacto por la discrepancia en la API pública del dashboard y por la ausencia del panel en el código de Monitoreo; esta derivación no atribuye causa raíz.\n- **Severidad:** **${severidad}**. ${impacto}\n- **Requisito incumplido:** RF-58, \`tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo3.md:5400-5406\`, Salida 2: «Panel de Alertas Activas Integrado», «Número total de alertas activas», «Lista de alertas ordenada por severidad (CRITICO primero)», «Tipo de alerta, variable afectada y tiempo transcurrido», «Enlace directo al detalle del activo biológico afectado». CA-11, mismo archivo \`:5531-5532\`: «Dado que existen alertas ACTIVAS en RF-57, cuando el usuario visualice el dashboard, entonces las alertas deben estar visibles e integradas en el panel, ordenadas por severidad con acceso directo al activo afectado.» Submódulo de Integración de Alertas \`:4924\`: «encargado de consumir y reflejar el estado de alertas activas provenientes de RF-57». Matriz \`tests/Test_Testing/Test_Modulo3/Casos_Prueba(Modulo3 Agrupado).csv:75\`, TC-M03-191: «${ORACULO}»\n- **Precondiciones:** Usuario Productor con acceso a la unidad productiva ${unidad}. ${precondicion}\n- **Pasos para reproducir:** 1) Iniciar sesión como Productor. 2) Hacer \`GET /iot/monitoreo/dashboard/${unidad}\` con \`X-Test-Run-Id\` y comprobar su eco; alternativamente, abrir Telemetría > Monitoreo y seleccionar el área. 3) Revisar respuesta o pantalla buscando total y lista de alertas activas. La alternativa UI no implica ejecución UI en este RUN.\n- **Resultado esperado:** HTTP 200 con sección integrada de alertas activas: número total y lista ordenada por severidad (CRITICO primero), cada elemento con tipo de alerta, variable afectada, tiempo transcurrido y enlace directo al activo biológico afectado.\n- **Resultado obtenido:** ${detalles} ${sinPanel ? 'No hay total global ni lista de alertas activas; el campo total cuenta sensores. Una referencia individual de alerta no constituye el panel.' : 'La sección o su orden/datos incumplen el oráculo citado.'} Los sensores se ordenan por id_sensor en \`src/telemetry/infrastructure/repositories/monitoreo_repository.py:70-74\`, no por severidad de alerta. Por lectura de código, \`MonitoreoView.tsx:143-179\` no representa el panel y las alertas aparecen en la página separada \`AlertasView.tsx:18,132\`; esta inferencia UI no fue comprobada en TEST.${observacion}\n- **Evidencia:** \`newman/newman-G98.json\` (petición/respuesta saneadas) y \`resultado.json\` (RUN, caso y comprobación), bajo el mismo RUN autorizado.\n- **Análisis (hipótesis no confirmada):** \`DashboardResponseSchema\` declara solo total/pagina/por_pagina/resumen_unidades/sensores (\`src/telemetry/infrastructure/schema/monitoreo_schema.py:67-73\`); el repositorio consulta la referencia individual de alerta activa y ordena sensores por ID (\`src/telemetry/infrastructure/repositories/monitoreo_repository.py:33-45,70-74\`), sin construir una lista de alertas del dashboard. \`MonitoreoView.tsx:143-179\` no representa el panel. Es inferencia del código de referencia, no causa raíz confirmada del despliegue.\n- **Impacto:** Los usuarios del dashboard (Productor, Veterinario e Ingeniero) no ven allí alertas activas integradas y priorizadas; acudir a otra vista dificulta reaccionar ante condiciones críticas.\n- **Qué se necesita para cerrarla:** Que API y pantalla de Monitoreo expongan el panel descrito en Salida 2 / CA-11, con total, lista ordenada y acceso al activo; QA verificará el caso en una reevaluación autorizada.`;
}
export function informe(r) {
  const estado = r.casos[CASO].estado;
  const comp = r.comprobaciones[0];
  const estructura = r.paginas.map(p => `| ${p.unidad ?? '?'} | ${p.http ?? 'sin respuesta'} | ${p.eco ? 'sí' : 'no'} | ${p.alertas_detectadas ? 'sí' : 'no'} | ${JSON.stringify(p.estructura)} | ${JSON.stringify(p.conteos_unidad)} | ${JSON.stringify(p.severidades_sensor)} | ${JSON.stringify(p.panel?.panel ?? {})} |`).join('\n') || '| — | sin respuesta | no | no | — | — | — | — |';
  const incidencia = incidenciaProducto(r, comp);
  const sinSeveridad = r.paginas.flatMap(p => p.sensores_alerta ?? []).filter(x => x.severidad_alerta == null);
  const observacionSensor = sinSeveridad.length
    ? `**Observación para Desarrollo (no es otra incidencia):** ${sinSeveridad.map(x => `El sensor ${x.id_sensor} tiene id_alerta=${x.id_alerta} y severidad_alerta=null`).join('; ')}. Conviene verificar si la severidad debería acompañar a id_alerta; esto no acredita por sí solo un segundo defecto.\n\n`
    : '';
  const analisis = `${observacionSensor}**Observación documental:** La matriz TC-M03-191 menciona CRITICO/ALTA/MEDIA (Casos_Prueba(Modulo3 Agrupado).csv:75), mientras RF-57 usa «CRITICO > MODERADO > LEVE» y «severidad: LEVE | MODERADO | CRITICO» (tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo3.md:3785,4547). QA debe aclarar la escala aplicable sin cambiar el esperado literal del caso.`;
  return `# TC-M03-G98 — ${estado}\n\n## Decisión del caso\n\n${CASO}: **${estado}**. ${comp.motivo}. RUN ${r.oficial ? 'OFICIAL' : 'NO_OFICIAL'}.${estado === 'RECHAZADO' && r.oficial ? ' Incidencia **INC-M03-191-G98-01**.' : ''}\n\n| Comprobación | Fuente | Estado | Evidencia |\n| --- | --- | --- | --- |\n| API-191-01 | API | ${comp.estado} | ${comp.evidencia ?? 'sin evidencia'} |\n\n## Identificación\n\nGrupo G98; RF-58 / CU04; versión V${r.version}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${r.autorizacion}; backend ${BACKEND}; frontend ${FRONTEND}; Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}. UI no requerida; Cypress 0.\n\n## Esperado y requisito\n\nMatriz TC-M03-191: «${ORACULO}» Datos: «Alertas activas de severidad CRITICO, ALTA y MEDIA sobre distintos sensores de la misma unidad.» RF-58 Salida 2, Especificacion-Requerimientos-Modulo3.md:5400-5407: número total, lista ordenada (CRITICO primero), tipo, variable, tiempo y enlace. CA-11, línea 5531-5532: alertas ACTIVAS integradas, ordenadas y con acceso al activo. RF-57, línea 3785: «CRITICO > MODERADO > LEVE»; línea 4547: «severidad: LEVE | MODERADO | CRITICO». La matriz usa ALTA/MEDIA; ambas escalas se comprueban de forma explícita y no se mezclan.\n\n## Observado por unidad\n\n| Unidad | HTTP | Eco | Alertas detectadas | Campos raíz | Conteos por unidad | Severidades por sensor | Panel: ruta, campos, total, lista y severidades |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n${estructura}\n\nCandidatas: ${r.unidades.join(', ') || 'ninguna'}. Páginas ${r.paginas.length}/${PRESUPUESTO.paginas_dashboard}; presupuesto: ${PRESUPUESTO.solicitudes_en_run} GET dentro del RUN, ${PRESUPUESTO.margen_cierre} DELETE y ${PRESUPUESTO.duracion_segundos} s. ${r.observaciones.join(' ')}\n\n## Incidencias de producto\n\n${incidencia}\n\n## Incidencias técnicas QA\n\n${r.problemas_tecnicos.join('; ') || 'Ninguna.'}\n\n## Análisis de causas y observaciones\n\n${analisis}\n\n## Evidencias y efectos\n\n${r.evidencias.join(', ')}. Login Productor previo al RUN puede registrar último acceso, auditoría, notificaciones y cierre de sesiones. Las lecturas del dashboard pueden generar correo RF-58 E7 por sensores GRIS sin umbral no desactualizados. Sin escrituras de escenario.\n\n## Cierre y rollback\n\nDELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback ${r.cierre.rollback.verificado ? 'verificado' : 'NO verificado'}: ${r.cierre.rollback.motivo}. No se afirma reversión de efectos externos.\n\n## Conclusión y acción\n\n${estado}: ${comp.motivo}. ${estado === 'RECHAZADO' && r.oficial ? 'Derivar a Desarrollo con la respuesta pública saneada.' : estado === 'APROBADO' ? 'Conservar evidencia del panel observado.' : 'Resolver el impedimento documentado y reintentar solo con autorización particular.'}\n`;
}
function finalizar(c, r, secretos) {
  const estado = r.comprobaciones[0].estado;
  r.casos[CASO] = { estado, motivo: r.comprobaciones[0].motivo };
  const nombre = c.version === 1 ? 'TC-M03-G98_resultado.md' : `TC-M03-G98_reevaluacion_V${c.version}.md`;
  r.evidencias = [...new Set([...r.evidencias, 'resultado.json', nombre])];
  const evidenciasOk = r.evidencias.every(x => typeof x === 'string' && !x.includes('..') && !path.isAbsolute(x)
    && (x === nombre || x === 'resultado.json' || fs.existsSync(path.join(c.directorio, x))));
  r.oficial = esOficial(estado, r, evidenciasOk);
  r.fin = new Date().toISOString();
  escribir(path.join(c.directorio, 'resultado.json'), r);
  fs.writeFileSync(path.join(c.directorio, nombre), sanearArtefacto(informe(r), secretos));
}
export async function evaluar(c, { env = leerEnv(), ensayo = false } = {}) {
  if (!fs.existsSync(c.directorio)) throw Error('RUN_NO_CREADO_POR_LANZADOR');
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G98', run_id: c.runId, version: c.version, operacion: c.operacion,
    autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST', oficial: false,
    consume_version: false, casos: { [CASO]: { estado: 'NO_CONCLUYENTE', motivo: 'Sin ejecución' } },
    comprobaciones: [{ caso: CASO, fuente: 'API', id: 'API-191-01', tipo: 'ASSERT', estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta', evidencia: null }],
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [], bitacora: [],
    paginas: [], unidades: [], observaciones: [], problemas_tecnicos: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'RUN no cerrado' } },
    inicio: new Date().toISOString() };
  const secretos = [env.QA_SANDBOX_SECRET, env.QA_PROD_PASSWORD, env.QA_PROD_EMAIL].filter(Boolean);
  let abierto = false;
  try {
    const pre = preflight(c, env, ensayo); escribir(path.join(c.directorio, 'preflight.json'), pre);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    r.preflight_herramientas.newman = prevalidarNewman();
    if (!r.preflight_herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    const login = await pedir(api, 'POST', '/sesiones/', { cuerpo: {
      correo_electronico: env.QA_PROD_EMAIL, contrasena: env.QA_PROD_PASSWORD }, bitacora: r.bitacora });
    if (login.http !== 200 || !login.cuerpo?.token) throw Error(`LOGIN_PRODUCTOR_HTTP_${login.http}`);
    secretos.push(login.cuerpo.token);
    abierto = true; r.consume_version = true;
    r.unidades = await descubrir(api, login.cuerpo.token, env, c, r);
    const n = await ejecutarNewman(c, { api, token: login.cuerpo.token, env, unidades: r.unidades, secretos, ensayo });
    r.evidencias.push(...n.artefactos);
    r.paginas = n.paginas;
    for (const p of n.paginas) r.bitacora.push({ metodo: 'GET',
      ruta: `/iot/monitoreo/dashboard/${p.unidad}?pagina=${p.pagina}&por_pagina=${PRESUPUESTO.por_pagina}`,
      http: p.http, en_run: true, eco: p.eco });
    const { datos, problemasTecnicos } = evaluarNewman(n);
    r.comprobaciones[0] = { ...r.comprobaciones[0], ...datos, evidencia: n.artefactos[0] ?? null };
    r.problemas_tecnicos.push(...problemasTecnicos);
  } catch (e) {
    const motivo = String(e.message).slice(0, 180);
    r.problemas_tecnicos.push(motivo);
    if (r.comprobaciones[0].motivo === 'Sin respuesta') r.comprobaciones[0].motivo = `Ejecución no completada: ${motivo}`;
  } finally {
    if (abierto) try {
      const cierre = await pedir(api, 'DELETE', `/test-control/runs/${c.runId}`,
        { secreto: env.QA_SANDBOX_SECRET, bitacora: r.bitacora });
      r.cierre.run.cierre_http = cierre.http;
      const dentro = r.bitacora.filter(x => x.en_run);
      const soloLectura = dentro.length > 0 && dentro.every(x => x.metodo === 'GET' && x.eco === true);
      r.cierre.rollback.verificado = cierre.http === 200 && soloLectura;
      r.cierre.rollback.motivo = r.cierre.rollback.verificado
        ? `Bitácora: ${dentro.length} GET con eco, ninguna escritura de escenario; DELETE 200`
        : `Sin verificación conjunta: GET con eco=${soloLectura}; DELETE HTTP ${cierre.http}`;
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
        QA_SANDBOX_SECRET: 'ENSAYO_SECRET', QA_PROD_EMAIL: 'productor@example.test', QA_PROD_PASSWORD: 'ENSAYO_PASS' }
        : leerEnv();
      const r = await evaluar(c, { env, ensayo });
      console.log(JSON.stringify({ run_id: r.run_id, estado: r.casos[CASO].estado, oficial: r.oficial }));
      if (r.problemas_tecnicos.length) process.exitCode = 2;
    } catch (e) { console.error(`G98: ${e.message}`); process.exitCode = 2; }
  }
}
