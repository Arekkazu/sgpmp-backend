import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import {ejecutar,CAPACIDADES} from '../g43.mjs';
import {CASOS,LIMITE} from '../lib/g43_core.mjs';
import {evaluarEstimacion1644} from '../lib/evidencia_estimacion.mjs';

assert.equal(LIMITE.solicitudes_totales,230);
const baseEstimacion={calculos:[],avisos:[],cierre:{activos_procesados:2},congelados:[{id_especie:[544,true],id_precio_mercado:492,precio_unitario:'1000000'}],precio492:'1000000'};
const sinVariacion={tipo_evento:'MEDICION_SIN_VARIACION',id_activo_biologico:1644,id_referencia:267,payload_evento:{}};
assert.equal(evaluarEstimacion1644({...baseEstimacion,auditoria:[sinVariacion]}).acreditada,false,'variaciÃ³n cero sin marca');
const conEstimacion={tipo_evento:'MEDICION_CON_ESTIMACION',id_activo_biologico:1644,id_referencia:267,payload_evento:{precio_usado:{id_precio_mercado:492,precio_unitario:'1000000'}}};
assert.equal(evaluarEstimacion1644({...baseEstimacion,auditoria:[sinVariacion,conEstimacion]}).vias.auditoria,true,'variaciÃ³n cero con auditorÃ­a de estimaciÃ³n');

