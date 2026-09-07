const fs=require('fs'),path=require('path');
const BASE='https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const FRONT='https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const CASOS=['TC-M09-57','TC-M09-58','TC-M09-65'];
const VARIANTES={'TC-M09-57':['inexistente','inactiva'],'TC-M09-58':['intento1','intento2'],'TC-M09-65':['intento1','intento2']};
const META={grupo:'TC-M09-G26',rf:'RF-17',cu:'CU-03',rol:'Administrador',rama:'qa/juan-esteban-m09',
 frontendSHA:'966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56',backendSHA:'adc3932b9f0293a76ebec7e89ed877274791b6a1',base:BASE};
// Separacion suficiente para que el ID candidato no colisione con altas recientes.
const SALTO=900;

function settings(){
 const caso=process.env.G26_CASE,runId=process.env.G26_RUN_ID,variante=process.env.G26_VARIANTE;
 if(!CASOS.includes(caso))throw Error('G26_CASE debe ser TC-M09-57, TC-M09-58 o TC-M09-65');
 if(!runId||!/^[\w-]+$/.test(runId))throw Error('G26_RUN_ID requerido');
 if(!VARIANTES[caso].includes(variante))throw Error(`G26_VARIANTE de ${caso} debe ser: ${VARIANTES[caso].join(' | ')}`);
 return {caso,runId,variante};
}
function clean(s){for(const secret of [process.env.TEST_ADMIN_PASSWORD,process.env.TEST_ADMIN_EMAIL].filter(Boolean))s=s.split(secret).join('[REDACTED]');
 return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[JWT REDACTED]').replace(/Bearer\s+[A-Za-z0-9_.-]+/g,'Bearer [REDACTED]');}
function dir(runId,sub){const d=sub?path.join(__dirname,'RESULTADOS',runId,sub):path.join(__dirname,'RESULTADOS',runId);fs.mkdirSync(d,{recursive:true});return d;}
function save(runId,name,value){fs.writeFileSync(path.join(dir(runId),name),clean(JSON.stringify({...META,fecha:new Date().toISOString(),...value},null,2)));}
async function get(endpoint,token){const r=await fetch(BASE+endpoint,{headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(25000)});
 if(r.status!==200)throw Error(`GET ${endpoint} HTTP ${r.status}`);return r.json();}
async function login(){const r=await fetch(BASE+'/sesiones/',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({correo_electronico:process.env.TEST_ADMIN_EMAIL,contrasena:process.env.TEST_ADMIN_PASSWORD}),signal:AbortSignal.timeout(25000)});
 if(r.status!==200)throw Error(`ENVIRONMENT_ERROR login HTTP ${r.status}`);const j=await r.json();if(!j.token)throw Error('ENVIRONMENT_ERROR login sin token');return j.token;}

// Cuatro cortes crecientes dentro del rango fisico: padre [p0,p3] con tres niveles contiguos.
function puntos(lo,hi){const f=fr=>Math.round((lo+(hi-lo)*fr)*100)/100;const p=[f(.2),f(.4),f(.6),f(.8)];
 return p.every((x,i)=>Number.isFinite(x)&&(!i||x>p[i-1]))?p:null;}
function niveles(p){return [{nivel:'normal',limite_inferior:p[0],limite_superior:p[1]},
 {nivel:'precaucion',limite_inferior:p[1],limite_superior:p[2]},
 {nivel:'critico',limite_inferior:p[2],limite_superior:p[3]}];}

