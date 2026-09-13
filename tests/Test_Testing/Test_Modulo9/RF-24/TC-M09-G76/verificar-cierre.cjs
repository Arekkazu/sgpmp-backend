// Solo autenticacion y GET. Nunca crea, edita ni elimina nada. Sin SQL.
const fs=require('fs'),path=require('path');
const {login,get,pedir,save,dir,load,clean,CASOS}=require('./helpers.cjs');
const runId=process.env.G76_RUN_ID;
if(!runId)throw Error('G76_RUN_ID requerido');
const evid=dir(runId);
(async()=>{
 const token=await login(process.env.QA_EMAIL,process.env.QA_PASSWORD);
 const checks=[];
 for(const caso of CASOS){
  const ev=load(runId,`newman-${caso}-intento1.json`);
  if(!ev)continue;
  const historial=await get(`/configuracion/sensores/${ev.sensor.id}/calibraciones`,token);
  const dispositivos=(await get('/configuracion/dispositivos-iot',token)).items;
  const d=dispositivos.find(x=>x.id_dispositivo_iot===ev.dispositivo.id);
  const asociaciones=(await get(`/configuracion/sensores/${ev.sensor.id}/asociaciones`,token)).items;
  const vigente=asociaciones.find(a=>a.fecha_finalizacion===null);
  const areaEnviada=await pedir(`/configuracion/infraestructuras/${ev.areaEnviada.id_infraestructura}`,token);
  checks.push({caso,status:ev.status,errorCode:ev.errorCode,
   dispositivoEstadoActual:d?d.es_activo:null,
   dispositivoSinCambios:d?d.es_activo===ev.dispositivo.es_activo:null,
   asociacionVigenteActual:vigente?vigente.id_infraestructura:null,
   asociacionSinCambios:vigente?vigente.id_infraestructura===ev.areaCorrecta.id_infraestructura:null,
   areaEnviadaSigueExistiendo:areaEnviada.status===200,
   historyBefore:ev.historyBefore.total,historyFinal:historial.total,
   idsFinales:historial.items.map(c=>c.id_calibracion),
   registrosNuevos:historial.items.map(c=>c.id_calibracion)
    .filter(id=>!ev.historyBefore.items.map(x=>x.id_calibracion).includes(id)),
   historicosIntactos:ev.historyBefore.items.every(prev=>{
    const a=historial.items.find(c=>c.id_calibracion===prev.id_calibracion);
    return a&&String(a.valor_referencia)===String(prev.valor_referencia)
     &&String(a.fecha_calibracion)===String(prev.fecha_calibracion);})});
 }
 save(runId,'verificacion-final-readonly.json',{checks,soloLectura:true,sqlEjecutado:'ninguno',
  STOP_ALL:checks.some(c=>c.registrosNuevos.length>0||c.historicosIntactos===false)});

 // Escaneo de secretos: valores, no vocabulario. El correo del actor lo publica el
 // propio caso y no figura entre los secretos del requisito.
 const valores=[[/eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\./,'JWT'],
  [/Bearer\s+[A-Za-z0-9_.-]{12,}/,'Authorization con token'],
  [/set-cookie/i,'cabecera de cookie'],
  [/(access|refresh)_token"?\s*[:=]\s*"?[A-Za-z0-9_.-]{12,}/i,'token en clave/valor'],
  [/(password|contrasena|contraseña)"?\s*[:=]\s*"?[^"\s,}]{4,}/i,'credencial en clave/valor'],
  [/postgres(ql)?:\/\//i,'cadena de conexion']];
 const secretos=[process.env.QA_PASSWORD].filter(Boolean);
 const revisados=[];
 const walk=d=>fs.readdirSync(d,{withFileTypes:true}).forEach(e=>{
  const p=path.join(d,e.name);
  if(e.isDirectory())return walk(p);
  if(!/\.(html|json|md)$/i.test(e.name))return;
  const txt=fs.readFileSync(p,'utf8');
  revisados.push({archivo:path.relative(evid,p).split(path.sep).join('/'),bytes:txt.length,
   secretos:valores.filter(([re])=>re.test(txt)).map(([,n])=>n),
   credencialesEnClaro:secretos.filter(x=>txt.includes(x)).length});
 });
 walk(evid);
 const sucios=revisados.filter(r=>r.secretos.length||r.credencialesEnClaro);
 save(runId,'seguridad-evidencias.json',{revisados,limpio:sucios.length===0,
  criterio:'Se marcan solo valores de secreto: contrasenas, JWT, Authorization con token, cookies, tokens en pares clave-valor y cadenas de conexion.',
  nota:'Reporter htmlextra con omitHeaders, showEnvironmentData=false, showGlobalData=false y skipEnvironmentVars=[token]; sanitizacion posterior de HTML y JSON.'});
 checks.forEach(c=>console.log(c.caso,'| status',c.status,c.errorCode,'| historial',c.historyBefore,'->',c.historyFinal,
  '| nuevos',c.registrosNuevos.length,'| historicos intactos',c.historicosIntactos,
  '| dispositivo sin cambios',c.dispositivoSinCambios,'| asociacion sin cambios',c.asociacionSinCambios,
  '| area enviada existe',c.areaEnviadaSigueExistiendo));
 console.log('archivos revisados:',revisados.length,'| con valores de secreto:',sucios.length?sucios.map(x=>x.archivo).join(' ; '):'ninguno');
})().catch(e=>{console.log(clean(e.message));process.exitCode=1;});