const RUN='RUN-G43-V2-20261112-000000';
const err=(code,message=code)=>({error_code:code,message,fields:[],timestamp:new Date().toISOString()});
const p=(id,estado,nit,cierre=null)=>({id_periodo_contable:id,estado,numero_id_tributaria:nit,fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30',fecha_cierre:null,ultimo_cierre:cierre});
const cierre67={id_cierre:67,estado:'EN_PROCESO',paso_actual:3,precios_congelados:null};
const l=(id,periodo,activo)=>({id_linea_asiento_nic41:id,id_activo_biologico:activo,estado:'REGISTRADA',tipo_hecho:'VARIACION_VR_TB',sentido:'GANANCIA',id_especie:39,subtipo_costo:null,valor:'1',tipo_evidencia:null,cuenta_debito:'1105',cuenta_credito:'4105',numero_id_tributaria:'N',id_periodo_contable:periodo,estado_trazabilidad:'VERIFICACION_PENDIENTE'});
const cl=x=>structuredClone(x);
const base=[p(8,'EN_CIERRE','N-A',cierre67),p(266,'ABIERTO','N-G')];
const linea17=l(17,8,944),linea3726=l(3726,266,1644);
const precio39={id_precio_mercado:100,id_especie:39,categoria:'POR_CABEZA',id_metrica_produccion:null,es_aplicado:false,precio_unitario:'10000',fuente:'MERCADO_ACTIVO',fecha_vigencia:'2026-11-09',fecha_vencimiento:null,unidad_medida:'UNIDAD',evidencia:'LOCAL',estado:'VIGENTE'};
const precio39Especie={...precio39,id_precio_mercado:18,categoria:'PESO_KG',precio_unitario:'9600',fecha_vigencia:'2026-11-07'};
const precio544={...precio39,id_precio_mercado:492,id_especie:544,precio_unitario:'1000000',fecha_vencimiento:'2026-11-10'};
const activos=[[943,463,39,false],[944,463,39,false],[1643,472,544,true],[1644,472,544,false]].map(([id_activo_biologico,id_finca,id_especie,valorado_por_costo])=>({id_activo_biologico,id_finca,id_especie,estado:'ACTIVO',valorado_por_costo,depreciacion_acumulada:null}));
const pre8={puede_cerrar:true,bloqueos:[],activos_sin_precio:[],lineas_sin_trazabilidad:[{id_linea:17,tipo_hecho:'VARIACION_VR_TB',id_activo_biologico:944,identificador:'A-944',faltantes:['lecturas_nic41'],nivel_fallo:1}],requiere_autorizacion:true};
const pre266={puede_cerrar:true,bloqueos:[],activos_sin_precio:[{id_activo_biologico:1644,identificador:'A-1644',especie:'Bovino'}],lineas_sin_trazabilidad:[],requiere_autorizacion:true};
const pre267=cl(pre266);
const calc=(id,activo,precio,estimado=false)=>({id_calculo_valor_razonable:id,id_activo_biologico:activo,tiene_valor_estimado:estimado,fecha_calculo:null,precio_unitario:String(precio),magnitud:'1',valor_razonable_bruto:String(precio),valor_neto:String(precio)});

function fixture(modo){
  const periodos=cl(base),precios=[cl(precio39),cl(precio39Especie),cl(precio544)],avisos=modo==='bandeja_400'?Array.from({length:400},(_,i)=>({id_notificacion:i+1,mensaje:'Aviso local anterior'})):[],escrituras=[],intentos=new Map();let deleted=false,postHeaders=true,reads=0,alterado=false;
  if(modo==='preflight_8')periodos[0].estado='CERRADO';
  const pre266Local=cl(pre266);if(modo==='preflight_266')pre266Local.activos_sin_precio.length=0;
  const pre=n=>n===8?{...pre8,lineas_sin_trazabilidad:pre8.lineas_sin_trazabilidad.map(x=>({...x,nivel_fallo:modo==='contrato_primera_lectura'?'INVALIDO':modo==='nivel_null'?null:x.nivel_fallo}))}:n===266?pre266Local:pre267;
  const reply=(res,status,data,req)=>{if(modo==='conforme_extra'&&req.method==='GET'&&status===200){const extra=x=>Array.isArray(x)?x.map(extra):x&&typeof x==='object'?{...Object.fromEntries(Object.entries(x).map(([k,v])=>[k,extra(v)])),campo_extra:'LOCAL'}:x;data=extra(data);}res.writeHead(status,{'content-type':'application/json',...(req.headers['x-test-run-id']?{'x-test-run-id':req.headers['x-test-run-id']}:{})});res.end(JSON.stringify(data));};
  const server=http.createServer(async(req,res)=>{
    const url=new URL(req.url,'http://local'),ruta=url.pathname.replace(/^\/api/,'');const met=req.method,n=Number(ruta.split('/')[3]);
    const chunks=[];for await(const c of req)chunks.push(c);const body=chunks.length?JSON.parse(Buffer.concat(chunks).toString()):{};
    if(deleted&&met==='GET'){reads++;if(req.headers['x-test-run-id']||req.headers['x-sandbox-secret'])postHeaders=false;}
    if(met==='POST'&&ruta!=='/sesiones/'||met==='DELETE')escrituras.push({met,ruta,body});
    let status=200,data;
    if(met==='POST'&&ruta==='/sesiones/')data={token:'LOCAL'};
    else if(met==='GET'&&ruta==='/sesiones/me/permisos')data={permisos:[['cierre_periodo',2],['cierre_periodo',5],['configuracion_contable',2],['configuracion_contable',1],['auditoria_financiera',2],['precios_mercado',2],['precios_mercado',1],['valoracion_activos',2],['revelaciones_nic41',2]].map(([nombre_recurso,id_accion])=>({nombre_recurso,id_accion}))};
    else if(met==='GET'&&ruta==='/finanzas/periodos')data=cl(periodos);
    else if(met==='GET'&&ruta==='/finanzas/activos')data=cl(activos);
    else if(met==='GET'&&ruta==='/finanzas/configuracion')data={general:{pct_umbral_desviacion_precio:'20'},especies:[{id_especie:39,categoria_precio:'PESO_KG'}],matriz:[]};
    else if(met==='GET'&&ruta==='/finanzas/precios')data=cl(precios.filter(x=>x.id_especie===Number(url.searchParams.get('id_especie'))));
    else if(met==='GET'&&/^\/finanzas\/periodos\/\d+\/prevalidacion$/.test(ruta))data=cl(pre(n));
    else if(met==='GET'&&ruta==='/finanzas/lineas')data=Number(url.searchParams.get('id_periodo_contable'))===8?[{...cl(linea17),estado:alterado?'ALTERADA':linea17.estado}]:Number(url.searchParams.get('id_periodo_contable'))===266?[cl(linea3726)]:Number(url.searchParams.get('id_periodo_contable'))===600?[{...cl(linea17),id_periodo_contable:600,estado_trazabilidad:'PENDIENTE_TRAZABILIDAD'}]:[];
    else if(met==='GET'&&/^\/finanzas\/periodos\/\d+\/(comprobantes|variaciones)$/.test(ruta))data=[];
    else if(met==='GET'&&/^\/finanzas\/periodos\/\d+\/calculos$/.test(ruta))data=n===8?[calc(1,943,modo==='precio_nuevo'?10080:9600)]:n===266?[calc(2,1643,100)]:n===267?[calc(3,1644,1000000,!['sin_estimacion','variacion_cero_con_auditoria','variacion_cero_sin_auditoria'].includes(modo))]:[];
    else if(met==='GET'&&ruta==='/finanzas/activos/1644')data={activo:{id_activo_biologico:1644,id_especie:544,id_finca:472,numero_id_tributaria:'N-G',estado:'ACTIVO',id_dispositivo_iot:null},valoracion_costo:modo==='costo_1644'?{es_activa:true,vida_util_meses:120,razon_sin_mercado:'LOCAL'}:null};
    else if(met==='GET'&&ruta==='/notificaciones'){const pagina=Number(url.searchParams.get('pagina')||1),tamano=Number(url.searchParams.get('tamano')||50);data={items:cl([...avisos].reverse().slice((pagina-1)*tamano,pagina*tamano)),total:avisos.length};}
    else if(met==='GET'&&ruta==='/finanzas/auditoria'){
      const eventos=modo==='cierre8_500'?[{tipo_evento:'CIERRE_PERIODO_FALLIDO',id_referencia:8,id_usuario:1,timestamp_evento:new Date().toISOString(),payload_evento:{paso:3,error:'LOCAL'}}]:modo.startsWith('variacion_cero_')?[{tipo_evento:'MEDICION_SIN_VARIACION',id_referencia:267,id_activo_biologico:1644,id_usuario:1,timestamp_evento:new Date().toISOString(),payload_evento:{}},...(modo==='variacion_cero_con_auditoria'?[{tipo_evento:'MEDICION_CON_ESTIMACION',id_referencia:267,id_activo_biologico:1644,id_usuario:1,timestamp_evento:new Date().toISOString(),payload_evento:{precio_usado:{id_precio_mercado:492,precio_unitario:'1000000'}}}]:[])]:[];
      data={eventos,total_registros:eventos.length};
    }
    else if(met==='POST'&&ruta==='/finanzas/periodos/8/cierre/cancelacion'){
      const pe=periodos.find(x=>x.id_periodo_contable===8);
      if(modo==='cancel_falla'){status=500;data=err('ERROR_INTERNO');}else{if(modo==='no_con_cambios'&&pe.ultimo_cierre?.id_cierre!==67)alterado=true;pe.estado='ABIERTO';pe.ultimo_cierre={id_cierre:pe.ultimo_cierre?.id_cierre??67,estado:'ROLLBACK',paso_actual:3,precios_congelados:null};data={id_periodo_contable:8,id_cierre:67,estado:'ABIERTO'};}
    }
    else if(met==='POST'&&ruta==='/finanzas/periodos/266/cierre/cancelacion'){periodos.find(x=>x.id_periodo_contable===266).estado='ABIERTO';data={id_periodo_contable:266,id_cierre:2661,estado:'ABIERTO'};}
    else if(met==='POST'&&ruta==='/finanzas/precios'){status=201;data={id_precio_mercado:493};precios.push({...precio39,...body,id_precio_mercado:493,fecha_vencimiento:null});}
    else if(met==='POST'&&/^\/finanzas\/periodos\/\d+\/cierre$/.test(ruta)){
      intentos.set(n,(intentos.get(n)??0)+1);const pe=periodos.find(x=>x.id_periodo_contable===n);
      if(n===267&&body.activos_estimados?.includes(1643)){status=400;data=err(modo==='sin_400'?'OTRO':'ACTIVO_ESTIMADO_NO_APLICA');}
      else if((n===8||n===266)&&!body.autorizar_exclusiones||n===267&&!body.activos_estimados?.includes(1644)&&modo!=='no_decision_200'){
        status=409;data=err('EXCLUSION_REQUIERE_AUTORIZACION');pe.estado='EN_CIERRE';pe.ultimo_cierre={id_cierre:n===8?68:2661,estado:'EN_PROCESO',paso_actual:3,precios_congelados:modo==='primer_congelado'&&n===8&&intentos.get(8)===1?[{id_especie:[39,false],id_precio_mercado:18,precio_unitario:'9600',fuente:'MERCADO_ACTIVO',fecha_vigencia:'2026-11-07'}]:null};
        if(modo==='pausa_abierto'&&n===8)pe.estado='ABIERTO';
      }else if(modo==='cierre8_500'&&n===8){status=500;data=err('ERROR_INTERNO');}
      else{
        pe.estado='CERRADO';pe.ultimo_cierre={id_cierre:n,estado:'COMPLETADO',paso_actual:9,precios_congelados:n===8?[{id_especie:modo==='contrato_congelado_invalido'?[39,'false']:[39,false],id_precio_mercado:modo==='precio_nuevo'?493:18,precio_unitario:modo==='precio_nuevo'?'10080':'9600',fuente:'MERCADO_ACTIVO',fecha_vigencia:modo==='precio_nuevo'?'2026-11-13':'2026-11-07'}]:[]};
        const siguiente=n===8?600:n===266?267:268;periodos.push(p(siguiente,'ABIERTO',pe.numero_id_tributaria));
        data={id_cierre:n,id_periodo_contable:n,periodo:'2026-11',estado:'CERRADO',activos_procesados:n===266?1:2,activos_excluidos:n===266?[{id_activo_biologico:1644,identificador:'A-1644',motivo:modo==='procesa_1644'?'OTRO':'PENDIENTE_PRECIO',detalle:null}]:[],lineas_excluidas:n===8?[{id_linea:17,tipo_hecho:'VARIACION_VR_TB',id_activo_biologico:944,faltantes:['lecturas_nic41'],nivel_fallo:1}]:[],comprobantes:[],hash_cierre:'LOCAL',id_periodo_siguiente:siguiente,reportes:{estado_resultados:{},informe_revelaciones:{}}};
      }
      avisos.push({id_notificacion:avisos.length+1,mensaje:`Aviso local de cierre ${n}`});
    }
    else if(met==='DELETE'&&ruta===`/test-control/runs/${RUN}`){if(modo==='delete_falla'){status=500;data=err('ERROR_INTERNO');}else{deleted=true;alterado=false;periodos.splice(0,periodos.length,...cl(base));precios.splice(0,precios.length,cl(precio39),cl(precio39Especie),cl(precio544));data={};}}
    else{status=404;data=err('NO_ENCONTRADO');}
    reply(res,status,data,req);
  });
  return {server,escrituras,intentos,get postHeaders(){return postHeaders;},get reads(){return reads;}};
}

function hijo(modo){return async(script,input)=>{
  if(script==='cypress_hijo.mjs'){const panel=input.panel,dir=input.dir,shots=path.join(dir,'screenshots','g43.cy.js');fs.mkdirSync(shots,{recursive:true});const capturas_tramos=[`G43-UI-${panel}-tabla-1.png`];for(const n of capturas_tramos)fs.writeFileSync(path.join(shots,n),'LOCAL');const acta={estado:'APROBADO',lista_completa:!(modo==='ui_incompleta'&&panel==='027'||modo==='ui_025_incompleta'&&panel==='025'),decision_por_activo:!(modo==='ui_026_sin_decision'&&panel==='026'),total_prevalidacion:1,peticiones:[],capturas_tramos,controles_citados:['Cerrar periodo','Excluir de este cierre'],resumen_dom:{encabezados:["Precondiciones para cerrar"],tablas:[{filas:["A-1644"]}],controles:[{texto:"Cerrar período"}]}};if(!acta.lista_completa||!acta.decision_por_activo)acta.estado='RECHAZADO';if((modo==='cypress_falla'&&panel==='025')||(modo==='contrato_congelado_invalido'&&panel==='027')){acta.estado='NO_CONCLUYENTE';acta.motivo=`Timed out retrying after 30000ms: Expected to find element: #fin-periodo option[value="${input.periodo}"]`;}
    fs.writeFileSync(path.join(dir,`G43-UI-${panel}.json`),JSON.stringify(acta));return{code:acta.motivo?2:0,data:{acta,totalTests:modo==='cypress_cero'&&panel==='025'?0:1},error:''};}
  assert.equal(script,'newman_hijo.mjs');fs.mkdirSync(input.salida,{recursive:true});fs.writeFileSync(path.join(input.salida,'newman-G43.json'),'{}');fs.writeFileSync(path.join(input.salida,'newman-G43.html'),'<html></html>');return{code:0,data:{codigo:0,fallos:0,reportes:true,solicitudes:10},error:''};
};}

const modos=[
  ['conforme',['APROBADO','APROBADO','APROBADO','APROBADO'],true],
  ['bandeja_400',['APROBADO','APROBADO','APROBADO','APROBADO'],true],
  ['presupuesto',CASOS.map(()=>'NO_CONCLUYENTE'),false],
  ['conforme_extra',['APROBADO','APROBADO','APROBADO','APROBADO'],true],
  ['nivel_null',['APROBADO','APROBADO','APROBADO','APROBADO'],true],
  ['contrato_primera_lectura',CASOS.map(()=>'NO_CONCLUYENTE'),false],
  ['finally_falla',['APROBADO','APROBADO','APROBADO','APROBADO'],false],
  ['informe_falla',['APROBADO','APROBADO','APROBADO','APROBADO'],false],
  ['pausa_abierto',['RECHAZADO','APROBADO','APROBADO','RECHAZADO'],true],
  ['cierre8_500',['RECHAZADO','APROBADO','APROBADO','RECHAZADO'],true],
  ['no_con_cambios',['APROBADO','APROBADO','APROBADO','RECHAZADO'],true],
  ['precio_nuevo',['RECHAZADO','APROBADO','APROBADO','APROBADO'],true],
  ['primer_congelado',['APROBADO','APROBADO','APROBADO','APROBADO'],true],
  ['ui_incompleta',['APROBADO','APROBADO','APROBADO','RECHAZADO'],true],
  ['ui_025_incompleta',['APROBADO','RECHAZADO','APROBADO','APROBADO'],true],
  ['ui_026_sin_decision',['APROBADO','APROBADO','RECHAZADO','APROBADO'],true],
  ['cypress_cero',['APROBADO','NO_CONCLUYENTE','APROBADO','APROBADO'],false],
  ['cypress_falla',['APROBADO','NO_CONCLUYENTE','APROBADO','APROBADO'],false],
  ['contrato_congelado_invalido',CASOS.map(()=>'NO_CONCLUYENTE'),false],
  ['procesa_1644',['APROBADO','RECHAZADO','APROBADO','APROBADO'],true],
  ['sin_400',['APROBADO','APROBADO','RECHAZADO','APROBADO'],true],
  ['no_decision_200',['APROBADO','APROBADO','RECHAZADO','APROBADO'],true],
  ['sin_estimacion',['APROBADO','APROBADO','RECHAZADO','APROBADO'],true],
  ['variacion_cero_con_auditoria',['APROBADO','APROBADO','APROBADO','APROBADO'],true],
  ['variacion_cero_sin_auditoria',['APROBADO','APROBADO','RECHAZADO','APROBADO'],true],
  ['costo_1644',['APROBADO','APROBADO','RECHAZADO','APROBADO'],true],
  ['preflight_8',CASOS.map(()=>'NO_CONCLUYENTE'),false],
  ['preflight_266',CASOS.map(()=>'NO_CONCLUYENTE'),false],
  ['cancel_falla',CASOS.map(()=>'NO_CONCLUYENTE'),false],
  ['delete_falla',['APROBADO','APROBADO','APROBADO','APROBADO'],false]
];
for(const [modo,esperado,oficial] of modos){
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g43-v2-sim-')),dir=path.join(tmp,RUN),f=fixture(modo);fs.mkdirSync(dir);
  try{
    if(modo==='presupuesto')LIMITE.solicitudes_totales=30;
    await new Promise(ok=>f.server.listen(0,'127.0.0.1',ok));const api=`http://127.0.0.1:${f.server.address().port}/api`;
    const falloLocal=modo==='finally_falla'?'finally':modo==='informe_falla'?'informe':undefined;
    const r=await ejecutar({dir,runId:RUN,version:2,ref:'LOCAL',operacion:'REEVALUAR'}, {QA_SANDBOX_SECRET:'LOCAL',QA_CONTADOR_EMAIL:'local@example.invalid',QA_CONTADOR_PASSWORD:'LOCAL'},{ensayo:true,api,hijo:hijo(modo),falloLocal});
    assert.deepEqual(CASOS.map(c=>r.casos[c].estado),esperado,`${modo}: ${JSON.stringify({problemas:r.problemas_tecnicos,casos:r.casos})}`);
    if(modo==='presupuesto'){assert.equal(r.rollback.verificado,true);assert.equal(r.condiciones_oficialidad.presupuesto,false);}
    if(modo==='bandeja_400'){assert(r.total_solicitudes_api<120);assert(r.cierres.every(x=>x.avisos.length===1));assert.equal(r.solicitudes.filter(x=>x.metodo==='GET'&&x.ruta==='/notificaciones').length,r.cierres.length*2,'máximo dos lecturas por cierre');}
    assert.equal(r.oficial,oficial,`${modo}: ${JSON.stringify({condiciones:r.condiciones_oficialidad,rollback:r.rollback,problemas:r.problemas_tecnicos})}`);
    assert(f.escrituras.filter(x=>x.met!=='DELETE').length===0||!modo.startsWith('preflight_'));
    if(modo==='contrato_primera_lectura')assert.equal(f.escrituras.filter(x=>x.met!=='DELETE').length,0);
    assert.equal(f.postHeaders,true);if(!['delete_falla','finally_falla'].includes(modo))assert(f.reads>0);
    assert(f.escrituras.some(x=>x.met==='DELETE'),`${modo}: DELETE no intentado`);
    assert(fs.existsSync(path.join(dir,'preflight.json')));
    assert(fs.existsSync(path.join(dir,'TC-M06-G43_reevaluacion_V2.md')));
    assert(fs.existsSync(path.join(dir,'resultado.json')));
    const guardado=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json'),'utf8'));
    assert.deepEqual(guardado.casos,r.casos);
    if(modo==='primer_congelado')assert.equal(r.precios[0].congelado_pausa_primero.id_precio_mercado,18);
    if(r.precios.length){assert.equal(r.precios[0].p_ini,18,`${modo}: precio de la categorÃ­a de la especie`);assert.equal(r.precios[0].categoria,'PESO_KG');const alta=f.escrituras.find(x=>x.ruta==='/finanzas/precios');assert.equal(alta?.body.categoria,'PESO_KG');assert.equal(alta?.body.fuente,'MERCADO_ACTIVO');}
    if(modo.startsWith('variacion_cero_')){
      assert.equal(guardado.diagnostico.estimacion_1644.auditoria_sin_variacion,true);
      assert.equal(guardado.diagnostico.estimacion_1644.vias.auditoria,modo==='variacion_cero_con_auditoria');
      if(modo==='variacion_cero_sin_auditoria')assert(r.observaciones.some(x=>x.includes('variación cero')));
    }
    if(modo==='cypress_falla'){
      assert.match(r.casos['TC-M06-025'].motivo,/Expected to find element/);
      assert.match(r.problemas_tecnicos.find(x=>x.startsWith('CYPRESS_025_')),/Expected to find element/);
      assert(!r.incidencias.some(x=>x.casos.includes('TC-M06-025')));
    }
    if(modo==='contrato_congelado_invalido'){
      assert.match(r.casos['TC-M06-024'].motivo,/TIPO_INVALIDO/);
      assert.match(r.casos['TC-M06-027'].motivo,/TIPO_INVALIDO/);
    }
    if(modo==='conforme'){
      assert(r.observaciones.some(x=>x.includes('precios_congelados.id_especie')));
      assert(fs.readFileSync(path.join(dir,'TC-M06-G43_reevaluacion_V2.md'),'utf8').includes('precios_congelados.id_especie'));
    }
    if(['contrato_primera_lectura','finally_falla','informe_falla'].includes(modo))assert(guardado.problemas_tecnicos.length>0);
    if(['contrato_primera_lectura','finally_falla','informe_falla'].includes(modo))assert(fs.readFileSync(path.join(dir,'TC-M06-G43_reevaluacion_V2.md'),'utf8').includes('NO OFICIAL'));
    assert.equal(fs.readdirSync(dir).filter(x=>x.endsWith('.md')).length,1);
    const contenido=fs.readFileSync(path.join(dir,'resultado.json'),'utf8')+fs.readFileSync(path.join(dir,'TC-M06-G43_reevaluacion_V2.md'),'utf8');
    assert(!/local@example\.invalid|Bearer LOCAL|"token"\s*:\s*"LOCAL"/i.test(contenido));
    if(modo==='conforme')assert(fs.readFileSync(path.join(dir,'TC-M06-G43_reevaluacion_V2.md'),'utf8').startsWith('# TC-M06-G43 — reevaluación V2 oficial - APROBADO'));
    if(modo==='precio_nuevo'){const informe=fs.readFileSync(path.join(dir,'TC-M06-G43_reevaluacion_V2.md'),'utf8');assert.match(informe,/reevaluación V2 oficial - RECHAZADO/);assert.match(informe,/Precio inicial 18\/2026-11-07; precio nuevo 493\/2026-11-13; congelado/);assert.match(informe,/Evidencia: G43-\d+/);}
    if(modo==='sin_estimacion'){const informe=fs.readFileSync(path.join(dir,'TC-M06-G43_reevaluacion_V2.md'),'utf8');assert.match(informe,/Vías de estimación consultadas:/);assert.match(informe,/variación cero:/);}
    if(modo==='conforme')assert(Object.values(r.seguimiento).every(x=>x==='CORREGIDA'));
    if(modo==='ui_incompleta')assert.equal(r.seguimiento['INC-M06-G43-02'],'REPRODUCIDA');
    if(modo==='cierre8_500')assert.equal(r.seguimiento['INC-M06-G32-01'],'REPRODUCIDA');
    if(modo==='conforme'&&process.env.QA_VERIFICAR_EJEMPLO){const destino=process.env.QA_VERIFICAR_EJEMPLO;if(!path.resolve(destino).startsWith(path.resolve(os.tmpdir())+path.sep))throw Error('EJEMPLO_FUERA_TEMPORAL');fs.mkdirSync(destino,{recursive:true});fs.cpSync(dir,path.join(destino,RUN),{recursive:true,force:true});fs.writeFileSync(path.join(destino,'capacidades.json'),JSON.stringify(CAPACIDADES,null,2));}
    console.log(`OK v2_${modo}: ${esperado.join('/')} oficial=${oficial} solicitudes=${r.total_solicitudes_api}`);
  }finally{LIMITE.solicitudes_totales=230;await new Promise(ok=>f.server.close(ok));assert(path.resolve(tmp).startsWith(path.resolve(os.tmpdir())+path.sep));fs.rmSync(tmp,{recursive:true,force:true});}
}





