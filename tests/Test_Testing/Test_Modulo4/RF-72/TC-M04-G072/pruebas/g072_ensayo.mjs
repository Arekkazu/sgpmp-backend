import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {evaluar,leerEnv,contextoVersionValido} from '../g072.mjs';
import {CASOS,CAPACIDADES,PRESUPUESTO} from '../lib/g072_core.mjs';
import {clasificarRegistro} from './registro_qa.mjs';

const id=i=>{const h=Number(i).toString(16);return `${h.padStart(8,'0')}-${h.padStart(4,'0')}-4${h.padStart(3,'0')}-8${h.padStart(3,'0')}-${h.padStart(12,'0')}`;};
const resultados=Array.from({length:9},(_,i)=>id(i+1));
for(const operacion of ['reevaluar','reintentar']){
  assert.equal(contextoVersionValido({version_anterior:1,alcance_reevaluacion:{casos:CASOS}},operacion,2),true);
  assert.equal(contextoVersionValido({version_anterior:1},operacion,2),false);
  assert.equal(contextoVersionValido({version_anterior:2,alcance_reevaluacion:{casos:CASOS}},operacion,2),false);
}
const modos=[
  ['v2_corregido',{v2:true},{}],
  ['v2_reintento',{v2:true,reintento:true},{}],
  ['v2_defecto',{v2:true,hist500:'230a'},{0:'RECHAZADO',1:'RECHAZADO',2:'RECHAZADO'}],
  ['aislamiento_falla',{v2:true,aislamientoFalla:true},{}],
  ['sin_activo_ajeno',{v2:true,sinActivoAjeno:true},{}],
  ['historial_sin_500',{},{}],['historial_paginado',{muchas:true},{}],['sin_flag_conflicto',{sinFlag:true},{0:'RECHAZADO'}],
  ['sin_evento_conflicto',{sinEvento:true},{0:'RECHAZADO'}],['evento_sin_referencia',{eventoSinRef:true},{0:'RECHAZADO'}],
  ['b_rechazado',{bRechazado:true},{0:'RECHAZADO'}],['a_modificado',{aModificado:true},{0:'RECHAZADO'}],
  ['registro_eliminado_227',{eliminado227:true},{1:'RECHAZADO'}],['registro_modificado_227',{modificado227:true},{1:'RECHAZADO'}],
  ['registro_consolidado_227',{consolidado227:true},{1:'RECHAZADO'}],['c_rechazado',{cRechazado:true},{1:'RECHAZADO'}],
  ['conflicto_iguales_correcto',{conflictoIgualCorrecto:true},{2:'RECHAZADO'}],
  ['conflicto_iguales_incorrecto',{conflictoIgualIncorrecto:true},{2:'RECHAZADO'}],
  ['evento_iguales',{eventoIguales:true},{2:'RECHAZADO'}],
  ['mismo_grupo_sin_conflicto',{mismoGrupo:true},{}],
  ['login_c_falla',{loginCFalla:true},{1:'NO_CONCLUYENTE'}],
  ['login_b_falla',{loginBFalla:true},{0:'NO_CONCLUYENTE',1:'NO_CONCLUYENTE',2:'NO_CONCLUYENTE'}],
  ['auditoria_no_disponible',{auditoriaFalla:true},{0:'BLOQUEADO',1:'BLOQUEADO',2:'BLOQUEADO'}],
  ['resultado_previo_con_retro',{ocupado:true},{}],['un_5xx',{un5xx:true},{1:'RECHAZADO'}],
  ['historial_500_tras_230a',{hist500:'230a'},{0:'RECHAZADO',1:'RECHAZADO',2:'RECHAZADO'}],
  ['historial_500_tras_230b',{hist500:'230b'},{0:'RECHAZADO',1:'RECHAZADO',2:'RECHAZADO'}],
  ['historial_500_tras_226',{hist500:'226'},{0:'RECHAZADO',1:'RECHAZADO'}],
  ['historial_500_tras_227_parcial',{hist500:'227_parcial'},{1:'RECHAZADO'}],
  ['historial_500_tras_227_final',{hist500:'227_final'},{1:'RECHAZADO'}],
  ['historial_500_transitorio',{hist500:'230a',hist500Transitorio:true},{2:'RECHAZADO'}],
  ['ambiente_caido',{ambienteCaido:true},{0:'BLOQUEADO',1:'BLOQUEADO',2:'BLOQUEADO'}],
  ['tres_5xx',{tres5xx:true},{0:'BLOQUEADO',1:'BLOQUEADO',2:'BLOQUEADO'}],
  ['datos_insuficientes',{pocos:true},{0:'NO_CONCLUYENTE',1:'NO_CONCLUYENTE',2:'NO_CONCLUYENTE'}],
  ['env_archivo',{envArchivo:true},{}],['env_sin_c',{envSinC:true},{0:'NO_CONCLUYENTE',1:'NO_CONCLUYENTE',2:'NO_CONCLUYENTE'}],
  ['login_lento',{loginLento:true},{}],['login_sin_red',{loginSinRed:true},{0:'BLOQUEADO',1:'BLOQUEADO',2:'BLOQUEADO'}],
  ['clave_403',{clave403:true},{0:'BLOQUEADO',1:'BLOQUEADO',2:'BLOQUEADO'}],
  ['sin_respuesta',{sinRespuesta:true},{1:'NO_CONCLUYENTE'}],
  ['corte_con_cierre',{corte:true},{1:'NO_CONCLUYENTE'}],
  ['newman_no_disponible',{newmanNo:true},{0:'BLOQUEADO',1:'BLOQUEADO',2:'BLOQUEADO'}],
];
function servidor(m,s){return http.createServer(async(req,res)=>{
  const u=new URL(req.url,'http://127.0.0.1');
  const enviar=(status,body,eco=true)=>{res.writeHead(status,{'Content-Type':'application/json','Connection':'close',
    ...(eco?{'X-Test-Run-Id':req.headers['x-test-run-id']??''}:{})});res.end(JSON.stringify(body));};
  let cuerpo={};if(req.method==='POST'){let raw='';for await(const b of req)raw+=b;try{cuerpo=JSON.parse(raw);}catch{}}
  if(u.pathname==='/sesiones/'&&req.method==='POST'){
    s.logins++;if(m.loginLento)await new Promise(ok=>setTimeout(ok,50));
    if(m.loginSinRed&&s.logins===1){req.socket.destroy();return;}
    const correo=String(cuerpo.correo_electronico??'');
    if(m.loginBFalla&&correo==='b@local.test'||m.loginCFalla&&correo==='c@local.test'){enviar(401,{error_code:'NO_AUTORIZADO'},false);return;}
    const sub=correo==='a@local.test'?91:correo==='b@local.test'?162:correo==='c@local.test'?163:1;
    enviar(200,{token:`e30.${Buffer.from(JSON.stringify({sub})).toString('base64url')}.firma`},false);return;
  }
  if(req.method==='DELETE'&&u.pathname.startsWith('/test-control/runs/')){
    s.cierres++;s.retros=[];s.audit=[];s.cerrado=true;enviar(200,{status:'Rollback exitoso'},false);return;
  }
  if(m.clave403&&req.headers['x-test-run-id']){enviar(403,{error_code:'CLAVE_INVALIDA',message:'Clave sandbox inválida'});return;}
  if(u.pathname==='/configuracion/fincas'){
    enviar(200,{total:3,items:[{id_finca:84},{id_finca:184},{id_finca:185}]});return;}
  if(u.pathname==='/configuracion/infraestructuras'){
    enviar(200,{total:1,items:[{id_infraestructura:300,id_finca:185}]});return;}
  if(u.pathname==='/activos-biologicos'){
    enviar(200,{total_registros:m.sinActivoAjeno?0:1,registros:m.sinActivoAjeno?[]:[{id_activo_biologico:999,id_infraestructura:300}]});return;}
  if(u.pathname==='/prediccion/historial/999'){
    if(m.aislamientoFalla)enviar(200,{eventos:[{tipo_evento:'INFERENCIA',id_activo_biologico:999}],cursor_siguiente:null});
    else enviar(403,{error_code:'SIN_ACCESO'});return;}
  if(u.pathname==='/prediccion/patologias'){enviar(200,{total:7,items:Array.from({length:7},(_,i)=>({id_patologia:i+8,es_activo:true}))});return;}
  if(u.pathname==='/prediccion/modelos/43'){enviar(200,{id_version_modelo:43,tipo_modelo:'MODELO_ESPECIES_MEDIANAS',paradigma:'INDIVIDUAL'});return;}
  if(u.pathname==='/prediccion/historial/885'){
    s.historiales++;
    s.historialConsultas.push({fecha_inicio:u.searchParams.get('fecha_inicio'),fecha_fin:u.searchParams.get('fecha_fin'),
      incluir_alertas:u.searchParams.get('incluir_alertas'),autorizacion:!!req.headers.authorization});
    const etapa={2:'230a',4:'230b',6:'226',8:'227_parcial',9:'227_final'}[s.posts];
    if((m.ambienteCaido&&s.posts>=2||m.tres5xx&&s.posts===2)&&!s.cerrado){enviar(500,{error_code:'ERROR_INTERNO',message:'Ocurrió un error interno.'});return;}
    const etapas=['230a','230b','226','227_parcial','227_final'];
    if(m.hist500&&etapas.indexOf(etapa)>=etapas.indexOf(m.hist500)&&!s.cerrado&&
      (!m.hist500Transitorio||!m.hist500Visto)){
      m.hist500Visto=true;enviar(500,{error_code:'ERROR_INTERNO',message:'Ocurrió un error interno.'});return;}
    const idsInfer=m.pocos?resultados.slice(0,3):m.muchas?[...resultados,...Array.from({length:55},(_,i)=>id(i+100))]:resultados;
    const infer=idsInfer.map((x,i)=>({id_evento:x,tipo_evento:'INFERENCIA',id_activo_biologico:885,
      id_resultado_inferencia:x,fecha_evento:new Date(s.inicio-(i+1)*86400000).toISOString(),
      payload:{tipo_modelo:'MODELO_ESPECIES_MEDIANAS',id_version_modelo:43,id_patologia:8}}));
    const retros=s.retros.filter(x=>!m.eliminado227||x.resultado!==s.seleccion?.[1]||x.usuario!==162).map(x=>({
      id_evento:x.id,tipo_evento:'RETROALIMENTACION',id_activo_biologico:885,id_resultado_inferencia:x.resultado,fecha_evento:x.fecha,
      payload:{id_retroalimentacion:x.id,estado_retroalimentacion:m.aModificado&&x.resultado===s.seleccion?.[0]&&x.usuario===91||
        m.modificado227&&x.resultado===s.seleccion?.[1]&&x.usuario===162?'SIN_EVENTO':x.estado,
        diagnosticos_reales:x.diagnosticos,id_usuario_veterinario:x.usuario,es_conflicto_retroalimentacion:x.conflicto}}));
    if(m.ocupado)retros.push({id_evento:id(50),tipo_evento:'RETROALIMENTACION',id_activo_biologico:885,
      id_resultado_inferencia:resultados[0],fecha_evento:new Date(s.inicio).toISOString(),
      payload:{id_retroalimentacion:id(50),estado_retroalimentacion:'CORRECTO',diagnosticos_reales:null,id_usuario_veterinario:900}});
    if(m.consolidado227&&s.posts>=9&&!s.cerrado)retros.push({id_evento:id(51),tipo_evento:'RETROALIMENTACION',id_activo_biologico:885,
      id_resultado_inferencia:s.seleccion?.[1],fecha_evento:new Date(s.inicio+20000).toISOString(),
      payload:{id_retroalimentacion:id(51),estado_retroalimentacion:'CORRECTO',diagnosticos_reales:null,id_usuario_veterinario:0}});
    const todos=[...infer,...retros].sort((a,b)=>Date.parse(b.fecha_evento)-Date.parse(a.fecha_evento));
    const offset=Number(u.searchParams.get('cursor_paginacion')??0),pagina=todos.slice(offset,offset+50);
    enviar(200,{eventos:pagina,cursor_siguiente:offset+50<todos.length?String(offset+50):null});return;
  }
  if(u.pathname==='/prediccion/auditoria'){
    if(m.ambienteCaido&&s.posts>=2){enviar(500,{error_code:'ERROR_INTERNO',message:'Auditoría no disponible'});return;}
    if(m.auditoriaFalla){enviar(503,{message:'Auditoría no disponible'});return;}
    const ref=u.searchParams.get('id_referencia'),items=s.audit.filter(x=>x.id_referencia===ref);
    enviar(200,{total:items.length,pagina:1,por_pagina:200,items});return;
  }
  if(u.pathname==='/prediccion/retroalimentacion'&&req.method==='POST'){
    s.posts++;s.seleccion??=[];
    for(const [n,i] of [[1,2],[3,3],[5,0],[7,1]])if(s.posts===n)s.seleccion[i]=cuerpo.id_resultado_inferencia;
    if(m.sinRespuesta&&s.posts===8||m.corte&&s.posts===8){req.socket.destroy();return;}
    if(m.ambienteCaido&&s.posts>=3||m.tres5xx&&s.posts<=3||m.un5xx&&s.posts===8){enviar(503,{error_code:'ERROR',message:'Fallo local'});return;}
    if(m.bRechazado&&s.posts===6||m.cRechazado&&s.posts===9){enviar(409,{error_code:'RECHAZADO'});return;}
    const token=req.headers.authorization?.split(' ')[1],usuario=JSON.parse(Buffer.from(token.split('.')[1],'base64url')).sub;
    const result=cuerpo.id_resultado_inferencia,estado=cuerpo.estado_retroalimentacion;
    const pares=s.retros.filter(x=>x.resultado===result&&x.usuario!==usuario);
    const sin=new Set(['CORRECTO','SIN_EVENTO']),con=new Set(['PARCIAL','INCORRECTO']);
    const todos=[...pares.map(x=>x.estado),estado];let conflicto=todos.some(x=>sin.has(x))&&todos.some(x=>con.has(x));
    const indice=s.seleccion?.indexOf(result);
    if(m.conflictoIgualCorrecto&&indice===2&&usuario===162||m.conflictoIgualIncorrecto&&indice===3&&usuario===162)conflicto=true;
    const rid=id(s.posts+20),x={id:rid,resultado:result,fecha:new Date(s.inicio+s.posts*1000).toISOString(),estado,
      diagnosticos:cuerpo.diagnosticos_reales??null,usuario,conflicto};s.retros.push(x);
    s.audit.push({id_evento:id(s.posts+60),tipo_evento:'RETROALIMENTACION_REGISTRADA',id_referencia:rid,
      payload_evento:{id_retroalimentacion:rid}});
    if(conflicto||m.eventoIguales&&indice===2&&usuario===162){
      if(!(m.sinEvento&&indice===0))s.audit.push({id_evento:id(s.posts+100),tipo_evento:'CONFLICTO_RETROALIMENTACION',
        id_referencia:m.eventoSinRef&&indice===0?resultados[8]:result,tipo_actor:'SISTEMA',
        payload_evento:{id_resultado_inferencia:result,activo_biologico_id:885,numero_retroalimentaciones:pares.length+1,
          estados_registrados:todos,nueva_retroalimentacion:rid}});
    }
    const flag=m.sinFlag&&indice===0&&usuario===162?false:m.mismoGrupo&&indice===1&&usuario===163?false:conflicto;
    enviar(201,{id_retroalimentacion:rid,id_resultado_inferencia:result,id_activo_biologico:885,
      estado_retroalimentacion:estado,diagnosticos_reales:x.diagnosticos,id_usuario_veterinario:usuario,
      es_conflicto_retroalimentacion:flag,fecha_retroalimentacion:x.fecha});return;
  }
  enviar(404,{detail:'Not Found'});
});}
const base={QA_AUTORIZADO:'SI',QA_SANDBOX_SECRET:'secreto-local',QA_VETERINARIO_EMAIL:'a@local.test',
  QA_VETERINARIO_B_EMAIL:'b@local.test',QA_VETERINARIO_C_EMAIL:'c@local.test',QA_ADMIN_EMAIL:'admin@local.test',QA_COMMON_PASSWORD:'clave-local'};
