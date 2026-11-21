#!/usr/bin/env node
// TC-M03-258, 259, 260 y 261 (RF-59 CA-5, Restricción 2, Fase 1; CU04 FA-01, E1): control de acceso
// por granja, por recurso usado como filtro y por rol en el historial y la exportación
// (OWASP API1 autorización a nivel de objeto; API5 a nivel de función).
//
// Escenario CONSTRUIDO en el sandbox con APIs oficiales (cuenta de preparación = Administrador):
// - Granja A con acceso del Ingeniero de Campo (creada con su id_usuario, sin tocar sus asignaciones):
//   unidad A con sensor y lectura (sus recursos autorizados).
// - Granja B sin acceso del Ingeniero: unidad B1 (sensor, lecturas y alerta activa) para 258, y unidad B2
//   (sensor, lecturas y un activo biológico INDIVIDUAL) para las tres variantes de 259.
// - La existencia de cada recurso ajeno la demuestra un actor autorizado (el Administrador obtiene su
//   historial o su ficha). 259 compara además la respuesta con la de un identificador inexistente: deben
//   ser indistinguibles (no revela existencia ni características).
// - Actores de 260 (lectura sí, exportación no) y 261 (sin lectura) se eligen por sus permisos REALES
//   (GET /roles/{id_rol}/permisos, recurso 34: acción 2 Leer, acción 5 Ejecutar), nunca por el nombre de la cuenta.
// - Matriz parametrizada actor × endpoint × recurso × comprobación (MATRIZ): Newman la recorre con
//   iterationData sobre una sola petición. La auditoría de 258 y 260 se busca en las bitácoras oficiales
//   RF-10 (/auditoria/) y RF-63 (/iot/auditoria) con testigo positivo (G107/G127). No es auditoria.logs_dml,
//   que solo es el testigo de aislamiento del sandbox.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  leerEnv, autorizar, version, carpetaResultados, runId, nombreInforme, argumentos, newmanModulo, sello, serialQa, nombreSensor,
  sandbox, catalogos, construirUnidad, cuerpoLectura, cuerpoAlerta, redactor, informe,
  veredictoCasos, sintaxisColeccion, nombresDeTests, casoDeTexto, idDeTexto, varianteDeTexto, tipoDeTexto, consultaTestigoDispositivo,
} from './monitoreo_lib.mjs';

export const GRUPO = 'TC-M03-G129';
export const CASOS = ['TC-M03-258', 'TC-M03-259', 'TC-M03-260', 'TC-M03-261'];
export const RECURSO_HISTORIAL = 34, LEER = 2, EJECUTAR = 5;
export const RECURSOS_259 = ['SENSOR', 'ACTIVO', 'UNIDAD'];
export const REQUERIDAS = {
  // La auditoría tiene variante propia: si la bitácora no es observable, solo se bloquea esa aserción.
  'TC-M03-258': ['API-258-01@GRANJA', 'API-258-02@GRANJA', 'API-258-03@GRANJA_AUDITORIA'],
  'TC-M03-259': RECURSOS_259.flatMap(x => [`API-259-01@${x}`, `API-259-02@${x}`]),
  'TC-M03-260': ['API-260-01@EXPORTAR', 'API-260-02@EXPORTAR', 'API-260-03@EXPORTAR_AUDITORIA'],
  'TC-M03-261': ['API-261-01@LECTURA', 'API-261-02@LECTURA'],
};
/** Cuentas QA candidatas para los actores de 260 y 261 (se eligen por permisos reales). */
export const CANDIDATAS = ['CONTADOR', 'REVISOR_FISCAL', 'EXTERNO_AGROFUSION', 'GESTOR_GRANJA', 'SUPERVISOR', 'VETERINARIO', 'PROD', 'ADMIN'];
/** Identificador de control que no existe (verificado con 404 por un actor autorizado). */
export const INEXISTENTE = 2147480000;

/**
 * Matriz parametrizada: cada fila es una petición. `actor` = ENG | SETUP | EXP | NOLEE; `ruta` = historial |
 * exportar | activo; `filtros` usa referencias simbólicas que el ejecutor resuelve con ids reales del RUN.
 * Tipos: control (PRE del caso), existe / existe_get (PRE de la variante: el recurso existe y lo ve un actor
 * autorizado), ajeno (ASSERT -01 y, en 258, -02), inexistente (ASSERT 259-02: indistinguible del ajeno),
 * control_lectura (PRE de 260), exportar_sin_permiso (ASSERT 260-01/02), lectura_sin_permiso (ASSERT 261-01/02).
 */
