import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {contrato,validarSolicitud,validarLecturas,validarError} from '../lib/contrato.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const justificaciones=contrato.justificaciones_tipos;
function comparar(a,b,ruta){
  if(typeof a==='string'&&typeof b==='string'){if(a!==b)assert.match(justificaciones[ruta]??'',/^src\/[^:]+:\d+/,ruta);return;}
  if(Array.isArray(a)&&Array.isArray(b)){if(a.length&&b.length)comparar(a[0],b[0],ruta+'[]');return;}
  if(a&&b&&typeof a==='object'&&typeof b==='object')for(const k of Object.keys(a).filter(k=>Object.hasOwn(b,k)))comparar(a[k],b[k],ruta+'.'+k);
}
for(const g of ['G037','G038','G039','G040','G041']){
  const ref=JSON.parse(fs.readFileSync(path.resolve(dir,'../../TC-M07-'+g+'/pruebas/contrato_'+g.toLowerCase()+'.json'),'utf8'));
  comparar(contrato.error_respuesta.cuerpo,ref.error_respuesta.cuerpo,'ERROR');
  for(const r of contrato.rutas){const otro=ref.rutas.find(x=>x.metodo===r.metodo&&x.ruta===r.ruta);if(otro){comparar(r.respuesta,otro.respuesta,r.metodo+' '+r.ruta);if(r.solicitud&&otro.solicitud)comparar(r.solicitud,otro.solicitud,r.metodo+' '+r.ruta+'.solicitud');}}
}
const campos=(v,p)=>{if(typeof v==='string')assert(contrato.citas_campos[p]?.startsWith('src/'),p);else if(Array.isArray(v)){if(v.length)campos(v[0],p+'[]');}else for(const [k,x] of Object.entries(v))campos(x,p+'.'+k);};
for(const r of contrato.rutas){const p=r.metodo+' '+r.ruta;assert(r.cita.startsWith('src/'));campos(r.respuesta,p);if(r.solicitud)campos(r.solicitud,p+'.solicitud');}
campos(contrato.error_respuesta.cuerpo,'ERROR');
console.log('OK T2 contrato G036 frente a G037-G041');
const fixture=JSON.parse(fs.readFileSync(path.join(dir,'fixture_g036.json'),'utf8'));
const lista=fixture.contratos.map(x=>({...x,motivo_no_activable:null,versiones_que_retira:[]}));
const contratos=validarLecturas(lista,'GET','/integracion/contratos',{estricto:true});
assert.equal(contratos[0].motivo_no_activable,null);
assert.throws(()=>contratos[0].campo_fantasma,/LECTURA_FUERA_CONTRATO/);
assert(validarError({error_code:'MAPPERS_INVALIDOS',message:'inválido',field:'mapeadores',fields:[{field:'mapeadores',message:'inválido'}],timestamp:'2026-11-20T00:00:00Z'}));
console.log('OK T3 lecturas estrictas y error actual');
const base={contrato_version:'6.0',tipo_cambio:'MAJOR',fecha_vigencia:'2027-12-31',id_mapeo_anexo_aaef:2,mapeadores:['COMPRAS'],periodo_gracia_dias:90};
assert(validarSolicitud('POST','/integracion/contratos',base));
assert(validarSolicitud('POST','/integracion/contratos',{...base,mapeadores:[]}));
assert(validarSolicitud('POST','/integracion/contratos',{...base,mapeadores:['MAPPER_X']}));
assert(validarSolicitud('POST','/integracion/anexos',{codigo_anexo:'QA-G036-X',version_anexo:'6.0',ruta_documento:'docs/qa/x.md',sha256_documento:'a'.repeat(64)}));
assert(!validarSolicitud('POST','/integracion/contratos',{...base,id_mapeo_anexo_aaef:'2'}));
console.log('OK T4 solicitudes del ejecutor y variantes FA-3');

