// Infraestructura compartida de G100 y G101: solo se conecta tras la barrera.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { envQa, autorizar, version, sqlTestigo, fetchAutorizado, tipoFallo } from '../TC-M03-G99/ejecutar_tc_m03_g99.mjs';

const realFetch = fetchAutorizado;
globalThis.fetch = async () => { throw Error('BLOQUEO_RED_LOTE5'); };
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../../../..');
export { envQa, autorizar, version };
export const envPath = path.join(ROOT, '.env.qa');

export function modulos() {
  const npm = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', shell: process.platform === 'win32' });
  if (npm.status !== 0) throw Error('npm global no disponible');
  const require = createRequire(path.join(ROOT, 'package.json'));
  return { newman: require(path.join(npm.stdout.trim(), 'newman')), cypress: require('cypress') };
}
export function argumentos(argv) {
  const a = { modo: 'local', efectos: [] };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--validar-local') a.modo = 'local';
    else if (k === '--ejecutar') a.modo = 'ejecutar';
    else if (['--ambiente', '--autorizacion', '--tipo', '--version'].includes(k)) a[k.slice(2)] = argv[++i];
    else if (k === '--aceptar-efectos') a.efectos.push(...String(argv[++i] || '').split(','));
    else throw Error(`Argumento desconocido ${k}`);
  }
  return a;
}
export function clasificar(estado, pre, asserts, rollback) {
  if (estado !== 'CONCLUIDA' || !rollback || pre.some(x => !x.ok)) return 'BLOQUEADO';
  if (asserts.some(x => !x.ok && x.observado)) return 'RECHAZADO';
  return asserts.length && asserts.every(x => x.ok) ? 'APROBADO' : 'BLOQUEADO';
}
export function lectura({ dispositivo, sensor, serial, valor, fecha, origen = 'TIEMPO_REAL' }) {
  return { device_id: dispositivo, sensor_id: sensor, tipo_variable: 'TEMPERATURA_AMBIENTAL', valor, unidad: '°C', timestamp_captura: fecha, access_key: serial, origen, estado_conectividad: true };
}
export function conteo(r) {
  const d = r?.data?.data?.[0];
  return r?.status === 200 && Number.isSafeInteger(Number(d?.n)) && Number(d.n) >= 0 ? Number(d.n) : null;
}