export const MATRIZ = [
  { caso: 'TC-M03-258', variante: null, tipo: 'control', actor: 'ENG', ruta: 'historial', filtros: { id_infraestructura: 'A.unidad' }, espera: ['id_sensor', 'A.sensor'], nombre: 'el actor consulta el historial de su granja A' },
  { caso: 'TC-M03-258', variante: 'GRANJA', tipo: 'existe', actor: 'SETUP', ruta: 'historial', filtros: { id_infraestructura: 'B1.unidad' }, espera: ['id_sensor', 'B1.sensor'], nombre: 'un actor autorizado obtiene el historial de la unidad de la granja B' },
  { caso: 'TC-M03-258', variante: 'GRANJA', tipo: 'ajeno', actor: 'ENG', ruta: 'historial', filtros: { id_infraestructura: 'B1.unidad' }, prohibidos: 'B1', nombre: 'historial con la unidad de la granja B' },
  { caso: 'TC-M03-259', variante: 'SENSOR', tipo: 'existe', actor: 'SETUP', ruta: 'historial', filtros: { sensor_id: 'B2.sensor' }, espera: ['id_sensor', 'B2.sensor'], nombre: 'un actor autorizado obtiene el historial del sensor ajeno' },
  { caso: 'TC-M03-259', variante: 'SENSOR', tipo: 'ajeno', actor: 'ENG', ruta: 'historial', filtros: { sensor_id: 'B2.sensor' }, prohibidos: 'B2', nombre: 'historial filtrado por un sensor ajeno' },
  { caso: 'TC-M03-259', variante: 'SENSOR', tipo: 'inexistente', actor: 'ENG', ruta: 'historial', filtros: { sensor_id: 'NX' }, prohibidos: 'B2', nombre: 'historial filtrado por un sensor inexistente' },
  { caso: 'TC-M03-259', variante: 'ACTIVO', tipo: 'existe_get', actor: 'SETUP', ruta: 'activo', id: 'B2.activo', espera: ['id_activo_biologico', 'B2.activo'], nombre: 'un actor autorizado obtiene la ficha del activo ajeno' },
  { caso: 'TC-M03-259', variante: 'ACTIVO', tipo: 'ajeno', actor: 'ENG', ruta: 'historial', filtros: { id_activo_biologico: 'B2.activo' }, contrato: 'id_activo_biologico', prohibidos: 'B2', nombre: 'historial filtrado por un activo biológico ajeno' },
  { caso: 'TC-M03-259', variante: 'ACTIVO', tipo: 'inexistente', actor: 'ENG', ruta: 'historial', filtros: { id_activo_biologico: 'NX' }, prohibidos: 'B2', nombre: 'historial filtrado por un activo biológico inexistente' },
  { caso: 'TC-M03-259', variante: 'UNIDAD', tipo: 'existe', actor: 'SETUP', ruta: 'historial', filtros: { id_infraestructura: 'B2.unidad' }, espera: ['id_sensor', 'B2.sensor'], nombre: 'un actor autorizado obtiene el historial de la unidad ajena' },
  { caso: 'TC-M03-259', variante: 'UNIDAD', tipo: 'ajeno', actor: 'ENG', ruta: 'historial', filtros: { id_infraestructura: 'B2.unidad' }, prohibidos: 'B2', nombre: 'historial filtrado por una unidad productiva ajena' },
  { caso: 'TC-M03-259', variante: 'UNIDAD', tipo: 'inexistente', actor: 'ENG', ruta: 'historial', filtros: { id_infraestructura: 'NX' }, prohibidos: 'B2', nombre: 'historial filtrado por una unidad productiva inexistente' },
  { caso: 'TC-M03-260', variante: null, tipo: 'control_lectura', actor: 'EXP', ruta: 'historial', filtros: {}, nombre: 'el rol con permiso de lectura consulta el historial' },
  { caso: 'TC-M03-260', variante: 'EXPORTAR', tipo: 'exportar_sin_permiso', actor: 'EXP', ruta: 'exportar', filtros: { id_infraestructura: 'A.unidad' }, prohibidos: 'TODO', nombre: 'exportación directa por API sin permiso de ejecución' },
  { caso: 'TC-M03-261', variante: 'LECTURA', tipo: 'lectura_sin_permiso', actor: 'NOLEE', ruta: 'historial', filtros: {}, prohibidos: 'TODO', nombre: 'historial con un rol sin permiso de lectura' },
];

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);

