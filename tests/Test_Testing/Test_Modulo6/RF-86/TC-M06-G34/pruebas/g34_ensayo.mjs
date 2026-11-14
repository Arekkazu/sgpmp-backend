import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { evaluar, informe, motivosNoOficial } from '../g34.mjs';
import { CAPACIDADES, PRESUPUESTO, medicionesConEstado, evaluarB } from '../lib/g34_core.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const grupo=fileURLToPath(new URL('../',import.meta.url));
const fetchLocal=globalThis.fetch;let intentosRemotos=0;
globalThis.fetch=(url,opciones)=>{
  if (!/^http:\/\/(?:127\.0\.0\.1|localhost):\d+\//.test(String(url))) {
    intentosRemotos++;throw Error('RED_REMOTA_PROHIBIDA_EN_ENSAYO');
  }
  return fetchLocal(url,opciones);
};
const archivos=(dir=grupo)=>fs.readdirSync(dir,{withFileTypes:true}).flatMap(x=>{
  const p=path.join(dir,x.name);return x.isDirectory()?archivos(p):[path.relative(grupo,p)];
}).sort();
const antes=archivos();
const modos=['todo_conforme','reintentar_v2_conforme','campos_inyectados','aviso_ausente','panel_sin_pendiente','ambos_defectos',
  'aviso_duplicado','aviso_sin_fecha','aviso_sin_identificador','periodo_actual_cerrado','a_con_medicion_previa',
  'variacion_de_A','B_bloqueado_por_A','restauracion_fallida','put_403','cypress_cero',
  'delete_sin_secreto','poscierre_config_original','sin_candidatos','registro_qa_fiel','sin_archivos',
  'cypress_base_sin_www','cypress_host_inesperado_bloqueado','login_nunca_sale','B_medicion_evento_959',
  'ui_tabla_tardia','ui_b_ausente','ui_periodo_por_selector','registro_oficial_valido','delete_fallido'];
