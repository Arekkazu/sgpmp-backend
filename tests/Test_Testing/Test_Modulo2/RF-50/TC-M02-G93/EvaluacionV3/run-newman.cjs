// TC-M02-G93 V3 — RF-50 / CU12. Reglas negativas de datos consolidados, con la identidad tecnica M06
// como consumidor:
//   TC-M02-155   tipo_dato sin scope autorizado            -> 403 SCOPE_TIPO_DATO_NO_AUTORIZADO
//   TC-M02-156-A fecha_inicio > fecha_fin                  -> 400 PARAMETROS_INVALIDOS
//   TC-M02-156-B rango futuro                              -> 400 PARAMETROS_INVALIDOS
//   TC-M02-157   0 metricas PESO en el rango (NIC-41)      -> 422 METRICAS_PESO_INSUFICIENTES
//   Verificacion complementaria: advertencia de peso fuera del rango.
//
// ADAPTACION RESPECTO A V1/V2
// ---------------------------
// V1 se ejecuto con un consumidor humano porque no existian la identidad M06 ni el scope granular
// por tipo_dato; TC-155 y TC-157 quedaron BLOQUEADOS. V2 no se ejecuto. Se conservan de V1 el
// endpoint, el fixture de referencia, el patron del constructor de coleccion y la regla de no
// exposicion de datos consolidados en los rechazos. La adaptacion descubre la identidad tecnica y
// los recursos de scope, satisface la unica precondicion que faltaba (alcance de M06 sobre la finca
// del activo, por el endpoint oficial) y ejecuta los mismos casos con el consumidor correcto.
//
// El caso no cambia: mismo actor tecnico, mismo endpoint, mismos tipo_dato, mismos codigos esperados
// y mismo oraculo. Solo se satisface una precondicion legitima.
//
// Fases:
//   G93_FASE=preflight  contrato, identidad, provision, fixture y rangos (sin RUN_ID)
//   G93_FASE=preparar   asigna a M06 la finca del activo por PUT oficial y verifica el alcance
//   G93_FASE=oficial    requiere G93_V3_RUN_ID: unica carpeta, ejecuta los casos
//   G93_FASE=cierre     consolida seguridad y estado de Git en la misma evidencia
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const BASE_TEST = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const RUTA = '/activos-biologicos/{id_activo}/datos-consolidados';
const M06_EMAIL = process.env.M06_EMAIL || 'integracion.m06.test@pecuaria.co';
const ACTIVO_PREFERIDO = Number(process.env.G93_ID_ACTIVO || 279);
const RECURSOS_SCOPE = {
  eventos: 'datos_analiticos_eventos', fases: 'datos_analiticos_fases',
  estado: 'datos_analiticos_estado', metricas: 'datos_analiticos_metricas',
};
const RECURSO_GENERAL = 'activos_biologicos';
const RECURSO_USUARIOS = 'usuarios';
const ACCION_LEER = 2;
const ACCION_ACTUALIZAR = 3;

const PRUEBAS = path.resolve(__dirname, '..', '..', '..', '..', '..', '..', '..');
const FRONT = path.join(PRUEBAS, 'SGPMP-FRONT-END-PWA');
const BACK = path.join(PRUEBAS, 'sgpmp-backend');

