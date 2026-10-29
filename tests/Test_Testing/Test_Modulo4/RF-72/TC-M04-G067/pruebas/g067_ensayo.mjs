import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { evaluar, leerEnv } from '../g067.mjs';
import { CASOS, CAPACIDADES, PRESUPUESTO } from '../lib/g067_core.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const A = CASOS.map(()=>'APROBADO'), one=(i,s='RECHAZADO')=>A.map((x,j)=>i===j?s:x);
const BL=CASOS.map(()=>'BLOQUEADO'), NC='NO_CONCLUYENTE';
const modos=[
  ['todo_ok',A,true], ['comportamiento_codigo_actual',one(0),true],
  ['minusculas_aceptada',one(0),true], ['numerico_400',one(0),true],
  ['vacio_aceptado',one(0),true], ['inexistente_aceptado',one(0),true],
  ['estado_422_otro_mensaje',one(0),true], ['ausente_400_completo',A,true],
  ['ausente_aceptado',one(1),true], ['ausente_400_sin_campo',one(1),true],
  ['parcial_sin_lista_aceptado',one(2),true], ['parcial_vacia_aceptada',one(2),true],
  ['parcial_400',one(2),true], ['incorrecto_sin_lista_aceptado',one(3),true],
  ['incorrecto_vacia_aceptada',one(3),true], ['correcto_con_diag_rechazado',one(4),true],
  ['sin_evento_sin_diag_rechazado',one(4),true], ['un_5xx',one(2),true],
  ['datos_insuficientes',[NC,NC,NC,NC,A[4]],false], ['env_archivo',A,true],
  ['login_lento',A,true], ['login_sin_red',BL,false], ['clave_403',BL,false],
  ['error5xx',BL,false], ['sin_respuesta',[NC,NC,A[2],NC,A[4]],false],
  ['corte_con_cierre',[NC,NC,NC,NC,A[4]],false],
  ['newman_no_disponible',BL,false], ['duplicada_con_reemplazo',A,true],
  ['ventana_con_reemplazo',A,true],
  ['post_clave_403',BL,false],
  ['post_tres_5xx',['BLOQUEADO','BLOQUEADO','BLOQUEADO','BLOQUEADO','RECHAZADO'],false]
];
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const read=req=>new Promise(resolve=>{const chunks=[];req.on('data',x=>chunks.push(x));req.on('end',()=>resolve(Buffer.concat(chunks).toString('utf8')));});
const send=(res,status,body,run)=>{res.writeHead(status,{'Content-Type':'application/json',...(run?{'X-Test-Run-Id':run}:{})});res.end(JSON.stringify(body));};
function makeServer(modo){
  const qty=modo==='datos_insuficientes'?5:14;
  const inferencias=Array.from({length:qty},(_,i)=>({id_evento:id(i+1),id_resultado_inferencia:id(i+1),
    id_activo_biologico:885,tipo_evento:'INFERENCIA',fecha_evento:new Date(Date.now()-86400000+i*60000).toISOString(),
    payload:{id_patologia:7,tipo_modelo:'MODELO_ESPECIES_MEDIANAS',id_version_modelo:43}}));
  const patologias=Array.from({length:8},(_,i)=>({id_patologia:i+7,especie_aplicable:'TODAS',es_activo:true,es_base:true}));
  const retros=[],audit=[],received=[];let deleted=false,closed=false,errors=0,invalidData=false;
  const server=http.createServer(async(req,res)=>{
    const u=new URL(req.url,'http://127.0.0.1'),run=req.headers['x-test-run-id'];
    const body=req.method==='POST'?JSON.parse((await read(req))||'{}'):{};
    if(u.pathname==='/sesiones/'&&req.method==='POST'){
      if(modo==='login_sin_red'){req.socket.destroy();return;}
      if(modo==='login_lento')await new Promise(resolve=>setTimeout(resolve,150));
      return send(res,200,{token:`local.${Buffer.from(JSON.stringify({sub:'900'})).toString('base64url')}.firma`});
    }
    if(u.pathname.startsWith('/test-control/runs/')&&req.method==='DELETE'){
      deleted=true;closed=true;return send(res,200,{status:'ok'});
    }
    if(modo==='clave_403'&&run)return send(res,403,{error_code:'CLAVE_INVALIDA'},run);
    if(u.pathname==='/activos-biologicos')return send(res,200,{registros:
      (modo==='error5xx'?[885,886,887]:[885]).map(n=>({id_activo_biologico:n,id_especie:220,tipo:'INDIVIDUAL'})),total_paginas:1},run);
    if(u.pathname.startsWith('/prediccion/historial/')){
      if(modo==='error5xx'&&errors++<3)return send(res,500,{error_code:'ERROR_INTERNO'},run);
      const eventos=[...inferencias,...(closed?[]:retros)];
      return send(res,200,{eventos,cursor_siguiente:null,total_pagina:eventos.length},run);
    }
    if(u.pathname==='/prediccion/patologias')return send(res,200,{items:patologias,total:patologias.length},run);
    if(u.pathname==='/prediccion/auditoria'){
      let items=closed?[]:audit;
      if(u.searchParams.has('id_referencia'))items=items.filter(x=>x.id_referencia===u.searchParams.get('id_referencia'));
      return send(res,200,{items,total:items.length},run);
    }
    if(u.pathname==='/prediccion/retroalimentacion'&&req.method==='POST'){
      const key=String(body.observaciones_clinicas||'').replace('QA G067 ','');received.push(key);
      if(modo==='post_clave_403')return send(res,403,{error_code:'CLAVE_INVALIDA'},run);
      if(modo==='post_tres_5xx')return send(res,503,{error_code:'ERROR_INTERNO'},run);
      if(['sin_respuesta','corte_con_cierre'].includes(modo)&&key===(modo==='sin_respuesta'?'208-omitido':'207-vacio')){req.socket.destroy();return;}
      if(['duplicada_con_reemplazo','ventana_con_reemplazo'].includes(modo)&&!invalidData){
        invalidData=true;return send(res,modo==='duplicada_con_reemplazo'?409:422,
          {error_code:modo==='duplicada_con_reemplazo'?'RETROALIMENTACION_DUPLICADA':'FUERA_DE_VENTANA_TEMPORAL'},run);
      }
      const persist=(estado=body.estado_retroalimentacion)=>{
        const rid=id(100+retros.length+1),fecha=new Date().toISOString();
        const response={...body,id_retroalimentacion:rid,estado_retroalimentacion:estado,
          id_usuario_veterinario:900,fecha_retroalimentacion:fecha};
        retros.push({id_evento:rid,id_resultado_inferencia:body.id_resultado_inferencia,
          id_activo_biologico:885,tipo_evento:'RETROALIMENTACION',fecha_evento:fecha,
          payload:{id_usuario_veterinario:900,estado_retroalimentacion:estado}});
        audit.push({tipo_evento:'RETROALIMENTACION_REGISTRADA',id_referencia:rid,
          payload_evento:{id_resultado_inferencia:body.id_resultado_inferencia}});
        return response;
      };
      const e3={error_code:'ESTADO_RETROALIMENTACION_INVALIDO',message:'El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO.',fields:[{field:'estado_retroalimentacion',message:'El estado de retroalimentación no es válido.'}]};
      const e4={error_code:'DIAGNOSTICO_REQUERIDO',message:'El diagnóstico clínico es obligatorio para este tipo de retroalimentación.',fields:[{field:'diagnosticos_reales',message:'El diagnóstico clínico es obligatorio para este tipo de retroalimentación.'}]};
      const missing={error_code:'VAL_ENTRADA',message:'Errores de validacion en la solicitud',fields:[{field:'estado_retroalimentacion',message:'Este campo es obligatorio.'}]};
      const numeric={error_code:'VAL_ENTRADA',message:'Errores de validacion en la solicitud',fields:[{field:'estado_retroalimentacion',message:'El valor ingresado debe ser un texto.'}]};
      if(modo==='un_5xx'&&key==='207-omitido')return send(res,503,{error_code:'ERROR_INTERNO'},run);
      if(modo==='correcto_con_diag_rechazado'&&key==='209-correcto-con'||modo==='sin_evento_sin_diag_rechazado'&&key==='209-sin-evento-sin')
        return send(res,422,e4,run);
      if(key==='206-ausente'){
        if(modo==='ausente_aceptado')return send(res,201,persist('CORRECTO'),run);
        if(modo==='ausente_400_sin_campo')missing.fields=[{field:'otro',message:'Este campo es obligatorio.'}];
        return send(res,['comportamiento_codigo_actual','ausente_400_completo','ausente_400_sin_campo'].includes(modo)?400:422,missing,run);
      }
      if(key==='205-numerico'){
        if(['numerico_400','comportamiento_codigo_actual'].includes(modo))return send(res,400,numeric,run);
        return send(res,422,e3,run);
      }
      if(key==='205-minusculas'){
        if(['minusculas_aceptada','comportamiento_codigo_actual'].includes(modo))return send(res,201,persist('CORRECTO'),run);
        return send(res,422,e3,run);
      }
      if(key==='205-vacio'){
        if(modo==='vacio_aceptado')return send(res,201,persist(''),run);
        return send(res,422,e3,run);
      }
      if(key==='205-inexistente'){
        if(modo==='inexistente_aceptado')return send(res,201,persist(),run);
        if(modo==='estado_422_otro_mensaje'){
          e3.message='El diagnóstico clínico es obligatorio.';
          e3.fields[0].message=e3.message;
        }
        return send(res,422,e3,run);
      }
      if(key.startsWith('207-')||key.startsWith('208-')){
        const accept=['parcial_sin_lista_aceptado','parcial_vacia_aceptada','incorrecto_sin_lista_aceptado','incorrecto_vacia_aceptada'].includes(modo)
          && key===({'parcial_sin_lista_aceptado':'207-omitido','parcial_vacia_aceptada':'207-vacio',
            'incorrecto_sin_lista_aceptado':'208-omitido','incorrecto_vacia_aceptada':'208-vacio'}[modo]);
        if(accept)return send(res,201,persist(),run);
        if(modo==='parcial_400'&&key==='207-omitido')return send(res,400,e4,run);
        return send(res,422,e4,run);
      }
      return send(res,201,persist(),run);
    }
    return send(res,404,{error_code:'NO_ENCONTRADO'},run);
  });
  return {server,status:()=>({deleted,received})};
}
let passed=0;
for(const [modo,expected,official] of modos){
  const {server,status}=makeServer(modo);
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),`g067-${modo}-`));
  const c={version:1,runId:'RUN-G067-V1-20261029-000000',referencia:'ENSAYO_LOCAL',
    operacion:'evaluar',directorio:tmp,ensayo:true};
  try{
    let env={SIGAB_API_TEST_BASE:`http://127.0.0.1:${server.address().port}`,
      QA_SANDBOX_SECRET:'sandbox-local',QA_VETERINARIO_EMAIL:'vet@local.invalid',
      QA_COMMON_PASSWORD:'local',QA_AUTORIZADO:'SI'};
    if(modo==='env_archivo'){
      const file=path.join(tmp,'.env.qa');fs.writeFileSync(file,Object.entries(env)
        .filter(([k])=>k!=='QA_AUTORIZADO').map(([k,v])=>`${k}=${v}`).join('\n'),'utf8');
      env=leerEnv({QA_AUTORIZADO:'SI'},file);
    }
    const r=await evaluar(c,{env,...(modo==='newman_no_disponible'
      ? {newmanVersion:{ok:false,error:'NEWMAN_NO_DISPONIBLE'}} : {})});
    assert.deepEqual(CASOS.map(x=>r.casos[x].estado),expected,modo);
    assert.equal(r.oficial,official,modo);
    if(!['login_sin_red','newman_no_disponible'].includes(modo))assert.equal(status().deleted,true,modo);
    const present=new Set(fs.readdirSync(tmp));
    if(fs.existsSync(path.join(tmp,'newman')))for(const x of fs.readdirSync(path.join(tmp,'newman')))present.add(`newman/${x}`);
    assert.equal(clasificarRegistro(CAPACIDADES,r,present,{runId:c.runId,version:1}),official,modo);
    assert.ok(r.solicitudes.length<=PRESUPUESTO.solicitudes_totales,modo);
    assert.equal(r.cypress.total_pruebas,0,modo);
    assert.ok(r.registros.every(z=>!z.lista_enviada?.includes(7)),modo);
    const report=fs.readFileSync(path.join(tmp,'TC-M04-G067_resultado.md'),'utf8');
    assert.equal((report.match(/### TC-M04-/g)||[]).length,5,modo);
    assert.ok(report.includes('## Precondición de datos')&&report.includes('## Detalle por caso'),modo);
    assert.equal(/[\u00c3\u00c2\ufffd]/.test(report),false,modo);
    if(modo==='comportamiento_codigo_actual'){
      assert.deepEqual(r.incidencias.map(x=>[x.id,x.severidad]),[
        ['INC-M04-G067-205-01','BAJA'],['INC-M04-G067-205-02','BAJA']]);
      assert.ok(report.includes("'correcto' recibió HTTP 201 y se guardó como CORRECTO"));
      assert.ok(report.includes('205-numerico: HTTP 400 VAL_ENTRADA'));
      assert.ok(report.includes('Este campo es obligatorio.'));
      assert.ok(report.includes('209-sin-evento-con: HTTP, mensaje, historial y auditoría concordantes'));
      assert.ok(report.includes('| 205-minusculas |')&&report.includes('| 201 | — | sí |'));
      assert.equal(report.includes('| 201 | ?;'),false);
    }
    if(modo==='vacio_aceptado')assert.equal(r.incidencias.find(x=>x.clave==='205-vacio')?.severidad,'ALTA');
    if(modo==='vacio_aceptado')assert.notEqual(r.registros.find(z=>z.clave==='205-vacio').resultado,
      r.registros.find(z=>z.clave==='205-numerico').resultado);
    if(['todo_ok','duplicada_con_reemplazo','ventana_con_reemplazo','corte_con_cierre','post_clave_403','post_tres_5xx'].includes(modo)){
      assert.deepEqual(fs.readdirSync(path.join(tmp,'newman')).sort(),['newman-G067.html','newman-G067.json']);
      assert.deepEqual(r.evidencias.filter(x=>x.startsWith('newman/')).sort(),
        ['newman/newman-G067.html','newman/newman-G067.json']);
      assert.equal(r.herramientas.newman.ejecuciones,1);
      for(const f of fs.readdirSync(path.join(tmp,'newman'))){
        const txt=fs.readFileSync(path.join(tmp,'newman',f),'utf8');
        assert.equal(txt.includes('sandbox-local')||txt.includes('vet@local.invalid'),false);
      }
    }
    if(modo==='post_clave_403')assert.equal(status().received.length,1);
    if(modo==='post_tres_5xx')assert.equal(status().received.length,3);
    if(modo==='todo_ok'){
      assert.equal(status().received.length,13);
      assert.equal(r.herramientas.newman.ejecuciones,1);
      assert.equal(r.herramientas.newman.iteraciones,1);
      assert.equal(r.herramientas.newman.solicitudes,13);
      assert.equal(r.herramientas.newman.aserciones,26);
      assert.ok(report.includes('1 ejecución, 1 iteraciones, 13 solicitudes y 26 aserciones'));
    }
    if(modo==='comportamiento_codigo_actual')assert.equal(r.registros.find(z=>z.clave==='205-minusculas').estado_persistido,'CORRECTO');
    if(modo==='parcial_vacia_aceptada')assert.equal(r.registros.find(z=>z.clave==='208-omitido').veredicto.estado,'APROBADO');
    if(modo==='newman_no_disponible')assert.equal(r.solicitudes.length,0);
    console.log(`${modo}: ${expected.join('/')} ${official?'OFICIAL':'TÉCNICO'}`);passed++;
  } finally {
    server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
    fs.rmSync(tmp,{recursive:true,force:true});
  }
}
console.log(`OK G067: ${passed}/${modos.length} modos; presupuesto ${PRESUPUESTO.solicitudes_totales}; registro QA fiel; newman único verificado`);
