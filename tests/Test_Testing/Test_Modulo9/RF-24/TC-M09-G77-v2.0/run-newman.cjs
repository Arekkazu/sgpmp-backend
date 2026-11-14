// Runner del único RUN oficial de TC-M09-G77-v2.0 (RF-24 v2.0, CU05 Flujo D) — OWASP API5.
//
// Presupuesto: 2 POST de calibración negativos (uno por rol), sin reintentos. Además, por
// actor y solo si su estado original NO era Activo, como máximo 1 activación y 1 restauración.
// La restauración se intenta siempre que sea posible, incluso si el subescenario falla.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:TEST_PRODUCTOR_EMAIL / $env:TEST_PRODUCTOR_PASSWORD
//   $env:TEST_CONTADOR_EMAIL  / $env:TEST_CONTADOR_PASSWORD
//   $env:TEST_ENGINEER_EMAIL  / $env:TEST_ENGINEER_PASSWORD
//   $env:TEST_ADMIN_PRIMARY   / $env:TEST_ADMIN_SECONDARY / $env:TEST_ADMIN_PASSWORD
//   $env:G77_RUN_ID="run-YYYYMMDD-HHMMSS"
//   node .\run-newman.cjs

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const H = require('./helpers.cjs'); // Incluye la guarda de directorio autorizado.

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const runId = process.env.G77_RUN_ID;
if (!runId || !/^run-\d{8}-\d{6}$/.test(runId)) throw new Error('G77_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
const outputDir = path.join(__dirname, 'RESULTADOS', runId);
if (fs.existsSync(outputDir)) throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);

const htmlPath = path.join(H.runDir(runId, 'newman'), `newman-${H.GROUP_ID}.html`);
const log = (...a) => console.log(...a);

// Raíz del repositorio: se localiza subiendo hasta encontrar .git, no contando niveles.
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
const git = (args) => { try { return execFileSync('git', args, { cwd: repoRoot, encoding: 'utf8' }).trim(); } catch (e) { return `ERROR: ${e.message}`; } };

