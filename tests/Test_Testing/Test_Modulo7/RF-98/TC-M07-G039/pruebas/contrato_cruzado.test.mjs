import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {contrato as actual} from '../lib/contrato.mjs';
import {simuladorG039} from './simulador_g039.mjs';

const dir=path.dirname(fileURLToPath(import.meta.url));
const referencias=['G036','G037','G038'].map(g=>JSON.parse(fs.readFileSync(path.resolve(dir,`../../TC-M07-${g}/pruebas/contrato_${g.toLowerCase()}.json`),'utf8')));
const justificaciones=actual.justificaciones_tipos??{};
function compararComun(a,b,ruta){
  if(typeof a==='string'&&typeof b==='string'){
    if(a!==b)assert.match(justificaciones[ruta]??'',/^src\/[^:]+:\d+(?:-\d+)?$/,`Diferencia sin cita: ${ruta}: ${a} != ${b}`);
    return;
  }
  if(Array.isArray(a)&&Array.isArray(b))return compararComun(a[0],b[0],`${ruta}[]`);
  if(a&&b&&typeof a==='object'&&typeof b==='object')for(const k of Object.keys(a).filter(k=>Object.hasOwn(b,k)))compararComun(a[k],b[k],`${ruta}.${k}`);
}
for(const ref of referencias){
  compararComun(actual.error_respuesta.cuerpo,ref.error_respuesta.cuerpo,'error_respuesta.cuerpo');
  for(const ruta of actual.rutas){const otra=ref.rutas.find(x=>x.metodo===ruta.metodo&&x.ruta===ruta.ruta);if(otra)compararComun(ruta.respuesta,otra.respuesta,`${ruta.metodo} ${ruta.ruta}`);}
}
assert.equal(actual.rutas.find(x=>x.ruta==='/integracion/auditoria').respuesta.items[0].id_evento_integracion,'string'); assert.equal(actual.rutas.find(x=>x.ruta==='/integracion/auditoria').respuesta.items[0].severidad,'string');
assert.match(actual.rutas.find(x=>x.ruta==='/integracion/auditoria').cita,/evento_integracion\.py:40-64/);
console.log('OK T2 contrato G039 frente a G036/G037/G038');

function validar(valor,modelo,ruta){
  if(typeof modelo==='string'){
    const permitido=modelo.split('|').some(t=>t==='null'?valor===null:t==='integer'?Number.isInteger(valor):t==='datetime'?typeof valor==='string'&&!Number.isNaN(Date.parse(valor))&&/T| /.test(valor):t==='date'?typeof valor==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(valor):t==='object'?valor!==null&&typeof valor==='object'&&!Array.isArray(valor):typeof valor===t);
    assert(permitido,`TIPO_INVALIDO_${ruta}: ${JSON.stringify(valor)}; esperado ${modelo}`);return;
  }
  if(Array.isArray(modelo)){assert(Array.isArray(valor),`ARRAY_INVALIDO_${ruta}`);for(const [i,x] of valor.entries())validar(x,modelo[0],`${ruta}[${i}]`);return;}
  assert(valor!==null&&typeof valor==='object'&&!Array.isArray(valor),`OBJETO_INVALIDO_${ruta}`);
  for(const [k,m] of Object.entries(modelo)){assert(Object.hasOwn(valor,k),`CAMPO_AUSENTE_${ruta}.${k}`);validar(valor[k],m,`${ruta}.${k}`);}
}
const sim=simuladorG039({auditoriaInicial:2,avisosInicial:2,conAviso:true});
async function comprobar(metodo,ruta,body,esError=false){
  const z=await sim.fetcher(sim.api+ruta,{method:metodo,headers:{'X-Test-Run-Id':'RUN-G039-V1-20261117-000000'},...(body?{body:JSON.stringify(body)}:{})});
  const valor=await z.json();const esquema=esError?actual.error_respuesta.cuerpo:actual.rutas.find(x=>x.metodo===metodo&&x.ruta===ruta.split('?')[0].replace(/\/\d+\/(activar|deprecar)$/,'/{id}/$1').replace(/\/\d+$/,'/{id}'))?.respuesta;
  assert(esquema,`${metodo} ${ruta}`);validar(valor,esquema,`${metodo} ${ruta}`);return valor;
}
await comprobar('POST','/sesiones/');
await comprobar('GET','/sesiones/me/permisos');
await comprobar('GET','/integracion/anexos');
await comprobar('GET','/integracion/contratos');
const contratos=await comprobar('GET','/integracion/contratos');
assert.equal(actual.rutas.find(x=>x.metodo==='GET'&&x.ruta==='/integracion/contratos').respuesta[0].fecha_vigencia,'date');
assert(contratos.every(x=>/^\d{4}-\d{2}-\d{2}$/.test(x.fecha_vigencia)));
const baseAuditoria=await comprobar('GET','/integracion/auditoria?tipo_evento=CONTRATO_DEPRECADO');
await comprobar('POST','/integracion/contratos/3/activar',undefined,true);
await comprobar('POST','/integracion/contratos/18/activar',undefined,true);
await comprobar('POST','/integracion/contratos/4/deprecar',{dias_gracia:90},true);
await comprobar('GET','/notificaciones');
for(const metodo of ['PATCH','PUT']){const z=await sim.fetcher(sim.api+'/integracion/contratos/18',{method:metodo,headers:{'X-Test-Run-Id':'RUN-G039-V1-20261117-000000'},body:JSON.stringify({mapeadores:['CAMBIO_QA']})});assert.equal(z.status,404);assert.deepEqual(await z.json(),{detail:'Not Found'});}
await comprobar('POST','/integracion/contratos/18/deprecar',{dias_gracia:90});
const auditoria=await comprobar('GET','/integracion/auditoria?tipo_evento=CONTRATO_DEPRECADO');
await comprobar('POST','/integracion/contratos/1/activar',undefined,true);
await comprobar('POST','/integracion/contratos/1/deprecar',{dias_gracia:90},true);
assert(auditoria.items.length>0);assert(auditoria.items.every(x=>typeof x.severidad==='string'));
for(const x of auditoria.items)assert.match(x.id_evento_integracion,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-8[0-9a-f]{3}-[0-9a-f]{12}$/);
assert.throws(()=>validar({...auditoria,items:[{...auditoria.items[0],id_evento_integracion:1}]},actual.rutas.find(x=>x.ruta==='/integracion/auditoria').respuesta,'auditoria'),/TIPO_INVALIDO_auditoria.items\[0\].id_evento_integracion/);
console.log('OK T3 rutas usadas y fecha_vigencia date');
const idsBase=new Set(baseAuditoria.items.map(x=>x.id_evento_integracion));
assert(auditoria.items.some(x=>!idsBase.has(x.id_evento_integracion)&&x.version_contrato==='3.0'));
console.log('OK T4 comparación de línea base con UUID');
