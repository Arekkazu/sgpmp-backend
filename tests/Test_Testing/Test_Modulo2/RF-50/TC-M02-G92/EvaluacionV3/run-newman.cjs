// TC-M02-G92 V3 — RF-50 / RF-51 · CU12. Consumo de datos analiticos e indicadores zootecnicos por una
// identidad tecnica M04 autorizada:
//   TC-M02-154  GET /activos-biologicos/{id}/datos-consolidados -> 200 conforme al contrato, <= 5 s
//   TC-M02-159  GET /activos-biologicos/{id}/indicadores        -> 200 con ganancia diaria de peso
//
// ADAPTACION RESPECTO A V1/V2
// ---------------------------
// V1 y V2 cerraron en BLOQUEADO porque la identidad tecnica M04 no estaba provisionada en TEST: la
// coleccion V1 era un gate de solo lectura sobre OpenAPI y los dos subcasos nunca se ejecutaron. Se
// conservan de V1 los endpoints y los parametros de consulta; la adaptacion autentica la identidad
// tecnica suministrada, valida su rol, su RBAC y su alcance, revalida el fixture, recalcula el
// indicador de forma independiente y ejecuta los dos subcasos con oraculo.
//
// El caso no cambia: mismo actor tecnico, mismos endpoints, mismas precondiciones y mismo oraculo.
// La unica preparacion permitida es dar alcance a la identidad sobre la finca del fixture.
//
// Fases:
//   G92_FASE=preflight  git, health, OpenAPI, identidad, RBAC, alcance, fixture y expected
//   G92_FASE=preparar   asigna la finca del fixture a la identidad por PUT oficial, si falta
//   G92_FASE=oficial    requiere G92_V3_RUN_ID: unica carpeta, ejecuta TC-154 y TC-159
//   G92_FASE=cierre     consolida seguridad y estado de Git en la misma evidencia
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const BASE_TEST = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const BASE_DEV = 'https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp';
const M04_EMAIL = process.env.M04_TEST_EMAIL || 'integracion.tes@gmail.com';
const ACTIVO_PREFERIDO = Number(process.env.G92_ID_ACTIVO || 295);
const RECURSO_ACTIVOS = 'activos_biologicos';
const RECURSO_USUARIOS = 'usuarios';
const ACCION_LEER = 2;
const ACCION_ACTUALIZAR = 3;
const RNF_MS = 5000;

const PRUEBAS = path.resolve(__dirname, '..', '..', '..', '..', '..', '..', '..');
const FRONT = path.join(PRUEBAS, 'SGPMP-FRONT-END-PWA');
const BACK = path.join(PRUEBAS, 'sgpmp-backend');

