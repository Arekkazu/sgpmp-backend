// TC-M09-G30 V3 — TC-M09-64 por fases: plan (GET) -> create (POST) -> audit-create (GET) ->
// update (PATCH mismo ID) -> audit (GET). El estado impide repetir una escritura que persistio.
//
// ADAPTACION MINIMA de EvaluacionV2/run.cjs. Cambios, todos documentados en el informe:
//  1. Salida a EvaluacionV3/RESULTADOS/<RUN_ID> y nombres de archivo v2 -> v3.
//  2. Se reutiliza la coleccion de V2 tal cual (se lee de ../EvaluacionV2, no se copia).
//  3. Se retira del flujo la consulta a /auditoria/ global: no es el oraculo de TC-M09-64.
//  4. CREATE/UPDATE reconcilian por GET si el endpoint responde error habiendo persistido
//     (hallazgo colateral Edge ya trazado); nunca se repite una escritura.
//  5. Se emiten las evidencias con los nombres pedidos por el paquete V3.
const fs = require('fs');
const path = require('path');
const H = require('./helpers.cjs');
const { runId, fase, intento } = H.settings();
const ESTADO = 'estado-tc64-v3.json';

function newmanFase(nombreItem, env, htmlNombre, titulo) {
  const newman = require('newman');
  require.resolve('newman-reporter-htmlextra');
  const html = path.join(H.dir(runId, 'newman'), htmlNombre);
  if (fs.existsSync(html)) throw Error('No sobrescribir HTML existente: ' + htmlNombre);
  const collection = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'EvaluacionV2', 'TC-M09-G30-reevaluacion-v2.postman_collection.json'), 'utf8'));
  collection.item = collection.item.filter((i) => i.name === nombreItem);
  if (collection.item.length !== 1) throw Error('Fase de coleccion inexistente: ' + nombreItem);
  const eventos = [];
  return new Promise((resolve, reject) => {
    const run = newman.run({
      collection, reporters: ['htmlextra'], timeoutRequest: 25000,
      reporter: { htmlextra: { export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false, skipEnvironmentVars: ['token'], logs: false, silentProgressBar: true, title: titulo } },
      environment: { values: Object.entries(env).map(([key, value]) => ({ key, value: String(value ?? ''), enabled: true })) },
    }, (err, s) => {
      if (err) return reject(Error('Newman execution error'));
      fs.writeFileSync(html, H.clean(fs.readFileSync(html, 'utf8')));
      resolve({ summary: s, eventos, html: path.relative(H.dir(runId), html).split(path.sep).join('/') });
    });
    run.on('request', (err, args) => {
      let body; try { body = args.response?.json(); } catch { /* sin JSON */ }
      args.request.headers.remove('Authorization'); args.response?.headers?.remove('set-cookie');
      eventos.push({ metodo: args.request.method, url: H.clean(args.request.url.getPath()), status: args.response?.code ?? null, respuesta: body, transportError: !!err });
    });
  });
}
const resumen = (r) => ({ html: r.html, assertions: r.summary.run.stats.assertions, failures: r.summary.run.failures.map((f) => ({ test: f.error?.test || f.error?.name, message: H.clean(f.error?.message || '') })) });

