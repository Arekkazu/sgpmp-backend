import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {contrato as actual,validarLecturas,validarError} from '../lib/contrato.mjs';
import {simuladorG039} from './simulador_g039.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const refs=['G036','G037','G038'].map(g=>JSON.parse(fs.readFileSync(path.resolve(dir,'../../TC-M07-'+g+'/pruebas/contrato_'+g.toLowerCase()+'.json'),'utf8')));
const citas=actual.citas_campos??{};
for(const ruta of actual.rutas)assert.match(ruta.cita,/^src\//,ruta.ruta);
for(const [k,v] of Object.entries(citas))assert.match(v,/src\/[^:]+:\d+/,'Cita de '+k);
function comparar(a,b,k){if(typeof a==='string'&&typeof b==='string'){if(a!==b)assert.match(actual.justificaciones_tipos?.[k]??citas[k]??'',/src\/[^:]+:\d+/,k);return;}if(Array.isArray(a)&&Array.isArray(b))return comparar(a[0],b[0],k+'[]');if(a&&b&&typeof a==='object'&&typeof b==='object')for(const x of Object.keys(a).filter(x=>Object.hasOwn(b,x)))comparar(a[x],b[x],k+'.'+x);}
for(const ref of refs){comparar(actual.error_respuesta.cuerpo,ref.error_respuesta.cuerpo,'error_respuesta.cuerpo');for(const r of actual.rutas){const otra=ref.rutas.find(x=>x.metodo===r.metodo&&x.ruta===r.ruta);if(otra)comparar(r.respuesta,otra.respuesta,r.metodo+' '+r.ruta);}}
console.log('OK T2 contrato cruzado G036/G037/G038');
const sim=simuladorG039({auditoriaInicial:2,avisosInicial:2});
const RUN='RUN-G039-V2-20261117-000000',h={'X-Test-Run-Id':RUN,'X-Sandbox-Secret':'LOCAL'};
async function ver(metodo,ruta,body,error=false){const z=await sim.fetcher(sim.api+ruta,{method:metodo,headers:ruta==='/sesiones/'?{}:h,...(body===undefined?{}:{body:JSON.stringify(body)})}),raw=await z.json();if(error)assert(validarError(raw),ruta);else validarLecturas(raw,metodo,ruta,{estricto:true});return{http:z.status,raw};}
await ver('POST','/sesiones/');
await ver('GET','/sesiones/me/permisos');
await ver('GET','/integracion/anexos');
const contratos=(await ver('GET','/integracion/contratos')).raw;
assert.equal(contratos.find(x=>x.estado==='ACTIVO').contrato_version,'3.0');
await ver('GET','/configuracion/parametros-integracion-contable');
const base=(await ver('GET','/integracion/auditoria?tipo_evento=CONTRATO_TRANSICION_RECHAZADA')).raw.items;
const rechazo=await ver('POST','/integracion/contratos/18/activar',undefined,true);assert.equal(rechazo.raw.error_code,'TRANSICION_NO_PERMITIDA');
await ver('GET','/notificaciones?modulo=integracion&nivel=CRITICA');
await ver('PATCH','/integracion/contratos/18',{descripcion:'QA G039 V2'},true);
await ver('PUT','/integracion/contratos/18',{descripcion:'QA G039 V2'},true);
await ver('POST','/integracion/contratos/18/deprecar',{dias_gracia:90});
await ver('POST','/integracion/contratos/18/activar',undefined,true);
await ver('POST','/integracion/contratos/1/activar',undefined,true);
await ver('POST','/integracion/contratos/1/deprecar',{dias_gracia:90},true);
console.log('OK T3 rutas V2, errores y cuerpos');
const respuesta=(await ver('GET','/integracion/auditoria?tipo_evento=CONTRATO_TRANSICION_RECHAZADA')).raw,despues=respuesta.items;
assert(despues.some(x=>!base.some(y=>y.id_evento_integracion===x.id_evento_integracion)&&x.severidad==='WARNING'&&x.codigo_resultado==='TRANSICION_NO_PERMITIDA'));
assert.throws(()=>validarLecturas({...respuesta,items:[{...despues[0],id_evento_integracion:1}]},'GET','/integracion/auditoria',{estricto:true}).items[0].id_evento_integracion);
console.log('OK T4 eventos nuevos por UUID');
