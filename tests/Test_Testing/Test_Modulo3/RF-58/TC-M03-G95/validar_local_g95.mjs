import test from 'node:test';
import assert from 'node:assert/strict';
import { autorizacion, capacidadExpiracion, limpiarTexto, versionSiguiente, veredicto } from './ejecutar_tc_m03_g95.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
test('la barrera exige autorización, TEST y efecto aceptado',()=>{
  const v={QA_AUTORIZADO:'SI',QA_PROD_EMAIL:'p@qa.test',QA_PROD_PASSWORD:'clave',QA_SANDBOX_SECRET:'secreto',SIGAB_API_TEST_BASE:'https://www.api.inmero.co/api-sgpmp-test',SIGAB_FRONT_TEST_URL:'https://api.inmero.co/sigab-test'};
  const a={ambiente:'TEST',autorizacion:'DEV-123456',efectos:['notificacion-login']};
  assert.equal(autorizacion(v,a).ok,true);assert.equal(autorizacion({...v,QA_AUTORIZADO:'NO'},a).ok,false);assert.equal(autorizacion(v,{...a,ambiente:'DEV'}).ok,false);assert.equal(autorizacion(v,{...a,efectos:[]}).ok,false);
});
test('la capacidad depende de expiraciones reales, no de un false fijo',()=>{
  assert.equal(capacidadExpiracion(40,'refresh_token=x; Max-Age=30',3).verificable,true);
  assert.equal(capacidadExpiracion(30,'refresh_token=x; Max-Age=40',3).verificable,false);
  assert.equal(capacidadExpiracion(28800,'refresh_token=x; Max-Age=604800',20).verificable,false);
  assert.equal(capacidadExpiracion(30,'',3).verificable,false);
});
test('la evidencia redacta secretos',()=>assert.equal(limpiarTexto('clave eyJabcde.abcdef.abcdef',['clave']),'[REDACTADO] [JWT]'));
test('sin expiración observada o rollback no hay aprobación',()=>{
  const base={estado:'CONCLUIDA',bloqueos:[],sandbox:{rollback:true},resultados:[{herramienta:'Cypress',total:1,failed:0,skipped:0}]};
  assert.equal(veredicto(base),'APROBADO');assert.equal(veredicto({...base,estado:'ABORTADA_PREFLIGHT'}),'BLOQUEADO');assert.equal(veredicto({...base,sandbox:{rollback:false}}),'BLOQUEADO');
});
test('V1, V2 y reintento conservan historial',()=>{const d=fs.mkdtempSync(path.join(os.tmpdir(),'g95-version-'));try{assert.equal(versionSiguiente(d,'evaluacion'),1);const v1=path.join(d,'RESULTADOS','G95-EVAL-V1-a');fs.mkdirSync(v1,{recursive:true});fs.writeFileSync(path.join(v1,'evidencia.json'),JSON.stringify({estado:'CONCLUIDA'}));assert.equal(versionSiguiente(d,'evaluacion'),2);assert.equal(versionSiguiente(d,'reintento'),1);}finally{fs.rmSync(d,{recursive:true,force:true});}});
