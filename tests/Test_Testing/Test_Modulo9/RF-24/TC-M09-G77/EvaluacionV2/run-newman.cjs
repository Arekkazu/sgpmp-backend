// TC-M09-G77 / TC-M09-148 — REEVALUACION V2: ejecucion del unico POST negativo.
// Un POST por invocacion, maximo dos en toda la reevaluacion (RF-24 §69).
const fs = require('fs');
const path = require('path');
const newman = require('newman');
require.resolve('newman-reporter-htmlextra');
const H = require('./helpers.cjs');
const { caso, runId, intento } = H.settings();

const archivoHtml = `newman-${caso}-reevaluacion-v2-intento${intento}`;
const archivoJson = `${caso}-reevaluacion-v2-intento${intento}`;
const evid = H.dir(runId);
const htmlDir = H.dir(runId, 'newman');

if (fs.existsSync(path.join(evid, archivoJson + '.json')) || fs.existsSync(path.join(htmlDir, archivoHtml + '.html'))) {
  throw Error('No sobrescribir la evidencia de este intento');
}
if (fs.existsSync(path.join(evid, `${caso}-reevaluacion-v2-intento2.json`))) {
  throw Error('Maximo 2 POST en la reevaluacion: el presupuesto ya esta consumido');
}
if (intento === 2 && !fs.existsSync(path.join(evid, `${caso}-reevaluacion-v2-intento1.json`))) {
  throw Error('El intento 2 requiere el intento 1 registrado y justificado');
}
const precheck = JSON.parse(fs.readFileSync(path.join(evid, 'precheck-v2.json'), 'utf8'));
if (!Object.values(precheck.checklist).every((v) => v === true)) {
  throw Error('El precheck no dejo el escenario listo: no se ejecuta el POST');
}

