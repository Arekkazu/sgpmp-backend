// Solo autenticacion y GET. Nunca crea, edita ni desactiva datos. Sin SQL.
const fs=require('fs'),path=require('path');
const {login,get,save,clean}=require('./helpers.cjs');
const runId=process.env.G26_RUN_ID;
if(!runId)throw Error('G26_RUN_ID requerido');
const evid=path.join(__dirname,'RESULTADOS',runId);
(async()=>{
 const token=await login();
 const cat=await get('/configuracion/especies',token);
 const variables=(await get('/configuracion/variables-ambientales',token)).items;
 const perms=(await get('/sesiones/me/permisos',token)).permisos;
 const checks=[];
 for(const f of fs.readdirSync(evid).filter(f=>/^newman-TC-M09-\d+-.+\.json$/.test(f)).sort()){
  const j=JSON.parse(fs.readFileSync(path.join(evid,f),'utf8'));
  const p=j.payloadEnviado;
  const after=await get(`/configuracion/umbrales?id_especie=${p.id_especie}`,token).catch(()=>null);
  const deLaCombinacion=after?after.items.filter(u=>u.id_variable_ambiental===p.id_variable_ambiental):[];
  checks.push({archivo:f,caso:j.caso,variante:j.variante,status:j.status,errorCode:j.errorCode,
   especieEnCatalogo:cat.items.some(s=>s.id_especie===p.id_especie),
   especieActiva:cat.items.find(s=>s.id_especie===p.id_especie)?.es_activo??null,
   variableEnCatalogo:variables.some(v=>v.id_variable_ambiental===p.id_variable_ambiental),
   permisosRF17:perms.filter(x=>x.id_recurso===20).map(x=>x.id_accion),
   getStatus:after?200:'no consultado',totalUmbrales:after?after.total:null,
   ids:after?after.items.map(u=>u.id_umbral_ambiental):null,
   umbralesDeLaCombinacion:deLaCombinacion.map(u=>({id:u.id_umbral_ambiental,es_activo:u.es_activo}))});
 }
 save(runId,'verificacion-final-readonly.json',{
  catalogoEspecies:{total:cat.total,ids:cat.items.map(s=>s.id_especie).sort((a,b)=>a-b),inactivas:cat.items.filter(s=>!s.es_activo).map(s=>s.id_especie)},
  catalogoVariables:{total:variables.length,ids:variables.map(v=>v.id_variable_ambiental).sort((a,b)=>a-b)},
  checks,soloLectura:true,sqlEjecutado:'ninguno'});

 // Escaneo de secretos: se buscan VALORES, no vocabulario. El informe menciona los
 // terminos en prosa al enumerar lo que no se persistio y eso no es una fuga.
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
 console.log('GET final:',checks.map(c=>`${c.caso}/${c.variante} combinacion=${c.umbralesDeLaCombinacion.length} total=${c.totalUmbrales}`).join(' | '));
 console.log('catalogos -> especies',cat.total,'| variables',variables.length);
 console.log('archivos revisados:',revisados.length,'| con valores de secreto:',sucios.length?sucios.map(s=>s.archivo).join(' ; '):'ninguno');
})().catch(e=>{console.log(clean(e.message));process.exitCode=1;});
