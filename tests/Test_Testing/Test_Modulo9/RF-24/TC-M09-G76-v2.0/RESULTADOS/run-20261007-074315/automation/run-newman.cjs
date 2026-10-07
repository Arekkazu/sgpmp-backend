// Runner del único RUN oficial de TC-M09-G76-v2.0 (RF-24 v2.0, CU05 Flujo D).
//
// Presupuesto: 2 POST de calibración (sin reintentos) y, como máximo, 1 PATCH de
// preparación de TC-146, que solo se ejecuta si NO existe ningún dispositivo ya inactivo
// utilizable y el candidato supera todas las comprobaciones de seguridad. El PATCH requiere
// además confirmación explícita por variable de entorno, porque el contrato no expone
// reactivación de dispositivos y el efecto es irreversible.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_EMAIL="ingeniero@pecuaria.co"
//   $env:QA_PASSWORD="<secreto>"
//   $env:QA_ADMIN_PRIMARY="admin.dev@gmail.com"
//   $env:QA_ADMIN_SECONDARY="administador.dev@gmail.com"
//   $env:QA_ADMIN_PASSWORD="<secreto>"
//   $env:G76_RUN_ID="run-YYYYMMDD-HHMMSS"
//   node .\run-newman.cjs
//
// Para autorizar la preparación irreversible, solo si el runner la reporta necesaria:
//   $env:G76_AUTORIZAR_PATCH_DESACTIVAR="SI"

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const H = require('./helpers.cjs'); // Incluye la guarda de directorio autorizado.

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const runId = process.env.G76_RUN_ID;
if (!runId || !/^run-\d{8}-\d{6}$/.test(runId)) throw new Error('G76_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
const actorEmail = process.env.QA_EMAIL;
const actorSecret = process.env.QA_PASSWORD;
if (!actorEmail || !actorSecret) throw new Error('QA_EMAIL y QA_PASSWORD requeridos (solo en memoria de proceso).');
const adminSecret = process.env.QA_ADMIN_PASSWORD;

const outputDir = path.join(__dirname, 'RESULTADOS', runId);
if (fs.existsSync(outputDir)) throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);

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
const git = (args) => { try { return execFileSync('git', args, { cwd: repoRoot, encoding: 'utf8' }).trim(); } catch (e) { return `ERROR: ${e.message}`; } };