const eventos = [];
(async () => {
  const plan = precheck.plan;

  // Lectura autorizada (solo GET) para el historial: mismo actor del precheck.
  const lectura = precheck.actorDiscoveryEfectivo.escalado
    ? await H.login(H.ACTOR_DISCOVERY_GLOBAL, process.env.TEST_ADMIN_PASSWORD)
    : await H.login(H.ACTOR_DISCOVERY, process.env.TEST_ENGINEER_PASSWORD);
  if (!lectura.token) throw Error(`ENVIRONMENT_ERROR login lector HTTP ${lectura.status}`);

  const antes = await H.get(`/configuracion/sensores/${plan.sensor.id_sensores}/calibraciones`, lectura.token);
  const historyBefore = {
    actor: precheck.actorDiscoveryEfectivo.rol + ' (GET read-only)',
    total: antes.total,
    ids: antes.items.map((c) => c.id_calibracion),
    items: antes.items.map((c) => ({ id_calibracion: c.id_calibracion, id_usuario: c.id_usuario, valor_referencia: String(c.valor_referencia), fecha_calibracion: c.fecha_calibracion })),
  };

  // Sesion del actor negativo. El token vive solo en memoria de este proceso.
  const prod = await H.login(H.ACTOR_NEGATIVO, process.env.TEST_PRODUCTOR_PASSWORD);
  if (prod.status !== 200 || !prod.token) throw Error(`El actor negativo no autentico: HTTP ${prod.status} ${prod.errorCode || ''}`);
  const me = await H.get('/usuarios/me', prod.token);
  const permisosRecurso12 = (await H.get('/sesiones/me/permisos', prod.token)).permisos
    .filter((p) => p.id_recurso === H.RECURSO_SENSORES).map((p) => p.id_accion).sort();
  if (me.nombre_rol !== 'Productor') throw Error(`El actor negativo no es Productor sino ${me.nombre_rol}`);
  if (permisosRecurso12.includes(H.ACCION_CREAR)) throw Error('El actor negativo tiene permiso de creacion: no es un actor no autorizado');

  const actor = {
    correo_electronico: me.correo_electronico,
    id_usuario: me.id_usuario,
    nombre_rol: me.nombre_rol,
    estado_cuenta: me.estado_cuenta,
    autenticado: true,
    permisosRecurso12,
  };
  const contexto = {
    actor,
    rolesAutorizadosRF24: H.ROLES_AUTORIZADOS_RF24,
    dispositivo: plan.dispositivo,
    sensor: plan.sensor,
    areaCorrecta: plan.areaCorrecta,
    rangoTecnico: plan.rangoTecnico,
  };
  const cuerpo = H.construirCuerpo(plan, runId);

  const collection = JSON.parse(fs.readFileSync(path.join(__dirname, 'TC-M09-G77-reevaluacion-v2.postman_collection.json'), 'utf8'));
  if (collection.item.length !== 1) throw Error('La coleccion debe contener un unico request');

  const summary = await new Promise((resolve, reject) => {
    const run = newman.run({
      collection,
      reporters: ['htmlextra'],
      timeoutRequest: 25000,
      reporter: {
        htmlextra: {
          export: path.join(htmlDir, archivoHtml + '.html'),
          omitHeaders: true,
          showEnvironmentData: false,
          showGlobalData: false,
          skipEnvironmentVars: ['token'],
          logs: false,
          silentProgressBar: true,
          title: `${caso} — G77 REEVALUACION V2 — RF-24 TEST — intento ${intento}`,
        },
      },
      environment: {
        values: Object.entries({
          base_url: H.BASE,
          token: prod.token,
          id_sensor: plan.sensor.id_sensores,
          payload: cuerpo.texto,
          contexto: JSON.stringify(contexto),
        }).map(([key, value]) => ({ key, value: String(value), enabled: true })),
      },
    }, (err, s) => (err ? reject(Error('Newman execution error: ' + H.clean(err.message || ''))) : resolve(s)));

    run.on('request', (err, args) => {
      let body = null;
      try { body = args.response?.json(); } catch { /* respuesta sin JSON */ }
      args.request.headers.remove('Authorization');
      args.response?.headers?.remove('set-cookie');
      eventos.push({
        metodo: args.request.method,
        url: H.clean(args.request.url.toString()),
        status: args.response?.code ?? null,
        cuerpoEnviado: cuerpo.texto,
        respuesta: body,
        transportError: !!err,
      });
    });
  });

  const despues = await H.get(`/configuracion/sensores/${plan.sensor.id_sensores}/calibraciones`, lectura.token);
  const historyAfter = {
    actor: historyBefore.actor,
    total: despues.total,
    ids: despues.items.map((c) => c.id_calibracion),
    items: despues.items.map((c) => ({ id_calibracion: c.id_calibracion, id_usuario: c.id_usuario, valor_referencia: String(c.valor_referencia), fecha_calibracion: c.fecha_calibracion })),
  };

  const post = eventos.find((e) => e.metodo === 'POST');
  const idsPrevios = historyBefore.ids;
  const nuevos = historyAfter.ids.filter((id) => !idsPrevios.includes(id));
  const desaparecidos = idsPrevios.filter((id) => !historyAfter.ids.includes(id));
  const alterados = historyBefore.items.filter((prev) => {
    const ahora = historyAfter.items.find((c) => c.id_calibracion === prev.id_calibracion);
    return ahora && (ahora.valor_referencia !== prev.valor_referencia || ahora.fecha_calibracion !== prev.fecha_calibracion);
  }).map((c) => c.id_calibracion);
  const atribuibleAlProductor = historyAfter.items.filter(
    (c) => nuevos.includes(c.id_calibracion) && c.id_usuario === actor.id_usuario
  );

  const persistio = nuevos.length > 0 || post?.status === 201 || !!post?.respuesta?.id_calibracion;
  const es403Rbac = post?.status === 403 && post?.respuesta?.error_code === 'ACCESO_DENEGADO';
  const resultado = es403Rbac && !persistio && !alterados.length && !desaparecidos.length && summary.run.failures.length === 0
    ? 'PASS' : 'FAIL';

  const html = path.join(htmlDir, archivoHtml + '.html');
  if (!fs.existsSync(html)) throw Error('HTML reporter no generado');
  fs.writeFileSync(html, H.clean(fs.readFileSync(html, 'utf8')));

  H.save(runId, archivoJson + '.json', {
    intento,
    resultado,
    actor: { correo_electronico: actor.correo_electronico, id_usuario: actor.id_usuario, nombre_rol: actor.nombre_rol, estado_cuenta: actor.estado_cuenta, autenticado: true, permisosRecurso12 },
    rolesAutorizadosRF24: H.ROLES_AUTORIZADOS_RF24,
    autenticacion: { endpoint: 'POST /sesiones/', status: 200, tokenPersistido: false },
    dispositivo: plan.dispositivo,
    sensor: plan.sensor,
    area: plan.areaCorrecta,
    rangoTecnico: plan.rangoTecnico,
    valorReferencia: plan.valor,
    endpoint: `POST /configuracion/sensores/${plan.sensor.id_sensores}/calibrar`,
    cuerpoEnviado: cuerpo.objeto,
    status: post?.status ?? null,
    responseCodeFuncional: post?.respuesta?.error_code ?? null,
    respuesta: post?.respuesta ?? null,
    origen403: es403Rbac ? 'RBAC del endpoint (require_permission recurso 12 accion 1)' : 'no aplica / por determinar',
    historyBefore,
    historyAfter,
    persistencia: {
      registrosNuevos: nuevos,
      atribuiblesAlProductor: atribuibleAlProductor,
      historicosAlterados: alterados,
      historicosDesaparecidos: desaparecidos,
      idCalibracionCreado: post?.respuesta?.id_calibracion ?? null,
      persistio,
    },
    eventos,
    assertions: summary.run.stats.assertions,
    failures: summary.run.failures.map((f) => ({ test: f.error?.test || f.error?.name, message: H.clean(f.error?.message || '') })),
    newman: '6.2.2',
    reporter: 'newman-reporter-htmlextra 1.23.1',
    html: path.relative(evid, html).split(path.sep).join('/'),
    postEjecutados: intento,
  });

  console.log(`${caso} V2 intento ${intento}: ${resultado} | POST ${post?.status} ${post?.respuesta?.error_code ?? '-'}`);
  console.log(`historial ${historyBefore.total} -> ${historyAfter.total} | nuevos ${nuevos.length} | alterados ${alterados.length} | persistio ${persistio}`);
  console.log(`assertions ${summary.run.stats.assertions.total} total, ${summary.run.failures.length} fallidas`);
  summary.run.failures.forEach((f) => console.log('   FAIL:', f.error?.test, '->', H.clean(f.error?.message || '').slice(0, 160)));
  process.exitCode = resultado === 'PASS' ? 0 : 1;
})().catch((e) => {
  H.save(runId, archivoJson + '-error.json', { intento, resultado: 'ERROR', motivo: H.clean(e.message), eventos });
  console.log('ERROR:', H.clean(e.message));
  process.exitCode = 1;
});