/** Permisos efectivos sobre el historial a partir de GET /roles/{id}/permisos (null si la lista no es válida). */
export function permisosHistorial(permisos) {
  if (!Array.isArray(permisos)) return null;
  const tiene = a => permisos.some(p => Number(p.id_recurso) === RECURSO_HISTORIAL && Number(p.id_accion) === a && p.es_activo === true);
  return { leer: tiene(LEER), ejecutar: tiene(EJECUTAR) };
}
/** Resuelve una referencia simbólica ('B2.sensor', 'NX', ...) contra los ids del escenario. */
export function resolver(ref, esc) {
  if (ref === 'NX') return INEXISTENTE;
  const [k, c] = String(ref).split('.');
  const v = esc?.[k]?.[c];
  if (v === undefined || v === null) throw Error(`Referencia sin resolver: ${ref}`);
  return v;
}
/** Filas de iterationData para Newman a partir de la MATRIZ y del escenario real del RUN. */
export function filasMatriz(esc, { api, fechaInicio, fechaFin }) {
  const prohibidosDe = k => k === 'TODO'
    ? ['A', 'B1', 'B2'].reduce((acc, x) => fusionar(acc, esc[x].prohibidos), { ids: {}, nombres: [] })
    : esc[k].prohibidos;
  return MATRIZ.map(f => {
    const q = new URLSearchParams({ fecha_inicio: fechaInicio, fecha_fin: fechaFin, ...(f.ruta === 'exportar' ? { formato: 'EXCEL' } : {}) });
    for (const [k, ref] of Object.entries(f.filtros || {})) q.set(k, String(resolver(ref, esc)));
    const url = f.ruta === 'activo' ? `${api}/activos-biologicos/${resolver(f.id, esc)}` : `${api}/iot/monitoreo/${f.ruta === 'exportar' ? 'historial/exportar' : 'historial'}?${q}`;
    return {
      caso: f.caso, variante: f.variante ?? '', tipo: f.tipo, actor: f.actor, nombre: f.nombre, url, contrato: f.contrato ?? '',
      espera_clave: f.espera?.[0] ?? '', espera_valor: f.espera ? String(resolver(f.espera[1], esc)) : '',
      prohibidos: JSON.stringify(f.prohibidos ? prohibidosDe(f.prohibidos) : { ids: {}, nombres: [] }),
    };
  });
}
function fusionar(a, b) {
  const ids = { ...a.ids };
  for (const [k, v] of Object.entries(b.ids)) ids[k] = [...(ids[k] || []), ...v];
  return { ids, nombres: [...a.nombres, ...b.nombres] };
}
/** Pares clave/valor escalares (recorrido profundo). */
export function pares(obj, out = []) {
  if (obj && typeof obj === 'object') for (const [k, v] of Object.entries(obj)) { if (v !== null && typeof v !== 'object') out.push([k, v]); pares(v, out); }
  return out;
}
/**
 * ¿El registro de bitácora documenta el intento? Usuario, recurso (la unidad solicitada o, en exportación,
 * la operación), fecha y motivo del rechazo. Excluye eventos ajenos al intento (p. ej. el login).
 */
export function registroIntento(r, intento) {
  const kv = pares(r);
  const texto = JSON.stringify(r);
  const usuario = Number(r?.id_usuario) === intento.id_usuario;
  const recurso = intento.id_unidad != null
    ? kv.some(([k, v]) => /infraestructura|unidad|entidad_afectada_id/i.test(k) && String(v) === String(intento.id_unidad))
    : /export/i.test(texto);
  const fecha = !!(r?.fecha_evento || r?.fecha_hora);
  const motivo = kv.some(([k, v]) => /motivo|raz[oó]n|codigo_error|error_code|reason/i.test(k) && String(v).trim()) || /deneg|rechaz|no autoriz|sin permiso|forbidden|ACCESO_DENEGADO/i.test(String(r?.descripcion || ''));
  return { coincide: usuario && recurso, completo: usuario && recurso && fecha && motivo };
}

