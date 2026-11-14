// TC-M09-G132: TEST decisorio, cuatro POST máximos sin reintentos.
// Newman envía cada POST; los GET PRE/POST y STOP_ALL se controlan aquí.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

if (path.basename(__dirname) !== 'TC-M09-G132') throw new Error('Carpeta de ejecución incorrecta.');
const runId = process.env.G132_RUN_ID;
if (!/^run-\d{8}-\d{6}$/.test(runId || '')) throw new Error('G132_RUN_ID debe tener formato run-YYYYMMDD-HHMMSS.');
const base = (process.env.QA_BASE_URL || '').replace(/\/$/, '');
if (base !== 'https://api.inmero.co/back-sigab-test') throw new Error('El ambiente decisorio debe ser TEST.');
const email = process.env.QA_EMAIL;
const password = process.env.QA_PASSWORD;
if (!email || !password) throw new Error('Faltan QA_EMAIL o QA_PASSWORD.');
const out = path.join(__dirname, 'RESULTADOS', runId);
if (fs.existsSync(out)) throw new Error('RUN_ID ya existente: la evidencia no se sobrescribe.');
fs.mkdirSync(out, { recursive: true });

const variants = ['NaN', 'Infinity', '-Infinity'];
const evidence = {
  grupo: 'TC-M09-G132', casos: ['TC-M09-261','TC-M09-262'], run_id: runId,
  ambiente: 'TEST', base_url: base, prueba_local: false, post_planificados: 4,
  post_ejecutados: 0, git: {}, openapi: {}, actor: {}, fixture: {},
  'TC-M09-262': {}, 'TC-M09-261': Object.fromEntries(variants.map(v => [v, {}])),
  stop_all: false, resultado_general: '', motivo_general: '', incidencias: []
};
const secrets = [password, process.env.QA_ADMIN_PASSWORD].filter(Boolean);
function clean(value) {
  let s = String(value ?? '');
  for (const x of new Set(secrets)) s = s.split(x).join('[REDACTED]');
  return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]+/gi, 'Bearer [REDACTED]');
}
function save() { fs.writeFileSync(path.join(out,'evidencia.json'), clean(JSON.stringify(evidence,null,2)), 'utf8'); }
function esc(x) { return String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function git(args) {
  try {
    let d = __dirname;
    while (!fs.existsSync(path.join(d,'.git')) && path.dirname(d) !== d) d = path.dirname(d);
    return execFileSync('git', args, {cwd:d,encoding:'utf8'}).trim();
  } catch(e) { return `ERROR: ${clean(e.message)}`; }
}
function decimalParts(x) {
  if (typeof x !== 'string' && typeof x !== 'number') return null;
  if (typeof x === 'number' && !Number.isFinite(x)) return null;
  const m = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(String(x));
  if (!m) return null;
  const fraction = m[3] || '';
  return { n: (m[1] === '-' ? -1n : 1n) * BigInt(m[2] + fraction), d: 10n ** BigInt(fraction.length) };
}
function decimalEqual(a,b) {
  const x=decimalParts(a), y=decimalParts(b);
  return Boolean(x && y && x.n*y.d === y.n*x.d);
}
function sameHistory(a,b) { return a && b && a.total === b.total && JSON.stringify(a.ids) === JSON.stringify(b.ids); }
function summary(data) {
  if (!Number.isInteger(data?.total) || !Array.isArray(data.items)) throw new Error('Historial sin total/items verificables.');
  const ids=data.items.map(x=>x.id_calibracion).sort((a,b)=>a-b);
  if (ids.some(x=>!Number.isInteger(x))) throw new Error('Historial sin IDs íntegros.');
  return {total:data.total,ids};
}
async function request(method, route, token, body) {
  const r = await fetch(base+route, {method,headers:{
    ...(token?{Authorization:`Bearer ${token}`}:{ }),
    ...(body?{'Content-Type':'application/json'}:{})
  },body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(30000)});
  return {status:r.status,body:await r.json().catch(()=>null)};
}
async function login(user,pass) {
  const r=await request('POST','/sesiones/',null,{correo_electronico:user,contrasena:pass});
  if (r.status!==200 || !r.body?.token) throw new Error(`La cuenta ${user} no autentica (HTTP ${r.status}).`);
  return r.body.token;
}
async function get(route,primary,auxiliary) {
  const r=await request('GET',route,primary);
  if (r.status===200) return {body:r.body,fuente:'Ingeniero'};
  if (r.status===404 && auxiliary) {
    const a=await request('GET',route,auxiliary);
    if (a.status===200) return {body:a.body,fuente:'Administrador solo GET'};
    throw new Error(`GET ${route}: Ingeniero 404, Administrador ${a.status}.`);
  }
  throw new Error(`GET ${route}: Ingeniero HTTP ${r.status}${r.status===404?'; requiere actor auxiliar GET':''}.`);
}
async function history(sensor,token) {
  const r=await get(`/configuracion/sensores/${sensor}/calibraciones`,token,null);
  return {all:r.body,brief:summary(r.body)};
}
async function fixture(deviceId,sensorId,areaId,token,admin,ranges) {
  const d=(await get(`/configuracion/dispositivos-iot/${deviceId}`,token,admin)).body;
  const list=(await get(`/configuracion/dispositivos-iot/${deviceId}/sensores`,token,admin)).body;
  const s=list.items?.find(x=>x.id_sensores===sensorId && x.id_dispositivo_iot===deviceId);
  const associations=(await get(`/configuracion/sensores/${sensorId}/asociaciones`,token,admin)).body;
  const a=associations.items?.find(x=>x.id_sensor===sensorId && x.id_dispositivo_iot===deviceId &&
    x.id_infraestructura===areaId && x.tiene_estado===true && x.fecha_finalizacion===null);
  const area=(await get(`/configuracion/infraestructuras/${areaId}`,token,admin)).body;
  const range=ranges.items?.find(x=>x.categoria===s?.categoria);
  if (d.es_activo!==true || s?.es_activo!==true || !a || area.es_activo!==true || !range ||
    Number(range.valor_min)>22.1234 || 22.1234>Number(range.valor_max)) return null;
  return {sensor:sensorId,dispositivo:deviceId,area:areaId,categoria:s.categoria,
    rango:{min:range.valor_min,max:range.valor_max},asociacion:a.id_sensores_area_asociada,
    activo:{dispositivo:d.es_activo,sensor:s.es_activo,area:area.es_activo},fuente:'GET en TEST'};
}
async function findFixture(token,admin,ranges) {
  let preferred=null, preferredError=null;
  try { preferred=await fixture(3,6,3,token,admin,ranges); }
  catch(e) { preferredError=clean(e.message); }
  evidence.fixture.preferido={ids:'sensor 6 / dispositivo 3 / área 3',error:preferredError,valido:Boolean(preferred)};
  if (preferred) return preferred;
  const devices=(await get('/configuracion/dispositivos-iot',token,admin)).body.items || [];
  for (const d of devices.filter(x=>x.es_activo===true)) {
    let sensors;
    try { sensors=(await get(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`,token,admin)).body.items||[]; }
    catch { continue; }
    for (const s of sensors.filter(x=>x.es_activo===true)) {
      let associations;
      try { associations=(await get(`/configuracion/sensores/${s.id_sensores}/asociaciones`,token,admin)).body.items||[]; }
      catch { continue; }
      for (const a of associations.filter(x=>x.tiene_estado===true && x.fecha_finalizacion===null)) {
        try {
          const f=await fixture(d.id_dispositivo_iot,s.id_sensores,a.id_infraestructura,token,admin,ranges);
          if (f) return f;
        } catch { /* siguiente candidato */ }
      }
    }
  }
  throw new Error(`No existe fixture verificable por GET que admita 22.1234. Preferido: ${preferredError || 'no válido'}.`);
}
function newmanOnce(vars) {
  let newman;
  try { newman=require('newman'); }
  catch { newman=require(path.join(path.dirname(process.execPath),'node_modules','newman')); }
  return new Promise((resolve,reject)=>newman.run({
    collection:path.join(__dirname,'TC-M09-G132.postman_collection.json'),reporters:['cli'],
    envVar:Object.entries(vars).map(([key,value])=>({key,value:String(value)})),timeoutRequest:30000
  },(err,run)=>{
    const ex=run?.run?.executions?.[0];
    if (err || !ex?.response) return reject(new Error(`Newman sin respuesta HTTP: ${clean(err?.message||'desconocido')}`));
    let body=null;
    try { body=JSON.parse(ex.response.stream.toString('utf8')); } catch { /* cuerpo no JSON */ }
    resolve({status:ex.response.code,body,assertions:ex.assertions?.map(a=>({name:a.assertion,error:a.error?.message||null}))||[]});
  }));
}
function expectedMessage(v) { return `Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada '${v}'.`; }
function markRemaining(reason,status='NO EJECUTADO') {
  for (const v of variants) if (!evidence['TC-M09-261'][v].resultado)
    Object.assign(evidence['TC-M09-261'][v],{resultado:status,motivo:reason});
}
function classify262(r) {
  if (!r.http) return ['BLOQUEADO / NO VERIFICABLE','Newman no obtuvo respuesta verificable del POST.'];
  if (!(r.http>=200 && r.http<300)) return ['RECHAZADO',`Con fixture válido, TEST respondió HTTP ${r.http} en lugar de 2xx.`];
  if (!Number.isInteger(r.id_calibracion)) return ['RECHAZADO','La respuesta 2xx no devolvió un id_calibracion íntegro.'];
  if (!decimalEqual(r.valor_respuesta,'22.1234')) return ['RECHAZADO',`La respuesta del ID ${r.id_calibracion} representó ${JSON.stringify(r.valor_respuesta)}, no 22.1234.`];
  if (!r.post) return ['BLOQUEADO / NO VERIFICABLE','No se pudo consultar el historial POST para verificar persistencia.'];
  if (!r.post.ids.includes(r.id_calibracion) || !r.registro_encontrado) return ['RECHAZADO',`El historial POST no contiene el ID ${r.id_calibracion} devuelto.`];
  if (!decimalEqual(r.valor_recuperado,'22.1234')) return ['RECHAZADO',`El GET del ID ${r.id_calibracion} representó ${JSON.stringify(r.valor_recuperado)}, no 22.1234.`];
  return ['APROBADO',`HTTP ${r.http}, ID ${r.id_calibracion}; respuesta y GET conservan exactamente 22.1234.`];
}
function classify261(r) {
  const failures=[];
  if (r.http!==400) failures.push(`HTTP ${r.http??'no verificable'} en vez de 400`);
  if (r.mensaje!==r.mensaje_esperado) failures.push(`mensaje ${JSON.stringify(r.mensaje)} distinto del texto de formato exigido`);
  if (r.id_calibracion!==null) failures.push(`respuesta contiene id_calibracion=${r.id_calibracion}`);
  if (!r.post) failures.push('historial POST no verificable');
  else if (!sameHistory(r.pre,r.post)) failures.push(`historial alterado; IDs nuevos ${r.ids_creados.join(', ')||'ninguno'}`);
  return failures.length ? ['RECHAZADO',failures.join('; ')+'.'] :
    ['APROBADO','HTTP 400, mensaje exacto, sin id_calibracion y total/IDs sin cambios.'];
}
function render() {
  const precision=evidence['TC-M09-262'];
  const rows=[['TC-M09-262','22.1234',precision],...variants.map(v=>['TC-M09-261',v,evidence['TC-M09-261'][v]])]
    .map(([c,v,r])=>`| ${c} | ${v} | ${r.resultado} | ${r.motivo} |`).join('\n');
  const details=variants.map(v=>{
    const r=evidence['TC-M09-261'][v];
    return `### ${v} — ${r.resultado}\n\n**Esperado:** HTTP 400; mensaje exacto «${expectedMessage(v)}»; respuesta sin id_calibracion; total e IDs del historial sin cambios.\n\n**Obtenido:** HTTP ${r.http??'sin POST'}; mensaje ${JSON.stringify(r.mensaje??null)}; id_calibracion ${JSON.stringify(r.id_calibracion??null)}.\n\n**Historial:** PRE ${JSON.stringify(r.pre??null)}; POST ${JSON.stringify(r.post??null)}.\n\n**Motivo:** ${r.motivo}\n`;
  }).join('\n');
  const incidents=evidence.incidencias.length?evidence.incidencias.map(i=>
    `### ${i.titulo}\n\n**INCIDENCIA REQUERIDA:** SÍ  \n**Grupo responsable:** ${i.grupo_responsable}  \n**Grupo de prueba:** TC-M09-G132  \n**Casos afectados:** ${i.casos.join(', ')}  \n**Resultado:** RECHAZADO  \n**Motivo:** ${i.motivo}  \n**Esperado:** ${i.esperado}  \n**Obtenido:** ${i.obtenido}  \n**Causa raíz:** ${i.causa_raiz}  \n**Type:** ${i.type}  \n**Severity:** ${i.severity}  \n**Priority:** ${i.priority}  \n**Evidencia:** evidencia.json / newman.html`)
    .join('\n\n'):'INCIDENCIA REQUERIDA: NO.';
  const md=`# TC-M09-G132 — Resultado\n\n## Decisión general\n\n**${evidence.resultado_general}.** ${evidence.motivo_general}\n\n| Caso | Variante | Resultado | Motivo |\n|---|---|---|---|\n${rows}\n\n## Entorno / actor / fixture\n\nTEST: ${base}. Prueba local: NO. RUN_ID: ${runId}. Rama: ${evidence.git.rama}. HEAD: ${evidence.git.head}. Actor: ${JSON.stringify(evidence.actor)}.\n\nOpenAPI: ${JSON.stringify(evidence.openapi)}.\n\nFixture validado por GET: ${JSON.stringify(evidence.fixture)}. La cuenta Administrador, si se utilizó, solo efectuó GET de discovery; los POST fueron del Ingeniero.\n\n## TC-M09-262 — precisión\n\n**Esperado:** HTTP 2xx, id_calibracion y valor decimal exacto 22.1234 tanto en respuesta como en GET de ese ID. JSON puede representar el decimal como número o string.\n\n**Obtenido:** HTTP ${precision.http??'sin POST'}; id_calibracion ${JSON.stringify(precision.id_calibracion??null)}; valor respuesta ${JSON.stringify(precision.valor_respuesta??null)}; valor GET ${JSON.stringify(precision.valor_recuperado??null)}; comparación decimal exacta: respuesta ${precision.respuesta_exacta??'no verificable'}, GET ${precision.get_exacto??'no verificable'}.\n\n**Historial:** PRE ${JSON.stringify(precision.pre??null)}; POST ${JSON.stringify(precision.post??null)}. Correlación por ID: ${precision.registro_encontrado?'sí':'no verificable'}.\n\n**Resultado:** ${precision.resultado}. **Motivo:** ${precision.motivo}\n\n## TC-M09-261 — valores especiales\n\n${details}\n## STOP_ALL\n\n${evidence.stop_all?'SÍ: '+evidence.motivo_stop_all:'NO'}. POST planificados: 4. POST ejecutados: ${evidence.post_ejecutados}. No hubo reintentos automáticos ni borrado de calibraciones.\n\n## Incidencias\n\n${incidents}\n\n## Conclusión\n\n${evidence.motivo_general}\n`;
  fs.writeFileSync(path.join(out,'TC-M09-G132_resultado.md'),clean(md),'utf8');
  const trs=[['TC-M09-262','22.1234',precision],...variants.map(v=>['TC-M09-261',v,evidence['TC-M09-261'][v]])]
    .map(([c,v,r])=>`<tr><td>${esc(c)}</td><td>${esc(v)}</td><td>${esc(r.resultado)}</td><td>${esc(r.http??'—')}</td><td>${esc(r.motivo)}</td></tr>`).join('');
  fs.writeFileSync(path.join(out,'newman.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman ${esc(runId)}</title><style>body{font:16px Arial,sans-serif;max-width:1100px;margin:40px auto;color:#182331}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbc5ce;padding:9px;text-align:left}th{background:#e9eef2}</style><h1>Newman — TC-M09-G132</h1><p>RUN ${esc(runId)} · TEST · ${esc(evidence.resultado_general)} · ${evidence.post_ejecutados}/4 POST</p><table><thead><tr><th>Caso</th><th>Variante</th><th>Resultado</th><th>HTTP</th><th>Motivo</th></tr></thead><tbody>${trs}</tbody></table><p>${esc(evidence.motivo_general)}</p><p>Detalle estructurado: evidencia.json. Informe: TC-M09-G132_resultado.md.</p></html>`,'utf8');
}
function finalize() {
  const p=evidence['TC-M09-262'];
  const values=variants.map(v=>evidence['TC-M09-261'][v].resultado);
  evidence['TC-M09-261'].resultado=values.every(x=>x==='APROBADO')?'APROBADO':
    values.includes('RECHAZADO')?'RECHAZADO':'BLOQUEADO / NO VERIFICABLE';
  evidence.resultado_general=p.resultado==='APROBADO' && evidence['TC-M09-261'].resultado==='APROBADO'?'APROBADO':
    p.resultado==='RECHAZADO' || evidence['TC-M09-261'].resultado==='RECHAZADO'?'RECHAZADO':'BLOQUEADO / NO VERIFICABLE';
  if (!evidence.motivo_general) evidence.motivo_general=evidence.resultado_general==='APROBADO'
    ?'La precisión 22.1234 se conservó y las tres entradas especiales cumplieron el rechazo exacto sin persistencia.'
    :evidence.resultado_general==='RECHAZADO'
      ?`El oráculo incumplido se detalla en ${[p.resultado==='RECHAZADO'?'TC-M09-262':null,...variants.filter(v=>evidence['TC-M09-261'][v].resultado==='RECHAZADO').map(v=>`TC-M09-261/${v}`)].filter(Boolean).join(', ')}.`
      :'Una precondición o respuesta no verificable impidió cerrar todos los oráculos.';
  save();render();
  console.log(`TC-M09-G132 → ${evidence.resultado_general}; POST ejecutados: ${evidence.post_ejecutados}; STOP_ALL: ${evidence.stop_all?'SÍ':'NO'}`);
  console.log(path.join(out,'TC-M09-G132_resultado.md'));
}
async function main() {
  evidence.git={rama:git(['branch','--show-current']),status_short:git(['status','--short']),
    diff_stat:git(['diff','--stat']),diff_cached_stat:git(['diff','--cached','--stat']),
    head:git(['rev-parse','HEAD']),origin_test:git(['rev-parse','origin/test']),
    divergencia:git(['rev-list','--left-right','--count','HEAD...origin/test'])};
  if (evidence.git.rama!=='qa/juan-esteban-rf24-v2') throw new Error('La rama QA requerida no está activa.');
  const o=await request('GET','/openapi.json');
  if (o.status!==200) throw new Error(`OpenAPI TEST respondió HTTP ${o.status}.`);
  const schema=o.body.components?.schemas?.RegistrarCalibracionDTO;
  evidence.openapi={fuente:base+'/openapi.json',endpoints:{
    calibrar:Boolean(o.body.paths?.['/configuracion/sensores/{id_sensor}/calibrar']?.post),
    calibraciones:Boolean(o.body.paths?.['/configuracion/sensores/{id_sensor}/calibraciones']?.get)},
    valor_referencia:schema?.properties?.valor_referencia||null,
    modo_calibracion_declarado:Boolean(schema?.properties?.modo_calibracion)};
  if (!evidence.openapi.endpoints.calibrar || !evidence.openapi.endpoints.calibraciones)
    throw new Error('Endpoint de calibración o historial ausente en OpenAPI TEST.');
  const token=await login(email,password);
  const identity=(await get('/usuarios/me',token,null)).body;
  const permissions=(await get('/sesiones/me/permisos',token,null)).body.permisos||[];
  evidence.actor={id_usuario:identity.id_usuario,correo:identity.correo_electronico,rol:identity.nombre_rol,
    estado:identity.estado_cuenta,permisos_calibracion:permissions.filter(x=>x.id_recurso===12).map(x=>x.id_accion),
    actor_auxiliar_get:null,intentos_admin:[]};
  if (identity.correo_electronico!==email || identity.nombre_rol!=='Ingeniero de Campo' || identity.estado_cuenta!=='Activo' ||
    !evidence.actor.permisos_calibracion.includes(1) || !evidence.actor.permisos_calibracion.includes(2))
    throw new Error('Identidad, estado o permisos del Ingeniero no cumplen las precondiciones.');
  const ranges=(await get('/configuracion/sensores/rangos-calibracion',token,null)).body;
  let fixtureData;
  try { fixtureData=await findFixture(token,null,ranges); }
  catch(e) {
    evidence.fixture.error_ingeniero=clean(e.message);
    let adminToken=null;
    if (process.env.QA_ADMIN_PASSWORD) {
      for (const candidate of ['admin.dev@gmail.com','administador.dev@gmail.com']) {
        try {
          const t=await login(candidate,process.env.QA_ADMIN_PASSWORD);
          const probe=await request('GET','/configuracion/dispositivos-iot/3',t);
          evidence.actor.intentos_admin.push({correo:candidate,login:200,get_dispositivo_3:probe.status});
          if (probe.status===200) {adminToken=t;evidence.actor.actor_auxiliar_get=candidate;break;}
        } catch(err) {evidence.actor.intentos_admin.push({correo:candidate,resultado:clean(err.message)});}
      }
    }
    if (!adminToken) throw new Error(`No se pudo validar fixture por API; ${clean(e.message)}; ningún Administrador de GET disponible.`);
    fixtureData=await findFixture(token,adminToken,ranges);
  }
  evidence.fixture={...evidence.fixture,...fixtureData};
  const sensor=fixtureData.sensor;
  const steps=[{kind:'precision',label:'TC-M09-262',value:22.1234},...variants.map(v=>({kind:'special',label:v,value:v}))];
  for (const step of steps) {
    const r=step.kind==='precision'?evidence['TC-M09-262']:evidence['TC-M09-261'][step.label];
    const pre=await history(sensor,token);
    r.pre=pre.brief;
    const body={modo_calibracion:'SENSOR',id_dispositivo_iot:fixtureData.dispositivo,
      id_infraestructura:fixtureData.area,valor_referencia:step.value,
      observaciones:step.kind==='precision'?'QA TC-M09-262':'QA TC-M09-261',
      fecha_calibracion:new Date().toISOString()};
    r.request={ruta:`/configuracion/sensores/${sensor}/calibrar`,body};
    if (step.kind==='special') r.mensaje_esperado=expectedMessage(step.value);
    evidence.post_ejecutados+=1;
    try {
      const response=await newmanOnce({base_url:base,sensor_id:sensor,token,
        body_json:JSON.stringify(body),expected_kind:step.kind,
        expected_message:step.kind==='special'?r.mensaje_esperado:''});
      r.http=response.status;r.mensaje=clean(response.body?.message??response.body?.detail??'');
      r.id_calibracion=response.body?.id_calibracion??null;
      r.valor_respuesta=response.body?.valor_referencia??null;
      r.assertions_newman=response.assertions;
    } catch(err) {r.error_ejecucion=clean(err.message);}
    try {
      const after=await history(sensor,token);
      r.post=after.brief;
      if (step.kind==='precision' && Number.isInteger(r.id_calibracion)) {
        const row=after.all.items.find(x=>x.id_calibracion===r.id_calibracion);
        r.registro_encontrado=Boolean(row);r.valor_recuperado=row?.valor_referencia??null;
      }
    } catch(err) {r.error_historial_post=clean(err.message);}
    r.ids_creados=r.post?r.post.ids.filter(x=>!r.pre.ids.includes(x)):[];
    if (step.kind==='precision') {
      r.respuesta_exacta=decimalEqual(r.valor_respuesta,'22.1234');
      r.get_exacto=decimalEqual(r.valor_recuperado,'22.1234');
      [r.resultado,r.motivo]=classify262(r);
      if (!r.post || !r.http) {
        evidence.stop_all=true;evidence.motivo_stop_all='TC-M09-262 quedó ambiguo; no se arriesgan más POST.';
        markRemaining(`STOP_ALL: ${evidence.motivo_stop_all}`);break;
      }
    } else {
      [r.resultado,r.motivo]=classify261(r);
      if (!r.post || r.ids_creados.length || !sameHistory(r.pre,r.post) || !r.http) {
        evidence.stop_all=true;
        evidence.motivo_stop_all=`${step.label}: ${r.post?'historial alterado':'historial POST no verificable'}; IDs nuevos ${r.ids_creados.join(', ')||'no verificables'}.`;
        markRemaining(`STOP_ALL: ${evidence.motivo_stop_all}`);break;
      }
    }
  }
  const p=evidence['TC-M09-262'];
  if (p.resultado==='RECHAZADO') evidence.incidencias.push({
    titulo:'Precisión de valor_referencia 22.1234 no conservada',grupo_responsable:'Por determinar',casos:['TC-M09-262'],
    motivo:p.motivo,esperado:'2xx, id_calibracion y 22.1234 exacto en respuesta y GET por ese ID.',
    obtenido:`HTTP ${p.http}; id ${p.id_calibracion}; respuesta ${JSON.stringify(p.valor_respuesta)}; GET ${JSON.stringify(p.valor_recuperado)}.`,
    causa_raiz:'Por determinar; distinguir transformación de aplicación de tipo de columna desplegado antes de asignar Desarrollo o DBA.',
    type:'bug',severity:'Important',priority:'High'});
  const failed=variants.filter(v=>evidence['TC-M09-261'][v].resultado==='RECHAZADO');
  if (failed.length) evidence.incidencias.push({
    titulo:'Valores especiales no rechazados como formato decimal inválido',grupo_responsable:'Desarrollo',casos:['TC-M09-261'],
    motivo:failed.map(v=>`${v}: ${evidence['TC-M09-261'][v].motivo}`).join(' '),
    esperado:failed.map(v=>`${v}: 400, mensaje exacto y sin persistencia.`).join(' '),
    obtenido:failed.map(v=>`${v}: HTTP ${evidence['TC-M09-261'][v].http}, mensaje ${JSON.stringify(evidence['TC-M09-261'][v].mensaje)}, PRE ${JSON.stringify(evidence['TC-M09-261'][v].pre)}, POST ${JSON.stringify(evidence['TC-M09-261'][v].post)}.`).join(' '),
    causa_raiz:'Validación o manejo de valores no finitos en la aplicación; mecanismo exacto del despliegue por confirmar.',
    type:'bug',severity:'Important',priority:'High'});
}
main().catch(err=>{
  evidence.motivo_general=`BLOQUEADO: ${clean(err.message)}`;
  if (!evidence['TC-M09-262'].resultado) Object.assign(evidence['TC-M09-262'],{resultado:'BLOQUEADO / NO VERIFICABLE',motivo:evidence.motivo_general});
  markRemaining(evidence.motivo_general,'BLOQUEADO / NO VERIFICABLE');
}).finally(finalize);
