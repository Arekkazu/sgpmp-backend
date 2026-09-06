const fs=require('fs'),path=require('path');
const BASE='https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const FRONT='https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const CASOS=['TC-M09-55','TC-M09-56'];
const META={grupo:'TC-M09-G25',rf:'RF-17',cu:'CU-03',rol:'Administrador',rama:'qa/juan-esteban-m09',
 frontendSHA:'966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56',backendSHA:'adc3932b9f0293a76ebec7e89ed877274791b6a1',base:BASE};

// Reglas fisicas que RF-17 declara para cada original. Si el catalogo real de TEST
// las contradice, se detiene antes del POST (CATALOG_REQUIREMENT_MISMATCH).
const REGLAS={
 'TC-M09-55':{variable:/humedad/i,unidadEsperada:'%',fisicoMin:0,fisicoMax:100,valor_min:50,valor_max:120,
  regla:'Humedad <= 100 %',corte:[70,90]},
 'TC-M09-56':{variable:/\bph\b/i,unidadEsperada:'pH',fisicoMin:0,fisicoMax:14,valor_min:6.5,valor_max:18,
  regla:'0 <= pH <= 14',corte:[10,14]},
};

function settings(){
 const caso=process.env.G25_CASE,runId=process.env.G25_RUN_ID,intento=Number(process.env.G25_INTENTO||1);
 if(!CASOS.includes(caso))throw Error('G25_CASE debe ser TC-M09-55 o TC-M09-56');
 if(!runId||!/^[\w-]+$/.test(runId))throw Error('G25_RUN_ID requerido');
 if(![1,2].includes(intento))throw Error('G25_INTENTO solo puede ser 1 o 2: maximo dos POST por original');
 return {caso,runId,intento};
}
function clean(s){for(const secret of [process.env.TEST_ADMIN_PASSWORD,process.env.TEST_ADMIN_EMAIL].filter(Boolean))s=s.split(secret).join('[REDACTED]');
 return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[JWT REDACTED]').replace(/Bearer\s+[A-Za-z0-9_.-]+/g,'Bearer [REDACTED]');}
function dir(runId,sub){const d=sub?path.join(__dirname,'RESULTADOS',runId,sub):path.join(__dirname,'RESULTADOS',runId);fs.mkdirSync(d,{recursive:true});return d;}
function save(runId,name,value){fs.writeFileSync(path.join(dir(runId),name),clean(JSON.stringify({...META,fecha:new Date().toISOString(),...value},null,2)));}
async function get(endpoint,token){const r=await fetch(BASE+endpoint,{headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(25000)});if(r.status!==200)throw Error(`GET ${endpoint} HTTP ${r.status}`);return r.json();}
async function login(){const r=await fetch(BASE+'/sesiones/',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({correo_electronico:process.env.TEST_ADMIN_EMAIL,contrasena:process.env.TEST_ADMIN_PASSWORD}),signal:AbortSignal.timeout(25000)});
 if(r.status!==200)throw Error(`ENVIRONMENT_ERROR login HTTP ${r.status}`);const j=await r.json();if(!j.token)throw Error('ENVIRONMENT_ERROR login sin token');return j.token;}

async function discover(token,caso){
 const regla=REGLAS[caso];
 const perms=(await get('/sesiones/me/permisos',token)).permisos;
 if(![1,2].every(a=>perms.some(p=>p.id_recurso===20&&p.id_accion===a)))throw Error('BLOCKED permiso RF17 ausente');
 const especies=(await get('/configuracion/especies',token)).items;
 const activas=especies.filter(s=>s.es_activo);
 if(!activas.length)throw Error('BLOCKED sin especies activas');
 const variables=(await get('/configuracion/variables-ambientales',token)).items;
 const candidatas=variables.filter(v=>regla.variable.test(v.nombre));
 if(candidatas.length!==1)throw Error(`BLOCKED variable de ${caso} no identificable de forma inequivoca (${candidatas.length} coincidencias)`);
 const v=candidatas[0],lo=Number(v.valor_fisico_min),hi=Number(v.valor_fisico_max);
 // El catalogo real debe coincidir con el limite fisico que declara RF-17.
 if(lo!==regla.fisicoMin||hi!==regla.fisicoMax)
  throw Error(`CATALOG_REQUIREMENT_MISMATCH ${v.nombre}: RF-17 declara [${regla.fisicoMin}, ${regla.fisicoMax}] y TEST expone [${lo}, ${hi}]`);
 if(!(regla.valor_min>=lo&&regla.valor_min<regla.valor_max&&regla.valor_max>hi))
  throw Error('Payload QA incoherente con el limite fisico descubierto');
 // Combinacion libre: ocupada aunque el umbral este inactivo.
 for(const s of activas){
  const before=(await get(`/configuracion/umbrales?id_especie=${s.id_especie}`,token)).items;
  if(before.some(u=>u.id_variable_ambiental===v.id_variable_ambiental))continue;
  const [c1,c2]=regla.corte;
  return {caso,regla:regla.regla,
   especie:{id:s.id_especie,nombre:s.nombre,es_activo:s.es_activo},
   variable:{id:v.id_variable_ambiental,nombre:v.nombre,unidad:v.unidad,catalogoActivo:true,fisicoMin:lo,fisicoMax:hi},
   combinacionLibre:true,umbralesPrevios:before.map(u=>({id:u.id_umbral_ambiental,id_variable_ambiental:u.id_variable_ambiental,es_activo:u.es_activo})),
   invalidezIntencional:`valor_max=${regla.valor_max} supera el maximo fisico ${hi} ${v.unidad}`,
   payload:{id_especie:s.id_especie,id_variable_ambiental:v.id_variable_ambiental,valor_min:regla.valor_min,valor_max:regla.valor_max,
    niveles:[{nivel:'normal',limite_inferior:regla.valor_min,limite_superior:c1},
             {nivel:'precaucion',limite_inferior:c1,limite_superior:c2},
             {nivel:'critico',limite_inferior:c2,limite_superior:regla.valor_max}]}};
 }
 throw Error(`BLOCKED sin combinacion libre para ${v.nombre}`);
}
module.exports={BASE,FRONT,META,CASOS,REGLAS,settings,clean,dir,save,get,login,discover};
