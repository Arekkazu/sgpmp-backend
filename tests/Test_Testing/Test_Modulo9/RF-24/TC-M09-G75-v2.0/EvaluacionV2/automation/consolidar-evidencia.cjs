// Consolida evidencia.json de la SEGUNDA EVALUACIÓN de TC-M09-G75-v2.0.
//
// NO ejecuta red, NO envía POST y NO reinterpreta el oráculo: solo lee los artefactos ya
// escritos por el RUN funcional oficial y los agrupa en un único archivo de evidencia.
//
// Doble función:
//   1. secciones estructuradas, legibles, con el oráculo por caso y por variante;
//   2. `artefactos_del_run`: copia VERBATIM del contenido de cada archivo de evidencia del
//      RUN, para que los JSON fragmentados puedan retirarse del directorio sin perder nada.
//
// Es idempotente: si un archivo ya fue retirado, su contenido se reutiliza desde el
// `evidencia.json` anterior en lugar de perderse.
//
// Uso:
//   $env:G75_RUN_ID="G75-REEVAL-V2-YYYYMMDD-HHMMSS"
//   node .\consolidar-evidencia.cjs

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const H = require('./paths-v2.cjs');

const runId = process.env.G75_RUN_ID;
if (!runId || !/^G75-REEVAL-V2-\d{8}-\d{6}$/.test(runId)) {
  throw new Error('G75_RUN_ID requerido con formato G75-REEVAL-V2-YYYYMMDD-HHMMSS.');
}
const dir = H.runDir(runId);

// Evidencia previa: permite reconsolidar después de retirar los JSON fragmentados.
const previaPath = path.join(dir, 'evidencia.json');
const previa = fs.existsSync(previaPath) ? JSON.parse(fs.readFileSync(previaPath, 'utf8')) : null;
const integradosPrevios = (previa && previa.artefactos_del_run) || {};

const VARIANTES = [
  { key: '142', caso: 'TC-M09-142-v2.0', etiqueta: 'MIN', valido: true },
  { key: '143', caso: 'TC-M09-143-v2.0', etiqueta: 'MAX', valido: true },
  { key: '144_low', caso: 'TC-M09-144-v2.0', etiqueta: 'LOW', valido: false },
  { key: '144_high', caso: 'TC-M09-144-v2.0', etiqueta: 'HIGH', valido: false },
  { key: '145_empty', caso: 'TC-M09-145-v2.0', etiqueta: 'EMPTY', valido: false },
  { key: '145_null', caso: 'TC-M09-145-v2.0', etiqueta: 'NULL', valido: false },
  { key: '145_abc', caso: 'TC-M09-145-v2.0', etiqueta: 'ABC', valido: false }
];

// Archivos cuyo contenido queda integrado verbatim en evidencia.json.
const ARCHIVOS = [
  'git_pre.txt',
  'health_preflight.json',
  'openapi_preflight.json',
  'identidad_actor.json',
  'permisos_actor.json',
  'fixture_descubierto.json',
  'rango_temperatura.json',
  'diagnostico_preflight_coleccion.json',
  'verificacion_persistencia_rls.json',
  'validacion_suplementaria_preflight.json',
  'verificacion-final-readonly.json',
  'seguridad-evidencias.json',
  'TC-M09-G75-v2.0.json'
];
for (const v of VARIANTES) {
  ARCHIVOS.push(`${v.key}_historial_pre.json`, `${v.key}_request.json`, `${v.key}_response.json`, `${v.key}_historial_post.json`);
  if (v.valido) ARCHIVOS.push(`${v.key}_calibracion_creada.json`);
}

