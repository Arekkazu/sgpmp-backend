const fs=require('fs'),path=require('path');
const BASE='https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const FRONT='https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const CASOS=['TC-M09-146','TC-M09-147'];
const META={grupo:'TC-M09-G76',rf:'RF-24',cu:'CU-05',rol:'Ingeniero de campo',rama:'qa/juan-esteban-m09',
 frontendSHA:'966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56',backendSHA:'adc3932b9f0293a76ebec7e89ed877274791b6a1',base:BASE};

function settings(){
 const caso=process.env.G76_CASE,runId=process.env.G76_RUN_ID,intento=Number(process.env.G76_INTENTO||1);
 if(!CASOS.includes(caso))throw Error('G76_CASE debe ser TC-M09-146 o TC-M09-147');
 if(!runId||!/^[\w-]+$/.test(runId))throw Error('G76_RUN_ID requerido');
 if(![1,2].includes(intento))throw Error('G76_INTENTO solo puede ser 1 o 2: maximo dos POST por original');
 return {caso,runId,intento};
}
function clean(s){
 for(const secreto of [process.env.QA_PASSWORD,process.env.QA_DISCOVERY_PASSWORD].filter(Boolean))s=s.split(secreto).join('[REDACTED]');
 return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[JWT REDACTED]')
         .replace(/Bearer\s+[A-Za-z0-9_.-]+/g,'Bearer [REDACTED]');
}
function dir(runId,sub){const d=sub?path.join(__dirname,'RESULTADOS',runId,sub):path.join(__dirname,'RESULTADOS',runId);fs.mkdirSync(d,{recursive:true});return d;}
function save(runId,name,value){fs.writeFileSync(path.join(dir(runId),name),clean(JSON.stringify({...META,fecha:new Date().toISOString(),...value},null,2)));}
function load(runId,name){const p=path.join(dir(runId),name);return fs.existsSync(p)?JSON.parse(fs.readFileSync(p,'utf8')):null;}

async function pedir(endpoint,token){
 const r=await fetch(BASE+endpoint,{headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(25000)});
 let b;try{b=await r.json();}catch{b=null;}
 return {status:r.status,body:b};
}
async function get(endpoint,token){
 const r=await pedir(endpoint,token);
 if(r.status!==200)throw Error(`GET ${endpoint} HTTP ${r.status}`);
 return r.body;
}
async function login(email,password){
 const r=await fetch(BASE+'/sesiones/',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({correo_electronico:email,contrasena:password}),signal:AbortSignal.timeout(25000)});
 if(r.status!==200)throw Error(`ENVIRONMENT_ERROR login HTTP ${r.status}`);
 const j=await r.json();if(!j.token)throw Error('ENVIRONMENT_ERROR login sin token');
 return j.token;
}

// Valor claramente interior del rango tecnico: no se prueban fronteras aqui.
function valorInterior(min,max){
 const esc=v=>{const [e,d='']=String(v).split('.');return BigInt((e.startsWith('-')?e:e)+(d+'0000').slice(0,4));};
 const medio=(esc(min)+esc(max))/2n;
 const neg=medio<0n,abs=(neg?-medio:medio).toString().padStart(5,'0');
 return (neg?'-':'')+abs.slice(0,-4)+'.'+abs.slice(-4);
}

async function catalogoRangos(token){
 const items=(await get('/configuracion/sensores/rangos-calibracion',token)).items;
 return Object.fromEntries(items.map(r=>[r.categoria,{min:String(r.valor_min),max:String(r.valor_max)}]));
}

// Sensores del dispositivo con su asociacion vigente, historial de areas y calibraciones.
async function sensoresUtilizables(token,dispositivo,rangos){
 let sensores;
 try{sensores=(await get(`/configuracion/dispositivos-iot/${dispositivo.id_dispositivo_iot}/sensores`,token)).items;}catch{return [];}
 const salida=[];
 for(const s of (sensores||[]).filter(x=>x.es_activo&&rangos[x.categoria])){
  let asociaciones;
  try{asociaciones=(await get(`/configuracion/sensores/${s.id_sensores}/asociaciones`,token)).items;}catch{continue;}
  const vigente=(asociaciones||[]).find(a=>a.fecha_finalizacion===null);
  if(!vigente)continue;
  const historial=await get(`/configuracion/sensores/${s.id_sensores}/calibraciones`,token);
  salida.push({sensor:s,vigente,areasHistoricas:[...new Set((asociaciones||[]).map(a=>a.id_infraestructura))],
   rango:rangos[s.categoria],historial});
 }
 // Se prefiere un sensor con calibraciones previas: asi la comprobacion de
 // "historicos intactos" tras el rechazo es significativa y no vacia.
 return salida.sort((a,b)=>b.historial.total-a.historial.total);
}

