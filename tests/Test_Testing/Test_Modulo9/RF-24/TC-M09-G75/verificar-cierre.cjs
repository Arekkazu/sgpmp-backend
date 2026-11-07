// Solo autenticacion y GET. Nunca crea, edita ni elimina calibraciones. Sin SQL.
const fs=require('fs'),path=require('path');
const {login,get,save,dir,load,clean,ESTADO}=require('./helpers.cjs');
const runId=process.env.G75_RUN_ID;
if(!runId)throw Error('G75_RUN_ID requerido');
const evid=dir(runId);
(async()=>{
 const token=await login(process.env.QA_EMAIL,process.env.QA_PASSWORD);
 const estado=load(runId,ESTADO);
 const s=estado.plan.sensor.id;
 const historial=await get(`/configuracion/sensores/${s}/calibraciones`,token);
 const rangos=(await get('/configuracion/sensores/rangos-calibracion',token)).items;
 const asociaciones=(await get(`/configuracion/sensores/${s}/asociaciones`,token)).items;
 const sensores=(await get(`/configuracion/dispositivos-iot/${estado.plan.dispositivo.id}/sensores`,token)).items;
 const rango=rangos.find(r=>r.categoria===estado.plan.sensor.categoria);
 // La calibracion vigente para procesamiento futuro es la de fecha mas reciente.
 const masReciente=historial.items.reduce((a,x)=>new Date(x.fecha_calibracion)>new Date(a.fecha_calibracion)?x:a,historial.items[0]);
 save(runId,'verificacion-final-readonly.json',{
  sensor:sensores.find(x=>x.id_sensores===s)||null,
  asociacionVigente:asociaciones.filter(a=>a.fecha_finalizacion===null),
  rangoTecnicoActual:rango,
  rangoSinCambios:rango&&String(rango.valor_min)===String(estado.plan.rangoTecnico.min)&&String(rango.valor_max)===String(estado.plan.rangoTecnico.max),
  historialInicial:estado.historialInicial,
  historialFinal:{total:historial.total,items:historial.items.map(c=>({id_calibracion:c.id_calibracion,
   valor_referencia:c.valor_referencia,ganancia:c.ganancia,offset:c.offset,
   fecha_calibracion:c.fecha_calibracion,id_usuario:c.id_usuario,observaciones:c.observaciones}))},
  calibracionVigenteParaProcesamiento:masReciente?{id_calibracion:masReciente.id_calibracion,
   valor_referencia:masReciente.valor_referencia,fecha_calibracion:masReciente.fecha_calibracion,
   criterio:'fecha_calibracion mas reciente, que es el criterio del adaptador de telemetria'}:null,
  soloLectura:true,sqlEjecutado:'ninguno',
 });

 // Escaneo de secretos: se buscan VALORES, no vocabulario.
 const valores=[[/eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\./,'JWT'],
  [/Bearer\s+[A-Za-z0-9_.-]{12,}/,'Authorization con token'],
  [/set-cookie/i,'cabecera de cookie'],
  [/(access|refresh)_token"?\s*[:=]\s*"?[A-Za-z0-9_.-]{12,}/i,'token en clave/valor'],
  [/(password|contrasena|contraseña)"?\s*[:=]\s*"?[^"\s,}]{4,}/i,'credencial en clave/valor'],
  [/postgres(ql)?:\/\//i,'cadena de conexion']];
 // Solo la contrasena es secreto. El correo del actor lo publica el propio caso y
 // no figura en la lista de secretos del requisito: se cuenta aparte, informativo.
 const secretos=[process.env.QA_PASSWORD].filter(Boolean);
 const correo=process.env.QA_EMAIL;
 const revisados=[];
 const walk=d=>fs.readdirSync(d,{withFileTypes:true}).forEach(e=>{
  const p=path.join(d,e.name);
  if(e.isDirectory())return walk(p);
  if(!/\.(html|json|md)$/i.test(e.name))return;
  const txt=fs.readFileSync(p,'utf8');
  revisados.push({archivo:path.relative(evid,p).split(path.sep).join('/'),bytes:txt.length,
   secretos:valores.filter(([re])=>re.test(txt)).map(([,n])=>n),
   credencialesEnClaro:secretos.filter(x=>txt.includes(x)).length,
   mencionaCorreoDelActor:correo?txt.includes(correo):false});
 });
 walk(evid);
 const sucios=revisados.filter(r=>r.secretos.length||r.credencialesEnClaro);
 save(runId,'seguridad-evidencias.json',{revisados,limpio:sucios.length===0,
  criterio:'Se marcan solo valores de secreto: contrasenas, JWT, Authorization con token, cookies, tokens en pares clave-valor y cadenas de conexion. El correo del actor no es un secreto del requisito y se cuenta aparte; las menciones de vocabulario en prosa tampoco son fuga.',
  nota:'Reporter htmlextra con omitHeaders, showEnvironmentData=false, showGlobalData=false y skipEnvironmentVars=[token]; sanitizacion posterior de HTML y JSON.'});
 console.log('historial final del sensor',s,'total',historial.total,'ids',historial.items.map(c=>c.id_calibracion).join(','));
 console.log('vigente para procesamiento: #'+(masReciente?masReciente.id_calibracion:'-'),masReciente?masReciente.valor_referencia:'');
 console.log('rango tecnico sin cambios:',String(rango.valor_min)===String(estado.plan.rangoTecnico.min)&&String(rango.valor_max)===String(estado.plan.rangoTecnico.max));
 console.log('archivos revisados:',revisados.length,'| con valores de secreto:',sucios.length?sucios.map(x=>x.archivo).join(' ; '):'ninguno');
})().catch(e=>{console.log(clean(e.message));process.exitCode=1;});