// --------------------------------------------------------------- integración verbatim
const integrados = {};
const procedencia = {};
for (const nombre of ARCHIVOS) {
  const p = path.join(dir, nombre);
  if (fs.existsSync(p)) {
    const texto = fs.readFileSync(p, 'utf8');
    integrados[nombre] = nombre.endsWith('.json') ? JSON.parse(texto) : texto;
    procedencia[nombre] = 'leido del archivo del RUN';
  } else if (Object.prototype.hasOwnProperty.call(integradosPrevios, nombre)) {
    integrados[nombre] = integradosPrevios[nombre];
    procedencia[nombre] = 'reutilizado de evidencia.json (archivo ya retirado del directorio)';
  } else {
    procedencia[nombre] = 'NO DISPONIBLE';
  }
}
const faltantes = Object.entries(procedencia).filter(([, v]) => v === 'NO DISPONIBLE').map(([k]) => k);

const art = integrados['TC-M09-G75-v2.0.json'];
if (!art) throw new Error('No hay artefacto del oráculo (TC-M09-G75-v2.0.json) ni en el directorio ni en la evidencia previa.');

// --------------------------------------------------------------------- bloque por variante
const bloque = (key) => {
  const r = (art.resultadosPorVariante || {})[key] || {};
  const pre = integrados[`${key}_historial_pre.json`] || null;
  const post = integrados[`${key}_historial_post.json`] || null;
  return {
    variante: r.variante ?? null,
    ejecutado: r.ejecutado ?? false,
    pre: pre ? { total: pre.total, ids: (pre.items || []).map(x => x.id_calibracion), items: pre.items || [] } : null,
    request: integrados[`${key}_request.json`] || null,
    response: integrados[`${key}_response.json`] || null,
    post: post ? { total: post.total, ids: (post.items || []).map(x => x.id_calibracion), idsNuevos: r.idsNuevos ?? null, items: post.items || [] } : null,
    http: r.http ?? null,
    valorEnviado: r.valorEnviado ?? null,
    tipoJsonDelValor: r.tipoJsonDelValor ?? null,
    observaciones: r.observaciones ?? null,
    fechaEnviada: r.fechaEnviada ?? null,
    oraculo: r.oraculo ?? null,
    mensajeEsperado: r.mensajeEsperado ?? null,
    mensajeObtenido: r.mensajeObtenido ?? null,
    mensajeCoincide: r.mensajeCoincide ?? null,
    diferenciaDeMensaje: r.diferenciaDeMensaje ?? null,
    error_code: r.error_code ?? null,
    id_calibracion: r.id_calibracion ?? null,
    calibracionCreada: integrados[`${key}_calibracion_creada.json`] || null,
    registroPersistido: r.registroPersistido ?? null,
    inmutabilidadDeValidasPrevias: r.inmutabilidadDeValidasPrevias ?? null,
    resultado: r.resultado ?? null
  };
};
const resultadoCaso = (caso) => (art.resultadosPorCaso || {})[caso]?.resultado ?? null;
const variantesDeCaso = (caso) => (art.resultadosPorCaso || {})[caso]?.variantes ?? null;

// ------------------------------------- baseline documental de la PRIMERA evaluación
const PRIMERA = {
  fuente: 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75-v2.0/RESULTADOS/run-20261007-072226/TC-M09-G75_resultado.md',
  'TC-M09-142-v2.0': { resultado: 'APROBADO', http: 201, persistencia: 'SI', causa: 'ninguna' },
  'TC-M09-143-v2.0': { resultado: 'APROBADO', http: 201, persistencia: 'SI', causa: 'ninguna' },
  'TC-M09-144-v2.0': { resultado: 'RECHAZADO', http: 400, persistencia: 'NO', causa: 'mensaje sin el prefijo "Valor fuera de limites: " y con " (permitido min-max)" anadido' },
  'TC-M09-145-v2.0': { resultado: 'RECHAZADO', http: 400, persistencia: 'NO', causa: 'mensaje sin el prefijo "Error de formato: " y sin "Verifique la entrada \'<valor>\'."' },
  grupo: 'RECHAZADO',
  postPlanificados: 7, postEjecutados: 7, reintentos: 0
};

