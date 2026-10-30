import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { evaluar, leerEnv } from '../g068.mjs';
import { CASOS, CAPACIDADES, PRESUPUESTO } from '../lib/g068_core.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const resultIds=['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222',
  '33333333-3333-4333-8333-333333333333'];
const error=(status,code,message)=>({status,body:{error_code:code,message}});
const ok210=error(404,'RESULTADO_INFERENCIA_NO_ENCONTRADO','El resultado de inferencia no existe o no está disponible.');
const ok211=error(422,'ACTIVO_BIOLOGICO_INCONSISTENTE','El activo biológico no corresponde al resultado de inferencia indicado.');
const ok245=error(422,'ACTIVO_EN_BAJA','El activo biológico está dado de baja.');
const modos=[
  ['todo_ok',{}],
  ['historial_real_con_libres',{historialReal:true}],
  ['baja_ok_retro_aceptada',{e245:{status:201,body:{id_retroalimentacion:'r245'}},e245Estado:'RECHAZADO'}],
  ['baja_ok_retro_rechazada',{}],
  ['baja_rechazada',{bajaRechazada:true,e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['baja_403',{baja403:true,e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['baja_vet_403_admin_ok',{bajaVet403:true}],
  ['baja_no_reflejada',{bajaNoReflejada:true,e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['bitacora_sin_evento',{bitacoraSinEvento:true}],
  ['corte_tras_baja',{corteTrasBaja:true,e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['newman_403_clave',{e210:error(403,'CLAVE_INVALIDA','Secreto sandbox inválido'),
    e210Estado:'BLOQUEADO',e211Estado:'BLOQUEADO',e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['newman_tres_5xx',{e210:error(503,'ERROR_INTERNO','Error'),e211:error(503,'ERROR_INTERNO','Error'),
    baja500:true,e210Estado:'BLOQUEADO',e211Estado:'BLOQUEADO',e245Estado:'BLOQUEADO',oficial:false}],
  ['inexistente_400',{e210:error(400,'RESULTADO_INFERENCIA_NO_ENCONTRADO',ok210.body.message),e210Estado:'RECHAZADO'}],
  ['inexistente_422',{e210:error(422,'RESULTADO_INFERENCIA_NO_ENCONTRADO',ok210.body.message),e210Estado:'RECHAZADO'}],
  ['inexistente_otro_mensaje',{e210:error(404,'RESULTADO_INFERENCIA_NO_ENCONTRADO','No encontrado'),e210Estado:'RECHAZADO'}],
  ['inexistente_201',{e210:{status:201,body:{id_retroalimentacion:'r210'}},e210Estado:'RECHAZADO'}],
  ['inexistente_500',{e210:error(500,'ERROR_INTERNO','Error'),e210Estado:'RECHAZADO'}],
  ['inexistente_503',{e210:error(503,'SERVICIO_NO_DISPONIBLE','Error'),e210Estado:'RECHAZADO'}],
  ['activo_distinto_aceptado',{e211:{status:201,body:{id_retroalimentacion:'r211'}},e211Estado:'RECHAZADO'}],
  ['activo_distinto_400_completo',{e211:error(400,'ACTIVO_BIOLOGICO_INCONSISTENTE',ok211.body.message)}],
  ['activo_distinto_409_completo',{e211:error(409,'ACTIVO_BIOLOGICO_INCONSISTENTE',ok211.body.message)}],
  ['activo_distinto_otro_significado',{e211:error(422,'OTRO_ERROR','La validación falló'),e211Estado:'RECHAZADO'}],
  ['activo_distinto_400_otro_significado',{e211:error(400,'OTRO_ERROR','Dato inválido'),e211Estado:'RECHAZADO'}],
  ['activo_distinto_500',{e211:error(500,'ERROR_INTERNO','Error'),e211Estado:'RECHAZADO'}],
  ['activo_distinto_503',{e211:error(503,'SERVICIO_NO_DISPONIBLE','Error'),e211Estado:'RECHAZADO'}],
  ['sin_respuesta',{sinRespuesta:true,e211Estado:'NO_CONCLUYENTE',e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['sin_resultados_libres',{sinResultados:true,e211Estado:'NO_CONCLUYENTE',e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['sin_otro_activo',{sinOtro:true,e211Estado:'NO_CONCLUYENTE',e245Estado:'APROBADO',oficial:false}],
  ['otro_activo_lote',{soloLote:true}],
  ['resultado_fuera_ventana',{primer211:error(422,'FUERA_DE_VENTANA_TEMPORAL','Fuera de ventana')}],
  ['resultado_duplicado',{primer211:error(409,'RETROALIMENTACION_DUPLICADA','Duplicado')}],
  ['auditoria_incompleta',{auditoria500:true,e210Estado:'NO_CONCLUYENTE',e211Estado:'NO_CONCLUYENTE',e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['activo_no_restaurado',{noRestaurado:true,oficial:false}],
  ['sin_fase_activa',{sinFaseActiva:true}],
  ['fase_activa_durante_baja',{faseActivaDuranteBaja:true,oficial:false}],
  ['fase_no_restaurada',{faseNoRestaurada:true,oficial:false}],
  ['clave_403',{clave403:true,e210Estado:'BLOQUEADO',e211Estado:'BLOQUEADO',e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['error5xx',{error5xx:true,e211Estado:'NO_CONCLUYENTE',e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['login_lento',{loginLento:true}],
  ['login_sin_red',{loginSinRed:true,e210Estado:'BLOQUEADO',e211Estado:'BLOQUEADO',e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['newman_no_disponible',{newmanNo:true,e210Estado:'BLOQUEADO',e211Estado:'BLOQUEADO',e245Estado:'NO_CONCLUYENTE',oficial:false}],
  ['corte_con_cierre',{corte:true,e210Estado:'NO_CONCLUYENTE',oficial:false}],
  ['env_archivo',{envArchivo:true}],
];

function servidor(mode,estado) {
  return http.createServer(async(req,res)=>{
    const u=new URL(req.url,'http://127.0.0.1');
    const enviar=(status,body,run=true)=>{res.writeHead(status,{'Content-Type':'application/json',...(run?{'X-Test-Run-Id':req.headers['x-test-run-id']??''}:{})});res.end(JSON.stringify(body));};
    if(u.pathname==='/sesiones/'&&req.method==='POST') {
      if(mode.loginLento) await new Promise(resolve=>setTimeout(resolve,50));
      if(mode.loginSinRed) {req.socket.destroy();return;}
      const payload=Buffer.from(JSON.stringify({sub:'91'})).toString('base64url');
      enviar(200,{token:`e30.${payload}.firma`},false);return;
    }
    if(req.method==='DELETE'&&u.pathname.startsWith('/test-control/runs/')) {
      estado.cierres++;estado.cerrado=true;estado.persistidos=[];estado.baja=false;enviar(200,{status:'Rollback exitoso'},false);return;
    }
    if(mode.clave403) {enviar(403,{detail:'Secreto inválido'});return;}
    if(mode.error5xx&&req.method==='GET'&&u.pathname.startsWith('/activos-biologicos')) {enviar(500,{message:'Error interno'});return;}
    if(u.pathname==='/activos-biologicos'&&req.method==='GET') {
      const soloIndividual=u.searchParams.has('tipo');
      enviar(200,{registros:[{id_activo_biologico:885,tipo:'INDIVIDUAL',nombre_estado:'ACTIVO',nombre:'Semilla'},
        ...(mode.sinOtro||mode.soloLote&&soloIndividual?[]:[{id_activo_biologico:886,tipo:mode.soloLote?'POBLACIONAL':'INDIVIDUAL',nombre_estado:'ACTIVO',nombre:'Otro activo'}])],total_paginas:1});return;
    }
    if(u.pathname==='/activos-biologicos/885'&&req.method==='GET') {
      if(mode.corteTrasBaja&&estado.baja&&!estado.cerrado){req.socket.destroy();return;}
      const deBaja=estado.cerrado?!!mode.noRestaurado:estado.baja&&!mode.bajaNoReflejada;
      enviar(200,{id_activo_biologico:885,tipo:'INDIVIDUAL',id_estado:deBaja?4:1,
        nombre_estado:deBaja?'BAJA':'ACTIVO'});return;
    }
    if(u.pathname==='/activos-biologicos/885/fases'&&req.method==='GET') {
      enviar(200,{id_activo_biologico:885,fases:mode.sinFaseActiva?[]:[{id_gestion_fases:estado.cerrado&&mode.faseNoRestaurada?2:1,
        nombre_fase_actual:'Crecimiento',es_activa:!estado.baja||estado.cerrado||!!mode.faseActivaDuranteBaja}]});return;
    }
    if(u.pathname.startsWith('/prediccion/historial/')&&req.method==='GET') {
      if(!u.searchParams.has('fecha_inicio')||!u.searchParams.has('fecha_fin')||u.searchParams.has('cursor'))
        {enviar(400,{message:'Parámetros de historial incorrectos'});return;}
      estado.historiales++;
      if(mode.corte&&estado.posts.length>0&&!estado.cortado){estado.cortado=true;enviar(500,{message:'Corte'});return;}
      const activo=Number(u.pathname.split('/').at(-1));
      const ids=mode.historialReal?[...resultIds,...Array.from({length:69},(_,i)=>`44444444-4444-4444-8444-${String(i+1).padStart(12,'0')}`)]:resultIds;
      const inf=activo===885&&!mode.sinResultados?ids.slice(0,mode.historialReal?71:3).map((id,i)=>({tipo_evento:'INFERENCIA',id_resultado_inferencia:id,
        id_evento:id,fecha_evento:new Date(Date.now()-(i+1)*86400000).toISOString(),payload:{tipo_modelo:i<14?'MODELO_ESPECIES_MEDIANAS':'MODELO_ACUICULTURA'}})):[];
      const retro=estado.persistidos.filter(e=>e.activo===activo).map(e=>({tipo_evento:'RETROALIMENTACION',
        id_resultado_inferencia:e.resultado,id_evento:e.id,fecha_evento:new Date().toISOString(),payload:{id_usuario_veterinario:91}}));
      const previo=mode.historialReal&&activo===885?[{tipo_evento:'RETROALIMENTACION',
        id_resultado_inferencia:ids[13],id_evento:'55555555-5555-4555-8555-555555555555',
        fecha_evento:new Date(Date.now()-86400000).toISOString(),payload:{id_usuario_veterinario:99}}]:[];
      const eventos=[...inf,...previo,...retro];
      if(mode.historialReal&&activo===885&&estado.posts.length===0){
        const segundo=u.searchParams.get('cursor_paginacion')==='pagina-2';
        if(u.searchParams.has('cursor_paginacion')&&!segundo){enviar(400,{message:'Cursor incorrecto'});return;}
        const pagina=segundo?eventos.slice(40):eventos.slice(0,40);
        enviar(200,{eventos:pagina,cursor_siguiente:segundo?null:'pagina-2',total_pagina:pagina.length});return;
      }
      enviar(200,{eventos,cursor_siguiente:null,total_pagina:eventos.length});return;
    }
    if(u.pathname==='/prediccion/auditoria'&&req.method==='GET') {
      if(mode.auditoria500){enviar(500,{message:'Auditoría no disponible'});return;}
      const items=estado.persistidos.map(e=>({tipo_evento:'RETROALIMENTACION_REGISTRADA',id_referencia:e.id,
        payload_evento:{id_resultado_inferencia:e.resultado}}));
      enviar(200,{total:items.length,items});return;
    }
    if(u.pathname==='/activos-biologicos/auditoria'&&req.method==='GET') {
      const registros=estado.baja&&!mode.bitacoraSinEvento?[{rf_origen:'RF45',tipo_evento:'BAJA_REGISTRADA',
        id_activo_biologico:885}]:[];
      enviar(200,{total_registros:registros.length,registros});return;
    }
    if(u.pathname==='/activos-biologicos/885/eventos/baja'&&req.method==='POST') {
      estado.bajas++;
      if(mode.baja403||mode.bajaVet403&&estado.bajas===1)
        {enviar(403,{message:'Permiso insuficiente'});return;}
      if(mode.baja500){enviar(503,{message:'Error interno'});return;}
      if(mode.bajaRechazada){enviar(422,{message:'Baja rechazada'});return;}
      estado.baja=true;enviar(201,{id_eventos:77});return;
    }
    if(u.pathname==='/prediccion/retroalimentacion'&&req.method==='POST') {
      let raw='';for await(const chunk of req) raw+=chunk;
      const b=JSON.parse(raw),es210=!resultIds.includes(b.id_resultado_inferencia),es245=estado.baja&&b.id_activo_biologico===885;
      if(!es210&&mode.sinRespuesta){estado.posts.push({ruta:u.pathname,caso:'211',cabeceras:!!req.headers['x-test-run-id']&&!!req.headers['x-sandbox-secret']});req.socket.destroy();return;}
      let respuesta=es210?mode.e210??ok210:es245?mode.e245??ok245:mode.e211??ok211;
      if(!es210&&!es245&&mode.primer211&&estado.post211++===0) respuesta=mode.primer211;
      if(respuesta.status===201){
        const id=respuesta.body.id_retroalimentacion;
        estado.persistidos.push({id,resultado:b.id_resultado_inferencia,activo:885});
        respuesta={...respuesta,body:{...respuesta.body,id_resultado_inferencia:b.id_resultado_inferencia}};
      }
      estado.posts.push({ruta:u.pathname,caso:es210?'210':es245?'245':'211',cabeceras:!!req.headers['x-test-run-id']&&!!req.headers['x-sandbox-secret']});
      enviar(respuesta.status,respuesta.body);return;
    }
    enviar(404,{message:'Sin ruta'});
  });
}
const temporal=fs.mkdtempSync(path.join(os.tmpdir(),'g068-ensayo-'));
let aprobados=0;
try {
  for(const [nombre,mode] of modos) {
    const estado={cerrado:false,cierres:0,persistidos:[],posts:[],bajas:0,baja:false,historiales:0,post211:0};
    const server=servidor(mode,estado);
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const directorio=path.join(temporal,nombre,'RUN-G068-V1-20261029-000000');
    const c={operacion:'evaluar',version:1,intento:1,runId:'RUN-G068-V1-20261029-000000',
      referencia:'ENSAYO_LOCAL',directorio,ensayo:true};
    const env={SIGAB_API_TEST_BASE:`http://127.0.0.1:${server.address().port}`,QA_SANDBOX_SECRET:'secreto-local',
      QA_VETERINARIO_EMAIL:'qa@example.invalid',QA_ADMIN_EMAIL:'admin@example.invalid',QA_COMMON_PASSWORD:'local',QA_AUTORIZADO:'SI'};
    if(mode.envArchivo) {
      const archivo=path.join(temporal,'.env.qa');fs.writeFileSync(archivo,'QA_VETERINARIO_EMAIL=qa@example.invalid\n','utf8');
      assert.equal(!!leerEnv({QA_AUTORIZADO:'SI'},archivo).QA_VETERINARIO_EMAIL,true);
    }
    let r;
    try {r=await evaluar(c,{env,newmanVersion:mode.newmanNo?{ok:false,error:'NEWMAN_NO_DISPONIBLE'}:undefined});}
    finally {await new Promise(resolve=>server.close(resolve));}
    assert.equal(r.casos[CASOS[0]].estado,mode.e210Estado??'APROBADO',nombre);
    assert.equal(r.casos[CASOS[1]].estado,mode.e211Estado??'APROBADO',nombre);
    assert.equal(r.casos[CASOS[2]].estado,mode.e245Estado??'APROBADO',nombre);
    assert.equal(r.oficial,mode.oficial??true,nombre);
    if(['todo_ok','baja_ok_retro_aceptada','baja_ok_retro_rechazada','baja_vet_403_admin_ok',
      'baja_rechazada','baja_403','baja_no_reflejada','bitacora_sin_evento','corte_tras_baja'].includes(nombre))
      assert(estado.bajas>=1,nombre);
    assert(estado.posts.every(x=>x.cabeceras),nombre);
    if(!mode.newmanNo&&!mode.loginSinRed) assert.equal(estado.cierres,1,nombre);
    const presentes=new Set(['preflight.json','resultado.json','TC-M04-G068_resultado.md',
      ...fs.existsSync(path.join(directorio,'newman'))?fs.readdirSync(path.join(directorio,'newman')).map(x=>`newman/${x}`):[]]);
    assert.equal(clasificarRegistro(CAPACIDADES,r,presentes,c),r.oficial,nombre);
    assert.equal(fs.existsSync(path.join(directorio,'TC-M04-G068_resultado.md')),true,nombre);
    assert.equal(fs.readdirSync(directorio).filter(x=>x.endsWith('.md')).length,1,nombre);
    assert.equal(r.solicitudes.length<=PRESUPUESTO.solicitudes_totales,true,nombre);
    assert(r.incidencias.every(x=>['CRÍTICA','ALTA','MEDIA','BAJA'].includes(x.severidad)&&x.equipo_inicial==='Desarrollo'
      &&/^INC-M04-G068-(210|211|245)-\d{2}$/.test(x.id)),nombre);
    const postsNewman=r.solicitudes.filter(x=>x.ruta==='/prediccion/retroalimentacion');
    assert(postsNewman.every(x=>x.herramienta==='Newman'),nombre);
    if(['todo_ok','corte_tras_baja'].includes(nombre)) {
      const archivos=fs.readdirSync(path.join(directorio,'newman')).sort();
      assert.deepEqual(archivos,['newman-G068.html','newman-G068.json'],nombre);
      assert.equal(r.herramientas.newman.iteraciones,1,nombre);
    }
    if(nombre==='bitacora_sin_evento')
      assert(r.observaciones.some(x=>x.includes('posible evento RF-52 en buffer local fuera del sandbox')),nombre);
    const texto=fs.readFileSync(path.join(directorio,'TC-M04-G068_resultado.md'),'utf8');
    const porQue=[...texto.matchAll(/^- Por qué [^:]+: (.+)$/gm)];
    assert.equal(porQue.length,3,nombre);
    assert(porQue.every(x=>!x[1].includes('rechazo, historial y auditoría concordantes')),nombre);
    assert(!texto.includes('Las comprobaciones se ejecutaron según los datos disponibles.'),nombre);
    if(nombre==='baja_ok_retro_aceptada') {
      assert(texto.includes('INC-M04-G068-245-01: MEDIA'),nombre);
      assert(texto.includes('RETROALIMENTACION_REGISTRADA, cuando RF-72 4112-4113'),nombre);
    }
    if(nombre==='todo_ok') {
      assert(texto.includes('HTTP 404 RESULTADO_INFERENCIA_NO_ENCONTRADO'),nombre);
      assert(texto.includes('rechazo HTTP 422 ACTIVO_BIOLOGICO_INCONSISTENTE'),nombre);
    }
    if(nombre==='sin_fase_activa') assert(texto.includes('sin fase activa'),nombre);
    if(nombre==='newman_no_disponible') {
      assert(texto.includes('Newman no se ejecutó (0 iteraciones)'),nombre);
      assert(!texto.includes('Reportes JSON y HTML generados'),nombre);
      assert(!fs.existsSync(path.join(directorio,'newman')),nombre);
    }
    if(['baja_rechazada','baja_403','baja_no_reflejada'].includes(nombre)) {
      assert(!estado.posts.some(x=>x.caso==='245'),nombre);
      assert(texto.includes('RUN oficial: no')&&texto.includes('Qué falta: TC-M04-245 (precondición de baja no montada:'),nombre);
    }
    if(nombre==='baja_vet_403_admin_ok') assert.equal(estado.bajas,2,nombre);
    if(nombre==='newman_403_clave') assert.equal(estado.posts.length,1,nombre);
    if(nombre==='newman_tres_5xx') {
      assert.equal(r.solicitudes.filter(x=>x.herramienta==='Newman').length,3,nombre);
      assert.equal(r.incidencias.length,0,nombre);
      assert(texto.includes('RUN oficial: no')&&texto.includes('Qué falta: TC-M04-210 (Fallo de ambiente:'),nombre);
    }
    if(nombre==='historial_real_con_libres') {
      assert.equal(r.datos_elegidos.descubrimiento_885.eventos_examinados,72,nombre);
      assert.equal(r.datos_elegidos.descubrimiento_885.paginas,2,nombre);
      assert(r.datos_elegidos.descubrimiento_885.resultados_libres>=3,nombre);
    }
    if(nombre==='sin_resultados_libres') {
      assert.deepEqual(estado.posts.map(x=>x.caso),['210'],nombre);
      assert.equal(r.herramientas.newman.iteraciones,1,nombre);
      assert.equal(r.datos_elegidos.descubrimiento_885.eventos_examinados,0,nombre);
    }
    if(nombre==='sin_fase_activa') {
      assert.deepEqual(r.datos_elegidos.activo_885_antes.fase,[],nombre);
      assert.deepEqual(r.cierre.activo_885.fase,[],nombre);
    }
    for(const x of r.evidencias.filter(x=>x.startsWith('newman/'))) {
      assert(fs.existsSync(path.join(directorio,x)),nombre);
      assert(!fs.readFileSync(path.join(directorio,x),'utf8').includes('secreto-local'),nombre);
    }
    assert(texto.includes('El resultado de inferencia no existe o no está disponible.')&&!texto.includes('�'),nombre);
    assert(texto.startsWith(`# TC-M04-G068 — ${r.oficial?'APROBADO':'TÉCNICO'}`)||
      r.oficial&&texto.startsWith('# TC-M04-G068 — RECHAZADO'),nombre);
    for(const caso of CASOS) assert(texto.includes(`### ${caso} — ${r.casos[caso].estado}`),nombre);
    if(mode.noRestaurado||mode.faseNoRestaurada||mode.faseActivaDuranteBaja)
      assert(texto.includes('ALERTA PRIORITARIA'),nombre);
    aprobados++;console.log(`${nombre}: OK ${CASOS.map(x=>r.casos[x].estado).join('/')} ${r.oficial?'OFICIAL':'TÉCNICO / no oficial'}`);
  }
  console.log(`OK G068: ${aprobados}/${modos.length} modos; presupuesto ${PRESUPUESTO.solicitudes_totales}; registro QA fiel; newman único verificado`);
} finally {fs.rmSync(temporal,{recursive:true,force:true});}
