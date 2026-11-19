import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {contrato,validarSolicitud,validarLecturas,validarError} from '../lib/contrato.mjs';
import {servidorG041} from './simulador_g041.mjs';

const dir=path.dirname(fileURLToPath(import.meta.url));
const justificaciones=contrato.justificaciones_tipos;
function comparar(a,b,ruta){
  if(typeof a==='string'&&typeof b==='string'){
    if(a!==b)assert.match(justificaciones[ruta]??'',/^src\/[^:]+:\d+(?:-\d+)?(?:;.*)?$/,`Diferencia sin cita: ${ruta}`);
    return;
  }
  if(Array.isArray(a)&&Array.isArray(b))return comparar(a[0],b[0],ruta+'[]');
  if(a&&b&&typeof a==='object'&&typeof b==='object')for(const k of Object.keys(a).filter(k=>Object.hasOwn(b,k)))comparar(a[k],b[k],ruta+'.'+k);
}
for(const g of ['G036','G037','G038','G039','G040']){
  const ref=JSON.parse(fs.readFileSync(path.resolve(dir,`../../TC-M07-${g}/pruebas/contrato_${g.toLowerCase()}.json`),'utf8'));
  comparar(contrato.error_respuesta.cuerpo,ref.error_respuesta.cuerpo,'error_respuesta.cuerpo');
  for(const r of contrato.rutas){const otro=ref.rutas.find(x=>x.metodo===r.metodo&&x.ruta===r.ruta);if(otro){comparar(r.respuesta,otro.respuesta,`${r.metodo} ${r.ruta}`);if(r.solicitud&&otro.solicitud)comparar(r.solicitud,otro.solicitud,`${r.metodo} ${r.ruta}.solicitud`);}}
}
assert(contrato.rutas.every(x=>x.cita?.startsWith('src/')));
const campo=(v,p)=>{if(typeof v==='string')assert(contrato.citas_campos[p]?.startsWith('src/'),p);else if(Array.isArray(v)){if(v.length)campo(v[0],p+'[]');else assert(contrato.citas_campos[p]?.startsWith('src/'),p);}else for(const [k,x] of Object.entries(v))campo(x,p+'.'+k);};
for(const r of contrato.rutas){const p=`${r.metodo} ${r.ruta}`;campo(r.respuesta,p);if(r.solicitud)campo(r.solicitud,p+'.solicitud');}
for(const k of Object.keys(contrato.error_respuesta.cuerpo))assert(contrato.citas_campos['ERROR.'+k]);
console.log('OK T2 contrato G041 frente a G036/G037/G038/G039/G040');

const sim=await servidorG041();
try{
  const h={'X-Test-Run-Id':'RUN-G041-V1-20261118-000000'};
  const get=async ruta=>{const z=await fetch(sim.api+ruta,{headers:h});assert.equal(z.status,200);return z.json();};
  assert(validarLecturas(await get('/integracion/contratos'),'GET','/integracion/contratos',{estricto:true}));
  const aud=validarLecturas(await get('/integracion/auditoria?tipo_evento=CONTRATO_ACTIVADO'),'GET','/integracion/auditoria',{estricto:true});
  assert.equal(aud.items[0].tipo_actor,'USUARIO');
  assert.equal(typeof aud.items[0].json_detalle.estado,'string');
  assert.throws(()=>aud.items[0].campo_fantasma,/LECTURA_FUERA_CONTRATO/);
  const bad=await fetch(sim.api+'/sesiones/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({correo:'x',contrasena:'x'})});
  assert.equal(bad.status,400);assert(validarError(await bad.json()));
  console.log('OK T3 simulador estricto y error completo');
  const fuente=fs.readFileSync(path.resolve(dir,'../g041.mjs'),'utf8');
  assert.match(fuente,/correo_electronico:e\.QA_ADMIN_EMAIL,contrasena:e\.QA_ADMIN_PASSWORD/);
  assert.match(fuente,/correo_electronico:e\.QA_CONTADOR_EMAIL,contrasena:e\.QA_CONTADOR_PASSWORD/);
  assert.match(fuente,/body=v=>\(\{contrato_version:v,tipo_cambio:'MINOR',fecha_vigencia:futura,id_mapeo_anexo_aaef:anexo\.id_mapeo_anexo_aaef,mapeadores:\['COMPRAS'\],periodo_gracia_dias:null,descripcion:null\}\)/);
  assert.match(fuente,/\{dias_gracia:90\}/);
  assert(validarSolicitud('POST','/sesiones/',{correo_electronico:'local@example.invalid',contrasena:'LOCAL'}));
  assert(validarSolicitud('POST','/integracion/contratos',{contrato_version:'6.0',tipo_cambio:'MINOR',fecha_vigencia:'2027-01-01',id_mapeo_anexo_aaef:2,mapeadores:['COMPRAS'],periodo_gracia_dias:null,descripcion:null}));
  assert(validarSolicitud('POST','/integracion/contratos/4/activar',{}));
  assert(validarSolicitud('POST','/integracion/contratos/18/deprecar',{dias_gracia:90}));
  assert(!validarSolicitud('POST','/sesiones/',{correo:'local@example.invalid',contrasena:'LOCAL'}));
  console.log('OK T4 solicitudes del ejecutor');
}finally{await sim.cerrar();}