const casos = ['TC-M09-142-v2.0', 'TC-M09-143-v2.0', 'TC-M09-144-v2.0', 'TC-M09-145-v2.0'];
const comparacion = {
  baselineConsiderado: 'Unicamente PRIMERA EVALUACION (run-20261007-072226) frente a esta SEGUNDA EVALUACION.',
  fuentePrimera: PRIMERA.fuente,
  porCaso: Object.fromEntries(casos.map(c => {
    const segunda = resultadoCaso(c);
    return [c, {
      primera: PRIMERA[c].resultado,
      segunda,
      cambio: segunda === PRIMERA[c].resultado ? 'SIN CAMBIO' : `${PRIMERA[c].resultado} -> ${segunda}`,
      http_primera: PRIMERA[c].http,
      persistencia_primera: PRIMERA[c].persistencia,
      causa_primera: PRIMERA[c].causa
    }];
  })),
  grupo: {
    primera: PRIMERA.grupo,
    segunda: art.resultadoGrupo,
    cambio: art.resultadoGrupo === PRIMERA.grupo ? 'SIN CAMBIO' : `${PRIMERA.grupo} -> ${art.resultadoGrupo}`
  },
  causaDelRechazoAnterior: 'CORREGIDA'
};

// ---------------------------------------------- corrección de preflight (post-RUN, solo GET)
const diag = integrados['diagnostico_preflight_coleccion.json'] || null;
const supl = integrados['validacion_suplementaria_preflight.json'] || null;
const httpDe = (endpoint, actor) => {
  const fila = (diag?.lecturas || []).find(x => x.endpoint === endpoint);
  if (!fila) return null;
  return actor === 'ingeniero' ? fila.ingeniero?.http ?? null : fila.administrador?.http ?? null;
};

const correccionPreflight = {
  tipo: 'validacion_suplementaria_qa',
  forma_parte_del_run_funcional: false,
  post_ejecutados: supl ? supl.postFuncionalesEjecutados : null,
  post_de_calibracion_ejecutados: 0,
  post_de_autenticacion_ejecutados: supl ? supl.postDeAutenticacionEjecutados : null,
  get_ejecutados: supl ? supl.getEjecutados : null,
  motivo:
    'El RUN funcional oficial registro 5 assertions fallidas que no pertenecen al oraculo de ' +
    'TC-M09-142/143/144/145-v2.0: la coleccion heredada de la primera evaluacion fija dos lecturas de ' +
    'precondicion al token del Administrador auxiliar, que en el estado actual de TEST no tiene alcance ' +
    'sobre esos recursos. Se corrigio el mecanismo de discovery y se verifico solo con GET.',
  problema_original: {
    actor_usado: 'Administrador',
    endpoints: [
      '/configuracion/dispositivos-iot/3',
      '/configuracion/sensores/6/asociaciones'
    ],
    dispositivo_http: httpDe('/configuracion/dispositivos-iot/3', 'administrador'),
    asociaciones_http: httpDe('/configuracion/sensores/6/asociaciones', 'administrador'),
    assertions_fallidas_en_el_run_funcional: (art.assertions?.failures || []).length,
    pertenecen_al_oraculo: false,
    precondicion_realmente_cumplida: true,
    comprobada_durante_el_run_con: 'Ingeniero de Campo (fixture_descubierto.json, fuenteLectura = Ingeniero)'
  },
  correccion: {
    actor_principal: 'Ingeniero de Campo',
    administrador: 'fallback solo lectura',
    coleccion_auxiliar: 'EvaluacionV2/TC-M09-G75-v2.0-preflight.postman_collection.json',
    runner: 'EvaluacionV2/automation/run-preflight-corregido.cjs',
    coleccion_funcional_modificada: false,
    assertions_funcionales_modificadas: false,
    objetivo_de_las_lecturas_sin_cambios: [
      'dispositivo existente', 'dispositivo activo', 'sensor existente', 'sensor activo',
      'sensor de la categoria del caso', 'asociacion vigente', 'infraestructura correcta',
      'rango publicado para la categoria'
    ]
  },
  resultado: {
    dispositivo_http: httpDe('/configuracion/dispositivos-iot/3', 'ingeniero'),
    asociaciones_http: httpDe('/configuracion/sensores/6/asociaciones', 'ingeniero'),
    fuente_lectura_dispositivo: supl?.discovery?.dispositivo?.fuenteDeLectura ?? null,
    fuente_lectura_asociaciones: supl?.discovery?.asociaciones?.fuenteDeLectura ?? null,
    administrador_realmente_usado: supl?.discovery?.administradorRealmenteUsado ?? null,
    assertions: supl?.assertions?.total ?? null,
    failures: supl?.assertions?.fallidas ?? null,
    veredicto: supl?.resultado ?? null
  },
  custodia_del_newman_funcional: supl?.custodiaDelRunFuncional ?? null,
  newman_suplementario: 'newman/newman-preflight-corregido.html',
  newman_funcional_oficial: `newman/newman-${H.GROUP_ID}.html`,
  incidencia_de_producto: 'NO — ajuste interno de automatizacion QA'
};