(async () => {
  // ------------------------------------------------------------------- git_pre
  const gitPre = [
    '# git_pre.txt — TC-M09-G76-v2.0', `# Capturado: ${new Date().toISOString()}`, '',
    `$ git branch --show-current\n${git(['branch', '--show-current'])}`, '',
    `$ git status --short\n${git(['status', '--short']) || '(vacio)'}`, '',
    `$ git diff --stat\n${git(['diff', '--stat']) || '(vacio)'}`, '',
    `$ git diff --cached --stat\n${git(['diff', '--cached', '--stat']) || '(vacio)'}`, '',
    `$ git rev-parse HEAD\n${git(['rev-parse', 'HEAD'])}`, '',
    `$ git rev-parse origin/test\n${git(['rev-parse', 'origin/test'])}`, '',
    `$ git rev-list --left-right --count HEAD...origin/test\n${git(['rev-list', '--left-right', '--count', 'HEAD...origin/test'])}`, '',
    '# Carpeta histórica TC-M09-G76 (debe quedar intacta)',
    `$ git status --short -- tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G76\n${git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G76']) || '(vacio = intacta)'}`
  ].join('\n');
  fs.writeFileSync(path.join(H.runDir(runId), 'git_pre.txt'), H.clean(gitPre));
  const headSha = git(['rev-parse', 'HEAD']);

  // ------------------------------------------------------- preflight OpenAPI
  const openapi = await (await fetch(H.base() + '/openapi.json', { signal: AbortSignal.timeout(30000) })).json();
  const requeridos = [
    ['post', '/configuracion/sensores/{id_sensor}/calibrar'],
    ['get', '/configuracion/sensores/{id_sensor}/calibraciones'],
    ['get', '/configuracion/sensores/{id_sensor}/asociaciones'],
    ['get', '/configuracion/dispositivos-iot/{id_dispositivo_iot}'],
    ['get', '/configuracion/dispositivos-iot/{id_dispositivo_iot}/sensores'],
    ['get', '/configuracion/infraestructuras/{id_infraestructura}'],
    ['get', '/configuracion/dispositivos-iot/{id_dispositivo_iot}/configuraciones'],
    ['patch', '/configuracion/dispositivos-iot/{id_dispositivo_iot}/desactivar']
  ];
  const endpoints = {};
  for (const [m, p] of requeridos) {
    const op = openapi.paths?.[p]?.[m] || null;
    endpoints[`${m.toUpperCase()} ${p}`] = { presente: Boolean(op), summary: op?.summary ?? null, codigosDeclarados: op ? Object.keys(op.responses || {}) : [] };
  }
  H.save(runId, 'openapi_preflight.json', {
    grupo: H.GROUP_ID, fuente: H.base() + '/openapi.json', endpoints,
    requestSchemaDelPost: openapi.components?.schemas?.RegistrarCalibracionDTO
      ? { properties: Object.keys(openapi.components.schemas.RegistrarCalibracionDTO.properties || {}), required: openapi.components.schemas.RegistrarCalibracionDTO.required || [] } : null,
    modo_calibracion_declarado_en_openapi: JSON.stringify(openapi).includes('modo_calibracion'),
    nota: 'modo_calibracion se envía como exige el caso aunque OpenAPI no lo declare. G76 no prueba el enum ni la obligatoriedad de ese campo.'
  });
  for (const [k, v] of Object.entries(endpoints)) {
    if (!v.presente && !k.startsWith('PATCH')) throw new Error(`BLOQUEADO: ${k} no está desplegado en TEST.`);
  }
  log('OpenAPI: endpoints del grupo verificados.');

  // --------------------------------------------------------------- identidad
  let tokenIng;
  try { tokenIng = await H.login(actorEmail, actorSecret); }
  catch (e) { throw new Error(`BLOQUEADO: el Ingeniero no autentica (${e.message}). No se prueban otras contraseñas ni se sustituye por Administrador.`); }
  const identidad = await H.getOk('/usuarios/me', tokenIng);
  if (identidad.correo_electronico !== actorEmail || identidad.nombre_rol !== 'Ingeniero de Campo') {
    throw new Error('BLOQUEADO: la identidad autenticada no corresponde al Ingeniero de Campo del caso.');
  }
  H.save(runId, 'identidad_actor.json', { id_usuario: identidad.id_usuario, correo_electronico: identidad.correo_electronico, nombre_rol: identidad.nombre_rol, credencial: '[REDACTED]' });

  const permisos = await H.getOk('/sesiones/me/permisos', tokenIng);
  const tiene = (r, a) => (permisos.permisos || []).some(p => p.id_recurso === r && p.id_accion === a);
  const permisosCaso = { leerDispositivos: tiene(11, 2), registrarCalibraciones: tiene(12, 1), consultarHistorial: tiene(12, 2) };
  H.save(runId, 'permisos_actor.json', { id_usuario: identidad.id_usuario, permisosDelCaso: permisosCaso, total: (permisos.permisos || []).length });
  if (!permisosCaso.registrarCalibraciones || !permisosCaso.consultarHistorial) throw new Error('BLOQUEADO: el Ingeniero no tiene los permisos funcionales del caso.');
  log(`Ingeniero autenticado (id_usuario ${identidad.id_usuario}, ${identidad.nombre_rol}).`);

  // Administrador auxiliar, en el orden autorizado y un solo intento por cuenta.
  let tokenAdmin = null, adminUsado = null;
  const intentosAdmin = [];
  for (const email of [process.env.QA_ADMIN_PRIMARY, process.env.QA_ADMIN_SECONDARY].filter(Boolean)) {
    try { tokenAdmin = await H.login(email, adminSecret); adminUsado = email; intentosAdmin.push({ email, resultado: 'autentica' }); break; }
    catch (e) { intentosAdmin.push({ email, resultado: `no autentica (${e.message})` }); }
  }
  if (adminUsado) log(`Administrador auxiliar de solo lectura: ${adminUsado}`);

  // ----------------------------------------------------------- fixture TC-146
  const usoAdmin = [];
  const d146 = await H.fixture146(tokenIng, tokenAdmin, usoAdmin);
  let f146 = d146.fixture;
  let patchEjecutado = 0;
  let setupInfo = { seUsoPatch: false, motivo: null };

  if (!f146) {
    // No existe dispositivo inactivo utilizable: preparación autorizada, con confirmación.
    H.save(runId, 'setup_146_candidatos.json', {
      totalInactivosEnTest: d146.totalInactivosEnTest,
      requierePatch: true,
      candidatosSeguros: d146.candidatosParaPatch.map(c => ({
        dispositivo: c.dispositivo, sensor: c.sensor, area: c.area,
        serialEsQA: c.serialEsQA, dependientesDeGateway: c.dependientesDeGateway, configuracionesPendientes: c.configuracionesPendientes
      }))
    });
    if (!d146.candidatosParaPatch.length) {
      throw new Error('BLOQUEADO: TC-M09-146-v2.0 no es verificable. No hay dispositivo inactivo utilizable ni candidato seguro para la preparación autorizada.');
    }
    if (process.env.G76_AUTORIZAR_PATCH_DESACTIVAR !== 'SI') {
      throw new Error(
        'DETENIDO antes de la preparación: haría falta PATCH /desactivar, que es irreversible ' +
        '(el contrato no expone reactivación de dispositivos). Candidatos seguros en ' +
        'setup_146_candidatos.json. Para autorizar: G76_AUTORIZAR_PATCH_DESACTIVAR=SI'
      );
    }
    const c = d146.candidatosParaPatch[0];
    const tokenSetup = tokenAdmin || tokenIng; // Actor con alcance sobre el dispositivo de prueba.
    H.save(runId, 'setup_146_dispositivo_pre.json', c.dispositivo);
    H.save(runId, 'setup_146_dependencias_gateway.json', { dispositivo: c.dispositivo.id, dependientes: [], criterio: 'ningún otro dispositivo declara id_dispositivo_gateway igual a este' });
    H.save(runId, 'setup_146_configuraciones.json', { dispositivo: c.dispositivo.id, configuracionesPendientes: 0 });
    const r = await H.patch(`/configuracion/dispositivos-iot/${c.dispositivo.id}/desactivar`, tokenSetup);
    patchEjecutado = 1;
    H.save(runId, 'setup_146_response.json', { http: r.status, cuerpo: r.cuerpo });
    const post = await H.getOk(`/configuracion/dispositivos-iot/${c.dispositivo.id}`, tokenSetup);
    H.save(runId, 'setup_146_dispositivo_post.json', post);
    if (post.es_activo !== false) throw new Error(`La preparación no dejó el dispositivo ${c.dispositivo.id} inactivo (HTTP PATCH ${r.status}). No se reintenta ni se prueba otro dispositivo.`);
    f146 = { ...c, dispositivo: { ...c.dispositivo, es_activo: false, serial: post.serial } };
    setupInfo = {
      seUsoPatch: true,
      dispositivo: c.dispositivo.id,
      actorDeSetup: adminUsado ? `Administrador ${adminUsado}` : 'Ingeniero',
      actorFuncionalDelCaso: 'Ingeniero de campo',
      httpPatch: r.status,
      quedaInactivoComoFixtureReutilizable: true,
      nota: 'El contrato no expone reactivación de dispositivos: el dispositivo queda inactivo a propósito y sirve como fixture reutilizable para futuras ejecuciones de TC-146. No se intentó restaurarlo por SQL ni inventando endpoints.'
    };
    log(`Preparación ejecutada: dispositivo ${c.dispositivo.id} desactivado (HTTP ${r.status}).`);
  } else {
    setupInfo = { seUsoPatch: false, motivo: `se encontró un dispositivo ya inactivo utilizable (${d146.totalInactivosEnTest} inactivos en TEST); no se ejecutó ningún PATCH` };
  }

  H.save(runId, 'fixture_146.json', {
    origen: d146.preexistenteInactivo ? 'dispositivo YA inactivo preexistente (sin PATCH)' : 'dispositivo desactivado por preparación autorizada',
    preexistenteInactivo: d146.preexistenteInactivo,
    totalInactivosEnTest: d146.totalInactivosEnTest,
    dispositivo: f146.dispositivo, sensor: f146.sensor, area: f146.area,
    valorEnviado: f146.valorInterior, historialInicial: f146.historialInicial,
    preparacion: setupInfo
  });
  H.save(runId, 'rango_146.json', { rango: f146.rango, valorInterior: f146.valorInterior, criterio: 'punto medio exacto del rango: valor interior, nunca una frontera' });
  log(`TC-146: dispositivo ${f146.dispositivo.id} (${f146.dispositivo.serial}, inactivo) / sensor ${f146.sensor.id} ${f146.sensor.categoria} / área ${f146.area.id_infraestructura} / valor ${f146.valorInterior}`);

  // ----------------------------------------------------------- fixture TC-147
  const d147 = await H.fixture147(tokenIng, tokenAdmin, usoAdmin);
  const f147 = d147.fixture;
  H.save(runId, 'fixture_147.json', { origen: d147.origen, ...f147 });
  H.save(runId, 'rango_147.json', { rango: f147.rango, valorEnviado: f147.valor });
  log(`TC-147: sensor ${f147.sensor.id} / dispositivo ${f147.dispositivo.id} activo / área vigente ${f147.areaVigente.id_infraestructura} / área alternativa ${f147.areaAlternativa.id_infraestructura} / valor ${f147.valor}`);

  H.save(runId, 'administrador_discovery.json', { intentos: intentosAdmin, usado: adminUsado || null, getsQueLoRequirieron: usoAdmin, ejecutaPostDeCalibracion: false });

  // ---------------------- trazabilidad de la automatización (antes de escribir)
  const artefactos = ['TC-M09-G76-v2.0.postman_collection.json', 'helpers.cjs', 'run-newman.cjs', 'verificar-cierre.cjs'];
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

  // ---------------------------------------------------------------- env newman
  const cuerpo = (dispositivo, area, valor, observaciones) =>
    `{"modo_calibracion":"SENSOR","id_dispositivo_iot":${dispositivo},"id_infraestructura":${area},"valor_referencia":${valor},"observaciones":${JSON.stringify(observaciones)},"fecha_calibracion":"__FECHA__"}`;

  const exp146 = H.mensaje146(f146.dispositivo.serial);
  const exp147 = H.mensaje147(f147.sensor.id, f147.areaAlternativa.id_infraestructura);

  const env = [
    ['base_url', H.base()], ['actor_email', actorEmail], ['actor_secret', actorSecret],
    ['admin_email', adminUsado || ''], ['admin_secret', adminUsado ? adminSecret : ''],
    ['device_146', String(f146.dispositivo.id)], ['serial_146', f146.dispositivo.serial],
    ['sensor_146', String(f146.sensor.id)], ['area_146', String(f146.area.id_infraestructura)],
    ['cat_146', f146.sensor.categoria], ['valor_146', f146.valorInterior],
    ['body_146', cuerpo(f146.dispositivo.id, f146.area.id_infraestructura, f146.valorInterior, H.CASOS['146'].observaciones)],
    ['exp_msg_146', exp146],
    ['device_147', String(f147.dispositivo.id)], ['sensor_147', String(f147.sensor.id)],
    ['area_vigente_147', String(f147.areaVigente.id_infraestructura)],
    ['area_alt_147', String(f147.areaAlternativa.id_infraestructura)],
    ['cat_147', f147.sensor.categoria], ['valor_147', f147.valor],
    ['body_147', cuerpo(f147.dispositivo.id, f147.areaAlternativa.id_infraestructura, f147.valor, H.CASOS['147'].observaciones)],
    ['exp_msg_147', exp147],
    ['stop_all', 'NO']
  ];

  log(`\nMensaje esperado TC-146: ${exp146}`);
  log(`Mensaje esperado TC-147: ${exp147}`);
  log('\nIniciando el RUN oficial. POST de calibración planificados: 2.\n');

  newman.run({
    collection: path.join(__dirname, 'TC-M09-G76-v2.0.postman_collection.json'),
    reporters: ['cli', 'htmlextra'],
    reporter: { htmlextra: { export: htmlPath, omitHeaders: true, showEnvironmentData: false, showGlobalData: false, skipEnvironmentVars: ['actor_secret', 'admin_secret', 'session_value', 'admin_session'], showMarkdownLinks: false } },
    envVar: env.map(([key, value]) => ({ key, value }))
  }, (err, summary) => {
    try { finalizar(err, summary); }
    catch (e) { console.error('Error al consolidar el RUN:', e.message); process.exitCode = 1; }
  });

  function finalizar(err, summary) {
    const ex = summary?.run?.executions || [];
    const find = (n) => ex.find(x => x.item && x.item.name === n);
    const bodyOf = (n) => { const e = find(n); if (!e || !e.response) return null; try { return JSON.parse(e.response.stream.toString()); } catch { return null; } };
    const statusOf = (n) => { const e = find(n); return e && e.response ? e.response.code : null; };
    const sentOf = (n) => { const e = find(n); try { return JSON.parse(e.request.body.raw.toString()); } catch { return null; } };

    if (fs.existsSync(htmlPath)) fs.writeFileSync(htmlPath, H.cleanHtml(fs.readFileSync(htmlPath, 'utf8')));

    const casos = {};
    let postsEjecutados = 0;

    for (const [k, meta] of Object.entries(H.CASOS)) {
      const pre = bodyOf(`${k} PRE historial`);
      const resp = bodyOf(`${k} POST calibrar`);
      const post = bodyOf(`${k} POST historial`);
      const status = statusOf(`${k} POST calibrar`);
      const enviado = sentOf(`${k} POST calibrar`);
      const ejecutado = status !== null;
      if (ejecutado) postsEjecutados += 1;

      if (pre) H.save(runId, `${k}_historial_pre.json`, pre);
      if (enviado) H.save(runId, `${k}_request.json`, {
        endpoint: `/configuracion/sensores/${k === '146' ? f146.sensor.id : f147.sensor.id}/calibrar`,
        metodo: 'POST', headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' }, body: enviado
      });
      if (resp) H.save(runId, `${k}_response.json`, { http: status, cuerpo: resp });
      if (post) H.save(runId, `${k}_historial_post.json`, post);

      const preIds = pre ? (pre.items || []).map(x => x.id_calibracion) : null;
      const postIds = post ? (post.items || []).map(x => x.id_calibracion) : null;
      const nuevos = preIds && postIds ? postIds.filter(x => !preIds.includes(x)) : null;
      const esperado = k === '146' ? exp146 : exp147;
      const obtenido = resp ? resp.message ?? null : null;

      // Ningún registro histórico pudo ser alterado por un rechazo.
      let historicosIntactos = null;
      if (pre && post) {
        historicosIntactos = (pre.items || []).every(s => {
          const row = (post.items || []).find(x => x.id_calibracion === s.id_calibracion);
          return row && String(row.valor_referencia) === String(s.valor_referencia) &&
            row.fecha_calibracion === s.fecha_calibracion && row.id_usuario === s.id_usuario &&
            row.observaciones === s.observaciones;
        });
      }

      const oraculo = {
        [`http_${meta.http}`]: status === meta.http,
        mensaje_exacto: obtenido === esperado,
        sin_persistencia: Array.isArray(nuevos) && nuevos.length === 0,
        total_sin_cambios: Boolean(pre) && Boolean(post) && Number(pre.total) === Number(post.total),
        historial_intacto: historicosIntactos === true
      };

      casos[k] = {
        caso: meta.caso, titulo: meta.titulo, ejecutado,
        httpEsperado: meta.http, httpObtenido: status,
        error_code: resp ? resp.error_code ?? null : null,
        mensajeEsperado: esperado, mensajeObtenido: obtenido, mensajeCoincide: obtenido === esperado,
        diferenciaDeMensaje: obtenido !== null && obtenido !== esperado
          ? { esperado, obtenido, nota: 'comparación exacta; un mensaje aproximado no es PASS' } : null,
        fechaEnviada: enviado ? enviado.fecha_calibracion : null,
        bodyEnviado: enviado,
        historialPre: pre ? { total: pre.total, ids: preIds } : null,
        historialPost: post ? { total: post.total, ids: postIds } : null,
        idsNuevos: nuevos,
        historicosIntactos,
        oraculo,
        resultado: !ejecutado ? 'NO EJECUTADO' : Object.values(oraculo).every(x => x === true) ? 'APROBADO' : 'RECHAZADO'
      };
    }

    const stopAll = summary?.environment?.values?.find?.(x => x.key === 'stop_all')?.value === 'SI' ||
      Object.values(casos).some(c => c.ejecutado && Array.isArray(c.idsNuevos) && c.idsNuevos.length > 0);
    const stopMotivo = summary?.environment?.values?.find?.(x => x.key === 'stop_all_motivo')?.value;

    const failures = (summary?.run?.failures || []).map(f => ({ item: f.source?.name, assertion: f.error?.test, error: f.error?.message })).filter(f => f.error);
    const rechazados = Object.values(casos).filter(c => c.resultado === 'RECHAZADO').length;
    const noEjecutados = Object.values(casos).filter(c => c.resultado === 'NO EJECUTADO').length;
    const resultadoGrupo = rechazados > 0 ? 'RECHAZADO' : noEjecutados > 0 ? 'BLOQUEADO / NO VERIFICABLE' : 'APROBADO';

    const artifact = {
      grupo: H.GROUP_ID, requisito: H.RF, casoDeUso: H.CU, runId, commit: headSha,
      ambiente: { decisorio: 'TEST', base_url: H.base() },
      carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${H.FOLDER}/`,
      actor: { id_usuario: identidad.id_usuario, correo: identidad.correo_electronico, rol: identidad.nombre_rol, credencial: '[REDACTED]' },
      administradorDiscovery: { usado: adminUsado || null, getsQueLoRequirieron: usoAdmin, ejecutaPostDeCalibracion: false },
      preparacion146: setupInfo,
      fixture146: { dispositivo: f146.dispositivo, sensor: f146.sensor, area: f146.area, rango: f146.rango, valorEnviado: f146.valorInterior, preexistenteInactivo: d146.preexistenteInactivo },
      fixture147: { dispositivo: f147.dispositivo, sensor: f147.sensor, areaVigente: f147.areaVigente, areaAlternativa: f147.areaAlternativa, rango: f147.rango, valorEnviado: f147.valor, origen: d147.origen },
      presupuesto: { postCalibracionPlanificados: H.POST_BUDGET, postCalibracionEjecutados: postsEjecutados, patchSetupPlanificados: H.PATCH_SETUP_BUDGET, patchSetupEjecutados: patchEjecutado },
      stopAll: stopAll ? 'SI' : 'NO', stopAllMotivo: stopMotivo ? JSON.parse(stopMotivo) : null,
      casos, resultadoGrupo,
      assertions: { total: summary?.run?.stats?.assertions?.total || 0, failed: failures.length, failures }
    };
    H.save(runId, `${H.GROUP_ID}.json`, artifact);

    log('\n================ RESUMEN DEL RUN ================');
    log(`RUN_ID: ${runId}`);
    log(`TC-146: dispositivo ${f146.dispositivo.id} (${f146.dispositivo.serial}) | inactivo preexistente: ${d146.preexistenteInactivo ? 'SI' : 'NO'} | PATCH setup: ${patchEjecutado}`);
    log(`TC-147: sensor ${f147.sensor.id} | área vigente ${f147.areaVigente.id_infraestructura} | área alternativa ${f147.areaAlternativa.id_infraestructura}`);
    log(`POST de calibración: ${postsEjecutados}/${H.POST_BUDGET}`);
    for (const c of Object.values(casos)) {
      log(`  ${c.caso} HTTP esperado=${c.httpEsperado} obtenido=${c.httpObtenido} | mensaje=${c.mensajeCoincide ? 'EXACTO' : 'NO COINCIDE'} | persistencia=${c.oraculo.sin_persistencia ? 'NO' : 'SI/?'} → ${c.resultado}`);
    }
    log(`GRUPO ${H.GROUP_ID} → ${resultadoGrupo}`);
    log(`Assertions: ${artifact.assertions.total} | Failures: ${artifact.assertions.failed} | STOP_ALL: ${artifact.stopAll}`);
    log('=================================================\n');

    if (err) process.exitCode = 1;
    else if (resultadoGrupo !== 'APROBADO') process.exitCode = 2;
  }
})().catch((e) => { console.error('\nRUN NO COMPLETADO:', e.message); process.exitCode = 1; });
