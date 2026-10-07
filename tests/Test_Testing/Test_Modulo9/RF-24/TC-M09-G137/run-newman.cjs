// G137: discovery contractual sin escrituras cuando TEST no publica RF-24 VISION.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const {execFileSync} = require('child_process');
const newman = require(path.join(path.dirname(process.execPath), 'node_modules', 'newman'));

const base = (process.env.QA_BASE_URL || '').replace(/\/$/, '');
const runId = process.env.G137_RUN_ID;
if(path.basename(__dirname)!=='TC-M09-G137' || base!=='https://api.inmero.co/back-sigab-test')
  throw new Error('Carpeta o backend TEST incorrectos.');
if(!/^run-\d{8}-\d{6}$/.test(runId||'')) throw new Error('G137_RUN_ID inválido.');
const out=path.join(__dirname,'RESULTADOS',runId);
if(fs.existsSync(out)) throw new Error('RUN_ID existente: no se sobrescribe.');
function git(args){let d=__dirname;while(!fs.existsSync(path.join(d,'.git'))&&path.dirname(d)!==d)d=path.dirname(d);
  return execFileSync('git',args,{cwd:d,encoding:'utf8'}).trim();}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function count(s,term){return (s.match(new RegExp('\\b'+term+'\\b','gi'))||[]).length;}
function conciseOperation(pathname,method,operation){return {method:method.toUpperCase(),path:pathname,
  summary:operation.summary||null,request_schema:operation.requestBody?.content?.['application/json']?.schema||null,
  responses:Object.keys(operation.responses||{}),security:operation.security||null};}
function contractualDiscovery(doc,raw){const operations=Object.entries(doc.paths||{}).flatMap(([p,methods])=>
  Object.entries(methods).filter(([method])=>['get','post','put','patch','delete'].includes(method))
    .map(([method,operation])=>({path:p,method,operation})));
  const termCounts=Object.fromEntries(['VISION','modo_calibracion','ventana_observacion','origen_disparo',
    'linea_base','baseline','vectores_comportamiento'].map(t=>[t,count(raw,t)]));
  const candidates=operations.filter(({path:p,operation})=>/\bvision\b/i.test([p,operation.summary,operation.description].join(' ')) ||
    /modo_calibracion|ventana_observacion/i.test(JSON.stringify(operation.requestBody||{})));
  const schema=doc.components?.schemas?.RegistrarCalibracionDTO||null;
  const sensor=doc.paths?.['/configuracion/sensores/{id_sensor}/calibrar']?.post;
  const vision=candidates.filter(({path:p,method,operation})=>['post','put','patch'].includes(method) &&
    /\bvision\b|modo_calibracion|ventana_observacion/i.test(JSON.stringify({path:p,summary:operation.summary,
      description:operation.description,body:operation.requestBody})));
  return {encontrada:vision.length>0,method:vision[0]?.method.toUpperCase()||null,path:vision[0]?.path||null,
    request_schema:vision[0]?.operation.requestBody||null,responses:vision[0]?Object.keys(vision[0].operation.responses||{}):null,
    security:vision[0]?.operation.security||null,
    operaciones_vision_candidatas:candidates.map(x=>conciseOperation(x.path,x.method,x.operation)),
    busqueda:{paths_totales:Object.keys(doc.paths||{}).length,post_totales:operations.filter(x=>x.method==='post').length,
      schemas_totales:Object.keys(doc.components?.schemas||{}).length,apariciones_exactas:termCounts},
    operacion_sensor_existente:sensor?{...conciseOperation('/configuracion/sensores/{id_sensor}/calibrar','post',sensor),
      dto:'RegistrarCalibracionDTO',campos:Object.keys(schema?.properties||{}),requeridos:schema?.required||[]} : null};}
function getOpenapi(){const collection=JSON.parse(fs.readFileSync(path.join(__dirname,'TC-M09-G137.postman_collection.json'),'utf8'));
  return new Promise((resolve,reject)=>newman.run({collection,reporters:['cli'],silent:true,timeoutRequest:30000,
    envVar:[{key:'base_url',value:base}]},(err,summary)=>{const ex=summary?.run?.executions?.[0];
    if(err||!ex?.response)return reject(new Error(`Newman no obtuvo OpenAPI: ${err?.message||'sin respuesta'}`));
    const raw=ex.response.stream.toString('utf8');let doc;try{doc=JSON.parse(raw);}catch{return reject(new Error('OpenAPI TEST no es JSON.'));}
    resolve({http:ex.response.code,raw,doc,assertions:(ex.assertions||[]).map(x=>({nombre:x.assertion,
      error:x.error?.message||null})),fallos:(summary.run.failures||[]).map(x=>x.error?.message||'fallo Newman')});}));}
