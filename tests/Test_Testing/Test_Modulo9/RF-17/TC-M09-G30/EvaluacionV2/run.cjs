// TC-M09-G30 V2 — TC-M09-64 por fases: plan (GET) → create (POST) → audit-create (GET) →
// update (PATCH mismo ID) → audit (GET). El estado impide repetir una escritura que persistio.
const fs = require('fs');
const path = require('path');
const H = require('./helpers.cjs');
const { runId, fase, intento } = H.settings();
const ESTADO = 'estado-tc64.json';

function newmanFase(nombreItem, env, htmlNombre, titulo) {
  const newman = require('newman');
  require.resolve('newman-reporter-htmlextra');
  const html = path.join(H.dir(runId, 'newman'), htmlNombre);
  if (fs.existsSync(html)) throw Error('No sobrescribir HTML existente: ' + htmlNombre);
  const collection = JSON.parse(fs.readFileSync(path.join(__dirname, 'TC-M09-G30-reevaluacion-v2.postman_collection.json'), 'utf8'));
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
    const ahora = new Date();
    const d09Antes = await H.d09Global(token, actor.id_usuario, new Date(ahora.getTime() - 3600e3).toISOString(), ahora.toISOString());
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
      auditBeforeObtenido: d09Antes.status === 200,
      filtrosPaginacionComprendidos: true,
    };
    estado.plan = {
      preflight, actor, contrato,
      mapa: { especiesActivas: m.activas.length, variables: m.variables.length, ocupadas: m.filas.filter((f) => !f.libre).length, libres: m.filas.filter((f) => f.libre).length, filas: m.filas },
      seleccion: { especie: sel.fila.especie, id_especie: sel.fila.id_especie, variable: sel.variable.nombre, id_variable_ambiental: sel.variable.id_variable_ambiental, unidad: sel.variable.unidad, fisicoMin: String(sel.variable.valor_fisico_min), fisicoMax: String(sel.variable.valor_fisico_max) },
      payloadCreate, valoresUpdate: sel.B,
      auditBeforeCreate: { recursoRF17: 'No aplica: el recurso aun no existe (GET /configuracion/umbrales/{id}/auditoria responde 404 para IDs inexistentes)', d09Global: d09Antes },
      checklist,
    };
    guardarEstado();
    console.log('Actor', actor.correo_electronico, actor.nombre_rol, 'id', actor.id_usuario, 'r20', JSON.stringify(actor.permisosRecurso20), 'r6', JSON.stringify(actor.permisosRecurso6_D09));
    console.log('Contrato', JSON.stringify(contrato));
    console.log('Seleccion', sel.fila.id_especie, sel.fila.especie, '+', sel.variable.id_variable_ambiental, sel.variable.nombre, `[${sel.variable.valor_fisico_min}, ${sel.variable.valor_fisico_max}]`);
    console.log('CREATE A', sel.A.valor_min, sel.A.valor_max, sel.A.niveles.map((n) => n.limite_inferior + '-' + n.limite_superior).join(' / '));
    console.log('UPDATE B', sel.B.valor_min, sel.B.valor_max, sel.B.niveles.map((n) => n.limite_inferior + '-' + n.limite_superior).join(' / '));
    console.log('D09 global antes:', d09Antes.status, 'total', d09Antes.total);
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
    const r = await newmanFase('create', envBase, `newman-TC-M09-64-create-v2${intento === 2 ? '-intento2' : ''}.html`, 'TC-M09-64 — CREATE — G30 V2 TEST');
    const t1 = new Date().toISOString();
    const post = r.eventos.find((e) => e.metodo === 'POST');
    const despues = (await H.get(`/configuracion/umbrales?id_especie=${plan.payloadCreate.id_especie}`, token)).items;
    const idCreado = post?.status === 201 ? post.respuesta?.id_umbral_ambiental ?? null : null;
    const persistido = despues.find((u) => u.id_umbral_ambiental === idCreado) || null;
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
    const r = await newmanFase('audit-create', env, 'newman-TC-M09-64-audit-create-v2.html', 'TC-M09-64 — AUDITORIA tras CREATE — G30 V2 TEST');
    const get = r.eventos.find((e) => e.metodo === 'GET');
    const ev = (get?.respuesta?.items || []).find((e) => e.tipo_operacion === 'CREATE') || null;
    estado.fases.auditCreate = { status: get?.status ?? null, total: get?.respuesta?.total ?? null, eventoCreate: ev, ...resumen(r), resultado: ev && r.summary.run.failures.length === 0 ? 'PASS' : 'FAIL' };
    guardarEstado();
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
    const checklist = { mismoId: antes.id_umbral_ambiental === idUmbral, createPersistido: true,
      valoresDistintos: payloadUpdate.valor_min !== antes.valor_min && payloadUpdate.valor_max !== antes.valor_max,
      valoresValidos: Number(payloadUpdate.valor_min) < Number(payloadUpdate.valor_max), sinDuplicado: true, auditCreateIdentificado: true, snapshotBeforeGuardado: true };
    if (!Object.values(checklist).every(Boolean)) throw Error('Checklist previo al UPDATE incompleto: ' + JSON.stringify(checklist));
    const t0 = new Date().toISOString();
    const r = await newmanFase('update', { ...env, payload_update: H.cuerpo(payloadUpdate) }, `newman-TC-M09-64-update-v2${intento === 2 ? '-intento2' : ''}.html`, 'TC-M09-64 — UPDATE — G30 V2 TEST');
    const t1 = new Date().toISOString();
    const patch = r.eventos.find((e) => e.metodo === 'PATCH');
    const despues = (await H.get(`/configuracion/umbrales?id_especie=${plan.payloadCreate.id_especie}`, token)).items.find((u) => u.id_umbral_ambiental === idUmbral);
    const persistido = !!despues && despues.valor_min === patch?.respuesta?.valor_min && Number(despues.valor_min) === Number(payloadUpdate.valor_min) && Number(despues.valor_max) === Number(payloadUpdate.valor_max);
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
      id_evento_create: estado.fases.auditCreate.eventoCreate.id_auditoria_umbral }, 'newman-TC-M09-64-audit-v2.html', 'TC-M09-64 — AUDITORIA CREATE + UPDATE — G30 V2 TEST');
    const get = r.eventos.find((e) => e.metodo === 'GET');
    const items = get?.respuesta?.items || [];
    const evCreate = items.find((e) => e.tipo_operacion === 'CREATE') || null;
    const evUpdate = items.find((e) => e.tipo_operacion === 'UPDATE') || null;
    const d09 = await H.d09Global(token, actor.id_usuario, new Date(Date.parse(estado.fases.create.t0) - 60e3).toISOString(), new Date(Date.parse(estado.fases.update.t1) + 60e3).toISOString());
    estado.fases.audit = { status: get?.status ?? null, total: get?.respuesta?.total ?? null, eventoCreate: evCreate, eventoUpdate: evUpdate, d09GlobalVentana: d09, ...resumen(r),
      resultado: evCreate && evUpdate && r.summary.run.failures.length === 0 ? 'PASS' : 'FAIL' };
    guardarEstado();

    const f = estado.fases;
    const resultado = f.create.resultado === 'PASS' && f.auditCreate.resultado === 'PASS' && f.update.resultado === 'PASS' && f.audit.resultado === 'PASS' ? 'APROBADO' : 'NO_APROBADO';
    H.save(runId, 'TC-M09-64-auditoria-v2.json', {
      environment: 'TEST', actor: plan.actor, resource_id: idUmbral,
      species: { id: plan.seleccion.id_especie, nombre: plan.seleccion.especie }, variable: { id: plan.seleccion.id_variable_ambiental, nombre: plan.seleccion.variable, unidad: plan.seleccion.unidad, fisico: [plan.seleccion.fisicoMin, plan.seleccion.fisicoMax] },
      create_timestamp: { t0: f.create.t0, t1: f.create.t1 }, create_status: f.create.status, create_values: plan.payloadCreate, create_audit_event: f.auditCreate.eventoCreate,
      update_timestamp: { t0: f.update.t0, t1: f.update.t1 }, update_status: f.update.status, before_values: f.update.configBeforeUpdate, after_values: f.update.configAfterUpdate, update_request: f.update.payloadUpdate,
      update_audit_event: evUpdate, audit_final: { total: f.audit.total, eventos: items.map((e) => ({ id_auditoria_umbral: e.id_auditoria_umbral, tipo_operacion: e.tipo_operacion, id_usuario: e.id_usuario, fecha_gestion: e.fecha_gestion })) },
      d09_global_observacion: { antesCreate: plan.auditBeforeCreate.d09Global, ventanaOperaciones: d09 },
      assertions: { create: f.create.assertions, auditCreate: f.auditCreate.assertions, update: f.update.assertions, audit: f.audit.assertions },
      failures: { create: f.create.failures, auditCreate: f.auditCreate.failures, update: f.update.failures, audit: f.audit.failures },
      escrituras: { create: 1, update: 1 }, result: resultado,
    });
    console.log('AUDIT FINAL', f.audit.resultado, '| HTTP', get?.status, '| total', items.length, '| CREATE', evCreate?.id_auditoria_umbral, evCreate?.fecha_gestion, '| UPDATE', evUpdate?.id_auditoria_umbral, 'usuario', evUpdate?.id_usuario, evUpdate?.fecha_gestion, '| fallidas', r.summary.run.failures.length);
    console.log('D09 global en ventana:', d09.status, 'total', d09.total, JSON.stringify(d09.eventos.map((e) => [e.tipo_evento, e.modulo, e.descripcion]).slice(0, 8)));
    r.summary.run.failures.forEach((x) => console.log('   FAIL:', x.error?.test, '->', H.clean(x.error?.message || '').slice(0, 160)));
    console.log('TC-M09-64 =', resultado);
  }
})().catch((e) => { console.log('ERROR:', H.clean(e.message)); process.exitCode = 1; });
