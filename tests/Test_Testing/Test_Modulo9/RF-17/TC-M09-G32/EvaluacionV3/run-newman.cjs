// TC-M09-G32 V3 — TC-M09-69: verificar que una modificacion de umbral RF-17 actualice la
// configuracion utilizada por Monitoreo.
//
// ADAPTACION RESPECTO A EvaluacionV2/run-newman.cjs
// ------------------------------------------------
// V2 era de solo lectura: no existia forma de correlacionar RF17_BEFORE con MONITORING_BEFORE,
// porque el historial no identificaba el umbral aplicado, y por eso no se ejecuto el PATCH.
// Tras PR #382 el historial expone id_especie, id_umbral_ambiental, valor_min_umbral,
// valor_max_umbral y version_umbral, de modo que la correlacion es demostrable y el flujo puede
// completarse. La adaptacion consiste en: discovery de una lectura historica ya vinculada,
// captura de BEFORE, un unico PATCH, reconciliacion por GET y captura de AFTER sobre la MISMA
// lectura. Se conserva de V2 la seleccion por API, el sanitizado, los actores y el oraculo de
// Monitoreo.
//
// Reutilizable cambiando solo datos de runtime: BASE_URL, actor, credenciales por variable de
// proceso, RUN_ID y, si se desea fijarlos, G32_ID_UMBRAL / G32_ID_TELEMETRIA.
//
// Fases:
//   G32_FASE=preflight  health, contrato, credenciales TEST/DEV, discovery y fixture (sin RUN_ID)
//   G32_FASE=oficial    requiere G32_V3_RUN_ID: unica carpeta, unico PATCH y oraculo
//   G32_FASE=cierre     consolida seguridad y estado de Git dentro de la misma evidencia
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ENVS = {
  TEST: {
    base: 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test',
    correos: ['administador.dev@gmail.com', 'administrador.dev@gmail.com'],
    passVar: 'TEST_ADMIN_PASSWORD',
  },
  DEV: {
    base: 'https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp',
    correos: ['admin.dev@gmail.com', 'administrador.dev@gmail.com'],
    passVar: 'DEV_ADMIN_PASSWORD',
  },
};

// El PATCH RF-17 exige recurso 20 accion 3; la matriz del caso exige Administrador o Veterinario.
const ROLES_PATCH = ['Administrador', 'Veterinario'];
// Campos incorporados por #382 que hacen correlacionable MONITORING_BEFORE con RF17_BEFORE.
const CAMPOS_382 = ['id_especie', 'id_umbral_ambiental', 'valor_min_umbral', 'valor_max_umbral', 'version_umbral'];
// Expansion aplicada al limite superior efectivo de la configuracion (en unidades de la variable).
const DELTA = '2.00';

const PRUEBAS = path.resolve(__dirname, '..', '..', '..', '..', '..', '..', '..');
const FRONT = path.join(PRUEBAS, 'SGPMP-FRONT-END-PWA');
const BACK = path.join(PRUEBAS, 'sgpmp-backend');

