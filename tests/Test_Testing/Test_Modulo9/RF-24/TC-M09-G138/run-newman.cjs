// TC-M09-G138: preflight de VISION en TEST con Newman. Sin POST si falta contrato.
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const {execFileSync}=require('child_process');
const newman=require(path.join(path.dirname(process.execPath),'node_modules','newman'));

const base=(process.env.QA_BASE_URL||'').replace(/\/$/,'');
const runId=process.env.G138_RUN_ID;
if(path.basename(__dirname)!=='TC-M09-G138'||base!=='https://api.inmero.co/back-sigab-test')
  throw new Error('Carpeta G138 o backend TEST incorrectos.');
if(!/^run-\d{8}-\d{6}$/.test(runId||''))throw new Error('G138_RUN_ID inválido.');
const out=path.join(__dirname,'RESULTADOS',runId);
if(fs.existsSync(out))throw new Error('RUN_ID existente: no se sobrescribe.');

function git(args){let d=__dirname;while(!fs.existsSync(path.join(d,'.git'))&&path.dirname(d)!==d)d=path.dirname(d);
  return execFileSync('git',args,{cwd:d,encoding:'utf8'}).trim();}
function snapshotGit(){return {rama:git(['branch','--show-current']),status_short:git(['status','--short']),
  diff_stat:git(['diff','--stat']),diff_cached_stat:git(['diff','--cached','--stat']),
  head:git(['rev-parse','HEAD']),origin_test:git(['rev-parse','origin/test']),
  divergencia:git(['rev-list','--left-right','--count','HEAD...origin/test'])};}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function exactCount(raw,word){return (raw.match(new RegExp('\\b'+word+'\\b','gi'))||[]).length;}
function getOpenapi(){const collection=JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G138.postman_collection.json'),'utf8'));
  return new Promise((resolve,reject)=>newman.run({collection,reporters:['cli'],silent:true,
    timeoutRequest:30000,envVar:[{key:'base_url',value:base}]},(err,summary)=>{
    const ex=summary?.run?.executions?.[0];if(err||!ex?.response)return reject(new Error(`Newman sin respuesta OpenAPI: ${err?.message||'desconocido'}`));
    const raw=ex.response.stream.toString('utf8');let doc;try{doc=JSON.parse(raw);}catch{return reject(new Error('OpenAPI TEST no devuelve JSON.'));}
    resolve({http:ex.response.code,raw,doc,assertions:(ex.assertions||[]).map(a=>({nombre:a.assertion,error:a.error?.message||null})),
      failures:(summary?.run?.failures||[]).map(x=>x.error?.message||'fallo Newman')});}));}
function operationEvidence(p,m,o){return {method:m.toUpperCase(),path:p,summary:o.summary||null,
  request_schema:o.requestBody?.content?.['application/json']?.schema||null,
  responses:Object.keys(o.responses||{}),security:o.security||null};}
function discover(doc,raw){const ops=Object.entries(doc.paths||{}).flatMap(([p,methods])=>Object.entries(methods)
  .filter(([m])=>['get','post','put','patch','delete'].includes(m)).map(([m,o])=>({p,m,o})));
  const terms=Object.fromEntries(['VISION','modo_calibracion','ventana_observacion','origen_disparo',
    'linea_base','baseline'].map(x=>[x,exactCount(raw,x)]));
  const candidates=ops.filter(({p,o})=>/\bvision\b/i.test([p,o.summary,o.description].join(' '))||
    /modo_calibracion|ventana_observacion/i.test(JSON.stringify(o.requestBody||{})));
  const vision=candidates.filter(({p,m,o})=>['post','put','patch'].includes(m)&&
    /\bvision\b|modo_calibracion|ventana_observacion/i.test(JSON.stringify({path:p,summary:o.summary,
      description:o.description,requestBody:o.requestBody})));
  const sensor=doc.paths?.['/configuracion/sensores/{id_sensor}/calibrar']?.post;
  const dto=doc.components?.schemas?.RegistrarCalibracionDTO;
  return {encontrada:vision.length>0,method:vision[0]?.m.toUpperCase()||null,path:vision[0]?.p||null,
    request_schema:vision[0]?.o.requestBody||null,responses:vision[0]?Object.keys(vision[0].o.responses||{}):null,
    security:vision[0]?.o.security||null,
    busqueda:{paths_totales:Object.keys(doc.paths||{}).length,
      post_totales:ops.filter(x=>x.m==='post').length,schemas_totales:Object.keys(doc.components?.schemas||{}).length,
      apariciones_exactas:terms,operaciones_vision_candidatas:candidates.map(x=>operationEvidence(x.p,x.m,x.o))},
    calibracion_sensor:sensor?{...operationEvidence('/configuracion/sensores/{id_sensor}/calibrar','post',sensor),
      dto:'RegistrarCalibracionDTO',campos:Object.keys(dto?.properties||{}),requeridos:dto?.required||[]}:null};}