(async () => {
  // ------------------------------------------------------------------- git_pre
  fs.writeFileSync(path.join(H.runDir(runId), 'git_pre.txt'), H.clean([
    '# git_pre.txt — TC-M09-G77-v2.0', `# Capturado: ${new Date().toISOString()}`, '',
    `$ git branch --show-current\n${git(['branch', '--show-current'])}`, '',
    `$ git status --short\n${git(['status', '--short']) || '(vacio)'}`, '',
    `$ git diff --stat\n${git(['diff', '--stat']) || '(vacio)'}`, '',
    `$ git diff --cached --stat\n${git(['diff', '--cached', '--stat']) || '(vacio)'}`, '',
    `$ git rev-parse HEAD\n${git(['rev-parse', 'HEAD'])}`, '',
    `$ git rev-parse origin/test\n${git(['rev-parse', 'origin/test'])}`, '',
    `$ git rev-list --left-right --count HEAD...origin/test\n${git(['rev-list', '--left-right', '--count', 'HEAD...origin/test'])}`, '',
    '# Carpeta histórica TC-M09-G77 (debe quedar intacta, incluida EvaluacionV2)',
    `$ git status --short -- tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G77\n${git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G77']) || '(vacio = intacta)'}`
  ].join('\n')));
  const headSha = git(['rev-parse', 'HEAD']);

  // --------------------------------------------------------- preflight OpenAPI
  const openapi = await (await fetch(H.base() + '/openapi.json', { signal: AbortSignal.timeout(30000) })).json();
  const requeridos = [
    ['post', '/usuarios/{id_usuario}/gestionar'],
    ['post', '/configuracion/sensores/{id_sensor}/calibrar'],
    ['get', '/configuracion/sensores/{id_sensor}/calibraciones'],
    ['get', '/usuarios/admin'],
    ['get', '/usuarios/{id_usuario}/detalle']
  ];
  const endpoints = {};
  for (const [m, p] of requeridos) {
    const op = openapi.paths?.[p]?.[m] || null;
    endpoints[`${m.toUpperCase()} ${p}`] = { presente: Boolean(op), summary: op?.summary ?? null, codigosDeclarados: op ? Object.keys(op.responses || {}) : [] };
    if (!op) throw new Error(`BLOQUEADO: ${m.toUpperCase()} ${p} no está desplegado en TEST.`);
  }
  H.save(runId, 'openapi_preflight.json', {
    grupo: H.GROUP_ID, fuente: H.base() + '/openapi.json', endpoints,
    declara403EnCalibrar: endpoints['POST /configuracion/sensores/{id_sensor}/calibrar'].codigosDeclarados.includes('403'),
    modo_calibracion_declarado: JSON.stringify(openapi).includes('modo_calibracion'),
    nota: 'modo_calibracion=SENSOR se envía como exige el caso aunque el schema no lo declare. El oráculo de RF-24 v2.0 no se adapta a OpenAPI.'
  });
  log('OpenAPI: endpoints del grupo verificados.');

  // ------------------------------------------- actor de discovery y administrador
  const tokenIng = await H.loginOk(process.env.TEST_ENGINEER_EMAIL, process.env.TEST_ENGINEER_PASSWORD, 'Ingeniero de discovery');
  let tokenAdmin = null, adminUsado = null;
  const intentosAdmin = [];
  for (const email of [process.env.TEST_ADMIN_PRIMARY, process.env.TEST_ADMIN_SECONDARY].filter(Boolean)) {
    const r = await H.login(email, process.env.TEST_ADMIN_PASSWORD);
    if (r.status === 200 && r.token) { tokenAdmin = r.token; adminUsado = email; intentosAdmin.push({ email, resultado: 'autentica' }); break; }
    intentosAdmin.push({ email, resultado: `no autentica (HTTP ${r.status}${r.errorCode ? ' ' + r.errorCode : ''})` });
  }
  if (!tokenAdmin) throw new Error('BLOQUEADO: ningún Administrador autenticó; sin él no se pueden localizar las cuentas de los actores.');
  H.save(runId, 'admin_efectivo.json', { intentos: intentosAdmin, usado: adminUsado, credencial: '[REDACTED]', uso: 'GET de fixture, localización de cuentas y, si hiciera falta, activación y restauración de estado. No ejecuta POST de calibración.' });
  log(`Administrador efectivo: ${adminUsado}`);

  // ------------------------------------------------------------------- fixture
  const usoAdmin = [];
  const { fixture, origen } = await H.construirFixture(tokenIng, tokenAdmin, usoAdmin);
  H.save(runId, 'fixture.json', { origen, ...fixture, getsConAdministrador: usoAdmin });
  log(`Fixture: ${origen} | sensor ${fixture.sensor.id} (${fixture.sensor.categoria}) / dispositivo ${fixture.dispositivo.id} / área ${fixture.area.id_infraestructura} / valor ${fixture.valor}`);

  // ------------------------------------- cuentas y snapshot del estado original
  const actores = {};
  for (const a of H.ACTORES) {
    const correo = process.env[a.envEmail];
    if (!correo) throw new Error(`Falta ${a.envEmail}.`);
    const cuenta = await H.localizarCuenta(correo, tokenAdmin);
    const plan = H.planDeEstado(cuenta.estado_cuenta);
    actores[a.key] = {
      ...a, correo, cuenta, estadoOriginal: cuenta.estado_cuenta, plan,
      rolCoincide: cuenta.nombre_rol === a.rolEsperado,
      setup: { ejecutado: false, http: null }, restauracion: { necesaria: false, ejecutada: false, http: null, estadoFinal: null, ok: null },
      ejecutable: null, motivoBloqueo: null
    };
    H.save(runId, `${a.key}_estado_pre.json`, { correo, cuenta, planDeEstado: plan, fechaConsulta: new Date().toISOString() });
  }
  H.save(runId, 'usuarios_pre.json', {
    nota: 'Estado original de cada actor: es el oráculo de la restauración. No se asume ningún estado previo histórico.',
    fechaConsulta: new Date().toISOString(),
    actores: Object.fromEntries(Object.entries(actores).map(([k, v]) => [k, {
      id_usuario: v.cuenta.id_usuario, correo: v.correo, rol: v.cuenta.nombre_rol,
      estado_cuenta_original: v.estadoOriginal, rolEsperado: v.rolEsperado, rolCoincide: v.rolCoincide
    }]))
  });

  // Preparación just-in-time: se activa solo lo imprescindible y solo si es restaurable.
  for (const v of Object.values(actores)) {
    if (!v.rolCoincide) {
      v.ejecutable = false;
      v.motivoBloqueo = `la cuenta tiene rol ${v.cuenta.nombre_rol} y el subescenario exige ${v.rolEsperado}; no se cambian roles para preparar la prueba`;
      log(`${v.key}: BLOQUEADO — ${v.motivoBloqueo}`);
      continue;
    }
    if (v.estadoOriginal === 'Activo') {
      v.ejecutable = true;
      log(`${v.key}: cuenta ya Activa (id ${v.cuenta.id_usuario}); no se modifica su estado.`);
      continue;
    }
    if (!v.plan.permitido) {
      v.ejecutable = false;
      v.motivoBloqueo = v.plan.motivo;
      log(`${v.key}: BLOQUEADO — ${v.motivoBloqueo}`);
      continue;
    }
    const r = await H.gestionarCuenta(v.cuenta.id_usuario, 'activar', tokenAdmin,
      `QA ${H.CASO}: activación temporal para prueba de seguridad`);
    v.setup = { ejecutado: true, http: r.status, cuerpo: r.cuerpo };
    // Se reconcilia por GET en lugar de reintentar la escritura.
    const confirm = await H.localizarCuenta(v.correo, tokenAdmin);
    v.setup.estadoTrasActivar = confirm.estado_cuenta;
    v.restauracion.necesaria = true;
    H.save(runId, `${v.key}_setup.json`, {
      accion: 'activar', http: r.status, estadoOriginal: v.estadoOriginal,
      estadoTrasActivar: confirm.estado_cuenta, accionDeRestauracionPrevista: v.plan.accionRestauracion
    });
    if (confirm.estado_cuenta !== 'Activo') {
      v.ejecutable = false;
      v.motivoBloqueo = `la activación temporal no dejó la cuenta Activa (HTTP ${r.status}, estado ${confirm.estado_cuenta}); no se reintenta`;
      log(`${v.key}: BLOQUEADO — ${v.motivoBloqueo}`);
    } else {
      v.ejecutable = true;
      log(`${v.key}: activada temporalmente (HTTP ${r.status}). Se restaurará a ${v.estadoOriginal}.`);
    }
  }

  const ejecutables = Object.values(actores).filter(v => v.ejecutable);
  if (!ejecutables.length) throw new Error('BLOQUEADO: ningún subescenario es ejecutable; no se envía ningún POST de calibración.');

  // Identidad y permisos del actor antes del POST (el rechazo debe ser por ROL, no por estado).
  for (const v of ejecutables) {
    const r = await H.login(v.correo, process.env[v.envPass]);
    v.login = { status: r.status, autenticado: r.status === 200 && Boolean(r.token) };
    if (!v.login.autenticado) {
      v.ejecutable = false;
      v.motivoBloqueo = `el actor no autentica (HTTP ${r.status}${r.errorCode ? ' ' + r.errorCode : ''})`;
      log(`${v.key}: BLOQUEADO — ${v.motivoBloqueo}`);
      continue;
    }
    const me = await H.getOk('/usuarios/me', r.token);
    const permisos = await H.getOk('/sesiones/me/permisos', r.token);
    const acciones = (permisos.permisos || []).filter(p => p.id_recurso === H.RECURSO_CALIBRACIONES).map(p => p.id_accion).sort();
    v.identidadActiva = { id_usuario: me.id_usuario, correo_electronico: me.correo_electronico, nombre_rol: me.nombre_rol, estado_cuenta: me.estado_cuenta };
    v.permisos = { accionesSobreCalibraciones: acciones, total: (permisos.permisos || []).length, permisoDeCreacionInesperado: acciones.includes(1) };
    H.save(runId, `${v.key}_identidad_activa.json`, { ...v.identidadActiva, credencial: '[REDACTED]' });
    H.save(runId, `${v.key}_permisos.json`, {
      id_usuario: me.id_usuario, ...v.permisos,
      nota: 'Un permiso de creación inesperado se registra como riesgo observado y NO bloquea la prueba: puede ser el propio defecto que el POST negativo debe revelar.'
    });
    if (me.estado_cuenta !== 'Activo') {
      v.ejecutable = false;
      v.motivoBloqueo = `la cuenta no está Activa en /usuarios/me (${me.estado_cuenta}); un 403 en ese estado no sería evidencia RBAC válida`;
      log(`${v.key}: BLOQUEADO — ${v.motivoBloqueo}`);
    } else if (me.nombre_rol !== v.rolEsperado) {
      v.ejecutable = false;
      v.motivoBloqueo = `/usuarios/me devuelve rol ${me.nombre_rol} y se esperaba ${v.rolEsperado}`;
      log(`${v.key}: BLOQUEADO — ${v.motivoBloqueo}`);
    } else {
      log(`${v.key}: id ${me.id_usuario}, rol ${me.nombre_rol}, estado ${me.estado_cuenta}, acciones sobre calibraciones ${JSON.stringify(acciones)}`);
    }
  }

  // ------------------------- trazabilidad de la automatización (antes del 1er POST)
  const artefactos = ['TC-M09-G77-v2.0.postman_collection.json', 'helpers.cjs', 'precheck.cjs', 'run-newman.cjs', 'verificar-cierre.cjs'];
  const automationDir = H.runDir(runId, 'automation');
  const manifest = [];
  for (const a of artefactos) {
    const src = path.join(__dirname, a);
    if (!fs.existsSync(src)) continue;
    const dst = path.join(automationDir, a);
    fs.writeFileSync(dst, H.clean(fs.readFileSync(src, 'utf8')));
    manifest.push({ archivo: a, sha256_original: H.sha256(src), sha256_copia: H.sha256(dst), bytes: fs.statSync(src).size });
  }
  H.save(runId, 'automation_manifest.json', { grupo: H.GROUP_ID, runId, commit: headSha, nota: 'SHA-256 de la automatización que produjo este RUN. Copias sanitizadas, sin secretos.', artefactos: manifest });

  // ------------------------------------------------------------------ env newman
  const bodyCalibracion = '{' +
    '"modo_calibracion":"SENSOR",' +
    `"id_dispositivo_iot":${fixture.dispositivo.id},` +
    `"id_infraestructura":${fixture.area.id_infraestructura},` +
    `"valor_referencia":${fixture.valor},` +
    `"observaciones":${JSON.stringify(H.OBSERVACIONES)},` +
    '"fecha_calibracion":"__FECHA__"' +
    '}';

  const env = [
    ['base_url', H.base()],
    ['ing_email', process.env.TEST_ENGINEER_EMAIL], ['ing_secret', process.env.TEST_ENGINEER_PASSWORD],
    ['admin_email', adminUsado], ['admin_secret', process.env.TEST_ADMIN_PASSWORD],
    ['device_id', String(fixture.dispositivo.id)], ['sensor_id', String(fixture.sensor.id)],
    ['area_id', String(fixture.area.id_infraestructura)], ['categoria', fixture.sensor.categoria],
    ['valor', fixture.valor], ['body_calibracion', bodyCalibracion],
    ['exp_msg_403', H.MENSAJE_403], ['stop_all', 'NO']
  ];
  for (const a of H.ACTORES) {
    const v = actores[a.key];
    env.push([`${a.key}_email`, v.correo]);
    env.push([`${a.key}_secret`, process.env[a.envPass]]);
    env.push([`${a.key}_estado_original`, v.estadoOriginal]);
  }

  log(`\nMensaje 403 esperado: ${H.MENSAJE_403}`);
  log(`\nIniciando el RUN oficial. POST de calibración planificados: ${H.POST_CALIBRACION_BUDGET}.\n`);

  newman.run({
    collection: path.join(__dirname, 'TC-M09-G77-v2.0.postman_collection.json'),
    reporters: ['cli', 'htmlextra'],
    reporter: {
      htmlextra: {
        export: htmlPath, omitHeaders: true, showEnvironmentData: false, showGlobalData: false,
        skipEnvironmentVars: ['ing_secret', 'admin_secret', 'productor_secret', 'contador_secret', 'ing_session', 'admin_session', 'productor_session', 'contador_session'],
        showMarkdownLinks: false
      }
    },
    envVar: env.map(([key, value]) => ({ key, value }))
  }, (err, summary) => {
    finalizar(err, summary).catch((e) => { console.error('Error al consolidar el RUN:', e.message); process.exitCode = 1; });
  });

  async function finalizar(err, summary) {
    const ex = summary?.run?.executions || [];
    const find = (n) => ex.find(x => x.item && x.item.name === n);
    const bodyOf = (n) => { const e = find(n); if (!e || !e.response) return null; try { return JSON.parse(e.response.stream.toString()); } catch { return null; } };
    const statusOf = (n) => { const e = find(n); return e && e.response ? e.response.code : null; };
    const sentOf = (n) => { const e = find(n); try { return JSON.parse(e.request.body.raw.toString()); } catch { return null; } };

    if (fs.existsSync(htmlPath)) fs.writeFileSync(htmlPath, H.cleanHtml(fs.readFileSync(htmlPath, 'utf8')));

    let postsEjecutados = 0;
    const resultados = {};

    for (const a of H.ACTORES) {
      const K = a.key;
      const v = actores[K];
      const pre = bodyOf(`${K} PRE historial`);
      const resp = bodyOf(`${K} POST calibrar`);
      const post = bodyOf(`${K} POST historial`);
      const status = statusOf(`${K} POST calibrar`);
      const enviado = sentOf(`${K} POST calibrar`);
      const ejecutado = status !== null;
      if (ejecutado) postsEjecutados += 1;

      if (pre) H.save(runId, `${K}_historial_pre.json`, pre);
      if (enviado) H.save(runId, `${K}_request.json`, {
        endpoint: `/configuracion/sensores/${fixture.sensor.id}/calibrar`, metodo: 'POST',
        actor: { correo: v.correo, rol: v.rolEsperado, id_usuario: v.identidadActiva?.id_usuario ?? null },
        headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' }, body: enviado
      });
      if (resp) H.save(runId, `${K}_response.json`, { http: status, cuerpo: resp });
      if (post) H.save(runId, `${K}_historial_post.json`, post);

      const preIds = pre ? (pre.items || []).map(x => x.id_calibracion) : null;
      const postIds = post ? (post.items || []).map(x => x.id_calibracion) : null;
      const nuevos = preIds && postIds ? postIds.filter(x => !preIds.includes(x)) : null;
      const actorId = v.identidadActiva?.id_usuario ?? null;
      const atribuibles = post && nuevos && actorId
        ? (post.items || []).filter(x => nuevos.includes(x.id_calibracion) && x.id_usuario === actorId).map(x => x.id_calibracion)
        : [];
      const obtenido = resp ? resp.message ?? null : null;

      let historicosIntactos = null;
      if (pre && post) {
        historicosIntactos = (pre.items || []).every(s => {
          const row = (post.items || []).find(x => x.id_calibracion === s.id_calibracion);
          return row && String(row.valor_referencia) === String(s.valor_referencia) &&
            row.fecha_calibracion === s.fecha_calibracion && row.id_usuario === s.id_usuario &&
            row.observaciones === s.observaciones;
        });
      }

      resultados[K] = {
        subescenario: v.rolEsperado, correo: v.correo, id_usuario: actorId,
        estadoOriginal: v.estadoOriginal,
        activacionTemporal: v.setup.ejecutado, httpActivacion: v.setup.http,
        ejecutado, motivoBloqueo: v.motivoBloqueo,
        cuentaActivaAlProbar: v.identidadActiva?.estado_cuenta === 'Activo',
        rolAlProbar: v.identidadActiva?.nombre_rol ?? null,
        permisos: v.permisos ?? null,
        httpEsperado: 403, httpObtenido: status,
        error_code: resp ? resp.error_code ?? null : null,
        mensajeEsperado: H.MENSAJE_403, mensajeObtenido: obtenido, mensajeCoincide: obtenido === H.MENSAJE_403,
        diferenciaDeMensaje: obtenido !== null && obtenido !== H.MENSAJE_403
          ? { esperado: H.MENSAJE_403, obtenido, nota: 'comparación exacta; un mensaje genérico no es PASS' } : null,
        devuelveIdCalibracion: resp ? resp.id_calibracion !== undefined : null,
        fechaEnviada: enviado ? enviado.fecha_calibracion : null,
        historialPre: pre ? { total: pre.total, ids: preIds } : null,
        historialPost: post ? { total: post.total, ids: postIds } : null,
        idsNuevos: nuevos, calibracionesAtribuiblesAlActor: atribuibles, historicosIntactos
      };
    }

    // Restauración del estado original. Se intenta siempre que sea posible, incluso si el
    // subescenario falló o se activó STOP_ALL.
    let restauracionesEjecutadas = 0;
    for (const a of H.ACTORES) {
      const v = actores[a.key];
      const r = resultados[a.key];
      if (!v.restauracion.necesaria) {
        r.restauracion = { necesaria: false, estadoOriginal: v.estadoOriginal, estadoFinal: v.estadoOriginal, restaurado: 'NO APLICABA' };
        continue;
      }
      const accion = v.plan.accionRestauracion;
      const res = await H.gestionarCuenta(v.cuenta.id_usuario, accion, tokenAdmin,
        `QA ${H.CASO}: restauración del estado original tras prueba de seguridad`);
      restauracionesEjecutadas += 1;
      const confirm = await H.localizarCuenta(v.correo, tokenAdmin);
      const ok = confirm.estado_cuenta === v.estadoOriginal;
      v.restauracion = { necesaria: true, ejecutada: true, http: res.status, estadoFinal: confirm.estado_cuenta, ok };
      H.save(runId, `${a.key}_restauracion.json`, {
        accion, http: res.status, estadoOriginal: v.estadoOriginal, estadoFinal: confirm.estado_cuenta,
        restaurado: ok, pendiente: !ok,
        nota: ok ? 'estado original restaurado y confirmado por consulta administrativa'
                 : 'RESTAURACIÓN PENDIENTE: no se probaron estados alternativos ni SQL; se escala tal cual'
      });
      r.restauracion = { necesaria: true, estadoOriginal: v.estadoOriginal, estadoFinal: confirm.estado_cuenta, restaurado: ok ? 'SI' : 'NO', http: res.status };
      log(`${a.key}: restauración a ${v.estadoOriginal} -> HTTP ${res.status}, estado final ${confirm.estado_cuenta}${ok ? '' : '  RESTAURACIÓN PENDIENTE'}`);
    }

    // Oráculo por subescenario.
    for (const K of Object.keys(resultados)) {
      const r = resultados[K];
      r.oraculo = {
        cuenta_activa_al_probar: r.cuentaActivaAlProbar === true,
        rol_correcto: r.rolAlProbar === r.subescenario,
        http_403: r.httpObtenido === 403,
        mensaje_exacto: r.mensajeCoincide === true,
        sin_id_calibracion: r.devuelveIdCalibracion === false,
        sin_persistencia: Array.isArray(r.idsNuevos) && r.idsNuevos.length === 0 && r.calibracionesAtribuiblesAlActor.length === 0,
        historicos_intactos: r.historicosIntactos === true,
        estado_restaurado: r.restauracion.restaurado === 'SI' || r.restauracion.restaurado === 'NO APLICABA'
      };
      r.resultado = !r.ejecutado
        ? 'BLOQUEADO / NO VERIFICABLE'
        : Object.values(r.oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO';
    }

    const stopAll = summary?.environment?.values?.find?.(x => x.key === 'stop_all')?.value === 'SI' ||
      Object.values(resultados).some(r => r.ejecutado && Array.isArray(r.idsNuevos) && r.idsNuevos.length > 0);
    const stopMotivo = summary?.environment?.values?.find?.(x => x.key === 'stop_all_motivo')?.value;

    const failures = (summary?.run?.failures || []).map(f => ({ item: f.source?.name, assertion: f.error?.test, error: f.error?.message })).filter(f => f.error);
    const rechazados = Object.values(resultados).filter(r => r.resultado === 'RECHAZADO').length;
    const bloqueados = Object.values(resultados).filter(r => r.resultado === 'BLOQUEADO / NO VERIFICABLE').length;
    const resultadoCaso = rechazados > 0 ? 'RECHAZADO' : bloqueados > 0 ? 'BLOQUEADO / NO VERIFICABLE' : 'APROBADO';
    const restauracionPendiente = Object.values(resultados).some(r => r.restauracion.restaurado === 'NO');

    const artifact = {
      grupo: H.GROUP_ID, caso: H.CASO, requisito: H.RF, casoDeUso: H.CU, tipo: H.TIPO,
      runId, commit: headSha, ambiente: { decisorio: 'TEST', base_url: H.base() },
      carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${H.FOLDER}/`,
      administradorDeSetup: { usado: adminUsado, credencial: '[REDACTED]', ejecutaPostDeCalibracion: false, getsQueLoRequirieron: usoAdmin },
      fixture: { origen, ...fixture },
      presupuesto: {
        postCalibracionPlanificados: H.POST_CALIBRACION_BUDGET, postCalibracionEjecutados: postsEjecutados,
        postSetupCuentaEjecutados: Object.values(actores).filter(v => v.setup.ejecutado).length,
        postRestauracionCuentaEjecutados: restauracionesEjecutadas
      },
      subescenarios: resultados, resultadoCaso,
      stopAll: stopAll ? 'SI' : 'NO', stopAllMotivo: stopMotivo ? JSON.parse(stopMotivo) : null,
      restauracionPendiente: restauracionPendiente ? 'SI' : 'NO',
      assertions: { total: summary?.run?.stats?.assertions?.total || 0, failed: failures.length, failures }
    };
    H.save(runId, `${H.GROUP_ID}.json`, artifact);

    log('\n================ RESUMEN DEL RUN ================');
    log(`RUN_ID: ${runId}`);
    log(`Fixture: sensor ${fixture.sensor.id} / dispositivo ${fixture.dispositivo.id} / infraestructura ${fixture.area.id_infraestructura}`);
    log(`POST de calibración: ${postsEjecutados}/${H.POST_CALIBRACION_BUDGET} | setup cuenta: ${artifact.presupuesto.postSetupCuentaEjecutados} | restauración cuenta: ${restauracionesEjecutadas}`);
    for (const r of Object.values(resultados)) {
      log(`  ${r.subescenario.padEnd(10)} estado original=${String(r.estadoOriginal).padEnd(8)} activa=${r.cuentaActivaAlProbar ? 'SI' : 'NO'} HTTP=${String(r.httpObtenido ?? '-').padEnd(4)} mensaje=${r.mensajeCoincide ? 'EXACTO' : 'NO COINCIDE'} persistencia=${r.oraculo.sin_persistencia ? 'NO' : 'SI/?'} restaurado=${r.restauracion.restaurado} → ${r.resultado}`);
    }
    log(`CASO ${H.CASO} → ${resultadoCaso}`);
    log(`GRUPO ${H.GROUP_ID} → ${resultadoCaso}`);
    log(`Assertions: ${artifact.assertions.total} | Failures: ${artifact.assertions.failed} | STOP_ALL: ${artifact.stopAll} | Restauración pendiente: ${artifact.restauracionPendiente}`);
    log('=================================================\n');

    if (err) process.exitCode = 1;
    else if (resultadoCaso !== 'APROBADO' || restauracionPendiente) process.exitCode = 2;
  }
})().catch((e) => { console.error('\nRUN NO COMPLETADO:', e.message); process.exitCode = 1; });
