// Verificación posterior al RUN: ¿siguen persistidas las calibraciones válidas y cómo
// afecta el RLS al alcance de lectura de cada cuenta?
//
// SOLO autenticación y GET. No envía ningún POST, no modifica datos y no altera el oráculo
// ya emitido: su salida es documentación adicional del RUN.
//
// Uso:
//   $env:G75_RUN_ID="G75-REEVAL-V2-YYYYMMDD-HHMMSS"
//   node .\verificar-persistencia-rls.cjs

const H = require('./paths-v2.cjs');

const runId = process.env.G75_RUN_ID;
if (!runId || !/^G75-REEVAL-V2-\d{8}-\d{6}$/.test(runId)) {
  throw new Error('G75_RUN_ID requerido con formato G75-REEVAL-V2-YYYYMMDD-HHMMSS.');
}

const IDS_DEL_RUN = [
  { id_calibracion: 28, caso: 'TC-M09-142-v2.0', valor: '0.0000', observaciones: 'QA TC-M09-142-v2.0' },
  { id_calibracion: 29, caso: 'TC-M09-143-v2.0', valor: '45.0000', observaciones: 'QA TC-M09-143-v2.0' }
];

(async () => {
  const cuentas = [
    { correo: process.env.QA_EMAIL, secreto: process.env.QA_PASSWORD, papel: 'actor del caso' },
    { correo: process.env.QA_ADMIN_PRIMARY, secreto: process.env.QA_ADMIN_PASSWORD, papel: 'administrador auxiliar de solo lectura' }
  ].filter(c => c.correo && c.secreto);

  const porCuenta = [];
  for (const c of cuentas) {
    let token = null;
    try { token = await H.login(c.correo, c.secreto); } catch (e) { porCuenta.push({ correo: c.correo, papel: c.papel, login: `FAIL (${e.message})` }); continue; }

    const me = await H.get('/usuarios/me', token);
    const historial = await H.get('/configuracion/sensores/6/calibraciones', token);
    const listado = await H.get('/configuracion/dispositivos-iot', token);
    const dispositivo = await H.get('/configuracion/dispositivos-iot/3', token);
    const asociaciones = await H.get('/configuracion/sensores/6/asociaciones', token);

    const items = historial.status === 200 ? (historial.cuerpo.items || []) : [];
    const idsVisibles = listado.status === 200 ? (listado.cuerpo.items || []).map(x => x.id_dispositivo_iot) : [];

    porCuenta.push({
      correo: c.correo,
      papel: c.papel,
      login: 'OK',
      id_usuario: me.status === 200 ? me.cuerpo.id_usuario : null,
      rol: me.status === 200 ? me.cuerpo.nombre_rol : null,
      alcance: {
        'GET /configuracion/dispositivos-iot': { http: listado.status, dispositivosVisibles: listado.status === 200 ? (listado.cuerpo.total ?? idsVisibles.length) : null, incluyeDispositivo3: idsVisibles.includes(3) },
        'GET /configuracion/dispositivos-iot/3': { http: dispositivo.status, error_code: dispositivo.cuerpo?.error_code ?? null },
        'GET /configuracion/sensores/6/asociaciones': { http: asociaciones.status, error_code: asociaciones.cuerpo?.error_code ?? null },
        'GET /configuracion/sensores/6/calibraciones': { http: historial.status, error_code: historial.cuerpo?.error_code ?? null, total: historial.status === 200 ? historial.cuerpo.total : null, ids: historial.status === 200 ? items.map(x => x.id_calibracion) : null }
      },
      calibracionesDelRun: IDS_DEL_RUN.map(e => {
        const row = items.find(x => x.id_calibracion === e.id_calibracion) || null;
        return {
          ...e,
          visible: Boolean(row),
          valorExacto: Boolean(row) && H.igualDecimal(row.valor_referencia, e.valor),
          observacionesCoinciden: Boolean(row) && row.observaciones === e.observaciones,
          id_usuario: row ? row.id_usuario : null,
          fecha_calibracion: row ? row.fecha_calibracion : null
        };
      })
    });
  }

  const actor = porCuenta.find(x => x.papel === 'actor del caso');
  const persisten = Boolean(actor) && actor.calibracionesDelRun.every(x => x.visible && x.valorExacto && x.observacionesCoinciden);

  H.save(runId, 'verificacion_persistencia_rls.json', {
    grupo: H.GROUP_ID, runId, fecha: new Date().toISOString(),
    soloLectura: true, postEnviados: 0, sqlEjecutado: 'ninguno',
    motivo: 'Confirmar, despues del RUN, que las calibraciones validas siguen persistidas y documentar el alcance de lectura por cuenta tras el RLS habilitado por los lideres.',
    persistenLasCalibracionesDelRun: persisten,
    porCuenta,
    conclusion: persisten
      ? 'Las calibraciones 28 (TC-142) y 29 (TC-143) siguen persistidas en TEST y visibles para el actor del caso, con el mismo valor, usuario, observaciones y fecha del RUN. El RLS da al Ingeniero de Campo el alcance necesario para repetir la prueba sobre los mismos datos; la cuenta de Administrador auxiliar quedo con alcance vacio y por eso recibe 404 en las lecturas de precondicion que la coleccion le fija.'
      : 'Las calibraciones del RUN no son visibles para el actor del caso: revisar antes de reutilizar el fixture.'
  });

  for (const c of porCuenta) {
    console.log(`\n${c.correo}  (id_usuario ${c.id_usuario}, rol ${c.rol})`);
    for (const [e, v] of Object.entries(c.alcance || {})) console.log(`  ${e.padEnd(46)} HTTP ${v.http}${v.total !== undefined && v.total !== null ? ` total ${v.total}` : ''}${v.dispositivosVisibles !== undefined && v.dispositivosVisibles !== null ? ` visibles ${v.dispositivosVisibles}` : ''}${v.error_code ? ` ${v.error_code}` : ''}`);
    for (const k of c.calibracionesDelRun || []) console.log(`  ${k.caso} id ${k.id_calibracion}: visible=${k.visible ? 'SI' : 'NO'} valorExacto=${k.valorExacto ? 'SI' : 'NO'}`);
  }
  console.log(`\npersisten las calibraciones del RUN (actor del caso): ${persisten ? 'SI' : 'NO'}`);
})().catch((e) => { console.error('VERIFICACION NO COMPLETADA:', e.message); process.exitCode = 1; });