const clean = (s) => {
  s = String(s);
  for (const v of ['M04_TEST_PASSWORD', 'QA_ADMIN_PASSWORD']) if (process.env[v]) s = s.split(process.env[v]).join('[REDACTED]');
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+(?!\[|\{\{)[A-Za-z0-9_.\-]+/g, 'Bearer [REDACTED]');
};
const norm = (s) => String(s == null ? '' : s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

// Decimales exactos con BigInt: el expected del indicador se recalcula sin coma flotante.
const esc = (v, dec) => { const [e, d = ''] = String(v).split('.'); const n = e.startsWith('-'); return (n ? -1n : 1n) * BigInt((n ? e.slice(1) : e) + (d + '0'.repeat(dec)).slice(0, dec)); };
const decimalesDe = (v) => { const p = String(v).split('.'); return p[1] ? p[1].length : 0; };
function dividir(numerador, denominador, dec) {
  const escala = 10n ** BigInt(dec + 1);
  const bruto = (numerador * escala) / denominador;
  let r = bruto / 10n;
  if (bruto % 10n >= 5n) r += 1n;
  const s = r.toString().padStart(dec + 1, '0');
  return dec === 0 ? s : s.slice(0, -dec) + '.' + s.slice(-dec);
}
const diasEntre = (a, b) => Math.round((new Date(b.slice(0, 10)) - new Date(a.slice(0, 10))) / 86400000);

async function http(url, { metodo = 'GET', token, cuerpo } = {}) {
  const t0 = Date.now();
  try {
    const r = await fetch(url, { method: metodo, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined, redirect: 'manual', signal: AbortSignal.timeout(45000) });
    let body = null; try { body = await r.json(); } catch { /* sin JSON */ }
    return { status: r.status, body, ms: Date.now() - t0, contentType: r.headers.get('content-type') };
  } catch (e) { return { status: 'ERR', error: clean(e.message), ms: Date.now() - t0 }; }
}
const login = (base, correo, pass) => http(base + '/sesiones/', { metodo: 'POST', cuerpo: { correo_electronico: correo, contrasena: pass } });

async function contratoDe(base) {
  const r = await http(base + '/openapi.json');
  const paths = r.body?.paths || {};
  const sch = r.body?.components?.schemas || {};
  const dc = paths['/activos-biologicos/{id_activo}/datos-consolidados']?.get;
  const ind = paths['/activos-biologicos/{id_activo}/indicadores']?.get;
  return {
    openapi: r.status,
    datos_consolidados: Boolean(dc), indicadores: Boolean(ind),
    respuestas_datos_consolidados: Object.keys(dc?.responses || {}),
    respuestas_indicadores: Object.keys(ind?.responses || {}),
    parametros_indicadores: (ind?.parameters || []).map((p) => p.name),
    campos_datos_consolidados: Object.keys(sch.DatosConsolidadosResponse?.properties || {}),
    campos_indicadores: Object.keys(sch.IndicadoresActivoResponse?.properties || {}),
    campos_indicador: Object.keys(sch.IndicadorZootecnicoResponse?.properties || {}),
    put_fincas: Boolean(paths['/usuarios/{id_usuario}/fincas']?.put),
  };
}

// Descubrimiento de la identidad tecnica y del catalogo de recursos, con observador administrativo
// de solo lectura. No sustituye a la identidad tecnica como consumidor del caso.
async function provision(base, tokenAdmin) {
  const out = {};
  const rec = await http(base + '/roles/catalogo/recursos', { token: tokenAdmin });
  const listaRec = Array.isArray(rec.body) ? rec.body : (rec.body?.items || rec.body?.registros || []);
  const idRecurso = (n) => { const x = listaRec.find((y) => norm(y.nombre ?? y.nombre_recurso) === norm(n)); return x ? (x.id_recurso ?? x.id) : null; };
  out.recursos = { activos_biologicos: idRecurso(RECURSO_ACTIVOS), usuarios: idRecurso(RECURSO_USUARIOS),
    scope: { eventos: idRecurso('datos_analiticos_eventos'), fases: idRecurso('datos_analiticos_fases'),
      estado: idRecurso('datos_analiticos_estado'), metricas: idRecurso('datos_analiticos_metricas') } };

  // El rol se resuelve por NOMBRE y sus permisos vienen en linea en el catalogo de roles.
  const roles = await http(base + '/roles/', { token: tokenAdmin });
  const listaRoles = Array.isArray(roles.body) ? roles.body : (roles.body?.items || roles.body?.registros || []);
  const rol = listaRoles.find((r) => /integracion\s*m04/.test(norm(r.nombre ?? r.nombre_rol))) ?? null;
  out.rol = rol ? { id_rol: rol.id_rol ?? rol.id, nombre: rol.nombre_rol ?? rol.nombre } : null;
  if (rol) {
    const lp = (rol.permisos || []).filter((x) => x.es_activo !== false);
    const tiene = (idRec) => lp.some((x) => Number(x.id_recurso) === Number(idRec) && Number(x.id_accion) === ACCION_LEER);
    out.permisos_del_rol = {
      total: lp.length,
      read_activos_biologicos: out.recursos.activos_biologicos ? tiene(out.recursos.activos_biologicos) : null,
      scopes: Object.fromEntries(Object.entries(out.recursos.scope).map(([k, r]) => [k, r ? tiene(r) : null])),
      permisos: lp.map((x) => ({ nombre: x.nombre, id_recurso: x.id_recurso, id_accion: x.id_accion })),
    };
  }

  const u = await http(base + `/usuarios/admin?correo=${encodeURIComponent(M04_EMAIL)}&pagina=1&tamano=50`, { token: tokenAdmin });
  const lista = u.body?.registros || u.body?.items || (Array.isArray(u.body) ? u.body : []);
  const exacto = lista.map((x) => ({ id_usuario: x.id_usuario, correo_electronico: x.correo_electronico,
    id_rol: x.id_rol, nombre_rol: x.nombre_rol, estado_cuenta: x.estado_cuenta }))
    .find((x) => norm(x.correo_electronico) === norm(M04_EMAIL)) ?? null;
  out.usuario = exacto;

  return out;
}

// Fixture: activo, su finca y sus mediciones de peso. Se lee con el observador administrativo.
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
  const fechasDistintas = [...new Set(pesos.map((p) => p.fecha))];
  return { id_activo_biologico: idActivo, existe: true, identificador: det.body.identificador, tipo: det.body.tipo,
    nombre_estado: det.body.nombre_estado, fecha_inicio_ciclo: String(det.body.fecha_inicio_ciclo ?? '').slice(0, 10),
    id_infraestructura: det.body.id_infraestructura, infraestructura: infra, id_finca: idFinca,
    total_eventos: ev.body?.total ?? null, mediciones_peso: pesos, fechas_distintas: fechasDistintas.length,
    apto_154: true, apto_159: pesos.length >= 2 && fechasDistintas.length >= 2 };
}

// Expected independiente: ganancia diaria = (peso_final - peso_inicial) / dias transcurridos.
function expectedGpd(mediciones) {
  const primera = mediciones[0];
  const ultima = mediciones[mediciones.length - 1];
  const dias = diasEntre(primera.fecha, ultima.fecha);
  const dec = Math.max(decimalesDe(primera.valor), decimalesDe(ultima.valor), 2);
  const delta = esc(ultima.valor, dec) - esc(primera.valor, dec);
  const divisor = BigInt(dias) * (10n ** BigInt(dec));
  return { peso_inicial: primera.valor, peso_final: ultima.valor,
    fecha_inicial: primera.fecha, fecha_final: ultima.fecha, dias, total_mediciones: mediciones.length,
    formula: `(${ultima.valor} - ${primera.valor}) / ${dias}`,
    por_decimales: Object.fromEntries([2, 3, 4, 5, 6].map((n) => [n, dividir(delta, divisor, n)])),
    a_precision: (n) => dividir(delta, divisor, n) };
}

// Alcance efectivo de la identidad tecnica sobre el activo del caso.
async function alcance(base, tokenM04, idActivo) {
  const listado = await http(base + '/activos-biologicos?pagina=1&por_pagina=50', { token: tokenM04 });
  // Llamada canonica de TC-M02-154: sin parametros, el contrato aplica tipo_dato=todos.
  const canonica = await http(base + `/activos-biologicos/${idActivo}/datos-consolidados`, { token: tokenM04 });
  // Un tipo_dato para el que el rol si tiene scope: distingue un rechazo por scope de uno por alcance.
  const autorizada = await http(base + `/activos-biologicos/${idActivo}/datos-consolidados?tipo_dato=eventos`, { token: tokenM04 });
  const indicadores = await http(base + `/activos-biologicos/${idActivo}/indicadores?tipo_indicador=CRECIMIENTO`, { token: tokenM04 });
  const resumen = (r) => ({ status: r.status, error_code: r.body?.error_code ?? null, ms: r.ms });
  return { activos_visibles: listado.body?.total_registros ?? (listado.body?.registros || []).length,
    datos_consolidados_canonica: resumen(canonica),
    datos_consolidados_tipo_autorizado: resumen(autorizada),
    indicadores: resumen(indicadores),
    alcance_sobre_el_activo: autorizada.status !== 404 && indicadores.status !== 404,
    ve_el_activo: canonica.status === 200 };
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

function gate({ health, contrato, prov, actor, fx, alc }) {
  const v = [];
  const ok = (c, t) => v.push({ condicion: t, cumple: Boolean(c) });
  ok(health === 200, 'TEST disponible');
  ok(contrato?.datos_consolidados && contrato?.indicadores, 'OpenAPI define ambos endpoints');
  ok(contrato?.campos_datos_consolidados?.length && contrato?.campos_indicador?.length, 'contrato de respuesta identificable');
  ok(actor?.id_usuario, 'la identidad suministrada autentica');
  ok(actor?.estado_cuenta === 'Activo', 'cuenta activa');
  ok(actor && /integracion/.test(norm(actor.nombre_rol)), 'identidad demostrablemente tecnica de integracion');
  ok(prov?.permisos_del_rol?.read_activos_biologicos, 'permiso READ sobre activos_biologicos');
  ok(fx?.existe, 'activo del fixture existe');
  ok(fx?.id_finca != null, 'finca del fixture identificada');
  ok(alc?.fincas_asignadas?.includes(fx?.id_finca), 'alcance sobre la finca del fixture confirmado');
  ok(alc?.alcance_sobre_el_activo, 'el activo del fixture es alcanzable para la identidad (no 404)');
  ok(fx?.apto_159, 'activo con al menos 2 mediciones de peso en fechas distintas');
  ok(fx?.apto_159 && fx.mediciones_peso[0].fecha < fx.mediciones_peso[fx.mediciones_peso.length - 1].fecha, 'periodo valido');
  const comun = v.every((x) => x.cumple);
  // Aptitud por subcaso: TC-154 exige scope sobre el tipo_dato de la llamada canonica (todos).
  const aptitud = {
    'TC-M02-154': { ejecutable: alc?.datos_consolidados_canonica?.status === 200,
      motivo: alc?.datos_consolidados_canonica?.status === 200 ? null
        : `la llamada canonica responde ${alc?.datos_consolidados_canonica?.status} ${alc?.datos_consolidados_canonica?.error_code ?? ''}`.trim() },
    'TC-M02-159': { ejecutable: alc?.indicadores?.status === 200,
      motivo: alc?.indicadores?.status === 200 ? null
        : `el endpoint de indicadores responde ${alc?.indicadores?.status} ${alc?.indicadores?.error_code ?? ''}`.trim() },
  };
  return { checklist: v, comun, aptitud,
    completo: comun && Object.values(aptitud).every((x) => x.ejecutable) };
}

async function contexto() {
  const health = (await http(BASE_TEST + '/health')).status;
  const contrato = await contratoDe(BASE_TEST);
  if (!process.env.QA_ADMIN_EMAIL || !process.env.QA_ADMIN_PASSWORD) throw Error('Se requiere una cuenta administrativa autorizada para el descubrimiento de solo lectura');
  const ra = await login(BASE_TEST, process.env.QA_ADMIN_EMAIL, process.env.QA_ADMIN_PASSWORD);
  if (!ra.body?.token) throw Error('La cuenta administrativa no autentico: ' + ra.status);
  const tokenAdmin = ra.body.token;
  const prov = await provision(BASE_TEST, tokenAdmin);
  const fx = await fixture(BASE_TEST, tokenAdmin, ACTIVO_PREFERIDO);
  const exp = fx.apto_159 ? expectedGpd(fx.mediciones_peso) : null;

  if (!process.env.M04_TEST_PASSWORD) throw Error('PRECONDICION PENDIENTE — credencial de la identidad tecnica no suministrada');
  const rm = await login(BASE_TEST, M04_EMAIL, process.env.M04_TEST_PASSWORD);
  const intento = { correo: M04_EMAIL, status: rm.status, error_code: rm.body?.error_code ?? null,
    campo: rm.body?.fields?.[0]?.field ?? null, detalle: clean(String(rm.body?.fields?.[0]?.message ?? '')).slice(0, 180) };
  if (!rm.body?.token) throw Error('La identidad tecnica no autentico: ' + JSON.stringify(intento));
  const tokenM04 = rm.body.token;
  const me = await http(BASE_TEST + '/usuarios/me', { token: tokenM04 });
  const actor = { id_usuario: me.body?.id_usuario, correo_electronico: me.body?.correo_electronico,
    nombre: me.body?.nombre, id_rol: me.body?.id_rol, nombre_rol: me.body?.nombre_rol, estado_cuenta: me.body?.estado_cuenta };
  const alc = await alcance(BASE_TEST, tokenM04, ACTIVO_PREFERIDO);
  const d = await http(BASE_TEST + `/usuarios/${actor.id_usuario}/detalle`, { token: tokenAdmin });
  alc.fincas_asignadas = (d.body?.fincas || []).map((f) => (typeof f === 'object' ? f.id_finca : f)).filter((x) => x != null);
  return { health, contrato, tokenAdmin, prov, fx, exp, tokenM04, actor, intento, alc };
}

// ---------------------------------------------------------------------------------- PREFLIGHT
async function preflight() {
  const c = await contexto();
  const g = gate(c);
  const exp = c.exp ? { ...c.exp, a_precision: undefined } : null;
  const salida = { fase: 'preflight', fecha: new Date().toISOString(), git: estadoGit(),
    health: c.health, contrato: c.contrato, provision: c.prov, login: c.intento, actor: c.actor,
    fixture: c.fx, expected: exp, alcance: c.alc, gate: g };
  const destino = process.env.G92_PREFLIGHT_OUT || path.join(require('os').tmpdir(), 'g92-v3-preflight.json');
  fs.writeFileSync(destino, clean(JSON.stringify(salida, null, 2)));
  console.log('health', c.health, '| endpoints', JSON.stringify({ dc: c.contrato.datos_consolidados, ind: c.contrato.indicadores, put_fincas: c.contrato.put_fincas }));
  console.log('login', JSON.stringify(c.intento));
  console.log('actor', JSON.stringify(c.actor));
  console.log('usuario en catalogo', JSON.stringify(c.prov.usuario), '| permisos del rol', JSON.stringify(c.prov.permisos_del_rol && { total: c.prov.permisos_del_rol.total, read: c.prov.permisos_del_rol.read_activos_biologicos }));
  console.log('fixture', JSON.stringify({ id: c.fx.id_activo_biologico, ident: c.fx.identificador, tipo: c.fx.tipo, estado: c.fx.nombre_estado, infra: c.fx.id_infraestructura, finca: c.fx.id_finca, pesos: c.fx.mediciones_peso, apto_159: c.fx.apto_159 }));
  if (exp) console.log('expected', JSON.stringify({ formula: exp.formula, dias: exp.dias, por_decimales: exp.por_decimales }));
  console.log('alcance', JSON.stringify(c.alc));
  console.log('GATE completo:', g.completo);
  g.checklist.filter((x) => !x.cumple).forEach((x) => console.log('   FALTA:', x.condicion));
  console.log('\nPreflight ->', destino);
}

// ----------------------------------------------------------------------------------- PREPARAR
// Unica preparacion permitida: dar a la identidad tecnica alcance sobre la finca del fixture, por el
// endpoint oficial y preservando las fincas activas preexistentes. No forma parte del oraculo.
async function preparar() {
  const c = await contexto();
  if (!c.fx.existe || c.fx.id_finca == null) throw Error('No se pudo identificar la finca del activo del fixture');
  const idUsuario = c.prov.usuario?.id_usuario ?? c.actor.id_usuario;
  if (!idUsuario) throw Error('No se descubrio el id de la identidad tecnica');

  const perm = await http(BASE_TEST + '/sesiones/me/permisos', { token: c.tokenAdmin });
  const lp = Array.isArray(perm.body) ? perm.body : (perm.body?.items || perm.body?.permisos || perm.body?.registros || []);
  const puede = lp.some((x) => Number(x.id_recurso ?? x.recurso?.id_recurso) === Number(c.prov.recursos.usuarios)
    && Number(x.id_accion ?? x.accion?.id_accion) === ACCION_ACTUALIZAR);
  if (!puede) throw Error('El ejecutor no tiene permiso de actualizacion sobre Usuarios; no se prepara el alcance');

  const antes = c.alc.fincas_asignadas;
  const objetivo = [...new Set([...antes, c.fx.id_finca])].sort((a, b) => a - b);
  let escritura = { omitido: true, motivo: 'la finca del fixture ya estaba asignada' };
  if (!antes.includes(c.fx.id_finca)) {
    const r = await http(BASE_TEST + `/usuarios/${idUsuario}/fincas`, { metodo: 'PUT', token: c.tokenAdmin, cuerpo: { ids_fincas: objetivo } });
    escritura = { omitido: false, endpoint: `PUT /usuarios/${idUsuario}/fincas`, ids_fincas_enviadas: objetivo,
      status: r.status, respuesta: r.body ? JSON.parse(clean(JSON.stringify(r.body))) : null };
  }
  const d = await http(BASE_TEST + `/usuarios/${idUsuario}/detalle`, { token: c.tokenAdmin });
  const despues = (d.body?.fincas || []).map((f) => (typeof f === 'object' ? f.id_finca : f)).filter((x) => x != null);
  const rm = await login(BASE_TEST, M04_EMAIL, process.env.M04_TEST_PASSWORD);
  const alc = rm.body?.token ? await alcance(BASE_TEST, rm.body.token, c.fx.id_activo_biologico) : null;

  const salida = { fase: 'preparar', fecha: new Date().toISOString(),
    identidad: { id_usuario: idUsuario, correo_electronico: M04_EMAIL },
    activo: { id_activo_biologico: c.fx.id_activo_biologico, identificador: c.fx.identificador,
      id_infraestructura: c.fx.id_infraestructura, id_finca: c.fx.id_finca },
    fincas_antes: antes, fincas_objetivo: objetivo, escritura, fincas_despues: despues,
    fincas_preexistentes_preservadas: antes.every((x) => despues.includes(x)),
    alcance_tras_preparar: alc,
    nota: 'Preparacion de datos por el endpoint oficial. No se modifico el rol, el permiso READ ni se crearon eventos de crecimiento.' };
  const destino = process.env.G92_PREPARAR_OUT || path.join(require('os').tmpdir(), 'g92-v3-preparar.json');
  fs.writeFileSync(destino, clean(JSON.stringify(salida, null, 2)));
  console.log('identidad', idUsuario, '| activo', c.fx.id_activo_biologico, '| finca', c.fx.id_finca);
  console.log('fincas antes', JSON.stringify(antes), '-> objetivo', JSON.stringify(objetivo));
  console.log('escritura', JSON.stringify(escritura).slice(0, 300));
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
const auth = () => [{ key: 'Authorization', value: 'Bearer {{token_tecnico}}' }];

function construir(cfg) {
  const items = [];

  items.push({
    name: '00 - Login de la identidad tecnica',
    request: { method: 'POST', header: [{ key: 'Content-Type', value: 'application/json' }], url: cfg.base + '/sesiones/',
      body: raw({ correo_electronico: cfg.email, contrasena: '{{clave_tecnica}}' }) },
    event: [test([
      "pm.test('00: la identidad tecnica autentica', () => pm.response.to.have.status(200));",
      "const t = pm.response.json().token;",
      "pm.expect(Boolean(t), 'token emitido').to.eql(true);",
      "pm.collectionVariables.set('token_tecnico', t);",
    ])],
  });

  items.push({
    name: '01 - Identidad y rol del consumidor',
    request: { method: 'GET', header: auth(), url: cfg.base + '/usuarios/me' },
    event: [test([
      "pm.test('01: /usuarios/me 200', () => pm.response.to.have.status(200));",
      "const b = pm.response.json();",
      "pm.test('01: es exactamente la identidad tecnica suministrada', () => pm.expect(b.correo_electronico).to.eql(pm.collectionVariables.get('email_tecnico')));",
      "pm.test('01: la cuenta esta activa', () => pm.expect(b.estado_cuenta).to.eql('Activo'));",
      "pm.test('01: el rol es una identidad tecnica de integracion', () => pm.expect(norm(b.nombre_rol), 'rol: ' + b.nombre_rol).to.include('integracion'));",
    ])],
  });

  items.push({
    name: '02 - TC-M02-154 - Consumir API interna con modulo autorizado',
    request: { method: 'GET', header: auth(), url: `${cfg.base}/activos-biologicos/${cfg.id_activo}/datos-consolidados?tipo_dato=todos&pagina=1&page_size=20` },
    event: [test([
      "pm.test('TC-M02-154: HTTP 200', () => pm.expect(pm.response.code).to.eql(200));",
      "pm.test('TC-M02-154: respuesta en JSON', () => pm.expect(String(pm.response.headers.get('Content-Type') || '')).to.include('application/json'));",
      "pm.test('TC-M02-154: tiempo de respuesta dentro del RNF', () => pm.expect(pm.response.responseTime).to.be.at.most(Number(pm.collectionVariables.get('rnf_ms'))));",
      "const b = cuerpo();",
      "const contrato = " + JSON.stringify(cfg.campos_datos_consolidados) + ";",
      "pm.test('TC-M02-154: la respuesta cumple el contrato desplegado', () => {",
      "  const faltan = contrato.filter((c) => !(c in b));",
      "  pm.expect(faltan, 'campos ausentes').to.be.an('array').that.is.empty;",
      "});",
      "pm.test('TC-M02-154: los datos corresponden al activo solicitado', () => {",
      "  pm.expect(b.id_activo_biologico).to.eql(Number(pm.collectionVariables.get('id_activo')));",
      "  pm.expect(b.identificador).to.eql(pm.collectionVariables.get('identificador'));",
      "});",
      "pm.test('TC-M02-154: no expone informacion de otros activos', () => {",
      "  const ajenos = (b.historial_eventos || []).filter((e) => e.id_activo_biologico != null && e.id_activo_biologico !== Number(pm.collectionVariables.get('id_activo')));",
      "  pm.expect(ajenos, 'eventos de otros activos').to.be.an('array').that.is.empty;",
      "});",
      "pm.test('TC-M02-154: la paginacion es coherente', () => {",
      "  pm.expect(b.pagina_actual).to.eql(1);",
      "  pm.expect(b.registros_por_pagina).to.eql(20);",
      "  pm.expect(b.total_registros).to.be.at.least(0);",
      "});",
    ])],
  });

  items.push({
    name: '03 - TC-M02-159 - Calcular Ganancia Diaria de Peso con datos suficientes',
    request: { method: 'GET', header: auth(), url: `${cfg.base}/activos-biologicos/${cfg.id_activo}/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=${cfg.fecha_inicio}&fecha_fin=${cfg.fecha_fin}` },
    event: [test([
      "pm.test('TC-M02-159: HTTP 200', () => pm.expect(pm.response.code).to.eql(200));",
      "pm.test('TC-M02-159: tiempo de respuesta dentro del RNF', () => pm.expect(pm.response.responseTime).to.be.at.most(Number(pm.collectionVariables.get('rnf_ms'))));",
      "const b = cuerpo();",
      "pm.test('TC-M02-159: la respuesta cumple el contrato desplegado', () => {",
      "  ['id_activo_biologico', 'tipo_activo', 'indicadores'].forEach((c) => pm.expect(b, 'campo ' + c).to.have.property(c));",
      "  pm.expect(b.indicadores).to.be.an('array');",
      "});",
      "const g = (b.indicadores || []).find((i) => /ganancia[_ ]?peso/i.test(String(i.tipo)));",
      "pm.test('TC-M02-159: el indicador de ganancia de peso esta presente', () => pm.expect(g, 'indicadores: ' + (b.indicadores || []).map((i) => i.tipo).join(',')).to.not.be.undefined);",
      "pm.test('TC-M02-159: el indicador esta disponible', () => pm.expect(g.disponible).to.eql(true));",
      "pm.test('TC-M02-159: el indicador expone los campos del contrato', () => ['tipo', 'valor', 'unidad', 'periodo_inicio', 'periodo_fin', 'variables_usadas', 'fecha_calculo', 'disponible'].forEach((c) => pm.expect(g, 'campo ' + c).to.have.property(c)));",
      "pm.test('TC-M02-159: la unidad es kg/dia', () => pm.expect(String(g.unidad)).to.eql('kg/dia'));",
      "pm.test('TC-M02-159: el valor coincide con el recalculo independiente', () => {",
      "  const esperado = pm.collectionVariables.get('expected_gpd');",
      "  pm.expect(Number(g.valor).toFixed(4), 'valor del indicador').to.eql(Number(esperado).toFixed(4));",
      "});",
      "pm.test('TC-M02-159: el periodo corresponde al rango de las mediciones', () => {",
      "  pm.expect(String(g.periodo_inicio).slice(0, 10)).to.eql(pm.collectionVariables.get('fecha_inicio'));",
      "  pm.expect(String(g.periodo_fin).slice(0, 10)).to.eql(pm.collectionVariables.get('fecha_fin'));",
      "});",
      "const plano = {}; const aplanar = (o, pre) => { if (o && typeof o === 'object') Object.entries(o).forEach(([k, v]) => { if (v && typeof v === 'object') aplanar(v, pre + k + '.'); else plano[(pre + k).toLowerCase()] = v; }); };",
      "aplanar(g.variables_usadas, '');",
      "const buscar = (re) => { const k = Object.keys(plano).find((x) => re.test(x)); return k ? plano[k] : undefined; };",
      "pm.test('TC-M02-159: declara las variables utilizadas en el calculo', () => pm.expect(Object.keys(plano).length, 'variables_usadas: ' + JSON.stringify(g.variables_usadas)).to.be.above(0));",
      "pm.test('TC-M02-159: el peso inicial utilizado es el de la primera medicion', () => { const v = buscar(/peso.*(inicial|ini)|inicial.*peso/); pm.expect(v, 'peso inicial en ' + JSON.stringify(plano)).to.not.be.undefined; pm.expect(Number(v)).to.eql(Number(pm.collectionVariables.get('expected_peso_inicial'))); });",
      "pm.test('TC-M02-159: el peso final utilizado es el de la ultima medicion', () => { const v = buscar(/peso.*(final|fin)|final.*peso/); pm.expect(v, 'peso final en ' + JSON.stringify(plano)).to.not.be.undefined; pm.expect(Number(v)).to.eql(Number(pm.collectionVariables.get('expected_peso_final'))); });",
      "pm.test('TC-M02-159: los dias transcurridos son los reales entre mediciones', () => { const v = buscar(/dias/); pm.expect(v, 'dias en ' + JSON.stringify(plano)).to.not.be.undefined; pm.expect(Number(v)).to.eql(Number(pm.collectionVariables.get('expected_dias'))); });",
      "pm.test('TC-M02-159: el total de mediciones utilizadas es el real', () => { const v = buscar(/total.*medicion|medicion.*total|n_?mediciones/); pm.expect(v, 'total de mediciones en ' + JSON.stringify(plano)).to.not.be.undefined; pm.expect(Number(v)).to.eql(Number(pm.collectionVariables.get('expected_total_mediciones'))); });",
    ])],
  });

  return {
    info: { name: 'TC-M02-G92 REEVALUACION V3 — TC-M02-154 (RF-50) y TC-M02-159 (RF-51) — CU12',
      description: 'Consumo de los endpoints analiticos de M02 por una identidad tecnica de integracion autorizada. Precondiciones: identidad exacta suministrada, cuenta activa, rol tecnico, permiso READ sobre activos_biologicos y alcance sobre la finca del fixture. Oraculo: TC-M02-154 datos consolidados conforme al contrato en menos de 5 s; TC-M02-159 indicador de ganancia diaria de peso disponible, con el valor recalculado de forma independiente a partir de las mediciones reales.',
      schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json' },
    item: items,
    variable: [
      { key: 'email_tecnico', value: cfg.email },
      { key: 'id_activo', value: String(cfg.id_activo) },
      { key: 'identificador', value: String(cfg.identificador) },
      { key: 'fecha_inicio', value: cfg.fecha_inicio },
      { key: 'fecha_fin', value: cfg.fecha_fin },
      { key: 'rnf_ms', value: String(RNF_MS) },
      { key: 'expected_gpd', value: cfg.expected_gpd },
      { key: 'expected_peso_inicial', value: cfg.expected_peso_inicial },
      { key: 'expected_peso_final', value: cfg.expected_peso_final },
      { key: 'expected_dias', value: String(cfg.expected_dias) },
      { key: 'expected_total_mediciones', value: String(cfg.expected_total_mediciones) },
    ],
  };
}

// -------------------------------------------------------------------------------- OFICIAL
async function oficial() {
  const runId = process.env.G92_V3_RUN_ID;
  if (!runId || !/^G92-REEVAL-V3-\d{8}-\d{6}$/.test(runId)) throw Error('G92_V3_RUN_ID con formato G92-REEVAL-V3-YYYYMMDD-HHMMSS es obligatorio');
  const c = await contexto();
  const g = gate(c);
  // Las condiciones comunes son obligatorias. Si una precondicion de subcaso falta, el subcaso se
  // clasifica BLOQUEADO y el otro se ejecuta: no se oculta el que si es verificable.
  if (!g.comun) throw Error('BLOCKED: precondiciones comunes incompletas, no se ejecuta ningun subcaso ' + JSON.stringify(g.checklist.filter((x) => !x.cumple)));
  if (!Object.values(g.aptitud).some((x) => x.ejecutable)) throw Error('BLOCKED: ningun subcaso es ejecutable ' + JSON.stringify(g.aptitud));

  const R = path.join(__dirname, 'RESULTADOS', runId);
  if (fs.existsSync(R)) throw Error('El RUN_ID ya existe; conservar la evidencia: ' + runId);
  fs.mkdirSync(R, { recursive: true });

  const exp = c.exp;
  const cfg = { base: BASE_TEST, email: M04_EMAIL, id_activo: c.fx.id_activo_biologico, identificador: c.fx.identificador,
    fecha_inicio: exp.fecha_inicial, fecha_fin: exp.fecha_final,
    campos_datos_consolidados: c.contrato.campos_datos_consolidados,
    expected_gpd: exp.por_decimales[4], expected_peso_inicial: exp.peso_inicial, expected_peso_final: exp.peso_final,
    expected_dias: exp.dias, expected_total_mediciones: exp.total_mediciones };
  const collection = construir(cfg);
  fs.writeFileSync(path.join(__dirname, 'test_tc_m02_g92_v3.json'), JSON.stringify(collection, null, 2));

  const newman = require('newman');
  require.resolve('newman-reporter-htmlextra');
  const html = path.join(R, 'newman-g92-v3.html');
  const summary = await new Promise((res, rej) => newman.run({
    collection, reporters: ['htmlextra', 'json'], timeoutRequest: 45000,
    reporter: {
      htmlextra: { export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false,
        skipEnvironmentVars: ['clave_tecnica', 'token_tecnico'], logs: false, silentProgressBar: true,
        title: 'TC-M02-154 / TC-M02-159 — G92 REEVALUACION V3 — TEST' },
      json: { export: path.join(R, 'newman-g92-v3.json') },
    },
    environment: { values: [{ key: 'clave_tecnica', value: process.env.M04_TEST_PASSWORD, enabled: true }] },
  }, (err, sm) => (err ? rej(Error('Newman execution error: ' + clean(err.message))) : res(sm))));
  for (const f of ['newman-g92-v3.html', 'newman-g92-v3.json']) { const p = path.join(R, f); if (fs.existsSync(p)) fs.writeFileSync(p, clean(fs.readFileSync(p, 'utf8'))); }

  const aserciones = []; const respuestas = {};
  for (const ex of summary.run.executions) {
    let b = null; try { b = JSON.parse(ex.response.stream.toString()); } catch { /* sin JSON */ }
    respuestas[ex.item.name] = { status: ex.response?.code ?? null, ms: ex.response?.responseTime ?? null,
      error_code: b?.error_code ?? null,
      indicador: Array.isArray(b?.indicadores) ? (b.indicadores.find((i) => /ganancia[_ ]?peso/i.test(String(i.tipo))) ?? null) : undefined,
      advertencias: b?.advertencias ?? undefined,
      campos: b && !Array.isArray(b) ? Object.keys(b) : undefined };
    for (const a of ex.assertions || []) aserciones.push({ request: ex.item.name, test: a.assertion, ok: !a.error, detalle: a.error ? clean(a.error.message).slice(0, 300) : undefined });
  }
  const fallan = (p) => aserciones.filter((a) => a.test.startsWith(p) && !a.ok);
  const hay = (p) => aserciones.some((a) => a.test.startsWith(p));
  // Un 403 por scope granular es una precondicion ausente (el modulo no esta autorizado para ese
  // tipo_dato), no un defecto de RF-50: el subcaso queda BLOQUEADO, no DESAPROBADO.
  const bloqueadoPorScope = (nombre) => {
    const r = Object.entries(respuestas).find(([k]) => k.includes(nombre));
    return Boolean(r && r[1].status === 403 && r[1].error_code === 'SCOPE_TIPO_DATO_NO_AUTORIZADO');
  };
  const decidir = (caso) => {
    if (!hay(caso)) return 'NO EJECUTADO';
    if (fallan(caso).length === 0) return 'APROBADO';
    return bloqueadoPorScope(caso) ? 'BLOQUEADO' : 'DESAPROBADO';
  };
  const veredicto = { 'TC-M02-154': decidir('TC-M02-154'), 'TC-M02-159': decidir('TC-M02-159') };
  veredicto['TC-M02-G92'] = Object.values(veredicto).every((x) => x === 'APROBADO') ? 'APROBADO'
    : (Object.values(veredicto).includes('DESAPROBADO') ? 'RECHAZADO' : 'BLOQUEADO');
  const issue = veredicto['TC-M02-G92'] === 'APROBADO'
    ? 'INC-M02-90-G92 / #241: BLOQUEO RESUELTO Y VERIFICADO EN TEST. Era un gap de provision de identidad, no un defecto funcional de RF-50/RF-51.'
    : (veredicto['TC-M02-G92'] === 'BLOQUEADO'
      ? 'INC-M02-90-G92 / #241: la identidad tecnica ya autentica y consume RF-51, de modo que el bloqueo historico de identidad quedo superado; queda pendiente un elemento de provision de scope para completar RF-50. No se reabre como defecto funcional.'
      : 'INC-M02-90-G92 / #241: la identidad funciona pero el comportamiento de RF-50/RF-51 no cumple; hallazgo funcional a consolidar aparte.');

  let dev = { ejecutado: false, motivo: 'TEST aprobo: el contraste DEV no es necesario' };
  if (veredicto['TC-M02-G92'] !== 'APROBADO') dev = { ejecutado: false, estado: 'DEV_NO_VERIFICABLE_POR_CREDENCIAL',
    contrato: await contratoDe(BASE_DEV), nota: 'No se dispone de una identidad tecnica DEV conocida y autorizada; no se ensayaron credenciales.' };

  const evidencia = {
    grupo: 'TC-M02-G92', casos: ['TC-M02-154', 'TC-M02-159'], rf: 'RF-50 / RF-51', cu: 'CU12',
    tipo: 'REEVALUACION V3', runId, environment: 'TEST', fecha: new Date().toISOString(),
    preflight: { health: c.health, contrato: c.contrato },
    identidad_tecnica: { ...c.actor, catalogo: c.prov.usuario, permisos_del_rol: c.prov.permisos_del_rol },
    alcance: c.alc, fixture: c.fx,
    expected: { ...exp, a_precision: undefined }, gate: g,
    respuestas_observadas: respuestas, veredicto, incidencia: issue, test_vs_dev: dev,
    newman: { html: 'newman-g92-v3.html', json: 'newman-g92-v3.json', stats: summary.run.stats.assertions, aserciones },
    git: estadoGit(),
  };
  fs.writeFileSync(path.join(R, 'evidencia-g92-v3.json'), clean(JSON.stringify(evidencia, null, 2)));

  console.log('actor', c.actor.correo_electronico, '| rol', c.actor.nombre_rol, '| fincas', JSON.stringify(c.alc.fincas_asignadas));
  console.log('fixture', c.fx.id_activo_biologico, c.fx.identificador, '| pesos', JSON.stringify(c.fx.mediciones_peso.map((p) => p.fecha + ' ' + p.valor)));
  console.log('expected', exp.formula, '=', exp.por_decimales[4]);
  Object.entries(respuestas).forEach(([n, r]) => console.log('  ', String(r.status).padEnd(4), n, r.ms + 'ms', r.error_code || ''));
  console.log('VEREDICTO', JSON.stringify(veredicto, null, 1));
  aserciones.filter((a) => !a.ok).forEach((a) => console.log('  FAIL', a.request, '::', a.test, '->', (a.detalle || '').slice(0, 140)));
  console.log('Evidencia:', path.join(R, 'evidencia-g92-v3.json'));
}

// --------------------------------------------------------------------------------- CIERRE
function cierre() {
  const R = path.join(__dirname, 'RESULTADOS', process.env.G92_V3_RUN_ID);
  const archivo = path.join(R, 'evidencia-g92-v3.json');
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

const FASE = (process.env.G92_FASE || 'preflight').toLowerCase();
(async () => {
  if (FASE === 'preflight') await preflight();
  else if (FASE === 'preparar') await preparar();
  else if (FASE === 'oficial') await oficial();
  else if (FASE === 'cierre') cierre();
  else throw Error('G92_FASE debe ser preflight | preparar | oficial | cierre');
})().catch((e) => { console.log('ERROR:', clean(e.message)); process.exitCode = 1; });
