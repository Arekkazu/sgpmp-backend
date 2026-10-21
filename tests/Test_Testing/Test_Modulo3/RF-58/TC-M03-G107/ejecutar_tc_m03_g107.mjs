#!/usr/bin/env node
// TC-M03-207, 208 y 209 (RF-58 CA-7, Restricción 6; CU04 FA-01, Precondición 8): control de acceso
// por granja (BOLA, OWASP API1), por rol (OWASP API5) y registro en bitácora de los accesos denegados.
//
// Escenario CONSTRUIDO en el sandbox con APIs oficiales:
// - Granja A con acceso del Ingeniero de Campo y una unidad con sensor y lectura (su vista legítima).
// - Granja B sin acceso del Ingeniero, con una unidad, sensor, lectura y alerta activa: los datos
//   que no deben exponerse.
// - Rol sin permiso: la primera cuenta QA cuyo rol no tiene el permiso activo (recurso 33,
//   acción Leer), comprobado con GET /roles/{id_rol}/permisos (no con el propio dashboard).
// 207 y 208 se evalúan con Newman en ambas rutas del dashboard. 209 reutiliza esos mismos rechazos
// y consulta inmediatamente las bitácoras RF-10 (/auditoria/) e IoT (/iot/auditoria), con un
// testigo positivo: si la bitácora no refleja eventos del propio RUN, su ausencia no se interpreta.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  leerEnv, autorizar, version, carpetaResultados, runId, nombreInforme, argumentos, newmanModulo, sello, serialQa,
  sandbox, catalogos, construirUnidad, estadosActualesCompletos, cuerpoAlerta, correrNewman, redactor, informe,
  veredictoCasos, sintaxisColeccion, nombresDeTests, casoDeTexto, tipoDeTexto, consultaTestigoDispositivo,
} from './monitoreo_lib.mjs';

export const GRUPO = 'TC-M03-G107';
export const CASOS = ['TC-M03-207', 'TC-M03-208', 'TC-M03-209'];
export const RECURSO_MONITOREO = 33, ACCION_LEER = 2;
export const REQUERIDAS = {
  'TC-M03-207': ['API-207-01@QUERY', 'API-207-02@QUERY', 'API-207-01@RUTA', 'API-207-02@RUTA'],
  'TC-M03-208': ['API-208-01@QUERY', 'API-208-02@QUERY', 'API-208-01@RUTA', 'API-208-02@RUTA'],
  'TC-M03-209': ['API-209-01@ROL', 'API-209-02@GRANJA', 'API-209-03@UNIDAD'],
};
/** Cuentas QA candidatas para el rol sin permiso de lectura (se elige por sus permisos reales). */
export const CANDIDATAS_SIN_PERMISO = ['CONTADOR', 'REVISOR_FISCAL', 'EXTERNO_AGROFUSION', 'GESTOR_GRANJA', 'SUPERVISOR', 'VETERINARIO', 'PROD'];

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);

/** ¿El rol tiene el permiso activo de lectura sobre el monitoreo? null si la lista no es válida. */
export function tieneLectura(permisos) {
  if (!Array.isArray(permisos)) return null;
  return permisos.some(p => Number(p.id_recurso) === RECURSO_MONITOREO && Number(p.id_accion) === ACCION_LEER && p.es_activo === true);
}
/** Valores (recorrido profundo) de las claves que cumplen el patrón. */
export function valores(obj, patron, out = []) {
  if (obj && typeof obj === 'object') for (const [k, v] of Object.entries(obj)) { if (patron.test(k) && v !== null && typeof v !== 'object') out.push(v); valores(v, patron, out); }
  return out;
}
/**
 * Un registro de bitácora documenta un intento si identifica al usuario, la unidad solicitada,
 * trae fecha y un motivo del rechazo (campo de motivo/código o descripción de denegación).
 */
