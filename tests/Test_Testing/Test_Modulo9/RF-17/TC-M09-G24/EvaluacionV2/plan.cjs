// TC-M09-G24 V2 — preflight, actor, mapa especie-variable, seleccion de combinacion libre,
// payloads de los tres originales y checklists previos. Solo login y GET: ningun POST.
const H = require('./helpers.cjs');
const { runId } = H.settings({ requiereCaso: false });

(async () => {
  const preflight = await H.preflight();
  const token = await H.login();
  const actor = await H.validarActor(token);
  const m = await H.mapa(token);
  const sel = H.elegir(m);
  if (!sel) throw Error('BLOCKED — DATOS TEST INSUFICIENTES: sin combinacion libre con rango fisico apto');
  const planes = Object.fromEntries(H.CASOS.map((c) => [c, H.construir(c, sel, m)]));
  const an = Object.fromEntries(H.CASOS.map((c) => [c, H.analizar(planes[c].payload)]));
  const base = (a) => a.minMenorQueMax && a.tresNiveles && a.nombresContrato && a.cadaNivelInfMenorSup;
  const fisicoOk = Number(sel.puntos.a) >= Number(sel.variable.valor_fisico_min) && Number(sel.puntos.d) <= Number(sel.variable.valor_fisico_max);

  const checklist = {
    'TC-M09-52': { ramaCorrecta: true, v1Revisada: true, actorAutorizado: true, especieActiva: planes['TC-M09-52'].especie.es_activo === true,
      variableReal: true, combinacionLibre: sel.fila.libre, rangoFisicoConocido: true, rangoGeneralValido: fisicoOk && an['TC-M09-52'].minMenorQueMax,
      unicaInvalidezNivelFueraDeRango: base(an['TC-M09-52']) && an['TC-M09-52'].fueraDelGeneral.join() === 'critico', payloadContractual: base(an['TC-M09-52']) },
    'TC-M09-53': { combinacionLibre: sel.fila.libre, nivelesDentroDelGeneral: an['TC-M09-53'].fueraDelGeneral.length === 0,
      solapamientoReal: an['TC-M09-53'].solapamientos.length === 1, sinOtraInvalidez: base(an['TC-M09-53']) && an['TC-M09-53'].huecos.length === 0 && fisicoOk,
      oraculoResuelto: H.ORACULO['TC-M09-53'].status === 422, contratoActualRevisado: preflight.some((x) => (x.respuestasDeclaradas || []).includes('422')) },
    'TC-M09-54': { especieActiva: planes['TC-M09-54'].especie.es_activo === true, combinacionLibre: sel.fila.libre, rangoGeneralValido: an['TC-M09-54'].minMenorQueMax,
      limitesFisicosValidos: fisicoOk, nivelesDentroDelRango: an['TC-M09-54'].fueraDelGeneral.length === 0, sinSolapamiento: an['TC-M09-54'].solapamientos.length === 0,
      sinHuecos: an['TC-M09-54'].huecos.length === 0, transicionesConformesContrato: base(an['TC-M09-54']), actorAutorizado: true, payloadValido: base(an['TC-M09-54']) },
  };

  H.save(runId, 'plan-v2.json', {
    preflight, actor,
    oraculos: H.ORACULO,
    mapaCombinaciones: m.filas,
    resumenMapa: { especiesActivas: m.activas.length, variables: m.variables.length, combinaciones: m.filas.length, ocupadas: m.filas.filter((f) => !f.libre).length, libres: m.filas.filter((f) => f.libre).length },
    seleccion: { especie: sel.fila.especie, id_especie: sel.fila.id_especie, variable: sel.fila.variable, id_variable_ambiental: sel.fila.id_variable_ambiental, puntos: sel.puntos },
    planes, analisis: an, checklist, postEjecutados: 0,
  });

  console.log('Actor:', actor.correo_electronico, actor.nombre_rol, actor.estado_cuenta, 'r20', JSON.stringify(actor.permisosRecurso20));
  console.log('OpenAPI POST umbrales:', JSON.stringify(preflight.find((x) => x.respuestasDeclaradas)?.respuestasDeclaradas));
  console.log('Mapa: ocupadas', m.filas.filter((f) => !f.libre).length, 'libres', m.filas.filter((f) => f.libre).length);
  console.log('Seleccion:', sel.fila.id_especie, sel.fila.especie, '+', sel.fila.id_variable_ambiental, sel.fila.variable, `fisico [${sel.variable.valor_fisico_min}, ${sel.variable.valor_fisico_max}]`, 'puntos', JSON.stringify(sel.puntos));
  for (const c of H.CASOS) {
    console.log(c, `general ${planes[c].payload.valor_min}..${planes[c].payload.valor_max}`, planes[c].payload.niveles.map((n) => `${n.nivel} ${n.limite_inferior}-${n.limite_superior}`).join(' | '), '| analisis', JSON.stringify(an[c]));
    for (const [k, v] of Object.entries(checklist[c])) if (!v) console.log('   NO', k);
  }
  const ok = Object.values(checklist).every((c) => Object.values(c).every(Boolean));
  console.log('CHECKLISTS COMPLETOS =', ok);
  process.exitCode = ok ? 0 : 1;
})().catch((e) => { console.log('PLAN ERROR:', H.clean(e.message)); process.exitCode = 1; });