async function discover(token,caso,variante){
 const perms=(await get('/sesiones/me/permisos',token)).permisos;
 if(![1,2].every(a=>perms.some(p=>p.id_recurso===20&&p.id_accion===a)))throw Error('BLOCKED permiso RF17 ausente');
 // Catalogo COMPLETO de especies (solo_activas=false por defecto, con total y sin paginacion).
 const cat=await get('/configuracion/especies',token);
 const especies=cat.items;
 if(cat.total!==especies.length)throw Error('BLOCKED catalogo de especies incompleto');
 const variables=(await get('/configuracion/variables-ambientales',token)).items;
 const catalogoVariables={total:variables.length,ids:variables.map(v=>v.id_variable_ambiental).sort((a,b)=>a-b),
  items:variables.map(v=>({id:v.id_variable_ambiental,nombre:v.nombre,unidad:v.unidad,fisicoMin:Number(v.valor_fisico_min),fisicoMax:Number(v.valor_fisico_max)}))};
 const base={caso,variante,catalogoEspecies:{total:cat.total,ids:especies.map(s=>s.id_especie).sort((a,b)=>a-b),
  activas:especies.filter(s=>s.es_activo).map(s=>s.id_especie),inactivas:especies.filter(s=>!s.es_activo).map(s=>s.id_especie)},catalogoVariables};

 if(caso==='TC-M09-57'){
  // Variable valida y activa; se prefiere Humedad por legibilidad del rango.
  const orden=[...variables].sort((a,b)=>Number(!/humedad/i.test(a.nombre))-Number(!/humedad/i.test(b.nombre)));
  const v=orden.find(x=>puntos(Number(x.valor_fisico_min),Number(x.valor_fisico_max)));
  if(!v)throw Error('BLOCKED sin variable con rango fisico utilizable');
  const p=puntos(Number(v.valor_fisico_min),Number(v.valor_fisico_max));
  const variable={id:v.id_variable_ambiental,nombre:v.nombre,unidad:v.unidad,catalogoActivo:true,fisicoMin:Number(v.valor_fisico_min),fisicoMax:Number(v.valor_fisico_max)};
  let especie,evidencia;
  if(variante==='inexistente'){
   const idCandidato=Math.max(...especies.map(s=>s.id_especie))+SALTO;
   if(especies.some(s=>s.id_especie===idCandidato))throw Error('El ID candidato si existe');
   especie={id:idCandidato,existe:false,es_activo:null};
   evidencia={metodo:'catalogo completo GET /configuracion/especies (solo_activas=false)',
    total:cat.total,idsExistentes:base.catalogoEspecies.ids,idEnviado:idCandidato,presenteEnCatalogo:false};
  }else{
   const inactivas=especies.filter(s=>!s.es_activo);
   if(!inactivas.length)throw Error('BLOCKED no existe especie inactiva disponible en TEST');
   let elegida=null;
   for(const s of inactivas){
    const u=(await get(`/configuracion/umbrales?id_especie=${s.id_especie}`,token)).items;
    if(!u.some(x=>x.id_variable_ambiental===v.id_variable_ambiental)){elegida={s,u};break;}
   }
   if(!elegida)throw Error('BLOCKED sin especie inactiva con combinacion libre');
   especie={id:elegida.s.id_especie,nombre:elegida.s.nombre,existe:true,es_activo:false};
   evidencia={metodo:'catalogo completo de especies',es_activo:false,umbralesPrevios:elegida.u.map(x=>x.id_umbral_ambiental)};
  }
  const umbralesPrevios=(await get(`/configuracion/umbrales?id_especie=${especie.id}`,token).catch(()=>({items:[]}))).items||[];
  return {...base,especie,variable,evidenciaEspecie:evidencia,
   invalidezIntencional:variante==='inexistente'?`id_especie=${especie.id} no pertenece al catalogo`:`id_especie=${especie.id} existe pero es_activo=false`,
   umbralesPrevios:umbralesPrevios.map(u=>({id:u.id_umbral_ambiental,id_variable_ambiental:u.id_variable_ambiental,es_activo:u.es_activo})),
   payload:{id_especie:especie.id,id_variable_ambiental:variable.id,valor_min:p[0],valor_max:p[3],niveles:niveles(p)}};
 }

 if(caso==='TC-M09-58'){
  // Se reutiliza una configuracion ACTIVA ya existente: no se crea ningun prerequisito.
  for(const s of especies.filter(x=>x.es_activo)){
   const items=(await get(`/configuracion/umbrales?id_especie=${s.id_especie}`,token)).items;
   for(const u of items.filter(x=>x.es_activo)){
    const v=variables.find(x=>x.id_variable_ambiental===u.id_variable_ambiental);
    if(!v)continue;
    const p=puntos(Number(v.valor_fisico_min),Number(v.valor_fisico_max));
    if(!p)continue;
    return {...base,
     especie:{id:s.id_especie,nombre:s.nombre,es_activo:true},
     variable:{id:v.id_variable_ambiental,nombre:v.nombre,unidad:v.unidad,catalogoActivo:true,fisicoMin:Number(v.valor_fisico_min),fisicoMax:Number(v.valor_fisico_max)},
     configuracionExistente:{id:u.id_umbral_ambiental,id_especie:u.id_especie,id_variable_ambiental:u.id_variable_ambiental,es_activo:u.es_activo,valor_min:u.valor_min,valor_max:u.valor_max},
     invalidezIntencional:`ya existe el umbral activo #${u.id_umbral_ambiental} para especie ${s.id_especie} + variable ${v.id_variable_ambiental}`,
     umbralesPrevios:items.map(x=>({id:x.id_umbral_ambiental,id_variable_ambiental:x.id_variable_ambiental,es_activo:x.es_activo})),
     // Rango propio dentro de los limites fisicos: el registro existente guarda valores
     // heredados fuera de rango y copiarlos dispararia FA-04 en vez de la unicidad.
     payload:{id_especie:s.id_especie,id_variable_ambiental:v.id_variable_ambiental,valor_min:p[0],valor_max:p[3],niveles:niveles(p)}};
   }
  }
  throw Error('BLOCKED no existe combinacion activa preexistente para validar duplicidad');
 }

 // TC-M09-65: variable ausente del catalogo. El DTO recibe id_variable_ambiental entero.
 const s=especies.find(x=>x.es_activo);
 if(!s)throw Error('BLOCKED sin especie activa');
 const idVariable=Math.max(...catalogoVariables.ids)+SALTO;
 if(catalogoVariables.ids.includes(idVariable))throw Error('El ID de variable candidato si existe');
 const items=(await get(`/configuracion/umbrales?id_especie=${s.id_especie}`,token)).items;
 return {...base,
  especie:{id:s.id_especie,nombre:s.nombre,es_activo:true},
  variable:{id:idVariable,perteneceAlCatalogo:false,tipoEnviado:'integer'},
  evidenciaVariable:{metodo:'GET /configuracion/variables-ambientales',totalCatalogo:catalogoVariables.total,idsCatalogo:catalogoVariables.ids,idEnviado:idVariable,presenteEnCatalogo:false},
  invalidezIntencional:`id_variable_ambiental=${idVariable} no pertenece al catalogo predefinido`,
  umbralesPrevios:items.map(x=>({id:x.id_umbral_ambiental,id_variable_ambiental:x.id_variable_ambiental,es_activo:x.es_activo})),
  // Rango neutro y estructuralmente valido: la variable no existe, asi que no hay
  // limites fisicos que contrastar y ninguna otra regla debe activarse.
  payload:{id_especie:s.id_especie,id_variable_ambiental:idVariable,valor_min:10,valor_max:40,niveles:niveles([10,20,30,40])}};
}
module.exports={BASE,FRONT,META,CASOS,VARIANTES,settings,clean,dir,save,get,login,discover};
