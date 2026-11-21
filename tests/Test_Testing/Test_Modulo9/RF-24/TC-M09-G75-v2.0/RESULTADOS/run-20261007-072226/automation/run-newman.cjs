// Runner del único RUN oficial de TC-M09-G75-v2.0 (RF-24 v2.0, CU05 Flujo D).
//
// Presupuesto exacto: 7 POST funcionales (no reintentos). Si una variante inválida
// persiste, la colección detiene el RUN (STOP_ALL) y los POST restantes no se envían.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_EMAIL="ingeniero@pecuaria.co"
//   $env:QA_PASSWORD="<secreto>"
//   $env:QA_ADMIN_PRIMARY="admin.dev@gmail.com"
//   $env:QA_ADMIN_SECONDARY="administador.dev@gmail.com"
//   $env:QA_ADMIN_PASSWORD="<secreto>"
//   $env:G75_RUN_ID="run-YYYYMMDD-HHMMSS"
//   node .\run-newman.cjs

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const H = require('./helpers.cjs'); // Incluye la guarda de directorio autorizado.

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const runId = process.env.G75_RUN_ID;
if (!runId || !/^run-\d{8}-\d{6}$/.test(runId)) {
  throw new Error('G75_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
}
const actorEmail = process.env.QA_EMAIL;
const actorSecret = process.env.QA_PASSWORD;
if (!actorEmail || !actorSecret) throw new Error('QA_EMAIL y QA_PASSWORD requeridos (solo en memoria de proceso).');
const adminSecret = process.env.QA_ADMIN_PASSWORD;
const adminPrimary = process.env.QA_ADMIN_PRIMARY;
const adminSecondary = process.env.QA_ADMIN_SECONDARY;

const outputDir = path.join(__dirname, 'RESULTADOS', runId);
if (fs.existsSync(outputDir)) {
  throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);
}

const htmlPath = path.join(H.runDir(runId, 'newman'), `newman-${H.GROUP_ID}.html`);

const log = (...a) => console.log(...a);
// Raíz del repositorio: se localiza subiendo hasta encontrar .git, en lugar de contar
// niveles a mano (contarlos mal deja git_pre.txt lleno de errores de "not a git repository").
const repoRoot = (() => {
  let d = __dirname;
  for (let i = 0; i < 12; i += 1) {
    if (fs.existsSync(path.join(d, '.git'))) return d;
    const padre = path.dirname(d);
    if (padre === d) break;
    d = padre;
  }
  return __dirname;
})();
const git = (args) => {
  try { return execFileSync('git', args, { cwd: repoRoot, encoding: 'utf8' }).trim(); }
  catch (e) { return `ERROR: ${e.message}`; }
};