function report(e){const v=e.openapi_vision;
  const caseDescriptions=[
    {id:'TC-M09-278',fixture:'A2 activa, especie AVES y modelo MODELO_AVES, sin cámaras asociadas',
      why:'Sin una operación VISION publicada no se puede enviar la ventana de observación para A2 ni comprobar que la falta de cámara produzca el 422 específico.'},
    {id:'TC-M09-279',fixture:'A3 activa con una única cámara C3 asociada e inactiva',
      why:'No se creó ni desactivó C3: el caso no tiene un endpoint VISION donde comprobar que una cámara inactiva provoca el 422 contractual.'},
    {id:'TC-M09-280',fixture:'A4 con cámara activa y paradigma INDIVIDUAL formalmente confirmado',
      why:'La ausencia de VISION impide la prueba antes de resolver el mapeo formal de MODELO_ESPECIES_GRANDES a INDIVIDUAL. No se atribuye un fallo adicional al paradigma ni a RFC-009.'},
    {id:'TC-M09-281',fixture:'A5 activa, especie AVES, cámara activa y tipo_modelo_asignado=null',
      why:'Sin el request VISION no puede comprobarse que la falta de modelo asignado origine el 422 ni que la línea base permanezca igual.'}
  ];
  const sections=caseDescriptions.flatMap(x=>[`### ${x.id} — RECHAZADO`,'',
    `**Escenario que debía probarse.** ${x.fixture}. El Ingeniero debía recibir HTTP 422 y el mensaje VISION exacto con el ID de esa área; no debía aparecer una nueva línea base.`,'',
    `**Qué ocurrió en TEST.** ${x.why} No se preparó el área ni se envió POST. Por ello HTTP, mensaje y línea base PRE/POST son **no observables**, no un 422 fallido medido.`, '',
    '**Por qué se rechaza.** La matriz de G138 considera la ausencia de la operación VISION un incumplimiento ejecutable para este caso. El defecto comprobado es que TEST no expone la funcionalidad necesaria para aplicar la regla; el comportamiento interno de esa regla aún no se ha evaluado.','']);
  const md=[
    '# TC-M09-G138 — Resultado','',
    `**Resultado general: ${e.resultado_general}.** RUN_ID: ${runId}. Ambiente decisorio: TEST. Prueba local: NO.`,'',
    '## Decisión general','',
    '| Caso | Precondición negativa | Resultado | Motivo |','|---|---|---|---|',
    '| TC-M09-278 | Área sin cámara | RECHAZADO | VISION no está publicada en TEST. |',
    '| TC-M09-279 | Única cámara inactiva | RECHAZADO | VISION no está publicada en TEST. |',
    '| TC-M09-280 | Paradigma INDIVIDUAL | RECHAZADO | VISION no está publicada en TEST. |',
    '| TC-M09-281 | Sin `tipo_modelo_asignado` | RECHAZADO | VISION no está publicada en TEST. |','',
    '## OpenAPI VISION','',
    `Newman consultó \`GET ${base}/openapi.json\` y obtuvo HTTP ${e.openapi_http}, con sus dos assertions correctas. Se revisaron ${v.busqueda.paths_totales} rutas, ${v.busqueda.post_totales} POST y ${v.busqueda.schemas_totales} esquemas. No se publicó ninguna operación VISION: método, ruta, body, respuestas y seguridad VISION figuran ausentes.`, '',
    'La única calibración publicada es `POST /configuracion/sensores/{id_sensor}/calibrar`, identificada en el contrato como **Flujo D SENSOR**. `RegistrarCalibracionDTO` requiere dispositivo, infraestructura y fecha; no declara `modo_calibracion`, `area_id` ni `ventana_observacion`. Tampoco aparece `VISION` como término exacto en el OpenAPI. Aceptar campos extras en ese endpoint no demuestra una operación de Flujo F.', '',
    `Hash SHA-256 del OpenAPI consultado: \`${e.openapi_sha256}\`. La búsqueda estructurada y los campos del DTO SENSOR se encuentran en \`evidencia.json\`.`, '',
    '## Fixtures y fuente de discovery','',
    'No se crearon A2, A3, A4, A5 ni cámaras. El preflight de operación es anterior a cualquier setup; al fallar, crear esos fixtures solo modificaría TEST sin permitir probar VISION. Los IDs, el conteo de cámaras y los snapshots de línea base se registran como **no aplicables/no evaluados**, nunca como cero medido.', '',
    '## Fuente formal del paradigma TC-280','',
    'No se consultó RFC-009 ni se clasificó MODELO_ESPECIES_GRANDES. El caso ya tiene una causa de rechazo anterior y concluyente: la operación VISION falta en TEST. Esta decisión no equivale a afirmar que el paradigma esté confirmado o que haya un defecto documental.', '',
    '## Resultado por caso','',...sections,
    '## Ejecución y trazabilidad','',
    `- Rama: \`${e.git.rama}\`; HEAD: \`${e.git.head}\`; origin/test: \`${e.git.origin_test}\`; divergencia: \`${e.git.divergencia}\`.`,
    `- Git previo: ${e.git.status_short?'carpetas QA sin seguimiento; detalle en evidencia.json':'limpio'}; diff de archivos seguidos: ${e.git.diff_stat||'vacío'}; staged: ${e.git.diff_cached_stat||'vacío'}.`,
    '- POST VISION planificados tras el preflight: 0; ejecutados: 0. POST/PATCH de setup: 0. STOP_ALL: NO (no hubo intento funcional). SQL: ninguno. No se utilizó actor funcional ni Administrador.','',
    '## Incidencias','',
    '**INCIDENCIA REQUERIDA: SÍ.** Se consolida una sola incidencia porque los cuatro casos comparten la misma causa observable: TEST no publica la operación RF-24 VISION.','',
    '- **Grupo responsable:** Desarrollo. **Grupo de prueba:** TC-M09-G138. **Casos afectados:** TC-M09-278, TC-M09-279, TC-M09-280 y TC-M09-281. **Resultado:** RECHAZADO.',
    '- **Motivo:** no es posible ejecutar las cuatro validaciones obligatorias de VISION ni obtener sus respuestas contractuales.',
    '- **Esperado:** operación VISION publicada; cada fixture válido salvo una precondición negativa debe obtener HTTP 422, mensaje exacto con su ID de área y ninguna línea base nueva.',
    `- **Obtenido:** operación VISION ausente en ${v.busqueda.paths_totales} rutas y ${v.busqueda.schemas_totales} esquemas de OpenAPI TEST. El único POST de calibración publicado es SENSOR Flujo D.`,
    '- **Causa raíz observable:** contrato VISION no expuesto en TEST. La API no permite distinguir si la lógica aún no está implementada o si está pendiente su despliegue; Desarrollo debe investigar ese punto. No hay evidencia para atribuir el fallo a AIoT o DBA.',
    '- **Type:** bug. **Severity:** Important. **Priority:** High. **Evidencia:** `evidencia.json` y `newman.html`.','',
    '## Conclusión','',
    'Los cuatro casos y G138 quedan **RECHAZADOS** por la regla explícita del paquete para una operación VISION no publicada. No se midió un 422 incorrecto ni se afirmó que un fixture o la línea base fallara: esas comprobaciones requieren primero la operación VISION en TEST.',''];
  fs.writeFileSync(path.join(out,'TC-M09-G138_resultado.md'),md.join('\n'),'utf8');
  fs.writeFileSync(path.join(out,'newman.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>G138 Newman OpenAPI TEST</title><style>body{font:16px system-ui;max-width:70rem;margin:2rem;line-height:1.45}pre{white-space:pre-wrap;background:#f4f4f4;padding:1rem}</style><h1>G138 — Newman GET OpenAPI TEST</h1><p>RUN ${esc(runId)} · HTTP ${e.openapi_http} · VISION publicada: NO · POST VISION: 0</p><h2>Assertions Newman</h2><pre>${esc(JSON.stringify(e.newman.assertions,null,2))}</pre><h2>Discovery contractual</h2><pre>${esc(JSON.stringify(e.openapi_vision,null,2))}</pre><p>OpenAPI SHA-256: ${esc(e.openapi_sha256)}</p></html>`,'utf8');}
async function main(){const e={grupo:'TC-M09-G138',casos:['TC-M09-278','TC-M09-279','TC-M09-280','TC-M09-281'],
  run_id:runId,ambiente:'TEST',prueba_local:false,base_url:base,git:snapshotGit(),openapi_vision:{},
  actores:{ingeniero:'NO CONSULTADO: VISION ausente',administrador:'NO CONSULTADO: VISION ausente'},
  fuente_paradigma_tc280:{estado:'NO EVALUADA',motivo:'No se llegó a la preparación del fixture A4'},
  fixtures:{A2:{estado:'NO CREADO'},A3:{estado:'NO CREADO'},A4:{estado:'NO CREADO'},A5:{estado:'NO CREADO'}},
  'TC-M09-278':{},'TC-M09-279':{},'TC-M09-280':{},'TC-M09-281':{},
  post_vision_planificados:0,post_vision_ejecutados:0,post_setup_ejecutados:0,
  sql_ejecutado:'ninguno',stop_all:false,resultado_general:'',motivo_general:'',incidencias:[]};
  if(e.git.rama!=='qa/juan-esteban-rf24-v2')throw new Error(`Rama inesperada: ${e.git.rama}`);
  fs.mkdirSync(out,{recursive:true});const o=await getOpenapi();e.openapi_http=o.http;
  e.newman={assertions:o.assertions,fallos:o.failures};
  if(o.http!==200||o.failures.length)throw new Error(`Preflight Newman inválido: HTTP ${o.http}; ${o.failures.join('; ')}`);
  e.openapi_observed_at_utc=new Date().toISOString();
  e.openapi_sha256=crypto.createHash('sha256').update(o.raw).digest('hex');e.openapi_vision=discover(o.doc,o.raw);
  if(e.openapi_vision.encontrada)throw new Error('Operación VISION candidata encontrada: comprobar contrato y fixtures antes de POST. Runner no envía escritura automática.');
  const names={'TC-M09-278':'área sin cámara','TC-M09-279':'única cámara inactiva',
    'TC-M09-280':'paradigma INDIVIDUAL','TC-M09-281':'sin tipo_modelo_asignado'};
  for(const id of e.casos)e[id]={resultado:'RECHAZADO',precondicion_negativa:names[id],fixture:'NO CREADO',
    post_ejecutado:false,http_esperado:422,http_obtenido:null,mensaje_exacto:'NO OBSERVABLE: sin operación VISION',
    linea_base_pre_post:'NO OBSERVABLE: no hubo POST ni fixture',
    motivo:`TEST no publica operación VISION para probar ${names[id]}; la matriz G138 califica esta ausencia como rechazo.`};
  e.resultado_general='RECHAZADO';e.motivo_general='Los cuatro casos comparten la ausencia concluyente del contrato VISION en TEST.';
  e.incidencias=[{incidencia_requerida:'SÍ',grupo_responsable:'Desarrollo',grupo:'TC-M09-G138',
    casos:e.casos,resultado:'RECHAZADO',motivo:'VISION no publicada en OpenAPI TEST.',
    esperado:'Operación VISION y HTTP 422/mensaje exacto para las cuatro precondiciones negativas.',
    obtenido:'Solo calibración SENSOR Flujo D; operación VISION ausente.',
    causa_raiz:'Contrato RF-24 VISION no expuesto en TEST; mecanismo implementación/despliegue pendiente de determinar.',
    type:'bug',severity:'Important',priority:'High',evidencia:'evidencia.json / newman.html'}];
  fs.writeFileSync(path.join(out,'evidencia.json'),JSON.stringify(e,null,2),'utf8');report(e);
  console.log(`G138 RECHAZADO; 278-281 RECHAZADOS; VISION: NO; POST VISION: 0; ${out}`);}
main().catch(x=>{console.error(x.stack||x.message);process.exitCode=1;});
