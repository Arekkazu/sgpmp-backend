// TC-M09-G24 V2 — un original por invocacion: un POST real + GET de persistencia.
// Maximo 2 POST por original; no se reintenta un PASS ni un negativo que persistio.
const fs = require('fs');
const path = require('path');
const newman = require('newman');
require.resolve('newman-reporter-htmlextra');
const H = require('./helpers.cjs');
const { runId, caso, intento } = H.settings();

const sufijo = intento === 1 ? '' : '-intento2';
const nombre = `${caso}-v2${sufijo}`;
const evid = H.dir(runId);
const html = path.join(H.dir(runId, 'newman'), `newman-${nombre}.html`);
if ([nombre + '.json', nombre + '-error.json'].some((f) => fs.existsSync(path.join(evid, f))) || fs.existsSync(html)) throw Error('No sobrescribir la evidencia de este intento');
if (fs.existsSync(path.join(evid, `${caso}-v2-intento2.json`))) throw Error(`Maximo 2 POST por original: ${caso} ya consumio su presupuesto`);
const previo = H.load(runId, `${caso}-v2.json`);
if (intento === 2) {
  if (!previo) throw Error('El intento 2 requiere el intento 1 registrado');
  if (previo.resultado === 'PASS') throw Error('No se reintenta un PASS');
  if (previo.persistencia?.registrosDeLaCombinacion > 0) throw Error('El intento 1 persistio: no se realiza otro POST');
}
const plan = H.load(runId, 'plan-v2.json');
if (!plan || !Object.values(plan.checklist[caso]).every(Boolean)) throw Error('Checklist previo del caso incompleto');
// Un negativo previo que haya persistido detiene el uso de la combinacion.
for (const c of H.CASOS.filter((x) => x !== caso)) {
  const ev = H.load(runId, `${c}-v2.json`);
  if (ev?.STOP_COMBINACION) throw Error(`La combinacion quedo contaminada por ${c}: detener`);
}

