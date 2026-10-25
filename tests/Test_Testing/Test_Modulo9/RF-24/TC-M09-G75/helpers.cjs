const fs=require('fs'),path=require('path');
const BASE='https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const FRONT='https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const CASOS=['TC-M09-142','TC-M09-143','TC-M09-144-LOW','TC-M09-144-HIGH','TC-M09-145-EMPTY','TC-M09-145-NONNUMERIC'];
const ORIGINAL={'TC-M09-142':'TC-M09-142','TC-M09-143':'TC-M09-143','TC-M09-144-LOW':'TC-M09-144',
 'TC-M09-144-HIGH':'TC-M09-144','TC-M09-145-EMPTY':'TC-M09-145','TC-M09-145-NONNUMERIC':'TC-M09-145'};
const ARCHIVO={'TC-M09-142':'newman-TC-M09-142-intento1','TC-M09-143':'newman-TC-M09-143-intento1',
 'TC-M09-144-LOW':'newman-TC-M09-144-bajo-minimo','TC-M09-144-HIGH':'newman-TC-M09-144-sobre-maximo',
 'TC-M09-145-EMPTY':'newman-TC-M09-145-vacio','TC-M09-145-NONNUMERIC':'newman-TC-M09-145-no-numerico'};
const META={grupo:'TC-M09-G75',rf:'RF-24',cu:'CU-05',rama:'qa/juan-esteban-m09',
 frontendSHA:'966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56',backendSHA:'adc3932b9f0293a76ebec7e89ed877274791b6a1',base:BASE};
const ESTADO='estado-g75.json';

function settings(){
 const caso=process.env.G75_CASE,runId=process.env.G75_RUN_ID;
 if(!CASOS.includes(caso))throw Error('G75_CASE debe ser uno de: '+CASOS.join(' | '));
 if(!runId||!/^[\w-]+$/.test(runId))throw Error('G75_RUN_ID requerido');
 return {caso,runId,original:ORIGINAL[caso],archivo:ARCHIVO[caso]};
}
function clean(s){
 for(const secreto of [process.env.QA_PASSWORD,process.env.QA_EMAIL,process.env.QA_DISCOVERY_PASSWORD,process.env.QA_DISCOVERY_EMAIL].filter(Boolean))
  s=s.split(secreto).join('[REDACTED]');
 return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[JWT REDACTED]')
         .replace(/Bearer\s+[A-Za-z0-9_.-]+/g,'Bearer [REDACTED]');
}
function dir(runId,sub){const d=sub?path.join(__dirname,'RESULTADOS',runId,sub):path.join(__dirname,'RESULTADOS',runId);fs.mkdirSync(d,{recursive:true});return d;}
function save(runId,name,value){fs.writeFileSync(path.join(dir(runId),name),clean(JSON.stringify({...META,fecha:new Date().toISOString(),...value},null,2)));}
function load(runId,name){const p=path.join(dir(runId),name);return fs.existsSync(p)?JSON.parse(fs.readFileSync(p,'utf8')):null;}

async function get(endpoint,token){
 const r=await fetch(BASE+endpoint,{headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(25000)});
 if(r.status!==200)throw Error(`GET ${endpoint} HTTP ${r.status}`);
 return r.json();
}
async function login(email,password){
 const r=await fetch(BASE+'/sesiones/',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({correo_electronico:email,contrasena:password}),signal:AbortSignal.timeout(25000)});
 if(r.status!==200)throw Error(`ENVIRONMENT_ERROR login HTTP ${r.status}`);
 const j=await r.json();if(!j.token)throw Error('ENVIRONMENT_ERROR login sin token');
 return j.token;
}

// Los valores del caso se construyen como literales decimales exactos: nunca se
// derivan de aritmetica en coma flotante sobre el rango descubierto.
const PASO='0.0001'; // numeric(10,4): el menor incremento representable
function decMenos(valor,paso){return sumaDecimal(valor,'-'+paso);}
function decMas(valor,paso){return sumaDecimal(valor,paso);}
function sumaDecimal(a,b){
 const esc=v=>{const [e,d='']=String(v).replace('+','').split('.');return BigInt(e+(d+'0000').slice(0,4));};
 const total=esc(a)+esc(b);
 const neg=total<0n,abs=(neg?-total:total).toString().padStart(5,'0');
 return (neg?'-':'')+abs.slice(0,-4)+'.'+abs.slice(-4);
}

