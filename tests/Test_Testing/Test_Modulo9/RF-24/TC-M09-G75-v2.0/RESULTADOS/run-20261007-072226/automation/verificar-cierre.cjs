// Verificación final de TC-M09-G75-v2.0: SOLO autenticación y GET.
// Nunca crea, edita ni elimina calibraciones. Sin SQL.
//
// Uso:
//   $env:G75_RUN_ID="run-YYYYMMDD-HHMMSS"
//   node .\verificar-cierre.cjs

const fs = require('fs');
const path = require('path');
const H = require('./helpers.cjs'); // Incluye la guarda de directorio autorizado.

const runId = process.env.G75_RUN_ID;
if (!runId) throw new Error('G75_RUN_ID requerido.');
const evid = H.runDir(runId);
const artifactPath = path.join(evid, `${H.GROUP_ID}.json`);
if (!fs.existsSync(artifactPath)) throw new Error(`No existe ${H.GROUP_ID}.json en el RUN: ejecute primero run-newman.cjs.`);
const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));

(async () => {
  const token = await H.login(process.env.QA_EMAIL, process.env.QA_PASSWORD);
  const sensorId = artifact.fixture.sensor.id;
  const deviceId = artifact.fixture.dispositivo.id;

  const historial = await H.getOk(`/configuracion/sensores/${sensorId}/calibraciones`, token);
  const rangos = await H.getOk('/configuracion/sensores/rangos-calibracion', token);
  const sensores = await H.getOk(`/configuracion/dispositivos-iot/${deviceId}/sensores`, token);

  const rango = (rangos.items || []).find(r => r.categoria === artifact.rango.categoria) || null;
  const idsFinales = (historial.items || []).map(c => c.id_calibracion);

  // Las calibraciones válidas creadas por el RUN deben seguir presentes e intactas.
  const validas = Object.entries(artifact.resultadosPorVariante)
    .filter(([, r]) => r.valido && r.registroPersistido)
    .map(([k, r]) => {
      const snap = r.registroPersistido;
      const row = (historial.items || []).find(x => x.id_calibracion === snap.id_calibracion) || null;
      return {
        variante: k, caso: r.caso, id_calibracion: snap.id_calibracion,
        siguePresente: Boolean(row),
        valoresSinCambios: Boolean(row) &&
          row.id_dispositivo_iot === snap.id_dispositivo_iot &&
          row.id_sensor === snap.id_sensor &&
          row.id_usuario === snap.id_usuario &&
          H.igualDecimal(row.valor_referencia, snap.valor_referencia) &&
          row.observaciones === snap.observaciones &&
          new Date(row.fecha_calibracion).getTime() === new Date(snap.fecha_calibracion).getTime()
      };
    });

  // Ningún intento inválido debe haber persistido.
  const invalidos = Object.entries(artifact.resultadosPorVariante)
    .filter(([, r]) => !r.valido && r.ejecutado)
    .map(([k, r]) => {
      const atribuibles = (historial.items || []).filter(
        x => r.observaciones === x.observaciones && r.fechaEnviada &&
             new Date(x.fecha_calibracion).getTime() === new Date(r.fechaEnviada).getTime()
      );
      return { variante: k, caso: r.caso, idsAtribuibles: atribuibles.map(x => x.id_calibracion), persistio: atribuibles.length > 0 };
    });

  const idsInicialesDelRun = artifact.resultadosPorVariante['142']?.historialPre?.ids || [];
  const historicosPreexistentes = idsInicialesDelRun.map(id => {
    const row = (historial.items || []).find(x => x.id_calibracion === id) || null;
    return { id_calibracion: id, siguePresente: Boolean(row) };
  });

  H.save(runId, 'verificacion-final-readonly.json', {
    grupo: H.GROUP_ID, runId, fecha: new Date().toISOString(),
    soloLectura: true, sqlEjecutado: 'ninguno',
    sensor: (sensores.items || []).find(x => H.sensorIdOf(x) === sensorId) || null,
    rangoTecnicoActual: rango,
    rangoSinCambiosDuranteElRun: Boolean(rango) &&
      H.igualDecimal(rango.valor_min, artifact.rango.min) && H.igualDecimal(rango.valor_max, artifact.rango.max),
    historialFinal: {
      total: historial.total,
      items: (historial.items || []).map(c => ({
        id_calibracion: c.id_calibracion, valor_referencia: c.valor_referencia,
        fecha_calibracion: c.fecha_calibracion, id_usuario: c.id_usuario, observaciones: c.observaciones
      }))
    },
    calibracionesValidasDelRun: validas,
    intentosInvalidos: invalidos,
    ningunIntentoInvalidoPersistio: invalidos.every(x => x.persistio === false),
    historicosPreexistentes,
    historicosAlterados: historicosPreexistentes.some(x => !x.siguePresente),
    idsFinales
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
  // En las copias de código de automation/ el vocabulario y los propios patrones del
  // escáner aparecen de forma legítima ("contrasena: password" es una referencia a una
  // variable; "set-cookie" es este mismo regex). Para código fuente solo cuentan VALORES
  // de secreto; el resto de evidencia se revisa con todos los patrones.
  const patronesSoloValores = patrones.filter(([, n]) =>
    n === 'JWT' || n === 'Authorization con token' || n === 'cadena de conexión'
  );
  const credenciales = [process.env.QA_PASSWORD, process.env.QA_ADMIN_PASSWORD].filter(Boolean);
  const revisados = [];
  const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).forEach(e => {
    const p = path.join(d, e.name);
    if (e.isDirectory()) return walk(p);
    if (!/\.(html|json|md|txt|cjs)$/i.test(e.name)) return;
    const rel = path.relative(evid, p).split(path.sep).join('/');
    const esCodigoFuente = rel.startsWith('automation/') && /\.cjs$/i.test(rel);
    const txt = fs.readFileSync(p, 'utf8');
    revisados.push({
      archivo: rel,
      bytes: txt.length,
      tipo: esCodigoFuente ? 'codigo-fuente' : 'evidencia',
      secretos: (esCodigoFuente ? patronesSoloValores : patrones).filter(([re]) => re.test(txt)).map(([, n]) => n),
      credencialesEnClaro: credenciales.filter(x => txt.includes(x)).length
    });
  });
  walk(evid);
  const sucios = revisados.filter(r => r.secretos.length || r.credencialesEnClaro);

  H.save(runId, 'seguridad-evidencias.json', {
    grupo: H.GROUP_ID, runId,
    limpio: sucios.length === 0,
    archivosConHallazgos: sucios,
    revisados,
    criterio: 'Se marcan solo valores de secreto: contraseñas, JWT, Authorization con token, cookies, tokens en pares clave-valor y cadenas de conexión. El correo del actor lo publica el propio caso y no es un secreto del requisito. En los archivos de automation/ (código fuente) solo se evalúan valores de secreto: el vocabulario del propio escáner y las referencias a variables no son fugas.',
    nota: 'Reporter htmlextra con omitHeaders, showEnvironmentData=false, showGlobalData=false y skipEnvironmentVars; sanitización posterior del HTML y de todo JSON de evidencia.'
  });

  console.log(`historial final del sensor ${sensorId}: total ${historial.total} | ids ${idsFinales.join(', ')}`);
  console.log(`validas del RUN intactas: ${validas.every(v => v.siguePresente && v.valoresSinCambios)}`);
  console.log(`ningun intento invalido persistio: ${invalidos.every(x => x.persistio === false)}`);
  console.log(`rango sin cambios: ${Boolean(rango) && H.igualDecimal(rango.valor_min, artifact.rango.min) && H.igualDecimal(rango.valor_max, artifact.rango.max)}`);
  console.log(`evidencia limpia de secretos: ${sucios.length === 0}`);
  if (sucios.length) process.exitCode = 3;
})().catch((e) => {
  console.error('VERIFICACION DE CIERRE NO COMPLETADA:', e.message);
  process.exitCode = 1;
});
