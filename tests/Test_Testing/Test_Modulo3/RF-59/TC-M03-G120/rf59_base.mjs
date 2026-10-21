import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { args, gate, parseEnv, ENV_PATH, evidence, request, nativeFetch, verdict } from '../../RF-58/TC-M03-G108/qa_lote6_base.mjs';

export { args, gate, parseEnv, ENV_PATH, evidence, verdict };
export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../..');
export function need(r, status, label) {
  if (r.status !== status) throw Error(`PRE: ${label}: HTTP ${r.status}`);
  return r.data;
}
export function count(r) {
  const n = r.status === 200 ? Number(r.data?.data?.[0]?.n) : NaN;
  return Number.isSafeInteger(n) && n >= 0 ? n : null;
}
export function witness(serial) {
  if (!/^[A-Za-z0-9_-]{1,50}$/.test(serial)) throw Error('Serial QA inválido');
  return `SELECT count(*) AS n FROM auditoria.logs_dml WHERE esquema_afectado='modulo9' AND tabla_afectada='dispositivos_iot' AND tipo_operacion='INSERT' AND datos_nuevos->>'serial'='${serial}'`;
}
export function query(pathname, params) {
  return pathname + '?' + new URLSearchParams(Object.entries(params).filter(([,v]) => v !== undefined && v !== null).map(([k,v]) => [k,String(v)])).toString();
}
export function secretsFree(text, secrets) {
  return !secrets.filter(x => x?.length > 5).some(x => text.includes(x));
}
export async function context(group, cases, dir, a, { volume = false } = {}) {
  const v = parseEnv(fs.readFileSync(ENV_PATH, 'utf8'));
  const g = gate(v, a, { login: true, sandbox: true });
  if (!v.QA_SETUP_EMAIL || !(v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD)) g.errores.push('credenciales preparador QA');
  if (volume && !a.efectos.includes('volumen-exportacion')) g.errores.push('autorización específica volumen-exportacion');
  if (g.errores.length) return { blocked: g.errores };
  const c = evidence(dir, group, cases, a, v);
  c.ev.rf = 'RF-59'; c.ev.cu = 'CU04'; c.ev.sandbox.rollback = false;
  const req = (method, route, opts = {}) => request(g.api, c.run, v.QA_SANDBOX_SECRET, method, route, opts);
  const sql = (q, run = c.run) => request(g.api, run, v.QA_SANDBOX_SECRET, 'POST', '/test-control/query', { body: { query: q } });
  const outside = async (q, suffix) => {
    const run = `${c.run}-${suffix}`;
    try { return await sql(q, run); }
    finally { await req('DELETE', `/test-control/runs/${run}`, { control: true }); }
  };
  let opened = false, serial = null;
  async function open() {
    const probe = await req('DELETE', `/test-control/runs/${c.run}-PREFLIGHT`, { control: true });
    if (probe.status !== 404) throw Error('PRE: sandbox no verificable');
    opened = true;
  }
  async function login(email, password) {
    const d = need(await req('POST', '/sesiones/', { body: { correo_electronico: email, contrasena: password } }), 200, 'login QA');
    if (!d?.token) throw Error('PRE: token QA no recibido');
    c.secrets.push(d.token);
    return d.token;
  }
  async function actors() {
    const setup = await login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD);
    const prod = await login(v.QA_PROD_EMAIL, v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD);
    const admin = need(await req('GET', '/usuarios/me', { token: setup }), 200, 'perfil preparador');
    const usuario = need(await req('GET', '/usuarios/me', { token: prod }), 200, 'perfil Productor');
    if (!/administrador/i.test(admin.nombre_rol || '') || !/productor/i.test(usuario.nombre_rol || '')) throw Error('PRE: roles QA insuficientes');
    return { setup, prod, usuario };
  }
  async function prepareSensor(actors) {
    const stamp = c.run.replace(/[^A-Za-z0-9]/g, '').slice(-22);
    serial = `${v.QA_DEVICE_PREFIX || 'QAAUTO'}-G${group}-${stamp}`.slice(0, 50);
    c.secrets.push(serial);
    const metaSql = "SELECT c.relrowsecurity AS rls, has_table_privilege(current_user,'auditoria.logs_dml','SELECT') AS lectura, EXISTS (SELECT 1 FROM pg_trigger t WHERE t.tgrelid='modulo9.dispositivos_iot'::regclass AND NOT t.tgisinternal AND t.tgenabled<>'D' AND pg_get_triggerdef(t.oid) ILIKE '%audit%') AS trigger_activo FROM pg_class c WHERE c.oid='auditoria.logs_dml'::regclass";
    const meta = need(await outside(metaSql, 'META'), 200, 'permisos de testigo')?.data?.[0];
    const control = count(await outside('SELECT count(*) AS n FROM auditoria.logs_dml', 'CONTROL'));
    if (meta?.rls !== false || meta?.lectura !== true || meta?.trigger_activo !== true || control === null || control < 1) throw Error('PRE: testigo externo sin permisos, trigger o control positivo');
    const fp = new Set((need(await req('GET', '/configuracion/fincas', { token: actors.prod }), 200, 'fincas Productor').items || []).map(x => Number(x.id_finca)));
    const fa = (need(await req('GET', '/configuracion/fincas', { token: actors.setup }), 200, 'fincas Preparador').items || []).map(x => Number(x.id_finca));
    let finca = fa.find(id => fp.has(id));
    if (!finca) finca = need(await req('POST', '/configuracion/fincas', { token: actors.setup, body: { nombre: `QA G${group} ${stamp}`.replace(/\d/g, d => 'abcdefghij'[Number(d)]), ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'QA', latitud: 2.9273, longitud: -75.2819 }, tamano_h: 1, id_usuario: actors.usuario.id_usuario } }), 201, 'crear finca').id_finca;
    const tipo = (need(await req('GET', '/configuracion/tipos-area?solo_activos=true', { token: actors.setup }), 200, 'tipos área').items || []).find(x => x.es_activo);
    const especie = (need(await req('GET', '/configuracion/especies?solo_activas=true', { token: actors.setup }), 200, 'especies').items || []).find(x => x.es_activo);
    const tipoDisp = (need(await req('GET', '/configuracion/tipos-dispositivo-iot', { token: actors.setup }), 200, 'tipos dispositivo').items || []).find(x => x.categoria === 'SENSOR');
    if (![tipo, especie, tipoDisp].every(Boolean)) throw Error('PRE: catálogos de infraestructura incompletos');
    const area = need(await req('POST', '/configuracion/infraestructuras', { token: actors.setup, body: { nombre_infraestructura: `QA G${group} ${stamp}`, tipo_area: tipo.nombre, superficie: 25, finca_id: finca, descripcion_infraestructura: `QA ${c.run}`, especie_id: especie.id_especie } }), 201, 'crear área');
    const disp = need(await req('POST', '/configuracion/dispositivos-iot', { token: actors.setup, body: { serial, descripcion: `QA ${c.run}`, id_infraestructura: area.id_infraestructura, id_tipo_dispositivo: tipoDisp.id_tipo_dispositivo, es_activo: true } }), 201, 'crear dispositivo');
    const wi = count(await sql(witness(serial)));
    const wo = count(await outside(witness(serial), 'SONDA'));
    c.ev.sandbox.aislamiento = { dentro: wi, fuera: wo, control };
    if (wi !== 1 || wo !== 0) throw Error('PRE: aislamiento no demostrado');
    const sensor = need(await req('POST', `/configuracion/dispositivos-iot/${disp.id_dispositivo_iot}/sensores`, { token: actors.setup, body: { nombre: `QA G${group} ${stamp} S1`, categoria: 'TEMPERATURA' } }), 201, 'crear sensor');
    need(await req('POST', `/configuracion/sensores/${sensor.id_sensores}/asociar`, { token: actors.setup, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, punto_instalacion: `QA G${group}` } }), 201, 'asociar sensor');
    need(await req('GET', `/configuracion/infraestructuras/${area.id_infraestructura}`, { token: actors.prod }), 200, 'visibilidad Productor');
    return { area: area.id_infraestructura, device: disp.id_dispositivo_iot, sensor: sensor.id_sensores, serial, finca };
  }
  async function download(route, token, maxBytes = 100_000_000) {
    const response = await nativeFetch(g.api + route, { headers: { Accept: 'application/octet-stream,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/json', Authorization: `Bearer ${token}`, 'X-Test-Run-Id': c.run, 'X-Sandbox-Secret': v.QA_SANDBOX_SECRET }, redirect: 'manual', signal: AbortSignal.timeout(60000) });
    if (response.headers.get('x-test-run-id') !== c.run) throw Error('PRE: falta eco del sandbox en exportación');
    const len = Number(response.headers.get('content-length') || 0);
    if (len > maxBytes) throw Error('PRE: archivo supera tope de descarga QA');
    const chunks = []; let size = 0;
    for await (const chunk of response.body || []) { size += chunk.length; if (size > maxBytes) { await response.body.cancel().catch(() => {}); throw Error('PRE: archivo supera tope de descarga QA'); } chunks.push(chunk); }
    return { status: response.status, headers: Object.fromEntries(response.headers), bytes: Buffer.concat(chunks) };
  }
  async function close() {
    if (!opened) { c.ev.sandbox.rollback = true; return; }
    try {
      const first = await req('DELETE', `/test-control/runs/${c.run}`, { control: true });
      const second = await req('DELETE', `/test-control/runs/${c.run}`, { control: true });
      const after = serial ? count(await outside(witness(serial), 'POST')) : 0;
      c.ev.sandbox.rollback = first.status === 200 && second.status === 404 && after === 0;
    } catch (e) { c.ev.sandbox.rollback = false; c.ev.dependencias.push(`Rollback no verificable: ${e.message}`); }
  }
  return { v, g, c, req, sql, outside, open, actors, prepareSensor, download, close };
}
