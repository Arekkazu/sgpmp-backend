import test from 'node:test';
import assert from 'node:assert/strict';
import { autorizacion, ceroAsignaciones, limpiarTexto, versionSiguiente, veredicto } from './ejecutar_tc_m03_g94.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
test('la barrera exige QA_AUTORIZADO, TEST y efecto aceptado',()=>{
  const v={QA_AUTORIZADO:'SI',QA_SETUP_EMAIL:'a@qa.test',QA_PROD_EMAIL:'p@qa.test',QA_COMMON_PASSWORD:'clave',QA_SANDBOX_SECRET:'secreto',SIGAB_API_TEST_BASE:'https://www.api.inmero.co/api-sgpmp-test',SIGAB_FRONT_TEST_URL:'https://api.inmero.co/sigab-test'};
  const a={ambiente:'TEST',autorizacion:'DEV-123456',efectos:['notificacion-login']};
  assert.equal(autorizacion(v,a).ok,true);assert.equal(autorizacion({...v,QA_AUTORIZADO:'NO'},a).ok,false);assert.equal(autorizacion(v,{...a,ambiente:'DEV'}).ok,false);assert.equal(autorizacion(v,{...a,efectos:[]}).ok,false);
});
test('la precondición usa el ID real y cero asignaciones',()=>{
  assert.equal(ceroAsignaciones([{n:0}],5),true);assert.equal(ceroAsignaciones([{n:1}],5),false);assert.equal(ceroAsignaciones([{n:0}],0),false);
});
test('la evidencia redacta secretos',()=>assert.equal(limpiarTexto('clave eyJabcde.abcdef.abcdef',['clave']),'[REDACTADO] [JWT]'));
test('veredicto exige todas las aserciones y rollback',()=>{
  const base={estado:'CONCLUIDA',bloqueos:[],sandbox:{rollback:true},resultados:[{herramienta:'Newman',exit:0,assertions:['API-185-01','API-185-02'].map(nombre=>({nombre,ok:true}))},{herramienta:'Cypress',total:2,failed:0,skipped:0}]};
  assert.equal(veredicto(base),'APROBADO');assert.equal(veredicto({...base,sandbox:{rollback:false}}),'BLOQUEADO');assert.equal(veredicto({...base,resultados:[base.resultados[0],{herramienta:'Cypress',total:2,failed:1,skipped:0}]}),'RECHAZADO');
});
test('V1, V2 y reintento no sobrescriben historial',()=>{
  const d=fs.mkdtempSync(path.join(os.tmpdir(),'g94-version-'));
  try{assert.equal(versionSiguiente(d,'evaluacion'),1);const v1=path.join(d,'RESULTADOS','G94-EVAL-V1-a');fs.mkdirSync(v1,{recursive:true});fs.writeFileSync(path.join(v1,'evidencia.json'),JSON.stringify({estado:'CONCLUIDA'}));assert.equal(versionSiguiente(d,'evaluacion'),2);assert.equal(versionSiguiente(d,'reintento'),1);}finally{fs.rmSync(d,{recursive:true,force:true});}
});
