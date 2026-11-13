import assert from 'node:assert/strict';
import {test} from 'node:test';
import {escenario} from './fixture_g40.mjs';
const rows=[
  ['selección sin bovino',{sinCandidato:true},'NO_CONCLUYENTE',false],
  ['permisos Contador incompletos',{permisosFail:true},'NO_CONCLUYENTE',false],
  ['matriz sin par inicial',{matrizSinPar:true},'NO_CONCLUYENTE',false],
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
  ['alerta anterior',{alertaVieja:true},'NO_CONCLUYENTE',false],
  ['conforme PERDIDA',{sentido:'PERDIDA'},'APROBADO',true],
  ['alerta de otra especie',{alertaTexto:'Falta la cuenta contable de Variación por transformación biológica (ganancia) para otra especie.'},'RECHAZADO',true],
  ['alerta de otro sentido',{alertaTexto:'Falta la cuenta contable de Variación por transformación biológica (pérdida ajena) para Bovino.'},'RECHAZADO',true],
  ['REINTENTAR V2 conforme',{operacion:'reintentar'},'APROBADO',true],
  ['REINTENTAR V2 PERDIDA',{operacion:'reintentar',sentido:'PERDIDA'},'APROBADO',true],
  ['PERDIDA sin par inicial',{sentido:'PERDIDA',matrizSinPar:true},'NO_CONCLUYENTE',false],
  ['alerta ausente',{alerta:false},'RECHAZADO',true],
  ['POST matriz sin resueltas',{postSinResueltas:true},'RECHAZADO',true],
  ['línea no pasa a REGISTRADA',{lineaNoRegistra:true},'RECHAZADO',true],
  ['base uno final cero',{pendientePreexistente:true},'APROBADO',true],
  ['base uno línea pendiente',{pendientePreexistente:true,lineaNoRegistra:true},'RECHAZADO',true],
  ['cuentas distintas',{cuentasDistintas:true},'RECHAZADO',true],
  ['conteo final alto',{conteoFinalAlto:true},'RECHAZADO',true],
  ['matriz no restaurada',{matrizNoRestaurada:true},'NO_CONCLUYENTE',false],
  ['DELETE final fallido',{closeFail:true},'NO_CONCLUYENTE',false],
  ['Cypress caído',{cypressFail:true},'NO_CONCLUYENTE',false],
  ['Newman fallido',{newmanFail:true},'NO_CONCLUYENTE',false],
];
for(const [name,options,expected,official] of rows)test(name,async()=>{
  const x=await escenario(name,options);assert.equal(x.preflight.ok,true);
  assert.equal(x.resultado.casos['TC-M06-018'].estado,expected,JSON.stringify(x.resultado.problemas_tecnicos));
  assert.equal(x.resultado.oficial,official);assert.equal(x.overlaps,0);
  assert.equal(x.deleteHttp,options.closeFail?500:200);
  if(options.alertaVieja||options.sinCandidato||options.matrizSinPar)assert.equal(x.writes,0);
  if(options.alertaVieja)assert.match(x.resultado.casos['TC-M06-018'].motivo,/combinación ya notificada/);
  if(options.sentido==='PERDIDA'&&!options.matrizSinPar)assert.equal(x.postBody?.sentido,'PERDIDA');
  if(name==='alerta presente'||name==='conforme PERDIDA'||name==='REINTENTAR V2 conforme'||name==='REINTENTAR V2 PERDIDA'||name==='base uno final cero')
    assert.equal(x.resultado.seguimiento.estado_v2,'CORREGIDA');
  if(['base uno línea pendiente','cuentas distintas','conteo final alto'].includes(name)){
    assert.equal(x.resultado.observado.c,true);
    assert.equal(x.resultado.observado.d,false);
    assert.equal(x.resultado.seguimiento.estado_v2,'CORREGIDA');}
  if(name==='base uno final cero'){
    assert.equal(x.resultado.observado.conteo_base,1);
    assert.equal(x.resultado.observado.conteo_pendiente,2);
    assert.equal(x.resultado.observado.conteo_final,0);
    assert.deepEqual(x.resultado.observado.ids_pendientes_antes,[400,500]);
    assert.deepEqual(x.resultado.observado.ids_pendientes_despues,[]);
    assert.equal(x.resultado.observado.lineas_resueltas,2);
    assert.equal(x.resultado.observado.linea_final.estado,'REGISTRADA');
    assert.equal(x.resultado.observado.linea_final.cuenta_debito,x.resultado.observado.asignacion_creada.cuenta_debito);
    assert.match(x.informe,/POST resolvió además otras líneas pendientes preexistentes/);
    assert.match(x.informe,/Antes del POST, los IDs pendientes del período fueron 400, 500; después, ninguno/);}
  if(name==='REINTENTAR V2 PERDIDA'){
    assert.equal(x.postBody?.sentido,'PERDIDA');
    assert.equal(x.resultado.observado.sentido,'PERDIDA');
    assert.deepEqual(x.asignacionDesactivada,{id:12,tipo_hecho:'VARIACION_VR_TB',sentido:'PERDIDA',id_especie:null});
    assert.equal(x.pesajeBody?.valor_medicion,99);
    assert.match(x.informe,/Por qué se decide: se cumplieron los cuatro pasos; veredicto aprobado/);}
  if(name==='alerta ausente')assert.equal(x.resultado.seguimiento.estado_v2,'REPRODUCIDA');
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

for(const [name,options,expected,sentido,descartados] of [
  ['AUTO sin avisos',{modoAuto:true},'APROBADO','GANANCIA',[]],
  ['AUTO descarta GANANCIA',{modoAuto:true,avisosPrevios:['GANANCIA'],operacion:'reintentar'},'APROBADO','PERDIDA',
    [{sentido:'GANANCIA',id_aviso:12796}]],
  ['AUTO ambos avisos',{modoAuto:true,avisosPrevios:['GANANCIA','PERDIDA']},'NO_CONCLUYENTE',null,
    [{sentido:'GANANCIA',id_aviso:12796},{sentido:'PERDIDA',id_aviso:12797}]],
  ['explícito GANANCIA previa',{sentido:'GANANCIA',avisosPrevios:['GANANCIA']},'NO_CONCLUYENTE','GANANCIA',
    [{sentido:'GANANCIA',id_aviso:12796}]]
])test(name,async()=>{
  const x=await escenario(name,options),o=x.resultado.observado;
  assert.equal(x.preflight.ok,true);assert.equal(x.resultado.casos['TC-M06-018'].estado,expected);
  assert.equal(o.sentido_modo,options.modoAuto?'AUTO':'EXPLICITO');assert.equal(o.sentido,sentido);
  assert.deepEqual(o.sentidos_descartados,descartados);assert.equal(x.deleteHttp,200);
  if(expected==='NO_CONCLUYENTE'){assert.equal(x.writes,0);assert.equal(x.resultado.oficial,false);}
  else{assert.equal(x.resultado.oficial,true);assert.equal(x.postBody?.sentido,sentido);
    assert.equal(x.pesajeBody?.valor_medicion,sentido==='GANANCIA'?101:99);}
  if(name==='AUTO descarta GANANCIA'){
    assert.match(x.informe,/se usó pérdida porque la ganancia de Bovino ya tenía aviso en el período 241 \(aviso 12796\)/i);
    assert.deepEqual(x.asignacionDesactivada,{id:12,tipo_hecho:'VARIACION_VR_TB',sentido:'PERDIDA',id_especie:null});}
  if(name==='AUTO ambos avisos')assert.match(x.resultado.casos['TC-M06-018'].motivo,/ambas combinaciones ya notificadas en el período/);
  if(name==='explícito GANANCIA previa')assert.match(x.resultado.casos['TC-M06-018'].motivo,/combinación ya notificada/);
  assert.equal(x.informeCoherente,true);assert.equal(x.evidenciasPresentes,true);
});