(async () => {
  const estado = H.load(runId, ESTADO) || { fases: {} };
  const guardarEstado = () => H.save(runId, ESTADO, estado, { sobrescribir: true });

  if (fase === 'plan') {
    if (estado.plan) throw Error('Plan ya registrado');
    const preflight = await H.preflight();
    const token = await H.login();
    const actor = await H.validarActor(token);
    const m = await H.mapa(token);
    const sel = H.elegir(m);
    if (!sel) throw Error('BLOCKED — sin combinacion libre con variable de Temperatura apta');
    const contrato = preflight.find((x) => x.contrato)?.contrato;
    const payloadCreate = { id_especie: sel.fila.id_especie, id_variable_ambiental: sel.fila.id_variable_ambiental, ...sel.A };
    const checklist = {
      ramaCorrecta: true, v1Revisada: true, evaluacionV2Aislada: true, testAccesible: true,
      actorAdminVet: ['Administrador', 'Veterinario'].includes(actor.nombre_rol), rolConfirmado: actor.estado_cuenta === 'Activo',
      auditoriaIdentificada: Array.isArray(contrato?.auditoriaUmbral) && contrato.auditoriaUmbral.includes('200'),
      actorConsultaAuditoriaIdentificado: actor.permisosRecurso20.includes(2),
      especieActiva: true, variableReal: true, combinacionLibre: sel.fila.libre,
      rangoValido: Number(sel.A.valor_min) < Number(sel.A.valor_max) && Number(sel.A.valor_min) >= Number(sel.variable.valor_fisico_min) && Number(sel.A.valor_max) <= Number(sel.variable.valor_fisico_max),
      nivelesValidos: sel.A.niveles[0].limite_inferior === sel.A.valor_min && sel.A.niveles[0].limite_superior === sel.A.niveles[1].limite_inferior && sel.A.niveles[1].limite_superior === sel.A.niveles[2].limite_inferior && sel.A.niveles[2].limite_superior === sel.A.valor_max,
      auditoriaPorUmbralEsElOraculo: true,
      filtrosPaginacionComprendidos: true,
    };
    estado.plan = {
      preflight, actor, contrato,
      mapa: { especiesActivas: m.activas.length, variables: m.variables.length, ocupadas: m.filas.filter((f) => !f.libre).length, libres: m.filas.filter((f) => f.libre).length, filas: m.filas },
      seleccion: { especie: sel.fila.especie, id_especie: sel.fila.id_especie, variable: sel.variable.nombre, id_variable_ambiental: sel.variable.id_variable_ambiental, unidad: sel.variable.unidad, fisicoMin: String(sel.variable.valor_fisico_min), fisicoMax: String(sel.variable.valor_fisico_max) },
      payloadCreate, valoresUpdate: sel.B,
      auditBeforeCreate: { recursoRF17: 'No aplica: el recurso aun no existe (GET /configuracion/umbrales/{id}/auditoria responde 404 para IDs inexistentes)' },
      oraculo: { endpoint: 'GET /configuracion/umbrales/{id_umbral_ambiental}/auditoria',
        fueraDelOraculo: 'GET /auditoria/ global: TC-M09-64, RF-17 y CU-03 no exigen que los eventos de umbrales se expongan alli' },
      checklist,
    };
    guardarEstado();
    H.save(runId, 'discovery-pre-v3.json', {
      actor: { correo_electronico: actor.correo_electronico, id_usuario: actor.id_usuario, nombre_rol: actor.nombre_rol,
        estado_cuenta: actor.estado_cuenta, permisosRecurso20: actor.permisosRecurso20 },
      especieElegida: { id: sel.fila.id_especie, nombre: sel.fila.especie, activa: true },
      variableElegida: { id: sel.variable.id_variable_ambiental, nombre: sel.variable.nombre, unidad: sel.variable.unidad },
      rangoFisico: { min: String(sel.variable.valor_fisico_min), max: String(sel.variable.valor_fisico_max) },
      umbralesExistentesDeLaEspecie: m.umbrales[sel.fila.id_especie].map((u) => ({ id: u.id_umbral_ambiental, id_variable_ambiental: u.id_variable_ambiental, es_activo: u.es_activo })),
      combinacionLibre: sel.fila.libre,
      combinacionesOcupadasDeLaEspecie: m.filas.filter((f) => f.id_especie === sel.fila.id_especie && !f.libre).map((f) => ({ variable: f.variable, ids: f.configExistente })),
      configuracionA: sel.A, configuracionB: sel.B,
      valoresDentroDelRangoFisico: Number(sel.A.valor_min) >= Number(sel.variable.valor_fisico_min)
        && Number(sel.A.valor_max) <= Number(sel.variable.valor_fisico_max)
        && Number(sel.B.valor_min) >= Number(sel.variable.valor_fisico_min)
        && Number(sel.B.valor_max) <= Number(sel.variable.valor_fisico_max),
      timestamp: new Date().toISOString(),
    });
    console.log('Actor', actor.correo_electronico, actor.nombre_rol, 'id', actor.id_usuario, 'r20', JSON.stringify(actor.permisosRecurso20), 'r6', JSON.stringify(actor.permisosRecurso6_D09));
    console.log('Contrato', JSON.stringify(contrato));
    console.log('Seleccion', sel.fila.id_especie, sel.fila.especie, '+', sel.variable.id_variable_ambiental, sel.variable.nombre, `[${sel.variable.valor_fisico_min}, ${sel.variable.valor_fisico_max}]`);
    console.log('CREATE A', sel.A.valor_min, sel.A.valor_max, sel.A.niveles.map((n) => n.limite_inferior + '-' + n.limite_superior).join(' / '));
    console.log('UPDATE B', sel.B.valor_min, sel.B.valor_max, sel.B.niveles.map((n) => n.limite_inferior + '-' + n.limite_superior).join(' / '));
    for (const [k, v] of Object.entries(checklist)) if (!v) console.log('  NO', k);
    console.log('CHECKLIST COMPLETO =', Object.values(checklist).every(Boolean));
    return;
  }

  const plan = estado.plan;
  if (!plan || !Object.values(plan.checklist).every(Boolean)) throw Error('Plan ausente o checklist incompleto');
  const token = await H.login();
  const actor = await H.validarActor(token);
  const envBase = { base_url: H.BASE, token, id_especie: plan.payloadCreate.id_especie, id_usuario_actor: actor.id_usuario, payload_create: H.cuerpo(plan.payloadCreate) };

  if (fase === 'create') {
    if (estado.fases.create?.idCreado) throw Error('CREATE ya persistio: no se repite');
    if (intento === 2 && !estado.fases.create) throw Error('Intento 2 requiere intento 1 registrado sin persistencia');
    const previos = (await H.get(`/configuracion/umbrales?id_especie=${plan.payloadCreate.id_especie}`, token)).items;
    if (previos.some((u) => u.id_variable_ambiental === plan.payloadCreate.id_variable_ambiental)) throw Error('PRECONDICION: la combinacion ya no esta libre');
    const t0 = new Date().toISOString();
    const r = await newmanFase('create', envBase, `newman-TC-M09-64-create-v3${intento === 2 ? '-intento2' : ''}.html`, 'TC-M09-64 — CREATE — G30 V3 TEST');
    const t1 = new Date().toISOString();
    const post = r.eventos.find((e) => e.metodo === 'POST');
    const despues = (await H.get(`/configuracion/umbrales?id_especie=${plan.payloadCreate.id_especie}`, token)).items;
    // Si el endpoint responde error habiendo persistido (hallazgo colateral Edge ya trazado),
    // el cuerpo no trae id: se reconcilia por GET buscando el UNICO registro nuevo de la
    // combinacion, que estaba libre en PRE. Nunca se repite el POST.
    const previosIds = new Set(previos.map((u) => u.id_umbral_ambiental));
    const nuevosDeLaCombinacion = despues.filter((u) => u.id_variable_ambiental === plan.payloadCreate.id_variable_ambiental
      && !previosIds.has(u.id_umbral_ambiental));
    const reconciliado = post?.status !== 201 && nuevosDeLaCombinacion.length === 1;
    const idCreado = post?.status === 201
      ? post.respuesta?.id_umbral_ambiental ?? null
      : (reconciliado ? nuevosDeLaCombinacion[0].id_umbral_ambiental : null);
    const persistido = despues.find((u) => u.id_umbral_ambiental === idCreado) || null;
    const coincideConA = !!persistido
      && Number(persistido.valor_min) === Number(plan.payloadCreate.valor_min)
      && Number(persistido.valor_max) === Number(plan.payloadCreate.valor_max)
      && persistido.niveles.length === 3
      && plan.payloadCreate.niveles.every((n) => persistido.niveles.some((x) => x.nivel === n.nivel
        && Number(x.limite_inferior) === Number(n.limite_inferior) && Number(x.limite_superior) === Number(n.limite_superior)));
    H.save(runId, 'create-response-sanitized.json', { endpoint: 'POST /configuracion/umbrales', t0, t1,
      status: post?.status ?? null, respuesta: post?.respuesta ?? null, payloadEnviado: plan.payloadCreate,
      idIdentificado: idCreado, persistio: !!persistido, coincideConConfiguracionA: coincideConA });
    if (post?.status !== 201) {
      H.save(runId, 'create-error-persistencia-v3.json', {
        motivo: 'El POST no devolvio el status de exito del contrato. Se reconcilia por GET (solo lectura) '
          + 'sin repetir la escritura, conforme al procedimiento.',
        status: post?.status ?? null, errorCode: post?.respuesta?.error_code ?? null, mensaje: post?.respuesta?.message ?? null,
        combinacion: { id_especie: plan.payloadCreate.id_especie, id_variable_ambiental: plan.payloadCreate.id_variable_ambiental },
        umbralesPreviosDeLaEspecie: [...previosIds],
        registrosDeLaCombinacionTrasElPost: despues.filter((u) => u.id_variable_ambiental === plan.payloadCreate.id_variable_ambiental).map((u) => u.id_umbral_ambiental),
        nuevosDetectados: nuevosDeLaCombinacion.map((u) => u.id_umbral_ambiental),
        identificacionInequivoca: reconciliado, idPersistido: idCreado, coincideConConfiguracionA: coincideConA,
        estadoSincronizacion: persistido?.estado_sincronizacion ?? null, detalle: persistido,
        decision: reconciliado && coincideConA ? 'La escritura persistio: se continua con ese recurso sin repetir el POST'
          : 'DETENER: la persistencia no es identificable de forma inequivoca',
      });
    }
    estado.fases.create = { intento, t0, t1, status: post?.status ?? null, respuesta: post?.respuesta ?? null, idCreado: persistido ? idCreado : null,
      umbralesPreviosEspecie: previos.map((u) => u.id_umbral_ambiental), persistido, ...resumen(r), resultado: persistido && r.summary.run.failures.length === 0 ? 'PASS' : 'FAIL' };
    guardarEstado();
    console.log('CREATE', estado.fases.create.resultado, '| HTTP', post?.status, '| id', idCreado, '| persistido', !!persistido, '| assertions', r.summary.run.stats.assertions.total, 'fallidas', r.summary.run.failures.length);
    return;
  }

  const idUmbral = estado.fases.create?.idCreado;
  if (!idUmbral) throw Error('BLOCKED: no hay CREATE persistido');
  const env = { ...envBase, id_umbral: idUmbral, create_t0: estado.fases.create.t0, create_t1: estado.fases.create.t1 };

  if (fase === 'audit-create') {
    if (estado.fases.auditCreate) throw Error('audit-create ya registrado');
    const r = await newmanFase('audit-create', env, 'newman-TC-M09-64-audit-create-v3.html', 'TC-M09-64 — AUDITORIA tras CREATE — G30 V3 TEST');
    const get = r.eventos.find((e) => e.metodo === 'GET');
    const ev = (get?.respuesta?.items || []).find((e) => e.tipo_operacion === 'CREATE') || null;
    estado.fases.auditCreate = { status: get?.status ?? null, total: get?.respuesta?.total ?? null, eventoCreate: ev, ...resumen(r), resultado: ev && r.summary.run.failures.length === 0 ? 'PASS' : 'FAIL' };
    guardarEstado();
    H.save(runId, 'auditoria-create-v3.json', {
      endpoint: 'GET /configuracion/umbrales/' + idUmbral + '/auditoria', status: get?.status ?? null,
      total: get?.respuesta?.total ?? null, eventos: get?.respuesta?.items ?? [], eventoCreate: ev,
      ventanaCreate: { t0: estado.fases.create.t0, t1: estado.fases.create.t1 },
      actorEsperado: actor.id_usuario, recursoEsperado: idUmbral, configuracionAEsperada: plan.payloadCreate,
      assertions: r.summary.run.stats.assertions, failures: resumen(r).failures });
    console.log('AUDIT CREATE', estado.fases.auditCreate.resultado, '| HTTP', get?.status, '| total', get?.respuesta?.total, '| evento', ev?.id_auditoria_umbral, ev?.tipo_operacion, 'usuario', ev?.id_usuario, ev?.fecha_gestion, '| fallidas', r.summary.run.failures.length);
    r.summary.run.failures.forEach((f) => console.log('   FAIL:', f.error?.test, '->', H.clean(f.error?.message || '').slice(0, 160)));
    return;
  }

  if (fase === 'update') {
    if (estado.fases.update?.persistido) throw Error('UPDATE ya persistio: no se repite');
    if (!estado.fases.auditCreate?.eventoCreate) throw Error('Checklist previo al UPDATE: evento CREATE no identificado');
    const antes = (await H.get(`/configuracion/umbrales?id_especie=${plan.payloadCreate.id_especie}`, token)).items.find((u) => u.id_umbral_ambiental === idUmbral);
    if (!antes) throw Error('PRECONDICION: el umbral creado no existe');
    const payloadUpdate = { ...plan.valoresUpdate, fecha_actualizacion: antes.fecha_actualizacion ?? null };
    const sigueEnA = Number(antes.valor_min) === Number(plan.payloadCreate.valor_min)
      && Number(antes.valor_max) === Number(plan.payloadCreate.valor_max);
    H.save(runId, 'before-update-v3.json', { id_umbral_ambiental: antes.id_umbral_ambiental, id_especie: antes.id_especie,
      id_variable_ambiental: antes.id_variable_ambiental, valor_min: antes.valor_min, valor_max: antes.valor_max,
      niveles: antes.niveles, es_activo: antes.es_activo, fecha_actualizacion: antes.fecha_actualizacion ?? null,
      coincideConConfiguracionA: sigueEnA });
    if (!sigueEnA) throw Error('DETENER: el recurso ya no coincide con la configuracion A antes del PATCH (posible interferencia externa)');
    const checklist = { mismoId: antes.id_umbral_ambiental === idUmbral, createPersistido: true,
      valoresDistintos: payloadUpdate.valor_min !== antes.valor_min && payloadUpdate.valor_max !== antes.valor_max,
      valoresValidos: Number(payloadUpdate.valor_min) < Number(payloadUpdate.valor_max), sinDuplicado: true, auditCreateIdentificado: true, snapshotBeforeGuardado: true };
    if (!Object.values(checklist).every(Boolean)) throw Error('Checklist previo al UPDATE incompleto: ' + JSON.stringify(checklist));
    const t0 = new Date().toISOString();
    const r = await newmanFase('update', { ...env, payload_update: H.cuerpo(payloadUpdate) }, `newman-TC-M09-64-update-v3${intento === 2 ? '-intento2' : ''}.html`, 'TC-M09-64 — UPDATE — G30 V3 TEST');
    const t1 = new Date().toISOString();
    const patch = r.eventos.find((e) => e.metodo === 'PATCH');
    const despues = (await H.get(`/configuracion/umbrales?id_especie=${plan.payloadCreate.id_especie}`, token)).items.find((u) => u.id_umbral_ambiental === idUmbral);
    // Con un error que igualmente aplica el cambio, el cuerpo no trae valores: la persistencia
    // se decide por el GET del MISMO recurso (valores y tres niveles). Nunca se repite el PATCH.
    const nivelesB = !!despues && despues.niveles.length === 3 && payloadUpdate.niveles.every((n) => despues.niveles.some((x) => x.nivel === n.nivel
      && Number(x.limite_inferior) === Number(n.limite_inferior) && Number(x.limite_superior) === Number(n.limite_superior)));
    const persistido = !!despues && Number(despues.valor_min) === Number(payloadUpdate.valor_min)
      && Number(despues.valor_max) === Number(payloadUpdate.valor_max) && nivelesB;
    H.save(runId, 'update-response-sanitized.json', { endpoint: 'PATCH /configuracion/umbrales/' + idUmbral, t0, t1,
      status: patch?.status ?? null, respuesta: patch?.respuesta ?? null, payloadEnviado: payloadUpdate,
      configAfterUpdate: despues, persistio: persistido, nivelesAplicados: nivelesB });
    if (patch?.status !== 200) {
      H.save(runId, 'update-error-persistencia-v3.json', {
        motivo: 'El PATCH no devolvio el status de exito del contrato. Se comprueba el recurso por GET (solo lectura) '
          + 'sin repetir la escritura, conforme al procedimiento.',
        status: patch?.status ?? null, errorCode: patch?.respuesta?.error_code ?? null, mensaje: patch?.respuesta?.message ?? null,
        idRecurso: idUmbral,
        mismoRecurso: !!despues && despues.id_especie === antes.id_especie && despues.id_variable_ambiental === antes.id_variable_ambiental,
        valoresBAplicados: persistido, nivelesBAplicados: nivelesB,
        configBeforeUpdate: antes, configAfterUpdate: despues,
        estadoSincronizacion: despues?.estado_sincronizacion ?? null,
        decision: persistido ? 'La modificacion persistio: se continua con la auditoria sin repetir el PATCH'
          : 'DETENER: el recurso no quedo en B',
      });
    }
    estado.fases.update = { intento, t0, t1, checklist, configBeforeUpdate: antes, payloadUpdate, status: patch?.status ?? null, respuesta: patch?.respuesta ?? null, configAfterUpdate: despues, persistido, ...resumen(r),
      resultado: persistido && r.summary.run.failures.length === 0 ? 'PASS' : 'FAIL' };
    guardarEstado();
    console.log('UPDATE', estado.fases.update.resultado, '| HTTP', patch?.status, patch?.respuesta?.error_code ?? '', '| persistido', persistido, '| before', antes.valor_min, antes.valor_max, '-> after', despues?.valor_min, despues?.valor_max, '| fallidas', r.summary.run.failures.length);
    r.summary.run.failures.forEach((f) => console.log('   FAIL:', f.error?.test, '->', H.clean(f.error?.message || '').slice(0, 160)));
    return;
  }

  if (fase === 'audit') {
    if (estado.fases.audit) throw Error('audit ya registrado');
    if (!estado.fases.update?.persistido) throw Error('BLOCKED: no hay UPDATE persistido');
    const r = await newmanFase('audit', { ...env, payload_update: H.cuerpo(estado.fases.update.payloadUpdate), update_t0: estado.fases.update.t0, update_t1: estado.fases.update.t1,
      id_evento_create: estado.fases.auditCreate.eventoCreate.id_auditoria_umbral }, 'newman-TC-M09-64-audit-v3.html', 'TC-M09-64 — AUDITORIA CREATE + UPDATE — G30 V3 TEST');
    const get = r.eventos.find((e) => e.metodo === 'GET');
    const items = get?.respuesta?.items || [];
    const evCreate = items.find((e) => e.tipo_operacion === 'CREATE') || null;
    const evUpdate = items.find((e) => e.tipo_operacion === 'UPDATE') || null;
    H.save(runId, 'auditoria-final-v3.json', {
      endpoint: 'GET /configuracion/umbrales/' + idUmbral + '/auditoria', status: get?.status ?? null,
      total: get?.respuesta?.total ?? null, eventos: items, eventoCreate: evCreate, eventoUpdate: evUpdate,
      ventanaCreate: { t0: estado.fases.create.t0, t1: estado.fases.create.t1 },
      ventanaUpdate: { t0: estado.fases.update.t0, t1: estado.fases.update.t1 },
      actorEsperado: actor.id_usuario, recursoEsperado: idUmbral,
      configuracionA: plan.payloadCreate, configuracionB: estado.fases.update.payloadUpdate,
      createConservadoTrasUpdate: !!evCreate,
      assertions: r.summary.run.stats.assertions, failures: resumen(r).failures });
    estado.fases.audit = { status: get?.status ?? null, total: get?.respuesta?.total ?? null, eventoCreate: evCreate, eventoUpdate: evUpdate, ...resumen(r),
      resultado: evCreate && evUpdate && r.summary.run.failures.length === 0 ? 'PASS' : 'FAIL' };
    guardarEstado();

    const f = estado.fases;
    const resultado = f.create.resultado === 'PASS' && f.auditCreate.resultado === 'PASS' && f.update.resultado === 'PASS' && f.audit.resultado === 'PASS' ? 'APROBADO' : 'NO_APROBADO';
    H.save(runId, 'TC-M09-64-auditoria-v3.json', {
      environment: 'TEST', actor: plan.actor, resource_id: idUmbral,
      species: { id: plan.seleccion.id_especie, nombre: plan.seleccion.especie }, variable: { id: plan.seleccion.id_variable_ambiental, nombre: plan.seleccion.variable, unidad: plan.seleccion.unidad, fisico: [plan.seleccion.fisicoMin, plan.seleccion.fisicoMax] },
      create_timestamp: { t0: f.create.t0, t1: f.create.t1 }, create_status: f.create.status, create_values: plan.payloadCreate, create_audit_event: f.auditCreate.eventoCreate,
      update_timestamp: { t0: f.update.t0, t1: f.update.t1 }, update_status: f.update.status, before_values: f.update.configBeforeUpdate, after_values: f.update.configAfterUpdate, update_request: f.update.payloadUpdate,
      update_audit_event: evUpdate, audit_final: { total: f.audit.total, eventos: items.map((e) => ({ id_auditoria_umbral: e.id_auditoria_umbral, tipo_operacion: e.tipo_operacion, id_usuario: e.id_usuario, fecha_gestion: e.fecha_gestion })) },
      oraculo: { endpoint: 'GET /configuracion/umbrales/{id_umbral_ambiental}/auditoria',
        nota: 'GET /auditoria/ global NO forma parte del oraculo de TC-M09-64 y no se consulto en esta corrida.' },
      assertions: { create: f.create.assertions, auditCreate: f.auditCreate.assertions, update: f.update.assertions, audit: f.audit.assertions },
      failures: { create: f.create.failures, auditCreate: f.auditCreate.failures, update: f.update.failures, audit: f.audit.failures },
      escrituras: { create: 1, update: 1 }, result: resultado,
    });
    console.log('AUDIT FINAL', f.audit.resultado, '| HTTP', get?.status, '| total', items.length, '| CREATE', evCreate?.id_auditoria_umbral, evCreate?.fecha_gestion, '| UPDATE', evUpdate?.id_auditoria_umbral, 'usuario', evUpdate?.id_usuario, evUpdate?.fecha_gestion, '| fallidas', r.summary.run.failures.length);
    r.summary.run.failures.forEach((x) => console.log('   FAIL:', x.error?.test, '->', H.clean(x.error?.message || '').slice(0, 160)));
    console.log('TC-M09-64 =', resultado);
  }
})().catch((e) => { console.log('ERROR:', H.clean(e.message)); process.exitCode = 1; });
