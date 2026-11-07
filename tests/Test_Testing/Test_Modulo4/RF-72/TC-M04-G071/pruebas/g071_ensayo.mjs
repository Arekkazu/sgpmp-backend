import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {evaluar,leerEnv} from '../g071.mjs';
import {CASOS,CAPACIDADES,PRESUPUESTO} from '../lib/g071_core.mjs';
import {clasificarRegistro} from './registro_qa.mjs';

const id=i=>`${String(i).repeat(8)}-${String(i).repeat(4)}-4${String(i).repeat(3)}-8${String(i).repeat(3)}-${String(i).repeat(12)}`;
const resultados=Array.from({length:8},(_,i)=>id(i+1));
const modos=[
  ['todo_ok',{},{}],['uuid_repetido',{uuidRepetido:true},{0:'RECHAZADO'}],
  ['uuid_invalido',{uuidInvalido:true},{0:'RECHAZADO'}],
  ['snapshot_cambia_riesgo',{riesgo:true},{1:'RECHAZADO'}],
  ['snapshot_cambia_probabilidades',{probabilidad:true},{1:'RECHAZADO'}],
  ['put_200',{put200:true},{2:'RECHAZADO'}],
  ['patch_modifica',{patchModifica:true},{2:'RECHAZADO'}],
  ['delete_204',{delete204:true},{2:'RECHAZADO'}],
  ['openapi_expone_edicion',{openapiEdita:true},{2:'RECHAZADO'}],
  ['campo_trazabilidad_nulo',{trazaNula:true},{3:'RECHAZADO'}],
  ['anonimo_aceptado',{anonimoAceptado:true},{3:'RECHAZADO'}],
  ['incompleto_aceptado',{incompletoAceptado:true},{3:'RECHAZADO'}],
  ['alerta_modificada',{alerta:true},{4:'RECHAZADO'}],
  ['version_cambia',{version:true},{4:'RECHAZADO'}],
  ['configuracion_cambia',{config:true},{4:'RECHAZADO'}],
  ['inferencia_nueva',{inferencia:true},{4:'RECHAZADO'}],
  ['resultado_246_cambia',{resultado246:true},{4:'RECHAZADO'}],
  ['lectura_alertas_no_disponible',{alertasFalla:true},{4:'NO_CONCLUYENTE'}],
  ['un_5xx',{un5xx:true},{1:'RECHAZADO'}],
  ['tres_5xx',{tres5xx:true},Object.fromEntries(CASOS.map((_,i)=>[i,'BLOQUEADO']))],
  ['datos_insuficientes',{pocos:true},Object.fromEntries(CASOS.map((_,i)=>[i,'NO_CONCLUYENTE']))],
  ['env_archivo',{envArchivo:true},{}],['login_lento',{loginLento:true},{}],
  ['login_sin_red',{loginSinRed:true},Object.fromEntries(CASOS.map((_,i)=>[i,'BLOQUEADO']))],
  ['clave_403',{clave403:true},Object.fromEntries(CASOS.map((_,i)=>[i,'BLOQUEADO']))],
  ['sin_respuesta',{sinRespuesta:true},{3:'NO_CONCLUYENTE'}],
  ['corte_con_cierre',{corte:true},{3:'NO_CONCLUYENTE'}],
  ['newman_no_disponible',{newmanNo:true},Object.fromEntries(CASOS.map((_,i)=>[i,'BLOQUEADO']))],
  ['historial_paginado',{paginado:true},{0:'NO_CONCLUYENTE',1:'NO_CONCLUYENTE',4:'NO_CONCLUYENTE'}],
];
function servidor(m,s){return http.createServer(async(req,res)=>{
  const u=new URL(req.url,'http://127.0.0.1');
  const enviar=(http,body,eco=true)=>{res.writeHead(http,{'Content-Type':'application/json','Connection':'close',
    ...(eco?{'X-Test-Run-Id':req.headers['x-test-run-id']??''}:{})});res.end(JSON.stringify(body));};
  let cuerpo={};if(['POST','PUT','PATCH','DELETE'].includes(req.method)){let raw='';for await(const b of req)raw+=b;
    try{cuerpo=JSON.parse(raw);}catch{}}
  if(u.pathname==='/sesiones/'&&req.method==='POST'){
    s.logins++;if(m.loginLento)await new Promise(ok=>setTimeout(ok,50));
    if(m.loginSinRed){req.socket.destroy();return;}
    enviar(200,{token:`e30.${Buffer.from(JSON.stringify({sub:91})).toString('base64url')}.firma`},false);return;}
  if(req.method==='DELETE'&&u.pathname.startsWith('/test-control/runs/')){
    s.cierres++;s.retros=[];s.retro220=false;s.retro246=false;s.cerrado=true;
    enviar(200,{status:'Rollback exitoso'},false);return;}
  if(m.clave403&&req.headers['x-test-run-id']){enviar(403,{error_code:'CLAVE_INVALIDA',message:'Clave sandbox inválida'});return;}
  if(u.pathname==='/prediccion/patologias'){
    enviar(200,{total:7,items:Array.from({length:7},(_,i)=>({id_patologia:i+8,es_activo:true}))});return;}
  if(u.pathname==='/prediccion/modelos/43'){
    enviar(200,{id_version_modelo:43,tipo_modelo:'MODELO_ESPECIES_MEDIANAS',paradigma:'INDIVIDUAL'});return;}
  if(u.pathname==='/prediccion/modelos'){
    const changed=m.version&&s.retro246;
    enviar(200,{total:1,items:[{id_version_modelo:43,tipo_modelo:'MODELO_ESPECIES_MEDIANAS',
      estado_version:changed?'INACTIVO':'ACTIVO',esta_produccion:!changed}]});return;}
  if(u.pathname==='/prediccion/motor-ia/MODELO_ESPECIES_MEDIANAS'){
    enviar(200,{tipo_modelo:'MODELO_ESPECIES_MEDIANAS',id_version_modelo:43,
      config_version:m.config&&s.retro246?2:1,umbral_alerta:0.8});return;}
  if(u.pathname==='/openapi.json'){
    const paths={'/prediccion/retroalimentacion':{post:{summary:'Registro'}}};
    if(m.openapiEdita&&s.posts>=4)paths['/prediccion/retroalimentacion/{id}']={patch:{summary:'Editar'}};
    enviar(200,{openapi:'3.1.0',paths});return;}
  if(u.pathname==='/prediccion/auditoria'){
    enviar(200,{total:s.retros.length,items:s.retros.map(x=>({id_referencia:x.id,tipo_evento:'RETROALIMENTACION_REGISTRADA'}))});return;}
  if(u.pathname==='/prediccion/historial/885'){
    s.historiales++;
    if(m.alertasFalla&&s.posts>=7&&s.posts<8){enviar(503,{message:'Alertas no disponibles'});return;}
    const inferencias=(m.pocos?resultados.slice(0,4):resultados).map((x,i)=>({
      id_evento:x,tipo_evento:'INFERENCIA',id_activo_biologico:885,id_resultado_inferencia:x,
      fecha_evento:new Date(s.inicio-(i+1)*86400000).toISOString(),payload:{nivel_riesgo:2,
        id_patologia:8,probabilidad_riesgo:m.riesgo&&s.retro220&&i===3?0.9:0.2,
        probabilidad_enfermedad:m.probabilidad&&s.retro220&&i===3?0.9:0.1,
        confianza_global:0.8,tipo_modelo:'MODELO_ESPECIES_MEDIANAS',id_version_modelo:43}}));
    if(m.resultado246&&s.retro246)inferencias[4].payload.nivel_riesgo=3;
    if(m.inferencia&&s.retro246)inferencias.push({...inferencias[0],id_evento:id(9),id_resultado_inferencia:id(9)});
    const retros=s.retros.map(x=>({id_evento:x.id,tipo_evento:'RETROALIMENTACION',
      id_activo_biologico:885,id_resultado_inferencia:x.resultado,fecha_evento:x.fecha,
      payload:{id_retroalimentacion:x.id,estado_retroalimentacion:x.estado,
        diagnosticos_reales:x.diagnosticos,id_usuario_veterinario:x.usuario}}));
    const alertas=m.alerta&&s.retro246?[{id_evento:id(10),tipo_evento:'ALERTA',
      id_activo_biologico:885,id_resultado_inferencia:resultados[4],fecha_evento:new Date(s.inicio).toISOString(),
      payload:{id_alerta_patologica:88,estado_alerta:'ACTIVA'}}]:[];
    const extras=m.paginado?Array.from({length:55},(_,i)=>({id_evento:`ruido-${i}`,tipo_evento:'OTRO',
      id_activo_biologico:885,id_resultado_inferencia:resultados[0],fecha_evento:new Date(s.inicio).toISOString(),payload:{}})):[];
    const todos=[...inferencias,...retros,...alertas,...extras].sort((a,b)=>Date.parse(b.fecha_evento)-Date.parse(a.fecha_evento));
    const offset=Number(u.searchParams.get('cursor_paginacion')??0),pagina=todos.slice(offset,offset+50);
    enviar(200,{eventos:pagina,cursor_siguiente:offset+50<todos.length?String(offset+50):null,total_pagina:pagina.length});return;}
  if(u.pathname.startsWith('/prediccion/retroalimentacion')&&req.method!=='POST'){
    s.metodos++;
    if(m.put200&&req.method==='PUT'){enviar(200,{ok:true});return;}
    if(m.patchModifica&&req.method==='PATCH'&&u.pathname!== '/prediccion/retroalimentacion'){
      const target=s.retros.find(x=>x.id===u.pathname.split('/').at(-1));
      if(target)target.estado='INCORRECTO';enviar(405,{detail:'Method Not Allowed'});return;}
    if(m.delete204&&req.method==='DELETE'&&u.pathname!== '/prediccion/retroalimentacion'){
      s.retros=s.retros.filter(x=>x.id!==u.pathname.split('/').at(-1));enviar(204,{});return;}
    enviar(u.pathname==='/prediccion/retroalimentacion'?405:404,{detail:'Not Found'});return;}
  if(u.pathname==='/prediccion/retroalimentacion'&&req.method==='POST'){
    s.posts++;
    if(m.sinRespuesta&&s.posts===5||m.corte&&s.posts===5){req.socket.destroy();return;}
    if(m.tres5xx&&s.posts<=3||m.un5xx&&s.posts===4){enviar(503,{error_code:'ERROR',message:'Fallo aislado'});return;}
    if(!req.headers.authorization&&!m.anonimoAceptado){enviar(401,{error_code:'NO_AUTORIZADO'});return;}
    if((cuerpo.id_activo_biologico==null||cuerpo.id_resultado_inferencia==null)&&!m.incompletoAceptado){
      enviar(400,{error_code:'VAL_ENTRADA',message:'Campo obligatorio'});return;}
    const n=s.retros.length+1;
    const retroId=m.uuidInvalido&&n===2?'uuid-invalido':m.uuidRepetido&&n===2?s.retros[0]?.id:id(n);
    const x={id:retroId,resultado:cuerpo.id_resultado_inferencia??resultados[6],
      fecha:new Date(s.inicio+n*1000).toISOString(),estado:cuerpo.estado_retroalimentacion,
      diagnosticos:cuerpo.diagnosticos_reales??null,usuario:91};
    s.retros.push(x);if(s.posts===4)s.retro220=true;if(s.posts===8)s.retro246=true;
    const respuesta={id_retroalimentacion:x.id,id_resultado_inferencia:x.resultado,id_activo_biologico:885,
      estado_retroalimentacion:x.estado,diagnosticos_reales:x.diagnosticos,id_usuario_veterinario:91,
      fecha_retroalimentacion:x.fecha};
    if(m.trazaNula&&s.posts===1)respuesta.id_usuario_veterinario=null;
    enviar(201,respuesta);return;}
  enviar(404,{detail:'Not Found'});
});}
let completados=0;
for(const [nombre,m,esperados] of modos){
  const s={inicio:Date.now(),logins:0,cierres:0,retros:[],posts:0,metodos:0,historiales:0,
    retro220:false,retro246:false,cerrado:false};
  const server=servidor(m,s);await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g071-ensayo-'));
  try{
    const port=server.address().port,base={SIGAB_API_TEST_BASE:`http://127.0.0.1:${port}`,
      QA_SANDBOX_SECRET:'secreto-local',QA_VETERINARIO_EMAIL:'vet@local.test',
      QA_COMMON_PASSWORD:'clave-local',QA_AUTORIZADO:'SI'};
    let env=base;if(m.envArchivo){const archivo=path.join(tmp,'.env.qa');
      fs.writeFileSync(archivo,Object.entries(base).filter(([k])=>k!=='QA_AUTORIZADO').map(([k,v])=>`${k}=${v}`).join('\n'));
      env=leerEnv({QA_AUTORIZADO:'SI'},archivo);}
    const c={ensayo:true,version:1,intento:1,runId:'RUN-G071-V1-20261029-000000',
      referencia:'ENSAYO_LOCAL',directorio:path.join(tmp,'Resultados','RUN-G071-V1-20261029-000000')};
    const r=await evaluar(c,{env,newmanVersion:m.newmanNo?{ok:false,error:'NEWMAN_NO_DISPONIBLE'}:undefined});
    for(let i=0;i<CASOS.length;i++)assert.equal(r.casos[CASOS[i]].estado,esperados[i]??'APROBADO',`${nombre} ${CASOS[i]} ${r.casos[CASOS[i]].motivo}`);
    const oficial=Object.values(r.casos).every(x=>['APROBADO','RECHAZADO'].includes(x.estado))&&r.cierre.rollback.verificado;
    assert.equal(r.oficial,oficial,`${nombre} oficial`);
    assert.equal(s.cierres,m.newmanNo?0:1,`${nombre} DELETE`);
    assert.ok(s.logins<=1,`${nombre} sesión única`);
    if(m.paginado)assert.ok(s.historiales>=6,`${nombre} cursor`);
    if(fs.existsSync(path.join(c.directorio,'newman'))){
      assert.deepEqual(fs.readdirSync(path.join(c.directorio,'newman')).sort(),['newman-G071.html','newman-G071.json']);
      assert.equal(r.herramientas.newman.iteraciones,1,`${nombre} Newman único`);}
    if(r.oficial){const presentes=new Set(r.evidencias);assert.ok(clasificarRegistro(CAPACIDADES,r,presentes,c),`${nombre} registro QA`);
      const informe=fs.readFileSync(path.join(c.directorio,'TC-M04-G071_resultado.md'),'utf8');
      assert.ok(!informe.includes('Oráculo comprobado por API'),`${nombre} motivo específico`);
      assert.ok(!/\b(?:true|false)\b|\.\./i.test(informe),`${nombre} sin booleanos ni puntos dobles`);
      for(const caso of CASOS){
        const seccion=informe.split(`### ${caso} — `)[1]?.split(/\n### |\n## /)[0];
        assert.ok(seccion?.includes('- **Qué se hizo:**'),`${nombre} ${caso} acción`);
        assert.ok(seccion?.includes('- **Qué se esperaba:**'),`${nombre} ${caso} esperado`);
        assert.ok(seccion?.includes('- **Qué se observó:**'),`${nombre} ${caso} observado`);
        const observado=seccion?.match(/- \*\*Qué se observó:\*\* (.*)/)?.[1];
        const razon=seccion?.match(/- \*\*Por qué [^:]+:\*\* (.*)/)?.[1];
        assert.ok(razon&&razon!==observado,`${nombre} ${caso} razonamiento distinto`);
      }
      assert.ok(informe.includes('**Qué se observó:**')&&informe.includes('**Por qué APROBADO:**'));
      assert.ok(!fs.readdirSync(path.join(c.directorio,'..')).some(x=>x.endsWith('.md')));}
    console.log(`${nombre}: ${CASOS.map(x=>r.casos[x].estado).join('/')} ${r.oficial?'OFICIAL':'NO OFICIAL'}`);
    completados++;
  }finally{await new Promise(ok=>server.close(ok));fs.rmSync(tmp,{recursive:true,force:true});}
}
console.log(`OK G071: ${completados}/${modos.length} modos; presupuesto ${PRESUPUESTO.solicitudes_totales}; registro QA fiel; newman único verificado`);
