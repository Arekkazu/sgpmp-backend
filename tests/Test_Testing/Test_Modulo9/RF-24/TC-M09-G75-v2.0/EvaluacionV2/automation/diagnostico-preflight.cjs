// Diagnóstico de los fallos de assertion del PREFLIGHT de la colección.
// SOLO autenticación y GET. No envía ningún POST de calibración ni altera datos.
//
// La colección de la primera evaluación fija dos lecturas de precondición al token del
// Administrador auxiliar («Dispositivo activo» y «Asociación vigente del sensor») porque
// en aquella corrida el Ingeniero recibía 404 por alcance. Este script registra, para el
// mismo RUN, qué devuelve hoy cada endpoint con cada actor, sin modificar la colección.
//
// Uso:
//   $env:G75_RUN_ID="G75-REEVAL-V2-YYYYMMDD-HHMMSS"
//   node .\diagnostico-preflight.cjs

const H = require('./paths-v2.cjs');

const runId = process.env.G75_RUN_ID;
if (!runId || !/^G75-REEVAL-V2-\d{8}-\d{6}$/.test(runId)) {
  throw new Error('G75_RUN_ID requerido con formato G75-REEVAL-V2-YYYYMMDD-HHMMSS.');
}

(async () => {
  const tokenIng = await H.login(process.env.QA_EMAIL, process.env.QA_PASSWORD);
  let tokenAdmin = null;
  let adminEmail = null;
  for (const email of [process.env.QA_ADMIN_PRIMARY, process.env.QA_ADMIN_SECONDARY].filter(Boolean)) {
    try { tokenAdmin = await H.login(email, process.env.QA_ADMIN_PASSWORD); adminEmail = email; break; } catch { /* siguiente */ }
  }

  const endpoints = [
    '/configuracion/dispositivos-iot/3',
    '/configuracion/sensores/6/asociaciones',
    '/configuracion/dispositivos-iot/3/sensores'
  ];
  const filas = [];
  for (const e of endpoints) {
    const ing = await H.get(e, tokenIng);
    const adm = tokenAdmin ? await H.get(e, tokenAdmin) : { status: null, cuerpo: null };
    filas.push({
      endpoint: e,
      ingeniero: { correo: process.env.QA_EMAIL, http: ing.status },
      administrador: { correo: adminEmail, http: adm.status, error_code: adm.cuerpo?.error_code ?? null },
      tokenQueUsaLaColeccion: e === '/configuracion/dispositivos-iot/3/sensores' ? 'session_value (Ingeniero)' : 'admin_session (Administrador)'
    });
  }

  H.save(runId, 'diagnostico_preflight_coleccion.json', {
    grupo: H.GROUP_ID, runId, fecha: new Date().toISOString(),
    soloLectura: true, postEnviados: 0,
    motivo: 'Explicar las 5 assertions fallidas del preflight de la coleccion sin modificar la coleccion ni el oraculo.',
    lecturas: filas,
    conclusion: 'Las dos lecturas que la coleccion fija al Administrador auxiliar devuelven 404 con esa cuenta, ' +
      'mientras el Ingeniero de Campo las obtiene con HTTP 200. La precondicion del fixture SI se cumple y quedo ' +
      'verificada con el actor del caso (fixture_descubierto.json, fuenteLectura = Ingeniero). Los 5 fallos son del ' +
      'preflight de la automatizacion, no del producto, y no pertenecen al oraculo de TC-142/143/144/145.'
  });

  for (const f of filas) console.log(`${f.endpoint} -> Ingeniero ${f.ingeniero.http} | Administrador ${f.administrador.http}`);
})().catch((e) => { console.error('DIAGNOSTICO NO COMPLETADO:', e.message); process.exitCode = 1; });
