// TC-M02-G92 V4 — RF-50 / RF-51 · CU12. TC-M02-154 (datos consolidados) y TC-M02-159 (ganancia
// diaria de peso) consumidos por la identidad tecnica M04.
//
// POR QUE EXISTE ESTE RUNNER (secciones 12 y 23 del paquete)
// ---------------------------------------------------------
// La fase `oficial` de EvaluacionV3/run-newman.cjs escribe dentro de EvaluacionV3/RESULTADOS/ y
// reescribe su propia coleccion `test_tc_m02_g92_v3.json`. Ejecutarla modificaria V3, que debe
// quedar intacta. Este runner es el minimo necesario para no tocarla.
//
// NO se genera una coleccion V4: se REUTILIZA la de V3 tal como esta en disco, en memoria y en
// modo lectura, con sus 26 assertions y sus variables. El unico ajuste es el host de las URLs,
// que se apunta a la URL TEST oficial vigente (cambio permitido por la seccion 12). Las
// assertions, el oraculo, el actor, los endpoints, el fixture y los expected no se tocan.
//
// La contrasena llega por la variable de entorno M04_TEST_PASSWORD, se entrega a Newman como
// variable de entorno de la ejecucion y nunca se escribe en los artefactos. El reporte de Newman
// se sanea antes de guardarse.
//
// Uso:
//   NODE_PATH=<node_modules global> G92_V4_RUN_ID=G92-REEVAL-V4-YYYYMMDD-HHMMSS \
//   M04_TEST_PASSWORD=... node run-v4.cjs
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

// URL TEST oficial adoptada para V4. El dominio historico sslip.io sirve el mismo despliegue
// (sha256 de /openapi.json identico), de modo que el cambio de dominio no altera la prueba.
const BASE_TEST = 'https://api.inmero.co/back-sigab-test';
const BASE_V3 = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const M04_EMAIL = 'integracion.tes@gmail.com';
const RNF_MS = 5000;

const AQUI = __dirname;
const V3 = path.join(AQUI, '..', 'EvaluacionV3');
const COLECCION_V3 = path.join(V3, 'test_tc_m02_g92_v3.json');
const PRUEBAS = path.resolve(AQUI, '..', '..', '..', '..', '..', '..', '..');
const BACK = path.join(PRUEBAS, 'sgpmp-backend');
const FRONT = path.join(PRUEBAS, 'SGPMP-FRONT-END-PWA');