export function registroCoincide(r, intento) {
  const usuario = Number(r?.id_usuario) === intento.id_usuario || valores(r, /^id_usuario$/).map(Number).includes(intento.id_usuario);
  const unidad = valores(r, /infraestructura|unidad|entidad_afectada_id/i).map(String).includes(String(intento.id_unidad));
  const fecha = !!(r?.fecha_evento || r?.fecha_hora);
  const motivo = valores(r, /motivo|razon|raz[oó]n|codigo_error|error_code|reason/i).some(x => String(x).trim()) || /deneg|rechaz|no autoriz|sin permiso|forbidden/i.test(String(r?.descripcion || ''));
  return { coincide: usuario && unidad, completo: usuario && unidad && fecha && motivo };
}
/** Para cada intento busca un registro distinto y completo. */
export function evaluarBitacora(registros, intentos) {
  const usados = new Set();
  return intentos.map(i => {
    const idx = registros.findIndex((r, k) => !usados.has(k) && registroCoincide(r, i).completo);
    if (idx >= 0) usados.add(idx);
    const parcial = idx < 0 ? registros.find(r => registroCoincide(r, i).coincide) : null;
    return { ...i, registrado: idx >= 0, registro: idx >= 0 ? registros[idx] : null, incompleto: parcial ? 'existe un registro del intento sin fecha o sin motivo' : undefined };
  });
}

