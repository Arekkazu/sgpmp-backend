const fs=require('fs'),path=require('path');
const BASE='https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const FRONT='https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const CASOS=['TC-M09-52','TC-M09-53','TC-M09-54'];
const META={grupo:'TC-M09-G24',rol:'Administrador',frontendSHA:'966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56',backendSHA:'adc3932b9f0293a76ebec7e89ed877274791b6a1',rama:'qa/juan-esteban-m09',base:BASE};
function settings(){const caso=process.env.G24_CASE,id=process.env.G24_RUN_ID;if(!CASOS.includes(caso)||!id||!/^[\w-]+$/.test(id))throw Error('G24_CASE (TC-M09-52|53|54) y G24_RUN_ID requeridos');return {caso,id};}
function clean(s){for(const secret of [process.env.TEST_ADMIN_PASSWORD,process.env.TEST_ADMIN_EMAIL].filter(Boolean))s=s.split(secret).join('[REDACTED]');return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[JWT REDACTED]').replace(/Bearer\s+[A-Za-z0-9_.-]+/g,'Bearer [REDACTED]');}
function save(name,value){const dir=path.join(__dirname,'RESULTADOS');fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path.join(dir,name),clean(JSON.stringify({...META,fecha:new Date().toISOString(),...value},null,2)));}
async function get(endpoint,token){const r=await fetch(BASE+endpoint,{headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(25000)});if(r.status!==200)throw Error(`GET ${endpoint} HTTP ${r.status}`);return r.json();}
async function login(){const r=await fetch(BASE+'/sesiones/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({correo_electronico:process.env.TEST_ADMIN_EMAIL,contrasena:process.env.TEST_ADMIN_PASSWORD}),signal:AbortSignal.timeout(25000)});if(r.status!==200)throw Error(`Login HTTP ${r.status}`);const j=await r.json();if(!j.token)throw Error('Login sin token');return j.token;}
// Puntos derivados del rango fisico real de la variable. El padre es [a,d] en los
// tres originales; solo cambia el defecto intencional de los niveles.
function puntos(lo,hi){const f=fr=>Math.round((lo+(hi-lo)*fr)*100)/100;const p={a:f(.2),b:f(.4),e:f(.5),c:f(.6),d:f(.8),g:f(.9)};const s=[p.a,p.b,p.e,p.c,p.d,p.g];return s.every((x,i)=>Number.isFinite(x)&&(!i||x>s[i-1]))?p:null;}
function niveles(caso,p){const n=(nivel,limite_inferior,limite_superior)=>({nivel,limite_inferior,limite_superior});return {
 // critico termina en g > valor_max: unico defecto intencional (FA-08).
 'TC-M09-52':[n('normal',p.a,p.b),n('precaucion',p.b,p.c),n('critico',p.c,p.g)],
 // critico empieza en e < c: solapa [e,c] con precaucion. Sin huecos (FA-05).
 'TC-M09-53':[n('normal',p.a,p.b),n('precaucion',p.b,p.c),n('critico',p.e,p.d)],
 // Cobertura continua y completa de [a,d].
 'TC-M09-54':[n('normal',p.a,p.b),n('precaucion',p.b,p.c),n('critico',p.c,p.d)],
}[caso];}
function defecto(caso,p){return {
 'TC-M09-52':{regla:'FA-08 nivel fuera del rango padre',detalle:`critico ${p.c}-${p.g} excede valor_max ${p.d}`,codigoEsperado:'NIVEL_FUERA_DE_RANGO'},
 'TC-M09-53':{regla:'FA-05 solapamiento entre niveles',detalle:`precaucion ${p.b}-${p.c} y critico ${p.e}-${p.d} ocupan a la vez [${p.e}, ${p.c}]`,codigoEsperado:'SOLAPAMIENTO_NIVELES'},
 'TC-M09-54':{regla:'FA-05 continuidad correcta',detalle:`niveles contiguos que cubren exactamente [${p.a}, ${p.d}] sin huecos ni solapamientos`,codigoEsperado:null},
}[caso];}
async function discover(token,caso){
 const perms=(await get('/sesiones/me/permisos',token)).permisos;
 if(![1,2].every(a=>perms.some(p=>p.id_recurso===20&&p.id_accion===a)))throw Error('BLOCKED permiso RF17');
 const species=(await get('/configuracion/especies',token)).items.filter(s=>s.es_activo);
 const variables=(await get('/configuracion/variables-ambientales',token)).items;
 const ordered=[...variables].sort((a,b)=>Number(!/Temperatura Ambiental/i.test(a.nombre))-Number(!/Temperatura Ambiental/i.test(b.nombre)));
 for(const v of ordered){
  const lo=Number(v.valor_fisico_min),hi=Number(v.valor_fisico_max),p=puntos(lo,hi);
  if(!p)continue;
  for(const s of species){
   const before=(await get(`/configuracion/umbrales?id_especie=${s.id_especie}`,token)).items;
   // La combinacion se considera ocupada aunque el umbral este inactivo.
   if(before.some(u=>u.id_variable_ambiental===v.id_variable_ambiental))continue;
   return {caso,especie:s.nombre,id_especie:s.id_especie,variable:v.nombre,id_variable:v.id_variable_ambiental,unidad:v.unidad,limitesFisicos:[lo,hi],puntos:p,defecto:defecto(caso,p),
    beforeIds:before.map(u=>u.id_umbral_ambiental),
    payload:{id_especie:s.id_especie,id_variable_ambiental:v.id_variable_ambiental,valor_min:p.a,valor_max:p.d,niveles:niveles(caso,p)}};
  }
 }
 throw Error('BLOCKED sin combinacion libre');
}
module.exports={BASE,FRONT,META,CASOS,settings,clean,save,get,login,discover};
