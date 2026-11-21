import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {contrato,validarSolicitud,validarLecturas,validarError} from '../lib/contrato.mjs';
import {simuladorG037} from './simulador_g037.mjs';

const dir=path.dirname(fileURLToPath(import.meta.url));
const refs=['G036','G038','G039','G040','G041'].map(g=>({grupo:g,valor:JSON.parse(fs.readFileSync(path.resolve(dir,`../../TC-M07-${g}/pruebas/contrato_${g.toLowerCase()}.json`),'utf8'))}));
function comun(a,b,etiqueta){
  if(Array.isArray(a)&&Array.isArray(b))return comun(a[0],b[0],etiqueta+'[]');
  if(a&&b&&typeof a==='object'&&typeof b==='object'){for(const k of Object.keys(a).filter(k=>Object.hasOwn(b,k)))comun(a[k],b[k],etiqueta+'.'+k);return;}
  assert.equal(a,b,etiqueta);
}
for(const {grupo,valor} of refs){
  comun(contrato.error_respuesta.cuerpo,valor.error_respuesta.cuerpo,`error compartido ${grupo}`);
  for(const ruta of contrato.rutas){
    const otra=valor.rutas.find(x=>x.metodo===ruta.metodo&&x.ruta===ruta.ruta);
    if(!otra)continue;
    assert(ruta.cita?.startsWith('src/'),`cita ausente ${ruta.ruta}`);
    comun(ruta.respuesta,otra.respuesta,`${grupo} ${ruta.ruta}`);
  }
}
assert.deepEqual(Object.keys(contrato.rutas.find(x=>x.ruta==='/sesiones/').solicitud).sort(),['contrasena','correo_electronico']);
const ejecutor=fs.readFileSync(path.resolve(dir,'../g037.mjs'),'utf8');
for(const [campo,env] of [['correo_electronico','EMAIL'],['contrasena','PASSWORD']])assert.match(ejecutor,new RegExp(`${campo}:e\\.QA_ADMIN_${env}`));
console.log('OK T2 contrato compartido G036 y G038-G041');

const sim=await simuladorG037();
try{
  const run=sim.runId,h={'X-Test-Run-Id':run,'Content-Type':'application/json'};
  const pedir=async(m,r,b,headers=h)=>{const z=await fetch(sim.api+r,{method:m,headers,...(b===undefined?{}:{body:JSON.stringify(b)})});return{http:z.status,raw:await z.json()};};
  const login={correo_electronico:'local@example.invalid',contrasena:'LOCAL'};
  assert(validarSolicitud('POST','/sesiones/',login));
  const l=await pedir('POST','/sesiones/',login);assert.equal(l.http,200);assert.equal(validarLecturas(l.raw,'POST','/sesiones/',{estricto:true}).token,'local-token');
  const m=await pedir('GET','/configuracion/parametros-integracion-contable');
  assert.equal(m.http,200);assert.equal(validarLecturas(m.raw,'GET','/configuracion/parametros-integracion-contable',{estricto:true})[0].valor,30);
  const p=await pedir('PATCH','/configuracion/parametros-integracion-contable',{parametros:{aaef_gracia_minima_dias:45,aaef_gracia_defecto_dias:120}});
  assert.equal(p.http,200);assert.equal(validarLecturas(p.raw,'PATCH','/configuracion/parametros-integracion-contable',{estricto:true})[0].valor,'45');
  const publico=await pedir('GET','/configuracion/parametros-integracion-contable',undefined,{});
  assert.equal(publico.raw[0].valor,30,'T3: PATCH aislado del estado público');
  console.log('OK T3 simulador estricto y sandbox aislado');
  assert.throws(()=>validarSolicitud('POST','/sesiones/',{correo:'local@example.invalid',contrasena:'LOCAL'}));
  assert.throws(()=>validarSolicitud('POST','/sesiones/',{...login,otro:'extra'}));
  assert.throws(()=>validarSolicitud('PATCH','/configuracion/parametros-integracion-contable',{parametros:{nombre_ajeno:1}}));
  assert.equal((await pedir('PATCH','/configuracion/parametros-integracion-contable',{parametros:{aaef_gracia_defecto_dias:44}})).http,400);
  assert(validarError((await pedir('PATCH','/configuracion/parametros-integracion-contable',{parametros:{aaef_gracia_defecto_dias:44}})).raw));
  console.log('OK T4 solicitudes y error');
}finally{await sim.cerrar();}