const eventos = [];
(async () => {
  const preflight = await H.preflight();
  const token = await H.login();
  const actor = await H.validarActor(token);
  const ctx = plan.planes[caso];

  // Redescubrimiento previo: especie activa, variable publicada y combinacion aun libre.
  const especie = (await H.get('/configuracion/especies', token)).items.find((s) => s.id_especie === ctx.especie.id);
  const variable = (await H.get('/configuracion/variables-ambientales', token)).items.find((v) => v.id_variable_ambiental === ctx.variable.id);
  const antes = (await H.get(`/configuracion/umbrales?id_especie=${ctx.especie.id}`, token)).items;
  const libreAntes = !antes.some((u) => u.id_variable_ambiental === ctx.variable.id);
  if (!especie?.es_activo || !variable || !libreAntes) throw Error(`PRECONDICION: especieActiva=${!!especie?.es_activo} variable=${!!variable} libre=${libreAntes}`);

  const payload = ctx.payload;
  const texto = H.cuerpo(payload);
  const analisis = H.analizar(payload);
  const collection = JSON.parse(fs.readFileSync(path.join(__dirname, 'TC-M09-G24-reevaluacion-v2.postman_collection.json'), 'utf8'));
  collection.item = collection.item.filter((i) => i.name === caso);
  if (collection.item.length !== 1) throw Error('Una invocacion ejecuta un unico original');

  const summary = await new Promise((resolve, reject) => {
    const run = newman.run({
      collection, reporters: ['htmlextra'], timeoutRequest: 25000,
      reporter: { htmlextra: { export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false, skipEnvironmentVars: ['token'],
        logs: false, silentProgressBar: true, title: `${caso} — G24 REEVALUACION V2 — RF-17 TEST${sufijo}` } },
      environment: { values: Object.entries({ base_url: H.BASE, token, id_especie: payload.id_especie, id_variable: payload.id_variable_ambiental, payload: texto })
        .map(([key, value]) => ({ key, value: String(value), enabled: true })) },
    }, (err, s) => (err ? reject(Error('Newman execution error')) : resolve(s)));
    run.on('request', (err, args) => {
      let body; try { body = args.response?.json(); } catch { /* sin JSON */ }
      args.request.headers.remove('Authorization'); args.response?.headers?.remove('set-cookie');
      eventos.push({ metodo: args.request.method, status: args.response?.code ?? null, respuesta: args.request.method === 'POST' ? body : undefined, transportError: !!err });
    });
  });

  const despues = (await H.get(`/configuracion/umbrales?id_especie=${ctx.especie.id}`, token)).items;
  const post = eventos.find((e) => e.metodo === 'POST');
  const deLaCombinacion = despues.filter((u) => u.id_variable_ambiental === ctx.variable.id);
  const idCreado = post?.status === 201 ? post.respuesta?.id_umbral_ambiental ?? null : null;
  const previosConservados = antes.every((u) => despues.some((x) => x.id_umbral_ambiental === u.id_umbral_ambiental));
  const oraculo = H.ORACULO[caso];
  let resultado;
  let stopCombinacion = false;
  if (oraculo.persiste) {
    const u = deLaCombinacion.find((x) => x.id_umbral_ambiental === idCreado);
    resultado = post?.status === 201 && u && deLaCombinacion.length === 1 && previosConservados && summary.run.failures.length === 0 ? 'PASS' : 'FAIL';
  } else {
    stopCombinacion = deLaCombinacion.length > 0 || post?.status === 201;
    resultado = !stopCombinacion && post?.status === oraculo.status && post?.respuesta?.error_code === oraculo.error_code && previosConservados && summary.run.failures.length === 0 ? 'PASS' : 'FAIL';
  }

  fs.writeFileSync(html, H.clean(fs.readFileSync(html, 'utf8')));
  H.save(runId, nombre + '.json', {
    caso, intento, resultado, ambiente: 'TEST', actor, preflight,
    especie: ctx.especie, variable: ctx.variable, limitesFisicos: { min: ctx.variable.fisicoMin, max: ctx.variable.fisicoMax },
    rangoGeneral: ctx.rangoGeneral, niveles: payload.niveles, analisisPayload: analisis,
    precondiciones: { especieActiva: true, variablePublicada: true, combinacionLibreAntes: libreAntes, umbralesPreviosEspecie: antes.map((u) => u.id_umbral_ambiental) },
    endpoint: 'POST /configuracion/umbrales', payloadEnviado: payload, cuerpoEnviado: texto,
    oraculo, status: post?.status ?? null, errorCode: post?.respuesta?.error_code ?? null, respuesta: post?.respuesta ?? null, idCreado,
    getPosterior: { endpoint: `GET /configuracion/umbrales?id_especie=${ctx.especie.id}`, status: 200, total: despues.length, ids: despues.map((u) => u.id_umbral_ambiental) },
    persistencia: { registrosDeLaCombinacion: deLaCombinacion.length, previosConservados,
      detalle: deLaCombinacion.map((u) => ({ id: u.id_umbral_ambiental, id_especie: u.id_especie, id_variable_ambiental: u.id_variable_ambiental, valor_min: u.valor_min, valor_max: u.valor_max, es_activo: u.es_activo, niveles: u.niveles })) },
    STOP_COMBINACION: stopCombinacion,
    eventos, assertions: summary.run.stats.assertions,
    failures: summary.run.failures.map((f) => ({ test: f.error?.test || f.error?.name, message: H.clean(f.error?.message || '') })),
    newman: '6.2.2', reporter: 'newman-reporter-htmlextra 1.23.1', html: path.relative(evid, html).split(path.sep).join('/'),
  });

  console.log(`${caso}${sufijo}: ${resultado} | POST ${post?.status} ${post?.respuesta?.error_code ?? ''} | id ${idCreado} | registros combinacion ${deLaCombinacion.length}`
    + ` | previos ${previosConservados} | assertions ${summary.run.stats.assertions.total} fallidas ${summary.run.failures.length}${stopCombinacion ? ' | STOP_COMBINACION' : ''}`);
  if (post?.respuesta?.message) console.log('   mensaje:', H.clean(post.respuesta.message));
  summary.run.failures.slice(0, 6).forEach((f) => console.log('   FAIL:', f.error?.test, '->', H.clean(f.error?.message || '').slice(0, 150)));
  process.exitCode = resultado === 'PASS' ? 0 : 1;
})().catch((e) => {
  H.save(runId, nombre + '-error.json', { caso, intento, resultado: 'ERROR', motivo: H.clean(e.message), eventos });
  console.log('ERROR:', H.clean(e.message));
  process.exitCode = 1;
});
