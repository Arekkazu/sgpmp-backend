import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {evaluar,leerEnv} from '../g069.mjs';
import {CASOS,CAPACIDADES,PRESUPUESTO} from '../lib/g069_core.mjs';
import {clasificarRegistro} from './registro_qa.mjs';

const ids=[1,2,3,4,5].map(n=>`${String(n).repeat(8)}-${String(n).repeat(4)}-4${String(n).repeat(3)}-8${String(n).repeat(3)}-${String(n).repeat(12)}`);
const duplicado={status:409,body:{error_code:'RETROALIMENTACION_DUPLICADA',message:'Ya existe una retroalimentación registrada por este usuario para este resultado.'}};
const error=(status,code,message)=>({status,body:{error_code:code,message}});
const modos=[
  ['todo_ok',{}],['duplicado_mismo_estado_201',{igual201:true,s212:'RECHAZADO'}],
  ['duplicado_estado_distinto_201',{distinto201:true,s212:'RECHAZADO'}],
  ['duplicado_422',{igual:error(422,'OTRO','Dato inválido'),s212:'RECHAZADO'}],
  ['duplicado_400',{igual:error(400,'OTRO','Dato inválido'),s212:'RECHAZADO'}],
  ['duplicado_409_otro_mensaje',{igual:error(409,'RETROALIMENTACION_DUPLICADA','Otro mensaje'),s212:'RECHAZADO'}],
  ['original_modificado',{modificar:true,s212:'RECHAZADO'}],
  ['registro_extra_tras_409',{extra:true,s212:'RECHAZADO'}],
  ['primer_registro_falla',{primer:error(500,'ERROR','Fallo'),s212:'NO_CONCLUYENTE',oficial:false}],
  ['b_rechazado_409',{b:duplicado,s213:'RECHAZADO'}],
  ['b_rechazado_422',{b:error(422,'OTRO','Dato inválido'),s213:'RECHAZADO'}],
  ['b_sobrescribe_a',{sobrescribe:true,s213:'RECHAZADO'}],
  ['precondicion_213_falla',{pre213:error(500,'ERROR','Fallo'),s213:'NO_CONCLUYENTE',oficial:false}],
  ['login_b_falla',{loginB:401,s213:'NO_CONCLUYENTE',oficial:false}],
  ['login_repetido_detectado',{sesionUnica:true}],
  ['un_5xx',{igual:error(503,'ERROR','Fallo'),s212:'RECHAZADO'}],
  ['tres_5xx',{igual:error(503,'ERROR','Fallo'),distinto:error(503,'ERROR','Fallo'),
    pre213:error(503,'ERROR','Fallo'),s212:'BLOQUEADO',s213:'BLOQUEADO',oficial:false}],
  ['resultado_previo_con_retro',{previo:true}],['ventana_con_reemplazo',{ventana:true}],
  ['datos_insuficientes',{pocos:true,s213:'NO_CONCLUYENTE',oficial:false}],
  ['env_archivo',{envArchivo:true}],['env_sin_b',{envSinB:true,s212:'NO_CONCLUYENTE',s213:'NO_CONCLUYENTE',oficial:false}],
  ['login_lento',{loginLento:true}],['login_sin_red',{sinRed:true,s212:'BLOQUEADO',s213:'BLOQUEADO',oficial:false}],
  ['clave_403',{clave:true,s212:'BLOQUEADO',s213:'BLOQUEADO',oficial:false}],
  ['sin_respuesta',{sinRespuesta:true,s212:'NO_CONCLUYENTE',oficial:false}],
  ['corte_con_cierre',{corte:true,s212:'NO_CONCLUYENTE',oficial:false}],
  ['newman_no_disponible',{newmanNo:true,s212:'BLOQUEADO',s213:'BLOQUEADO',oficial:false}],
  ['auditoria_incompleta',{auditoria500:true,s212:'NO_CONCLUYENTE',s213:'NO_CONCLUYENTE',oficial:false}],
  ['historial_incompleto',{historial500:true,s212:'NO_CONCLUYENTE',s213:'NO_CONCLUYENTE',oficial:false}],
  ['rollback_no_confirmado',{delete500:true,oficial:false}],
  ['mensaje_con_tilde',{igual:{status:409,body:{error_code:'RETROALIMENTACION_DUPLICADA',message:duplicado.body.message}}}],
];
function servidor(m,s){return http.createServer(async(req,res)=>{
  const u=new URL(req.url,'http://127.0.0.1');
  const enviar=(status,body,eco=true)=>{res.writeHead(status,{'Content-Type':'application/json','Connection':'close',
    ...(eco?{'X-Test-Run-Id':req.headers['x-test-run-id']??''}:{})});res.end(JSON.stringify(body));};
  if(u.pathname==='/sesiones/'&&req.method==='POST'){
    let raw='';for await(const x of req)raw+=x;const b=JSON.parse(raw),cuenta=b.correo_electronico.startsWith('b@')?'B':'A';
    s.logins[cuenta]=(s.logins[cuenta]??0)+1;
    if(m.loginLento)await new Promise(ok=>setTimeout(ok,50));
    if(m.sinRed){req.socket.destroy();return;}
    if(cuenta==='B'&&m.loginB){enviar(m.loginB,{message:'Login fallido'},false);return;}
    const sub=cuenta==='B'?162:91,payload=Buffer.from(JSON.stringify({sub})).toString('base64url');
    const token=`e30.${payload}.firma${s.logins[cuenta]}`;s.tokens[cuenta]=token;
    enviar(200,{token},false);return;
  }
  if(req.method==='DELETE'&&u.pathname.startsWith('/test-control/runs/')){
    s.cierres++;s.registros=[];s.cerrado=true;
    enviar(m.delete500?500:200,{status:m.delete500?'Error':'Rollback exitoso'},false);return;
  }
  if(m.clave&&req.method!=='GET'){enviar(403,{error_code:'CLAVE_INVALIDA',message:'Secreto sandbox inválido'});return;}
  const bearer=String(req.headers.authorization??'').replace(/^Bearer /,'');
  if(bearer&&m.sesionUnica&&!Object.values(s.tokens).includes(bearer)){enviar(401,{message:'Sesión revocada'});return;}
  if(u.pathname==='/activos-biologicos/885'&&req.method==='GET'){
    enviar(200,{id_activo_biologico:885,nombre_estado:'ACTIVO'});return;}
  if(u.pathname.startsWith('/prediccion/modelos/')&&req.method==='GET'){
    enviar(200,{id_version_modelo:Number(u.pathname.split('/').at(-1)),tipo_modelo:'MODELO_ESPECIES_MEDIANAS'});return;}
  if(u.pathname==='/prediccion/historial/885'&&req.method==='GET'){
    if(m.historial500&&s.posts>0&&!s.cerrado){enviar(500,{message:'Sin historial'});return;}
    const inf=ids.slice(0,m.pocos?1:5).map((id,i)=>({id_evento:id,tipo_evento:'INFERENCIA',
      id_activo_biologico:885,id_resultado_inferencia:id,
      fecha_evento:new Date(Date.now()-(i+1)*86400000).toISOString(),payload:{id_version_modelo:43}}));
    const retros=s.registros.map(x=>({id_evento:x.id,tipo_evento:'RETROALIMENTACION',
      id_activo_biologico:885,id_resultado_inferencia:x.resultado,fecha_evento:x.fecha,
      payload:{id_retroalimentacion:x.id,id_usuario_veterinario:x.usuario,
        estado_retroalimentacion:x.estado,diagnosticos_reales:x.diagnosticos}}));
    enviar(200,{eventos:[...inf,...retros],cursor_siguiente:null,total_pagina:inf.length+retros.length});return;
  }
  if(u.pathname==='/prediccion/auditoria'&&req.method==='GET'){
    if(m.auditoria500){enviar(500,{message:'Sin auditoría'});return;}
    const items=s.auditoria.map(x=>({tipo_evento:'RETROALIMENTACION_REGISTRADA',resultado_operacion:'EXITOSO',
      id_usuario:Number(x.usuario),id_referencia:x.id,payload_evento:{id_resultado_inferencia:x.resultado}}));
    enviar(200,{total:items.length,items});return;
  }
  if(u.pathname==='/prediccion/retroalimentacion'&&req.method==='POST'){
    s.posts++;
    if(m.sinRespuesta&&s.posts===2){req.socket.destroy();return;}
    if(m.corte&&s.posts===2){req.socket.destroy();return;}
    let raw='';for await(const x of req)raw+=x;const b=JSON.parse(raw);
    const cuenta=bearer===s.tokens.B?'B':'A',usuario=cuenta==='B'?162:91;
    let respuesta;
    const existente=s.registros.find(x=>x.resultado===b.id_resultado_inferencia&&x.usuario===String(usuario));
    if(!existente&&m.primer&&s.posts===1)respuesta=m.primer;
    else if(!existente&&m.pre213&&ids.slice(1).includes(b.id_resultado_inferencia)&&s.registros.some(x=>x.resultado===b.id_resultado_inferencia)===false&&s.posts>3)respuesta=m.pre213;
    else if(m.previo&&s.posts===1||m.ventana&&s.posts===1)respuesta=m.ventana?
      error(422,'FUERA_DE_VENTANA_TEMPORAL','Ventana vencida'):duplicado;
    else if(existente&&cuenta==='A'&&b.estado_retroalimentacion==='CORRECTO')respuesta=m.igual201?
      {status:201,body:{}}:m.igual??duplicado;
    else if(existente&&cuenta==='A')respuesta=m.distinto201?{status:201,body:{}}:m.distinto??duplicado;
    else if(cuenta==='B'&&m.b)respuesta=m.b;
    else respuesta={status:201,body:{}};
    if(respuesta.status===201){
      const id=`aaaaaaaa-aaaa-4aaa-8aaa-${String(s.secuencia++).padStart(12,'0')}`;
      if(m.sobrescribe&&cuenta==='B')s.registros=s.registros.filter(x=>x.resultado!==b.id_resultado_inferencia);
      const fecha=new Date().toISOString(),registro={id,resultado:b.id_resultado_inferencia,
        usuario:String(usuario),estado:b.estado_retroalimentacion,diagnosticos:b.diagnosticos_reales??null,fecha};
      s.registros.push(registro);s.auditoria.push(registro);
      respuesta={status:201,body:{id_retroalimentacion:id,id_resultado_inferencia:b.id_resultado_inferencia,
        estado_retroalimentacion:b.estado_retroalimentacion,diagnosticos_reales:b.diagnosticos_reales??null,
        id_usuario_veterinario:usuario,fecha_retroalimentacion:fecha}};
    }else if(m.extra&&s.posts===2){
      s.registros.push({id:'extra',resultado:b.id_resultado_inferencia,usuario:'91',
        estado:'CORRECTO',diagnosticos:null,fecha:new Date().toISOString()});}
    if(m.modificar&&s.posts===2&&s.registros.length)s.registros[0].estado='INCORRECTO';
    enviar(respuesta.status,respuesta.body);return;
  }
  enviar(404,{message:'Ruta no encontrada'});
});}
let completados=0;
for(const [nombre,m] of modos){
  const s={logins:{},tokens:{},cierres:0,registros:[],auditoria:[],secuencia:1,posts:0,cerrado:false};
  const server=servidor(m,s);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g069-ensayo-'));
  try{
    const runId='RUN-G069-V1-20261029-000000',directorio=path.join(tmp,runId);
    const envBase={SIGAB_API_TEST_BASE:`http://127.0.0.1:${server.address().port}`,
      QA_SANDBOX_SECRET:'secreto-local',QA_VETERINARIO_EMAIL:'a@local.test',
      QA_VETERINARIO_B_EMAIL:'b@local.test',QA_COMMON_PASSWORD:'clave-local',QA_AUTORIZADO:'SI'};
    let env=envBase;
    if(m.envArchivo||m.envSinB){const archivo=path.join(tmp,'.env.qa');
      fs.writeFileSync(archivo,Object.entries(envBase).filter(([k])=>k!=='QA_AUTORIZADO'&&(!m.envSinB||k!=='QA_VETERINARIO_B_EMAIL'))
        .map(([k,v])=>`${k}=${v}`).join('\n'));
      env=leerEnv({QA_AUTORIZADO:'SI'},archivo);}
    const c={runId,version:1,intento:1,referencia:'ensayo local',directorio,ensayo:true};
    const r=await evaluar(c,{env,...(m.newmanNo?{newmanVersion:{ok:false,error:'NEWMAN_NO_DISPONIBLE'}}:{})});
    const esperado212=m.s212??'APROBADO',esperado213=m.s213??'APROBADO';
    assert.equal(r.casos[CASOS[0]].estado,esperado212,`${nombre} 212: ${r.casos[CASOS[0]].motivo}`);
    assert.equal(r.casos[CASOS[1]].estado,esperado213,`${nombre} 213: ${r.casos[CASOS[1]].motivo}`);
    assert.equal(r.oficial,m.oficial??true,`${nombre} oficial`);
    assert.ok(r.solicitudes.length<=PRESUPUESTO.solicitudes_totales,`${nombre} presupuesto`);
    if(!m.envSinB&&!m.newmanNo){assert.equal(s.logins.A,1,`${nombre} login A`);
      if(!m.sinRed)assert.equal(s.logins.B,1,`${nombre} login B`);
      assert.equal(s.cierres,1,`${nombre} cierre`);}
    if(m.envSinB||m.newmanNo)assert.equal(s.posts,0,`${nombre} sin peticiones`);
    if(r.herramientas.newman.iteraciones){
      const files=fs.readdirSync(path.join(directorio,'newman'));
      assert.deepEqual(files.sort(),['newman-G069.html','newman-G069.json']);
      const texto=files.map(x=>fs.readFileSync(path.join(directorio,'newman',x),'utf8')).join('\n');
      for(const secreto of [envBase.QA_COMMON_PASSWORD,envBase.QA_SANDBOX_SECRET,envBase.QA_VETERINARIO_EMAIL,envBase.QA_VETERINARIO_B_EMAIL])
        assert.ok(!texto.includes(secreto),`${nombre} saneamiento`);
      assert.equal(r.herramientas.newman.iteraciones,1,`${nombre} Newman único`);
    }
    if(fs.existsSync(path.join(directorio,'resultado.json'))){
      const persistido=JSON.parse(fs.readFileSync(path.join(directorio,'resultado.json'),'utf8'));
      assert.equal(persistido.run_id,runId,`${nombre} RUN en JSON`);
      assert.deepEqual(Object.fromEntries(CASOS.map(x=>[x,persistido.casos[x].estado])),
        Object.fromEntries(CASOS.map(x=>[x,r.casos[x].estado])),`${nombre} estados en JSON`);
      const informe=fs.readFileSync(path.join(directorio,'TC-M04-G069_resultado.md'),'utf8');
      assert.ok(informe.includes(runId)&&CASOS.every(x=>informe.includes(x)),`${nombre} informe coherente`);
      assert.ok(informe.includes('Qué se esperaba')&&!informe.includes('retroalimentaciÃ'),`${nombre} UTF-8`);
      for(const caso of CASOS){
        const bloque=informe.split(`### ${caso} — ${r.casos[caso].estado}\n`)[1]?.split('\n### ')[0];
        assert.ok(bloque,`${nombre} encabezado con decisión ${caso}`);
        const observado=bloque.match(/^- \*\*Qué se observó:\*\* (.+)$/m)?.[1];
        const razon=bloque.match(new RegExp(`^- \\*\\*Por qué ${r.casos[caso].estado}:\\*\\* (.+)$`,'m'))?.[1];
        assert.ok(observado&&razon&&observado!==razon,`${nombre} observación y razón distintas ${caso}`);
        assert.ok(bloque.includes('- **Qué se hizo:**')&&bloque.includes('- **Qué se esperaba:**'),`${nombre} cuatro líneas ${caso}`);
      }
      for(const evidencia of ['preflight.json','resultado.json','TC-M04-G069_resultado.md','newman/newman-G069.json','newman/newman-G069.html'])
        assert.equal(informe.includes(`- ${evidencia}`),fs.existsSync(path.join(directorio,evidencia)),
          `${nombre} evidencia ${evidencia}`);
      assert.equal(fs.readdirSync(directorio).filter(x=>x.endsWith('.md')).length,1,`${nombre} un informe`);
    }
    if(r.oficial){const presentes=new Set(fs.readdirSync(directorio).flatMap(x=>x==='newman'?
      fs.readdirSync(path.join(directorio,x)).map(y=>`newman/${y}`):[x]));
      assert.equal(clasificarRegistro(CAPACIDADES,r,presentes,{runId,version:1}),true,`${nombre} registro QA`);}
    console.log(`${nombre}: ${esperado212} / ${esperado213}; ${r.oficial?'OFICIAL':'TÉCNICO'}`);completados++;
  }finally{await new Promise(resolve=>server.close(resolve));fs.rmSync(tmp,{recursive:true,force:true});}
}
console.log(`OK G069: ${completados}/${modos.length} modos; presupuesto ${PRESUPUESTO.solicitudes_totales}; registro QA fiel; newman único verificado`);