export async function ejecutarGrupo({ numero, casos, cantidad, carpeta, escenario, a }) {
  const v = envQa(fs.readFileSync(envPath, 'utf8'));
  const gate = autorizar(v, a);
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.errores.join(', ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) throw Error('--tipo evaluacion|reintento obligatorio');
  const { n, carpeta: resultados } = version(carpeta, a.tipo, a.version);
  const { newman, cypress } = modulos();
  const stamp = new Date().toISOString().replace(/\D/g, '').slice(0, 14);
  const run = `G${numero}-${n === 1 ? 'EVAL' : 'REEVAL'}-V${n}-${stamp}`;
  const out = path.join(resultados, run);
  fs.mkdirSync(resultados, { recursive: true }); fs.mkdirSync(out);
  const serial = `${v.QA_DEVICE_PREFIX || 'QAAUTO'}-G${numero}-${stamp}`.slice(0, 50);
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_PROD_PASSWORD].filter(Boolean);
  const registrarSecreto = x => { if (x) secretos.push(x); };
  const limpiar = s => secretos.reduce((t, x) => t.replaceAll(x, '[REDACTADO]'), String(s)).replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT]');
  const ev = { grupo: `TC-M03-G${numero}`, rf: 'RF-58', cu: 'CU04', casos, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', pre: [], asserts: [], dependencias: [], sandbox: {}, inicio: new Date().toISOString() };
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  let abierto = false, creado = false;
  async function req(method, ruta, { token, body, rid = run, control = false, timeout = 30000 } = {}) {
    const headers = { Accept: 'application/json', 'X-Sandbox-Secret': v.QA_SANDBOX_SECRET };
    if (!control) headers['X-Test-Run-Id'] = rid;
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const r = await realFetch(`${gate.api}${ruta}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), redirect: 'manual', signal: AbortSignal.timeout(timeout) });
    const data = await r.json().catch(() => null);
    if (!control && r.headers.get('x-test-run-id') !== rid) throw Error(`Falta eco de sandbox: ${ruta}`);
    return { status: r.status, data };
  }
  const need = (r, s, nombre) => { if (r.status !== s) throw Error(`${nombre}: HTTP ${r.status}`); return r.data; };
  const query = (sql, rid = run) => req('POST', '/test-control/query', { body: { query: sql }, rid });
  async function fuera(sql, sufijo) {
    const rid = `${run}-${sufijo}`;
    try { return await query(sql, rid); } finally { await req('DELETE', `/test-control/runs/${rid}`, { control: true }); }
  }
  const assert = (nombre, ok, observado = true, detalle) => ev.asserts.push({ nombre, ok: !!ok, observado, detalle });
  const pre = (nombre, ok, detalle) => { ev.pre.push({ nombre, ok: !!ok, detalle }); if (!ok) throw Error(`PRE: ${nombre}${detalle ? `: ${detalle}` : ''}`); };
  try {
    const probe = await req('DELETE', `/test-control/runs/${run}-PREFLIGHT`, { control: true });
    pre('sandbox de TEST', probe.status === 404);
    abierto = true;
    const login = async (email, pass) => { const d = need(await req('POST', '/sesiones/', { body: { correo_electronico: email, contrasena: pass } }), 200, 'Login QA'); pre('token QA', !!d?.token); secretos.push(d.token); return d.token; };
    const setup = await login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD);
    const prod = await login(v.QA_PROD_EMAIL, v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD);
    const me = need(await req('GET', '/usuarios/me', { token: prod }), 200, 'Productor');
    pre('rol Productor', /productor/i.test(me.nombre_rol || ''));
    const admin = need(await req('GET', '/usuarios/me', { token: setup }), 200, 'Preparador');
    pre('rol Administrador para preparar', /administrador/i.test(admin.nombre_rol || ''));
    const meta = "SELECT c.relrowsecurity AS rls, has_table_privilege(current_user,'auditoria.logs_dml','SELECT') AS lectura, EXISTS (SELECT 1 FROM pg_trigger t WHERE t.tgrelid='modulo9.dispositivos_iot'::regclass AND NOT t.tgisinternal AND t.tgenabled<>'D' AND pg_get_triggerdef(t.oid) ILIKE '%audit%') AS trigger_activo FROM pg_class c WHERE c.oid='auditoria.logs_dml'::regclass";
    const m = need(await fuera(meta, 'META'), 200, 'Metadatos auditoría')?.data?.[0];
    pre('testigo sin RLS, visible y con trigger activo', m?.rls === false && m?.lectura === true && m?.trigger_activo === true);
    const control = conteo(await fuera('SELECT count(*) AS n FROM auditoria.logs_dml', 'CONTROL'));
    pre('control observable fuera del RUN', control !== null && control > 0);
    ev.fase = 'PREPARACION';
    const fp = new Set((need(await req('GET', '/configuracion/fincas', { token: prod }), 200, 'Fincas Productor').items || []).map(x => Number(x.id_finca)));
    const fa = (need(await req('GET', '/configuracion/fincas', { token: setup }), 200, 'Fincas preparador').items || []).map(x => Number(x.id_finca));
    let finca = fa.find(id => fp.has(id));
    if (!finca) finca = need(await req('POST', '/configuracion/fincas', { token: setup, body: { nombre: `QA Monitoreo ${stamp}`.replace(/\d/g, d => 'abcdefghij'[Number(d)]), ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'QA', latitud: 2.9273, longitud: -75.2819 }, tamano_h: 1, id_usuario: me.id_usuario } }), 201, 'Crear finca').id_finca;
    const tipo = (need(await req('GET', '/configuracion/tipos-area?solo_activos=true', { token: setup }), 200, 'Tipo área').items || []).find(x => x.es_activo);
    const especie = (need(await req('GET', '/configuracion/especies?solo_activas=true', { token: setup }), 200, 'Especie').items || []).find(x => x.es_activo);
    const tipoDisp = (need(await req('GET', '/configuracion/tipos-dispositivo-iot', { token: setup }), 200, 'Tipo dispositivo').items || []).find(x => x.categoria === 'SENSOR');
    const rango = (need(await req('GET', '/configuracion/sensores/rangos-calibracion', { token: setup }), 200, 'Rango calibración').items || []).find(x => x.categoria === 'TEMPERATURA');
    pre('catálogos para sensor propio', [tipo, especie, tipoDisp, rango].every(Boolean));
    const area = need(await req('POST', '/configuracion/infraestructuras', { token: setup, body: { nombre_infraestructura: `QA G${numero} ${stamp}`, tipo_area: tipo.nombre, superficie: 25, finca_id: finca, descripcion_infraestructura: `QA ${run}`, especie_id: especie.id_especie } }), 201, 'Crear área');
    const disp = need(await req('POST', '/configuracion/dispositivos-iot', { token: setup, body: { serial, descripcion: `QA ${run}`, id_infraestructura: area.id_infraestructura, id_tipo_dispositivo: tipoDisp.id_tipo_dispositivo, es_activo: true } }), 201, 'Crear dispositivo');
    creado = true;
    const dentro = conteo(await query(sqlTestigo(serial)));
    const externo = conteo(await fuera(sqlTestigo(serial), 'SONDA'));
    pre('aislamiento testigo auditable', dentro === 1 && externo === 0);
    ev.sandbox.aislamiento = { dentro, fuera: externo, control };
    const sensores = [];
    for (let i = 0; i < cantidad; i++) {
      const nombre = `QA G${numero} ${stamp} S${String(i + 1).padStart(2, '0')}`;
      const s = need(await req('POST', `/configuracion/dispositivos-iot/${disp.id_dispositivo_iot}/sensores`, { token: setup, body: { nombre, categoria: 'TEMPERATURA' } }), 201, `Crear sensor ${i + 1}`);
      need(await req('POST', `/configuracion/sensores/${s.id_sensores}/asociar`, { token: setup, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, punto_instalacion: `QA G${numero}` } }), 201, `Asociar ${i + 1}`);
      need(await req('POST', `/configuracion/sensores/${s.id_sensores}/calibrar`, { token: setup, body: { id_dispositivo_iot: disp.id_dispositivo_iot, id_infraestructura: area.id_infraestructura, valor_referencia: Number(((Number(rango.valor_min) + Number(rango.valor_max)) / 2).toFixed(2)), ganancia: 1, offset: 0, fecha_calibracion: new Date(Date.now() - 600000).toISOString(), observaciones: `QA ${run}`, modo_calibracion: 'SENSOR' } }), 201, `Calibrar ${i + 1}`);
      sensores.push({ id: s.id_sensores, nombre });
    }
    need(await req('GET', `/configuracion/infraestructuras/${area.id_infraestructura}`, { token: prod }), 200, 'Visibilidad Productor');
    // Sembrar por API; el post-commit futuro debe ser observable en el sandbox para ejecutar el escenario.
    for (let i = 0; i < sensores.length; i++) {
      const r = await req('POST', '/iot/telemetria', { body: lectura({ dispositivo: disp.id_dispositivo_iot, sensor: sensores[i].id, serial, valor: 25, fecha: new Date(Date.now() - (sensores.length - i) * 1000).toISOString() }) });
      pre(`ingesta inicial ${i + 1} por contrato oficial`, r.status === 201, `HTTP ${r.status}; DEV-06 puede exigir token de servicio todavía no documentado`);
    }
    let dash;
    let observables = false;
    for (let intento = 0; intento < 10; intento++) {
      dash = need(await req('GET', `/iot/monitoreo/dashboard/${area.id_infraestructura}?pagina=1&por_pagina=50`, { token: prod }), 200, 'Dashboard preparado');
      observables = sensores.every(s => {
        const x = (dash.sensores || []).find(y => Number(y.id_sensor) === Number(s.id));
        return x && Number(x.ultimo_valor) === 25 && x.estado_conectividad === 'ONLINE';
      });
      if (observables) break;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    pre('todos los sensores activos y lecturas del RUN observables', observables, 'post-commit debe ver transacción sandbox');
    ev.datos = { area: area.id_infraestructura, dispositivo: disp.id_dispositivo_iot, sensores };
    guardar();
    ev.fase = 'ESCENARIO';
    await escenario({ v, a, gate, n, out, run, serial, stamp, ev, req, query, need, pre, assert, sensores, area: area.id_infraestructura, dispositivo: disp.id_dispositivo_iot, prod, newman, cypress, limpiar, guardar, registrarSecreto });
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = ev.fase === 'ESCENARIO' ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.fallo_tipo = tipoFallo(String(e.message)); ev.dependencias.push(limpiar(e.message)); }
  finally {
    if (abierto) try {
      const c = await req('DELETE', `/test-control/runs/${run}`, { control: true });
      const d = await req('DELETE', `/test-control/runs/${run}`, { control: true });
      const p = creado ? await fuera(sqlTestigo(serial), 'POST') : null;
      ev.sandbox.rollback = c.status === 200 && d.status === 404 && (!creado || conteo(p) === 0);
      if (!ev.sandbox.rollback) ev.dependencias.push('Rollback no confirmado');
    } catch (e) { ev.sandbox.rollback = false; ev.dependencias.push(limpiar(e.message)); }
    ev.veredicto = clasificar(ev.estado, ev.pre, ev.asserts, ev.sandbox.rollback);
    ev.fin = new Date().toISOString(); guardar();
    const nombre = n === 1 ? `TC-M03-G${numero}_resultado.md` : `TC-M03-G${numero}_reevaluacion_V${n}.md`;
    fs.writeFileSync(path.join(out, nombre), limpiar(`# TC-M03-G${numero} — ${casos.join(', ')}\n\nRUN ${run}; TEST; estado ${ev.estado}; resultado propuesto ${ev.veredicto}. Revisión QA requerida.\n\nFase: ${ev.fase}; naturaleza del fallo técnico: ${ev.fallo_tipo || 'ninguna'}.\n\nPrecondiciones: ${JSON.stringify(ev.pre)}\n\nAserciones: ${JSON.stringify(ev.asserts)}\n\nDependencias: ${ev.dependencias.join('; ') || 'ninguna'}\n\nRollback: ${ev.sandbox.rollback ? 'confirmado' : 'NO confirmado'}\n`));
  }
  return ev.estado === 'CONCLUIDA' ? 0 : 4;
}