function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const texto = JSON.stringify(col);
  const fuente = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const futuras = { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] };
  const ids = Object.values(REQUERIDAS).flat().map(k => k.split('@')[0]);
  ck('Matriz: TC-M03-258, 259, 260 y 261', CASOS.join() === 'TC-M03-258,TC-M03-259,TC-M03-260,TC-M03-261' && CASOS.every(c => MATRIZ.some(f => f.caso === c)));
  ck('259 con tres recursos (sensor, activo, unidad) y comparación con inexistente', RECURSOS_259.every(x => ['existe', 'ajeno', 'inexistente'].every(t => MATRIZ.some(f => f.variante === x && f.tipo.startsWith(t)))));
  ck('Recursos ajenos con existencia demostrada por un actor autorizado', MATRIZ.filter(f => f.tipo === 'ajeno').every(f => MATRIZ.some(g => g.variante === f.variante && g.tipo.startsWith('existe') && g.actor === 'SETUP')));
  ck('Ambos endpoints de la matriz (historial y exportación)', MATRIZ.some(f => f.ruta === 'historial') && MATRIZ.some(f => f.ruta === 'exportar'));
  const scripts = [...(col.event || []), ...col.item.flatMap(i => i.event || [])].flatMap(e => e.script?.exec || []).join('\n');
  ck('260 exige HTTP 403 estricto', scripts.includes('pm.expect(pm.response.code, "HTTP 403 obligatorio").to.eql(403)'));
  ck('Solo 260 impone código HTTP (403); 258 y 261 no', (texto.match(/to\.eql\(4\d\d\)/g) || []).length === 1);
  ck('Todas las aserciones requeridas aparecen en la colección o en el ejecutor', ids.every(id => texto.includes(id) || fuente.includes(`'${id}'`)));
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza la ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, futuras).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ...futuras, ambiente: 'DEV' }).ok);
  ck('Cuentas de preparación (Administrador) e Ingeniero resueltas', ['SETUP', 'ENG'].every(r => !!v[`QA_${r}_EMAIL`] && !!(v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD)) && !!v.QA_SANDBOX_SECRET);
  ck('Cuentas candidatas para los roles de 260 y 261', CANDIDATAS.filter(r => v[`QA_${r}_EMAIL`]).length >= 2);
  ck('Actores elegidos por permisos reales, no por el nombre de la cuenta', /\/roles\/\$\{/.test(fuente) && /permisosHistorial/.test(fuente));
  ck('Auditoría por bitácoras oficiales con testigo positivo', /['`]\/auditoria\/\?/.test(fuente) && /['`]\/iot\/auditoria\?/.test(fuente) && /testigo positivo/.test(fuente));
  ck('Colección parametrizada: una petición recorrida con iterationData', col.item.length === 1 && texto.includes('pm.iterationData.get'));
  ck('Cada test de la colección declara PRE, ASSERT o INFO', nombresDeTests(col).every(n => tipoDeTexto(n) !== null));
  ck('Barrera propia de Newman (nivel colección)', (col.event || []).some(e => e.listen === 'prerequest' && e.script.exec.join('\n').includes('BLOQUEO_G129')));
  try { sintaxisColeccion(col); ck('Sintaxis Postman (colección e ítems)', true); } catch { ck('Sintaxis Postman (colección e ítems)', false); }
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis librería', spawnSync(process.execPath, ['--check', path.join(DIR, 'monitoreo_lib.mjs')]).status === 0);
  ck('Testigo de aislamiento sin RLS (distinto de la auditoría evaluada)', /FROM auditoria\.logs_dml/.test(consultaTestigoDispositivo('QAAUTO-G129-1')));
  ck('Sin escrituras sobre asignaciones de usuarios ni roles', !new RegExp(["'(PUT|POST|PATCH|DELETE)', ", '`/(usuarios|roles)'].join('')).test(fuente));
  ck('Sin peticiones concurrentes al sandbox', !new RegExp(['Promise', 'all'].join('\\.')).test(fuente));
  ck('Sin carpetas RESULTADOS de construcción', !fs.existsSync(path.join(DIR, 'RESULTADOS')) && !fs.readdirSync(DIR).some(x => /^EvaluacionV\d+$/.test(x)));
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD].filter(x => x?.length > 4);
  ck('Sin secretos ni JWT literales', [fileURLToPath(import.meta.url), COLLECTION, path.join(DIR, 'monitoreo_lib.mjs')].every(f => { const t = fs.readFileSync(f, 'utf8'); return !secretos.some(s => t.includes(s)) && !/eyJ[A-Za-z0-9_-]{10,}\.eyJ/.test(t); }));
  ck('Pruebas unitarias locales', spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g129.mjs')], { encoding: 'utf8' }).status === 0);
  try { newmanModulo(ROOT); ck('Newman disponible', true); } catch { ck('Newman disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G129 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}

async function ejecutar(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const gate = autorizar(v, a);
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.motivos.join('; ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) { console.error('Indique --tipo evaluacion|reintento'); return 2; }
  const n = version(DIR, a.tipo, a.version), newman = newmanModulo(ROOT);
  const marca = sello(), run = runId(GRUPO, n, marca);
  const base = carpetaResultados(DIR, n), out = path.join(base, run);
  fs.mkdirSync(base, { recursive: true }); fs.mkdirSync(out);
  const seriales = { A: serialQa(v, 'G129', marca, 'A'), B1: serialQa(v, 'G129', marca, 'B1'), B2: serialQa(v, 'G129', marca, 'B2') };
  const letras = s => s.replace(/\d/g, d => 'abcdefghij'[Number(d)]);
  const ev = { grupo: GRUPO, rf: 'RF-59', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, dependencias: [], bloqueos: {}, aserciones: [], sandbox: {}, datos: {}, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD, ...CANDIDATAS.map(r => v[`QA_${r}_PASSWORD`]), ...Object.values(seriales)];
  let limpiar = redactor(secretos);
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  const pre = (caso, variante, nombre, ok, detalle) => ev.aserciones.push({ herramienta: 'Ejecutor', caso, tipo: 'PRE', id: null, variante, nombre: `[${caso}][PRE]${variante ? `[V:${variante}]` : ''} ${nombre}`, ok: !!ok, evidencia: false, error: ok ? undefined : detalle });
  const sb = sandbox({ api: gate.api, run, secreto: v.QA_SANDBOX_SECRET });
  let abierto = false, dispositivo = false;
  try {
    await sb.abrir(); abierto = true;
    const setup = await sb.login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD, 'preparación', /administrador/i);
    secretos.push(setup.token); limpiar = redactor(secretos);
    const S = setup.token;
    const permisosDe = async idRol => { const r = idRol ? await sb.req('GET', `/roles/${idRol}/permisos`, { token: S }) : null; return permisosHistorial(r?.status === 200 ? r.data : null); };
    // Ancla temporal del servidor, anterior a los logins de los actores (testigo positivo de la bitácora).
    const ancla = await sb.req('GET', '/auditoria/?tamano=1', { token: S });
    const desde = [200, 206].includes(ancla.status) ? ancla.data?.fecha_hasta : null;
    const meSetup = sb.need(await sb.req('GET', '/usuarios/me', { token: S }), 200, 'Identidad de preparación');
    const pSetup = await permisosDe(meSetup.id_rol);
    pre('TC-M03-259', null, 'el actor autorizado de control (Administrador) tiene lectura del historial', pSetup?.leer, JSON.stringify(pSetup));
    pre('TC-M03-258', null, 'el actor autorizado de control (Administrador) tiene lectura del historial', pSetup?.leer, JSON.stringify(pSetup));
    const eng = await sb.login(v.QA_ENG_EMAIL, v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, 'Ingeniero', /ingeniero/i);
    secretos.push(eng.token); limpiar = redactor(secretos);
    const meEng = sb.need(await sb.req('GET', '/usuarios/me', { token: eng.token }), 200, 'Identidad del Ingeniero');
    const pEng = await permisosDe(meEng.id_rol);
    for (const c of ['TC-M03-258', 'TC-M03-259']) pre(c, null, 'el actor de 258/259 tiene lectura del historial (su denegación se debe al ámbito, no al rol)', pEng?.leer, JSON.stringify(pEng));
    // Actores de 260 y 261 por permisos reales.
    const actores = { EXP: null, NOLEE: null };
    for (const r of CANDIDATAS.filter(x => v[`QA_${x}_EMAIL`] && (v[`QA_${x}_PASSWORD`] || v.QA_COMMON_PASSWORD))) {
      if (actores.EXP && actores.NOLEE) break;
      const l = await sb.req('POST', '/sesiones/', { body: { correo_electronico: v[`QA_${r}_EMAIL`], contrasena: v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD } });
      if (l.status !== 200 || !l.data?.token) continue;
      secretos.push(l.data.token); limpiar = redactor(secretos);
      const me = await sb.req('GET', '/usuarios/me', { token: l.data.token });
      const p = await permisosDe(me.data?.id_rol);
      if (!p) continue;
      const actor = { cuenta: r, token: l.data.token, id_usuario: me.data.id_usuario, id_rol: me.data.id_rol, rol: me.data.nombre_rol, permisos: p };
      if (!actores.EXP && p.leer && !p.ejecutar) actores.EXP = actor;
      else if (!actores.NOLEE && !p.leer) actores.NOLEE = actor;
    }
    pre('TC-M03-260', null, 'cuenta QA cuyo rol tiene lectura y no ejecución sobre el historial (recurso 34)', !!actores.EXP, 'ninguna cuenta candidata tiene ese perfil: requiere una cuenta QA con lectura y sin exportación');
    pre('TC-M03-261', null, 'cuenta QA autenticable cuyo rol no tiene lectura del historial (recurso 34)', !!actores.NOLEE, 'ninguna cuenta candidata tiene ese perfil');
    ev.datos.actores = Object.fromEntries(Object.entries(actores).map(([k, x]) => [k, x ? { cuenta: x.cuenta, id_rol: x.id_rol, rol: x.rol, permisos: x.permisos } : null]));

    // ---- PREPARACIÓN: granjas A y B -------------------------------------------------------------
    ev.fase = 'PREPARACION';
    const cat = await catalogos(sb, S);
    const finca = async (etiqueta, idUsuario) => sb.need(await sb.req('POST', '/configuracion/fincas', { token: S, body: { nombre: letras(`QA Historial G Ciento Veintinueve ${etiqueta} ${marca}`), ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'QA', latitud: 2.9273, longitud: -75.2819 }, tamano_h: 1, id_usuario: idUsuario } }), 201, `Crear granja ${etiqueta}`).id_finca;
    const fincaA = await finca('A', eng.id), fincaB = await finca('B', setup.id);
    const unidad = async (k, f, extra) => {
      const u = await construirUnidad(sb, { tok: S, cat, finca: f, run, nombreUnidad: `QA G129 ${marca} ${k}`, serial: seriales[k], nombres: [nombreSensor(`QA G129 ${marca}`, k, 1)], alCrearDispositivo: extra });
      sb.need(await sb.req('POST', '/iot/telemetria', { body: cuerpoLectura({ idDispositivo: u.id_dispositivo, idSensor: u.sensores[0].id, serial: seriales[k], timestamp: new Date(Date.now() - 300000).toISOString(), valor: 23 }) }), 201, `Segunda lectura de ${k}`);
      return u;
    };
    const uA = await unidad('A', fincaA, async () => { dispositivo = true; ev.sandbox.aislamiento = await sb.aislamiento(seriales.A); });
    const uB1 = await unidad('B1', fincaB);
    const alertaB1 = await sb.req('POST', '/iot/alertas', { body: cuerpoAlerta({ idDispositivo: uB1.id_dispositivo, idSensor: uB1.sensores[0].id, serial: seriales.B1, idTelemetria: uB1.sensores[0].id_telemetria, severidad: 'MODERADO' }) });
    const uB2 = await unidad('B2', fincaB);
    // Activo biológico INDIVIDUAL en B2 (especie sin atributos obligatorios para INDIVIDUAL).
    let especie = null;
    for (const e of ((await sb.need(await sb.req('GET', '/configuracion/especies?solo_activas=true', { token: S }), 200, 'Especies')).items ?? []).filter(x => x.es_activo).slice(0, 40)) {
      const m = sb.need(await sb.req('GET', `/configuracion/metricas?id_especie=${e.id_especie}&solo_activas=true`, { token: S }), 200, 'Métricas');
      if (!(m.items ?? []).some(x => x.es_obligatorio && ['INDIVIDUAL', 'AMBOS'].includes(x.aplica_a_tipo_activo))) { especie = e; break; }
    }
    if (!especie) throw Error('Ninguna especie activa admite un activo INDIVIDUAL sin atributos obligatorios');
    const hoy = new Date();
    const activo = sb.need(await sb.req('POST', '/activos-biologicos', { token: S, body: { tipo_activo: 'INDIVIDUAL', id_especie: especie.id_especie, fecha_inicio_ciclo: hoy.toISOString().slice(0, 10), origen_financiero: 'nacimiento', id_infraestructura: uB2.id, identificador: `QA-G129-${marca}`, raza: 'QA', sexo: 'Macho', fecha_nacimiento: new Date(hoy.getTime() - 365 * 86400000).toISOString() } }), 201, 'Activo biológico en B2');
    const nombreFincaB = letras(`QA Historial G Ciento Veintinueve B ${marca}`), nombreFincaA = letras(`QA Historial G Ciento Veintinueve A ${marca}`);
    const esc = {
      A: { unidad: uA.id, sensor: uA.sensores[0].id, prohibidos: { ids: { id_infraestructura: [uA.id], id_sensor: [uA.sensores[0].id], id_finca: [fincaA] }, nombres: [uA.nombre, uA.sensores[0].nombre, nombreFincaA] } },
      B1: { unidad: uB1.id, sensor: uB1.sensores[0].id, prohibidos: { ids: { id_infraestructura: [uB1.id], id_sensor: [uB1.sensores[0].id], id_finca: [fincaB], id_alerta: alertaB1.data?.id_alerta ? [alertaB1.data.id_alerta] : [] }, nombres: [uB1.nombre, uB1.sensores[0].nombre, nombreFincaB] } },
      B2: { unidad: uB2.id, sensor: uB2.sensores[0].id, activo: activo.id_activo_biologico, prohibidos: { ids: { id_infraestructura: [uB2.id], id_sensor: [uB2.sensores[0].id], id_finca: [fincaB], id_activo_biologico: [activo.id_activo_biologico] }, nombres: [uB2.nombre, uB2.sensores[0].nombre, nombreFincaB, `QA-G129-${marca}`] } },
    };
    ev.datos.escenario = { granja_A: { id: fincaA, unidad: uA.id, acceso: 'Ingeniero de Campo' }, granja_B: { id: fincaB, unidad_258: uB1.id, unidad_259: uB2.id, sensor_259: uB2.sensores[0].id, activo_259: activo.id_activo_biologico, id_alerta_B1: alertaB1.data?.id_alerta ?? null, acceso: 'solo la cuenta de preparación' }, inexistente: INEXISTENTE };
    // Ámbito del Ingeniero: A sí, B no (sin modificar sus asignaciones).
    const fincasEng = new Set((sb.need(await sb.req('GET', '/configuracion/fincas', { token: eng.token }), 200, 'Fincas del Ingeniero').items || []).map(f => Number(f.id_finca)));
    for (const c of ['TC-M03-258', 'TC-M03-259']) pre(c, null, 'el actor está autorizado para la granja A y no para la granja B', fincasEng.has(Number(fincaA)) && !fincasEng.has(Number(fincaB)), `A ${fincasEng.has(Number(fincaA))}; B ${fincasEng.has(Number(fincaB))}`);
    // Existencia por ficha (actor autorizado) y no existencia de los identificadores de control.
    const ficha = async (ruta, esperado) => (await sb.req('GET', ruta, { token: S })).status === esperado;
    pre('TC-M03-258', 'GRANJA', 'la unidad de la granja B existe (ficha 200) y tiene alerta activa', await ficha(`/configuracion/infraestructuras/${uB1.id}`, 200) && alertaB1.status === 201, `alerta HTTP ${alertaB1.status}`);
    pre('TC-M03-259', 'SENSOR', 'el sensor ajeno existe (asociaciones 200) y el de control no (404)', await ficha(`/configuracion/sensores/${uB2.sensores[0].id}/asociaciones`, 200) && await ficha(`/configuracion/sensores/${INEXISTENTE}/asociaciones`, 404), 'existencia no demostrada');
    pre('TC-M03-259', 'ACTIVO', 'el activo de control no existe (404)', await ficha(`/activos-biologicos/${INEXISTENTE}`, 404), 'el identificador de control existe');
    pre('TC-M03-259', 'UNIDAD', 'la unidad ajena existe (ficha 200) y la de control no (404)', await ficha(`/configuracion/infraestructuras/${uB2.id}`, 200) && await ficha(`/configuracion/infraestructuras/${INEXISTENTE}`, 404), 'existencia no demostrada');
    const hoyUtc = new Date().toISOString().slice(0, 10);
    const sonda = await sb.req('GET', `/iot/monitoreo/historial?fecha_inicio=${hoyUtc}&fecha_fin=${hoyUtc}&id_infraestructura=${uA.id}`, { token: eng.token });
    const fechaFin = sonda.status !== 200 && /FECHA_FIN_FUTURA/.test(JSON.stringify(sonda.data ?? '')) ? new Date(Date.now() - 86400000).toISOString().slice(0, 10) : hoyUtc;
    const fechaInicio = new Date(Date.parse(fechaFin) - 2 * 86400000).toISOString().slice(0, 10);

    // ---- MATRIZ (Newman, iterationData) ----------------------------------------------------------------
    ev.fase = 'ESCENARIOS'; guardar();
    const filas = filasMatriz(esc, { api: gate.api, fechaInicio, fechaFin });
    const tokens = { ENG: eng.token, SETUP: S, EXP: actores.EXP?.token ?? '', NOLEE: actores.NOLEE?.token ?? '' };
    const vars = { run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, autorizado_run: 'SI', base_url: gate.api, ...Object.fromEntries(Object.entries(tokens).map(([k, t]) => [`token_${k}`, t])) };
    const nr = await new Promise(resolve => newman.run({ ignoreRedirects: true,  collection: JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), environment: { values: Object.entries(vars).map(([key, value]) => ({ key, value: String(value) })) }, iterationData: filas, reporters: [], silent: true }, (error, summary) => resolve({ error, summary })));
    ev.respuestas = [];
    for (const e of nr.summary?.run?.executions || []) {
      const fila = filas[e.cursor?.iteration ?? -1] || {};
      const http = e.response?.code ?? null;
      ev.respuestas.push({ caso: fila.caso, variante: fila.variante || null, tipo: fila.tipo, actor: fila.actor, http });
      for (const x of e.assertions || []) {
        const nombre = String(x.assertion);
        ev.aserciones.push({ herramienta: 'Newman', caso: casoDeTexto(nombre) ?? fila.caso, tipo: tipoDeTexto(nombre), id: idDeTexto(nombre), variante: varianteDeTexto(nombre) ?? (casoDeTexto(nombre) ? null : fila.variante || null), nombre, ok: !x.error && !x.skipped, evidencia: http != null, http, error: x.error ? limpiar(x.error.message) : undefined });
      }
    }
    for (const f of (nr.summary?.run?.failures || []).filter(f => !/AssertionError/.test(f.error?.name || ''))) { const m = limpiar(`AUTOMATIZACION: ${f.source?.name ?? ''}: ${f.error?.message}`); ev.dependencias.push(m); for (const c of CASOS) (ev.bloqueos[c] ??= []).push(m); }
    if (nr.error) { const m = limpiar(`AUTOMATIZACION: Newman — ${nr.error.message}`); ev.dependencias.push(m); for (const c of CASOS) (ev.bloqueos[c] ??= []).push(m); }
    if (!ev.aserciones.some(x => x.caso === 'TC-M03-259' && x.variante === 'ACTIVO' && x.tipo === 'PRE' && /filtro/.test(x.nombre) && x.ok)) ev.dependencias.push('259 ACTIVO: el contrato de GET /iot/monitoreo/historial no reconoce id_activo_biologico como filtro (no aparece en filtros_aplicados); la variante queda BLOQUEADA hasta que Desarrollo lo incorpore. Su aserción de no exposición se conserva.');

    // ---- AUDITORÍA de 258 y 260 (bitácoras oficiales, testigo positivo) -------------------------------
    const buscar = async idUsuario => {
      const regs = []; let ok = !!desde, hasta = null;
      for (let p = 1; p <= 10 && desde; p++) {
        const r = await sb.req('GET', `/auditoria/?id_usuario=${idUsuario}&fecha_desde=${encodeURIComponent(desde)}${hasta ? `&fecha_hasta=${encodeURIComponent(hasta)}` : ''}&pagina=${p}&tamano=50`, { token: S });
        if (![200, 206].includes(r.status)) { ok = false; break; }
        hasta ??= r.data?.fecha_hasta;
        regs.push(...(r.data?.items || []).map(x => ({ ...x, _bitacora: 'RF-10' })));
        if ((r.data?.items || []).length < 50) break;
      }
      for (let p = 1; p <= 5 && desde; p++) {
        const r = await sb.req('GET', `/iot/auditoria?fecha_desde=${encodeURIComponent(desde)}&pagina=${p}&por_pagina=200`, { token: S });
        if (r.status !== 200) break;
        regs.push(...(r.data?.items || []).filter(x => Number(x.id_usuario) === idUsuario).map(x => ({ ...x, _bitacora: 'RF-63' })));
        if ((r.data?.items || []).length < 200) break;
      }
      return { regs, rf10: ok };
    };
    const auditar = async (caso, variante, id, actor, intento, etiqueta) => {
      if (!actor) return;
      let b = null, m = null;
      for (let k = 0; k < 3 && !m; k++) { if (k) await new Promise(r => setTimeout(r, 10000)); b = await buscar(actor.id_usuario); m = b.regs.find(r => registroIntento(r, intento).completo) || null; }
      // Testigo positivo: la bitácora RF-10 refleja eventos del propio RUN de este actor (su inicio de sesión).
      pre(caso, variante, 'testigo positivo: la bitácora RF-10 es consultable y refleja eventos del actor en este RUN', b.rf10 && b.regs.some(r => r._bitacora === 'RF-10'), b.rf10 ? 'sin eventos del RUN: la bitácora no es observable dentro del sandbox' : 'bitácora RF-10 no consultable');
      const parcial = !m && b.regs.find(r => registroIntento(r, intento).coincide);
      ev.aserciones.push({ herramienta: 'Ejecutor', caso, tipo: 'ASSERT', id, variante, nombre: `[${caso}][ASSERT][${id}][V:${variante}] ${etiqueta}`, ok: !!m, evidencia: b.rf10, error: m ? undefined : parcial ? 'existe un registro del intento sin fecha o sin motivo' : 'no hay registro del intento en las bitácoras' });
      ev.datos[`auditoria_${caso}`] = { registro: m ? { bitacora: m._bitacora, id: m.id_evento ?? null } : null, revisados: b.regs.length };
    };
    await auditar('TC-M03-258', 'GRANJA_AUDITORIA', 'API-258-03', { id_usuario: eng.id }, { id_usuario: eng.id, id_unidad: uB1.id }, 'el intento sobre la granja B queda registrado (usuario, unidad, fecha y motivo)');
    await auditar('TC-M03-260', 'EXPORTAR_AUDITORIA', 'API-260-03', actores.EXP, { id_usuario: actores.EXP?.id_usuario, id_unidad: null }, 'la exportación rechazada queda registrada (usuario, operación, fecha y motivo)');
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = ev.fase === 'ESCENARIOS' ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.dependencias.push(limpiar(e.message)); }
  finally {
    try {
      if (abierto) {
        const c = await sb.cerrar(dispositivo ? seriales.A : null);
        ev.sandbox.cierre = c; ev.sandbox.rollback = c.rollback;
        if (dispositivo && c.sonda_posterior === null) ev.dependencias.push('Rollback no confirmable: testigo auditoria.logs_dml no consultable.');
      }
    } catch (e) { ev.sandbox.rollback = false; ev.dependencias.push(limpiar(e.message)); }
    ev.veredicto = veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: ev.estado, rollback: !!ev.sandbox.rollback, aserciones: ev.aserciones, bloqueos: ev.bloqueos });
    ev.fin = new Date().toISOString(); guardar();
    fs.writeFileSync(path.join(out, nombreInforme(GRUPO, n)), limpiar(informe({ grupo: GRUPO, n, run, ev, casos: CASOS, extra: `\n258 y 261 no imponen código HTTP (la matriz no lo define); 260 exige HTTP 403.\n` })));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