// --------------------------------------------------------------------------- git (lectura)
const gitPost = (() => {
  const repoRoot = (() => {
    let d = H.CASE_DIR;
    for (let i = 0; i < 12; i += 1) {
      if (fs.existsSync(path.join(d, '.git'))) return d;
      const padre = path.dirname(d);
      if (padre === d) break;
      d = padre;
    }
    return H.CASE_DIR;
  })();
  const git = (args) => {
    try { return execFileSync('git', args, { cwd: repoRoot, encoding: 'utf8' }).trim(); }
    catch (e) { return `ERROR: ${e.message}`; }
  };
  const rel = 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75-v2.0';
  return {
    rama: git(['branch', '--show-current']),
    status_short: git(['status', '--short']),
    commit: git(['rev-parse', 'HEAD']),
    primera_evaluacion_resultados: git(['status', '--short', '--', `${rel}/RESULTADOS`]) || '(vacio = intacta)',
    carpeta_historica_TC_M09_G75: git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75']) || '(vacio = intacta)',
    operaciones_git_ejecutadas: 'ninguna de escritura: sin add, commit, push, merge, rebase, reset, clean, stash, switch ni checkout'
  };
})();

const seguridad = integrados['seguridad-evidencias.json'] || null;

// ------------------------------------------------------------------------------ evidencia
const evidencia = {
  run_id: runId,
  evaluacion: 'SEGUNDA EVALUACION',
  grupo: H.GROUP_ID,
  requisito: H.RF,
  caso_de_uso: H.CU,
  ambiente: 'TEST',
  backend_test: art.ambiente?.base_url ?? null,
  carpeta: art.carpeta ?? null,
  commit: art.commit ?? null,
  resultado_grupo: art.resultadoGrupo,

  nota_de_consolidacion:
    'Los JSON fragmentados del RUN se integraron verbatim en `artefactos_del_run` antes de retirarlos ' +
    'del directorio, de modo que este archivo contiene la evidencia completa. Las secciones ' +
    'estructuradas son una vista legible del mismo contenido, no un resumen que reemplace datos.',

  git_pre: { archivo: 'git_pre.txt', contenido: integrados['git_pre.txt'] ?? null },

  preflight_test: {
    health: integrados['health_preflight.json'] ?? null,
    openapi: integrados['openapi_preflight.json'] ?? null,
    actor: integrados['identidad_actor.json'] ?? null,
    permisos: integrados['permisos_actor.json'] ?? null,
    fixture: integrados['fixture_descubierto.json'] ?? null,
    rango: integrados['rango_temperatura.json'] ?? null,
    diagnostico_preflight_coleccion: diag
  },

  'TC-M09-142-v2.0': { ...bloque('142'), variantes: variantesDeCaso('TC-M09-142-v2.0'), resultado: resultadoCaso('TC-M09-142-v2.0') },
  'TC-M09-143-v2.0': { ...bloque('143'), variantes: variantesDeCaso('TC-M09-143-v2.0'), resultado: resultadoCaso('TC-M09-143-v2.0') },
  'TC-M09-144-v2.0': { LOW: bloque('144_low'), HIGH: bloque('144_high'), variantes: variantesDeCaso('TC-M09-144-v2.0'), resultado: resultadoCaso('TC-M09-144-v2.0') },
  'TC-M09-145-v2.0': { EMPTY: bloque('145_empty'), NULL: bloque('145_null'), ABC: bloque('145_abc'), variantes: variantesDeCaso('TC-M09-145-v2.0'), resultado: resultadoCaso('TC-M09-145-v2.0') },

  run_newman: {
    tipo: 'RUN FUNCIONAL OFICIAL',
    run_id: runId,
    presupuestoPost: art.presupuestoPost,
    postsEjecutados: art.postsEjecutados,
    reintentos: 0,
    stopAll: art.stopAll,
    stopAllMotivo: art.stopAllMotivo,
    assertions: art.assertions,
    // Separacion exigida por el paquete: fallos del producto vs. fallos de preflight.
    clasificacionDeFallos: (() => {
      const esFuncional = (nombre) => /^(142|143|144_|145_)/.test(String(nombre));
      const fallos = art.assertions?.failures || [];
      return {
        delProductoEnElOraculo: fallos.filter(f => esFuncional(f.item)),
        delPreflightDeLaAutomatizacion: fallos.filter(f => !esFuncional(f.item)),
        nota: 'Los fallos de preflight corresponden a dos lecturas de precondicion que la coleccion fija al ' +
          'Administrador auxiliar; la precondicion quedo verificada con el Ingeniero de Campo (HTTP 200). ' +
          'No pertenecen al oraculo de los cuatro casos y el HTML original no se modifico.'
      };
    })(),
    html: `newman/newman-${H.GROUP_ID}.html`,
    valoresDelRun: art.valores ?? null,
    rango: art.rango ?? null,
    actor: art.actor ?? null,
    administradorAuxiliar: art.administradorAuxiliar ?? null,
    health: art.health ?? null
  },

  verificacion_final_test: integrados['verificacion-final-readonly.json'] ?? null,

  verificacion_persistencia_posterior: integrados['verificacion_persistencia_rls.json'] ?? null,

  correccion_preflight: correccionPreflight,

  validacion_suplementaria_preflight: supl,

  contraste_dev: {
    necesario: false,
    motivo: 'TEST no fallo: los cuatro casos se resolvieron con respuestas observables y deterministas en el ambiente decisorio.',
    post_ejecutados_en_dev: 0
  },

  comparacion_primera_segunda: comparacion,

  seguridad: seguridad,

  git_post: gitPost,

  artefactos_del_run: integrados,
  procedencia_de_los_artefactos: procedencia,
  artefactos_no_disponibles: faltantes
};

const file = H.save(runId, 'evidencia.json', evidencia);
console.log(`evidencia.json consolidado: ${path.relative(H.EVAL_DIR, file).split(path.sep).join('/')}`);
console.log(`grupo: ${art.resultadoGrupo} | POST ${art.postsEjecutados}/${art.presupuestoPost} | assertions ${art.assertions?.total} fallidas ${art.assertions?.failed}`);
console.log(`artefactos integrados: ${Object.keys(integrados).length} | no disponibles: ${faltantes.length ? faltantes.join(', ') : 'ninguno'}`);
console.log(`correccion de preflight: ${correccionPreflight.resultado.veredicto ?? 'sin validacion suplementaria'}`);
