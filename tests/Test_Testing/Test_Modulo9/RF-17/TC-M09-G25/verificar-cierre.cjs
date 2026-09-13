// Solo autenticacion y GET. Nunca crea, edita ni desactiva umbrales. Sin SQL.
const fs=require('fs'),path=require('path');
const {login,get,save,clean,CASOS}=require('./helpers.cjs');
const runId=process.env.G25_RUN_ID;
if(!runId)throw Error('G25_RUN_ID requerido');
const evid=path.join(__dirname,'RESULTADOS',runId);
(async()=>{
 const token=await login();
 const especies=(await get('/configuracion/especies',token)).items;
 const variables=(await get('/configuracion/variables-ambientales',token)).items;
 const perms=(await get('/sesiones/me/permisos',token)).permisos;
 const checks=[];
 for(const caso of CASOS){
  const files=fs.readdirSync(evid).filter(f=>f.startsWith(`newman-${caso}-intento`)&&f.endsWith('.json')).sort();
  const ultimo=JSON.parse(fs.readFileSync(path.join(evid,files[files.length-1]),'utf8'));
  const after=await get(`/configuracion/umbrales?id_especie=${ultimo.especie.id}`,token);
  const persisted=after.items.filter(u=>u.id_variable_ambiental===ultimo.variable.id);
  checks.push({caso,intentos:files.length,status:ultimo.status,errorCode:ultimo.errorCode,
   especieActiva:especies.find(s=>s.id_especie===ultimo.especie.id)?.es_activo??null,
   variableCatalogo:variables.find(v=>v.id_variable_ambiental===ultimo.variable.id)?.nombre??null,
   limitesFisicos:[ultimo.variable.fisicoMin,ultimo.variable.fisicoMax],
   permisosRF17:perms.filter(p=>p.id_recurso===20).map(p=>p.id_accion),
   getStatus:200,total:after.total,ids:after.items.map(u=>u.id_umbral_ambiental),
   persistenciaDelPayload:persisted.length});
 }
 save(runId,'verificacion-final-readonly.json',{checks,STOP_ALL:checks.some(c=>c.persistenciaDelPayload>0),soloLectura:true,sqlEjecutado:'ninguno'});

 // Escaneo de secretos sobre toda la evidencia textual generada por G25.
 // Se buscan VALORES de secreto, no vocabulario: el informe menciona los terminos
 // en prosa ("no se persistieron JWT ni cookies") y eso no es una fuga.
 const valores=[[/eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\./,'JWT'],
  [/Bearer\s+[A-Za-z0-9_.-]{12,}/,'Authorization con token'],
  [/set-cookie/i,'cabecera cookie'],
  [/(access|refresh)_token"?\s*[:=]\s*"?[A-Za-z0-9_.-]{12,}/i,'token en clave/valor'],
  [/(password|contrasena|contraseña)"?\s*[:=]\s*"?[^"\s,}]{4,}/i,'password en clave/valor'],
  [/postgres(ql)?:\/\//i,'connection string']];
 const vocabulario=['Authorization','Bearer ','access_token','refresh_token','password','cookie','jwt'];
 const secretos=[process.env.TEST_ADMIN_PASSWORD,process.env.TEST_ADMIN_EMAIL].filter(Boolean);
 const revisados=[];
 const walk=d=>fs.readdirSync(d,{withFileTypes:true}).forEach(e=>{
  const p=path.join(d,e.name);
  if(e.isDirectory())return walk(p);
  if(!/\.(html|json|md)$/i.test(e.name))return;
  const txt=fs.readFileSync(p,'utf8'),bajo=txt.toLowerCase();
  revisados.push({archivo:path.relative(evid,p).split(path.sep).join('/'),bytes:txt.length,
   secretos:valores.filter(([re])=>re.test(txt)).map(([,n])=>n),
   credencialesEnClaro:secretos.filter(s=>txt.includes(s)).length,
   mencionesDeVocabulario:vocabulario.filter(t=>bajo.includes(t.toLowerCase()))});
 });
 walk(evid);
 const sucios=revisados.filter(r=>r.secretos.length||r.credencialesEnClaro);
 save(runId,'seguridad-evidencias.json',{revisados,limpio:sucios.length===0,
  criterio:'Se marcan solo valores de secreto. Las menciones de vocabulario se listan aparte: aparecen como prosa en el informe y no constituyen fuga.',
  nota:'Reporter htmlextra con omitHeaders, showEnvironmentData=false, showGlobalData=false y skipEnvironmentVars=[token]; sanitizacion posterior de HTML y JSON. Token y contrasena solo en memoria del proceso.'});
 console.log('GET final:',checks.map(c=>`${c.caso} status ${c.getStatus} total ${c.total} persistencia ${c.persistenciaDelPayload}`).join(' | '));
 console.log('archivos revisados:',revisados.length,'| con valores de secreto:',sucios.length?sucios.map(s=>s.archivo).join(' ; '):'ninguno');
})().catch(e=>{console.log(clean(e.message));process.exitCode=1;});