let aprobados=0;
for(const [nombre,m,esperados] of modos){
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g072-ensayo-'));
  const state={inicio:Date.now(),logins:0,posts:0,cierres:0,historiales:0,historialConsultas:[],retros:[],audit:[]};
  const server=servidor(m,state);await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  try{
    const version=m.v2?2:1,runId=`RUN-G072-V${version}-20261029-000000`;
    const c={ensayo:true,runId,version,intento:1,referencia:'ENSAYO-LOCAL',
      operacion:m.reintento?'reintentar':m.v2?'reevaluar':'evaluar',version_anterior:m.v2?1:null,
      alcance_reevaluacion:m.v2?{casos:CASOS,control_aislamiento:true}:null,
      directorio:path.join(tmp,runId)};
    const env={...base,SIGAB_API_TEST_BASE:`http://127.0.0.1:${server.address().port}`};
    if(m.envSinC)delete env.QA_VETERINARIO_C_EMAIL;
    if(m.envArchivo){const archivo=path.join(tmp,'.env.qa');fs.writeFileSync(archivo,Object.entries(env).filter(([k])=>k!=='QA_AUTORIZADO').map(([k,v])=>`${k}=${v}`).join('\n'));
      Object.assign(env,leerEnv({QA_AUTORIZADO:'SI'},archivo));}
    const r=await evaluar(c,{env,newmanVersion:m.newmanNo?{ok:false,error:'NEWMAN_NO_DISPONIBLE'}:{ok:true,version:'6.2.2'}});
    if(m.v2){assert.equal(c.version_anterior,1);assert.ok(c.alcance_reevaluacion);
      assert.ok(['reevaluar','reintentar'].includes(c.operacion));}
    for(const [i,x] of CASOS.entries())assert.equal(r.casos[x].estado,esperados[i]??'APROBADO',`${nombre} ${x}: ${r.casos[x].motivo}`);
    assert.ok(r.solicitudes.length<=PRESUPUESTO.solicitudes_totales,`${nombre} presupuesto`);
    assert.ok(state.historialConsultas.every(x=>/^\d{4}-\d{2}-\d{2}$/.test(x.fecha_inicio)&&/^\d{4}-\d{2}-\d{2}$/.test(x.fecha_fin)&&
      x.incluir_alertas==='false'&&x.autorizacion),`${nombre} parámetros historial y Veterinario A`);
    assert.equal(state.logins,m.newmanNo||m.envSinC?0:m.loginBFalla||m.loginSinRed?3:4,`${nombre} logins`);
    if(m.newmanNo||m.envSinC){assert.equal(r.solicitudes.length,0);assert.equal(fs.existsSync(c.directorio),false);}
    else if(m.loginBFalla){assert.equal(state.posts,0);assert.equal(state.cierres,0);}
    else if(m.loginSinRed){assert.equal(state.posts,0);assert.equal(state.cierres,0);}
    else {assert.equal(state.cierres,1,`${nombre} DELETE`);assert.ok(r.cierre.run.cierre_http===200);}
    if(fs.existsSync(c.directorio)){
      const files=fs.readdirSync(c.directorio),result=JSON.parse(fs.readFileSync(path.join(c.directorio,'resultado.json'),'utf8'));
      assert.deepEqual(result.casos,r.casos);assert.equal(files.filter(x=>x.endsWith('.md')).length,1);
      const informe=version===1?'TC-M04-G072_resultado.md':'TC-M04-G072_reevaluacion_V2.md';
      const md=fs.readFileSync(path.join(c.directorio,informe),'utf8');
      for(const x of CASOS){assert.ok(md.includes(x));assert.ok(md.includes('Qué se hizo:'));assert.ok(md.includes('Qué se esperaba:'));assert.ok(md.includes('Qué se observó:'));assert.ok(md.includes('Por qué '));}
      assert.ok(md.includes('Decisión del caso')&&md.includes('Qué falta:')&&md.includes('Detalle por caso'));
      assert.ok(md.includes('Lecturas del historial')&&md.includes('Historial de intentos'));
      assert.ok(!md.includes('..')&&!md.includes('a@local.test')&&!md.includes('b@local.test')&&!md.includes('c@local.test'));
      if(m.v2){assert.ok(!/matriz/i.test(md),`${nombre} sin mención de matriz`);
        assert.ok(md.includes('Issue #869 / PR #871')&&md.includes('V1 → V2'));
        assert.ok(md.includes('Control complementario de aislamiento RF-67'));}
      if(files.includes('newman')){
        assert.deepEqual(fs.readdirSync(path.join(c.directorio,'newman')).sort(),['newman-G072.html','newman-G072.json']);
        const n=fs.readFileSync(path.join(c.directorio,'newman','newman-G072.json'),'utf8');assert.ok(!n.includes('a@local.test')&&!n.includes('secreto-local'));
      }
      const presentes=new Set([...files,...(files.includes('newman')?['newman/newman-G072.json','newman/newman-G072.html']:[])]);
      if(r.oficial){assert.equal(clasificarRegistro(CAPACIDADES,result,presentes,c),true,`${nombre} registro QA`);aprobados++;}
    }
    if(nombre==='resultado_previo_con_retro')assert.notEqual(r.semilla.resultados[0].id,resultados[0]);
    if(nombre==='mismo_grupo_sin_conflicto')assert.ok(r.observaciones.some(x=>x.includes('OBS-M04-G072-227')));
    if(nombre.startsWith('historial_500_')){
      const md=fs.readFileSync(path.join(c.directorio,'TC-M04-G072_resultado.md'),'utf8');
      assert.equal(state.posts,9,`${nombre} continúa POST`);
      assert.equal(r.lecturas_historial.length,5,`${nombre} cinco lecturas`);
      const primero=r.lecturas_historial.find(x=>x.http===500);
      assert.equal(primero.momento,m.hist500,`${nombre} momento`);
      assert.equal(primero.codigo,'ERROR_INTERNO');
      assert.ok(r.incidencias.some(x=>x.caso===CASOS[Number(Object.keys(esperados)[0])]&&x.fundamento_derivacion.includes('HTTP 500')));
      assert.equal(r.incidencias.length,Object.keys(esperados).length,`${nombre} incidencias por caso afectado`);
      assert.ok(r.incidencias.every(x=>x.fundamento_derivacion.includes('HTTP 500')));
      assert.equal(r.oficial,true,`${nombre} RUN oficial`);
      const desde=['230a','230b','226','227_parcial','227_final'].indexOf(m.hist500);
      assert.deepEqual(r.lecturas_historial.map(x=>x.http),
        ['230a','230b','226','227_parcial','227_final'].map((_,i)=>i<desde||m.hist500Transitorio&&i>desde?200:500),`${nombre} persistencia`);
      assert.ok(md.includes(`Primera lectura HTTP 500: ${m.hist500}`),`${nombre} disparador informe`);
      assert.ok(md.includes(`tras ${primero.tras_post}, HTTP 500 ${primero.codigo}`),`${nombre} momento y código en incidencia`);
      assert.ok(!md.includes('reclasificar a BLOQUEADO')&&!md.includes('Causa raíz NO DETERMINADA'),`${nombre} sin reclasificación ni causa no determinada`);
      if(m.hist500Transitorio)assert.ok(r.observaciones.some(x=>x.includes('transitorio')));
      else {assert.ok(r.observaciones.some(x=>x.includes('persistente')||x.includes('última lectura')));
        assert.ok(md.includes(m.hist500==='227_final'?'persistencia no se confirmó':'persistió en todas las lecturas siguientes'));
      }
    }
    if(nombre==='v2_corregido'){
      assert.equal(r.control_aislamiento.estado,'APROBADO');assert.equal(r.casos['TC-M04-230'].estado,'APROBADO');
      assert.ok(fs.readFileSync(path.join(c.directorio,'TC-M04-G072_reevaluacion_V2.md'),'utf8').includes('CORREGIDA'));}
    if(nombre==='aislamiento_falla'){
      assert.equal(r.control_aislamiento.estado,'RECHAZADO');
      assert.ok(r.incidencias.some(x=>x.id==='INC-M04-G072-RF67-01'&&x.equipo==='Desarrollo'&&x.severidad==='CRÍTICA'));}
    if(nombre==='sin_activo_ajeno')assert.equal(r.control_aislamiento.estado,'NO_CONCLUYENTE');
    if(nombre==='historial_sin_500')assert.ok(r.observaciones.some(x=>x.includes('OBS-M04-G072-HIST')));
    if(nombre==='historial_paginado')assert.ok(r.lecturas_historial.every(x=>x.paginas>=2&&x.completo));
    if(nombre==='ambiente_caido'){assert.equal(state.posts,4);assert.ok(r.problemas_tecnicos.includes('TRES_5XX_CONSECUTIVOS'));assert.equal(r.oficial,false);}
    console.log(`${nombre}: ${CASOS.map(x=>r.casos[x].estado).join('/')} ${r.oficial?'OFICIAL':'TÉCNICO'}`);
  }finally{await new Promise(ok=>server.close(ok));fs.rmSync(tmp,{recursive:true,force:true});}
}
console.log(`OK G072: ${modos.length}/${modos.length} modos; presupuesto ${PRESUPUESTO.solicitudes_totales}; registro QA fiel; newman único verificado`);