async function discover(tokenDescubrimiento){
 const rangos=(await get('/configuracion/sensores/rangos-calibracion',tokenDescubrimiento)).items;
 const porCategoria=Object.fromEntries(rangos.map(r=>[r.categoria,{min:String(r.valor_min),max:String(r.valor_max)}]));
 const dispositivos=(await get('/configuracion/dispositivos-iot',tokenDescubrimiento)).items.filter(d=>d.es_activo);
 // Se prefiere TEMPERATURA por fidelidad con el original; sirve cualquier categoria
 // con rango tecnico publicado y sensor con asociacion de area vigente.
 const preferencia=c=>c==='TEMPERATURA'?0:1;
 const candidatos=[];
 for(const d of dispositivos){
  let sensores;
  try{sensores=(await get(`/configuracion/dispositivos-iot/${d.id_dispositivo_iot}/sensores`,tokenDescubrimiento)).items;}catch{continue;}
  for(const s of (sensores||[]).filter(x=>x.es_activo&&porCategoria[x.categoria])){
   let asociaciones;
   try{asociaciones=(await get(`/configuracion/sensores/${s.id_sensores}/asociaciones`,tokenDescubrimiento)).items;}catch{continue;}
   // Asociacion vigente = sin fecha de finalizacion.
   const vigente=(asociaciones||[]).find(a=>a.fecha_finalizacion===null);
   if(!vigente||vigente.id_dispositivo_iot!==d.id_dispositivo_iot)continue;
   candidatos.push({dispositivo:d,sensor:s,asociacion:vigente,rango:porCategoria[s.categoria]});
  }
  if(candidatos.some(c=>preferencia(c.sensor.categoria)===0))break;
 }
 if(!candidatos.length)throw Error('BLOCKED sin sensor activo con asociacion de area vigente y rango tecnico publicado');
 candidatos.sort((a,b)=>preferencia(a.sensor.categoria)-preferencia(b.sensor.categoria)||a.sensor.id_sensores-b.sensor.id_sensores);
 const {dispositivo,sensor,asociacion,rango}=candidatos[0];
 const historial=await get(`/configuracion/sensores/${sensor.id_sensores}/calibraciones`,tokenDescubrimiento);
 return {
  dispositivo:{id:dispositivo.id_dispositivo_iot,serial:dispositivo.serial,es_activo:dispositivo.es_activo},
  sensor:{id:sensor.id_sensores,nombre:sensor.nombre,categoria:sensor.categoria,es_activo:sensor.es_activo,
          id_dispositivo_iot:sensor.id_dispositivo_iot},
  area:{id_infraestructura:asociacion.id_infraestructura,punto_instalacion:asociacion.punto_instalacion,
        fecha_finalizacion:asociacion.fecha_finalizacion},
  rangoTecnico:{categoria:sensor.categoria,min:rango.min,max:rango.max,fuente:'GET /configuracion/sensores/rangos-calibracion'},
  valores:{minExacto:rango.min,maxExacto:rango.max,bajoInvalido:decMenos(rango.min,PASO),altoInvalido:decMas(rango.max,PASO),paso:PASO},
  historial:{total:historial.total,ids:historial.items.map(c=>c.id_calibracion)},
 };
}

// Cuerpo JSON con literales exactos: '0.0000' no se degrada a 0 ni '45.0001' a un binario.
function construirCuerpo(caso,plan,runId){
 const p=plan;
 const valor={
  'TC-M09-142':p.valores.minExacto,
  'TC-M09-143':p.valores.maxExacto,
  'TC-M09-144-LOW':p.valores.bajoInvalido,
  'TC-M09-144-HIGH':p.valores.altoInvalido,
  'TC-M09-145-EMPTY':'""',
  'TC-M09-145-NONNUMERIC':'"abc"',
 }[caso];
 const observaciones=`QA ${ORIGINAL[caso]} G75 ${runId}`;
 const fecha=new Date().toISOString();
 // valorLiteral conserva el texto exacto tal como viaja en el JSON (sin comillas):
 // '0.0000' no se degrada a '0' ni '45.0001' a un binario de coma flotante.
 const valorLiteral=valor.startsWith('"')?JSON.parse(valor):valor;
 return {
  texto:`{"id_dispositivo_iot":${p.dispositivo.id},"id_infraestructura":${p.area.id_infraestructura},`
   +`"valor_referencia":${valor},"fecha_calibracion":"${fecha}",`
   +`"observaciones":${JSON.stringify(observaciones)}}`,
  objeto:{id_dispositivo_iot:p.dispositivo.id,id_infraestructura:p.area.id_infraestructura,
   valor_referencia:valorLiteral,fecha_calibracion:fecha,observaciones},
  valorEnviado:valorLiteral,tipoEnviado:valor.startsWith('"')?'string':'number',observaciones,
 };
}

module.exports={BASE,FRONT,META,CASOS,ORIGINAL,ARCHIVO,ESTADO,settings,clean,dir,save,load,get,login,discover,construirCuerpo,sumaDecimal};
