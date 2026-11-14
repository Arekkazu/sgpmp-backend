// Solo autenticacion y GET. Nunca crea, edita ni desactiva umbrales.
const fs=require('fs'),path=require('path');
const {login,get,save,clean,CASOS}=require('./helpers.cjs');
const dir=path.join(__dirname,'RESULTADOS');
(async()=>{
 const token=await login();
 const species=(await get('/configuracion/especies',token)).items;
 const variables=(await get('/configuracion/variables-ambientales',token)).items;
 const perms=(await get('/sesiones/me/permisos',token)).permisos;
 const checks=[];
 for(const caso of CASOS){
  const files=fs.readdirSync(dir).filter(f=>f.startsWith(`newman-${caso}-intento`)&&f.endsWith('.json')).sort();
  const ultimo=JSON.parse(fs.readFileSync(path.join(dir,files[files.length-1]),'utf8'));
  const p=ultimo.plan.payload;
  const after=await get(`/configuracion/umbrales?id_especie=${p.id_especie}`,token);
  const persisted=after.items.filter(u=>u.id_variable_ambiental===p.id_variable_ambiental);
  checks.push({caso,intentosNewman:files.length,postStatus:ultimo.events?.filter(e=>e.method==='POST').map(e=>e.status),
   especie:species.find(s=>s.id_especie===p.id_especie),
   variableCatalogoActivo:variables.find(v=>v.id_variable_ambiental===p.id_variable_ambiental)?.nombre??null,
   permisosRF17:perms.filter(x=>x.id_recurso===20).map(x=>x.id_accion),
   getStatus:200,total:after.total,ids:after.items.map(u=>u.id_umbral_ambiental),persisted});
 }
 save('verificacion-final-readonly.json',{checks,STOP_ALL:checks.some(c=>c.caso!=='TC-M09-54'&&c.persisted.length>0)});

 // Barrido de secretos sobre toda la evidencia textual antes de cerrar G24.
 const secretos=[process.env.TEST_ADMIN_PASSWORD,process.env.TEST_ADMIN_EMAIL].filter(Boolean);
 const patrones=[[/eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\./,'JWT'],[/Bearer\s+[A-Za-z0-9_.-]{12,}/,'Authorization'],[/set-cookie/i,'cookie'],[/refresh_token/i,'refresh token'],[/postgresql:\/\//i,'DB credentials']];
 const revisados=[];
 for(const f of fs.readdirSync(dir).filter(f=>/\.(html|json|md)$/i.test(f))){
  const txt=fs.readFileSync(path.join(dir,f),'utf8');
  const hallazgos=[...patrones.filter(([re])=>re.test(txt)).map(([,n])=>n),...secretos.filter(s=>txt.includes(s)).map(()=>'credencial')];
  revisados.push({archivo:f,bytes:txt.length,hallazgos});
 }
 const capturas=[];
 const shots=path.join(dir,'screenshots');
 if(fs.existsSync(shots))for(const run of fs.readdirSync(shots)){
  const sub=path.join(shots,run,'tc-m09-g24-niveles-alerta.cy.ts');
  if(fs.existsSync(sub))for(const png of fs.readdirSync(sub))capturas.push(`${run}/${png}`);
 }
 save('seguridad-evidencias.json',{revisados,limpios:revisados.every(r=>!r.hallazgos.length),capturas,
  nota:'Reporter htmlextra con omitHeaders y showEnvironmentData=false; sanitizacion adicional de HTML y JSON. Capturas con blackout de correo y contrasena.'});
 console.log('GET final',checks.map(c=>`${c.caso}: status ${c.getStatus}, total ${c.total}, persisted ${c.persisted.length}`).join(' | '));
 console.log('secretos en evidencia:',revisados.filter(r=>r.hallazgos.length).length===0?'ninguno':JSON.stringify(revisados.filter(r=>r.hallazgos.length)));
 console.log('capturas:',capturas.length);
})().catch(e=>{console.log(clean(e.message));process.exitCode=1;});