const clean = (s) => {
  s = String(s);
  for (const v of ['M06_PASSWORD', 'QA_ADMIN_PASSWORD']) if (process.env[v]) s = s.split(process.env[v]).join('[REDACTED]');
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+(?!\[|\{\{)[A-Za-z0-9_.\-]+/g, 'Bearer [REDACTED]');
};
const norm = (s) => String(s == null ? '' : s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const f10 = (d) => d.toISOString().slice(0, 10);
const masDias = (base, n) => f10(new Date(new Date(base).getTime() + n * 86400000));

async function http(url, { metodo = 'GET', token, cuerpo } = {}) {
  const t0 = Date.now();
  try {
    const r = await fetch(url, { method: metodo, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined, redirect: 'manual', signal: AbortSignal.timeout(45000) });
    let body = null; try { body = await r.json(); } catch { /* sin JSON */ }
    return { status: r.status, body, ms: Date.now() - t0 };
  } catch (e) { return { status: 'ERR', error: clean(e.message), ms: Date.now() - t0 }; }
}

const login = (base, correo, pass) => http(base + '/sesiones/', { metodo: 'POST', cuerpo: { correo_electronico: correo, contrasena: pass } });

async function contratoDe(base) {
  const r = await http(base + '/openapi.json');
  const op = r.body?.paths?.[RUTA]?.get;
  const par = Object.fromEntries((op?.parameters || []).map((p) => [p.name, p]));
  const resp = Object.keys(op?.responses || {});
  return { openapi: r.status, endpoint: Boolean(op),
    parametros: ['tipo_dato', 'fecha_inicio', 'fecha_fin', 'pagina', 'page_size'].filter((n) => n in par),
    respuestas: resp, declara_400: resp.includes('400'), declara_403: resp.includes('403'), declara_422: resp.includes('422'),
    tipo_dato_admite: par.tipo_dato?.schema?.description ?? null,
    put_fincas: Boolean(r.body?.paths?.['/usuarios/{id_usuario}/fincas']?.put) };
}

// Provision del ambiente: rol, recursos de scope, permisos e identidad. Observador administrativo de
// solo lectura; no es el consumidor del caso.
async function provision(base, tokenAdmin) {
  const out = {};
  const roles = await http(base + '/roles/', { token: tokenAdmin });
  const listaRoles = Array.isArray(roles.body) ? roles.body : (roles.body?.items || roles.body?.registros || []);
  out.rol_m06 = listaRoles.map((r) => ({ id_rol: r.id_rol ?? r.id, nombre: r.nombre ?? r.nombre_rol }))
    .find((r) => /integracion\s*m06/.test(norm(r.nombre))) ?? null;

  const rec = await http(base + '/roles/catalogo/recursos', { token: tokenAdmin });
  const listaRec = Array.isArray(rec.body) ? rec.body : (rec.body?.items || rec.body?.registros || []);
  const porNombre = (n) => listaRec.find((x) => norm(x.nombre ?? x.nombre_recurso) === norm(n));
  const id = (n) => { const r = porNombre(n); return r ? (r.id_recurso ?? r.id) : null; };
  out.recursos = { general: id(RECURSO_GENERAL), usuarios: id(RECURSO_USUARIOS),
    scope: Object.fromEntries(Object.entries(RECURSOS_SCOPE).map(([k, n]) => [k, id(n)])) };
  out.recursos.scope_desplegado = Object.values(out.recursos.scope).every(Boolean);

  const permisosDeRol = async (idRol) => {
    const p = await http(base + `/roles/${idRol}/permisos`, { token: tokenAdmin });
    const l = Array.isArray(p.body) ? p.body : (p.body?.items || p.body?.permisos || p.body?.registros || []);
    return { lista: l, tiene: (idRecurso, accion) => l.some((x) => {
      const r = x.id_recurso ?? x.recurso?.id_recurso;
      const a = x.id_accion ?? x.accion?.id_accion;
      return Number(r) === Number(idRecurso) && Number(a) === Number(accion);
    }) };
  };
  if (out.rol_m06) {
    const p = await permisosDeRol(out.rol_m06.id_rol);
    out.permisos_m06 = { total: p.lista.length,
      general_read: out.recursos.general ? p.tiene(out.recursos.general, ACCION_LEER) : null,
      scopes: Object.fromEntries(Object.entries(out.recursos.scope).map(([k, r]) => [k, r ? p.tiene(r, ACCION_LEER) : null])) };
  }

  const consultar = async (qs) => {
    const r = await http(base + '/usuarios/admin?' + qs, { token: tokenAdmin });
    const l = r.body?.registros || r.body?.items || (Array.isArray(r.body) ? r.body : []);
    return l.map((u) => ({ id_usuario: u.id_usuario, correo_electronico: u.correo_electronico,
      nombre_rol: u.nombre_rol, id_rol: u.id_rol, estado_cuenta: u.estado_cuenta }));
  };
  const hallados = await consultar(`correo=${encodeURIComponent(M06_EMAIL)}&pagina=1&tamano=50`);
  const exacto = hallados.find((u) => norm(u.correo_electronico) === norm(M06_EMAIL)) ?? null;
  out.usuario_m06 = exacto;
  out.m06_existe = Boolean(exacto);
  out.m06_activo = exacto ? exacto.estado_cuenta === 'Activo' : null;
  return out;
}

// Fixture y su finca. Se lee con el observador administrativo.
async function fixture(base, tokenAdmin, idActivo) {
  const det = await http(base + `/activos-biologicos/${idActivo}`, { token: tokenAdmin });
  if (det.status !== 200) return { id_activo_biologico: idActivo, existe: false, status: det.status };
  const ev = await http(base + `/activos-biologicos/${idActivo}/eventos`, { token: tokenAdmin });
  const pesos = (ev.body?.eventos || [])
    .filter((e) => e.crecimiento && /peso/i.test(String(e.crecimiento.tipo_medicion ?? '')))
    .map((e) => ({ id_eventos: e.id_eventos, fecha: String(e.fecha).slice(0, 10),
      valor: String(e.crecimiento.valor_medicion ?? e.crecimiento.nuevo_peso_promedio), unidad: e.crecimiento.unidad_medida }))
    .sort((a, b) => (a.fecha < b.fecha ? -1 : 1));
  let idFinca = null; let infra = null;
  if (det.body.id_infraestructura) {
    const i = await http(base + `/configuracion/infraestructuras/${det.body.id_infraestructura}`, { token: tokenAdmin });
    if (i.status === 200) { idFinca = i.body.id_finca ?? null; infra = { id_infraestructura: i.body.id_infraestructura, nombre: i.body.nombre, id_finca: idFinca }; }
  }
  return { id_activo_biologico: idActivo, existe: true, identificador: det.body.identificador, tipo: det.body.tipo,
    nombre_estado: det.body.nombre_estado, fecha_inicio_ciclo: String(det.body.fecha_inicio_ciclo ?? '').slice(0, 10),
    id_infraestructura: det.body.id_infraestructura, infraestructura: infra, id_finca: idFinca,
    total_eventos: ev.body?.total ?? null, mediciones_peso: pesos };
}

// Rangos derivados de los datos reales; nunca literales fijos.
function rangos(fx, hoy) {
  const pesos = fx.mediciones_peso || [];
  const ciclo = fx.fecha_inicio_ciclo || '2000-01-01';
  const dentro = (ini, finExcl) => pesos.filter((p) => p.fecha >= ini && p.fecha < finExcl);
  let nic = null;
  if (pesos.length && ciclo < pesos[0].fecha) {
    const c = { inicio: ciclo, fin: masDias(pesos[0].fecha, -1) };
    if (c.inicio < c.fin && c.fin < hoy && dentro(c.inicio, masDias(c.fin, 1)).length === 0) nic = c;
  }
  let obs = null;
  if (pesos.length >= 2) {
    const ultimo = pesos[pesos.length - 1];
    const ini = pesos[0].fecha;
    const fin = masDias(ultimo.fecha, -1);
    if (ini <= fin && fin < hoy && dentro(ini, masDias(fin, 1)).length >= 1 && ultimo.fecha > fin) obs = { inicio: ini, fin };
  }
  return {
    nic41: nic, pesos_dentro_de_nic41: nic ? dentro(nic.inicio, masDias(nic.fin, 1)).length : null,
    observacion_392: obs, pesos_dentro_de_observacion: obs ? dentro(obs.inicio, masDias(obs.fin, 1)).length : null,
    peso_mas_reciente: pesos.length ? pesos[pesos.length - 1].fecha : null,
    invertido: { inicio: masDias(hoy, -10), fin: masDias(hoy, -30) },
    futuro: { inicio: masDias(hoy, 1), fin: masDias(hoy, 2) },
    hoy_observado: hoy, pesos_totales: pesos.length,
  };
}

// Alcance efectivo de M06 sobre el activo del caso.
async function alcance(base, tokenM06, idActivo) {
  const me = await http(base + '/usuarios/me', { token: tokenM06 });
  const listado = await http(base + '/activos-biologicos?pagina=1&por_pagina=50', { token: tokenM06 });
  const control = await http(base + `/activos-biologicos/${idActivo}/datos-consolidados?tipo_dato=metricas`, { token: tokenM06 });
  return {
    fincas_en_el_perfil: (me.body?.fincas || []).map((f) => (typeof f === 'object' ? f.id_finca : f)),
    activos_visibles: listado.body?.total_registros ?? (listado.body?.registros || []).length,
    control_positivo: { status: control.status, error_code: control.body?.error_code ?? null,
      id_activo_devuelto: control.body?.id_activo_biologico ?? null, tiene_metricas: Boolean(control.body?.metricas_actuales) },
    ve_el_activo: control.status === 200,
  };
}

function estadoGit() {
  const out = {};
  for (const [nombre, cwd] of [['frontend', FRONT], ['backend', BACK]]) {
    const g = (...a) => { try { return execFileSync('git', a, { cwd, encoding: 'utf8' }).trim(); } catch (e) { return 'ERROR: ' + String(e.message).slice(0, 120); } };
    g('fetch', 'origin');
    out[nombre] = { rama: g('branch', '--show-current'), head: g('rev-parse', 'HEAD'),
      status: g('status', '--short') || '(limpio)', indice: g('diff', '--cached', '--stat') || '(vacio)',
      head_vs_origin_test: g('rev-list', '--left-right', '--count', 'HEAD...origin/test') };
  }
  return out;
}

function gate({ contrato, prov, actorM06, fx, rg, alc }) {
  const v = [];
  const ok = (c, t) => v.push({ condicion: t, cumple: Boolean(c) });
  ok(contrato?.endpoint, 'OpenAPI RF-50 valido');
  ok(contrato?.declara_400 && contrato?.declara_403 && contrato?.declara_422, 'contrato declara 400, 403 y 422');
  ok(actorM06?.id_usuario, 'M06 autentica');
  ok(actorM06 && /integracion\s*m06/.test(norm(actorM06.nombre_rol)), 'rol M06 confirmado');
  ok(actorM06?.estado_cuenta === 'Activo', 'cuenta M06 activa');
  ok(prov?.permisos_m06?.general_read, 'permiso general READ confirmado');
  ok(prov?.permisos_m06?.scopes?.metricas === true, 'scope metricas = SI');
  ok(prov?.permisos_m06?.scopes?.eventos === false, 'scope eventos = NO');
  ok(fx?.existe, 'activo existe');
  ok(fx?.id_finca != null, 'finca del activo identificada');
  ok(alc?.fincas_asignadas?.includes(fx?.id_finca), 'finca asignada a M06 por el endpoint oficial');
  ok(alc?.ve_el_activo, 'M06 ve el activo');
  ok(alc?.control_positivo?.status === 200, 'control positivo metricas = HTTP 200');
  ok(rg?.nic41 && rg.pesos_dentro_de_nic41 === 0, 'rango NIC-41 con 0 metricas PESO confirmado');
  ok(rg?.invertido?.inicio > rg?.invertido?.fin, 'fechas invertidas preparadas');
  ok(rg?.futuro?.inicio > rg?.hoy_observado && rg?.futuro?.inicio < rg?.futuro?.fin, 'fechas futuras preparadas');
  ok(rg?.observacion_392 && rg.pesos_dentro_de_observacion >= 1, 'rango de la verificacion complementaria preparado');
  return { checklist: v, completo: v.every((x) => x.cumple) };
}

// --------------------------------------------------------------- Contexto compartido de fases
async function contexto() {
  const health = (await http(BASE_TEST + '/health')).status;
  const contrato = await contratoDe(BASE_TEST);
  if (!process.env.QA_ADMIN_EMAIL || !process.env.QA_ADMIN_PASSWORD) throw Error('Se requiere una cuenta administrativa autorizada para descubrir la provision y preparar el alcance');
  const ra = await login(BASE_TEST, process.env.QA_ADMIN_EMAIL, process.env.QA_ADMIN_PASSWORD);
  if (!ra.body?.token) throw Error('La cuenta administrativa no autentico: ' + ra.status);
  const tokenAdmin = ra.body.token;
  const prov = await provision(BASE_TEST, tokenAdmin);
  const fx = await fixture(BASE_TEST, tokenAdmin, ACTIVO_PREFERIDO);
  const rg = fx.existe ? rangos(fx, f10(new Date())) : null;
  if (!process.env.M06_PASSWORD) throw Error('PRECONDICION PENDIENTE — credencial tecnica M06 no suministrada');
  const rm = await login(BASE_TEST, M06_EMAIL, process.env.M06_PASSWORD);
  if (!rm.body?.token) throw Error('La identidad tecnica M06 no autentico: ' + JSON.stringify({ status: rm.status, error_code: rm.body?.error_code }));
  const tokenM06 = rm.body.token;
  const me = await http(BASE_TEST + '/usuarios/me', { token: tokenM06 });
  const actorM06 = { id_usuario: me.body?.id_usuario, correo_electronico: me.body?.correo_electronico,
    id_rol: me.body?.id_rol, nombre_rol: me.body?.nombre_rol, estado_cuenta: me.body?.estado_cuenta };
  const alc = await alcance(BASE_TEST, tokenM06, ACTIVO_PREFERIDO);
  // La asignacion de fincas se verifica en la fuente autoritativa: el detalle administrativo del
  // usuario. `/usuarios/me` no refleja las asociaciones de esta identidad, aunque el alcance
  // efectivo si las aplica.
  if (prov.usuario_m06?.id_usuario) {
    const d = await http(BASE_TEST + `/usuarios/${prov.usuario_m06.id_usuario}/detalle`, { token: tokenAdmin });
    alc.fincas_asignadas = (d.body?.fincas || []).map((f) => (typeof f === 'object' ? f.id_finca : f)).filter((x) => x != null);
  } else alc.fincas_asignadas = [];
  return { health, contrato, tokenAdmin, prov, fx, rg, tokenM06, actorM06, alc };
}

// ---------------------------------------------------------------------------------- PREFLIGHT
async function preflight() {
  const c = await contexto();
  const g = gate(c);
  const salida = { fase: 'preflight', fecha: new Date().toISOString(), git: estadoGit(),
    health: c.health, contrato: c.contrato, provision: c.prov, actor_m06: c.actorM06,
    fixture: c.fx, rangos: c.rg, alcance: c.alc, gate: g };
  const destino = process.env.G93_PREFLIGHT_OUT || path.join(require('os').tmpdir(), 'g93-v3-preflight.json');
  fs.writeFileSync(destino, clean(JSON.stringify(salida, null, 2)));
  console.log('health', c.health, '| contrato', JSON.stringify({ endpoint: c.contrato.endpoint, respuestas: c.contrato.respuestas.join(','), put_fincas: c.contrato.put_fincas }));
  console.log('rol M06', JSON.stringify(c.prov.rol_m06), '| usuario', JSON.stringify(c.prov.usuario_m06));
  console.log('permisos M06', JSON.stringify(c.prov.permisos_m06));
  console.log('fixture', JSON.stringify({ id: c.fx.id_activo_biologico, ident: c.fx.identificador, estado: c.fx.nombre_estado, ciclo: c.fx.fecha_inicio_ciclo, infra: c.fx.id_infraestructura, finca: c.fx.id_finca, pesos: (c.fx.mediciones_peso || []).map((p) => p.fecha) }));
  console.log('rangos', JSON.stringify(c.rg));
  console.log('alcance M06', JSON.stringify(c.alc));
  console.log('GATE completo:', g.completo);
  g.checklist.filter((x) => !x.cumple).forEach((x) => console.log('   FALTA:', x.condicion));
  console.log('\nPreflight ->', destino);
}

// ----------------------------------------------------------------------------------- PREPARAR
// Unica preparacion permitida: dar a M06 alcance sobre la finca del activo, por el endpoint oficial
// y preservando cualquier finca activa preexistente. No es el oraculo del caso.
async function preparar() {
  const c = await contexto();
  if (!c.fx.existe || c.fx.id_finca == null) throw Error('No se pudo identificar la finca del activo del fixture');
  const idUsuario = c.prov.usuario_m06?.id_usuario;
  if (!idUsuario) throw Error('No se descubrio el id de la identidad tecnica M06');

  // Permiso del ejecutor sobre Usuarios/UPDATE, confirmado antes de escribir.
  const perm = await http(BASE_TEST + '/sesiones/me/permisos', { token: c.tokenAdmin });
  const lista = Array.isArray(perm.body) ? perm.body : (perm.body?.items || perm.body?.permisos || perm.body?.registros || []);
  const puedeActualizarUsuarios = lista.some((p) => {
    const r = p.id_recurso ?? p.recurso?.id_recurso;
    const a = p.id_accion ?? p.accion?.id_accion;
    return Number(r) === Number(c.prov.recursos.usuarios) && Number(a) === ACCION_ACTUALIZAR;
  });
  if (!puedeActualizarUsuarios) throw Error('El ejecutor no tiene permiso de actualizacion sobre Usuarios; no se prepara el alcance');

  // Conjunto completo: el endpoint reemplaza las asignaciones, asi que se envia la union.
  const detalle = await http(BASE_TEST + `/usuarios/${idUsuario}/detalle`, { token: c.tokenAdmin });
  const antes = (detalle.body?.fincas || []).map((f) => (typeof f === 'object' ? f.id_finca : f)).filter((x) => x != null);
  const objetivo = [...new Set([...antes, c.fx.id_finca])].sort((a, b) => a - b);

  let put = { omitido: true, motivo: 'la finca del activo ya estaba asignada' };
  if (!antes.includes(c.fx.id_finca)) {
    const r = await http(BASE_TEST + `/usuarios/${idUsuario}/fincas`, { metodo: 'PUT', token: c.tokenAdmin, cuerpo: { ids_fincas: objetivo } });
    put = { omitido: false, endpoint: `PUT /usuarios/${idUsuario}/fincas`, ids_fincas_enviadas: objetivo,
      status: r.status, respuesta: r.body ? JSON.parse(clean(JSON.stringify(r.body))) : null };
  }

  const detalleDespues = await http(BASE_TEST + `/usuarios/${idUsuario}/detalle`, { token: c.tokenAdmin });
  const despues = (detalleDespues.body?.fincas || []).map((f) => (typeof f === 'object' ? f.id_finca : f)).filter((x) => x != null);
  // El alcance se reevalua con un token nuevo de M06.
  const rm = await login(BASE_TEST, M06_EMAIL, process.env.M06_PASSWORD);
  const alc = rm.body?.token ? await alcance(BASE_TEST, rm.body.token, c.fx.id_activo_biologico) : null;

  const salida = { fase: 'preparar', fecha: new Date().toISOString(),
    identidad: { id_usuario: idUsuario, correo_electronico: M06_EMAIL },
    activo: { id_activo_biologico: c.fx.id_activo_biologico, identificador: c.fx.identificador,
      id_infraestructura: c.fx.id_infraestructura, id_finca: c.fx.id_finca },
    fincas_antes: antes, fincas_objetivo: objetivo, escritura: put, fincas_despues: despues,
    fincas_preexistentes_preservadas: antes.every((x) => despues.includes(x)),
    alcance_tras_preparar: alc,
    nota: 'Preparacion de datos por el endpoint oficial. No se modificaron roles, scopes, eventos de crecimiento ni datos analiticos.' };
  const destino = process.env.G93_PREPARAR_OUT || path.join(require('os').tmpdir(), 'g93-v3-preparar.json');
  fs.writeFileSync(destino, clean(JSON.stringify(salida, null, 2)));
  console.log('identidad', idUsuario, '| activo', c.fx.id_activo_biologico, '| infraestructura', c.fx.id_infraestructura, '| finca', c.fx.id_finca);
  console.log('fincas antes', JSON.stringify(antes), '-> objetivo', JSON.stringify(objetivo));
  console.log('escritura', JSON.stringify(put).slice(0, 300));
  console.log('fincas despues', JSON.stringify(despues), '| preexistentes preservadas:', salida.fincas_preexistentes_preservadas);
  console.log('alcance tras preparar', JSON.stringify(alc));
  console.log('\nPreparar ->', destino);
}

// ------------------------------------------------- Construccion de la coleccion (patron de V1)
const PRELUDIO = [
  "const norm = (s) => String(s == null ? '' : s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();",
  "const cuerpo = () => { try { return pm.response.json(); } catch (e) { return {}; } };",
].join('\n');
const raw = (obj) => ({ mode: 'raw', raw: JSON.stringify(obj, null, 2), options: { raw: { language: 'json' } } });
const test = (lineas) => ({ listen: 'test', script: { type: 'text/javascript', exec: (PRELUDIO + '\n' + lineas.join('\n')).split('\n') } });
const auth = () => [{ key: 'Authorization', value: 'Bearer {{token_consumidor}}' }];
const sinExposicion = (id) => [
  "pm.test('" + id + ": la respuesta no expone datos consolidados del activo', () => {",
  "  const b = cuerpo();",
  "  ['historial_eventos', 'historial_fases', 'historico_estados', 'metricas_actuales', 'infraestructura_asociada'].forEach((campo) => {",
  "    pm.expect(b, 'la respuesta incluye ' + campo).to.not.have.property(campo);",
  "  });",
  "});",
];
const sinFugaValidacion = (id) => [
  "pm.test('" + id + " (#393): el error no expone detalles internos de validacion', () => {",
  "  const texto = pm.response.text();",
  "  ['DatosConsolidadosDTO', 'validation error', 'type=value_error', 'input_value', 'pydantic.dev'].forEach((f) => {",
  "    pm.expect(texto, 'la respuesta contiene ' + f).to.not.include(f);",
  "  });",
  "});",
];

function construir(cfg) {
  const url = (qs) => `${cfg.base}/activos-biologicos/${cfg.id_activo}/datos-consolidados${qs ? '?' + qs : ''}`;
  const items = [];

  items.push({
    name: '00 - Login M06',
    request: { method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }], url: cfg.base + '/sesiones/',
      body: raw({ correo_electronico: cfg.m06_email, contrasena: '{{m06_password}}' }) },
    event: [test([
      "pm.test('00: la identidad tecnica M06 autentica', () => pm.response.to.have.status(200));",
      "const t = pm.response.json().token;",
      "pm.expect(Boolean(t), 'token emitido').to.eql(true);",
      "pm.collectionVariables.set('token_consumidor', t);",
    ])],
  });

  items.push({
    name: '01 - Actor y rol del consumidor',
    request: { method: 'GET', header: auth(), url: cfg.base + '/usuarios/me' },
    event: [test([
      "pm.test('01: /usuarios/me 200', () => pm.response.to.have.status(200));",
      "const b = pm.response.json();",
      "pm.test('01: el consumidor es la identidad tecnica M06', () => pm.expect(b.correo_electronico).to.eql(pm.collectionVariables.get('m06_email')));",
      "pm.test('01: el rol es Integracion M06', () => pm.expect(norm(b.nombre_rol)).to.include('integracion m06'));",
      "pm.test('01: la cuenta esta activa', () => pm.expect(b.estado_cuenta).to.eql('Activo'));",
    ])],
  });

  items.push({
    name: '02 - Control positivo M06 + metricas',
    request: { method: 'GET', header: auth(), url: url('tipo_dato=metricas') },
    event: [test([
      "pm.test('02: HTTP 200 — token valido, activo visible, permiso general y scope metricas', () => pm.expect(pm.response.code).to.eql(200));",
      "const b = pm.response.json();",
      "pm.test('02: responde el activo solicitado', () => pm.expect(b.id_activo_biologico).to.eql(Number(pm.collectionVariables.get('id_activo'))));",
      "pm.test('02: devuelve JSON de exito con la seccion de metricas', () => pm.expect(b).to.have.property('metricas_actuales'));",
    ])],
  });

  items.push({
    name: '03 - TC-M02-155 - tipo_dato sin scope autorizado',
    request: { method: 'GET', header: auth(), url: url('tipo_dato=eventos') },
    event: [test([
      "pm.test('TC-M02-155: HTTP 403', () => pm.expect(pm.response.code).to.eql(403));",
      "const b = cuerpo();",
      "pm.test('TC-M02-155: el rechazo proviene del scope granular por tipo_dato', () => pm.expect(b.error_code).to.eql('SCOPE_TIPO_DATO_NO_AUTORIZADO'));",
      "pm.test('TC-M02-155: el mensaje identifica el tipo_dato solicitado', () => pm.expect(norm(b.message)).to.include('eventos'));",
      "pm.test('TC-M02-155: el mensaje indica falta de autorizacion del modulo solicitante', () => pm.expect(norm(b.message)).to.include('no tiene autorizacion'));",
      ...sinExposicion('TC-M02-155'),
    ])],
  });

  items.push({
    name: '04 - TC-M02-156-A - fecha_inicio posterior a fecha_fin',
    request: { method: 'GET', header: auth(), url: url(`tipo_dato=metricas&fecha_inicio=${cfg.invertido.inicio}&fecha_fin=${cfg.invertido.fin}`) },
    event: [test([
      "pm.test('TC-M02-156-A: HTTP 400', () => pm.expect(pm.response.code).to.eql(400));",
      "const b = cuerpo();",
      "pm.test('TC-M02-156-A: error_code PARAMETROS_INVALIDOS', () => pm.expect(b.error_code).to.eql('PARAMETROS_INVALIDOS'));",
      "pm.test('TC-M02-156-A: el motivo funcional se refiere al orden del rango', () => {",
      "  const m = norm(b.message) + ' ' + norm(JSON.stringify(b.fields || []));",
      "  pm.expect(/inicio|posterior|mayor|rango/.test(m), 'mensaje: ' + m).to.eql(true);",
      "});",
      ...sinExposicion('TC-M02-156-A'),
      ...sinFugaValidacion('TC-M02-156-A'),
    ])],
  });

  items.push({
    name: '05 - TC-M02-156-B - rango de fechas futuro',
    request: { method: 'GET', header: auth(), url: url(`tipo_dato=metricas&fecha_inicio=${cfg.futuro.inicio}&fecha_fin=${cfg.futuro.fin}`) },
    event: [test([
      "pm.test('TC-M02-156-B: HTTP 400', () => pm.expect(pm.response.code).to.eql(400));",
      "const b = cuerpo();",
      "pm.test('TC-M02-156-B: error_code PARAMETROS_INVALIDOS', () => pm.expect(b.error_code).to.eql('PARAMETROS_INVALIDOS'));",
      "pm.test('TC-M02-156-B: el motivo se refiere a la condicion temporal futura', () => {",
      "  const m = norm(b.message) + ' ' + norm(JSON.stringify(b.fields || []));",
      "  pm.expect(/futur|posterior a la fecha actual|hoy/.test(m), 'mensaje: ' + m).to.eql(true);",
      "});",
      ...sinExposicion('TC-M02-156-B'),
      ...sinFugaValidacion('TC-M02-156-B'),
    ])],
  });

  items.push({
    name: '06 - TC-M02-157 - NIC-41 sin metricas de PESO en el rango',
    request: { method: 'GET', header: auth(), url: url(`tipo_dato=metricas&fecha_inicio=${cfg.nic41.inicio}&fecha_fin=${cfg.nic41.fin}`) },
    event: [test([
      "pm.test('TC-M02-157: HTTP 422', () => pm.expect(pm.response.code).to.eql(422));",
      "const b = cuerpo();",
      "pm.test('TC-M02-157: error_code METRICAS_PESO_INSUFICIENTES', () => pm.expect(b.error_code).to.eql('METRICAS_PESO_INSUFICIENTES'));",
      "pm.test('TC-M02-157: el mensaje identifica la insuficiencia de PESO en el rango', () => {",
      "  const m = norm(b.message);",
      "  pm.expect(m).to.include('peso');",
      "  pm.expect(/rango de fechas|periodo/.test(m), 'mensaje: ' + m).to.eql(true);",
      "});",
      "pm.test('TC-M02-157: no es un 422 generico de validacion de entrada', () => pm.expect(b.error_code).to.not.eql('VAL_ENTRADA'));",
      ...sinExposicion('TC-M02-157'),
      ...sinFugaValidacion('TC-M02-157'),
    ])],
  });

  items.push({
    name: '07 - Verificacion complementaria - advertencia de peso fuera del rango',
    request: { method: 'GET', header: auth(), url: url(`tipo_dato=metricas&fecha_inicio=${cfg.observacion.inicio}&fecha_fin=${cfg.observacion.fin}`) },
    event: [test([
      "pm.test('#392: HTTP 200 — existe al menos un PESO en el rango, no aplica el 422', () => pm.expect(pm.response.code).to.eql(200));",
      "const b = cuerpo();",
      "pm.test('#392: metricas_actuales sigue visible', () => pm.expect(b).to.have.property('metricas_actuales'));",
      "const plano = JSON.stringify(b);",
      "pm.test('#392: la respuesta incluye advertencia_peso_fuera_de_rango', () => pm.expect(plano).to.include('advertencia_peso_fuera_de_rango'));",
      "pm.test('#392: la advertencia aclara que el peso mostrado no pertenece al periodo solicitado', () => {",
      "  const m = b.metricas_actuales || {};",
      "  const a = norm(m.advertencia_peso_fuera_de_rango || (plano.match(/\"advertencia_peso_fuera_de_rango\"\\s*:\\s*\"([^\"]*)\"/) || [])[1] || '');",
      "  pm.expect(/fuera|no pertenece|posterior|rango|periodo/.test(a), 'advertencia: ' + a).to.eql(true);",
      "});",
    ])],
  });

  return {
    info: { name: 'TC-M02-G93 REEVALUACION V3 — RF-50 reglas negativas de datos consolidados (CU12)',
      description: 'TC-M02-155 (403 por scope granular de tipo_dato), TC-M02-156-A y B (400 por rango invertido y por rango futuro) y TC-M02-157 (422 por insuficiencia de metricas PESO segun NIC-41), ejecutados con la identidad tecnica M06. Incluye control positivo previo, para que ningun rechazo sea atribuible a autenticacion, permiso general o alcance, y la verificacion complementaria de la advertencia de peso fuera del rango.',
      schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json' },
    item: items,
    variable: [{ key: 'id_activo', value: String(cfg.id_activo) }, { key: 'm06_email', value: cfg.m06_email }],
  };
}

// -------------------------------------------------------------------------------- OFICIAL
async function oficial() {
  const runId = process.env.G93_V3_RUN_ID;
  if (!runId || !/^G93-REEVAL-V3-\d{8}-\d{6}$/.test(runId)) throw Error('G93_V3_RUN_ID con formato G93-REEVAL-V3-YYYYMMDD-HHMMSS es obligatorio');
  const c = await contexto();
  const g = gate(c);
  if (!g.completo) throw Error('BLOCKED: gate incompleto, no se ejecutan los casos ' + JSON.stringify(g.checklist.filter((x) => !x.cumple)));

  const R = path.join(__dirname, 'RESULTADOS', runId);
  if (fs.existsSync(R)) throw Error('El RUN_ID ya existe; conservar la evidencia: ' + runId);
  fs.mkdirSync(R, { recursive: true });

  const cfg = { base: BASE_TEST, id_activo: c.fx.id_activo_biologico, m06_email: M06_EMAIL,
    invertido: c.rg.invertido, futuro: c.rg.futuro, nic41: c.rg.nic41, observacion: c.rg.observacion_392 };
  const collection = construir(cfg);
  fs.writeFileSync(path.join(__dirname, 'test_tc_m02_g93_v3.json'), JSON.stringify(collection, null, 2));

  const newman = require('newman');
  require.resolve('newman-reporter-htmlextra');
  const html = path.join(R, 'newman-g93-v3.html');
  const summary = await new Promise((res, rej) => newman.run({
    collection, reporters: ['htmlextra', 'json'], timeoutRequest: 45000,
    reporter: {
      htmlextra: { export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false,
        skipEnvironmentVars: ['m06_password', 'token_consumidor'], logs: false, silentProgressBar: true,
        title: 'TC-M02-155 / 156-A / 156-B / 157 — G93 REEVALUACION V3 — TEST' },
      json: { export: path.join(R, 'newman-g93-v3.json') },
    },
    environment: { values: [{ key: 'm06_password', value: process.env.M06_PASSWORD, enabled: true }] },
  }, (err, sm) => (err ? rej(Error('Newman execution error: ' + clean(err.message))) : res(sm))));
  for (const f of ['newman-g93-v3.html', 'newman-g93-v3.json']) { const p = path.join(R, f); if (fs.existsSync(p)) fs.writeFileSync(p, clean(fs.readFileSync(p, 'utf8'))); }

  const aserciones = []; const respuestas = {};
  for (const ex of summary.run.executions) {
    let b = null; try { b = JSON.parse(ex.response.stream.toString()); } catch { /* sin JSON */ }
    respuestas[ex.item.name] = { status: ex.response?.code ?? null, ms: ex.response?.responseTime ?? null,
      error_code: b?.error_code ?? null, mensaje: b?.message ? String(b.message).slice(0, 240) : null };
    for (const a of ex.assertions || []) aserciones.push({ request: ex.item.name, test: a.assertion, ok: !a.error, detalle: a.error ? clean(a.error.message).slice(0, 300) : undefined });
  }
  const del = (p) => aserciones.filter((a) => a.test.startsWith(p));
  const esCalidad = (a) => a.test.includes('(#393)');
  const fallanFuncionales = (p) => del(p).filter((a) => !a.ok && !esCalidad(a));
  const controlPositivo = del('02:').every((a) => a.ok) && del('02:').length > 0;

  const veredicto = {
    'TC-M02-155': controlPositivo && fallanFuncionales('TC-M02-155').length === 0 ? 'APROBADO' : 'DESAPROBADO',
    'TC-M02-156-A': fallanFuncionales('TC-M02-156-A').length === 0 ? 'APROBADO' : 'DESAPROBADO',
    'TC-M02-156-B': fallanFuncionales('TC-M02-156-B').length === 0 ? 'APROBADO' : 'DESAPROBADO',
    'TC-M02-157': fallanFuncionales('TC-M02-157').length === 0 ? 'APROBADO' : 'DESAPROBADO',
  };
  veredicto['TC-M02-156'] = veredicto['TC-M02-156-A'] === 'APROBADO' && veredicto['TC-M02-156-B'] === 'APROBADO' ? 'APROBADO' : 'DESAPROBADO';
  veredicto['TC-M02-G93'] = ['TC-M02-155', 'TC-M02-156', 'TC-M02-157'].every((k) => veredicto[k] === 'APROBADO') ? 'APROBADO' : 'RECHAZADO';

  const issues = {
    '#390 (scope granular por tipo_dato)': veredicto['TC-M02-155'] === 'APROBADO' ? 'CORREGIDO Y VERIFICADO EN V3' : 'NO CORREGIDO / REGRESION',
    '#242 (rango de fechas futuro)': veredicto['TC-M02-156-B'] === 'APROBADO' ? 'CORREGIDO Y VERIFICADO EN V3' : 'NO CORREGIDO / REGRESION',
    '#391 (identidad M06 y regla 422 NIC-41)': veredicto['TC-M02-157'] === 'APROBADO' ? 'CORREGIDO Y VERIFICADO EN V3' : 'NO CORREGIDO / REGRESION',
    '#392 (advertencia de peso fuera del rango)': del('#392').length && del('#392').every((a) => a.ok) ? 'CORREGIDO Y VERIFICADO EN V3' : 'NO CORREGIDO',
    '#393 (fuga de detalles de validacion)': aserciones.filter(esCalidad).length && aserciones.filter(esCalidad).every((a) => a.ok) ? 'CORREGIDO Y VERIFICADO EN V3' : 'NO CORREGIDO / REGRESION DE CALIDAD',
  };

  const evidencia = {
    grupo: 'TC-M02-G93', casos: ['TC-M02-155', 'TC-M02-156-A', 'TC-M02-156-B', 'TC-M02-157'],
    rf: 'RF-50', cu: 'CU12', tipo: 'REEVALUACION V3', runId, environment: 'TEST', fecha: new Date().toISOString(),
    preflight: { health: c.health, contrato: c.contrato },
    provision: c.prov, identidad_tecnica: c.actorM06, alcance: c.alc,
    fixture: c.fx, rangos: c.rg, gate: g,
    respuestas_observadas: respuestas, control_positivo_superado: controlPositivo,
    veredicto, seguimiento_issues: issues,
    newman: { html: 'newman-g93-v3.html', json: 'newman-g93-v3.json', stats: summary.run.stats.assertions, aserciones },
    git: estadoGit(),
  };
  fs.writeFileSync(path.join(R, 'evidencia-g93-v3.json'), clean(JSON.stringify(evidencia, null, 2)));

  console.log('actor', c.actorM06.correo_electronico, '| rol', c.actorM06.nombre_rol, '| fincas', JSON.stringify(c.alc.fincas_en_el_perfil));
  console.log('activo', c.fx.id_activo_biologico, c.fx.identificador, '| finca', c.fx.id_finca);
  Object.entries(respuestas).forEach(([n, r]) => console.log('  ', String(r.status).padEnd(4), n, '->', r.error_code || '(200)', r.ms + 'ms'));
  console.log('control positivo superado:', controlPositivo);
  console.log('VEREDICTO', JSON.stringify(veredicto, null, 1));
  console.log('ISSUES', JSON.stringify(issues, null, 1));
  aserciones.filter((a) => !a.ok).forEach((a) => console.log('  FAIL', a.request, '::', a.test, '->', (a.detalle || '').slice(0, 130)));
  console.log('Evidencia:', path.join(R, 'evidencia-g93-v3.json'));
}

// --------------------------------------------------------------------------------- CIERRE
function cierre() {
  const R = path.join(__dirname, 'RESULTADOS', process.env.G93_V3_RUN_ID);
  const archivo = path.join(R, 'evidencia-g93-v3.json');
  const evidencia = JSON.parse(fs.readFileSync(archivo, 'utf8'));
  const patrones = [
    ['password', /"?(contrasena|password|contraseña)"?\s*[:=]\s*"[^"\[{]{3,}"/i],
    ['jwt', /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\./],
    ['authorization', /"?authorization"?\s*[:=]\s*"(?!\[|Bearer \{\{)[^"]*"/i],
    ['bearer', /Bearer\s+(?!\[|\{\{)[A-Za-z0-9_.\-]{10,}/],
    ['refresh_token', /"refresh_token"\s*:\s*"[^"\[]{3,}"/],
    ['cookie', /"?set-cookie"?\s*[:=]\s*"[^"\[]{3,}"/i],
    ['connstring', /postgres(ql)?:\/\/[^\s"]+/i],
  ];
  const hallazgos = []; let total = 0;
  const caminar = (dir) => { for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { caminar(p); continue; }
    if (/\.(png|jpg|jpeg|gif|pdf|zip|mp4)$/i.test(p)) continue;
    total += 1;
    const txt = fs.readFileSync(p, 'utf8');
    for (const [nombre, re] of patrones) if (re.test(txt)) hallazgos.push({ archivo: path.relative(R, p).split(path.sep).join('/'), patron: nombre });
  } };
  caminar(R);
  evidencia.seguridad = { fecha: new Date().toISOString(), archivosEscaneados: total, archivosComprometidos: [...new Set(hallazgos.map((h) => h.archivo))].length, hallazgos };
  evidencia.git = estadoGit();
  fs.writeFileSync(archivo, clean(JSON.stringify(evidencia, null, 2)));
  console.log('Seguridad:', total, 'archivos,', evidencia.seguridad.archivosComprometidos, 'comprometidos', JSON.stringify(hallazgos));
  console.log(JSON.stringify(evidencia.git, null, 1));
}

const FASE = (process.env.G93_FASE || 'preflight').toLowerCase();
(async () => {
  if (FASE === 'preflight') await preflight();
  else if (FASE === 'preparar') await preparar();
  else if (FASE === 'oficial') await oficial();
  else if (FASE === 'cierre') cierre();
  else throw Error('G93_FASE debe ser preflight | preparar | oficial | cierre');
})().catch((e) => { console.log('ERROR:', clean(e.message)); process.exitCode = 1; });
