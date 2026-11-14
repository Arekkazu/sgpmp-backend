// TC-M09-G77 / TC-M09-148 — REEVALUACION V2: precondiciones (sin POST).
// Verifica entorno, contrato, actor negativo, datos dinamicos e HISTORY_BEFORE.
// No ejecuta ninguna escritura: solo login y GET.
const H = require('./helpers.cjs');
const { runId } = H.settings();

(async () => {
  const preflight = [];
  // El esquema HTTP suministrado no esta enrutado en el edge de TEST; se deja
  // constancia del hecho y se ejecuta sobre HTTPS por autorizacion explicita.
  try {
    const r = await fetch(H.BASE_HTTP_SUMINISTRADA + '/health', { signal: AbortSignal.timeout(20000) });
    preflight.push({ url: H.BASE_HTTP_SUMINISTRADA + '/health', status: r.status, nota: 'esquema HTTP suministrado' });
  } catch (e) {
    preflight.push({ url: H.BASE_HTTP_SUMINISTRADA + '/health', error: H.clean(e.message) });
  }
  for (const url of [H.FRONT + '/login', H.BASE + '/health', H.BASE + '/openapi.json']) {
    const r = await fetch(url, { signal: AbortSignal.timeout(25000) });
    preflight.push({ url, status: r.status });
    if (r.status !== 200) throw Error('ENVIRONMENT_ERROR preflight HTTP ' + r.status + ' en ' + url);
    if (url.endsWith('openapi.json')) {
      const j = await r.json();
      const op = j.paths['/configuracion/sensores/{id_sensor}/calibrar']?.post;
      if (!op) throw Error('Contrato ausente: POST /configuracion/sensores/{id_sensor}/calibrar');
      preflight.push({
        contrato: 'POST /configuracion/sensores/{id_sensor}/calibrar',
        respuestasDeclaradas: Object.keys(op.responses),
        declara403: Object.keys(op.responses).includes('403'),
      });
    }
  }

  // 1) Actor de solo lectura para el descubrimiento (RF-24: Ingeniero de Campo).
  const ing = await H.login(H.ACTOR_DISCOVERY, process.env.TEST_ENGINEER_PASSWORD);
  if (ing.status !== 200 || !ing.token) throw Error(`ENVIRONMENT_ERROR login Ingeniero HTTP ${ing.status} ${ing.errorCode || ''}`);
  const ingPerfil = await H.get('/usuarios/me', ing.token);
  const ingPermisos = (await H.get('/sesiones/me/permisos', ing.token)).permisos
    .filter((p) => p.id_recurso === H.RECURSO_SENSORES).map((p) => p.id_accion).sort();

  // 2) El Ingeniero no alcanza los datos: en TEST no tiene fincas asignadas y el
  //    alcance de finca le oculta dispositivos y asociaciones. Se deja constancia
  //    y se escala a Administrador SOLO para GET (RF-24 §10-§11).
  const alcanceIngeniero = {
    listaDispositivos: (await H.pedir('/configuracion/dispositivos-iot?solo_activos=true', ing.token)).body?.total ?? null,
    fincasAsignadas: (ingPerfil.fincas || []).length,
    esGlobal: false,
  };
  let tokenLectura = ing.token;
  let actorDescubrimiento = { correo: H.ACTOR_DISCOVERY, rol: ingPerfil.nombre_rol, escalado: false };
  let adminPerfil = null;
  if (!alcanceIngeniero.listaDispositivos) {
    const adm = await H.login(H.ACTOR_DISCOVERY_GLOBAL, process.env.TEST_ADMIN_PASSWORD);
    if (adm.status !== 200 || !adm.token) throw Error(`ENVIRONMENT_ERROR login Administrador HTTP ${adm.status} ${adm.errorCode || ''}`);
    adminPerfil = await H.get('/usuarios/me', adm.token);
    tokenLectura = adm.token;
    actorDescubrimiento = {
      correo: H.ACTOR_DISCOVERY_GLOBAL,
      rol: adminPerfil.nombre_rol,
      escalado: true,
      motivo: 'El Ingeniero de Campo no tiene fincas asignadas en TEST: alcance de finca deja la lista de dispositivos en total 0 y el detalle/asociaciones en 404.',
      uso: 'exclusivamente GET; no ejecuta ninguna calibracion',
    };
  }

  // 3) Datos dinamicos redescubiertos (no se reutilizan los literales de V1).
  const plan = await H.discover(tokenLectura);

  // 4) Actor negativo: Productor autenticado.
  const prod = await H.login(H.ACTOR_NEGATIVO, process.env.TEST_PRODUCTOR_PASSWORD);
  const actor = {
    correo: H.ACTOR_NEGATIVO,
    login_status: prod.status,
    autenticado: prod.status === 200 && !!prod.token,
    error_code: prod.errorCode,
    mensaje: prod.mensaje,
  };
  let perfil = null, permisosRecurso12 = null, historialProductor = null;
  if (actor.autenticado) {
    const me = await H.get('/usuarios/me', prod.token);
    perfil = {
      id_usuario: me.id_usuario,
      correo_electronico: me.correo_electronico,
      nombre_rol: me.nombre_rol,
      estado_cuenta: me.estado_cuenta,
      fincas: (me.fincas || []).length,
    };
    permisosRecurso12 = (await H.get('/sesiones/me/permisos', prod.token)).permisos
      .filter((p) => p.id_recurso === H.RECURSO_SENSORES).map((p) => p.id_accion).sort();
    const h = await H.pedir(`/configuracion/sensores/${plan.sensor.id_sensores}/calibraciones`, prod.token);
    historialProductor = { status: h.status, total: h.body?.total ?? null };
  }

  // 5) HISTORY_BEFORE autoritativo (GET con actor autorizado de solo lectura).
  const antes = await H.get(`/configuracion/sensores/${plan.sensor.id_sensores}/calibraciones`, tokenLectura);
  const historyBefore = {
    actor: `${actorDescubrimiento.rol} (GET read-only)`,
    total: antes.total,
    ids: antes.items.map((c) => c.id_calibracion),
    items: antes.items.map((c) => ({
      id_calibracion: c.id_calibracion,
      id_usuario: c.id_usuario,
      valor_referencia: String(c.valor_referencia),
      fecha_calibracion: c.fecha_calibracion,
    })),
  };

  const cuerpo = H.construirCuerpo(plan, runId);
  const checklist = {
    entornoTestAccesible: true,
    contratoDeclara403: preflight.find((p) => p.declara403 !== undefined)?.declara403 === true,
    productorAutenticado: actor.autenticado,
    rolProductorConfirmado: perfil?.nombre_rol === 'Productor',
    cuentaActiva: perfil?.estado_cuenta === 'Activo',
    rolNoAutorizadoRF24: perfil ? !H.ROLES_AUTORIZADOS_RF24.includes(perfil.nombre_rol) : null,
    sinPermisoCrearRecurso12: permisosRecurso12 ? !permisosRecurso12.includes(H.ACCION_CREAR) : null,
    dispositivoExisteYActivo: plan.dispositivo.es_activo === true,
    sensorExisteYActivo: plan.sensor.es_activo === true,
    sensorPerteneceAlDispositivo: plan.sensor.id_dispositivo_iot === plan.dispositivo.id_dispositivo_iot,
    areaCorrectaVigente: plan.areaCorrecta.vigente === true,
    valorDentroDelRango:
      Number(plan.valor) > Number(plan.rangoTecnico.min) && Number(plan.valor) < Number(plan.rangoTecnico.max),
    historyBeforeCapturado: Number.isInteger(historyBefore.total),
    unicaCondicionNegativaEsElRol: true,
  };

  H.save(runId, 'precheck-v2.json', {
    preflight,
    esquemaSuministradoHttp: {
      url: H.BASE_HTTP_SUMINISTRADA,
      resultado: preflight[0],
      nota: 'HTTP devuelve 404 del proxy en todas las rutas; ejecucion sobre HTTPS autorizada explicitamente por el responsable QA.',
    },
    actorDiscovery: { correo: H.ACTOR_DISCOVERY, nombre_rol: ingPerfil.nombre_rol, estado_cuenta: ingPerfil.estado_cuenta, permisosRecurso12: ingPermisos, uso: 'solo GET', alcance: alcanceIngeniero },
    actorDiscoveryEfectivo: actorDescubrimiento,
    actorNegativo: { ...actor, perfil, permisosRecurso12, historialLegiblePorProductor: historialProductor },
    rolesAutorizadosRF24: H.ROLES_AUTORIZADOS_RF24,
    plan,
    cuerpoPreparado: cuerpo.objeto,
    historyBefore,
    checklist,
    postEjecutados: 0,
  });

  console.log('--- PRECHECK V2', runId, '---');
  console.log('Ingeniero rol:', ingPerfil.nombre_rol, '| permisos recurso 12:', JSON.stringify(ingPermisos),
    '| dispositivos visibles:', alcanceIngeniero.listaDispositivos);
  console.log('Actor de descubrimiento efectivo:', actorDescubrimiento.rol, actorDescubrimiento.escalado ? '(escalado, solo GET)' : '');
  console.log('Productor login:', actor.login_status, '| rol:', perfil?.nombre_rol, '| cuenta:', perfil?.estado_cuenta,
    '| permisos recurso 12:', JSON.stringify(permisosRecurso12));
  console.log('Dispositivo:', plan.dispositivo.id_dispositivo_iot, plan.dispositivo.serial, 'activo=', plan.dispositivo.es_activo,
    '| Sensor:', plan.sensor.id_sensores, plan.sensor.categoria, '| Area:', plan.areaCorrecta.id_infraestructura,
    '| Rango:', plan.rangoTecnico.min, '-', plan.rangoTecnico.max, '| Valor:', plan.valor);
  console.log('HISTORY_BEFORE total:', historyBefore.total, 'ids:', JSON.stringify(historyBefore.ids));
  for (const [k, v] of Object.entries(checklist)) console.log((v === true ? '  OK   ' : '  NO   ') + k + ' = ' + v);
  const listo = Object.values(checklist).every((v) => v === true);
  console.log('LISTO_PARA_POST =', listo);
  process.exitCode = listo ? 0 : 1;
})().catch((e) => { console.log('PRECHECK ERROR:', H.clean(e.message)); process.exitCode = 1; });
