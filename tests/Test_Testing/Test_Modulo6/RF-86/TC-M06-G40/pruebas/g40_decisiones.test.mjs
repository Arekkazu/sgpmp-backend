import assert from 'node:assert/strict';
import {test} from 'node:test';
import {escenario} from './fixture_g40.mjs';
const rows=[
  ['selección sin bovino',{sinCandidato:true},'BLOQUEADO',false],
  ['permisos Contador incompletos',{permisosFail:true},'NO_CONCLUYENTE',false],
  ['matriz sin par inicial',{matrizSinPar:true},'BLOQUEADO',false],
  ['DELETE matriz 404',{deleteFail:true},'NO_CONCLUYENTE',false],
  ['pesaje fallido',{pesajeFail:true},'NO_CONCLUYENTE',false],
  ['procesar fallido',{procesarFail:true},'NO_CONCLUYENTE',false],
  ['línea registrada con par ausente',{lineaRegistrada:true},'RECHAZADO',true],
  ['línea ausente',{lineaAusente:true},'RECHAZADO',true],
  ['panel sin aviso',{panel:false},'RECHAZADO',true],
  ['panel conteo distinto',{conteoDistinto:true},'RECHAZADO',true],
  ['alerta presente',{alerta:true},'APROBADO',true],
  ['alerta traducida',{alertaTexto:'Variación por transformación biológica. Ganancia. Especie Bovino'},'APROBADO',true],
  ['alerta genérica',{alertaTexto:'Hay una línea sin cuenta contable'},'RECHAZADO',true],
  ['alerta anterior',{alertaVieja:true},'RECHAZADO',true],
  ['alerta ausente',{alerta:false},'RECHAZADO',true],
  ['POST matriz sin resueltas',{postSinResueltas:true},'RECHAZADO',true],
  ['línea no pasa a REGISTRADA',{lineaNoRegistra:true},'RECHAZADO',true],
  ['matriz no restaurada',{matrizNoRestaurada:true},'NO_CONCLUYENTE',false],
  ['Cypress caído',{cypressFail:true},'NO_CONCLUYENTE',false],
  ['Newman fallido',{newmanFail:true},'NO_CONCLUYENTE',false],
];
for(const [name,options,expected,official] of rows)test(name,async()=>{
  const x=await escenario(name,options);assert.equal(x.preflight.ok,true);
  assert.equal(x.resultado.casos['TC-M06-018'].estado,expected,JSON.stringify(x.resultado.problemas_tecnicos));
  assert.equal(x.resultado.oficial,official);assert.equal(x.overlaps,0);
  assert.equal(x.resultado.total_solicitudes_api,x.requests);
  const cyEjecutado=x.resultado.herramientas.cypress!==null;
  assert.equal(x.resultado.cypress.total_pruebas,cyEjecutado?1:0);
  assert.equal(x.resultado.cypress.aprobadas,cyEjecutado&&!options.cypressFail?1:0);
  assert.equal(x.resultado.cypress.fallidas,cyEjecutado&&options.cypressFail?1:0);
  assert.equal(x.resultado.cypress.codigo,cyEjecutado?(options.cypressFail?2:0):null);
  assert.equal(x.resultado.cypress.spec,'g40.cy.js');
  assert.equal(x.informeCoherente,true);assert.equal(x.evidenciasPresentes,true);assert.equal(x.sinSecretos,true);
  assert.equal(x.files.filter(z=>z.endsWith('.md')).length,1);
  assert.ok(x.requests<=150,`solicitudes ${x.requests}`);
  if(official)assert.deepEqual(x.reports.sort(),['newman-G40.html','newman-G40.json']);
  console.log(`OK escenario_fila_${name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-zA-Z0-9]+/g,'_').toLowerCase()}: 018=${x.resultado.casos['TC-M06-018'].estado} oficial=${x.resultado.oficial?'sí':'no'} solicitudes=${x.requests}/150`);
});
