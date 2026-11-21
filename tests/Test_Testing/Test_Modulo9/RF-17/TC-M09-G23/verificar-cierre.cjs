// Only authentication and GET requests. Never creates/edits/deletes thresholds.
const fs=require('fs');
const {login,get,save,clean}=require('./helpers.cjs');
(async()=>{
 const token=await login();
 const species=(await get('/configuracion/especies',token)).items;
 const variables=(await get('/configuracion/variables-ambientales',token)).items;
 const perms=(await get('/sesiones/me/permisos',token)).permisos;
 const checks=[];
 for(const caso of ['TC-M09-50','TC-M09-51']){
  const plan=JSON.parse(fs.readFileSync(`RESULTADOS/newman-${caso}-intento1.json`)).plan;
  const p=plan.payload;
  const after=await get(`/configuracion/umbrales?id_especie=${p.id_especie}`,token);
  checks.push({caso,especie:species.find(s=>s.id_especie===p.id_especie),variableCatalogoActivo:variables.find(v=>v.id_variable_ambiental===p.id_variable_ambiental),permisosRF17:perms.filter(p=>p.id_recurso===20),getStatus:200,total:after.total,ids:after.items.map(u=>u.id_umbral_ambiental),persisted:after.items.filter(u=>u.id_variable_ambiental===p.id_variable_ambiental)});
 }
 save('verificacion-final-readonly.json',{checks,STOP_ALL:checks.some(c=>c.persisted.length>0)});
 console.log('GET final',checks.map(c=>({caso:c.caso,status:c.getStatus,persisted:c.persisted.length})));
})().catch(e=>{console.log(clean(e.message));process.exitCode=1;});
