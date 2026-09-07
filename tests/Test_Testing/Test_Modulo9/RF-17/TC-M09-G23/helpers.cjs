const fs=require('fs'),path=require('path');
const BASE='https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const FRONT='https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const META={grupo:'TC-M09-G23',rol:'Administrador',frontendSHA:'966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56',backendSHA:'b6131f190e01768599f3ef5e4f9c13487cd78f68',rama:'qa/juan-esteban-m09',base:BASE};
function settings(){const caso=process.env.G23_CASE,id=process.env.G23_RUN_ID;if(!['TC-M09-50','TC-M09-51'].includes(caso)||!id||!/^[\w-]+$/.test(id))throw Error('G23_CASE/G23_RUN_ID requeridos');return {caso,id};}
function clean(s){for(const secret of [process.env.TEST_ADMIN_PASSWORD,process.env.TEST_ADMIN_EMAIL].filter(Boolean))s=s.split(secret).join('[REDACTED]');return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[JWT REDACTED]').replace(/Bearer\s+[A-Za-z0-9_.-]+/g,'Bearer [REDACTED]');}
function save(name,value){const dir=path.join(__dirname,'RESULTADOS');fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path.join(dir,name),clean(JSON.stringify({...META,fecha:new Date().toISOString(),...value},null,2)));}
async function get(endpoint,token){const r=await fetch(BASE+endpoint,{headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(25000)});if(r.status!==200)throw Error(`GET ${endpoint} HTTP ${r.status}`);return r.json();}
async function login(){const r=await fetch(BASE+'/sesiones/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({correo_electronico:process.env.TEST_ADMIN_EMAIL,contrasena:process.env.TEST_ADMIN_PASSWORD}),signal:AbortSignal.timeout(25000)});if(r.status!==200)throw Error(`Login HTTP ${r.status}`);const j=await r.json();if(!j.token)throw Error('Login sin token');return j.token;}
async function discover(token,caso){
 const perms=(await get('/sesiones/me/permisos',token)).permisos;
 if(![1,2].every(a=>perms.some(p=>p.id_recurso===20&&p.id_accion===a)))throw Error('BLOCKED permiso RF17');
 const species=(await get('/configuracion/especies',token)).items.filter(s=>s.es_activo);
 const variables=(await get('/configuracion/variables-ambientales',token)).items;
 const ordered=[...variables].sort((a,b)=>Number(!/Temperatura Ambiental/i.test(a.nombre))-Number(!/Temperatura Ambiental/i.test(b.nombre)));
 for(const v of ordered){
  const lo=Number(v.valor_fisico_min),hi=Number(v.valor_fisico_max),points=[.2,.4,.6,.8].map(f=>Math.round((lo+(hi-lo)*f)*100)/100);
  if(!points.every((x,i)=>Number.isFinite(x)&&(!i||x>points[i-1])))continue;
  for(const s of species){
   const before=(await get(`/configuracion/umbrales?id_especie=${s.id_especie}`,token)).items;
   if(before.some(u=>u.id_variable_ambiental===v.id_variable_ambiental))continue;
   return {caso,especie:s.nombre,variable:v.nombre,unidad:v.unidad,limitesFisicos:[lo,hi],beforeIds:before.map(u=>u.id_umbral_ambiental),payload:{id_especie:s.id_especie,id_variable_ambiental:v.id_variable_ambiental,valor_min:caso==='TC-M09-50'?points[1]:points[2],valor_max:points[1],niveles:['normal','precaucion','critico'].map((nivel,i)=>({nivel,limite_inferior:points[i],limite_superior:points[i+1]}))}};
  }
 }
 throw Error('BLOCKED sin combinacion libre');
}
module.exports={BASE,FRONT,META,settings,clean,save,get,login,discover};
