// Verificación final de TC-M09-G77-v2.0: SOLO autenticación y GET.
// No crea, edita ni elimina nada. Sin SQL. Nunca borra una calibración inesperada.
//
// Uso:
//   $env:G77_RUN_ID="run-YYYYMMDD-HHMMSS"
//   node .\verificar-cierre.cjs

const fs = require('fs');
const path = require('path');
const H = require('./helpers.cjs'); // Incluye la guarda de directorio autorizado.

const runId = process.env.G77_RUN_ID;
if (!runId) throw new Error('G77_RUN_ID requerido.');
const evid = H.runDir(runId);
const artifactPath = path.join(evid, `${H.GROUP_ID}.json`);
if (!fs.existsSync(artifactPath)) throw new Error(`No existe ${H.GROUP_ID}.json: ejecute primero run-newman.cjs.`);
const A = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));

(async () => {
  const tokenIng = await H.loginOk(process.env.TEST_ENGINEER_EMAIL, process.env.TEST_ENGINEER_PASSWORD, 'Ingeniero');
  let tokenAdmin = null;
  for (const email of [process.env.TEST_ADMIN_PRIMARY, process.env.TEST_ADMIN_SECONDARY].filter(Boolean)) {
    const r = await H.login(email, process.env.TEST_ADMIN_PASSWORD);
    if (r.status === 200 && r.token) { tokenAdmin = r.token; break; }
  }
  if (!tokenAdmin) throw new Error('Sin Administrador no se puede confirmar el estado final de las cuentas.');

  const usoAdmin = [];
  const leer = H.lectorConFallback(tokenIng, tokenAdmin, usoAdmin);

  const sensorId = A.fixture.sensor.id;
  const deviceId = A.fixture.dispositivo.id;

  // Estado final de cada cuenta frente a su estado original.
  const cuentas = {};
  for (const [k, r] of Object.entries(A.subescenarios)) {
    const actual = await H.localizarCuenta(r.correo, tokenAdmin);
    cuentas[k] = {
      subescenario: r.subescenario, correo: r.correo, id_usuario: actual.id_usuario,
      rol: actual.nombre_rol,
      estadoOriginal: r.estadoOriginal, estadoFinal: actual.estado_cuenta,
      coincideConElOriginal: actual.estado_cuenta === r.estadoOriginal,
      seModificoDuranteLaPrueba: r.activacionTemporal === true,
      restauracionPendiente: r.activacionTemporal === true && actual.estado_cuenta !== r.estadoOriginal
    };
  }

  // Historial: ninguna calibración atribuible a los roles rechazados.
  const historial = await H.getOk(`/configuracion/sensores/${sensorId}/calibraciones`, tokenIng);
  const idsFinales = (historial.items || []).map(x => x.id_calibracion);
  const porSubescenario = {};
  for (const [k, r] of Object.entries(A.subescenarios)) {
    const idsPre = r.historialPre?.ids || [];
    const atribuibles = (historial.items || []).filter(x =>
      (r.id_usuario && x.id_usuario === r.id_usuario) ||
      (x.observaciones === H.OBSERVACIONES && r.fechaEnviada &&
       new Date(x.fecha_calibracion).getTime() === new Date(r.fechaEnviada).getTime())
    );
    porSubescenario[k] = {
      subescenario: r.subescenario,
      idsPre, totalPre: r.historialPre?.total ?? null, totalFinal: historial.total,
      idsNuevosDesdePre: idsFinales.filter(x => !idsPre.includes(x)),
      calibracionesAtribuibles: atribuibles.map(x => ({ id_calibracion: x.id_calibracion, id_usuario: x.id_usuario, observaciones: x.observaciones })),
      sinRegistrosAtribuibles: atribuibles.length === 0,
      historicosSiguenPresentes: idsPre.every(id => idsFinales.includes(id))
    };
  }

  // Fixture sin cambios.
  const dispositivo = (await leer(`/configuracion/dispositivos-iot/${deviceId}`)).cuerpo;
  const asociaciones = (await leer(`/configuracion/sensores/${sensorId}/asociaciones`, true)).cuerpo;
  const rangos = await H.getOk('/configuracion/sensores/rangos-calibracion', tokenIng);
  const rango = (rangos.items || []).find(r => r.categoria === A.fixture.rango.categoria) || null;
  const vigentes = (asociaciones.items || []).filter(H.vigente);

  H.save(runId, 'verificacion-final-readonly.json', {
    grupo: H.GROUP_ID, caso: H.CASO, runId, fecha: new Date().toISOString(),
    soloLectura: true, sqlEjecutado: 'ninguno',
    cuentas,
    todasLasCuentasEnSuEstadoOriginal: Object.values(cuentas).every(c => c.coincideConElOriginal),
    restauracionPendiente: Object.values(cuentas).some(c => c.restauracionPendiente),
    historial: { total: historial.total, idsFinales, porSubescenario },
    sinCalibracionesDeRolesRechazados: Object.values(porSubescenario).every(x => x.sinRegistrosAtribuibles),
    fixture: {
      dispositivo: { id: dispositivo?.id_dispositivo_iot, es_activo: dispositivo?.es_activo },
      asociacionesVigentes: vigentes.map(x => ({ id_sensor: H.sensorIdOf(x), id_dispositivo_iot: x.id_dispositivo_iot, id_infraestructura: x.id_infraestructura })),
      rangoActual: rango,
      sinCambios: dispositivo?.es_activo === A.fixture.dispositivo.es_activo &&
        vigentes.some(x => H.sensorIdOf(x) === sensorId && x.id_infraestructura === A.fixture.area.id_infraestructura) &&
        Boolean(rango) && H.igualDecimal(rango.valor_min, A.fixture.rango.min) && H.igualDecimal(rango.valor_max, A.fixture.rango.max)
    },
    getsConAdministrador: usoAdmin
  });

  // Escaneo de secretos: se buscan VALORES, no vocabulario en prosa.
  const patrones = [
    [/eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\./, 'JWT'],
    [/Bearer\s+[A-Za-z0-9_.-]{12,}/, 'Authorization con token'],
    [/set-cookie/i, 'cabecera de cookie'],
    [/(access|refresh)_token"?\s*[:=]\s*"?[A-Za-z0-9_.-]{12,}/i, 'token en clave/valor'],
    [/(password|contrasena|contraseña)"?\s*[:=]\s*"?[^"\s,}\]]{4,}/i, 'credencial en clave/valor'],
    [/postgres(ql)?:\/\//i, 'cadena de conexión']
  ];
  // En automation/ el código fuente contiene legítimamente ese vocabulario y los propios
  // patrones del escáner: allí solo cuentan VALORES de secreto.
  const soloValores = patrones.filter(([, n]) => n === 'JWT' || n === 'Authorization con token' || n === 'cadena de conexión');
  const credenciales = [
    process.env.TEST_PRODUCTOR_PASSWORD, process.env.TEST_CONTADOR_PASSWORD,
    process.env.TEST_ENGINEER_PASSWORD, process.env.TEST_ADMIN_PASSWORD
  ].filter(Boolean);
  const revisados = [];
  const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).forEach(e => {
    const p = path.join(d, e.name);
    if (e.isDirectory()) return walk(p);
    if (!/\.(html|json|md|txt|cjs)$/i.test(e.name)) return;
    const rel = path.relative(evid, p).split(path.sep).join('/');
    const esCodigo = rel.startsWith('automation/') && /\.cjs$/i.test(rel);
    const txt = fs.readFileSync(p, 'utf8');
    revisados.push({
      archivo: rel, bytes: txt.length, tipo: esCodigo ? 'codigo-fuente' : 'evidencia',
      secretos: (esCodigo ? soloValores : patrones).filter(([re]) => re.test(txt)).map(([, n]) => n),
      credencialesEnClaro: [...new Set(credenciales)].filter(x => txt.includes(x)).length
    });
  });
  walk(evid);
  const sucios = revisados.filter(r => r.secretos.length || r.credencialesEnClaro);

  H.save(runId, 'seguridad-evidencias.json', {
    grupo: H.GROUP_ID, runId, limpio: sucios.length === 0, archivosConHallazgos: sucios, revisados,
    criterio: 'Se marcan solo valores de secreto: contraseñas, JWT, Authorization con token, cookies, tokens en pares clave-valor y cadenas de conexión. En automation/ (código fuente) solo se evalúan valores. Los correos de los actores los publica el propio caso y no son secretos del requisito.',
    nota: 'Reporter htmlextra con omitHeaders, sin environment ni globals y con skipEnvironmentVars; sanitización posterior del HTML y de todo JSON de evidencia.'
  });

  for (const c of Object.values(cuentas)) {
    console.log(`${c.subescenario}: estado original ${c.estadoOriginal} | final ${c.estadoFinal} | coincide: ${c.coincideConElOriginal}${c.restauracionPendiente ? '  RESTAURACION PENDIENTE' : ''}`);
  }
  console.log(`historial final del sensor ${sensorId}: total ${historial.total} | ids ${idsFinales.join(', ')}`);
  console.log(`sin calibraciones de roles rechazados: ${Object.values(porSubescenario).every(x => x.sinRegistrosAtribuibles)}`);
  console.log(`evidencia limpia de secretos: ${sucios.length === 0}`);
  if (sucios.length) process.exitCode = 3;
})().catch((e) => { console.error('VERIFICACION DE CIERRE NO COMPLETADA:', e.message); process.exitCode = 1; });