// --- Sanitizado: contrasenas, JWT y Authorization ---
const secretos = new Set();
for (const v of ['M04_TEST_PASSWORD', 'QA_ADMIN_PASSWORD']) if (process.env[v]) secretos.add(process.env[v]);
const clean = (s) => {
  s = String(s);
  for (const x of secretos) s = s.split(x).join('[REDACTED]');
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+(?!\[|\{\{)[A-Za-z0-9_.\-]+/g, 'Bearer [REDACTED]')
    // El login responde con Set-Cookie: refresh_token=...; el reporte de Newman guarda las
    // cabeceras de respuesta tal cual, de modo que hay que redactar el valor de la cookie.
    .replace(/(refresh_token|access_token|session|csrftoken)=(?!\[)[^;",\s]+/gi, '$1=[REDACTED]');
};

// --- Decimales exactos con BigInt: el expected del indicador se recalcula sin coma flotante ---
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
    const r = await fetch(url, {
      method: metodo,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      redirect: 'manual', signal: AbortSignal.timeout(45000),
    });
    let body = null; try { body = await r.json(); } catch { /* sin JSON */ }
    return { status: r.status, body, ms: Date.now() - t0, contentType: r.headers.get('content-type') };
  } catch (e) { return { status: 'ERR', error: clean(e.message), ms: Date.now() - t0 }; }
}

function git(repo, ...args) {
  try { return execFileSync('git', args, { cwd: repo, encoding: 'utf8' }).trim(); }
  catch (e) { return 'ERROR: ' + String(e.message).slice(0, 120); }
}

function estadoGit() {
  const out = {};
  for (const [nombre, repo] of [['backend', BACK], ['frontend', FRONT]]) {
    out[nombre] = {
      rama: git(repo, 'branch', '--show-current'),
      head: git(repo, 'rev-parse', 'HEAD'),
      origin_test: git(repo, 'rev-parse', 'origin/test'),
      head_vs_origin_test: git(repo, 'rev-list', '--left-right', '--count', 'HEAD...origin/test'),
      status: git(repo, 'status', '--short') || '(limpio)',
      diff: git(repo, 'diff', '--stat') || '(vacio)',
      indice: git(repo, 'diff', '--cached', '--stat') || '(vacio)',
    };
  }
  return out;
}

// Expected independiente: ganancia diaria = (peso_final - peso_inicial) / dias transcurridos.
// Se recalcula AQUI, antes de ejecutar el oraculo; nunca se toma el valor de la API.
function expectedGpd(mediciones) {
  const primera = mediciones[0];
  const ultima = mediciones[mediciones.length - 1];
  const dias = diasEntre(primera.fecha, ultima.fecha);
  const dec = Math.max(decimalesDe(primera.valor), decimalesDe(ultima.valor), 2);
  const delta = esc(ultima.valor, dec) - esc(primera.valor, dec);
  const divisor = BigInt(dias) * (10n ** BigInt(dec));
  return {
    peso_inicial: primera.valor, peso_final: ultima.valor,
    fecha_inicial: primera.fecha, fecha_final: ultima.fecha,
    dias, total_mediciones: mediciones.length,
    formula: `(${ultima.valor} - ${primera.valor}) / ${dias}`,
    por_decimales: Object.fromEntries([2, 3, 4, 5, 6].map((n) => [n, dividir(delta, divisor, n)])),
  };
}

(async () => {
  const runId = process.env.G92_V4_RUN_ID;
  if (!runId || !/^G92-REEVAL-V4-\d{8}-\d{6}$/.test(runId)) throw Error('G92_V4_RUN_ID con formato G92-REEVAL-V4-YYYYMMDD-HHMMSS es obligatorio');
  if (!process.env.M04_TEST_PASSWORD) throw Error('Falta M04_TEST_PASSWORD: la credencial se pasa por variable de entorno');
  const R = path.join(AQUI, 'RESULTADOS', runId);
  fs.mkdirSync(R, { recursive: true });

  const gitInicial = estadoGit();

  // ---- Contexto del RUN: identidad, contrato, fixture, alcance y expected independiente ----
  const health = await http(BASE_TEST + '/health');
  const oa = await http(BASE_TEST + '/openapi.json');
  const rutas = oa.body?.paths || {};
  const esquemas = oa.body?.components?.schemas || {};
  const contrato = {
    health: health.status, openapi: oa.status, version: oa.body?.info?.version ?? null,
    datos_consolidados: Boolean(rutas['/activos-biologicos/{id_activo}/datos-consolidados']?.get),
    indicadores: Boolean(rutas['/activos-biologicos/{id_activo}/indicadores']?.get),
    campos_datos_consolidados: Object.keys(esquemas.DatosConsolidadosResponse?.properties || {}),
    campos_indicador: Object.keys(esquemas.IndicadorZootecnicoResponse?.properties || {}),
  };

  const lg = await http(BASE_TEST + '/sesiones/', { metodo: 'POST', cuerpo: { correo_electronico: M04_EMAIL, contrasena: process.env.M04_TEST_PASSWORD } });
  const token = lg.body?.token;
  if (!token) throw Error('La identidad tecnica no autentico: ' + lg.status);
  const me = await http(BASE_TEST + '/usuarios/me', { token });
  const perm = await http(BASE_TEST + '/sesiones/me/permisos', { token });
  const permisos = perm.body?.permisos || [];
  const recursosScope = { eventos: 60, fases: 61, estado: 62, metricas: 63 };
  const actor = {
    correo: me.body?.correo_electronico ?? null, id_usuario: me.body?.id_usuario ?? null,
    nombre_rol: me.body?.nombre_rol ?? null, estado_cuenta: me.body?.estado_cuenta ?? null,
    loginEstado: lg.status, tokenPersistido: false,
    es_la_identidad_del_caso: me.body?.correo_electronico === M04_EMAIL,
    sustituidaPorOtraIdentidad: false,
    permisos_totales: permisos.length,
    recursos_con_read: permisos.filter((p) => Number(p.id_accion) === 2).map((p) => p.id_recurso).sort((a, b) => a - b),
    read_activos_biologicos: permisos.some((p) => Number(p.id_recurso) === 29 && Number(p.id_accion) === 2),
    scopes: Object.fromEntries(Object.entries(recursosScope).map(([k, rec]) => [k, permisos.some((p) => Number(p.id_recurso) === rec && Number(p.id_accion) === 2)])),
  };

  // Fixture y mediciones, leidos con la propia identidad tecnica.
  const det = await http(BASE_TEST + `/activos-biologicos/${295}`, { token });
  const ev = await http(BASE_TEST + `/activos-biologicos/${295}/eventos`, { token });
  const pesos = (ev.body?.eventos || [])
    .filter((e) => e.crecimiento && /peso/i.test(String(e.crecimiento.tipo_medicion ?? '')))
    .map((e) => ({ id_eventos: e.id_eventos, fecha: String(e.fecha).slice(0, 10),
      valor: String(e.crecimiento.valor_medicion ?? e.crecimiento.nuevo_peso_promedio), unidad: e.crecimiento.unidad_medida }))
    .sort((a, b) => (a.fecha < b.fecha ? -1 : 1));
  const fechasDistintas = [...new Set(pesos.map((p) => p.fecha))].length;
  const fixture = {
    id_activo_biologico: det.body?.id_activo_biologico ?? null,
    identificador: det.body?.identificador ?? null, tipo: det.body?.tipo ?? null,
    nombre_estado: det.body?.nombre_estado ?? null,
    id_infraestructura: det.body?.id_infraestructura ?? null,
    id_especie: det.body?.id_especie ?? null,
    mediciones_peso: pesos, fechas_distintas: fechasDistintas,
    leidoConLaIdentidadTecnica: true, reutilizadoDeV3: true,
  };
  const exp = pesos.length >= 2 ? expectedGpd(pesos) : null;
  if (!exp) throw Error('El fixture no conserva dos mediciones de peso');

  // Alcance efectivo de la identidad sobre el activo.
  const listado = await http(BASE_TEST + '/activos-biologicos?pagina=1&por_pagina=50', { token });
  const alcance = {
    activos_visibles: listado.body?.total_registros ?? (listado.body?.registros || []).length,
    ve_el_activo: det.status === 200,
    escriturasDePreparacion: 0,
    notaPreparacion: 'No se ejecuto ninguna escritura de preparacion: la identidad ya tiene alcance '
                   + 'sobre el activo del fixture. No se modificaron fincas, scopes ni rol.',
  };

  // ---- Coleccion: la de V3, reutilizada en memoria. Solo se reapunta el host. ----
  const crudo = fs.readFileSync(COLECCION_V3, 'utf8');
  const coleccion = JSON.parse(crudo.split(BASE_V3).join(BASE_TEST));
  const assertionsDeclaradas = (crudo.match(/pm\.test\(/g) || []).length;
  const reutilizacion = {
    coleccionOrigen: 'EvaluacionV3/test_tc_m02_g92_v3.json',
    coleccionV4Generada: false,
    motivo: 'La coleccion V3 se reutiliza tal cual, en memoria y en modo lectura. No se duplica.',
    unicoAjuste: `host de las URLs: ${BASE_V3} -> ${BASE_TEST}`,
    assertionsDeclaradasEnLaColeccion: assertionsDeclaradas,
    variablesDeLaColeccion: Object.fromEntries((coleccion.variable || []).map((v) => [v.key, v.value])),
    assertionsModificadas: 0, assertionsEliminadas: 0, assertionsAnadidas: 0,
  };

  // Comprobacion de que el fixture y los expected de la coleccion V3 siguen siendo los validos.
  const vc = reutilizacion.variablesDeLaColeccion;
  const coherencia = {
    id_activo: Number(vc.id_activo) === fixture.id_activo_biologico,
    identificador: vc.identificador === fixture.identificador,
    fecha_inicio: vc.fecha_inicio === exp.fecha_inicial,
    fecha_fin: vc.fecha_fin === exp.fecha_final,
    expected_gpd: vc.expected_gpd === exp.por_decimales[4],
    expected_peso_inicial: vc.expected_peso_inicial === exp.peso_inicial,
    expected_peso_final: vc.expected_peso_final === exp.peso_final,
    expected_dias: Number(vc.expected_dias) === exp.dias,
    expected_total_mediciones: Number(vc.expected_total_mediciones) === exp.total_mediciones,
    rnf_ms: Number(vc.rnf_ms) === RNF_MS,
  };
  coherencia.todo = Object.values(coherencia).every(Boolean);
  if (!coherencia.todo) throw Error('El fixture de la coleccion V3 ya no coincide con el descubierto: ' + JSON.stringify(coherencia));

  // ---- Ejecucion oficial con Newman ----
  const newman = require('newman');
  const summary = await new Promise((res, rej) => newman.run({
    collection: coleccion, reporters: ['json'], timeoutRequest: 45000,
    reporter: { json: { export: path.join(R, 'newman-g92-v4.json') } },
    environment: { values: [{ key: 'clave_tecnica', value: process.env.M04_TEST_PASSWORD, enabled: true }] },
  }, (err, s) => (err ? rej(err) : res(s))));

  // Saneado del reporte de Newman antes de dejarlo en disco.
  const reporte = path.join(R, 'newman-g92-v4.json');
  if (fs.existsSync(reporte)) fs.writeFileSync(reporte, clean(fs.readFileSync(reporte, 'utf8')));

  const porNombre = (frag) => summary.run.executions.find((e) => e.item.name.includes(frag)) || null;
  const resumenEjecucion = (e) => {
    if (!e) return null;
    const cuerpo = (() => { try { return JSON.parse(e.response?.stream?.toString() || 'null'); } catch { return null; } })();
    return {
      request: { metodo: e.request.method, url: clean(e.request.url.toString()) },
      http: e.response?.code ?? null,
      contentType: e.response?.headers?.get?.('content-type') ?? null,
      tiempo_ms: e.response?.responseTime ?? null,
      assertions: (e.assertions || []).map((a) => ({ nombre: a.assertion, paso: !a.error, error: a.error ? clean(String(a.error.message)).slice(0, 300) : null })),
      assertionsTotal: (e.assertions || []).length,
      assertionsFallidas: (e.assertions || []).filter((a) => a.error).length,
      cuerpo,
    };
  };

  const e154 = porNombre('TC-M02-154');
  const e159 = porNombre('TC-M02-159');
  const r154 = resumenEjecucion(e154);
  const r159 = resumenEjecucion(e159);

  const indicador = (() => {
    const inds = r159?.cuerpo?.indicadores || [];
    return inds.find((i) => /ganancia[_ ]?peso/i.test(String(i.tipo))) || null;
  })();

  const tc154 = {
    nombre: 'Consumir API interna con modulo autorizado',
    peticionCanonica: `GET /activos-biologicos/295/datos-consolidados?tipo_dato=todos&pagina=1&page_size=20`,
    tipoDatoSustituido: false,
    http: r154?.http ?? null, contentType: r154?.contentType ?? null, tiempo_ms: r154?.tiempo_ms ?? null,
    dentroDelRnf: (r154?.tiempo_ms ?? Infinity) <= RNF_MS,
    camposDelContratoPresentes: r154?.cuerpo ? contrato.campos_datos_consolidados.filter((c) => c in r154.cuerpo) : [],
    camposDelContratoAusentes: r154?.cuerpo ? contrato.campos_datos_consolidados.filter((c) => !(c in r154.cuerpo)) : contrato.campos_datos_consolidados,
    correspondeAlActivo: r154?.cuerpo?.id_activo_biologico === fixture.id_activo_biologico
      && r154?.cuerpo?.identificador === fixture.identificador,
    paginacion: r154?.cuerpo ? { pagina_actual: r154.cuerpo.pagina_actual, registros_por_pagina: r154.cuerpo.registros_por_pagina, total_registros: r154.cuerpo.total_registros, total_paginas: r154.cuerpo.total_paginas } : null,
    assertions: r154?.assertions ?? [], assertionsTotal: r154?.assertionsTotal ?? 0, assertionsFallidas: r154?.assertionsFallidas ?? 0,
    veredicto: r154 && r154.assertionsFallidas === 0 ? 'APROBADO' : 'NO APROBADO',
  };

  const tc159 = {
    nombre: 'Calcular Ganancia Diaria de Peso con datos suficientes',
    peticion: `GET /activos-biologicos/295/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=${exp.fecha_inicial}&fecha_fin=${exp.fecha_final}`,
    http: r159?.http ?? null, tiempo_ms: r159?.tiempo_ms ?? null,
    dentroDelRnf: (r159?.tiempo_ms ?? Infinity) <= RNF_MS,
    indicador: indicador ? {
      tipo: indicador.tipo, valor: indicador.valor, unidad: indicador.unidad,
      disponible: indicador.disponible, periodo_inicio: indicador.periodo_inicio,
      periodo_fin: indicador.periodo_fin, fecha_calculo: indicador.fecha_calculo,
      variables_usadas: indicador.variables_usadas,
    } : null,
    valorObservado: indicador ? Number(indicador.valor).toFixed(4) : null,
    valorEsperadoIndependiente: exp.por_decimales[4],
    coincide: indicador ? Number(indicador.valor).toFixed(4) === Number(exp.por_decimales[4]).toFixed(4) : false,
    assertions: r159?.assertions ?? [], assertionsTotal: r159?.assertionsTotal ?? 0, assertionsFallidas: r159?.assertionsFallidas ?? 0,
    veredicto: r159 && r159.assertionsFallidas === 0 ? 'APROBADO' : 'NO APROBADO',
  };

  const stats = summary.run.stats;
  const fallos = (summary.run.failures || []).map((f) => ({
    item: f.source?.name ?? null, assertion: f.error?.test ?? null,
    mensaje: clean(String(f.error?.message ?? '')).slice(0, 300),
  }));

  const grupo = tc154.veredicto === 'APROBADO' && tc159.veredicto === 'APROBADO' ? 'APROBADO' : 'NO APROBADO';

  const evidencia = {
    grupo: 'TC-M02-G92',
    nombre: 'Consumo exitoso de datos analiticos e indicadores zootecnicos por modulos autorizados',
    tipo: 'CUARTA EVALUACION (V4)', runId,
    fecha: new Date().toISOString(),
    rf: 'RF-50 / RF-51', cu: 'CU12', responsableQa: 'Juan Esteban',
    ambienteDecisorio: 'TEST',
    baseUrl: {
      oficialAdoptada: BASE_TEST,
      configuradaEnLaColeccionV3: BASE_V3,
      mismoDespliegue: true,
      comprobacion: 'sha256 de /openapi.json identico en ambos dominios',
      ejecucionesContraAmbosDominios: false,
    },
    veredicto: { 'TC-M02-G92': grupo, 'TC-M02-154': tc154.veredicto, 'TC-M02-159': tc159.veredicto },
    git: { inicial: gitInicial },
    contrato,
    actor,
    alcance,
    fixture,
    expectedIndependiente: exp,
    reutilizacionDeAutomatizacion: { ...reutilizacion, coherenciaConElFixtureDescubierto: coherencia },
    resultadoNewman: {
      iteraciones: stats.iterations, peticiones: stats.requests,
      assertionsTotal: stats.assertions.total, assertionsFallidas: stats.assertions.failed,
      duracion_ms: summary.run.timings?.completed && summary.run.timings?.started
        ? summary.run.timings.completed - summary.run.timings.started : null,
      fallos,
      peticiones_detalle: summary.run.executions.map((e) => ({
        item: e.item.name, metodo: e.request.method, http: e.response?.code ?? null,
        tiempo_ms: e.response?.responseTime ?? null,
        assertions: (e.assertions || []).length,
        fallidas: (e.assertions || []).filter((a) => a.error).length,
      })),
    },
    'TC-M02-154': tc154,
    'TC-M02-159': tc159,
    escrituras: {
      funcionalesDelCaso: 0, dePreparacion: 0, sqlWrite: 0,
      cambiosRbac: 0, cambiosDeRol: 0, cambiosDeScopes: 0,
      eventosCreados: 0, medicionesCreadas: 0, modificacionesDelActivo: 0,
      nota: 'La ejecucion oficial es de lectura: solo un POST /sesiones/ de autenticacion y tres GET.',
    },
    seguridad: {
      contrasenaPersistida: false, jwtPersistido: false, bearerPersistido: false,
      cookiesPersistidas: false, refreshTokenPersistido: false,
      correoDelActorDocumentado: M04_EMAIL,
      nota: 'La contrasena se tomo de M04_TEST_PASSWORD y se entrego a Newman como variable de entorno '
          + 'de la ejecucion. El reporte de Newman se saneo antes de guardarse.',
    },
    incidencia: { referencia: 'INC-M02-90-G92 / GitHub #241', nuevaIncidenciaCreada: false, issueModificado: false },
  };

  evidencia.git.final = estadoGit();
  fs.writeFileSync(path.join(R, 'evidencia-g92-v4.json'), clean(JSON.stringify(evidencia, null, 2)));

  console.log('scopes', JSON.stringify(actor.scopes));
  console.log('TC-M02-154 | HTTP', tc154.http, '|', tc154.tiempo_ms, 'ms |', tc154.assertionsTotal - tc154.assertionsFallidas, '/', tc154.assertionsTotal, '->', tc154.veredicto);
  console.log('TC-M02-159 | HTTP', tc159.http, '|', tc159.tiempo_ms, 'ms | valor', tc159.valorObservado, 'esperado', tc159.valorEsperadoIndependiente, '|', tc159.assertionsTotal - tc159.assertionsFallidas, '/', tc159.assertionsTotal, '->', tc159.veredicto);
  console.log('Newman: assertions', stats.assertions.total, 'fallidas', stats.assertions.failed);
  if (fallos.length) console.log('FALLOS:', JSON.stringify(fallos, null, 1));
  console.log('GRUPO:', grupo);
  console.log('evidencia ->', path.join(R, 'evidencia-g92-v4.json'));
})().catch((e) => { console.log('ERROR:', clean(e.message)); process.exitCode = 1; });
