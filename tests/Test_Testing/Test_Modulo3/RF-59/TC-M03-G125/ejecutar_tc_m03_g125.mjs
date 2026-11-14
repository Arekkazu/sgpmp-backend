#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { args, context, ENV_PATH, parseEnv, query, secretsFree, ROOT } from '../TC-M03-G120/rf59_base.mjs';
import { xlsxSheets, dataRows, metadataText } from '../TC-M03-G124/validadores.mjs';

export const CASOS=['TC-M03-251','TC-M03-252','TC-M03-253','TC-M03-265'];
const DIR=path.dirname(fileURLToPath(import.meta.url));
export function plan250({device,sensor,serial,at}) {
  const start=Date.parse(at);
  if(!Number.isFinite(start))throw Error('Fecha inválida');
  return Array.from({length:250},(_,i)=>({device_id:device,sensor_id:sensor,tipo_variable:'TEMPERATURA_AMBIENTAL',valor:25+i/100,unidad:'°C',timestamp_captura:new Date(start+i*1000).toISOString(),access_key:serial,origen:'TIEMPO_REAL',estado_conectividad:true}));
}
export function codeOf(body){return body?.code ?? body?.detail?.code ?? body?.error?.code ?? null;}
export function page2Valid(page){return page?.pagina===2 && page?.por_pagina===100 && page?.total===250 && Array.isArray(page?.items) && page.items.length===100;}
export function failureControlled({status,bytes,visible,unchanged,informed}) {
  return status>=400 && !visible && !bytes?.length && unchanged===true && informed===true;
}
export function ratePlan(requests=20,windowMs=60000){
  if(!Number.isSafeInteger(requests)||requests<1||requests>30||!Number.isSafeInteger(windowMs)||windowMs<1000||windowMs>120000)throw Error('Plan de carga fuera del límite QA');
  return Array.from({length:requests},(_,i)=>Math.floor(i*windowMs/requests));
}
export function faultHook(paths){
  return Object.entries(paths||{}).find(([route,methods])=>{
    const op=methods.post, description=String(op?.description||'')+' '+String(op?.summary||'');
    return route.startsWith('/test-control/') && !route.includes('{') && op && !op.requestBody
      && !(op.parameters||[]).some(p=>p.required) && /export/i.test(description)
      && /fallo|failure|timeout/i.test(description) && /sandbox/i.test(description) && /run_id|rollback/i.test(description);
  })?.[0]||null;
}
export function ratePolicy(op){
  const policy=op?.['x-rate-limit'];
  const max=Number(policy?.limite??policy?.max), window=Number(policy?.ventana_seg??policy?.windowSeconds);
  const otherUserMaxMs=Number(policy?.otro_usuario_max_ms??policy?.otherUserMaxMs);
  return op?.responses?.['429'] && Number.isSafeInteger(max) && max>0 && Number.isSafeInteger(window) && window>0
    ? {max,window,otherUserMaxMs:Number.isFinite(otherUserMaxMs)&&otherUserMaxMs>0?otherUserMaxMs:null} : null;
}
export function snapshotSql(sensor){
  if(!Number.isSafeInteger(sensor)||sensor<=0)throw Error('Sensor inválido');
  return `SELECT count(*) AS n, md5(coalesce(string_agg(id_telemetria::text || ':' || timestamp_captura::text || ':' || valor_crudo::text, ',' ORDER BY id_telemetria),'')) AS huella FROM modulo3.telemetrias WHERE id_sensor=${sensor}`;
}
function local(){
  const v=parseEnv(fs.readFileSync(ENV_PATH,'utf8'));
  const router=fs.readFileSync(path.join(ROOT,'src/telemetry/infrastructure/routers/monitoreo_router.py'),'utf8');
  const checks=[
    ['casos exactos',CASOS.join()==='TC-M03-251,TC-M03-252,TC-M03-253,TC-M03-265'],
    ['QA desautorizado',v.QA_AUTORIZADO==='NO'],
    ['contrato de filtros obligatorios',router.includes('EXPORTAR_SIN_FILTROS')&&router.includes('tiene_filtro_adicional')],
    ['250 lecturas distintas',new Set(plan250({device:1,sensor:2,serial:'QA',at:'2026-10-17T00:00:00Z'}).map(x=>x.timestamp_captura)).size===250],
    ['20 solicitudes son referencia, no umbral',ratePlan().length===20],
    ['sin RESULTADOS',!fs.existsSync(path.join(DIR,'RESULTADOS'))],
    ['sin secretos literales',secretsFree(fs.readFileSync(fileURLToPath(import.meta.url),'utf8'),[v.QA_SANDBOX_SECRET,v.QA_COMMON_PASSWORD,v.QA_PROD_PASSWORD])],
  ];
  checks.forEach(([n,ok])=>console.log(`${ok?'OK':'FALLO'} ${n}`));
  console.log(`G125 ${checks.filter(x=>x[1]).length}/${checks.length}`);
  return checks.every(x=>x[1])?0:1;
}
async function execute(a){
  const x=await context(125,CASOS,DIR,a);
  if(x.blocked){console.error(`EJECUCIÓN NO AUTORIZADA: ${x.blocked.join(', ')}`);return 2;}
  const {c,req,sql,open,actors,prepareSensor,download,close}=x;
  try{
    await open();
    const auth=await actors();
    const date=new Date().toISOString().slice(0,10);
    // TC-252 no depende del motor M08 ni de un fixture de volumen.
    const bad=await download(query('/iot/monitoreo/historial/exportar',{formato:'EXCEL',fecha_inicio:date,fecha_fin:date}),auth.prod,1_000_000);
    let body=null;try{body=JSON.parse(bad.bytes.toString('utf8')||'null');}catch{}
    c.ev.asserts.push({caso:CASOS[1],nombre:'[TC-M03-252][ASSERT] HTTP 400 sin filtros adicionales',ok:bad.status===400,observado:true});
    c.ev.asserts.push({caso:CASOS[1],nombre:'[TC-M03-252][ASSERT] código EXPORTAR_SIN_FILTROS',ok:codeOf(body)==='EXPORTAR_SIN_FILTROS',observado:true});
    c.ev.asserts.push({caso:CASOS[1],nombre:'[TC-M03-252][ASSERT] no se entrega archivo',ok:!bad.headers['content-disposition']&&!bad.bytes.subarray(0,2).equals(Buffer.from('PK'))&&!bad.bytes.subarray(0,5).equals(Buffer.from('%PDF-')),observado:true});
    const sensor=await prepareSensor(auth);
    const records=plan250({device:sensor.device,sensor:sensor.sensor,serial:sensor.serial,at:new Date(Date.now()-7_200_000).toISOString()});
    const ing=await req('POST','/iot/telemetria/batch',{body:{registros:records}});
    if([401,403,404,422].includes(ing.status))throw Error(`PRE: batch oficial no disponible HTTP ${ing.status}`);
    c.ev.pre.push({caso:CASOS[0],nombre:'250 lecturas QA preparadas por API oficial',ok:ing.status===200&&ing.data?.aceptados===250&&ing.data?.rechazados===0});
    if(!c.ev.pre.at(-1).ok)throw Error('PRE: no se prepararon 250 lecturas exactas');
    const prepared=await sql(snapshotSql(sensor.sensor));
    c.ev.pre.push({caso:CASOS[0],nombre:'250 lecturas del RUN persistidas y consultables',ok:prepared.status===200&&Number(prepared.data?.data?.[0]?.n)===250});
    if(!c.ev.pre.at(-1).ok)throw Error('PRE: serie del RUN no verificable');
    const filters={fecha_inicio:date,fecha_fin:date,sensor_id:sensor.sensor};
    const page=await req('GET',query('/iot/monitoreo/historial',{...filters,pagina:2,por_pagina:100}),{token:auth.prod});
    if(page.status!==200)throw Error(`PRE: segunda página no consultable HTTP ${page.status}`);
    c.ev.asserts.push({caso:CASOS[0],nombre:'[TC-M03-251][ASSERT] segunda página de 100 sobre conjunto filtrado de 250',ok:page2Valid(page.data),observado:true});
    const exp=await download(query('/iot/monitoreo/historial/exportar',{formato:'EXCEL',...filters}),auth.prod,30_000_000);
    if(exp.status===503&&exp.bytes.toString('utf8').includes('M08_NO_DISPONIBLE')){
      c.ev.pre.push({caso:CASOS[0],nombre:'motor M08 disponible',ok:false});
      c.ev.dependencias.push('TC-M03-251: M08_NO_DISPONIBLE; la página 2 de 100 y el conjunto de 250 sí quedaron preparados.');
    }else if(exp.status!==200){c.ev.asserts.push({caso:CASOS[0],nombre:'[TC-M03-251][ASSERT] archivo exportado disponible',ok:false,observado:true,detalle:`HTTP ${exp.status}`});}
    else{
      fs.writeFileSync(path.join(c.out,'export_TC-M03-251.xlsx'),exp.bytes);
      let sheets;try{sheets=xlsxSheets(exp.bytes);}catch(e){c.ev.asserts.push({caso:CASOS[0],nombre:'[TC-M03-251][ASSERT] archivo XLSX válido',ok:false,observado:true,detalle:e.message});}
      if(sheets){
        const raw=sheets[0], count=dataRows(raw);
        c.ev.info.push({caso:CASOS[0],nombre:'filas hoja de datos',total:count});
        c.ev.asserts.push({caso:CASOS[0],nombre:'[TC-M03-251][ASSERT] 250 registros exportados, no 100 de la página',ok:count===250,observado:true});
        const meta=(metadataText(raw)||'').toLowerCase();
        c.ev.asserts.push({caso:CASOS[0],nombre:'[TC-M03-251][ASSERT] filtros y periodo en metadatos',ok:meta.includes('filtros')&&meta.includes('sensor')&&meta.includes(String(sensor.sensor))&&meta.includes(date),observado:true});
      }
    }
    const openapi=await req('GET','/openapi.json');
    const paths=openapi.status===200?openapi.data?.paths:{};
    const hook=faultHook(paths);
    const runFault=async()=>{
    const historyBefore=await sql(snapshotSql(sensor.sensor));
    const before=historyBefore.status===200?historyBefore.data?.data?.[0]:null;
    if(!hook||!a.efectos.includes('fallo-exportador')||!Number.isSafeInteger(Number(before?.n))||Number(before.n)<250){
      c.ev.pre.push({caso:CASOS[2],nombre:'hook de fallo M08 aislado y snapshot histórico verificable',ok:false});
      c.ev.dependencias.push('TC-M03-253: falta hook oficial de fallo/timeout dentro del sandbox, aceptación expresa fallo-exportador o snapshot verificable.');
    }else{
      const enabled=await req('POST',hook);
      if(enabled.status<200||enabled.status>=300)c.ev.pre.push({caso:CASOS[2],nombre:'hook de fallo M08 activado dentro del RUN',ok:false});
      else{
        const failure=await download(query('/iot/monitoreo/historial/exportar',{formato:'EXCEL',...filters}),auth.prod,1_000_000);
        const afterRes=await sql(snapshotSql(sensor.sensor)),after=afterRes.status===200?afterRes.data?.data?.[0]:null;
        const unchanged=Number(after?.n)===Number(before.n)&&after?.huella===before.huella;
        const noFile=!failure.headers['content-disposition']&&!/application\/pdf|spreadsheet|octet-stream/i.test(failure.headers['content-type']||'')
          &&!failure.bytes.subarray(0,2).equals(Buffer.from('PK'))&&!failure.bytes.subarray(0,5).equals(Buffer.from('%PDF-'));
        let errorBody;try{errorBody=JSON.parse(failure.bytes.toString('utf8'));}catch{}
        const informed=!!(errorBody?.message||errorBody?.detail||errorBody?.error);
        c.ev.asserts.push({caso:CASOS[2],nombre:'[TC-M03-253][ASSERT] fallo informado sin archivo parcial exitoso',ok:failureControlled({status:failure.status,bytes:noFile?Buffer.alloc(0):failure.bytes,visible:!noFile,unchanged:true,informed}),observado:true});
        c.ev.asserts.push({caso:CASOS[2],nombre:'[TC-M03-253][ASSERT] lecturas históricas intactas',ok:unchanged,observado:true});
      }
    }
    };
    // El ejemplo de 20/min no define el umbral. Solo una política oficial habilita la carga.
    const op=paths?.['/iot/monitoreo/historial/exportar']?.get, policy=ratePolicy(op);
    const volumeAuth=a.efectos.includes('volumen-exportacion');
    const loadReady=!!policy&&policy.max<30&&policy.window<=120&&volumeAuth&&exp.status===200;
    try{
    if(!loadReady){
      c.ev.pre.push({caso:CASOS[3],nombre:'política oficial acotable a 30 solicitudes/120 s, M08 y autorización específica',ok:loadReady});
      c.ev.dependencias.push('TC-M03-265: faltan política oficial acotable, M08 y/o autorización específica volumen-exportacion; 20/min es solo referencia.');
    }else{
      let prepared=250;
      while(prepared<5000){
        const n=Math.min(500,5000-prepared);
        const extra=Array.from({length:n},(_,i)=>({...records[0],timestamp_captura:new Date(Date.parse(records[0].timestamp_captura)+(prepared+i)*1000).toISOString()}));
        const batch=await req('POST','/iot/telemetria/batch',{body:{registros:extra}});
        if(batch.status!==200||batch.data?.aceptados!==n||batch.data?.rechazados!==0)throw Error('PRE: volumen QA de rate limiting incompleto');
        prepared+=n;
        if((await sql(snapshotSql(sensor.sensor))).status!==200)throw Error('PRE: vigencia del sandbox no confirmada durante carga');
      }
      const full=await req('GET',query('/iot/monitoreo/historial',{...filters,pagina:1,por_pagina:1}),{token:auth.prod});
      if(full.status!==200||full.data?.total!==5000)throw Error('PRE: conjunto de 5000 lecturas no verificable');
      const planned=Math.max(20,policy.max+1),windowMs=policy.window*1000;
      const start=Date.now(),responses=[],otherDuring=[];
      const otherBeforeStart=Date.now(),otherBefore=await req('GET','/usuarios/me',{token:auth.setup});
      const otherBeforeMs=Date.now()-otherBeforeStart;
      if(otherBefore.status!==200)throw Error('PRE: segundo usuario QA no observable antes de la carga');
      for(const offset of ratePlan(planned,windowMs)){
        const wait=start+offset-Date.now();if(wait>0)await new Promise(resolve=>setTimeout(resolve,wait));
        if(Date.now()-start>windowMs+30000)throw Error('PRE: ventana de carga controlada superada');
        const result=await download(query('/iot/monitoreo/historial/exportar',{formato:'PDF',...filters}),auth.prod,30_000_000);
        responses.push({status:result.status,queued:result.status===202,limited:result.status===429});
        if((await sql(snapshotSql(sensor.sensor))).status!==200)throw Error('PRE: sandbox perdió vigencia durante rate limiting');
        if(responses.length%5===0){
          const probe=await req('GET','/usuarios/me',{token:auth.setup});
          otherDuring.push(probe.status);
          if(probe.status!==200)break;
        }
      }
      c.ev.info.push({caso:CASOS[3],nombre:'solicitudes acotadas por la política oficial; 20/min como referencia',planned,windowMs,responses,otherDuring});
      c.ev.asserts.push({caso:CASOS[3],nombre:'[TC-M03-265][ASSERT] todas las solicitudes sobre el límite oficial rechazadas o encoladas',ok:responses.length===planned&&responses.slice(policy.max).every(r=>r.limited||r.queued),observado:true});
      const otherAfterStart=Date.now(),otherAfter=await req('GET','/usuarios/me',{token:auth.setup});
      const otherAfterMs=Date.now()-otherAfterStart;
      c.ev.info.push({caso:CASOS[3],nombre:'segundo usuario QA',antes_ms:otherBeforeMs,despues_ms:otherAfterMs,status:otherAfter.status});
      c.ev.asserts.push({caso:CASOS[3],nombre:'[TC-M03-265][ASSERT] segundo usuario conserva disponibilidad',ok:otherAfter.status===200&&otherDuring.every(s=>s===200),observado:true});
      c.ev.pre.push({caso:CASOS[3],nombre:'límite oficial de latencia de otros usuarios documentado',ok:policy.otherUserMaxMs!==null});
      if(policy.otherUserMaxMs!==null)c.ev.asserts.push({caso:CASOS[3],nombre:'[TC-M03-265][ASSERT] segundo usuario dentro de latencia oficial',ok:otherAfterMs<=policy.otherUserMaxMs,observado:true});
      else c.ev.dependencias.push('TC-M03-265: falta límite oficial para evaluar degradación de latencia de otros usuarios; las respuestas y tiempos observados quedan como INFO.');
    }
    }catch(e){c.ev.pre.push({caso:CASOS[3],nombre:'escenario de frecuencia ejecutable y sandbox vigente',ok:false,detalle:String(e.message)});c.ev.dependencias.push(`TC-M03-265: ${e.message}`);}
    await runFault();
    c.ev.estado='CONCLUIDA';
  }catch(e){c.ev.estado='INTERRUMPIDA';c.ev.dependencias.push(String(e.message));}
  finally{await close();c.finish();}
  return c.ev.veredicto==='APROBADO'?0:4;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const a=args(process.argv.slice(2));process.exitCode=a.modo==='local'?local():await execute(a);}
  catch(e){console.error(e.message);process.exitCode=2;}
}