const clean = (s) => {
  s = String(s);
  for (const v of ['TEST_ADMIN_PASSWORD', 'DEV_ADMIN_PASSWORD']) if (process.env[v]) s = s.split(process.env[v]).join('[REDACTED]');
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+(?!\[|\{\{)[A-Za-z0-9_.\-]+/g, 'Bearer [REDACTED]');
};

// Decimales exactos en centesimas; nunca coma flotante para comparar configuraciones.
const d2 = (v) => { const [e, d = ''] = String(v).split('.'); const n = e.startsWith('-'); return (n ? -1n : 1n) * BigInt((n ? e.slice(1) : e) + (d + '00').slice(0, 2)); };
const t2 = (c) => { const n = c < 0n; const a = (n ? -c : c).toString().padStart(3, '0'); return (n ? '-' : '') + a.slice(0, -2) + '.' + a.slice(-2); };
const eq = (a, b) => a != null && b != null && d2(a) === d2(b);

async function http(url, { metodo = 'GET', token, cuerpo } = {}) {
  try {
    const r = await fetch(url, { method: metodo, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined, redirect: 'manual', signal: AbortSignal.timeout(45000) });
    let body = null; try { body = await r.json(); } catch { /* sin JSON */ }
    return { status: r.status, body };
  } catch (e) { return { status: 'ERR', error: clean(e.message) }; }
}

async function autenticar(E) {
  const intentos = [];
  for (const correo of E.correos) {
    if (!process.env[E.passVar]) { intentos.push({ correo, status: 'SIN_VARIABLE' }); continue; }
    const r = await http(E.base + '/sesiones/', { metodo: 'POST', cuerpo: { correo_electronico: correo, contrasena: process.env[E.passVar] } });
    if (r.status === 200 && r.body?.token) {
      const me = await http(E.base + '/usuarios/me', { token: r.body.token });
      const actor = { correo: me.body?.correo_electronico, id_usuario: me.body?.id_usuario, rol: me.body?.nombre_rol, estado: me.body?.estado_cuenta };
      const apto = ROLES_PATCH.includes(actor.rol) && actor.estado === 'Activo';
      intentos.push({ correo, status: 200, rol: actor.rol, estado: actor.estado, autorizado_para_patch: apto });
      if (apto) return { token: r.body.token, actor, intentos };
    } else intentos.push({ correo, status: r.status, error_code: r.body?.error_code });
    // Nunca se repite la misma cuenta ni se ensayan contrasenas desconocidas.
  }
  return { token: null, actor: null, intentos };
}

const f10 = (d) => d.toISOString().slice(0, 10);
const urlHist = (base, ini, fin, idSensor) => `${base}/iot/monitoreo/historial?fecha_inicio=${ini}&fecha_fin=${fin}${idSensor ? `&sensor_id=${idSensor}` : ''}&pagina=1&por_pagina=500&orden=ASC`;

async function contrato(base) {
  const api = await http(base + '/openapi.json');
  const paths = api.body?.paths || {};
  const lectura = api.body?.components?.schemas?.LecturaHistoricaSchema?.properties || {};
  return {
    patch_umbral: Boolean(paths['/configuracion/umbrales/{id_umbral_ambiental}']?.patch),
    get_umbrales: Boolean(paths['/configuracion/umbrales']?.get),
    get_auditoria_umbral: Boolean(paths['/configuracion/umbrales/{id_umbral_ambiental}/auditoria']?.get),
    get_historial: Boolean(paths['/iot/monitoreo/historial']?.get),
    campos_382: Object.fromEntries(CAMPOS_382.map((c) => [c, c in lectura])),
    campos_382_completo: CAMPOS_382.every((c) => c in lectura),
  };
}

// Localiza una lectura historica YA vinculada cuyo umbral RF-17 activo sea correlacionable.
async function descubrir(base, token) {
  const hoy = new Date();
  const ventanas = [
    ['historicos', '2024-05-15', '2024-07-01'],
    ['intermedios', '2026-04-01', '2026-06-15'],
    ['recientes', f10(new Date(hoy.getTime() - 89 * 86400e3)), f10(hoy)],
  ];
  const variables = (await http(base + '/configuracion/variables-ambientales', { token })).body?.items || [];
  const umbralesPorEspecie = {};
  const candidatos = [];

  for (const [etiqueta, ini, fin] of ventanas) {
    const r = await http(urlHist(base, ini, fin), { token });
    for (const l of (r.body?.items || [])) {
      if (l.id_activo_biologico == null || l.id_especie == null || l.id_variable == null) continue;
      if (!umbralesPorEspecie[l.id_especie]) umbralesPorEspecie[l.id_especie] = (await http(base + `/configuracion/umbrales?id_especie=${l.id_especie}`, { token })).body?.items || [];
      const activos = umbralesPorEspecie[l.id_especie].filter((x) => x.id_variable_ambiental === l.id_variable && x.es_activo);
      const u = activos.length === 1 ? activos[0] : null;
      const v = variables.find((x) => x.id_variable_ambiental === l.id_variable);
      const correlacion = u ? {
        id_coincide: l.id_umbral_ambiental === u.id_umbral_ambiental,
        min_coincide: eq(l.valor_min_umbral, u.valor_min),
        max_coincide: eq(l.valor_max_umbral, u.valor_max),
      } : null;
      candidatos.push({
        ventana: { etiqueta, fecha_inicio: ini, fecha_fin: fin },
        lectura: { id_telemetria: l.id_telemetria, id_sensor: l.id_sensor, id_variable: l.id_variable, tipo_variable: l.tipo_variable,
          valor: l.valor, unidad_medida: l.unidad_medida, timestamp_captura: l.timestamp_captura,
          id_activo_biologico: l.id_activo_biologico, id_especie: l.id_especie, especie: l.especie,
          estado_semaforo_historico: l.estado_semaforo_historico, id_umbral_ambiental: l.id_umbral_ambiental,
          valor_min_umbral: l.valor_min_umbral, valor_max_umbral: l.valor_max_umbral, version_umbral: l.version_umbral },
        configuraciones_activas_para_la_combinacion: activos.length,
        rf17: u ? { id_umbral_ambiental: u.id_umbral_ambiental, id_especie: u.id_especie, id_variable_ambiental: u.id_variable_ambiental,
          unidad_medida: u.unidad_medida, valor_min: u.valor_min, valor_max: u.valor_max, es_activo: u.es_activo,
          fecha_actualizacion: u.fecha_actualizacion,
          niveles: (u.niveles || []).map((n) => ({ nivel: n.nivel, limite_inferior: n.limite_inferior, limite_superior: n.limite_superior })) } : null,
        variable: v ? { id: v.id_variable_ambiental, nombre: v.nombre, unidad: v.unidad, valor_fisico_min: v.valor_fisico_min, valor_fisico_max: v.valor_fisico_max } : null,
        temperatura: /temperatur/i.test(l.tipo_variable || ''),
      });
    }
  }

  for (const c of candidatos) {
    c.apto = Boolean(c.rf17 && c.rf17.niveles.length === 3 && c.variable
      && c.correlacion_ok !== false
      && c.configuraciones_activas_para_la_combinacion === 1
      && c.lectura.id_umbral_ambiental === c.rf17.id_umbral_ambiental
      && eq(c.lectura.valor_min_umbral, c.rf17.valor_min)
      && eq(c.lectura.valor_max_umbral, c.rf17.valor_max));
  }
  // Preferencia del caso original: variable de temperatura; desempate por id de umbral.
  const aptos = candidatos.filter((c) => c.apto)
    .sort((a, b) => (Number(b.temperatura) - Number(a.temperatura)) || (a.rf17.id_umbral_ambiental - b.rf17.id_umbral_ambiental));
  const fijado = process.env.G32_ID_UMBRAL ? aptos.find((c) => c.rf17.id_umbral_ambiental === Number(process.env.G32_ID_UMBRAL)) : null;
  return { candidatos, elegido: fijado || aptos[0] || null };
}

// RF17_AFTER derivado del BEFORE real. El producto exige (FA-04/FA-05/FA-08) que el rango general
// coincida exactamente con la cobertura de los tres niveles contiguos y quede dentro del rango
// fisico de la variable, asi que la modificacion normaliza el rango general y expande ligeramente
// su limite superior.
function construirAfter(rf17, variable) {
  const orden = [...rf17.niveles].sort((a, b) => Number(d2(a.limite_inferior) - d2(b.limite_inferior)));
  const coberturaMin = orden[0].limite_inferior;
  const coberturaMax = orden[orden.length - 1].limite_superior;
  const fisicoMax = d2(variable.valor_fisico_max);
  const fisicoMin = d2(variable.valor_fisico_min);

  let nuevoMin = coberturaMin;
  let nuevoMax = t2(d2(coberturaMax) + d2(DELTA));
  let extremo = 'superior';
  if (d2(nuevoMax) > fisicoMax) {
    // Sin margen hacia arriba: se expande el limite inferior.
    nuevoMax = coberturaMax;
    nuevoMin = t2(d2(coberturaMin) - d2(DELTA) < fisicoMin ? fisicoMin : d2(coberturaMin) - d2(DELTA));
    extremo = 'inferior';
  }
  const niveles = orden.map((n, i) => ({
    nivel: n.nivel,
    limite_inferior: i === 0 ? nuevoMin : n.limite_inferior,
    limite_superior: i === orden.length - 1 ? nuevoMax : n.limite_superior,
  }));

  const errores = [];
  if (!(d2(nuevoMin) < d2(nuevoMax))) errores.push('valor_min debe ser menor que valor_max');
  if (d2(nuevoMin) < fisicoMin || d2(nuevoMax) > fisicoMax) errores.push('rango fuera de los limites fisicos de la variable');
  if (!eq(niveles[0].limite_inferior, nuevoMin)) errores.push('el primer nivel debe comenzar en valor_min');
  if (!eq(niveles[niveles.length - 1].limite_superior, nuevoMax)) errores.push('el ultimo nivel debe terminar en valor_max');
  for (let i = 0; i < niveles.length - 1; i++) if (!eq(niveles[i].limite_superior, niveles[i + 1].limite_inferior)) errores.push('niveles no contiguos');
  for (const n of niveles) if (!(d2(n.limite_inferior) < d2(n.limite_superior))) errores.push(`nivel ${n.nivel} con amplitud no positiva`);
  const sinCambio = eq(nuevoMin, rf17.valor_min) && eq(nuevoMax, rf17.valor_max);
  if (sinCambio) errores.push('la modificacion propuesta no cambia la configuracion');

  return {
    payload: { valor_min: nuevoMin, valor_max: nuevoMax, niveles },
    cobertura_before: [coberturaMin, coberturaMax], extremo_expandido: extremo, delta: DELTA,
    validaciones_previas: errores.length ? errores : 'todas superadas', valido: errores.length === 0,
  };
}

const dentroDeAlgunNivel = (valor, niveles) => niveles.some((n) => d2(valor) >= d2(n.limite_inferior) && d2(valor) <= d2(n.limite_superior));

function verificarFixture(c) {
  const v = [];
  const ok = (cond, texto) => { v.push({ condicion: texto, cumple: Boolean(cond) }); };
  ok(c, 'existe una lectura historica candidata');
  if (!c) return { checklist: v, completo: false };
  ok(c.lectura.id_telemetria != null, 'lectura historica real con id_telemetria');
  ok(c.lectura.id_activo_biologico != null, 'la lectura tiene id_activo_biologico');
  ok(c.lectura.id_especie != null, 'la lectura tiene id_especie');
  ok(c.rf17 && c.rf17.es_activo, 'la configuracion RF-17 esta activa');
  ok(c.rf17 && c.rf17.niveles.length === 3, 'la configuracion RF-17 tiene tres niveles');
  ok(c.configuraciones_activas_para_la_combinacion === 1, 'existe exactamente una configuracion activa para la combinacion especie+variable');
  ok(c.rf17 && c.lectura.id_variable === c.rf17.id_variable_ambiental, 'la lectura y la configuracion RF-17 usan la misma variable');
  ok(c.lectura.id_umbral_ambiental != null, 'el historial devuelve id_umbral_ambiental');
  ok(c.rf17 && c.lectura.id_umbral_ambiental === c.rf17.id_umbral_ambiental, 'id_umbral_ambiental del historial == RF-17 elegido');
  ok(c.rf17 && eq(c.lectura.valor_min_umbral, c.rf17.valor_min), 'valor_min_umbral del historial == valor_min del RF-17');
  ok(c.rf17 && eq(c.lectura.valor_max_umbral, c.rf17.valor_max), 'valor_max_umbral del historial == valor_max del RF-17');
  return { checklist: v, completo: v.every((x) => x.cumple) };
}

// ---------------------------------------------------------------------------------- PREFLIGHT
async function preflight() {
  const salida = { fase: 'preflight', fecha: new Date().toISOString(), git: estadoGit(), entornos: {} };
  for (const [nombre, E] of Object.entries(ENVS)) {
    const info = { base: E.base, health: (await http(E.base + '/health')).status };
    const auth = await autenticar(E);
    info.logins = auth.intentos; info.actor = auth.actor; info.autorizado = Boolean(auth.token);
    if (auth.token) {
      info.contrato = await contrato(E.base);
      const d = await descubrir(E.base, auth.token);
      info.candidatos = d.candidatos.length;
      info.aptos = d.candidatos.filter((c) => c.apto).length;
      info.elegido = d.elegido;
      info.fixture = verificarFixture(d.elegido);
      if (d.elegido) info.after_propuesto = construirAfter(d.elegido.rf17, d.elegido.variable);
    }
    salida.entornos[nombre] = info;
  }
  const destino = process.env.G32_PREFLIGHT_OUT || path.join(require('os').tmpdir(), 'g32-v3-preflight.json');
  fs.writeFileSync(destino, clean(JSON.stringify(salida, null, 2)));
  for (const [n, i] of Object.entries(salida.entornos)) {
    console.log('==', n, 'health', i.health, '| actor', i.actor ? `${i.actor.correo} ${i.actor.rol} ${i.actor.estado}` : '-');
    if (i.contrato) console.log('   contrato', JSON.stringify(i.contrato));
    console.log('   candidatos', i.candidatos, '| aptos', i.aptos);
    if (i.fixture) console.log('   fixture completo:', i.fixture.completo, i.fixture.completo ? '' : JSON.stringify(i.fixture.checklist.filter((x) => !x.cumple)));
    if (i.elegido) console.log('   elegido: lectura', i.elegido.lectura.id_telemetria, i.elegido.lectura.tipo_variable, '| especie', i.elegido.lectura.id_especie, i.elegido.lectura.especie, '| umbral', i.elegido.rf17.id_umbral_ambiental, `${i.elegido.rf17.valor_min}-${i.elegido.rf17.valor_max}`, JSON.stringify(i.elegido.rf17.niveles));
    if (i.after_propuesto) console.log('   AFTER propuesto', JSON.stringify(i.after_propuesto));
  }
  console.log('\nPreflight ->', destino, '\nCrear RUN_ID solo si el fixture esta completo y el AFTER es valido.');
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

// ------------------------------------------------------------------------------------ OFICIAL
async function oficial() {
  const runId = process.env.G32_V3_RUN_ID;
  if (!runId || !/^G32-REEVAL-V3-\d{8}-\d{6}$/.test(runId)) throw Error('G32_V3_RUN_ID con formato G32-REEVAL-V3-YYYYMMDD-HHMMSS es obligatorio');
  const E = ENVS.TEST;

  const auth = await autenticar(E);
  if (!auth.token) throw Error('BLOCKED: ninguna cuenta autorizada (Administrador/Veterinario) autentico en TEST ' + JSON.stringify(auth.intentos));
  const contratoTest = await contrato(E.base);
  if (!contratoTest.campos_382_completo) throw Error('BLOCKED: el contrato desplegado en TEST no expone los campos de #382; no se ejecuta PATCH ' + JSON.stringify(contratoTest.campos_382));
  const d = await descubrir(E.base, auth.token);
  const fixture = verificarFixture(d.elegido);
  if (!fixture.completo) throw Error('BLOCKED: fixture incompleto, no se ejecuta PATCH ' + JSON.stringify(fixture.checklist.filter((x) => !x.cumple)));
  const after = construirAfter(d.elegido.rf17, d.elegido.variable);
  if (!after.valido) throw Error('BLOCKED: la modificacion propuesta no es valida ' + JSON.stringify(after.validaciones_previas));

  const R = path.join(__dirname, 'RESULTADOS', runId);
  if (fs.existsSync(R)) throw Error('El RUN_ID ya existe; conservar la evidencia: ' + runId);
  fs.mkdirSync(R, { recursive: true });

  const token = auth.token;
  const C = d.elegido;
  const idUmbral = C.rf17.id_umbral_ambiental;
  const idTelemetria = C.lectura.id_telemetria;
  const ven = C.ventana;

  const leerUmbral = async () => {
    const r = await http(E.base + `/configuracion/umbrales?id_especie=${C.lectura.id_especie}`, { token });
    const u = (r.body?.items || []).find((x) => x.id_umbral_ambiental === idUmbral);
    return { status: r.status, umbral: u ? { id_umbral_ambiental: u.id_umbral_ambiental, id_especie: u.id_especie, id_variable_ambiental: u.id_variable_ambiental,
      unidad_medida: u.unidad_medida, valor_min: u.valor_min, valor_max: u.valor_max, es_activo: u.es_activo, fecha_actualizacion: u.fecha_actualizacion,
      estado_sincronizacion: u.estado_sincronizacion,
      niveles: (u.niveles || []).map((n) => ({ nivel: n.nivel, limite_inferior: n.limite_inferior, limite_superior: n.limite_superior })) } : null };
  };
  const leerLectura = async () => {
    const r = await http(urlHist(E.base, ven.fecha_inicio, ven.fecha_fin, C.lectura.id_sensor), { token });
    const l = (r.body?.items || []).find((x) => x.id_telemetria === idTelemetria);
    return { status: r.status, lectura: l ? { id_telemetria: l.id_telemetria, valor: l.valor, unidad_medida: l.unidad_medida,
      timestamp_captura: l.timestamp_captura, id_activo_biologico: l.id_activo_biologico, id_especie: l.id_especie, especie: l.especie,
      id_variable: l.id_variable, tipo_variable: l.tipo_variable, estado_semaforo_historico: l.estado_semaforo_historico,
      id_umbral_ambiental: l.id_umbral_ambiental, valor_min_umbral: l.valor_min_umbral, valor_max_umbral: l.valor_max_umbral,
      version_umbral: l.version_umbral } : null };
  };
  const leerDashboard = async () => {
    const r = await http(E.base + '/iot/monitoreo/dashboard?pagina=1&por_pagina=50', { token });
    const s = (r.body?.sensores || []).find((x) => x.id_sensor === C.lectura.id_sensor);
    return { status: r.status, sensor: s ? { id_sensor: s.id_sensor, tipo_variable: s.tipo_variable, ultimo_valor: s.ultimo_valor,
      ultimo_timestamp_captura: s.ultimo_timestamp_captura, estado_semaforo: s.estado_semaforo, dato_desactualizado: s.dato_desactualizado } : null };
  };

  const rf17Before = await leerUmbral();
  const monBefore = await leerLectura();
  const dashBefore = await leerDashboard();

  const correlacionBefore = {
    id_umbral_ambiental: { monitoreo: monBefore.lectura?.id_umbral_ambiental, rf17: rf17Before.umbral?.id_umbral_ambiental, coincide: monBefore.lectura?.id_umbral_ambiental === rf17Before.umbral?.id_umbral_ambiental },
    valor_min: { monitoreo: monBefore.lectura?.valor_min_umbral, rf17: rf17Before.umbral?.valor_min, coincide: eq(monBefore.lectura?.valor_min_umbral, rf17Before.umbral?.valor_min) },
    valor_max: { monitoreo: monBefore.lectura?.valor_max_umbral, rf17: rf17Before.umbral?.valor_max, coincide: eq(monBefore.lectura?.valor_max_umbral, rf17Before.umbral?.valor_max) },
    version: { monitoreo: monBefore.lectura?.version_umbral, rf17: rf17Before.umbral?.fecha_actualizacion },
  };
  const beforeCorrelacionado = correlacionBefore.id_umbral_ambiental.coincide && correlacionBefore.valor_min.coincide && correlacionBefore.valor_max.coincide;
  if (!beforeCorrelacionado) throw Error('BLOCKED: MONITORING_BEFORE no representa el mismo RF17_BEFORE; no se ejecuta PATCH ' + JSON.stringify(correlacionBefore));

  // ------------------------------------------------------------------ UNICO PATCH
  const cuerpo = { ...after.payload };
  if (rf17Before.umbral.fecha_actualizacion != null) cuerpo.fecha_actualizacion = rf17Before.umbral.fecha_actualizacion;
  const patch = await http(E.base + `/configuracion/umbrales/${idUmbral}`, { metodo: 'PATCH', token, cuerpo });
  const escritura = { endpoint: `PATCH /configuracion/umbrales/${idUmbral}`, payload: cuerpo, status: patch.status,
    body: patch.body ? JSON.parse(clean(JSON.stringify(patch.body))) : null, reintento: false };

  // Reconciliacion inmediata por GET: el PATCH puede fallar por un efecto colateral posterior al
  // commit, asi que el estado real se determina leyendo, nunca reintentando.
  const rf17Reconciliado = await leerUmbral();
  const persistio = Boolean(rf17Reconciliado.umbral
    && eq(rf17Reconciliado.umbral.valor_min, after.payload.valor_min)
    && eq(rf17Reconciliado.umbral.valor_max, after.payload.valor_max));
  const reconciliacion = { motivo: patch.status === 200 ? 'verificacion posterior a respuesta 200' : `respuesta ${patch.status}: se determina el estado real por GET, sin reintentar`,
    persistio, rf17_tras_get: rf17Reconciliado.umbral };

  let rf17After = null; let monAfter = null; let dashAfter = null; let relectura = null; let oraculo = null;
  if (persistio) {
    rf17After = rf17Reconciliado;
    monAfter = await leerLectura();
    dashAfter = await leerDashboard();

    const esperado = { id_umbral_ambiental: idUmbral, valor_min: after.payload.valor_min, valor_max: after.payload.valor_max };
    const evaluar = (m) => ({
      id_umbral_ambiental: { esperado: esperado.id_umbral_ambiental, obtenido: m.lectura?.id_umbral_ambiental, cumple: m.lectura?.id_umbral_ambiental === esperado.id_umbral_ambiental },
      valor_min_umbral: { esperado: esperado.valor_min, obtenido: m.lectura?.valor_min_umbral, cumple: eq(m.lectura?.valor_min_umbral, esperado.valor_min) },
      valor_max_umbral: { esperado: esperado.valor_max, obtenido: m.lectura?.valor_max_umbral, cumple: eq(m.lectura?.valor_max_umbral, esperado.valor_max) },
      version_umbral: { esperado: rf17After.umbral?.fecha_actualizacion, obtenido: m.lectura?.version_umbral,
        cumple: m.lectura?.version_umbral != null && rf17After.umbral?.fecha_actualizacion != null
          && new Date(m.lectura.version_umbral).getTime() === new Date(rf17After.umbral.fecha_actualizacion).getTime() },
      ya_no_usa_before: { valor_max_before: rf17Before.umbral?.valor_max, cumple: !eq(m.lectura?.valor_max_umbral, rf17Before.umbral?.valor_max) },
    });
    let ev = evaluar(monAfter);
    // Una sola relectura confirmatoria de solo lectura si hay discrepancia inesperada.
    if (!Object.values(ev).every((x) => x.cumple)) {
      relectura = { motivo: 'discrepancia inesperada en MONITORING_AFTER: una unica relectura confirmatoria', resultado: await leerLectura() };
      ev = evaluar(relectura.resultado);
      monAfter = relectura.resultado;
    }
    oraculo = {
      before_correlacionado: beforeCorrelacionado, correlacion_before: correlacionBefore,
      rf17_cambio: !eq(rf17After.umbral?.valor_max, rf17Before.umbral?.valor_max) || !eq(rf17After.umbral?.valor_min, rf17Before.umbral?.valor_min),
      after: ev,
      aprobado: beforeCorrelacionado && Object.values(ev).every((x) => x.cumple),
    };
  }

  // Auditoria RF-17: prueba en vivo de la transicion BEFORE -> AFTER
  const aud = await http(E.base + `/configuracion/umbrales/${idUmbral}/auditoria`, { token });
  const auditoria = { status: aud.status, total: aud.body?.total ?? null,
    registros: (aud.body?.items || []).slice(-3).map((a) => ({ id_auditoria_umbral: a.id_auditoria_umbral, tipo_operacion: a.tipo_operacion,
      id_usuario: a.id_usuario, fecha_gestion: a.fecha_gestion, valores_anteriores: a.valores_anteriores, valores_nuevos: a.valores_nuevos })) };

  // Evidencia secundaria: clasificacion semaforica de la lectura
  const semaforo = {
    antes: monBefore.lectura?.estado_semaforo_historico, despues: monAfter?.lectura?.estado_semaforo_historico,
    valor_lectura: monBefore.lectura?.valor,
    dentro_de_algun_nivel_before: dentroDeAlgunNivel(monBefore.lectura?.valor ?? '0', rf17Before.umbral?.niveles || []),
    dentro_de_algun_nivel_after: rf17After ? dentroDeAlgunNivel(monBefore.lectura?.valor ?? '0', rf17After.umbral?.niveles || []) : null,
    nota: 'Evidencia secundaria. La modificacion no se diseno para forzar un cambio de color: el criterio principal es que Monitoreo utilice el nuevo rango y version.',
  };

  // ------------------------------------------------------------------------ Newman
  const newman = require('newman');
  require.resolve('newman-reporter-htmlextra');
  const html = path.join(R, 'newman-g32-v3.html');
  const collection = JSON.parse(fs.readFileSync(path.join(__dirname, 'TC-M09-G32-reevaluacion-v3.postman_collection.json'), 'utf8'));
  const vars = {
    base_url: E.base, token, id_especie: C.lectura.id_especie, id_umbral: idUmbral, id_telemetria: idTelemetria,
    id_sensor: C.lectura.id_sensor, fecha_inicio: ven.fecha_inicio, fecha_fin: ven.fecha_fin,
    before_valor_min: rf17Before.umbral.valor_min, before_valor_max: rf17Before.umbral.valor_max,
    after_valor_min: after.payload.valor_min, after_valor_max: after.payload.valor_max,
  };
  const summary = await new Promise((res, rej) => newman.run({
    collection, reporters: ['htmlextra', 'json'], timeoutRequest: 45000,
    reporter: {
      htmlextra: { export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false, skipEnvironmentVars: ['token'], logs: false, silentProgressBar: true, title: 'TC-M09-69 — G32 REEVALUACION V3 — TEST' },
      json: { export: path.join(R, 'newman-g32-v3.json') },
    },
    environment: { values: Object.entries(vars).map(([key, value]) => ({ key, value: String(value), enabled: true })) },
  }, (err, sm) => (err ? rej(Error('Newman execution error: ' + clean(err.message))) : res(sm))));
  for (const f of ['newman-g32-v3.html', 'newman-g32-v3.json']) { const p = path.join(R, f); if (fs.existsSync(p)) fs.writeFileSync(p, clean(fs.readFileSync(p, 'utf8'))); }
  const aserciones = [];
  for (const ex of summary.run.executions) for (const a of ex.assertions || []) aserciones.push({ request: ex.item.name, test: a.assertion, ok: !a.error, detalle: a.error ? clean(a.error.message).slice(0, 300) : undefined });

  // ------------------------------------------------------- Contraste DEV (solo si TEST no aprueba)
  let dev = { ejecutado: false, motivo: 'TEST aprobo: el contraste DEV no es necesario' };
  if (!oraculo?.aprobado) {
    const authDev = await autenticar(ENVS.DEV);
    if (!authDev.token) dev = { ejecutado: false, estado: 'DEV_NO_VERIFICABLE_POR_CREDENCIAL', logins: authDev.intentos };
    else {
      const cDev = await contrato(ENVS.DEV.base);
      const dDev = await descubrir(ENVS.DEV.base, authDev.token);
      dev = { ejecutado: true, tipo: 'SOLO_LECTURA', actor: authDev.actor, contrato: cDev,
        candidatos: dDev.candidatos.length, aptos: dDev.candidatos.filter((x) => x.apto).length,
        elegido: dDev.elegido ? { lectura: dDev.elegido.lectura, rf17: dDev.elegido.rf17 } : null,
        nota: 'Contraste de solo lectura: no se ejecuto PATCH en DEV.' };
    }
  }

  const evidencia = {
    grupo: 'TC-M09-G32', caso: 'TC-M09-69', rf: 'RF-17', tipo: 'REEVALUACION V3',
    runId, environment: 'TEST', fecha: new Date().toISOString(),
    preflight: { health: (await http(E.base + '/health')).status, contrato: contratoTest },
    actor: auth.actor,
    fixture: {
      lectura_historica: C.lectura, configuracion_rf17: C.rf17, variable: C.variable,
      ventana_consulta: ven, checklist: fixture.checklist, completo: fixture.completo,
      candidatos_evaluados: d.candidatos.map((x) => ({ id_telemetria: x.lectura.id_telemetria, tipo_variable: x.lectura.tipo_variable,
        id_especie: x.lectura.id_especie, id_umbral_ambiental_historial: x.lectura.id_umbral_ambiental, apto: x.apto })),
    },
    rf17_before: rf17Before.umbral, monitoring_before: { historial: monBefore.lectura, dashboard: dashBefore.sensor },
    correlacion_before: correlacionBefore,
    modificacion: { criterio: 'El rango general se normaliza a la cobertura real de los tres niveles y su limite '
      + after.extremo_expandido + ' se expande en ' + DELTA + ' unidades, dentro del rango fisico de la variable.',
      cobertura_before: after.cobertura_before, validaciones_previas: after.validaciones_previas, escritura },
    reconciliacion,
    rf17_after: rf17After?.umbral ?? null, monitoring_after: { historial: monAfter?.lectura ?? null, dashboard: dashAfter?.sensor ?? null },
    relectura_confirmatoria: relectura,
    oraculo, semaforo, auditoria, test_vs_dev: dev,
    newman: { html: 'newman-g32-v3.html', json: 'newman-g32-v3.json', stats: summary.run.stats.assertions, aserciones },
    git: estadoGit(),
  };
  fs.writeFileSync(path.join(R, 'evidencia-g32-v3.json'), clean(JSON.stringify(evidencia, null, 2)));

  console.log('Fixture: lectura', idTelemetria, C.lectura.tipo_variable, '| especie', C.lectura.id_especie, C.lectura.especie, '| umbral', idUmbral);
  console.log('BEFORE correlacionado:', beforeCorrelacionado, '|', `${rf17Before.umbral.valor_min}-${rf17Before.umbral.valor_max}`);
  console.log('PATCH', escritura.status, '| persistio:', persistio, '| AFTER', rf17After ? `${rf17After.umbral.valor_min}-${rf17After.umbral.valor_max}` : '-');
  if (oraculo) { console.log('ORACULO aprobado:', oraculo.aprobado); Object.entries(oraculo.after).forEach(([k, v]) => console.log('  ', v.cumple ? 'OK ' : 'FAIL', k, JSON.stringify(v))); }
  console.log('Semaforo antes/despues:', semaforo.antes, '/', semaforo.despues);
  aserciones.forEach((a) => console.log(a.ok ? '  PASS' : '  FAIL', a.request, '::', a.test, a.ok ? '' : '-> ' + (a.detalle || '').slice(0, 140)));
  console.log('Evidencia:', path.join(R, 'evidencia-g32-v3.json'));
}

// ------------------------------------------------------------------------------------- CIERRE
function cierre() {
  const R = path.join(__dirname, 'RESULTADOS', process.env.G32_V3_RUN_ID);
  const archivo = path.join(R, 'evidencia-g32-v3.json');
  const evidencia = JSON.parse(fs.readFileSync(archivo, 'utf8'));
  const patrones = [
    ['password', /"?(contrasena|password|contraseña)"?\s*[:=]\s*"[^"\[]{3,}"/i],
    ['jwt', /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\./],
    ['authorization', /"?authorization"?\s*[:=]\s*"(?!\[)[^"]*"/i],
    ['bearer', /Bearer\s+(?!\[)[A-Za-z0-9_.\-]{10,}/],
    ['refresh_token', /"refresh_token"\s*:\s*"[^"\[]{3,}"/],
    ['access_key', /"access_key"\s*:\s*"(?!\[)[^"]{3,}"/],
    ['cookie', /"?set-cookie"?\s*[:=]\s*"[^"\[]{3,}"/i],
    ['connstring', /postgres(ql)?:\/\/[^\s"]+/i],
  ];
  const hallazgos = [];
  let total = 0;
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

const FASE = (process.env.G32_FASE || 'oficial').toLowerCase();
(async () => {
  if (FASE === 'preflight') await preflight();
  else if (FASE === 'oficial') await oficial();
  else if (FASE === 'cierre') cierre();
  else throw Error('G32_FASE debe ser preflight | oficial | cierre');
})().catch((e) => { console.log('ERROR:', clean(e.message)); process.exitCode = 1; });