(async () => {
  // ------------------------------------------------------------------ git_pre
  const gitPre = [
    '# git_pre.txt — TC-M09-G75-v2.0',
    `# Capturado: ${new Date().toISOString()}`,
    '',
    `$ git branch --show-current\n${git(['branch', '--show-current'])}`,
    '',
    `$ git status --short\n${git(['status', '--short']) || '(vacio)'}`,
    '',
    `$ git diff --stat\n${git(['diff', '--stat']) || '(vacio)'}`,
    '',
    `$ git diff --cached --stat\n${git(['diff', '--cached', '--stat']) || '(vacio)'}`,
    '',
    `$ git rev-parse HEAD\n${git(['rev-parse', 'HEAD'])}`,
    '',
    `$ git rev-parse origin/test\n${git(['rev-parse', 'origin/test'])}`,
    '',
    `$ git rev-list --left-right --count HEAD...origin/test\n${git(['rev-list', '--left-right', '--count', 'HEAD...origin/test'])}`,
    '',
    '# Carpeta histórica TC-M09-G75 (debe quedar intacta)',
    `$ git status --short -- tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75\n${git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75']) || '(vacio = intacta)'}`
  ].join('\n');
  fs.writeFileSync(path.join(H.runDir(runId), 'git_pre.txt'), H.clean(gitPre));
  const headSha = git(['rev-parse', 'HEAD']);

  // --------------------------------------------------------- preflight OpenAPI
  const openapi = await (await fetch(H.base() + '/openapi.json', { signal: AbortSignal.timeout(30000) })).json();
  const rutas = {
    'POST /configuracion/sensores/{id_sensor}/calibrar':
      openapi.paths?.['/configuracion/sensores/{id_sensor}/calibrar']?.post || null,
    'GET /configuracion/sensores/{id_sensor}/calibraciones':
      openapi.paths?.['/configuracion/sensores/{id_sensor}/calibraciones']?.get || null,
    'GET /configuracion/sensores/rangos-calibracion':
      openapi.paths?.['/configuracion/sensores/rangos-calibracion']?.get || null
  };
  const dto = openapi.components?.schemas?.RegistrarCalibracionDTO || null;
  H.save(runId, 'openapi_preflight.json', {
    grupo: H.GROUP_ID,
    fuente: H.base() + '/openapi.json',
    endpoints: Object.fromEntries(Object.entries(rutas).map(([k, v]) => [k, {
      presente: Boolean(v),
      summary: v?.summary ?? null,
      codigosDeclarados: v ? Object.keys(v.responses || {}) : []
    }])),
    requestSchemaDelPost: dto ? { properties: Object.keys(dto.properties || {}), required: dto.required || [] } : null,
    // Observación transversal: G75 evalúa límites de valor_referencia, no el discriminador de modalidad.
    modo_calibracion_declarado_en_openapi: JSON.stringify(openapi).includes('modo_calibracion'),
    nota: 'modo_calibracion se envía como exige el caso aunque OpenAPI no lo declare. El oráculo de G75 son los límites y el formato de valor_referencia.'
  });
  for (const [k, v] of Object.entries(rutas)) {
    if (!v) throw new Error(`BLOQUEADO: ${k} no está desplegado en TEST.`);
  }
  log('OpenAPI: los tres endpoints del grupo están desplegados.');

  // ------------------------------------------------------------ autenticación
  let tokenIng;
  try {
    tokenIng = await H.login(actorEmail, actorSecret);
  } catch (e) {
    throw new Error(
      `BLOQUEADO: el Ingeniero no autentica (${e.message}). No se prueban otras contraseñas ` +
      'ni se sustituye por Administrador.'
    );
  }
  log('Ingeniero autenticado.');

  const identidad = await H.getOk('/usuarios/me', tokenIng);
  if (identidad.correo_electronico !== actorEmail || identidad.nombre_rol !== 'Ingeniero de Campo') {
    throw new Error('BLOQUEADO: la identidad autenticada no corresponde al Ingeniero de Campo del caso.');
  }
  H.save(runId, 'identidad_actor.json', {
    id_usuario: identidad.id_usuario,
    correo_electronico: identidad.correo_electronico,
    nombre_rol: identidad.nombre_rol,
    credencial: '[REDACTED]'
  });

  const permisos = await H.getOk('/sesiones/me/permisos', tokenIng);
  const tiene = (r, a) => (permisos.permisos || []).some(p => p.id_recurso === r && p.id_accion === a);
  const permisosCaso = {
    leerDispositivos: tiene(11, 2),
    registrarCalibraciones: tiene(12, 1),
    consultarHistorial: tiene(12, 2)
  };
  H.save(runId, 'permisos_actor.json', { id_usuario: identidad.id_usuario, permisosDelCaso: permisosCaso, total: (permisos.permisos || []).length });
  if (!permisosCaso.registrarCalibraciones || !permisosCaso.consultarHistorial) {
    throw new Error('BLOQUEADO: el Ingeniero no tiene los permisos funcionales del caso.');
  }
  log(`Identidad y permisos confirmados (id_usuario ${identidad.id_usuario}).`);

  // Administrador auxiliar: solo para GET de precondición fuera del alcance del Ingeniero.
  let tokenAdmin = null;
  let adminUsado = null;
  const intentosAdmin = [];
  for (const email of [adminPrimary, adminSecondary].filter(Boolean)) {
    try {
      tokenAdmin = await H.login(email, adminSecret);
      adminUsado = email;
      intentosAdmin.push({ email, resultado: 'autentica' });
      break;
    } catch (e) {
      intentosAdmin.push({ email, resultado: `no autentica (${e.message})` });
    }
  }
  if (adminUsado) log(`Administrador auxiliar de solo lectura: ${adminUsado}`);

  // ------------------------------------------------------------------- plan
  const { plan, origenFixture, usoAdmin, valores, literales, esperados, cuerpos, variable } =
    await H.construirPlan(tokenIng, tokenAdmin);

  H.save(runId, 'fixture_descubierto.json', {
    origenFixture,
    dispositivo: plan.dispositivo,
    sensor: plan.sensor,
    area: plan.area,
    historialInicial: plan.historialInicial,
    administradorAuxiliar: {
      intentos: intentosAdmin,
      usado: adminUsado || null,
      getsQueLoRequirieron: usoAdmin,
      ejecutaPostFuncional: false
    }
  });
  H.save(runId, 'rango_temperatura.json', {
    rangoTecnico: plan.rangoTecnico,
    paso: valores.paso,
    valoresDelRun: valores,
    aritmetica: 'decimal exacta sobre numeric(10,4) con BigInt; nunca coma flotante binaria'
  });
  log(`Fixture: dispositivo ${plan.dispositivo.id} / sensor ${plan.sensor.id} / infraestructura ${plan.area.id_infraestructura} (${variable})`);
  log(`Rango vigente: ${valores.minExacto} – ${valores.maxExacto} | LOW ${valores.bajoInvalido} | HIGH ${valores.altoInvalido}`);

  // ------------------------- trazabilidad de la automatización (antes del 1er POST)
  const artefactos = ['TC-M09-G75-v2.0.postman_collection.json', 'helpers.cjs', 'run-newman.cjs', 'verificar-cierre.cjs'];
  const automationDir = H.runDir(runId, 'automation');
  const manifest = [];
  for (const a of artefactos) {
    const src = path.join(__dirname, a);
    if (!fs.existsSync(src)) continue;
    const dst = path.join(automationDir, a);
    fs.writeFileSync(dst, H.clean(fs.readFileSync(src, 'utf8')));
    manifest.push({ archivo: a, sha256_original: H.sha256(src), sha256_copia: H.sha256(dst), bytes: fs.statSync(src).size });
  }
  H.save(runId, 'automation_manifest.json', {
    grupo: H.GROUP_ID, runId, commit: headSha,
    nota: 'SHA-256 de la automatización que produjo este RUN. Las copias están sanitizadas y no contienen secretos.',
    artefactos: manifest
  });
  log(`Automatización registrada con SHA-256 (${manifest.length} artefactos).`);

  // -------------------------------------------------------------- env de newman
  const env = [
    ['base_url', H.base()],
    ['actor_email', actorEmail],
    ['actor_secret', actorSecret],
    ['admin_email', adminUsado || ''],
    ['admin_secret', adminUsado ? adminSecret : ''],
    ['device_id', String(plan.dispositivo.id)],
    ['sensor_id', String(plan.sensor.id)],
    ['area_id', String(plan.area.id_infraestructura)],
    ['categoria', variable],
    ['range_min', valores.minExacto],
    ['range_max', valores.maxExacto],
    ['stop_all', 'NO']
  ];
  for (const v of H.VARIANTS) {
    env.push([`body_${v.key}`, cuerpos[v.key]]);
    if (v.valido) env.push([`valor_${v.key}`, String(literales[v.key].enviado)]);
    else env.push([`exp_msg_${v.key}`, esperados[v.key]]);
  }

  log('\nIniciando el RUN oficial. POST planificados: 7.\n');

  newman.run({
    collection: path.join(__dirname, 'TC-M09-G75-v2.0.postman_collection.json'),
    reporters: ['cli', 'htmlextra'],
    reporter: {
      htmlextra: {
        export: htmlPath,
        omitHeaders: true,
        showEnvironmentData: false,
        showGlobalData: false,
        skipEnvironmentVars: ['actor_secret', 'admin_secret', 'session_value', 'admin_session'],
        showMarkdownLinks: false
      }
    },
    envVar: env.map(([key, value]) => ({ key, value }))
  }, (err, summary) => {
    try {
      finalizar(err, summary);
    } catch (e) {
      console.error('Error al consolidar el RUN:', e.message);
      process.exitCode = 1;
    }
  });

  function finalizar(err, summary) {
    const executions = summary?.run?.executions || [];
    const find = (name) => executions.find(x => x.item && x.item.name === name);
    const bodyOf = (name) => {
      const e = find(name);
      if (!e || !e.response) return null;
      try { return JSON.parse(e.response.stream.toString()); } catch { return null; }
    };
    const statusOf = (name) => { const e = find(name); return e && e.response ? e.response.code : null; };
    const sentBodyOf = (name) => {
      const e = find(name);
      try { return JSON.parse(e.request.body.raw.toString()); } catch { return null; }
    };

    // HTML sanitizado antes de conservarlo como evidencia.
    if (fs.existsSync(htmlPath)) fs.writeFileSync(htmlPath, H.cleanHtml(fs.readFileSync(htmlPath, 'utf8')));

    const resultados = {};
    let postsEjecutados = 0;
    const snapshots = {};

    for (const v of H.VARIANTS) {
      const K = v.key;
      const pre = bodyOf(`${K} PRE historial`);
      const resp = bodyOf(`${K} POST calibrar`);
      const post = bodyOf(`${K} POST historial`);
      const status = statusOf(`${K} POST calibrar`);
      const enviado = sentBodyOf(`${K} POST calibrar`);
      const ejecutado = status !== null;
      if (ejecutado) postsEjecutados += 1;

      if (pre) H.save(runId, `${K}_historial_pre.json`, pre);
      if (enviado) {
        H.save(runId, `${K}_request.json`, {
          endpoint: `/configuracion/sensores/${plan.sensor.id}/calibrar`,
          metodo: 'POST',
          headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' },
          body: enviado,
          valorEnviado: literales[K].enviado,
          tipoJsonDelValor: literales[K].tipo
        });
      }
      if (resp) H.save(runId, `${K}_response.json`, { http: status, cuerpo: resp });
      if (post) H.save(runId, `${K}_historial_post.json`, post);

      const preIds = pre ? (pre.items || []).map(x => x.id_calibracion) : null;
      const postIds = post ? (post.items || []).map(x => x.id_calibracion) : null;
      const nuevos = preIds && postIds ? postIds.filter(x => !preIds.includes(x)) : null;

      const r = {
        caso: v.caso, variante: v.etiqueta, valido: v.valido, ejecutado,
        http: status,
        valorEnviado: literales[K].enviado,
        tipoJsonDelValor: literales[K].tipo,
        observaciones: v.observaciones,
        fechaEnviada: enviado ? enviado.fecha_calibracion : null,
        historialPre: pre ? { total: pre.total, ids: preIds } : null,
        historialPost: post ? { total: post.total, ids: postIds } : null,
        idsNuevos: nuevos
      };

      if (v.valido) {
        const creado = resp && resp.id_calibracion ? resp.id_calibracion : null;
        const persistido = post && creado ? (post.items || []).find(x => x.id_calibracion === creado) || null : null;
        if (persistido) {
          snapshots[K] = persistido;
          H.save(runId, `${K}_calibracion_creada.json`, persistido);
        }
        r.id_calibracion = creado;
        r.registroPersistido = persistido;
        r.oraculo = {
          http_2xx: status !== null && status >= 200 && status <= 299,
          id_nuevo: Boolean(creado) && Array.isArray(preIds) && !preIds.includes(creado),
          valor_exacto: Boolean(resp) && H.igualDecimal(resp.valor_referencia, literales[K].enviado),
          id_dispositivo_iot: Boolean(resp) && resp.id_dispositivo_iot === plan.dispositivo.id,
          id_sensor: Boolean(resp) && resp.id_sensor === plan.sensor.id,
          id_usuario: Boolean(resp) && resp.id_usuario === identidad.id_usuario,
          observaciones: Boolean(resp) && resp.observaciones === v.observaciones,
          fecha_mismo_instante: Boolean(resp) && Boolean(enviado) &&
            new Date(resp.fecha_calibracion).getTime() === new Date(enviado.fecha_calibracion).getTime(),
          persistido_en_historial: Boolean(persistido)
        };
      } else {
        const obtenido = resp ? resp.message : null;
        r.error_code = resp ? resp.error_code ?? null : null;
        r.mensajeEsperado = esperados[K];
        r.mensajeObtenido = obtenido;
        r.mensajeCoincide = obtenido === esperados[K];
        r.oraculo = {
          http_400: status === 400,
          // El esperado del caso no se adapta al backend: comparación exacta.
          mensaje_exacto: r.mensajeCoincide,
          sin_persistencia: Array.isArray(nuevos) && nuevos.length === 0,
          total_sin_cambios: Boolean(pre) && Boolean(post) && Number(pre.total) === Number(post.total)
        };
        if (!r.mensajeCoincide && obtenido !== null) {
          r.diferenciaDeMensaje = { esperado: esperados[K], obtenido, nota: 'comparación exacta; no se acepta un mensaje aproximado' };
        }
      }

      // Inmutabilidad de las válidas previas, comprobada sobre el historial de esta variante.
      if (post) {
        r.inmutabilidadDeValidasPrevias = Object.entries(snapshots)
          .filter(([k]) => k !== K)
          .map(([k, snap]) => {
            const row = (post.items || []).find(x => x.id_calibracion === snap.id_calibracion);
            return {
              variante: k, id_calibracion: snap.id_calibracion, presente: Boolean(row),
              intacta: Boolean(row) &&
                row.id_dispositivo_iot === snap.id_dispositivo_iot &&
                row.id_sensor === snap.id_sensor &&
                row.id_usuario === snap.id_usuario &&
                H.igualDecimal(row.valor_referencia, snap.valor_referencia) &&
                row.observaciones === snap.observaciones &&
                new Date(row.fecha_calibracion).getTime() === new Date(snap.fecha_calibracion).getTime()
            };
          });
      }

      r.resultado = !ejecutado ? 'NO EJECUTADO' : Object.values(r.oraculo).every(x => x === true) ? 'PASS' : 'FAIL';
      resultados[K] = r;
    }

    // Resultado por caso: una variante que falla hace fallar su caso.
    const porCaso = {};
    for (const v of H.VARIANTS) {
      const r = resultados[v.key];
      const actual = porCaso[v.caso] || { variantes: [], resultado: 'APROBADO' };
      actual.variantes.push({ etiqueta: v.etiqueta, resultado: r.resultado });
      if (r.resultado === 'FAIL') actual.resultado = 'RECHAZADO';
      else if (r.resultado === 'NO EJECUTADO' && actual.resultado !== 'RECHAZADO') actual.resultado = 'NO CONCLUIDO';
      porCaso[v.caso] = actual;
    }

    const stopAll = summary?.environment?.values?.find?.(x => x.key === 'stop_all')?.value === 'SI' ||
      Object.values(resultados).some(r => r.ejecutado && !r.valido && Array.isArray(r.idsNuevos) && r.idsNuevos.length > 0);
    const stopMotivoRaw = summary?.environment?.values?.find?.(x => x.key === 'stop_all_motivo')?.value;

    const failures = (summary?.run?.failures || [])
      .map(f => ({ item: f.source?.name, assertion: f.error?.test, error: f.error?.message }))
      .filter(f => f.error);

    const casosRechazados = Object.values(porCaso).filter(c => c.resultado === 'RECHAZADO').length;
    const casosNoConcluidos = Object.values(porCaso).filter(c => c.resultado === 'NO CONCLUIDO').length;
    const resultadoGrupo = casosRechazados > 0 ? 'RECHAZADO'
      : casosNoConcluidos > 0 ? 'BLOQUEADO / NO VERIFICABLE'
      : 'APROBADO';

    const artifact = {
      grupo: H.GROUP_ID, requisito: H.RF, casoDeUso: H.CU, runId, commit: headSha,
      ambiente: { decisorio: 'TEST', base_url: H.base() },
      carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${H.FOLDER}/`,
      actor: { id_usuario: identidad.id_usuario, correo: identidad.correo_electronico, rol: identidad.nombre_rol, credencial: '[REDACTED]' },
      administradorAuxiliar: { usado: adminUsado || null, getsQueLoRequirieron: usoAdmin, ejecutaPostFuncional: false },
      fixture: { origenFixture, dispositivo: plan.dispositivo, sensor: plan.sensor, area: plan.area },
      rango: plan.rangoTecnico, valores,
      presupuestoPost: H.POST_BUDGET, postsEjecutados,
      stopAll: stopAll ? 'SI' : 'NO',
      stopAllMotivo: stopMotivoRaw ? JSON.parse(stopMotivoRaw) : null,
      resultadosPorVariante: resultados,
      resultadosPorCaso: porCaso,
      resultadoGrupo,
      assertions: {
        total: summary?.run?.stats?.assertions?.total || 0,
        failed: failures.length,
        failures
      }
    };
    H.save(runId, `${H.GROUP_ID}.json`, artifact);

    log('\n================ RESUMEN DEL RUN ================');
    log(`RUN_ID: ${runId}`);
    log(`Fixture: dispositivo ${plan.dispositivo.id} / sensor ${plan.sensor.id} / infraestructura ${plan.area.id_infraestructura}`);
    log(`Rango: ${valores.minExacto} – ${valores.maxExacto}`);
    log(`POST planificados: ${H.POST_BUDGET} | ejecutados: ${postsEjecutados}`);
    for (const v of H.VARIANTS) {
      const r = resultados[v.key];
      const extra = r.valido
        ? `id_calibracion=${r.id_calibracion ?? 'N/A'}`
        : `mensaje_exacto=${r.oraculo?.mensaje_exacto ? 'SI' : 'NO'} persistencia=${r.oraculo?.sin_persistencia === true ? 'NO' : 'SI/?'}`;
      log(`  ${v.caso} ${v.etiqueta.padEnd(5)} HTTP=${String(r.http ?? '-').padEnd(4)} ${r.resultado.padEnd(12)} ${extra}`);
    }
    for (const [caso, c] of Object.entries(porCaso)) log(`  ${caso} → ${c.resultado}`);
    log(`GRUPO ${H.GROUP_ID} → ${resultadoGrupo}`);
    log(`Assertions: ${artifact.assertions.total} | Failures: ${artifact.assertions.failed}`);
    log(`STOP_ALL: ${artifact.stopAll}`);
    log('=================================================\n');

    if (err) process.exitCode = 1;
    else if (resultadoGrupo !== 'APROBADO') process.exitCode = 2;
  }
})().catch((e) => {
  console.error('\nRUN NO COMPLETADO:', e.message);
  process.exitCode = 1;
});
