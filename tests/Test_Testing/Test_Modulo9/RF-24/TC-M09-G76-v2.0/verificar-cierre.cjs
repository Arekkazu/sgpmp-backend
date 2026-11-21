// Verificación final de TC-M09-G76-v2.0: SOLO autenticación y GET.
// No crea, edita ni elimina nada. Sin SQL.
//
// Uso:
//   $env:G76_RUN_ID="run-YYYYMMDD-HHMMSS"
//   node .\verificar-cierre.cjs

const fs = require('fs');
const path = require('path');
const H = require('./helpers.cjs'); // Incluye la guarda de directorio autorizado.

const runId = process.env.G76_RUN_ID;
if (!runId) throw new Error('G76_RUN_ID requerido.');
const evid = H.runDir(runId);
const artifactPath = path.join(evid, `${H.GROUP_ID}.json`);
if (!fs.existsSync(artifactPath)) throw new Error(`No existe ${H.GROUP_ID}.json: ejecute primero run-newman.cjs.`);
const A = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));

(async () => {
  const tokenIng = await H.login(process.env.QA_EMAIL, process.env.QA_PASSWORD);
  let tokenAdmin = null;
  for (const email of [process.env.QA_ADMIN_PRIMARY, process.env.QA_ADMIN_SECONDARY].filter(Boolean)) {
    try { tokenAdmin = await H.login(email, process.env.QA_ADMIN_PASSWORD); break; } catch { /* siguiente */ }
  }
  const usoAdmin = [];
  const leer = H.lectorConFallback(tokenIng, tokenAdmin, usoAdmin);

  const d146 = A.fixture146.dispositivo.id;
  const s146 = A.fixture146.sensor.id;
  const s147 = A.fixture147.sensor.id;
  const d147 = A.fixture147.dispositivo.id;

  // El dispositivo de TC-146 debe continuar inactivo.
  const dispositivo146 = (await leer(`/configuracion/dispositivos-iot/${d146}`)).cuerpo;
  // La asociación de TC-147 no pudo ser alterada por un rechazo.
  const asociaciones147 = (await leer(`/configuracion/sensores/${s147}/asociaciones`)).cuerpo;
  const dispositivo147 = (await leer(`/configuracion/dispositivos-iot/${d147}`)).cuerpo;

  const hist146 = await H.getOk(`/configuracion/sensores/${s146}/calibraciones`, tokenIng);
  const hist147 = await H.getOk(`/configuracion/sensores/${s147}/calibraciones`, tokenIng);

  const comparar = (k, historialFinal) => {
    const c = A.casos[k];
    if (!c || !c.historialPre) return null;
    const idsFinales = (historialFinal.items || []).map(x => x.id_calibracion);
    const idsPre = c.historialPre.ids || [];
    const atribuibles = (historialFinal.items || []).filter(
      x => x.observaciones === H.CASOS[k].observaciones && c.fechaEnviada &&
           new Date(x.fecha_calibracion).getTime() === new Date(c.fechaEnviada).getTime()
    );
    return {
      caso: c.caso,
      totalPre: c.historialPre.total, totalFinal: historialFinal.total,
      idsPre, idsFinales,
      idsNuevosDesdePre: idsFinales.filter(x => !idsPre.includes(x)),
      calibracionesAtribuiblesAlRechazo: atribuibles.map(x => x.id_calibracion),
      elRechazoNoPersistio: atribuibles.length === 0 && idsFinales.filter(x => !idsPre.includes(x)).length === 0,
      historicosSiguenPresentes: idsPre.every(id => idsFinales.includes(id))
    };
  };

  const vigentes147 = (asociaciones147.items || []).filter(H.vigente);
  const asociacionVigenteSinCambios =
    vigentes147.length === 1 &&
    H.sensorIdOf(vigentes147[0]) === s147 &&
    vigentes147[0].id_infraestructura === A.fixture147.areaVigente.id_infraestructura &&
    vigentes147[0].id_dispositivo_iot === d147;

  const resultado = {
    grupo: H.GROUP_ID, runId, fecha: new Date().toISOString(),
    soloLectura: true, sqlEjecutado: 'ninguno',
    tc146: {
      dispositivo: { id: dispositivo146.id_dispositivo_iot, serial: dispositivo146.serial, es_activo: dispositivo146.es_activo },
      continuaInactivo: dispositivo146.es_activo === false,
      historial: comparar('146', hist146)
    },
    tc147: {
      dispositivo: { id: dispositivo147.id_dispositivo_iot, es_activo: dispositivo147.es_activo },
      asociacionVigente: vigentes147.map(x => ({ id_sensor: H.sensorIdOf(x), id_dispositivo_iot: x.id_dispositivo_iot, id_infraestructura: x.id_infraestructura, fecha_finalizacion: x.fecha_finalizacion })),
      asociacionVigenteSinCambios,
      historial: comparar('147', hist147)
    },
    getsConAdministrador: usoAdmin
  };
  H.save(runId, 'verificacion-final-readonly.json', resultado);

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
  const credenciales = [process.env.QA_PASSWORD, process.env.QA_ADMIN_PASSWORD].filter(Boolean);
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
      credencialesEnClaro: credenciales.filter(x => txt.includes(x)).length
    });
  });
  walk(evid);
  const sucios = revisados.filter(r => r.secretos.length || r.credencialesEnClaro);

  H.save(runId, 'seguridad-evidencias.json', {
    grupo: H.GROUP_ID, runId, limpio: sucios.length === 0, archivosConHallazgos: sucios, revisados,
    criterio: 'Se marcan solo valores de secreto: contraseñas, JWT, Authorization con token, cookies, tokens en pares clave-valor y cadenas de conexión. En automation/ (código fuente) solo se evalúan valores. El correo del actor lo publica el propio caso y no es un secreto del requisito.',
    nota: 'Reporter htmlextra con omitHeaders, sin environment ni globals y con skipEnvironmentVars; sanitización posterior del HTML y de todo JSON de evidencia.'
  });

  console.log(`TC-146 dispositivo ${d146} continua inactivo: ${resultado.tc146.continuaInactivo}`);
  console.log(`TC-146 el rechazo no persistio: ${resultado.tc146.historial?.elRechazoNoPersistio}`);
  console.log(`TC-147 asociacion vigente sin cambios: ${asociacionVigenteSinCambios}`);
  console.log(`TC-147 el rechazo no persistio: ${resultado.tc147.historial?.elRechazoNoPersistio}`);
  console.log(`evidencia limpia de secretos: ${sucios.length === 0}`);
  if (sucios.length) process.exitCode = 3;
})().catch((e) => { console.error('VERIFICACION DE CIERRE NO COMPLETADA:', e.message); process.exitCode = 1; });