function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const texto = JSON.stringify(col);
  const fuente = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const futuras = { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] };
  ck('Matriz: TC-M03-207, 208 y 209', CASOS.join() === 'TC-M03-207,TC-M03-208,TC-M03-209');
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza la ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, futuras).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ...futuras, ambiente: 'DEV' }).ok);
  ck('Cuentas de preparación (Administrador) e Ingeniero resueltas', ['SETUP', 'ENG'].every(r => !!v[`QA_${r}_EMAIL`] && !!(v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD)) && !!v.QA_SANDBOX_SECRET);
  ck('Al menos una cuenta candidata para el rol sin permiso', CANDIDATAS_SIN_PERMISO.some(r => !!v[`QA_${r}_EMAIL`]));
  ck('Colección Postman v2.1 con ambas rutas del dashboard (query y /dashboard/{id})', /v2\.1\.0/.test(col.info?.schema || '') && col.item.some(i => i.request.url.path.length === 3 && i.request.url.query?.length) && col.item.some(i => i.request.url.path.length === 4));
  ck('Aserciones API de 207 y 208 en la colección', [...REQUERIDAS['TC-M03-207'], ...REQUERIDAS['TC-M03-208']].every(k => texto.includes(`[${k.split('@')[0]}]`)));
  ck('Cada petición declara su caso', col.item.every(i => casoDeTexto(i.name)));
  ck('Cada test de la colección declara PRE, ASSERT o INFO', nombresDeTests(col).every(n => tipoDeTexto(n) !== null));
  const vars = new Set([...texto.matchAll(/\{\{([a-z0-9_]+)\}\}/g)].map(x => x[1]));
  ck('Variables Newman resueltas por el ejecutor', [...vars].every(x => ['base_url', 'run_id', 'sandbox_secret', 'token_eng', 'token_sin_permiso', 'id_a', 'id_b'].includes(x)) && ['finca_a', 'finca_b', 'sensor_a', 'sensor_b', 'alerta_b', 'nombres_a', 'nombres_b'].every(x => fuente.includes(`${x}:`)));
  ck('Barrera propia de Newman (nivel colección)', (col.event || []).some(e => e.listen === 'prerequest' && e.script.exec.join('\n').includes('BLOQUEO_G107')));
  try { sintaxisColeccion(col); ck('Sintaxis Postman (colección e ítems)', true); } catch { ck('Sintaxis Postman (colección e ítems)', false); }
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis librería', spawnSync(process.execPath, ['--check', path.join(DIR, 'monitoreo_lib.mjs')]).status === 0);
  ck('Testigo de aislamiento sin RLS', /FROM auditoria\.logs_dml/.test(consultaTestigoDispositivo('QAAUTO-G107-1')));
  ck('Sin peticiones concurrentes al sandbox', !new RegExp(['Promise', 'all'].join('\\.')).test(fuente));
  ck('209 con testigo positivo de la bitácora', /testigo positivo/.test(fuente));
  ck('Veredicto: rechazo con evidencia; PRE de la ruta lo invalida; sin 209-03 no hay APROBADO', (() => {
    const todas = Object.entries(REQUERIDAS).flatMap(([caso, ks]) => ks.map(k => ({ caso, tipo: 'ASSERT', id: k.split('@')[0], variante: k.split('@')[1], ok: true, evidencia: true })));
    const base = { casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true };
    const r = veredictoCasos({ ...base, aserciones: todas.map(a => a.id === 'API-207-01' && a.variante === 'RUTA' ? { ...a, ok: false } : a) });
    const b = veredictoCasos({ ...base, aserciones: [...todas.map(a => a.id === 'API-207-01' && a.variante === 'RUTA' ? { ...a, ok: false } : a), { caso: 'TC-M03-207', tipo: 'PRE', variante: null, ok: false }] });
    const c = veredictoCasos({ ...base, aserciones: todas.filter(a => a.variante !== 'UNIDAD') });
    return r.casos['TC-M03-207'] === 'RECHAZADO' && b.casos['TC-M03-207'] === 'BLOQUEADO' && c.casos['TC-M03-209'] === 'BLOQUEADO' && c.casos['TC-M03-207'] === 'APROBADO';
  })());
  ck('Sin carpetas RESULTADOS de construcción', !fs.existsSync(path.join(DIR, 'RESULTADOS')) && !fs.readdirSync(DIR).some(x => /^EvaluacionV\d+$/.test(x)));
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD].filter(x => x?.length > 4);
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), COLLECTION, path.join(DIR, 'monitoreo_lib.mjs')].every(f => !secretos.some(s => fs.readFileSync(f, 'utf8').includes(s))));
  ck('Pruebas unitarias locales', spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g107.mjs')], { encoding: 'utf8' }).status === 0);
  try { newmanModulo(ROOT); ck('Newman disponible', true); } catch { ck('Newman disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G107 local ${checks.filter(x => x[1]).length}/${checks.length}`);
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
  const seriales = { A: serialQa(v, 'G107', marca, 'A'), B: serialQa(v, 'G107', marca, 'B') };
  const letras = s => s.replace(/\d/g, d => 'abcdefghij'[Number(d)]);
  const ev = { grupo: GRUPO, rf: 'RF-58', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, dependencias: [], bloqueos: {}, aserciones: [], sandbox: {}, datos: {}, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD, ...CANDIDATAS_SIN_PERMISO.map(r => v[`QA_${r}_PASSWORD`]), ...Object.values(seriales)];
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
    // Ancla temporal del servidor (no del reloj del equipo QA) para buscar en la bitácora.
    const ancla = await sb.req('GET', '/auditoria/?tamano=1', { token: S });
    const desde = ancla.status === 200 || ancla.status === 206 ? ancla.data?.fecha_hasta : null;
    const eng = await sb.login(v.QA_ENG_EMAIL, v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, 'Ingeniero', /ingeniero/i);
    secretos.push(eng.token); limpiar = redactor(secretos);

    // ---- PREPARACIÓN --------------------------------------------------------------------------
    ev.fase = 'PREPARACION';
    const cat = await catalogos(sb, S);
    const finca = async (etiqueta, idUsuario) => sb.need(await sb.req('POST', '/configuracion/fincas', { token: S, body: { nombre: letras(`QA Monitoreo G Ciento Siete ${etiqueta} ${marca}`), ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'QA', latitud: 2.9273, longitud: -75.2819 }, tamano_h: 1, id_usuario: idUsuario } }), 201, `Crear granja ${etiqueta}`).id_finca;
    const fincaA = await finca('A', eng.id), fincaB = await finca('B', setup.id);
    const unidadA = await construirUnidad(sb, { tok: S, cat, finca: fincaA, run, nombreUnidad: `QA G107 ${marca} UNIDAD A`, serial: seriales.A, nombres: [`QA G107 ${marca} SENSOR A`], alCrearDispositivo: async () => { dispositivo = true; ev.sandbox.aislamiento = await sb.aislamiento(seriales.A); } });
    const unidadB = await construirUnidad(sb, { tok: S, cat, finca: fincaB, run, nombreUnidad: `QA G107 ${marca} UNIDAD B`, serial: seriales.B, nombres: [`QA G107 ${marca} SENSOR B`] });
    const sB = unidadB.sensores[0];
    const alertaB = await sb.req('POST', '/iot/alertas', { body: cuerpoAlerta({ idDispositivo: unidadB.id_dispositivo, idSensor: sB.id, serial: seriales.B, idTelemetria: sB.id_telemetria, severidad: 'MODERADO' }) });
    const nombresB = { finca: letras(`QA Monitoreo G Ciento Siete B ${marca}`), unidad: unidadB.nombre, sensor: sB.nombre };
    const nombresA = { finca: letras(`QA Monitoreo G Ciento Siete A ${marca}`), unidad: unidadA.nombre, sensor: unidadA.sensores[0].nombre };
    ev.datos = { granja_A: { id: fincaA, unidad: unidadA.id, sensor: unidadA.sensores[0].id, acceso: 'Ingeniero de Campo' }, granja_B: { id: fincaB, unidad: unidadB.id, sensor: sB.id, id_alerta: alertaB.data?.id_alerta ?? null, acceso: 'solo la cuenta de preparación' } };
    // Precondiciones de 207: el Ingeniero está autorizado en A y no en B; B es un identificador válido con datos.
    const fincasEng = new Set((sb.need(await sb.req('GET', '/configuracion/fincas', { token: eng.token }), 200, 'Fincas del Ingeniero').items || []).map(f => Number(f.id_finca)));
    pre('TC-M03-207', null, 'el Ingeniero está autorizado para la granja A y no para la granja B', fincasEng.has(Number(fincaA)) && !fincasEng.has(Number(fincaB)), `granjas visibles: ${[...fincasEng].length}; A ${fincasEng.has(Number(fincaA))}; B ${fincasEng.has(Number(fincaB))}`);
    const valida = await sb.req('GET', `/configuracion/infraestructuras/${unidadB.id}`, { token: S });
    const eB = await estadosActualesCompletos(sb, unidadB);
    pre('TC-M03-207', null, 'la unidad de la granja B es un identificador válido con sensor, lectura y alerta activa', valida.status === 200 && eB.ok && alertaB.status === 201, `infraestructura HTTP ${valida.status}; estado actual ${eB.encontrados}; alerta HTTP ${alertaB.status}`);
    // Rol sin permiso de lectura, elegido por sus permisos reales.
    let sinPermiso = null;
    for (const r of CANDIDATAS_SIN_PERMISO.filter(x => v[`QA_${x}_EMAIL`] && (v[`QA_${x}_PASSWORD`] || v.QA_COMMON_PASSWORD))) {
      const l = await sb.req('POST', '/sesiones/', { body: { correo_electronico: v[`QA_${r}_EMAIL`], contrasena: v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD } });
      if (l.status !== 200 || !l.data?.token) continue;
      secretos.push(l.data.token); limpiar = redactor(secretos);
      const me = await sb.req('GET', '/usuarios/me', { token: l.data.token });
      const idRol = me.data?.id_rol;
      const permisos = idRol ? await sb.req('GET', `/roles/${idRol}/permisos`, { token: S }) : null;
      if (tieneLectura(permisos?.status === 200 ? permisos.data : null) === false) { sinPermiso = { cuenta: r, token: l.data.token, id_usuario: me.data.id_usuario, id_rol: idRol, rol: me.data.nombre_rol }; break; }
    }
    pre('TC-M03-208', null, 'cuenta QA cuyo rol no tiene el permiso de lectura del monitoreo (recurso 33)', !!sinPermiso, 'ninguna cuenta candidata cumple: requiere una cuenta QA con ese perfil');
    ev.datos.rol_sin_permiso = sinPermiso ? { cuenta: sinPermiso.cuenta, id_rol: sinPermiso.id_rol, rol: sinPermiso.rol } : null;

    // ---- ESCENARIOS 207 y 208 (Newman) -----------------------------------------------------------
    ev.fase = 'ESCENARIOS'; guardar();
    const vars = { base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, autorizado_run: 'SI', token_eng: eng.token, token_sin_permiso: sinPermiso?.token ?? '', id_a: unidadA.id, id_b: unidadB.id, finca_a: fincaA, finca_b: fincaB, sensor_a: unidadA.sensores[0].id, sensor_b: sB.id, alerta_b: alertaB.data?.id_alerta ?? '', nombres_a: JSON.stringify(Object.values(nombresA)), nombres_b: JSON.stringify(Object.values(nombresB)) };
    const nw = await correrNewman(newman, JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), vars, { limpiar });
    ev.aserciones.push(...nw.aserciones); ev.respuestas = nw.muestras;
    for (const e of nw.errores) { ev.dependencias.push(e.mensaje); (ev.bloqueos[e.caso || 'TC-M03-207'] ??= []).push(e.mensaje); }

    // ---- 209: bitácora de los mismos rechazos, consultada inmediatamente -------------------------
    const denegado = nombre => nw.muestras.filter(m => m.peticion === nombre && m.http >= 400 && m.http < 500).length;
    const intentos = [
      ...Array.from({ length: denegado('[TC-M03-208][V:QUERY] rol sin permiso, ruta con id_infraestructura') + denegado('[TC-M03-208][V:RUTA] rol sin permiso, ruta /dashboard/{id}') }, () => ({ tipo: 'ROL', id_usuario: sinPermiso?.id_usuario, id_unidad: unidadA.id })),
      ...Array.from({ length: denegado('[TC-M03-207][V:QUERY] granja ajena, ruta con id_infraestructura') + denegado('[TC-M03-207][V:RUTA] granja ajena, ruta /dashboard/{id}') }, () => ({ tipo: 'GRANJA', id_usuario: eng.id, id_unidad: unidadB.id })),
    ];
    pre('TC-M03-209', 'ROL', 'hubo rechazos por rol sin permiso que registrar', intentos.some(i => i.tipo === 'ROL'), 'no se produjo ningún rechazo por rol (ver 208)');
    pre('TC-M03-209', 'GRANJA', 'hubo rechazos por granja ajena que registrar', intentos.some(i => i.tipo === 'GRANJA'), 'el acceso a la granja ajena no fue rechazado con un error (ver 207)');
    pre('TC-M03-209', 'UNIDAD', 'escenario «unidad no asignada» definido', false, 'REQUIERE DECISIÓN QA: el producto delimita el alcance por granja (usuarios_fincas) y no existe asignación de unidades a usuarios, así que «unidad no asignada» no se distingue de «granja ajena».');
    const registros = [];
    let consultable = !!desde;
    for (const idUsuario of [...new Set([eng.id, sinPermiso?.id_usuario].filter(Boolean))]) {
      let hasta = null;
      for (let p = 1; p <= 10; p++) {
        const r = await sb.req('GET', `/auditoria/?id_usuario=${idUsuario}&fecha_desde=${encodeURIComponent(desde)}${hasta ? `&fecha_hasta=${encodeURIComponent(hasta)}` : ''}&pagina=${p}&tamano=50`, { token: S });
        if (![200, 206].includes(r.status)) { consultable = false; break; }
        hasta ??= r.data?.fecha_hasta;
        registros.push(...(r.data?.items || []).map(x => ({ ...x, _bitacora: 'RF-10' })));
        if ((r.data?.items || []).length < 50) break;
      }
    }
    // Testigo positivo: la bitácora RF-10 refleja, dentro del RUN, el inicio de sesión del Ingeniero.
    const testigo = registros.some(r => r._bitacora === 'RF-10' && Number(r.id_usuario) === eng.id);
    pre('TC-M03-209', null, 'testigo positivo: la bitácora RF-10 es consultable y refleja eventos del propio RUN (inicio de sesión del Ingeniero)', consultable && testigo, consultable ? 'sin eventos del RUN: la bitácora no es observable dentro del sandbox; su ausencia no se interpreta' : 'bitácora RF-10 no consultable');
    for (let p = 1; p <= 5 && desde; p++) {
      const r = await sb.req('GET', `/iot/auditoria?fecha_desde=${encodeURIComponent(desde)}&pagina=${p}&por_pagina=200`, { token: S });
      if (r.status !== 200) { ev.dependencias.push(`Bitácora IoT no consultable (HTTP ${r.status}); se evalúa solo RF-10.`); break; }
      registros.push(...(r.data?.items || []).map(x => ({ ...x, _bitacora: 'IoT' })));
      if ((r.data?.items || []).length < 200) break;
    }
    const resultado = evaluarBitacora(registros, intentos);
    ev.datos.bitacora = { desde, registros_revisados: registros.length, intentos: resultado.map(x => ({ tipo: x.tipo, registrado: x.registrado, bitacora: x.registro?._bitacora ?? null, incompleto: x.incompleto })) };
    for (const [tipo, id] of [['ROL', 'API-209-01'], ['GRANJA', 'API-209-02']]) {
      const propios = resultado.filter(x => x.tipo === tipo);
      if (!propios.length) continue;
      const faltan = propios.filter(x => !x.registrado);
      ev.aserciones.push({ herramienta: 'Ejecutor', caso: 'TC-M03-209', tipo: 'ASSERT', id, variante: tipo, nombre: `[TC-M03-209][ASSERT][${id}][V:${tipo}] cada rechazo (${tipo === 'ROL' ? 'rol sin permiso' : 'granja ajena'}) queda en bitácora con fecha, usuario, unidad y motivo: ${propios.length - faltan.length}/${propios.length}`, ok: !faltan.length, evidencia: consultable, error: faltan.length ? `${faltan.length} intento(s) sin registro completo${faltan.some(x => x.incompleto) ? ' (hay registros sin fecha o sin motivo)' : ''}` : undefined });
    }
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
    fs.writeFileSync(path.join(out, nombreInforme(GRUPO, n)), limpiar(informe({ grupo: GRUPO, n, run, ev, casos: CASOS, extra: `\nEl código HTTP de 207 se registra como información: la matriz no lo fija; se exige denegación sin exposición de datos de la granja B.\n` })));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
