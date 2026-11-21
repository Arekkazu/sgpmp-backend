import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { evaluar, leerEnv } from '../g066.mjs';
import { CASOS, CAPACIDADES, PRESUPUESTO } from '../lib/g066_core.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const A=CASOS.map(()=> 'APROBADO');
const one=(i,state='RECHAZADO')=>A.map((x,j)=>i===j?state:x);
const NC='NO_CONCLUYENTE',BL='BLOQUEADO';
const modos=[
  ['todo_ok',A,true],['una_patologia_con_extra',one(0),true],['orden_alterado',one(1),true],
  ['tres_rechazadas',one(1),true],['post5xx_201',one(1),true],['lista2_rechazada',one(2),true],
  ['lista4_aceptada',one(2),true],['lista4_400_completo',A,true],
  ['lista4_sin_maximo',one(2),true],['lista4_persiste',one(2),true],
  ['inexistente_201',one(3),true],['mixta_persiste_validas',one(3),true],
  ['inexistente_400',one(3),true],['inactiva_201',one(4),true],
  ['inactiva_400',one(4),true],['sin_inactiva_con_contingencia',A,true],
  ['sin_inactiva_contingencia_sin_rollback',A,false],
  ['sin_inactiva_sin_contingencia',one(4,NC),false],
  ['datos_insuficientes',[A[0],A[1],NC,NC,NC],false],
  ['env_archivo',A,true],['login_lento',A,true],
  ['login_sin_red',CASOS.map(()=>BL),false],['clave_403',CASOS.map(()=>BL),false],
  ['newman_no_disponible',CASOS.map(()=>BL),false],
  ['error5xx',CASOS.map(()=>BL),false],
  ['sin_respuesta',[A[0],A[1],A[2],NC,NC],false],
  ['corte_con_cierre',[A[0],NC,NC,NC,NC],false],
  ['duplicada_con_reemplazo',A,true],['ventana_con_reemplazo',A,true]
];
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const read=req=>new Promise(resolve=>{const parts=[];req.on('data',x=>parts.push(x));req.on('end',()=>resolve(Buffer.concat(parts).toString('utf8')));});
const send=(res,http,body,run)=>{res.writeHead(http,{'Content-Type':'application/json',...(run?{'X-Test-Run-Id':run}:{})});res.end(JSON.stringify(body));};
function makeServer(modo){
  const qty=modo==='datos_insuficientes'?4:14;
  const inferencias=Array.from({length:qty},(_,i)=>({id_evento:id(i+1),id_resultado_inferencia:id(i+1),
    id_activo_biologico:885,tipo_evento:'INFERENCIA',fecha_evento:new Date(Date.now()-86400000+i*60000).toISOString(),
    payload:{id_patologia:7,tipo_modelo:'MODELO_ESPECIES_MEDIANAS',id_version_modelo:43}}));
  const patologias=Array.from({length:8},(_,i)=>({id_patologia:i+7,especie_aplicable:'TODAS',es_activo:true,es_base:true}));
  if(modo.startsWith('sin_inactiva'))patologias.push({id_patologia:21,especie_aplicable:'TODAS',es_activo:true,
    es_base:modo==='sin_inactiva_sin_contingencia'});
  else patologias.push({id_patologia:30,especie_aplicable:'TODAS',es_activo:false,es_base:false});
  const retros=[],audit=[],received=[];let closed=false,deleted=false,duplicate=false,window=false,errors=0;
  const server=http.createServer(async(req,res)=>{
    const u=new URL(req.url,'http://127.0.0.1'),run=req.headers['x-test-run-id'];
    const body=req.method==='POST'?JSON.parse((await read(req))||'{}'):{};
    if(u.pathname==='/sesiones/'&&req.method==='POST'){
      if(modo==='login_sin_red'){req.socket.destroy();return;}
      if(modo==='login_lento')await new Promise(resolve=>setTimeout(resolve,150));
      return send(res,200,{token:`local.${Buffer.from(JSON.stringify({sub:'900'})).toString('base64url')}.firma`});
    }
    if(u.pathname.startsWith('/test-control/runs/')&&req.method==='DELETE'){
      closed=true;deleted=true;
      if(modo!=='sin_inactiva_contingencia_sin_rollback')
        for(const p of patologias)if(p.id_patologia===21)p.es_activo=true;
      return send(res,200,{status:'ok'});
    }
    if(modo==='clave_403'&&run)return send(res,403,{error_code:'CLAVE_INVALIDA'},run);
    if(u.pathname==='/activos-biologicos')return send(res,200,{registros:
      (modo==='error5xx'?[885,886,887]:[885]).map(n=>({id_activo_biologico:n,id_especie:220,tipo:'INDIVIDUAL'})),
      total_paginas:1,total_registros:modo==='error5xx'?3:1},run);
    if(u.pathname.startsWith('/prediccion/historial/')){
      if(modo==='error5xx'&&errors++<3)return send(res,500,{error_code:'ERROR_INTERNO'},run);
      const events=[...inferencias,...(closed?[]:retros)];
      return send(res,200,{eventos:events,cursor_siguiente:null,total_pagina:events.length},run);
    }
    if(u.pathname==='/prediccion/patologias'&&req.method==='GET')return send(res,200,{total:patologias.length,items:patologias},run);
    if(/^\/prediccion\/patologias\/\d+$/.test(u.pathname)&&req.method==='GET'){
      const p=patologias.find(x=>x.id_patologia===Number(u.pathname.split('/').at(-1)));
      return send(res,p?200:404,p??{error_code:'PATOLOGIA_NO_ENCONTRADA'},run);
    }
    if(u.pathname.endsWith('/desactivar')&&req.method==='PATCH'){
      const n=Number(u.pathname.split('/').at(-2)),p=patologias.find(x=>x.id_patologia===n);
      if(!p||p.es_base)return send(res,405,{error_code:'PATOLOGIA_BASE_INMUTABLE'},run);
      p.es_activo=false;return send(res,200,p,run);
    }
    if(u.pathname==='/prediccion/auditoria'){
      let items=audit;
      if(u.searchParams.has('id_referencia'))items=items.filter(x=>x.id_referencia===u.searchParams.get('id_referencia'));
      return send(res,200,{total:items.length,items},run);
    }
    if(u.pathname==='/prediccion/retroalimentacion'&&req.method==='POST'){
      const key=String(body.observaciones_clinicas||'').replace('QA G066 ','');received.push(key);
      if(modo==='duplicada_con_reemplazo'&&!duplicate){duplicate=true;return send(res,409,{error_code:'RETROALIMENTACION_DUPLICADA'},run);}
      if(modo==='ventana_con_reemplazo'&&!window){window=true;return send(res,422,{error_code:'FUERA_DE_VENTANA_TEMPORAL'},run);}
      if((modo==='sin_respuesta'&&key==='203-inexistente')||(modo==='corte_con_cierre'&&key==='201-tres')){
        req.socket.destroy();return;
      }
      if(modo==='post5xx_201'&&key==='201-tres')return send(res,503,{error_code:'BD_NO_DISPONIBLE'},run);
      if(modo==='tres_rechazadas'&&key==='201-tres'||modo==='lista2_rechazada'&&key==='202-dos')
        return send(res,422,{error_code:'DIAGNOSTICO_NO_VALIDO',message:'La patologia no es valida o no esta activa.'},run);
      const four=key==='202-cuatro',missing=key.startsWith('203-'),inactive=key==='204-inactiva';
      const realFour={error_code:'VAL_ENTRADA',message:'Errores de validacion en la solicitud',
        fields:[{field:'diagnosticos_reales',message:'List should have at most 3 items after validation, not 4'}]};
      const realInvalid={error_code:'DIAGNOSTICO_NO_VALIDO',message:'La patologia con id no es valida o no esta activa en el sistema.',
        fields:[{field:'diagnosticos_reales',message:'La patologia no es valida o no esta activa.'}]};
      const persist=(responseList=body.diagnosticos_reales)=>{
        const rid=id(100+retros.length+1),response={...body,id_retroalimentacion:rid,
          diagnosticos_reales:responseList,id_usuario_veterinario:900,estado_registro:'ACTIVO',
          fecha_retroalimentacion:new Date().toISOString()};
        retros.push({id_evento:rid,id_resultado_inferencia:body.id_resultado_inferencia,
          id_activo_biologico:885,tipo_evento:'RETROALIMENTACION',fecha_evento:response.fecha_retroalimentacion,
          payload:{id_usuario_veterinario:900,diagnosticos_reales:responseList}});
        audit.push({tipo_evento:'RETROALIMENTACION_REGISTRADA',id_referencia:rid,
          payload_evento:{id_resultado_inferencia:body.id_resultado_inferencia,diagnosticos_reales:responseList}});
        return response;
      };
      if(four&&modo==='lista4_persiste'){persist();return send(res,400,realFour,run);}
      if(key==='203-mixta'&&modo==='mixta_persiste_validas'){
        persist(body.diagnosticos_reales.slice(0,2));return send(res,422,realInvalid,run);
      }
      if(four&&!['lista4_aceptada'].includes(modo)){
        if(modo==='lista4_sin_maximo')realFour.fields[0].message='Invalid diagnosticos_reales';
        return send(res,400,realFour,run);
      }
      if((missing||inactive)&&!((modo==='inexistente_201'&&key==='203-inexistente')
        ||(modo==='inactiva_201'&&inactive))){
        const wrong=(missing&&modo==='inexistente_400')||(inactive&&modo==='inactiva_400');
        return send(res,wrong?400:422,realInvalid,run);
      }
      let list=body.diagnosticos_reales;
      if(key==='200-una'&&modo==='una_patologia_con_extra')list=[...list,8];
      if(key==='201-tres'&&modo==='orden_alterado')list=[...list].reverse();
      return send(res,201,persist(list),run);
    }
    return send(res,404,{error_code:'NO_ENCONTRADO'},run);
  });
  return {server,status:()=>({deleted,received})};
}
let passed=0;
for(const [modo,expected,official] of modos){
  const {server,status}=makeServer(modo);
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),`g066-${modo}-`));
  const c={version:1,runId:'RUN-G066-V1-20261029-000000',referencia:'ENSAYO_LOCAL',
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
    if(fs.existsSync(path.join(tmp,'newman')))for(const x of fs.readdirSync(path.join(tmp,'newman')))
      present.add(`newman/${x}`);
    assert.equal(clasificarRegistro(CAPACIDADES,r,present,{runId:c.runId,version:1}),official,modo);
    assert.ok(r.solicitudes.length<=PRESUPUESTO.solicitudes_totales,modo);
    assert.equal(r.cypress.total_pruebas,0,modo);
    if(modo==='newman_no_disponible'){
      assert.equal(r.solicitudes.length,0);
      assert.equal(fs.existsSync(path.join(tmp,'newman')),false);
      assert.ok(r.problemas_tecnicos.some(x=>x.includes('NEWMAN_NO_DISPONIBLE')));
    }
    const report=fs.readFileSync(path.join(tmp,'TC-M04-G066_resultado.md'),'utf8');
    assert.equal((report.match(/### TC-M04-/g)||[]).length,5,modo);
    assert.ok(report.includes('## Precondici'),modo);
    assert.equal(report.includes('concordantes'),false,`detalle ${modo}`);
    assert.equal(report.includes('Observaciones: ninguna'),false,`observaciones ${modo}`);
    assert.ok(r.registros.every(z => !z.lista_enviada?.includes(7)),`selección sin patología 7 ${modo}`);
    if(modo==='todo_ok'||modo==='lista4_400_completo'){
      assert.ok(report.includes('OBS-M04-G066-202'),modo);
      assert.equal(report.includes('Se usó la patología 7'),false,modo);
      assert.deepEqual(r.registros.find(z=>z.clave==='200-una')?.lista_enviada,[8],`preferencia 8-14 ${modo}`);
    }
    if(modo==='lista4_400_completo'){
      assert.ok(report.includes('| TC-M04-202 | APROBADO con observación |'),modo);
      assert.ok(report.includes('### TC-M04-202 — APROBADO con observación'),modo);
      assert.ok(report.includes('- Por qué APROBADO con observación:')
        && report.includes('OBS-M04-G066-202: HTTP 400 en lugar del 422 recomendado'),modo);
      const observaciones=report.split('## Observaciones\n\n')[1].split('\n\n## Incidencias')[0];
      assert.equal(observaciones.split('\n').filter(x=>x.startsWith('- ')).length,2,modo);
      assert.ok(observaciones.includes('RF-72 exige que la patología exista y esté activa en el catálogo (4067-4068, 4163); no exige que corresponda a la especie del activo, y el sistema no lo comprueba.'),modo);
    }
    assert.equal(/[\u00c3\u00c2\ufffd]/.test(report),false,`encoding ${modo}`);
    if(modo==='todo_ok'){
      assert.equal(status().received.length,9);
      assert.equal(r.herramientas.newman.iteraciones,9);
      assert.equal(r.herramientas.newman.solicitudes,9);
      assert.equal(r.herramientas.newman.aserciones,18);
      assert.ok(report.includes('9 iteraciones, 9 solicitudes y 18 aserciones'));
      const archivos=fs.readdirSync(path.join(tmp,'newman'));
      assert.equal(archivos.filter(x=>x.endsWith('.json')).length,9);
      assert.equal(archivos.filter(x=>x.endsWith('.html')).length,9);
      for(const archivo of archivos){
        const contenido=fs.readFileSync(path.join(tmp,'newman',archivo),'utf8');
        assert.equal(contenido.includes('sandbox-local'),false);
        assert.equal(contenido.includes('vet@local.invalid'),false);
        assert.ok(contenido.includes('Newman'));
      }
      const cuatro=JSON.parse(fs.readFileSync(path.join(tmp,'newman','newman-G066-POST-202-4.json'),'utf8'));
      assert.equal(cuatro.http,400);
      assert.ok(cuatro.respuesta.detalle_campo.includes('at most 3'));
    }
    if(modo==='login_lento')assert.ok(r.solicitudes[0].duracion_ms>=100);
    if(modo==='sin_inactiva_con_contingencia')assert.equal(r.cierre.catalogo?.restaurada,true);
    if(modo==='sin_inactiva_contingencia_sin_rollback'){
      assert.equal(r.cierre.catalogo?.restaurada,false);
      assert.ok(report.startsWith('# TC-M04-G066 — NO_CONCLUYENTE'));
    }
    console.log(`${modo}: ${expected.join('/')} ${official?'OFICIAL':'TECNICO'}`);passed++;
  } finally {
    server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
    fs.rmSync(tmp,{recursive:true,force:true});
  }
}
console.log(`OK G066: ${passed}/${modos.length} modos; presupuesto ${PRESUPUESTO.solicitudes_totales}; registro QA fiel; newman verificado`);
