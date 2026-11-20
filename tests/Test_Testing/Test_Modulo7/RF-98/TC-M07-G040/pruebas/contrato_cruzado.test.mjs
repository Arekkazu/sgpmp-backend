import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {contrato,validarLecturas,validarError,validarSolicitud} from '../lib/contrato.mjs';
import {servidorG040} from './simulador_g040.mjs';

const dir=path.dirname(fileURLToPath(import.meta.url));
const referencias=['G036','G037','G038','G039'].map(g=>JSON.parse(fs.readFileSync(path.resolve(dir,`../../TC-M07-${g}/pruebas/contrato_${g.toLowerCase()}.json`),'utf8')));
const justificaciones=contrato.justificaciones_tipos??{};
function comparar(a,b,ruta){
 if(typeof a==='string'&&typeof b==='string'){if(a!==b)assert.match(justificaciones[ruta]??'',/^src\/[^:]+:\d+(?:-\d+)?$/,`Diferencia sin cita: ${ruta}`);return;}
 if(Array.isArray(a)&&Array.isArray(b))return comparar(a[0],b[0],ruta+'[]');
 if(a&&b&&typeof a==='object'&&typeof b==='object')for(const k of Object.keys(a).filter(k=>Object.hasOwn(b,k)))comparar(a[k],b[k],ruta+'.'+k);
}
for(const ref of referencias){
 comparar(contrato.error_respuesta.cuerpo,ref.error_respuesta.cuerpo,'error_respuesta.cuerpo');
 for(const ruta of contrato.rutas){const otra=ref.rutas.find(x=>x.metodo===ruta.metodo&&x.ruta===ruta.ruta);if(otra)comparar(ruta.respuesta,otra.respuesta,`${ruta.metodo} ${ruta.ruta}`);}
}
assert(contrato.rutas.every(x=>x.cita?.startsWith('src/')));
const loginSchema=contrato.rutas.find(x=>x.ruta==='/sesiones/').solicitud;
for(const grupo of ['G036','G037','G038','G039']){const fuente=fs.readFileSync(path.resolve(dir,`../../TC-M07-${grupo}/g${grupo.slice(1)}.mjs`),'utf8');assert.match(fuente,/correo_electronico\s*:\s*e\.QA_ADMIN_EMAIL/);assert.match(fuente,/contrasena\s*:\s*e\.QA_ADMIN_PASSWORD/);}
assert.deepEqual(Object.keys(loginSchema).sort(),['contrasena','correo_electronico']);
const ejecutor=fs.readFileSync(path.resolve(dir,'../g040.mjs'),'utf8');
for(const campo of Object.keys(loginSchema))assert.match(ejecutor,new RegExp(`${campo}:e\\.QA_ADMIN_${campo==='contrasena'?'PASSWORD':'EMAIL'}`));
for(const campo of ['client_id','client_secret','email'])assert.match(ejecutor,new RegExp(`${campo}:e\\.`));
console.log('OK T2 contrato G040 frente a G036/G037/G038/G039');

const sim=await servidorG040();
try{
 const h={'X-Test-Run-Id':'RUN-G040-V2-20261118-000000'};
 async function get(ruta,metodo='GET',extra={},body){const z=await fetch(sim.api+ruta,{method:metodo,headers:{...h,...extra,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});const raw=await z.json();return{z,raw};}
 const loginBody={correo_electronico:'local@example.invalid',contrasena:'LOCAL_PASSWORD'};
 const tokenBody={client_id:'LOCAL_CLIENT',client_secret:'LOCAL_SECRET',email:'local@example.invalid'};
 assert(validarSolicitud('POST','/sesiones/',loginBody));assert(validarSolicitud('POST','/integraciones/agrofusion/token',tokenBody));
 assert(validarSolicitud('GET','/finanzas/periodos',{numero_id_tributaria:'900123456'}));
 assert(validarSolicitud('GET','/integracion/aaef/productores/900123456',{Authorization:'Bearer <token de canal>','Accept-Version':'opcional; MAYOR.MENOR',desde:'2026-11-01',hasta:'2026-11-30',nit:'900123456'}));
 const login=await get('/sesiones/','POST',{},loginBody);assert.equal(login.z.status,200);assert.equal(validarLecturas(login.raw,'POST','/sesiones/',{estricto:true}).token,'LOCAL_ADMIN_TOKEN');
 for(const ruta of ['/sesiones/me/permisos','/integracion/anexos','/integracion/contratos','/configuracion/fincas/463/titular','/finanzas/periodos?numero_id_tributaria=900123456','/integracion/auditoria?pagina=1&tamano=100']){const {z,raw}=await get(ruta);assert.equal(z.status,200,ruta);assert(validarLecturas(raw,'GET',ruta,{estricto:true}));}
 const token=await get('/integraciones/agrofusion/token','POST',{},tokenBody);assert.equal(token.z.status,200);assert.equal(validarLecturas(token.raw,'POST','/integraciones/agrofusion/token',{estricto:true}).expires_in,300);
 const ruta='/integracion/aaef/productores/900123456?desde=2026-11-01&hasta=2026-11-30';
 const {z,raw}=await get(ruta,'GET',{Authorization:'Bearer LOCAL_CHANNEL_TOKEN','Accept-Version':'2.1'});
 assert.equal(z.status,200);const v=validarLecturas(raw,'GET',ruta,{estricto:true});assert.equal(v.metadata.StandardVersion,'1.0');assert.equal(v.invoices.length,0);
 assert.equal(z.headers.get('X-Version-Contrato-AAEF'),'2.1');assert.equal(z.headers.get('Deprecation'),'true');assert.equal(Date.parse(z.headers.get('Sunset')),Date.parse('2027-02-16T13:53:12Z'));
 sim.avanzar(13000);const bad=await get(ruta,'GET',{Authorization:'Bearer LOCAL_CHANNEL_TOKEN','Accept-Version':'abc'});assert.equal(bad.z.status,400);assert(validarError(bad.raw));
 console.log('OK T3 simulador estricto: token, 200, cabeceras y error');
 assert.equal((await get('/sesiones/','POST',{}, {correo:'local@example.invalid',contrasena:'LOCAL_PASSWORD'})).z.status,400);
 assert.equal((await get('/sesiones/','POST',{}, {...loginBody,correo:'extra'})).z.status,400);
 assert.equal((await get('/integraciones/agrofusion/token','POST',{}, {client_id:'LOCAL_CLIENT',email:'local@example.invalid'})).z.status,400);
 assert.equal((await get('/integraciones/agrofusion/token','POST',{}, {...tokenBody,client_secret:'incorrecto'})).z.status,401);
 assert.equal((await get('/integraciones/agrofusion/token','POST',{}, {...tokenBody,otro:'extra'})).z.status,400);
 console.log('OK T4 solicitudes');
}finally{await sim.cerrar();}
