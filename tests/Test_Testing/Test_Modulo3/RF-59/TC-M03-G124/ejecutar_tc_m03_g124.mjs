#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { args, context, ENV_PATH, parseEnv, query, secretsFree, count, witness, ROOT } from '../TC-M03-G120/rf59_base.mjs';
import { validarPdf, validarExcel, volumen, zipEntries, dataRows, xlsxSheets, pdfText } from './validadores.mjs';

export const CASOS = ['TC-M03-249','TC-M03-250','TC-M03-254'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
export function exportPath(format, filters) {
  if (!['PDF','EXCEL'].includes(format)) throw Error('Formato inválido');
  return query('/iot/monitoreo/historial/exportar',{ formato:format,...filters });
}
export function classifyExport(response, format) {
  if (response.status === 503 && response.bytes.toString('utf8').includes('M08_NO_DISPONIBLE')) return { kind:'DEPENDENCIA_M08' };
  if (response.status !== 200) return { kind:'HTTP', status:response.status };
  const signature=format==='PDF'?response.bytes.subarray(0,5).toString()==='%PDF-':response.bytes.subarray(0,2).toString()==='PK';
  return { kind:'ARCHIVO', signature };
}
export function volumePlan(today=Date.now()) {
  const day=86_400_000, midnight=Date.UTC(new Date(today).getUTCFullYear(),new Date(today).getUTCMonth(),new Date(today).getUTCDate());
  const counts=[5000,1,4999,...Array(8).fill(5000),1];
  const dates=counts.map((_,i)=>new Date(midnight-(12-i)*day).toISOString().slice(0,10));
  return { counts, dates, targets:[{format:'PDF',n:5000,end:0},{format:'PDF',n:5001,end:1},{format:'EXCEL',n:50000,end:10},{format:'EXCEL',n:50001,end:11}] };
}
export function fragmentInfo(r) {
  const mime=r.headers?.['content-type']||'';
  if(/application\/json/i.test(mime)){
    let body;try{body=JSON.parse(r.bytes.toString('utf8'));}catch{return null;}
    const chunks=body?.fragmentos??body?.archivos;
    const sizes=Array.isArray(chunks)?chunks.map(x=>Number(x.registros??x.cantidad_registros)):null;
    return sizes?.every(Number.isSafeInteger)?{sizes,files:chunks,aviso:!!(body.aviso??body.mensaje)}:null;
  }
  if(r.bytes.subarray(0,2).toString()==='PK'){
    try{return {files:[...zipEntries(r.bytes).keys()].filter(x=>/\.pdf$|\.xlsx$/i.test(x))};}catch{return null;}
  }
  return null;
}
export function volumeCountSql(sensor,start,end){
  if(!Number.isSafeInteger(sensor)||sensor<=0||![start,end].every(d=>/^\d{4}-\d{2}-\d{2}$/.test(d)))throw Error('Parámetros de volumen inválidos');
  return `SELECT count(*) AS n FROM modulo3.telemetrias WHERE id_sensor=${sensor} AND timestamp_captura >= '${start}'::date AND timestamp_captura < ('${end}'::date + interval '1 day')`;
}
export function safeFragmentPath(value,api){
  try{
    if(typeof value!=='string'||value.startsWith('//'))return null;
    const base=new URL(api),prefix=base.pathname.replace(/\/+$/,'');
    const u=new URL(value,`${base.href.replace(/\/+$/,'')}/`);
    if(u.origin!==base.origin||u.username||u.password||!(u.protocol==='https:'||base.hostname==='127.0.0.1'))return null;
    return u.pathname.startsWith(`${prefix}/`)?u.pathname.slice(prefix.length)+u.search:null;
  }catch{return null;}
}
function local() {
  const v=parseEnv(fs.readFileSync(ENV_PATH,'utf8'));
  const router=fs.readFileSync(path.join(ROOT,'src/telemetry/infrastructure/routers/monitoreo_router.py'),'utf8');
  const ck=[
    ['casos exactos',CASOS.join()==='TC-M03-249,TC-M03-250,TC-M03-254'],
    ['QA desautorizado',v.QA_AUTORIZADO==='NO'],
    ['contrato exportación',exportPath('PDF',{fecha_inicio:'2026-10-01',fecha_fin:'2026-10-02',sensor_id:7}).includes('/iot/monitoreo/historial/exportar?')],
    ['ruta oficial PDF/Excel',router.includes('"/historial/exportar"')&&router.includes('formato: str')],
    ['límite PDF y Excel',volumen('PDF',5001,[5000,1],true).fragmentado && volumen('EXCEL',50001,[50000,1],true).fragmentado],
    ['sin RESULTADOS',!fs.existsSync(path.join(DIR,'RESULTADOS'))],
    ['sin secretos literales',[fileURLToPath(import.meta.url),path.join(DIR,'validadores.mjs')].every(p=>secretsFree(fs.readFileSync(p,'utf8'),[v.QA_SANDBOX_SECRET,v.QA_COMMON_PASSWORD,v.QA_PROD_PASSWORD]))],
  ];
  ck.forEach(([n,ok])=>console.log(`${ok?'OK':'FALLO'} ${n}`));
  console.log(`G124 ${ck.filter(x=>x[1]).length}/${ck.length}`);
  return ck.every(x=>x[1])?0:1;
}
async function execute(a) {
  const x=await context(124,CASOS,DIR,a);
  if(x.blocked){console.error(`EJECUCIÓN NO AUTORIZADA: ${x.blocked.join(', ')}`);return 2;}
  const {c,req,sql,open,actors,prepareSensor,download,close}=x;
  try{
    await open();
    const auth=await actors(), sensor=await prepareSensor(auth);
    const stamp=new Date().toISOString(), d=stamp.slice(0,10);
    const lectura={device_id:sensor.device,sensor_id:sensor.sensor,tipo_variable:'TEMPERATURA_AMBIENTAL',valor:25,unidad:'°C',timestamp_captura:stamp,access_key:sensor.serial,origen:'TIEMPO_REAL',estado_conectividad:true};
    const ing=await req('POST','/iot/telemetria',{body:lectura});
    if([401,403,404,422].includes(ing.status))throw Error(`PRE: preparación de lectura no disponible HTTP ${ing.status}`);
    c.ev.pre.push({caso:CASOS[0],nombre:'lectura QA aislada creada por contrato oficial',ok:ing.status===201});
    if(ing.status!==201)throw Error('PRE: no se pudo preparar la lectura de exportación');
    const farms=await req('GET','/configuracion/fincas',{token:auth.prod});
    const farm=farms.data?.items?.find(f=>Number(f.id_finca)===sensor.finca);
    if(farms.status!==200||!farm?.nombre)throw Error('PRE: metadatos de granja no consultables');
    const meta={granja:farm.nombre,inicio:d,fin:d,filtros:['sensor',String(sensor.sensor)],usuario:auth.usuario.nombre||auth.usuario.correo_electronico||''};
    if(!meta.usuario)throw Error('PRE: identidad del usuario exportador no consultable');
    const filters={fecha_inicio:d,fecha_fin:d,sensor_id:sensor.sensor};
    const requests=[['PDF',CASOS[0],validarPdf],['EXCEL',CASOS[1],validarExcel]];
    let m08Ready=true;
    for(const [format,caso,validator] of requests){
      const route=exportPath(format,format==='EXCEL'?{...filters,incluir_alertas:true}:filters);
      const r=await download(route,auth.prod,30_000_000), kind=classifyExport(r,format);
      c.ev.info.push({caso,nombre:'respuesta exportación',status:r.status,bytes:r.bytes.length,content_type:r.headers['content-type']});
      if(kind.kind==='DEPENDENCIA_M08'){m08Ready=false;c.ev.pre.push({caso,nombre:'motor M08 disponible',ok:false});c.ev.dependencias.push(`${caso}: M08_NO_DISPONIBLE`);continue;}
      if(kind.kind==='HTTP'){m08Ready=false;c.ev.asserts.push({caso,nombre:`[${caso}][ASSERT] exportación ${format} completada`,ok:false,observado:true,detalle:`HTTP ${r.status}`});continue;}
      c.ev.asserts.push({caso,nombre:`[${caso}][ASSERT] archivo ${format} válido`,ok:kind.signature,observado:true});
      if(!kind.signature){m08Ready=false;continue;}
      fs.writeFileSync(path.join(c.out,`export_${caso}.${format==='PDF'?'pdf':'xlsx'}`),r.bytes);
      const result=validator(r.bytes,meta);
      if(!result.verificable){
        if(format==='PDF'&&/texto PDF no extraíble/.test(result.motivo||''))c.ev.pre.push({caso,nombre:'texto PDF inspeccionable',ok:false,detalle:result.motivo});
        else c.ev.asserts.push({caso,nombre:`[${caso}][ASSERT] estructura ${format} íntegra`,ok:false,observado:true,detalle:result.motivo});
        m08Ready=false;continue;
      }
      for(const [name,ok] of Object.entries(result.checks)){
        if(ok===null)c.ev.pre.push({caso,nombre:`${name} inspeccionable con evidencia gráfica`,ok:false,detalle:'gráfica no distinguible de trazos genéricos del PDF'});
        else c.ev.asserts.push({caso,nombre:`[${caso}][ASSERT] ${name}`,ok,observado:true});
      }
      c.ev.info.push({caso,nombre:'estructura inspeccionada',paginas:result.paginas,hojas:result.hojas,filas_datos:result.filas_datos});
    }
    const volumeAuth=a.efectos.includes('volumen-exportacion');
    if(!m08Ready||!volumeAuth){
      c.ev.pre.push({caso:CASOS[2],nombre:'M08 disponible y autorización específica para 50.001 lecturas QA aisladas',ok:m08Ready&&volumeAuth});
      c.ev.dependencias.push('TC-M03-254: requiere M08 y aceptación expresa volumen-exportacion; no se genera carga masiva sin ambas condiciones.');
    }else{
      const plan=volumePlan(), begin=Date.now();
      for(let dayIndex=0;dayIndex<plan.counts.length;dayIndex++){
        for(let offset=0;offset<plan.counts[dayIndex];offset+=500){
          if(Date.now()-begin>600_000)throw Error('PRE: presupuesto temporal de preparación de volumen agotado');
          const n=Math.min(500,plan.counts[dayIndex]-offset);
          const records=Array.from({length:n},(_,i)=>({device_id:sensor.device,sensor_id:sensor.sensor,tipo_variable:'TEMPERATURA_AMBIENTAL',valor:25,unidad:'°C',timestamp_captura:`${plan.dates[dayIndex]}T${new Date((offset+i)*1000).toISOString().slice(11,19)}Z`,access_key:sensor.serial,origen:'TIEMPO_REAL',estado_conectividad:true}));
          const batch=await req('POST','/iot/telemetria/batch',{body:{registros:records}});
          if(batch.status!==200||batch.data?.aceptados!==n||batch.data?.rechazados!==0||batch.data?.duplicados!==0)throw Error(`PRE: lote de volumen incompleto HTTP ${batch.status}`);
          if(count(await sql(witness(sensor.serial)))!==1)throw Error('PRE: vigencia/aislamiento del RUN no verificable durante preparación masiva');
        }
      }
      for(const target of plan.targets){
        const filter={fecha_inicio:plan.dates[0],fecha_fin:plan.dates[target.end],sensor_id:sensor.sensor};
        const exact=count(await sql(volumeCountSql(sensor.sensor,filter.fecha_inicio,filter.fecha_fin)))===target.n;
        c.ev.pre.push({caso:CASOS[2],nombre:`conjunto QA exacto ${target.format} ${target.n}`,ok:exact});
        if(!exact)continue;
        const r=await download(exportPath(target.format,filter),auth.prod,100_000_000);
        const kind=classifyExport(r,target.format),fragment=fragmentInfo(r);
        if(kind.kind==='DEPENDENCIA_M08'){c.ev.pre.push({caso:CASOS[2],nombre:'M08 continuó disponible durante volumen',ok:false});continue;}
        if(r.status===202){c.ev.pre.push({caso:CASOS[2],nombre:`trabajo asíncrono ${target.format} ${target.n} consultable por contrato`,ok:false,detalle:'HTTP 202 sin contrato de seguimiento'});continue;}
        if(r.status!==200){c.ev.asserts.push({caso:CASOS[2],nombre:`[TC-M03-254][ASSERT] ${target.format} ${target.n} procesado`,ok:false,observado:true,detalle:`HTTP ${r.status}`});continue;}
        if(target.n===5000||target.n===50000){
          c.ev.asserts.push({caso:CASOS[2],nombre:`[TC-M03-254][ASSERT] ${target.format} ${target.n} procesado dentro del límite`,ok:r.status===200&&kind.signature,observado:true});
        }else if(fragment?.sizes){
          const files=fragment.files;
          const paths=files.map(f=>safeFragmentPath(f.url??f.ruta_descarga,x.g.api));
          const fetchable=paths.every(Boolean);
          c.ev.pre.push({caso:CASOS[2],nombre:`fragmentos ${target.format} ${target.n} descargables por ruta oficial del mismo API`,ok:fetchable});
          if(!fetchable)continue;
          const checked=[];
          for(let i=0;i<paths.length;i++){
            const part=await download(paths[i],auth.prod,100_000_000);
            const valid=part.status===200&&classifyExport(part,target.format).signature;
            let actual=null, structure=false;
            if(valid)try{
              if(target.format==='EXCEL'){actual=dataRows(xlsxSheets(part.bytes)[0]);structure=actual===fragment.sizes[i];}
              else structure=pdfText(part.bytes).verificable;
            }catch{}
            checked.push(valid&&structure);
          }
          const result=volumen(target.format,target.n,fragment.sizes,fragment.aviso);
          for(const [name,ok] of Object.entries(result))if(name!=='dentro')c.ev.asserts.push({caso:CASOS[2],nombre:`[TC-M03-254][ASSERT] ${target.format} ${target.n} ${name}`,ok,observado:true});
          c.ev.asserts.push({caso:CASOS[2],nombre:`[TC-M03-254][ASSERT] fragmentos ${target.format} íntegros y disponibles`,ok:checked.every(Boolean),observado:true});
        }else{
          c.ev.pre.push({caso:CASOS[2],nombre:`fragmentos y aviso ${target.format} ${target.n} inspeccionables`,ok:false,detalle:fragment?.files?.length?`${fragment.files.length} archivos sin conteos oficiales`:'respuesta sin manifiesto de fragmentos'});
          c.ev.dependencias.push('TC-M03-254: M08 debe exponer conteos por fragmento y aviso verificable para evaluar la fragmentación sin inferir registros de un ZIP.');
        }
      }
    }
    c.ev.estado='CONCLUIDA';
  }catch(e){c.ev.estado='INTERRUMPIDA';c.ev.dependencias.push(String(e.message));}
  finally{await close();c.finish();}
  return c.ev.veredicto==='APROBADO'?0:4;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const a=args(process.argv.slice(2));process.exitCode=a.modo==='local'?local():await execute(a);}
  catch(e){console.error(e.message);process.exitCode=2;}
}