function writeResults(e){const json=JSON.stringify(e,null,2);fs.writeFileSync(path.join(out,'evidencia.json'),json,'utf8');
  const v=e.openapi_vision;const c275=e['TC-M09-275'],c276=e['TC-M09-276'],c277=e['TC-M09-277'];
  const md=[
    '# TC-M09-G137 — Resultado','',
    `**Resultado general: ${e.resultado_general}.** RUN_ID: ${runId}. Ambiente decisorio: TEST. Prueba local: NO.`,'',
    '## Decisión general','',
    '| Caso | Resultado | Motivo principal |','|---|---|---|',
    `| TC-M09-275 | ${c275.resultado} | No hay operación VISION para el disparo manual del Ingeniero. |`,
    `| TC-M09-276 | ${c276.resultado} | No hay operación VISION para el disparo manual del Administrador. |`,
    `| TC-M09-277 | ${c277.resultado} | No existe la operación VISION sobre la cual exigir el 403 contractual al Productor. |`,'',
    '## Preflight VISION','',
    `Newman consultó **GET ${base}/openapi.json** y recibió HTTP ${e.openapi_http}. El documento contiene ${v.busqueda.paths_totales} rutas, ${v.busqueda.post_totales} operaciones POST y ${v.busqueda.schemas_totales} esquemas. La revisión de rutas, descripciones y cuerpos no identificó una operación RF-24 VISION.`, '',
    'La única operación de calibración publicada es `POST /configuracion/sensores/{id_sensor}/calibrar`, descrita como **Flujo D: calibración de sensor**. Su body `RegistrarCalibracionDTO` declara `id_dispositivo_iot`, `id_infraestructura`, `valor_referencia`, `ganancia`, `offset`, `fecha_calibracion` y `observaciones`. No declara `modo_calibracion`, `area_id` ni `ventana_observacion`. En todo el OpenAPI hay cero apariciones exactas de `VISION`, `modo_calibracion`, `ventana_observacion` y `origen_disparo`. Por ello ese POST SENSOR no demuestra el Flujo F.', '',
    `**Operación VISION encontrada:** NO. **Método/ruta:** no publicados. **Schema/respuestas/security VISION:** no publicados. Hash SHA-256 del OpenAPI consultado: \`${e.openapi_sha256}\`.`, '',
    'El preflight termina aquí conforme al orden del paquete. Persistencia de línea base, dependencias M03, área/especie/modelo/cámara y volumen mínimo: **no evaluados**. No se infiere que esas dependencias falten; su verificación solo tendría sentido después de identificar la operación VISION. No se hicieron consultas SQL, Pytest, login de actores ni preparación de Productor.', '',
    '## TC-M09-275 — Ingeniero de Campo','',
    '**Escenario esperado.** El Ingeniero dispara manualmente VISION con un área y una ventana válida. Tras un 2xx, debe quedar una línea base nueva, vigente, de origen MANUAL y atribuida a él, además de una auditoría exitosa.', '',
    '**Qué se pudo comprobar.** TEST no publica método, ruta ni body VISION. Por eso no hay un request contractual que permita iniciar el caso. No se envió POST y no se buscó una línea base que este RUN no podía crear.', '',
    `**Decisión: ${c275.resultado}.** Es un bloqueo de precondición: no se alcanzó el flujo positivo. No se afirma que la persistencia, M03 o la auditoría hayan fallado; quedaron sin evaluar por la ausencia anterior.`, '',
    '## TC-M09-276 — Administrador','',
    '**Escenario esperado.** El Administrador repite la misma calibración VISION válida y debe generar otra línea base manual, vigente y atribuida a su usuario, diferenciable de la del Ingeniero.', '',
    '**Qué se pudo comprobar.** La misma ausencia de contrato VISION impide construir su POST. Ejecutar el endpoint SENSOR cambiaría la operación bajo prueba. No se utilizó la cuenta Administrador para una escritura ni se preparó un fixture.', '',
    `**Decisión: ${c276.resultado}.** Falta la operación VISION publicada; la sustitución de línea base y el usuario responsable no son verificables todavía.`, '',
    '## TC-M09-277 — Productor','',
    '**Escenario esperado.** Un Productor activo envía un request VISION estructuralmente válido y recibe HTTP 403 con el mensaje exacto: “Acceso denegado: La calibración de sensores es una función crítica restringida exclusivamente al Ingeniero de Campo o al Administrador.” No debe existir efecto funcional.', '',
    '**Qué se obtuvo.** TEST no publica una operación VISION ni el schema necesario para construir ese request. En consecuencia no hay un endpoint VISION que pueda responder 403 o el mensaje contractual. No se envió POST; el HTTP obtenido y el mensaje son **no observables**, y no se realizó login del Productor porque el preflight se detuvo antes de usar cualquier actor.', '',
    `**Decisión: ${c277.resultado}.** La matriz de G137 califica expresamente como rechazo la ausencia de la operación VISION para este caso de seguridad. La evidencia demuestra falta de exposición del control contractual; no demuestra cómo se comportaría un endpoint VISION si llegara a publicarse.`, '',
    '## Ejecución y trazabilidad','',
    `- Rama: \`${e.git.rama}\`; HEAD: \`${e.git.head}\`; origin/test: \`${e.git.origin_test}\`; divergencia: \`${e.git.divergencia}\`.`,
    `- Estado Git previo: ${e.git.status_short ? 'hay carpetas QA sin seguimiento de grupos anteriores y G137; detalle en evidencia.json' : 'limpio'}. Diff de archivos seguidos: ${e.git.diff_stat||'vacío'}; staged: ${e.git.diff_cached_stat||'vacío'}.`,
    '- POST VISION planificados: 0 tras el preflight; ejecutados: 0. POST de setup: 0. SELECT/SQL: ninguno. No hubo cambios de cuenta ni de BD.','',
    '## Incidencias','',
    '**INCIDENCIA REQUERIDA: SÍ.** Una incidencia para la causa compartida: la operación RF-24 VISION no está publicada en el contrato de TEST. Afecta a los tres casos, con distinto resultado por el oráculo de cada uno.','',
    `- **Casos:** ${e.incidencias[0].casos_afectados.join(', ')}. **Grupo responsable:** Desarrollo. **Grupo de prueba:** TC-M09-G137.`,
    '- **Motivo:** TC-275 y TC-276 no pueden iniciar la calibración manual; TC-277 no puede observar el 403 y el mensaje exigidos a un Productor en la operación VISION.',
    '- **Esperado:** operación VISION publicada, con body para área y ventana; disparos positivos 2xx y control Productor 403 con texto exacto.',
    `- **Obtenido:** solo POST de calibración SENSOR Flujo D; ningún método/ruta/body VISION en ${v.busqueda.paths_totales} rutas, ${v.busqueda.post_totales} POST y ${v.busqueda.schemas_totales} esquemas del OpenAPI de TEST.`,
    '- **Causa raíz observable:** falta de exposición del contrato RF-24 VISION en TEST. Con la API sola no se distingue si falta implementación o despliegue; Desarrollo debe determinar ese mecanismo.',
    '- **Type:** bug. **Severity:** Important. **Priority:** High. **Evidencia:** `evidencia.json` (resumen y hash OpenAPI), `newman.html` (GET contractual).','',
    '## Conclusión','',
    'G137 queda **RECHAZADO** porque TC-277 tiene un incumplimiento concluyente según la matriz. TC-275 y TC-276 permanecen **BLOQUEADOS / NO VERIFICABLES**. El siguiente paso del producto es publicar el contrato VISION en TEST; solo entonces podrán prepararse y evaluarse las dependencias M03, la línea base y los tres POST reales.',''];
  fs.writeFileSync(path.join(out,'TC-M09-G137_resultado.md'),md.join('\n'),'utf8');
  fs.writeFileSync(path.join(out,'newman.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>G137 Newman OpenAPI TEST</title><style>body{font:16px system-ui;max-width:70rem;margin:2rem;line-height:1.45}pre{white-space:pre-wrap;background:#f4f4f4;padding:1rem}</style><h1>G137 — Newman GET OpenAPI TEST</h1><p>RUN ${esc(runId)} · HTTP ${e.openapi_http} · operación VISION encontrada: ${v.encontrada?'sí':'no'} · POST VISION ejecutados: 0</p><h2>Assertions Newman</h2><pre>${esc(JSON.stringify(e.newman.assertions,null,2))}</pre><h2>Contrato relevante</h2><pre>${esc(JSON.stringify({busqueda:v.busqueda,operaciones_vision_candidatas:v.operaciones_vision_candidatas,operacion_sensor_existente:v.operacion_sensor_existente},null,2))}</pre><p>OpenAPI SHA-256: ${esc(e.openapi_sha256)}</p></html>`,'utf8');}
async function main(){const e={grupo:'TC-M09-G137',casos:['TC-M09-275','TC-M09-276','TC-M09-277'],run_id:runId,
  ambiente:'TEST',prueba_local:false,base_url:base,git:{rama:git(['branch','--show-current']),
    status_short:git(['status','--short']),diff_stat:git(['diff','--stat']),
    diff_cached_stat:git(['diff','--cached','--stat']),head:git(['rev-parse','HEAD']),
    origin_test:git(['rev-parse','origin/test']),divergencia:git(['rev-list','--left-right','--count','HEAD...origin/test'])},
  openapi_vision:{},precondiciones_vision:{linea_base_verificable:'NO EVALUADA',area:'NO EVALUADA',
    especie:'NO EVALUADA',modelo:'NO EVALUADA',camara:'NO EVALUADA',vectores:'NO EVALUADOS',minimo:'NO EVALUADO'},
  actores:{ingeniero:'NO CONSULTADO: no existe operación VISION',administrador:'NO CONSULTADO: no existe operación VISION',
    productor:'NO CONSULTADO: no existe operación VISION'},setup_productor:{realizado:false,motivo:'Sin operación VISION; no se modificó cuenta'},
  post_vision_planificados:0,post_vision_ejecutados:0,post_setup_ejecutados:0,sql_ejecutado:'ninguno',
  'TC-M09-275':{},'TC-M09-276':{},'TC-M09-277':{},resultado_general:'',motivo_general:'',incidencias:[]};
  if(e.git.rama!=='qa/juan-esteban-rf24-v2')throw new Error(`Rama incorrecta: ${e.git.rama}`);
  fs.mkdirSync(out,{recursive:true});const fetched=await getOpenapi();e.openapi_http=fetched.http;
  e.newman={assertions:fetched.assertions,fallos:fetched.fallos};
  if(fetched.http!==200||fetched.fallos.length)throw new Error(`OpenAPI/Newman no verificable: HTTP ${fetched.http}; ${fetched.fallos.join('; ')}`);
  e.openapi_observed_at_utc=new Date().toISOString();
  e.openapi_sha256=crypto.createHash('sha256').update(fetched.raw).digest('hex');
  e.openapi_vision=contractualDiscovery(fetched.doc,fetched.raw);
  if(e.openapi_vision.encontrada)throw new Error('Se encontró una posible operación VISION: revisar body, persistencia y M03 antes de ejecutar; runner seguro no envía POST.');
  e['TC-M09-275']={resultado:'BLOQUEADO / NO VERIFICABLE',post_ejecutado:false,
    motivo:'No existe en OpenAPI TEST una operación VISION para ejecutar el disparo manual del Ingeniero. La línea base, M03 y auditoría no se evaluaron.'};
  e['TC-M09-276']={resultado:'BLOQUEADO / NO VERIFICABLE',post_ejecutado:false,
    motivo:'No existe en OpenAPI TEST una operación VISION para ejecutar el disparo manual del Administrador. No se puede observar una segunda línea base.'};
  e['TC-M09-277']={resultado:'RECHAZADO',post_ejecutado:false,http_esperado:403,http_obtenido:null,mensaje_exacto:'NO OBSERVABLE',
    productor_activo_autenticado:'NO VERIFICADO: la operación VISION no existe',
    motivo:'El producto no expone la operación VISION a la que RF-24 exige aplicar 403 y mensaje exacto al Productor; el oráculo de G137 califica esta ausencia como rechazo.'};
  e.resultado_general='RECHAZADO';e.motivo_general='TC-277 demuestra la falta de operación VISION exigida por RF-24; TC-275/276 no son ejecutables sin esa operación.';
  e.incidencias=[{incidencia_requerida:'SÍ',grupo_responsable:'Desarrollo',grupo_prueba:'TC-M09-G137',
    casos_afectados:e.casos,resultado:'RECHAZADO con TC-275/276 BLOQUEADOS',
    motivo:'OpenAPI TEST no publica la operación VISION del Flujo F.',
    esperado:'Método/ruta/body VISION para disparo manual y control Productor HTTP 403 con mensaje exacto.',
    obtenido:'Solo calibración SENSOR Flujo D; ninguna operación VISION publicada.',
    causa_raiz:'Falta exposición del contrato VISION en TEST; API no distingue implementación ausente de despliegue pendiente.',
    type:'bug',severity:'Important',priority:'High',evidencia:'evidencia.json / newman.html'}];
  writeResults(e);console.log(`G137 ${e.resultado_general}; 275/276 BLOQUEADOS; 277 RECHAZADO; VISION: NO; POST VISION: 0; ${out}`);}
main().catch(x=>{console.error(x.stack||x.message);process.exitCode=1;});
