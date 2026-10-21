import test from 'node:test';
import assert from 'node:assert/strict';
import { autorizacion, candidatoSinSenal, limpiarTexto, versionSiguiente, veredicto, consultaTestigoArea, leerConteo, evaluarAislamiento } from './ejecutar_tc_m03_g93.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

test('la barrera exige autorización completa, TEST y aceptación de efecto', () => {
  const v={QA_AUTORIZADO:'SI',QA_SETUP_EMAIL:'qa@example.org',QA_PROD_EMAIL:'prod@example.org',QA_COMMON_PASSWORD:'clave',QA_SANDBOX_SECRET:'secreto',SIGAB_API_TEST_BASE:'https://www.api.inmero.co/api-sgpmp-test',SIGAB_FRONT_TEST_URL:'https://api.inmero.co/sigab-test'};
  const a={ambiente:'TEST',autorizacion:'DEV-123456',efectos:['notificacion-login']};
  assert.equal(autorizacion(v,a).ok,true);
  assert.equal(autorizacion({...v,QA_AUTORIZADO:'NO'},a).ok,false);
  assert.equal(autorizacion(v,{...a,ambiente:'DEV'}).ok,false);
  assert.equal(autorizacion(v,{...a,efectos:[]}).ok,false);
});
test('la segunda unidad exige todos los sensores y paginación completa', () => {
  const d={resumen_unidades:[{id_infraestructura:7,total_sensores:2}],sensores:[{id_infraestructura:7,estado_conectividad:'SIN_SEÑAL'}]};
  assert.equal(candidatoSinSenal(d),null);
  assert.equal(candidatoSinSenal({...d,sensores:[...d.sensores,{id_infraestructura:7,estado_conectividad:'SIN_SEÑAL'}]}).id_infraestructura,7);
  assert.equal(candidatoSinSenal({...d,sensores:[...d.sensores,{id_infraestructura:7,estado_conectividad:'ACTIVO'}]}),null);
});
test('secretos y JWT no pasan a evidencia', () => assert.equal(limpiarTexto('clave eyJabcde.abcdef.abcdef', ['clave']),'[REDACTADO] [JWT]'));
test('veredicto: PRE, hooks, entorno y rollback bloquean; solo un ASSERT incumplido rechaza',()=>{
  const n=(id,ok=true,t='ASSERT')=>({nombre:`[TC-M03-184][${t}][${id}] x`,ok});
  const base={estado:'CONCLUIDA',bloqueos:[],sandbox:{rollback:true},resultados:[
    {herramienta:'Newman',exit:0,assertions:[n('PRE-184-01',true,'PRE'),n('API-184-01'),n('API-184-02'),n('API-184-03')]},
    {herramienta:'Cypress',total:2,failed:0,skipped:0,tests:[{titulo:'[TC-M03-184][ASSERT][UI-184-01] a',estado:'passed',hook:false},{titulo:'[TC-M03-184][ASSERT][UI-184-02] b',estado:'passed',hook:false}]}]};
  const conNewman=(a)=>({...base,resultados:[{...base.resultados[0],assertions:a},base.resultados[1]]});
  const conCypress=(t)=>({...base,resultados:[base.resultados[0],{...base.resultados[1],failed:1,tests:t}]});
  assert.equal(veredicto(base),'APROBADO');
  assert.equal(veredicto({...base,bloqueos:['segunda variante no disponible']}),'BLOQUEADO');
  assert.equal(veredicto(conNewman([n('PRE-184-01'),n('API-184-01',false),n('API-184-02'),n('API-184-03')])),'RECHAZADO');
  assert.equal(veredicto(conNewman([n('PRE-184-01',false,'PRE'),n('API-184-01',false),n('API-184-02'),n('API-184-03')])),'BLOQUEADO');
  assert.equal(veredicto(conCypress([{titulo:'[TC-M03-184][ASSERT][UI-184-01] a',estado:'failed',hook:true}])),'BLOQUEADO');
  assert.equal(veredicto(conCypress([{titulo:'[TC-M03-184][ASSERT][UI-184-01] a',estado:'failed',hook:false}])),'RECHAZADO');
  assert.equal(veredicto({...base,sandbox:{rollback:false}}),'BLOQUEADO');
  assert.equal(veredicto({...base,estado:'ABORTADA_PREFLIGHT'}),'BLOQUEADO');
});
test('testigo de aislamiento: auditoria.logs_dml sin RLS, identificado por id y nombre del RUN', () => {
  const q=consultaTestigoArea(321,'QA G93 G93-EVAL-V1-20261017101500');
  assert.match(q,/FROM auditoria\.logs_dml/);
  assert.doesNotMatch(q,/modulo9\.infraestructuras/);
  assert.match(q,/tabla_afectada = 'infraestructuras'/);
  assert.match(q,/tipo_operacion = 'INSERT'/);
  assert.match(q,/datos_nuevos->>'id_infraestructura' = '321'/);
  assert.match(q,/datos_nuevos->>'nombre' = 'QA G93 G93-EVAL-V1-20261017101500'/);
  assert.throws(()=>consultaTestigoArea('x','QA'));
  assert.throws(()=>consultaTestigoArea(5,"x' OR '1'='1"));
});
test('leerConteo usa {data:[...]} y nunca convierte un fallo en 0', () => {
  assert.equal(leerConteo({status:200,data:{data:[{n:1}]}}),1);
  assert.equal(leerConteo({status:200,data:{data:[{n:'0'}]}}),0);
  assert.equal(leerConteo({status:400,data:{detail:'permission denied'}}),null);
  assert.equal(leerConteo({status:200,data:{data:[]}}),null);
  assert.equal(leerConteo({status:200,data:[{n:1}]}),null);
});
test('aislamiento: solo dentro=1 y fuera=0 lo demuestran; null o fuga lo niegan', () => {
  assert.equal(evaluarAislamiento(1,0).demostrado,true);
  assert.equal(evaluarAislamiento(null,0).demostrado,false);
  assert.equal(evaluarAislamiento(1,null).demostrado,false);
  assert.equal(evaluarAislamiento(0,0).demostrado,false);
  assert.match(evaluarAislamiento(1,1).motivo,/FUGA/);
});
test('V1, V2 y reintento conservan historial', () => {
  const d=fs.mkdtempSync(path.join(os.tmpdir(),'g93-version-'));
  try{
    assert.equal(versionSiguiente(d,'evaluacion'),1);
    const v1=path.join(d,'RESULTADOS','G93-EVAL-V1-a');fs.mkdirSync(v1,{recursive:true});fs.writeFileSync(path.join(v1,'evidencia.json'),JSON.stringify({estado:'CONCLUIDA'}));
    assert.equal(versionSiguiente(d,'evaluacion'),2);
    assert.equal(versionSiguiente(d,'reintento'),1);
  }finally{fs.rmSync(d,{recursive:true,force:true});}
});