async function probarIntercept(modo) {
  let matcher, handler;
  const env={API_BASE:'https://api.inmero.co/api-sgpmp-test',FRONT_BASE:'https://api.inmero.co/sigab-test',
    RUN_ID:'RUN-G34-V1-20261108-000000',ARTIFACTS_DIR:'local',ACTIVO_A:'101',ACTIVO_B:'102',
    PERIODO_ID:'201',PROD_LOGIN_TOKEN:'token-local',SANDBOX_SECRET:'secreto-local'};
  const contexto=vm.createContext({URL,Promise,Error,Cypress:{env:k=>env[k]},cy:{intercept:(m,h)=>{matcher=m;handler=h;}},
    describe:()=>{}});
  vm.runInContext(fs.readFileSync(path.join(grupo,'g34.cy.js'),'utf8'),contexto);
  vm.runInContext('interceptar()',contexto);
  const llamar=async(url,method='GET')=>{
    assert.equal(matcher.url.test(url),true,modo+': host cubierto');
    const salida={reply:null,continue:false,headers:{}};
    handler({url,method,headers:salida.headers,reply:x=>{salida.reply=x;},
      continue:cb=>{salida.continue=true;cb({statusCode:200,headers:{'x-test-run-id':env.RUN_ID}});}});
    await Promise.resolve();return salida;
  };
  if (modo==='cypress_base_sin_www') {
    const sonda=await llamar(env.API_BASE+'/__g34_sonda__');
    assert.equal(sonda.reply?.body?.interceptado,true);
    assert.equal(sonda.continue,false);
    const lectura=await llamar(env.API_BASE+'/finanzas/periodos/201/mediciones');
    assert.equal(lectura.continue,true);
    assert.equal(lectura.headers['X-Test-Run-Id'],env.RUN_ID);
    assert.equal(lectura.headers['X-Sandbox-Secret'],env.SANDBOX_SECRET);
  }
  if (modo==='cypress_host_inesperado_bloqueado') {
    const x=await llamar('https://www.api.inmero.co/api-sgpmp-inesperada/sesiones/','POST');
    assert.equal(x.reply?.forceNetworkError,true);assert.equal(x.continue,false);
    assert.equal(vm.runInContext('acta.estado',contexto),'NO_CONCLUYENTE');
    assert.match(vm.runInContext('acta.host_bloqueado',contexto),/www\.api\.inmero\.co/);
  }
  if (modo==='login_nunca_sale') {
    const x=await llamar(env.API_BASE+'/sesiones/','POST');
    assert.equal(x.reply?.statusCode,200);assert.equal(x.continue,false);
    assert.equal(vm.runInContext('acta.login_resuelto_localmente',contexto),true);
  }
}
function probarMedicion959() {
  const base={completa:true,activo:945,variaciones:[],lineas:[],mediciones:[]};
  const historial=[{id_medicion_posterior:701,id_evento:959,
    ganancia_perdida_transformacion:'55226.88',ganancia_perdida_precio_mercado:'0'}];
  const periodo=[{id_medicion_posterior:701,estado:'COMPLETADO'}];
  const post={completa:true,activo:945,
    variaciones:[{id_variacion_valor_razonable:239,id_activo_biologico:945,
      tipo:'GANANCIA_TRANSFORMACION_BIOLOGICA',monto_variacion:'55226.88',id_linea:561}],
    lineas:[{id_linea_asiento_nic41:561,id_activo_biologico:945,id_origen:239}],
    mediciones:medicionesConEstado(historial,periodo,945)};
  assert.equal(base.mediciones.length,0,'base antes del evento B');
  assert.equal(post.mediciones[0].id_activo_biologico,945,'ID de la ruta del historial B');
  assert.equal(post.mediciones[0].estado,'COMPLETADO');
  assert.equal(evaluarB(base,post,{activo:945,evento:959,periodo:8,
    calculoPrevio:{valor_neto:2761344,magnitud:306},pesoNuevo:312.12}).estado,'APROBADO');
  assert.equal(evaluarB({...base,activo:943},post,{activo:945,evento:959,periodo:8,
    calculoPrevio:{valor_neto:2761344,magnitud:306},pesoNuevo:312.12}).estado,'NO_CONCLUYENTE');
}
function probarTabla(modo) {
  const spec=fs.readFileSync(path.join(grupo,'g34.cy.js'),'utf8');
  assert.ok(spec.indexOf("cy.wait('@medicionesPeriodo'") < spec.indexOf("cy.contains('tbody tr',IB"),
    'la lectura de mediciones precede a la fila B');
  assert.ok(spec.indexOf("cy.contains('tbody tr',IB") < spec.indexOf("cy.contains('tbody tr',IA"),
    'B precede a A');
  if (modo==='ui_periodo_por_selector') {
    const espera=spec.indexOf('cy.get(opcionPeriodo,{timeout:30000})');
    const seleccion=spec.indexOf("cy.get('#fin-periodo').select(PERIODO");
    const lectura=spec.indexOf("cy.wait('@medicionesPeriodo'");
    assert.ok(espera>=0 && espera<seleccion && seleccion<lectura,
      'con período predeterminado distinto, esperar opción y seleccionar PERIODO antes de medir');
    assert.match(spec,/\.should\('have\.value',PERIODO\)/);
    assert.match(spec,/Período '\+PERIODO\+' no disponible en el selector/);
    assert.doesNotMatch(spec,/pushState\([^\n]*\?periodo/);
  }
  const env={API_BASE:'https://api.inmero.co/api-sgpmp-test',FRONT_BASE:'https://api.inmero.co/sigab-test',
    RUN_ID:'RUN-G34-V1-20261108-000000',ARTIFACTS_DIR:'local',ACTIVO_A:'101',ACTIVO_B:'102',
    PERIODO_ID:'201',IDENTIFICADOR_A:'QA-M06-BOV-01',IDENTIFICADOR_B:'QA-M06-BOV-02',
    PROD_LOGIN_TOKEN:'token-local',SANDBOX_SECRET:'secreto-local'};
  const contexto=vm.createContext({URL,Promise,Error,Cypress:{env:k=>env[k]},describe:()=>{}});
  vm.runInContext(spec,contexto);
  const evaluar=(a,b)=>vm.runInContext(`evaluarFilas(${JSON.stringify(a)},${JSON.stringify(b)})`,contexto);
  if (modo==='ui_tabla_tardia') {
    assert.equal(evaluar({innerText:'QA-M06-BOV-01 Medición pendiente'},null).estado,'NO_CONCLUYENTE');
    assert.equal(evaluar({innerText:'QA-M06-BOV-01 Medición pendiente'},
      {innerText:'QA-M06-BOV-02 Medido'}).estado,'APROBADO');
  }
  if (modo==='ui_b_ausente') assert.equal(evaluar({innerText:'QA-M06-BOV-01 Medición pendiente'},null).estado,'NO_CONCLUYENTE');
}
const hoy=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
async function servidor(modo) {
  const eventos={101:[],102:[]},calculos={101:[{id_calculo_valor_razonable:101,id_activo_biologico:101,
    id_precio_mercado:401,magnitud:400,unidad_magnitud:'kg',valor_neto:'1000',estado:'CALCULADO',fecha_calculo:hoy}],
    102:[{id_calculo_valor_razonable:102,id_activo_biologico:102,id_precio_mercado:401,
      magnitud:400,unidad_magnitud:'kg',valor_neto:'1000',estado:'CALCULADO',fecha_calculo:hoy}]};
  const mediciones=[],variaciones=[],lineas=[],auditoria=[],avisos=[],registros=[];
  const original={pct_transporte:'0.02',pct_comisiones:'0.01',pct_impuestos:'0.01'};
  let costos={...original},eid=300,aidAudit=700,avisId=1,cerrado=false,procesados=0,put=0;
  const send=(res,code,data,run)=>{res.writeHead(code,{'Content-Type':'application/json',
    ...(run?{'X-Test-Run-Id':run}:{})});res.end(JSON.stringify(code>=400?{
      error_code:data?.error_code??'ERROR_LOCAL',message:'Error local simulado',fields:{},
      timestamp:new Date().toISOString()}:data));};
  const server=http.createServer(async(req,res)=>{
    const u=new URL(req.url,'http://127.0.0.1'),run=req.headers['x-test-run-id'];
    const body=await new Promise(resolve=>{let s='';req.on('data',b=>s+=b);
      req.on('end',()=>{try{resolve(JSON.parse(s||'{}'));}catch{resolve({});}});});
    registros.push({metodo:req.method,ruta:u.pathname,run,secreto:!!req.headers['x-sandbox-secret']});
    if (req.method==='POST'&&u.pathname==='/sesiones/') return send(res,200,{token:'token-local'});
    if (req.method==='DELETE'&&u.pathname.startsWith('/test-control/runs/')) {
      if (modo==='delete_fallido') return send(res,500,{error_code:'FALLO_LOCAL'});
      if (req.headers['x-sandbox-secret']!=='secreto-local') return send(res,400,{error_code:'SECRETO_REQUERIDO'});
      cerrado=true;costos={...original};
      Object.values(eventos).forEach(x=>x.splice(0));calculos[101].splice(1);calculos[102].splice(1);
      mediciones.splice(0);variaciones.splice(0);lineas.splice(0);auditoria.splice(0);
      return send(res,200,{ok:true});
    }
    if (req.method==='GET'&&u.pathname==='/finanzas/activos') return send(res,200,
      modo==='sin_candidatos'?[]:[101,102].map(id=>({id_activo_biologico:id,id_especie:39,
        especie:'Bovino',tipo:'INDIVIDUAL',estado:'ACTIVO',valorado_por_costo:false,
        valor_razonable_neto:1000,identificador:'QA-'+id})),run);
    if (req.method==='GET'&&u.pathname==='/finanzas/periodos') return send(res,200,
      [{id_periodo_contable:201,numero_id_tributaria:'titular-local',estado:modo==='periodo_actual_cerrado'?'CERRADO':'ABIERTO',
        fecha_inicio:hoy.slice(0,4)+'-01-01',fecha_fin:hoy.slice(0,4)+'-12-31'},
       {id_periodo_contable:202,numero_id_tributaria:'titular-local',estado:'ABIERTO',
        fecha_inicio:(Number(hoy.slice(0,4))+1)+'-01-01',fecha_fin:(Number(hoy.slice(0,4))+1)+'-12-31'}],run);
    if (req.method==='GET'&&u.pathname==='/finanzas/precios') return send(res,200,
      [{id_precio_mercado:401,id_especie:39,categoria:'PESO_KG',fuente:'MERCADO_ACTIVO',
        fecha_vigencia:hoy,precio_unitario:10}],run);
    if (req.method==='GET'&&/^\/finanzas\/activos\/(101|102)$/.test(u.pathname)) {
      const aid=Number(u.pathname.split('/').at(-1));
      return send(res,200,{activo:{numero_id_tributaria:'titular-local'},
        calculos:calculos[aid],mediciones:mediciones.filter(x=>x.id_activo_biologico===aid)},run);
    }
    if (req.method==='GET'&&/^\/activos-biologicos\/(101|102)\/ficha-integral$/.test(u.pathname))
      return send(res,200,{peso_actual:400,unidad_peso:'kg',estado_actual:'ACTIVO'},run);
    if (req.method==='GET'&&/^\/activos-biologicos\/(101|102)\/eventos$/.test(u.pathname)) {
      const aid=Number(u.pathname.split('/')[2]);
      return send(res,200,{eventos:eventos[aid].map(x=>({id_eventos:x.id}))},run);
    }
    if (req.method==='POST'&&/^\/activos-biologicos\/(101|102)\/eventos\/crecimiento$/.test(u.pathname)) {
      const aid=Number(u.pathname.split('/')[2]);assert.equal(body.unidad_medida,'kg');
      assert.ok(body.valor_medicion===400||body.valor_medicion===408);
      eventos[aid].push({id:++eid,peso:body.valor_medicion,procesado:false});
      return send(res,201,{evento:{id_eventos:eid}},run);
    }
    if (req.method==='POST'&&u.pathname==='/finanzas/eventos/procesar') {
      procesados++;
      for (const aid of [101,102]) for (const ev of eventos[aid].filter(x=>!x.procesado)) {
        ev.procesado=true;
        if (aid===101 && modo!=='B_bloqueado_por_A') {
          calculos[101].push({...calculos[101][0],id_calculo_valor_razonable:103,magnitud:408,valor_neto:'1020'});
          mediciones.push({id_medicion_posterior:601,id_activo_biologico:101,id_evento:ev.id,
            id_periodo_contable:201,estado:'COMPLETADO',ganancia_perdida_transformacion:'20',
            ganancia_perdida_precio_mercado:'0'});
          variaciones.push({id_variacion_valor_razonable:501,id_activo_biologico:101,
            tipo:'GANANCIA_TRANSFORMACION_BIOLOGICA',monto_variacion:'20',id_linea:401});
          lineas.push({id_linea_asiento_nic41:401,id_activo_biologico:101,id_origen:501});
        }
        if (aid===102) {
          auditoria.push({id_evento:++aidAudit,tipo_evento:'MEDICION_PENDIENTE',severidad_evento:'WARNING',
            id_activo_biologico:102,id_periodo_contable:201,id_referencia:ev.id,
            payload_evento:{motivo:'VALOR_NETO_NO_POSITIVO',id_evento:ev.id}});
          if (!['aviso_ausente','ambos_defectos'].includes(modo)) {
            const dia=hoy.slice(8,10)+'/'+hoy.slice(5,7)+'/'+hoy.slice(0,4);
            const mensaje='No se pudo completar la medición del activo '+
              (modo==='aviso_sin_identificador'?'otro activo':'QA-102')+' por el evento biológico del '+
              (modo==='aviso_sin_fecha'?'fecha omitida':dia)+'; el registro financiero quedó suspendido.';
            avisos.unshift({id_notificacion:avisId++,id_evento:900,tipo_evento:41,
              fecha_envio:new Date().toISOString(),es_leido:false,mensaje,
              ...(modo==='campos_inyectados'?{id_activo_biologico:102,id_referencia:ev.id}:{} )});
            if(modo==='aviso_duplicado') avisos.unshift({id_notificacion:avisId++,id_evento:901,tipo_evento:41,
              fecha_envio:new Date().toISOString(),es_leido:false,mensaje});
          }
          if (modo==='variacion_de_A') variaciones.push({id_variacion_valor_razonable:502,
            id_activo_biologico:102,tipo:'GANANCIA_TRANSFORMACION_BIOLOGICA',monto_variacion:'20'});
        }
      }
      return send(res,200,{procesados:1},run);
    }
    if (req.method==='GET'&&u.pathname==='/finanzas/configuracion') return send(res,200,{
      matriz:[{tipo_hecho:'VARIACION_VR_TB',sentido:'GANANCIA',id_especie:39,cuenta_debito:'1',cuenta_credito:'2'},
        {tipo_hecho:'VARIACION_VR_PM',sentido:'GANANCIA',id_especie:39,cuenta_debito:'1',cuenta_credito:'2'}],
      costos_venta:[{id_especie:39,region:'GENERAL',es_activo:true,...costos}]},run);
    if (req.method==='PUT'&&u.pathname==='/finanzas/configuracion/costos-venta/39') {
      put++;
      if (modo==='put_403') return send(res,403,{error_code:'SIN_PERMISO'},run);
      if (modo==='restauracion_fallida'&&put>1) return send(res,500,{error_code:'FALLO_LOCAL'},run);
      costos={...body};return send(res,200,{id_parametro_costo_venta:900+put},run);
    }
    if (req.method==='GET'&&u.pathname==='/finanzas/periodos/201/variaciones')
      return send(res,200,variaciones,run);
    if (req.method==='GET'&&u.pathname==='/finanzas/lineas') return send(res,200,lineas,run);
    if (req.method==='GET'&&u.pathname==='/finanzas/periodos/201/mediciones')
      return send(res,200,modo==='a_con_medicion_previa'?[...mediciones,
        ...[101,102].map((aid,i)=>({id_medicion_posterior:590+i,
          id_activo_biologico:aid,id_evento:290+i,id_periodo_contable:201,estado:'COMPLETADO'}))]:mediciones,run);
    if (req.method==='GET'&&u.pathname==='/finanzas/periodos/201/eventos-pendientes')
      return send(res,200,auditoria.filter(x=>x.tipo_evento==='MEDICION_PENDIENTE').map(x=>({
        id_evento:x.id_referencia,id_activo_biologico:x.id_activo_biologico,identificador:'QA-102',
        fecha_evento:new Date().toISOString(),motivo:'VALOR_NETO_NO_POSITIVO',fecha_procesamiento:new Date().toISOString()})),run);
    if (req.method==='GET'&&u.pathname==='/finanzas/auditoria') {
      const aid=Number(u.searchParams.get('id_activo_biologico'));
      const rows=auditoria.filter(x=>x.id_activo_biologico===aid);
      const page=Number(u.searchParams.get('pagina')||1);
      return send(res,200,{total_registros:rows.length,eventos:rows.slice((page-1)*500,page*500)},run);
    }
    if (req.method==='GET'&&u.pathname==='/notificaciones') {
      const page=Number(u.searchParams.get('pagina')||1);
      return send(res,200,{total:avisos.length,items:avisos.slice((page-1)*50,page*50)},run);
    }
    return send(res,404,{error_code:'NO_ENCONTRADO'},run);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {server,api:'http://127.0.0.1:'+server.address().port,estado:()=>({registros,cerrado,costos,original,procesados,put})};
}
if (process.argv[2] === '--servidor') {
  assert.equal(process.argv[3],'todo_conforme');
  const s=await servidor('todo_conforme');
  process.stdout.write(s.api+'\n');
  await new Promise(()=>{});
} else {
let completados=0;
for (const modo of modos) {
  if (modo.startsWith('cypress_') && modo!=='cypress_cero' || modo==='login_nunca_sale')
    await probarIntercept(modo);
  if (modo==='B_medicion_evento_959') probarMedicion959();
  if (['ui_tabla_tardia','ui_b_ausente','ui_periodo_por_selector'].includes(modo)) probarTabla(modo);
  const s=await servidor(modo);
  try {
    const c={runId:'RUN-G34-V2-20261111-000000',version:2,
      version_anterior:modo==='reintentar_v2_conforme'?null:1,
      operacion:modo==='reintentar_v2_conforme'?'reintentar':'reevaluar',intento:1,
      referencia:'ENSAYO_LOCAL',ensayo:true,directorio:path.join(grupo,'RUN-PROHIBIDO')};
    const env={QA_AUTORIZADO:'SI',SIGAB_API_TEST_BASE:s.api,QA_SANDBOX_SECRET:'secreto-local',
      QA_CONTADOR_EMAIL:'contador@local.test',QA_CONTADOR_PASSWORD:'clave-local',
      QA_ADMIN_EMAIL:'admin@local.test',QA_ADMIN_PASSWORD:'clave-local'};
    const ui=modo==='ui_b_ausente'?
      {estado:'NO_CONCLUYENTE',motivo:'Fila B ausente tras cargar tabla',fila_b:'SIN_FILA',total_pruebas:1,total_failed:1,captura:true}:
      modo==='cypress_host_inesperado_bloqueado'?
      {estado:'NO_CONCLUYENTE',motivo:'Host inesperado bloqueado',fila_b:'SIN_FILA',total_pruebas:1,total_failed:1,captura:true}:
      ['panel_sin_pendiente','ambos_defectos'].includes(modo)?
      {estado:'RECHAZADO',motivo:'Fila A sin MEDICION_PENDIENTE',fila_a:'Medido',fila_b:'Medido',total_pruebas:1,total_failed:0,captura:true}:
      {estado:'APROBADO',motivo:'Filas conformes',fila_a:'Medición pendiente',fila_b:'Medido',total_pruebas:modo==='cypress_cero'?0:1,total_failed:0,captura:true};
    const r=await evaluar(c,{env,apiOverride:s.api,sinArtefactos:true,cypressOverride:ui});
    const x=r.casos['TC-M06-006'];
    const esperado=['sin_candidatos','put_403','restauracion_fallida','periodo_actual_cerrado','a_con_medicion_previa',
      'cypress_cero','cypress_host_inesperado_bloqueado','ui_b_ausente','delete_fallido'].includes(modo)?'NO_CONCLUYENTE':
      ['aviso_ausente','panel_sin_pendiente','ambos_defectos','variacion_de_A','B_bloqueado_por_A',
        'aviso_duplicado','aviso_sin_fecha','aviso_sin_identificador'].includes(modo)?'RECHAZADO':'APROBADO';
    assert.equal(x.estado,esperado,modo+': estado '+x.motivo);
    assert.ok(r.solicitudes.length<=PRESUPUESTO.solicitudes_totales,modo+': presupuesto API');
    assert.ok((r.cypress.solicitudes??0)<=PRESUPUESTO.solicitudes_cypress,modo+': presupuesto Cypress');
    assert.equal(s.estado().cerrado,modo!=='delete_fallido',modo+': DELETE con secreto');
    assert.ok(s.estado().registros.find(z=>z.metodo==='DELETE')?.secreto,modo+': DELETE sin secreto');
    if (modo!=='delete_fallido') assert.deepEqual(s.estado().costos,s.estado().original,modo+': configuración poscierre');
    assert.ok(s.estado().registros.filter(z=>z.metodo==='POST'&&z.ruta.endsWith('/eventos/crecimiento')).length<=3);
    assert.ok(s.estado().registros.filter(z=>z.metodo==='POST'&&z.ruta==='/finanzas/eventos/procesar').length<=3);
    assert.ok(s.estado().put<=3);
    if (['periodo_actual_cerrado','a_con_medicion_previa'].includes(modo))
      assert.equal(s.estado().registros.filter(z=>['POST','PUT'].includes(z.metodo)&&z.run).length,0,
        modo+': cero escrituras dentro del RUN');
    if (modo==='delete_fallido') assert.equal(r.oficial,false);
    if (['todo_conforme','reintentar_v2_conforme'].includes(modo)) assert.equal(r.oficial,true);
    if (modo==='todo_conforme') {
      const presupuesto={...r,solicitudes:Array(78).fill(null),cypress:{...r.cypress,solicitudes:14}};
      assert.deepEqual(motivosNoOficial(presupuesto,true),[],'78 API + 14 Cypress oficial');
      assert.match(informe(c,{...presupuesto,oficial:true}),/solicitudes API 78\/90 y Cypress 14\/16/);
      presupuesto.solicitudes=Array(91).fill(null);
      assert.deepEqual(motivosNoOficial(presupuesto,true),['presupuesto API excedido']);
      presupuesto.solicitudes=Array(78).fill(null);
      presupuesto.cypress.solicitudes=17;
      const motivos=motivosNoOficial(presupuesto,true);
      assert.deepEqual(motivos,['presupuesto Cypress excedido']);
      assert.match(informe(c,{...presupuesto,oficial:false,motivos_no_oficial:motivos}),
        /Condiciones de oficialidad incumplidas: presupuesto Cypress excedido/);
      assert.equal(r.casos['TC-M06-006'].observados.A.tipo_evento_aviso_valido,41);
      assert.equal(r.casos['TC-M06-006'].observados.A.tipo_contrastado_con_referencia_previa,false);
      assert.equal(r.efectos_persistentes_declarados[0].autorizacion,'ENSAYO_LOCAL');
      assert.match(informe(c,r),/tipo no contrastado con referencia previa/);
      assert.match(informe(c,r),/Efecto persistente declarado bajo la autorización de este RUN/);
      assert.match(informe(c,r),/rollback se limita a datos del sandbox/);
    }
    if (['todo_conforme','reintentar_v2_conforme'].includes(modo))
      assert.deepEqual(r.seguimiento_incidencias_v1.map(x=>x.estado_v2),['CORREGIDA','CORREGIDA']);
    if (modo==='ambos_defectos') assert.deepEqual(r.seguimiento_incidencias_v1.map(x=>x.estado_v2),['REPRODUCIDA','REPRODUCIDA']);
    if (modo==='aviso_duplicado') assert.equal(r.incidencias[0].severidad,'ALTA');
    if (modo==='aviso_ausente'||modo==='panel_sin_pendiente') assert.equal(r.incidencias.length,1);
    if (modo==='ambos_defectos') assert.equal(r.incidencias.length,2);
    if (modo==='restauracion_fallida') {assert.equal(r.cierre.costos.problema_critico,true);assert.equal(r.oficial,false);}
    if (modo==='cypress_cero') {
      assert.equal(r.oficial,false);
      assert.match(x.motivo,/Comprobación UI sin pruebas ejecutadas/);
    }
    if (modo==='ui_b_ausente') {
      assert.equal(r.oficial,false);assert.equal(r.incidencias.length,0);
      assert.match(x.motivo,/Fila B ausente tras cargar tabla/);
      assert.doesNotMatch(x.motivo,/Oráculo API y UI completo/);
      assert.match(informe(c,r),/Comprobación pendiente: UI — Fila B ausente tras cargar tabla/);
    }
    if (modo==='put_403') assert.equal(r.oficial,false);
    if (modo==='poscierre_config_original') assert.equal(r.cierre.costos.poscierre_original,true);
    if (modo==='registro_qa_fiel'||modo==='registro_oficial_valido') {
      const pub=structuredClone(r);
      pub.evidencias=['resultado.json','TC-M06-G34_reevaluacion_V2.md','preflight.json','newman/newman-G34.json',
        'newman/newman-G34.html','cypress/G34-UI-006-01.json','cypress/G34-cypress.json',
        'cypress/screenshots/g34.cy.js/G34-UI-006-01.png'];
      pub.comprobaciones.forEach(z=>z.evidencia=z.fuente==='UI'?'cypress/G34-UI-006-01.json':'resultado.json');
      const presentes=new Set(pub.evidencias);
      assert.equal(clasificarRegistro(CAPACIDADES,pub,presentes,{runId:c.runId,version:2}),true);
      if (modo==='registro_oficial_valido') {
        const anterior=structuredClone(pub);
        anterior.comprobaciones.forEach(z=>z.caso='TC-M06-G34 / TC-M06-006');
        assert.equal(clasificarRegistro(CAPACIDADES,anterior,presentes,{runId:c.runId,version:2}),false);
      }
      pub.cypress.total_pruebas=0;
      assert.equal(clasificarRegistro(CAPACIDADES,pub,presentes,{runId:c.runId,version:2}),false);
    }
    if (modo==='todo_conforme'||modo==='aviso_ausente'||modo==='ambos_defectos') {
      const md=informe(c,r);assert.match(md,/Detalle por caso/);assert.match(md,/Costos originales/);
      assert.match(md,/A \(APROBADO\)|A \(RECHAZADO\)/);assert.match(md,/B \(APROBADO\)/);
      assert.match(md,modo==='ambos_defectos'?/UI \(RECHAZADO\)/:/UI \(APROBADO\)/);
      assert.match(md,/\*\*Esperado:\*\*/);assert.match(md,/\*\*Observado y decisión:\*\*/);
      assert.doesNotMatch(md,/Observado: \{/);
      if (modo==='ambos_defectos') {
        assert.match(md,/INC-M06-G34-02 — El panel de medición muestra como Medido/);
        assert.match(md,/\*\*Pasos para reproducir:\*\*/);
        assert.match(md,/\*\*Primera atención:\*\* Desarrollo/);
        assert.match(md,/B se mostró correctamente/);
        assert.doesNotMatch(md,/condición de A o la medición completada de B/);
      }
      if (modo==='aviso_ausente') {assert.match(md,/avisos relacionados 0/);
        assert.equal(r.incidencias[0].equipo_inicial,'Desarrollo');
        assert.equal(r.incidencias[0].severidad,'ALTA');
        assert.match(md,/Pasos para reproducir/);
        assert.match(md,/RF_83_NO_COMPLETADO/);
        assert.match(md,/línea base de bandeja/);}
    }
    assert.deepEqual(archivos(),antes,modo+': sin archivos residuales');
    completados++;
  } finally {await new Promise(resolve=>s.server.close(resolve));}
}
const sonda=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'application/json'});res.end('{"ok":true}');});
await new Promise(resolve=>sonda.listen(0,'127.0.0.1',resolve));
try {
  const entrada=JSON.stringify({coleccion:{info:{name:'sonda',
    schema:'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'},
    item:[{name:'sonda',request:{method:'GET',url:'http://127.0.0.1:'+sonda.address().port+'/sonda'}}]},
    environment:{values:[]},timeout:30000});
  const salida=await new Promise(resolve=>{
    let hijo;try {hijo=spawn(process.execPath,[fileURLToPath(new URL('./newman_hijo.mjs',import.meta.url))],
      {stdio:['pipe','pipe','pipe'],windowsHide:true});} catch(e) {resolve({error:e.code});return;}
    let out='',error=null;hijo.on('error',e=>{error=e.code;});
    hijo.stdout.on('data',b=>out+=b.toString());hijo.stdin.on('error',()=>{});
    hijo.stdin.end(entrada);hijo.on('close',codigo=>resolve({codigo,out,error}));
  });
  if (salida.error) console.log('OK newman_hijo: no ejecutable en este entorno ('+salida.error+')');
  else {const x=JSON.parse(salida.out);assert.equal(salida.codigo,0);assert.equal(x.solicitudes[0].http,200);
    console.log('OK newman_hijo: process.execPath, 1 lectura loopback HTTP 200');
    var newmanEjecutable=true;}
} finally {await new Promise(resolve=>sonda.close(resolve));}
if (newmanEjecutable) {
  let hijo, hijoCerrado=false;
  try {
    hijo=spawn(process.execPath,[fileURLToPath(import.meta.url),'--servidor','todo_conforme'],
      {stdio:['ignore','pipe','pipe'],windowsHide:true});
    hijo.on('close',()=>{hijoCerrado=true;});
    const url=await new Promise((resolve,reject)=>{
      let salida='',error='';
      hijo.stdout.on('data',b=>{salida+=b.toString();if(salida.includes('\n')) {
        const linea=salida.split(/\r?\n/,1)[0];
        /^http:\/\/127\.0\.0\.1:\d+$/.test(linea)?resolve(linea):reject(Error('URL loopback inválida: '+linea));
      }});
      hijo.stderr.on('data',b=>error+=b.toString());
      hijo.on('error',reject);
      hijo.on('close',codigo=>reject(Error('Servidor A4 terminó ('+codigo+'): '+error)));
    });
    const ejemplo=path.resolve(os.tmpdir(),'g34-verificar-ejemplo');
    assert.equal(path.dirname(ejemplo),path.resolve(os.tmpdir()),'A4: destino temporal limitado');
    fs.rmSync(ejemplo,{recursive:true,force:true});
    const fechaRun=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',
      month:'2-digit',day:'2-digit'}).format(new Date()).replaceAll('-','');
    const runId='RUN-G34-V2-'+fechaRun+'-'+new Date().toISOString().slice(11,19).replaceAll(':','');
    const directorio=path.join(ejemplo,runId);
    fs.mkdirSync(directorio,{recursive:true});
    const env={QA_AUTORIZADO:'SI',SIGAB_API_TEST_BASE:url,QA_SANDBOX_SECRET:'secreto-local',
      QA_CONTADOR_EMAIL:'contador@local.test',QA_CONTADOR_PASSWORD:'clave-local',
      QA_ADMIN_EMAIL:'admin@local.test',QA_ADMIN_PASSWORD:'clave-local'};
    const c={runId,directorio,version:2,version_anterior:1,operacion:'reevaluar',intento:1,
      referencia:'ENSAYO_LOCAL',ensayo:true};
    const ui={estado:'APROBADO',motivo:'Filas simuladas; no evidencia TEST',fila_a:'Medición pendiente',
      fila_b:'Medido',total_pruebas:1,total_failed:0,captura:true};
    const r=await evaluar(c,{env,apiOverride:url,cypressOverride:ui});
    fs.writeFileSync(path.join(ejemplo,'capacidades.json'),JSON.stringify(CAPACIDADES,null,2));
    if(r.oficial){
      const presentes=new Set(r.evidencias.filter(x=>fs.existsSync(path.join(directorio,x))));
      assert.equal(clasificarRegistro(CAPACIDADES,r,presentes,{runId,version:2}),true);
      console.log('OK ejemplo local V2 (simulado; NO TEST): '+directorio);
      console.log('resultado.json: '+path.join(directorio,'resultado.json'));
      console.log('capacidades.json: '+path.join(ejemplo,'capacidades.json'));
    } else console.log('Ejemplo local V2 no oficial: '+JSON.stringify({
      casos:Object.fromEntries(Object.entries(r.casos).map(([k,v])=>[k,{estado:v.estado,motivo:v.motivo}])),
      cierre_http:r.cierre?.run?.cierre_http,rollback:r.cierre?.rollback,
      newman_fallos:r.herramientas?.newman?.fallos,newman_codigo:r.herramientas?.newman?.codigo,
      cypress:{estado:r.cypress?.estado,total_pruebas:r.cypress?.total_pruebas,error:r.cypress?.error}
    }));
  } catch(e) {console.log('Ejemplo local V2 no oficial: '+(e.code??e.message));}
  finally {if(hijo && !hijoCerrado){const cerrado=new Promise(resolve=>hijo.once('close',resolve));hijo.kill();await cerrado;}}
} else console.log('A4 no ejecutado: Newman hijo no disponible en este entorno.');
assert.deepEqual(archivos(),antes,'sin archivos residuales');
assert.equal(intentosRemotos,0,'guarda de red: cero intentos remotos');
console.log('OK G34: '+completados+'/'+modos.length+' modos; aislamiento y cierre comprobados; registro QA fiel');
}
