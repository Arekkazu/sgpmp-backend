const fs=require('fs'),path=require('path');

const BASE='https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const FRONT='https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const CASO='TC-M09-59';
const META={
 grupo:'TC-M09-G27',caso:CASO,rf:'RF-17',cu:'CU-03',trazabilidad:'CU-07',
 rama:'qa/juan-esteban-m09',
 frontendSHA:'966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56',
 backendSHA:'adc3932b9f0293a76ebec7e89ed877274791b6a1',base:BASE,front:FRONT,
};
// Productor es el actor preferido. Los siguientes candidatos solo se consultan
// si Productor no puede autenticar o su identidad/permisos reales no sirven.
const ACTORES=[
 {rolEsperado:'Productor',email:'m2m.nuevo@ejemplo.com'},
 {rolEsperado:'Supervisor',email:'supervisor.dev@sgpmp.test'},
 {rolEsperado:'Gestor de granja',email:'gestor.granja.test@pecuaria.co'},
 {rolEsperado:'Revisor fiscal',email:'revisor.fiscal.test@pecuaria.co'},
 {rolEsperado:'Contador',email:'contador@pecuaria.co'},
 {rolEsperado:'Ingeniero de campo',email:'ingeniero@pecuaria.co'},
];

function settings(){
 const runId=process.env.G27_RUN_ID,attempt=Number(process.env.G27_ATTEMPT||1);
 if(!runId||!/^[\w-]+$/.test(runId))throw Error('G27_RUN_ID requerido (solo letras, numeros, _ o -)');
 if(![1,2].includes(attempt))throw Error('G27_ATTEMPT debe ser 1 o 2');
 if(!process.env.TEST_ADMIN_EMAIL||!process.env.TEST_ADMIN_PASSWORD||!process.env.TEST_UNAUTHORIZED_PASSWORD)
  throw Error('Faltan credenciales TEST requeridas en variables de proceso');
 return {runId,attempt};
}
function clean(s){
 s=String(s);
 for(const secret of [process.env.TEST_ADMIN_PASSWORD,process.env.TEST_UNAUTHORIZED_PASSWORD,process.env.TEST_ADMIN_EMAIL].filter(Boolean))s=s.split(secret).join('[REDACTED]');
 return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[JWT REDACTED]')
  .replace(/Bearer\s+[A-Za-z0-9_.-]+/gi,'Bearer [REDACTED]')
  .replace(/(refresh_token|access_token|token)\s*[=:]\s*[^\s,;"']+/gi,'$1=[REDACTED]');
}
function dir(runId,sub){const d=sub?path.join(__dirname,'RESULTADOS',runId,sub):path.join(__dirname,'RESULTADOS',runId);fs.mkdirSync(d,{recursive:true});return d;}
function save(runId,name,value){fs.writeFileSync(path.join(dir(runId),name),clean(JSON.stringify({...META,fecha:new Date().toISOString(),...value},null,2)));}
async function api(method,endpoint,token,body){
 const headers={};if(token)headers.Authorization=`Bearer ${token}`;if(body!==undefined)headers['Content-Type']='application/json';
 const r=await fetch(BASE+endpoint,{method,headers,body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(25000)});
 let json=null;try{json=await r.json();}catch{}
 return {status:r.status,json};
}
async function require200(endpoint,token){const r=await api('GET',endpoint,token);if(r.status!==200)throw Error(`GET ${endpoint} HTTP ${r.status}`);return r.json;}
async function login(email,password){
 const r=await api('POST','/sesiones/',null,{correo_electronico:email,contrasena:password});
 if(r.status!==200||!r.json?.token)throw Object.assign(Error(`Login HTTP ${r.status}`),{status:r.status});
 return r.json.token;
}
function functional(u){return {
 id_umbral_ambiental:u.id_umbral_ambiental,id_especie:u.id_especie,id_variable_ambiental:u.id_variable_ambiental,
 unidad_medida:u.unidad_medida,valor_min:String(u.valor_min),valor_max:String(u.valor_max),es_activo:u.es_activo,
 niveles:[...u.niveles].map(n=>({nivel:n.nivel,limite_inferior:String(n.limite_inferior),limite_superior:String(n.limite_superior)})).sort((a,b)=>a.nivel.localeCompare(b.nivel)),
};}
function roleAllowed(role){return ['administrador','veterinario'].includes(String(role||'').trim().toLowerCase());}
function hasUpdate(perms){return Array.isArray(perms)&&perms.some(p=>p.id_recurso===20&&p.id_accion===3);}
async function actorNoAutorizado(){
 const intentos=[];
 for(const candidato of ACTORES){
  let token;
  try{token=await login(candidato.email,process.env.TEST_UNAUTHORIZED_PASSWORD);}catch(e){
   intentos.push({actor:candidato.rolEsperado,email:candidato.email,login:'fallido',status:e.status??null});continue;
  }
  const me=await api('GET','/usuarios/me',token);
  const permisos=await api('GET','/sesiones/me/permisos',token);
  if(me.status!==200||permisos.status!==200){
   intentos.push({actor:candidato.rolEsperado,email:candidato.email,login:'ok',meStatus:me.status,permisosStatus:permisos.status,seleccionado:false});continue;
  }
  const rol=me.json?.nombre_rol;
  const puedeEditar=hasUpdate(permisos.json?.permisos);
  const esNoAutorizado=!roleAllowed(rol)&&!puedeEditar;
  intentos.push({actor:candidato.rolEsperado,email:candidato.email,login:'ok',meStatus:200,permisosStatus:200,rolReal:rol,permisoRF17Actualizar:puedeEditar,seleccionado:esNoAutorizado});
  if(esNoAutorizado)return {token,actor:{email:candidato.email,rol:rol,rolEsperado:candidato.rolEsperado,authStatus:200,identityStatus:200,permisosStatus:200,permisoRF17Actualizar:false},intentos};
 }
 throw Object.assign(Error('BLOCKED ningun actor TEST autenticado es inequivocamente no autorizado para RF-17'),{intentos});
}
function puntos(lo,hi,variant){
 const fr=variant===0?[.2,.4,.6,.8]:variant===1?[.1,.35,.65,.9]:[.15,.4,.6,.85];
 const p=fr.map(f=>Math.round((lo+(hi-lo)*f)*100)/100);
 return p.every((x,i)=>Number.isFinite(x)&&(!i||x>p[i-1]))?p:null;
}
function igualPayloadActual(payload,actual){
 const a=functional(actual);
 return String(payload.valor_min)===a.valor_min&&String(payload.valor_max)===a.valor_max&&
  JSON.stringify([...payload.niveles].map(n=>({nivel:n.nivel,limite_inferior:String(n.limite_inferior),limite_superior:String(n.limite_superior)})).sort((x,y)=>x.nivel.localeCompare(y.nivel)))===JSON.stringify(a.niveles);
}
async function discoverAdmin(){
 const adminToken=await login(process.env.TEST_ADMIN_EMAIL,process.env.TEST_ADMIN_PASSWORD);
 const adminMe=await require200('/usuarios/me',adminToken);
 const adminPerms=await require200('/sesiones/me/permisos',adminToken);
 if(![2,3].every(a=>hasAction(adminPerms.permisos,20,a)))throw Error('BLOCKED administrador TEST sin permisos leer/editar RF-17');
 const especies=(await require200('/configuracion/especies',adminToken)).items;
 const variables=(await require200('/configuracion/variables-ambientales',adminToken)).items;
 const preferidas=[...variables].sort((a,b)=>Number(!/temperatura/i.test(a.nombre))-Number(!/temperatura/i.test(b.nombre)));
 for(const especie of especies){
  const lista=await require200(`/configuracion/umbrales?id_especie=${especie.id_especie}`,adminToken);
  for(const umbral of lista.items.filter(u=>u.es_activo)){
   const variable=preferidas.find(v=>v.id_variable_ambiental===umbral.id_variable_ambiental);
   if(!variable)continue;
   const lo=Number(variable.valor_fisico_min),hi=Number(variable.valor_fisico_max);
   for(let i=0;i<3;i++){
    const p=puntos(lo,hi,i);if(!p)continue;
    const payload={valor_min:p[0],valor_max:p[3],niveles:[
     {nivel:'normal',limite_inferior:p[0],limite_superior:p[1]},
     {nivel:'precaucion',limite_inferior:p[1],limite_superior:p[2]},
     {nivel:'critico',limite_inferior:p[2],limite_superior:p[3]}],fecha_actualizacion:umbral.fecha_actualizacion};
    if(!igualPayloadActual(payload,umbral))return {adminToken,admin:{email:adminMe.correo_electronico,rol:adminMe.nombre_rol,authStatus:200,identityStatus:200},
     contract:{metodo:'PATCH',endpoint:`/configuracion/umbrales/${umbral.id_umbral_ambiental}`,recurso:20,accionActualizar:3},
     especie:{id:especie.id_especie,nombre:especie.nombre,es_activo:especie.es_activo},
     variable:{id:variable.id_variable_ambiental,nombre:variable.nombre,unidad:variable.unidad,limiteFisicoMin:lo,limiteFisicoMax:hi},
     before:functional(umbral),payload};
   }
  }
 }
 throw Error('BLOCKED no existe umbral ambiental activo con una modificacion valida y no-op evitable');
}
function hasAction(perms,recurso,accion){return Array.isArray(perms)&&perms.some(p=>p.id_recurso===recurso&&p.id_accion===accion);}
module.exports={BASE,FRONT,CASO,META,settings,clean,dir,save,api,require200,login,actorNoAutorizado,discoverAdmin,functional};
