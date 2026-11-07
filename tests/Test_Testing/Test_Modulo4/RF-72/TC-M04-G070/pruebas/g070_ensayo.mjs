import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {evaluar,leerEnv,validarReevaluacion} from '../g070.mjs';
import {CASOS,CAPACIDADES,PRESUPUESTO,DIAS} from '../lib/g070_core.mjs';
import {clasificarRegistro} from './registro_qa.mjs';

const ids=Array.from({length:7},(_,i)=>`${String(i+1).repeat(8)}-${String(i+1).repeat(4)}-4${String(i+1).repeat(3)}-8${String(i+1).repeat(3)}-${String(i+1).repeat(12)}`);
const claves=['reciente','d89','d90','d90h','d91','d120a','d120b'];
const horas=[26,89*24+1,90*24+1,90*24+12,91*24+1,120*24+2,120*24+1];
const fixture=JSON.parse(fs.readFileSync(new URL('./semilla_observada_G070_V2.json',import.meta.url),'utf8'));
const hoursVencidas=(idx,ventana,edades)=>Math.floor(edades[idx]/24)>ventana;
assert.equal(validarReevaluacion({version_anterior:1,alcance_reevaluacion:'216, 217 y regresión'},2),true);
assert.equal(validarReevaluacion({version_anterior:0,alcance_reevaluacion:'216, 217'},2),false);
const estados=(s={})=>Object.fromEntries(CASOS.map((x,i)=>[x,s[i]??(i===2||i===3?'RECHAZADO':'APROBADO')]));
const modos=[
  ['todo_ok',{superficie:true,esperado:estados({2:'NO_CONCLUYENTE',3:'NO_CONCLUYENTE'}),oficial:false}],
  ['comportamiento_codigo_actual',{}],
  ['timestamp_aceptado_422',{timestamp422:true}],
  ['timestamp_aceptado_201_fecha_anterior',{timestampAnterior:true,esperado:estados({0:'RECHAZADO'})}],
  ['dia89_rechazado',{d89:422,esperado:estados({1:'RECHAZADO'})}],
  ['dia90_rechazado',{d90:422,esperado:estados({1:'RECHAZADO'})}],
  ['dia91_aceptado',{d91:201,esperado:estados({1:'RECHAZADO'})}],
  ['dia91_400',{d91:400,esperado:estados({1:'RECHAZADO'})}],
  ['noventa_mas_horas_rechazado',{d90h:422}],
  ['noventa_mas_horas_aceptado',{d90h:201}],
  ['semilla_fuera_de_tramo',{fuera:true,esperado:estados({1:'NO_CONCLUYENTE'}),oficial:false}],
  ['ventana_en_parametros_solo_lectura',{configLee:true}],
  ['ciento_veinte_aceptado',{d120a:201,d120b:201,esperado:estados({3:'RECHAZADO',4:'RECHAZADO'})}],
  ['mensaje_sin_fecha',{mensaje:'sin_fecha',esperado:estados({4:'RECHAZADO'})}],
  ['mensaje_fecha_incorrecta',{mensaje:'fecha_incorrecta',esperado:estados({4:'RECHAZADO'})}],
  ['mensaje_sin_id',{mensaje:'sin_id',esperado:estados({4:'RECHAZADO'})}],
  ['mensaje_sin_contacto',{mensaje:'sin_contacto',esperado:estados({4:'RECHAZADO'})}],
  ['un_5xx',{un5xx:true,esperado:estados({0:'RECHAZADO'})}],
  ['tres_5xx',{tres5xx:true,esperado:estados(Object.fromEntries(CASOS.map((_,i)=>[i,'BLOQUEADO']))),oficial:false}],
  ['datos_insuficientes',{sinDatos:true,esperado:estados({0:'NO_CONCLUYENTE',1:'NO_CONCLUYENTE',3:'NO_CONCLUYENTE',4:'NO_CONCLUYENTE'}),oficial:false}],
  ['env_archivo',{envArchivo:true}],
  ['login_lento',{loginLento:true}],
  ['login_sin_red',{loginSinRed:true,esperado:estados(Object.fromEntries(CASOS.map((_,i)=>[i,'BLOQUEADO']))),oficial:false}],
  ['clave_403',{clave403:true,esperado:estados(Object.fromEntries(CASOS.map((_,i)=>[i,'BLOQUEADO']))),oficial:false}],
  ['sin_respuesta',{sinRespuesta:true,esperado:estados({0:'NO_CONCLUYENTE'}),oficial:false}],
  ['corte_con_cierre',{corte:true,esperado:estados({0:'NO_CONCLUYENTE'}),oficial:false}],
  ['newman_no_disponible',{newmanNo:true,esperado:estados(Object.fromEntries(CASOS.map((_,i)=>[i,'BLOQUEADO']))),oficial:false}],
  ['historial_incompleto',{historialFalla:true,esperado:estados({0:'NO_CONCLUYENTE',1:'NO_CONCLUYENTE',3:'NO_CONCLUYENTE',4:'NO_CONCLUYENTE'}),oficial:false}],
  ['auditoria_incompleta',{auditFalla:true,esperado:estados({0:'NO_CONCLUYENTE',1:'NO_CONCLUYENTE',3:'NO_CONCLUYENTE',4:'NO_CONCLUYENTE'}),oficial:false}],
  ['rollback_no_confirmado',{deleteFalla:true,oficial:false}],
  ['historial_paginado',{paginado:true}],
  ['v2_corregido',{v2:true,esperado:estados({2:'APROBADO',3:'APROBADO'})}],
  ['vencidos_sin_120',{v2:true,vencidosSin120:true,esperado:estados({2:'APROBADO',3:'APROBADO'})}],
  ['reintentar_v2',{v2:true,reintentar:true,esperado:estados({2:'APROBADO',3:'APROBADO'})}],
  ['v2_defecto',{v2:true,defecto:true}],
  ['patch_6_aceptado',{v2:true,patch6:true,esperado:estados({2:'RECHAZADO',3:'APROBADO'})}],
  ['ampliacion_afecta_b',{v2:true,afectaB:true,esperado:estados({2:'APROBADO',3:'RECHAZADO'})}],
  ['ampliacion_cambia_global',{v2:true,cambiaGlobal:true,esperado:estados({2:'APROBADO',3:'RECHAZADO'})}],
  ['sin_semilla_fronteras',{v2:true,fuera:true,esperado:estados({1:'NO_CONCLUYENTE',2:'APROBADO',3:'APROBADO'}),oficial:false}],
  ['veterinario_patch_ok',{v2:true,vetPatch:true,esperado:estados({2:'RECHAZADO',3:'APROBADO'})}],
];
function servidor(m,s){
  const idsModo=m.vencidosSin120?[ids[0],...fixture.semilla_observada.map(x=>x.id)]:ids;
  const horasModo=m.vencidosSin120?[26,...fixture.semilla_observada.map(x=>x.horas)]:horas;
  const clavesModo=m.vencidosSin120?['reciente','d89','d90','d90h','d91',null,null,'d120b','d120a']:claves;
  return http.createServer(async(req,res)=>{
  const u=new URL(req.url,'http://127.0.0.1');
  const enviar=(status,body,eco=true)=>{res.writeHead(status,{'Content-Type':'application/json','Connection':'close',
    ...(eco?{'X-Test-Run-Id':req.headers['x-test-run-id']??''}:{})});res.end(JSON.stringify(body));};
  if(u.pathname==='/sesiones/'&&req.method==='POST'){
    let raw='';for await(const b of req)raw+=b;const cuenta=JSON.parse(raw).correo_electronico.startsWith('admin')?'admin':'vet';
    s.logins[cuenta]=(s.logins[cuenta]??0)+1;
    if(m.loginLento)await new Promise(ok=>setTimeout(ok,50));
    if(m.loginSinRed&&cuenta==='vet'){req.socket.destroy();return;}
    const payload=Buffer.from(JSON.stringify({sub:cuenta==='vet'?91:1})).toString('base64url');
    enviar(200,{token:`e30.${payload}.firma${cuenta}`},false);return;}
  if(req.method==='DELETE'&&u.pathname.startsWith('/test-control/runs/')){
    s.cierres++;if(!m.deleteFalla){s.registros=[];s.config=90;s.ampliado=false;s.eventoAmpliacion=null;}s.cerrado=true;
    enviar(m.deleteFalla?500:200,{status:m.deleteFalla?'Error':'Rollback exitoso'},false);return;}
  if(u.pathname==='/activos-biologicos/885'){enviar(200,{id_activo_biologico:885,nombre_estado:'ACTIVO'});return;}
  if(u.pathname==='/prediccion/modelos/43'){enviar(200,{id_version_modelo:43,tipo_modelo:'MODELO_ESPECIES_MEDIANAS'});return;}
  if(u.pathname==='/openapi.json'){
    const paths={'/prediccion/retroalimentacion':{post:{summary:'Registrar retroalimentación'}},
      '/configuracion/parametros':{get:{summary:'Consultar configuración operativa'},patch:{summary:'Actualizar frecuencia e heartbeat'}}};
    if(m.v2){paths['/configuracion/parametros-retroalimentacion']={get:{summary:'Consultar ventana'},patch:{summary:'Actualizar ventana'}};
      paths['/prediccion/retroalimentacion/ampliaciones']={post:{summary:'Ampliar ventana'}};}
    if(m.superficie){paths['/m09/ventana_retroalimentacion_dias']={get:{summary:'Leer ventana'},patch:{summary:'Cambiar ventana'}};
      paths['/prediccion/retroalimentacion/ampliar-ventana']={post:{summary:'Ampliar ventana de resultado'}};}
    enviar(200,{openapi:'3.1.0',paths});return;}
  if(u.pathname==='/configuracion/parametros'){
    enviar(200,{frecuencia_muestreo:10,intervalo_heartbeat:20,...(m.configLee?{ventana_retroalimentacion_dias:90}:{})});return;}
  if(m.v2&&u.pathname==='/configuracion/parametros-retroalimentacion'){
    const respuesta=()=>[{nombre:'ventana_retroalimentacion_dias',valor:s.config,fuente:'CONFIGURADO'}];
    if(req.method==='GET'){enviar(200,respuesta());return;}
    if(req.method==='PATCH'){
      let raw='';for await(const b of req)raw+=b;const p=JSON.parse(raw).parametros;
      if(m.defecto){enviar(404,{error_code:'NO_EXISTE',message:'Ruta ausente'});return;}
      if(req.headers.authorization?.includes('firmavet')&&!m.vetPatch){enviar(403,{error_code:'SIN_PERMISO',message:'Sin permiso'});return;}
      const valor=p?.ventana_retroalimentacion_dias;
      if(Object.keys(p??{}).some(k=>k!=='ventana_retroalimentacion_dias')
        ||!Number.isInteger(valor)||valor<7&&!(m.patch6&&valor===6)||valor>365){
        enviar(400,{error_code:'PARAMETRO_RETROALIMENTACION_INVALIDO',message:'Valor inválido'});return;}
      s.config=valor;enviar(200,respuesta());return;}}
  if(m.v2&&u.pathname==='/prediccion/retroalimentacion/ampliaciones'&&req.method==='POST'){
    let raw='';for await(const b of req)raw+=b;const p=JSON.parse(raw);
    if(req.headers.authorization?.includes('firmavet')){enviar(403,{error_code:'SIN_PERMISO',message:'Sin permiso'});return;}
    if(m.defecto){enviar(404,{error_code:'NO_EXISTE',message:'Ruta ausente'});return;}
    if(p.justificacion.length<10||p.dias_habilitados<1||p.dias_habilitados>365){
      enviar(422,{error_code:'VALIDACION',message:'Solicitud inválida'});return;}
    s.ampliado=true;if(m.cambiaGlobal)s.config=365;
    s.eventoAmpliacion={id_evento:'evento-ampliacion-1',tipo_evento:'VENTANA_RETROALIMENTACION_AMPLIADA',
      id_referencia:p.id_resultado_inferencia,id_usuario:1,payload_evento:{...p,id_usuario_autorizador:1}};
    enviar(201,{...p,id_usuario_autorizador:1,id_ampliacion_ventana_retroalimentacion:1,
      fecha_limite:new Date(s.inicio+5*DIAS).toISOString()});return;}
  if(u.pathname==='/prediccion/historial/885'){
    s.historiales++;
    if(m.historialFalla&&s.posts>0&&!s.cerrado){enviar(500,{message:'Historial no disponible'});return;}
    const ahora=s.inicio;
    const inf=m.sinDatos?[]:idsModo.filter((_,i)=>!m.fuera||i!==1).map((id,i)=>({id_evento:id,tipo_evento:'INFERENCIA',
      id_activo_biologico:885,id_resultado_inferencia:id,
      fecha_evento:new Date(ahora-horasModo[idsModo.indexOf(id)]*3600000).toISOString(),payload:{id_version_modelo:43}}));
    const retros=s.registros.map(x=>({id_evento:x.id,tipo_evento:'RETROALIMENTACION',
      id_activo_biologico:885,id_resultado_inferencia:x.resultado,fecha_evento:x.fecha,
      payload:{id_retroalimentacion:x.id,id_usuario_veterinario:91}}));
    const ruido=m.paginado?Array.from({length:55},(_,i)=>({id_evento:`ruido-${i}`,tipo_evento:'OTRO',
      id_activo_biologico:885,id_resultado_inferencia:null,fecha_evento:new Date(ahora-i*1000).toISOString(),payload:{}})):[];
    const todos=[...ruido,...inf,...retros],offset=Number(u.searchParams.get('cursor_paginacion')??0),pagina=todos.slice(offset,offset+50);
    enviar(200,{eventos:pagina,cursor_siguiente:offset+50<todos.length?String(offset+50):null,total_pagina:pagina.length});return;}
  if(u.pathname==='/prediccion/auditoria'){
    if(m.auditFalla){enviar(500,{message:'Auditoría no disponible'});return;}
    const items=u.searchParams.get('tipo_evento')==='VENTANA_RETROALIMENTACION_AMPLIADA'?
      (s.eventoAmpliacion?[s.eventoAmpliacion]:[]):s.auditoria.map(x=>({tipo_evento:'RETROALIMENTACION_REGISTRADA',
      id_usuario:91,id_referencia:x.id,payload_evento:{id_resultado_inferencia:x.resultado}}));
    enviar(200,{total:items.length,items});return;}
  if(u.pathname==='/prediccion/retroalimentacion'&&req.method==='POST'){
    s.posts++;if((m.sinRespuesta||m.corte)&&s.posts===1){req.socket.destroy();return;}
    let raw='';for await(const b of req)raw+=b;const body=JSON.parse(raw);
    const idx=idsModo.indexOf(body.id_resultado_inferencia),clave=clavesModo[idx];
    if(m.clave403){enviar(403,{error_code:'CLAVE_INVALIDA',message:'Clave sandbox inválida'});return;}
    if(m.tres5xx&&s.posts<=3||m.un5xx&&idx===0){enviar(503,{error_code:'ERROR',message:'Fallo'});return;}
    if(m.timestamp422&&idx===0){enviar(422,{error_code:'TIMESTAMP_INVALIDO',message:'La fecha de retroalimentación es inválida.'});return;}
    const forzado=m[clave];
    const vencido=m.v2?hoursVencidas(idx,s.config,horasModo)&&!(clave==='d120a'&&s.ampliado)&&!(clave==='d120b'&&s.ampliado&&m.afectaB):idx===4||idx>=5;
    const status=forzado??(vencido?422:201);
    if(status===201){const id=`retro-${++s.secuencia}`,fecha=m.timestampAnterior&&idx===0?
      body.timestamp_retroalimentacion:new Date().toISOString();
      s.registros.push({id,resultado:body.id_resultado_inferencia,fecha});s.auditoria.push({id,resultado:body.id_resultado_inferencia});
      enviar(201,{id_retroalimentacion:id,id_resultado_inferencia:body.id_resultado_inferencia,
        fecha_retroalimentacion:fecha});return;}
    if(status===400){enviar(400,{error_code:'OTRO',message:'Dato inválido'});return;}
    const limite=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'})
      .format(new Date(s.inicio-horasModo[idx]*3600000+90*DIAS));
    let message=`La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia ${body.id_resultado_inferencia}. La ventana válida para este resultado venció el ${limite}. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo.`;
    if(idx===6){if(m.mensaje==='sin_fecha')message=message.replace(limite,'[sin fecha]');
      if(m.mensaje==='fecha_incorrecta')message=message.replace(limite,'2020-01-01');
      if(m.mensaje==='sin_id')message=message.replace(body.id_resultado_inferencia,'[sin id]');
      if(m.mensaje==='sin_contacto')message=message.replace(/Contacte al administrador[^.]*\./,'');}
    enviar(422,{error_code:'FUERA_DE_VENTANA_TEMPORAL',message});return;}
  enviar(404,{message:'Ruta no encontrada'});
});}
let completados=0;
for(const [nombre,m] of modos){
  const s={inicio:Date.now(),config:90,ampliado:false,eventoAmpliacion:null,logins:{},cierres:0,
    registros:[],auditoria:[],secuencia:0,posts:0,historiales:0,cerrado:false};
  const server=servidor(m,s);await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g070-ensayo-'));
  try{const version=m.v2?2:1,runId=`RUN-G070-V${version}-20261029-000000`,directorio=path.join(tmp,runId);
    const envBase={SIGAB_API_TEST_BASE:`http://127.0.0.1:${server.address().port}`,
      QA_SANDBOX_SECRET:'secreto-local',QA_VETERINARIO_EMAIL:'a@local.test',QA_ADMIN_EMAIL:'admin@local.test',
      QA_COMMON_PASSWORD:'clave-local',QA_ADMIN_PASSWORD:'clave-admin-local',QA_AUTORIZADO:'SI'};
    let env=envBase;if(m.envArchivo){const archivo=path.join(tmp,'.env.qa');
      fs.writeFileSync(archivo,Object.entries(envBase).filter(([k])=>k!=='QA_AUTORIZADO').map(([k,v])=>`${k}=${v}`).join('\n'));
      env=leerEnv({QA_AUTORIZADO:'SI'},archivo);}
    const c={runId,version,intento:1,referencia:'ensayo local',directorio,ensayo:true,
      ...(m.reintentar?{operacion:'reintentar',semillaCommit:new Date(s.inicio-30*60000).toISOString(),
        commit:null,alembicTest:'c31f8a6d920e'}:{})};
    const r=await evaluar(c,{env,...(m.newmanNo?{newmanVersion:{ok:false,error:'NEWMAN_NO_DISPONIBLE'}}:{})});
    const esperado=m.esperado??estados();
    assert.deepEqual(Object.fromEntries(CASOS.map(x=>[x,r.casos[x].estado])),esperado,`${nombre}: ${JSON.stringify(r.casos)}`);
    if(m.vencidosSin120){
      const de215=new Set(['d89','d90','d90h','d91'].map(k=>r.semilla[k].id));
      for(const k of ['d120a','d120b']){
        assert.ok(r.semilla[k].dias_backend>91&&r.semilla[k].dias_backend<120,`${nombre} ${k} vencido sin 120`);
        assert.ok(!de215.has(r.semilla[k].id),`${nombre} ${k} distinto de 215`);}
      assert.ok(r.v2_ampliacion?.pasos?.length,`${nombre} 217 ejecutado`);
      assert.ok(r.solicitudes.some(x=>x.nombre==='G070-218-120B'),`${nombre} 218 ejecutado`);}
    assert.equal(r.oficial,m.oficial??true,`${nombre} oficial`);
    assert.ok(r.solicitudes.length<=PRESUPUESTO.solicitudes_totales,`${nombre} presupuesto`);
    if(!m.newmanNo){assert.equal(s.logins.vet,1,`${nombre} login vet`);assert.equal(s.cierres,1,`${nombre} DELETE`);
      if(!m.loginSinRed)assert.equal(s.logins.admin,1,`${nombre} login admin`);}
    if(m.newmanNo)assert.equal(s.posts,0);
    if(r.herramientas.newman.iteraciones){const files=fs.readdirSync(path.join(directorio,'newman'));
      assert.deepEqual(files.sort(),['newman-G070.html','newman-G070.json']);
      const texto=files.map(x=>fs.readFileSync(path.join(directorio,'newman',x),'utf8')).join('\n');
      for(const secreto of [envBase.QA_COMMON_PASSWORD,envBase.QA_ADMIN_PASSWORD,envBase.QA_SANDBOX_SECRET,
        envBase.QA_VETERINARIO_EMAIL,envBase.QA_ADMIN_EMAIL])assert.ok(!texto.includes(secreto),`${nombre} saneamiento`);
      assert.equal(r.herramientas.newman.iteraciones,1,`${nombre} Newman único`);}
    if(fs.existsSync(path.join(directorio,'resultado.json'))){
      const guardado=JSON.parse(fs.readFileSync(path.join(directorio,'resultado.json'),'utf8'));
      assert.equal(guardado.run_id,runId);assert.deepEqual(Object.fromEntries(CASOS.map(x=>[x,guardado.casos[x].estado])),esperado);
      const informe=fs.readFileSync(path.join(directorio,version===2?'TC-M04-G070_reevaluacion_V2.md':'TC-M04-G070_resultado.md'),'utf8');
      assert.ok(informe.includes(runId)&&CASOS.every(x=>informe.includes(x)));
      assert.ok(!/matriz/i.test(informe),`${nombre} sin mención de matriz`);
      assert.ok(!/retroalimentaciÃ|configuraciÃ|vÃ¡lida/.test(informe),`${nombre} UTF-8`);
      for(const secreto of [envBase.QA_COMMON_PASSWORD,envBase.QA_ADMIN_PASSWORD,envBase.QA_SANDBOX_SECRET,
        envBase.QA_VETERINARIO_EMAIL,envBase.QA_ADMIN_EMAIL])
        assert.ok(!informe.includes(secreto)&&!JSON.stringify(guardado).includes(secreto),`${nombre} datos saneados`);
      assert.deepEqual(r.incidencias.map(x=>x.caso).sort(),CASOS.filter(x=>r.casos[x].estado==='RECHAZADO').sort(),
        `${nombre} incidencias solo rechazados`);
      assert.ok(r.incidencias.every(x=>['Desarrollo','AIoT','DBA','Implementación'].includes(x.equipo_responsable)
        &&['CRÍTICA','ALTA','MEDIA','BAJA'].includes(x.severidad)),`${nombre} equipos y severidades`);
      for(const x of CASOS){const bloque=informe.split(`### ${x} — ${r.casos[x].estado}\n`)[1]?.split('\n### ')[0];
        assert.ok(bloque?.includes('**Qué se hizo:**')&&bloque.includes('**Qué se esperaba:**')
          &&bloque.includes('**Qué se observó:**')&&bloque.includes(`**Por qué ${r.casos[x].estado}:**`),`${nombre} detalle ${x}`);}
      assert.ok(informe.includes('## Decisión del caso')&&informe.includes('Qué falta:'),`${nombre} decisión`);
      if(m.v2){
        const patch=r.solicitudes.findIndex(x=>x.metodo==='PATCH');
        const ultimo215=r.solicitudes.findIndex(x=>x.nombre==='G070-215-91');
        const mensaje218=r.solicitudes.findIndex(x=>x.nombre==='G070-218-120B');
        assert.ok(patch>ultimo215&&patch>mensaje218,`${nombre} regresión antes de PATCH`);
        assert.ok(r.v2_config?.restaurada,`${nombre} restauración 90`);}
      if(m.reintentar){assert.ok(informe.includes('Dos intentos técnicos anteriores V2'));
        assert.ok(informe.includes(c.semillaCommit));assert.ok(informe.includes('c31f8a6d920e'));
        assert.ok(informe.includes('commit de código desplegado: no verificado'));}
      if(m.vencidosSin120){assert.ok(informe.includes('vencido A')&&informe.includes('vencido B'));
        assert.ok(informe.includes('A (93 días completos)')&&informe.includes('B (93 días completos)'));
        assert.ok(!informe.includes('resultados de 120 días'));}
      assert.ok(!informe.includes('Se ejecutó la comprobación API correspondiente'),`${nombre} acción genérica`);
      for(const x of CASOS){const bloque=informe.split(`### ${x} — ${r.casos[x].estado}\n`)[1]?.split('\n### ')[0];
        const observado=bloque.match(/\*\*Qué se observó:\*\* (.*)/)?.[1]?.trim();
        const razon=bloque.match(/\*\*Por qué [^:]+:\*\* (.*)/)?.[1]?.trim();
        assert.ok(observado&&razon&&observado!==razon&&!razon.includes(observado),`${nombre} razón distinta de observación ${x}`);}
      assert.equal(fs.readdirSync(directorio).filter(x=>x.endsWith('.md')).length,1);
      for(const evidencia of r.evidencias)assert.ok(fs.existsSync(path.join(directorio,evidencia)),`${nombre} evidencia ${evidencia}`);
      if(r.oficial){const presentes=new Set(fs.readdirSync(directorio).flatMap(x=>x==='newman'?
        fs.readdirSync(path.join(directorio,x)).map(y=>`newman/${y}`):[x]));
        assert.equal(clasificarRegistro(CAPACIDADES,r,presentes,{runId,version}),true,`${nombre} registro QA`);}}
    console.log(`${nombre}: ${CASOS.map(x=>r.casos[x].estado).join(' / ')}; ${r.oficial?'OFICIAL':'TÉCNICO'}`);completados++;
  }finally{await new Promise(ok=>server.close(ok));fs.rmSync(tmp,{recursive:true,force:true});}
}
console.log(`OK G070: ${completados}/${modos.length} modos; presupuesto ${PRESUPUESTO.solicitudes_totales}; registro QA fiel; newman único verificado`);