async function discover(token,caso){
 const rangos=await catalogoRangos(token);
 const dispositivos=(await get('/configuracion/dispositivos-iot',token)).items;
 const quiereInactivo=caso==='TC-M09-146';
 const candidatos=dispositivos.filter(d=>d.es_activo!==quiereInactivo);
 for(const d of candidatos){
  const utilizables=await sensoresUtilizables(token,d,rangos);
  for(const u of utilizables){
   const base={
    dispositivo:{id:d.id_dispositivo_iot,serial:d.serial,es_activo:d.es_activo,id_infraestructura:d.id_infraestructura},
    sensor:{id:u.sensor.id_sensores,nombre:u.sensor.nombre,categoria:u.sensor.categoria,
            es_activo:u.sensor.es_activo,id_dispositivo_iot:u.sensor.id_dispositivo_iot},
    areaCorrecta:{id_infraestructura:u.vigente.id_infraestructura,punto_instalacion:u.vigente.punto_instalacion,
                  fecha_finalizacion:u.vigente.fecha_finalizacion},
    areasHistoricasDelSensor:u.areasHistoricas,
    rangoTecnico:{categoria:u.sensor.categoria,min:u.rango.min,max:u.rango.max,
                  fuente:'GET /configuracion/sensores/rangos-calibracion'},
    valor:valorInterior(u.rango.min,u.rango.max),
    historialPrevio:{total:u.historial.total,
     items:u.historial.items.map(c=>({id_calibracion:c.id_calibracion,valor_referencia:c.valor_referencia,
      fecha_calibracion:c.fecha_calibracion}))},
   };
   if(quiereInactivo){
    // TC-146: unica invalidez = dispositivo inactivo. Area enviada = la correcta.
    return {...base,caso,areaEnviada:{id_infraestructura:u.vigente.id_infraestructura,esLaCorrecta:true,existe:true},
     invalidezIntencional:`el dispositivo ${d.id_dispositivo_iot} existe pero es_activo=false`};
   }
   // TC-147: se busca un area REAL distinta y no asociada al sensor.
   const alternativa=await areaAlternativa(token,dispositivos,u);
   if(!alternativa)continue;
   return {...base,caso,areaEnviada:alternativa,
    invalidezIntencional:`el sensor ${u.sensor.id_sensores} no esta asociado al area ${alternativa.id_infraestructura}`};
  }
 }
 throw Error(quiereInactivo
  ? 'BLOCKED: no existe dispositivo inactivo apto en TEST'
  : 'BLOCKED: no existe area alternativa real para probar asociacion incorrecta');
}

// El area alternativa debe EXISTIR de verdad: se demuestra con GET por ID (200),
// no se inventa un identificador como 999, que devolveria 404 y probaria otra cosa.
async function areaAlternativa(token,dispositivos,utilizable){
 const correcta=utilizable.vigente.id_infraestructura;
 const posibles=[...new Set(dispositivos.map(d=>d.id_infraestructura).filter(Boolean))]
  .filter(id=>id!==correcta&&!utilizable.areasHistoricas.includes(id));
 for(const id of posibles){
  const r=await pedir(`/configuracion/infraestructuras/${id}`,token);
  if(r.status!==200)continue;
  return {id_infraestructura:id,esLaCorrecta:false,existe:true,
   evidenciaExistencia:{endpoint:`GET /configuracion/infraestructuras/${id}`,status:200,
    nombre:r.body?.nombre??null,es_activo:r.body?.es_activo??null},
   distintaDeLaCorrecta:true,sensorNoAsociada:true};
 }
 return null;
}

function construirCuerpo(caso,plan,runId){
 const observaciones=`QA ${caso} G76 ${runId}`;
 const fecha=new Date().toISOString();
 return {
  texto:`{"id_dispositivo_iot":${plan.dispositivo.id},"id_infraestructura":${plan.areaEnviada.id_infraestructura},`
   +`"valor_referencia":${plan.valor},"fecha_calibracion":"${fecha}","observaciones":${JSON.stringify(observaciones)}}`,
  objeto:{id_dispositivo_iot:plan.dispositivo.id,id_infraestructura:plan.areaEnviada.id_infraestructura,
   valor_referencia:plan.valor,fecha_calibracion:fecha,observaciones},
  observaciones,
 };
}

module.exports={BASE,FRONT,META,CASOS,settings,clean,dir,save,load,get,pedir,login,discover,construirCuerpo,valorInterior};
