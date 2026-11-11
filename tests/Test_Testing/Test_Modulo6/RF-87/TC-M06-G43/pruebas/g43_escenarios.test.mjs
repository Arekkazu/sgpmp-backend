import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {ejecutar,CAPACIDADES} from '../g43.mjs';
import {CASOS,hoyBogota} from '../lib/g43_core.mjs';
import {validarError} from '../lib/contrato.mjs';
import {clasificarRegistro} from '../lib/infra.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';

const DIR=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const RUN='RUN-G43-V1-20261110-000000',fecha=hoyBogota();
const ant=n=>{const d=new Date(fecha+'T12:00:00Z');d.setUTCDate(d.getUTCDate()-n);return d.toISOString().slice(0,10);};
const clone=structuredClone;
const error=(error_code,message)=>({error_code,message,fields:[],timestamp:new Date().toISOString()});
const precio=(id,esp,vig)=>({id_precio_mercado:id,id_especie:esp,categoria:'POR_CABEZA',id_metrica_produccion:null,es_aplicado:false,precio_unitario:'10000',fuente:'MERCADO_ACTIVO',fecha_vigencia:vig,fecha_vencimiento:null,unidad_medida:'UNIDAD',evidencia:'LOCAL',estado:'VIGENTE'});
const periodo=(id,nit)=>({id_periodo_contable:id,numero_id_tributaria:nit,fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30',fecha_cierre:null,estado:'ABIERTO',ultimo_cierre:null});
const linea=(id,p)=>({id_linea_asiento_nic41:id,id_activo_biologico:945,estado:'REGISTRADA',tipo_hecho:'VARIACION_VR_TB',sentido:'GANANCIA',id_especie:39,subtipo_costo:null,valor:'10',tipo_evidencia:null,cuenta_debito:'1105',cuenta_credito:'4105',numero_id_tributaria:'N8',id_periodo_contable:p,estado_trazabilidad:'VERIFICACION_PENDIENTE'});
const calculo=(id,aid,valor,estimado=false)=>({id_calculo_valor_razonable:id,id_activo_biologico:aid,tiene_valor_estimado:estimado,fecha_calculo:fecha+'T12:00:00Z',precio_unitario:String(valor),magnitud:'1',valor_razonable_bruto:String(valor),valor_neto:String(valor)});
function cypress(nombre){return async(script,input)=>{if(script==='newman_hijo.mjs'){const data=await ejecutarNewman(input);return {code:data.codigo,data,error:''};}assert.equal(script,'cypress_hijo.mjs');const {dir,panel}=input,totalTests=nombre==='cypress_cero'?0:1;fs.mkdirSync(path.join(dir,'screenshots'),{recursive:true});fs.writeFileSync(path.join(dir,'screenshots','local.png'),Buffer.from('89504e470d0a1a0a','hex'));const acta={estado:'APROBADO',lista_completa:!(nombre==='codigo_actual'&&panel==='027'),confirmacion_individual:!(nombre==='codigo_actual'&&panel==='026'),controles:[{tipo:'boton',nombre:'Sí'},{tipo:'boton',nombre:'No'}],peticiones:[]};fs.writeFileSync(path.join(dir,`G43-UI-${panel}.json`),JSON.stringify(acta));return{code:0,data:{acta,totalTests},error:''};};}
function fixture(nombre,extra){
 const periodos=[periodo(8,'N8'),periodo(219,'N219'),periodo(220,'N220'),{...periodo(99999,null),estado:null,fecha_inicio:null,fecha_fin:null}];
 const precios=[precio(17,39,ant(3)),precio(18,422,ant(3)),precio(19,423,ant(3))];
 const matriz=['UNICO','GANANCIA','PERDIDA'].map((sentido,i)=>({id_asignacion_cuenta_contable:i+1,tipo_hecho:'ORIGEN',sentido,id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'}));
 if(nombre!=='matriz_depreciacion_creada')matriz.push({...matriz[0],id_asignacion_cuenta_contable:4,tipo_hecho:'DEPRECIACION_ACTIVO_COSTO'});
 if(nombre==='matriz_sin_origen')matriz.splice(2,1);
 for(const [tipo,sentido,id] of [['VARIACION_VR_PM','GANANCIA',5],['VARIACION_VR_TB','GANANCIA',6],['VARIACION_VR_TB','PERDIDA',7]])if(!(nombre==='matriz_sin_origen'&&sentido==='PERDIDA'))matriz.push({...matriz[1],id_asignacion_cuenta_contable:id,tipo_hecho:tipo,sentido});
 const base={periodos:clone(periodos),precios:clone(precios),matriz:clone(matriz)},cerrados=new Set(),cal8=[],cal220=[],auditoria=[],lineas8=[linea(17,8)];
 const activos=[[945,463,39,false],[947,463,39,false],[1567,466,423,true],[1568,466,422,false],[1569,467,423,false],[1570,467,423,false],[1571,467,423,false],[1572,467,423,true],[1573,467,423,true]].map(([id_activo_biologico,id_finca,id_especie,valorado_por_costo])=>({id_activo_biologico,id_finca,id_especie,estado:'ACTIVO',valorado_por_costo,depreciacion_acumulada:null}));
 const noPrice=esp=>{const latest=precios.filter(x=>x.id_especie===esp&&x.fecha_vigencia<=fecha).sort((a,b)=>b.fecha_vigencia.localeCompare(a.fecha_vigencia)||b.id_precio_mercado-a.id_precio_mercado)[0];return !latest||!!latest.fecha_vencimiento&&latest.fecha_vencimiento<fecha;};
 const faltantes=id=>id===219&&noPrice(422)?[{id_activo_biologico:1568,identificador:'A-1568',especie:'Caprino'}]:id===220&&noPrice(423)?[1569,1570,1571].map(a=>({id_activo_biologico:a,identificador:'A-'+a,especie:'Caprino'})):[];
 const pre=id=>({bloqueos:nombre==='prevalidacion_distinta'&&id===8?[{codigo:'DIFERENTE',mensaje:'Local'}]:[],activos_sin_precio:faltantes(id),lineas_sin_trazabilidad:id===8?[{id_linea:17,tipo_hecho:'VARIACION_VR_TB',id_activo_biologico:945,faltantes:['lecturas_nic41'],nivel_fallo:'PENDIENTE'}]:[],puede_cerrar:true,requiere_autorizacion:id===8||faltantes(id).length>0});
 const stats={max:0,active:0,total:0,writes:[],intentos:new Map(),postHeaders:true,postReads:0},deleted={value:false};
 const server=http.createServer(async(req,res)=>{
  if(stats.active){res.writeHead(409,{'content-type':'application/json'});res.end(JSON.stringify(error('PETICION_CONCURRENTE','Servidor local ocupado')));return;}
  stats.active++;stats.max=Math.max(stats.max,stats.active);stats.total++;
  let status=200,data;try{
   const ruta=req.url.replace(/^\/api/,'');const u=new URL('http://local'+ruta),p=u.pathname,m=req.method,id=Number(p.split('/')[3]);let chunks=[];for await(const x of req)chunks.push(x);const body=chunks.length?JSON.parse(Buffer.concat(chunks).toString()):{};
   if(deleted.value&&m==='GET'){stats.postReads++;if(req.headers['x-test-run-id']||req.headers['x-sandbox-secret'])stats.postHeaders=false;}
   if(m==='POST'&&p!=='/sesiones/'||m==='DELETE')stats.writes.push({m,p,body});
   if(m==='POST'&&p==='/sesiones/')data={token:'LOCAL'};
   else if(m==='GET'&&p==='/sesiones/me/permisos')data={permisos:[['cierre_periodo',2],['cierre_periodo',5],['configuracion_contable',2],['configuracion_contable',1],['auditoria_financiera',2],['precios_mercado',2],['precios_mercado',1],['valoracion_activos',2],['revelaciones_nic41',2]].map(([nombre_recurso,id_accion])=>({nombre_recurso,id_accion}))};
   else if(m==='GET'&&p==='/finanzas/periodos'){data=clone(periodos);const pe=periodos.find(x=>x.id_periodo_contable===8);if(pe.estado==='EN_CIERRE')pe.estado='ABIERTO';}
   else if(m==='GET'&&p==='/finanzas/configuracion')data={general:{pct_umbral_desviacion_precio:'20'},especies:[39,422,423].map(id_especie=>({id_especie,categoria_precio:'POR_CABEZA',vida_util_meses:id_especie===423?120:null})),matriz};
   else if(m==='GET'&&p==='/finanzas/activos')data=activos;
   else if(m==='GET'&&/^\/finanzas\/activos\/\d+$/.test(p)){const aid=Number(p.split('/')[3]),a=activos.find(x=>x.id_activo_biologico===aid);data={activo:{id_activo_biologico:aid,id_especie:a.id_especie,id_finca:a.id_finca,numero_id_tributaria:a.id_finca===463?'N8':a.id_finca===466?'N219':'N220',estado:'ACTIVO',id_dispositivo_iot:null},valoracion_costo:a.valorado_por_costo?{es_activa:true,vida_util_meses:120,razon_sin_mercado:'Sin mercado'}:null};}
   else if(m==='GET'&&p==='/finanzas/precios')data=precios.filter(x=>x.id_especie===Number(u.searchParams.get('id_especie')));
   else if(m==='POST'&&p==='/finanzas/precios'){
    const anterior=precios.filter(x=>x.id_especie===body.id_especie&&x.fuente===body.fuente&&x.fecha_vigencia<=fecha).sort((a,b)=>b.fecha_vigencia.localeCompare(a.fecha_vigencia)||b.id_precio_mercado-a.id_precio_mercado)[0];
    const desvio=anterior?Math.abs(Number(body.precio_unitario)/Number(anterior.precio_unitario)-1)*100:0;
    if(body.fecha_vencimiento&&body.fecha_vencimiento<=body.fecha_vigencia){status=422;data=error('FECHA_VENCIMIENTO_INVALIDA','Vencimiento anterior a vigencia');}
    else if(desvio>20&&!body.confirmar_desviacion){status=409;data=error('DESVIACION_PRECIO_REQUIERE_CONFIRMACION','Confirmar desviación');}
    else{status=201;const pid=100+precios.length;precios.push({...precio(pid,body.id_especie,body.fecha_vigencia),...body,id_precio_mercado:pid,fecha_vencimiento:body.fecha_vencimiento??null});data={id_precio_mercado:pid};}
   }
   else if(m==='POST'&&p==='/finanzas/configuracion/matriz'){status=201;const mid=100+matriz.length;matriz.push({...body,id_asignacion_cuenta_contable:mid});data={id_asignacion_cuenta_contable:mid};}
   else if(m==='GET'&&/^\/finanzas\/periodos\/\d+\/prevalidacion$/.test(p))data=pre(id);
   else if(m==='GET'&&p==='/finanzas/lineas')data=Number(u.searchParams.get('id_periodo_contable'))===8?lineas8:Number(u.searchParams.get('id_periodo_contable'))===301&&cerrados.has(8)?[{...linea(17,301),estado_trazabilidad:'PENDIENTE_TRAZABILIDAD'}]:[];
   else if(m==='GET'&&/^\/finanzas\/periodos\/\d+\/(comprobantes|variaciones)$/.test(p))data=[];
   else if(m==='GET'&&/^\/finanzas\/periodos\/\d+\/calculos$/.test(p))data=id===8?cal8:cal220;
   else if(m==='GET'&&/^\/finanzas\/periodos\/\d+\/revelaciones$/.test(p))data=id===220&&cerrados.has(220)?[{id_informe:44,version_informe:1}]:[];
   else if(m==='GET'&&p==='/finanzas/revelaciones/44')data={id_informe:44,contenido:{parr_54_56_activos_al_costo:[1572,1573].map(id_activo_biologico=>({id_activo_biologico,vida_util_meses:120,razon:'Sin mercado'}))}};
   else if(m==='GET'&&p==='/finanzas/auditoria')data={eventos:auditoria,total_registros:auditoria.length};
   else if(m==='POST'&&/^\/finanzas\/periodos\/\d+\/cierre$/.test(p)){
    stats.intentos.set(id,(stats.intentos.get(id)??0)+1);
    if((id===8||id===219)&&!body.autorizar_exclusiones){status=409;if(id===8&&nombre!=='codigo_actual')periodos.find(x=>x.id_periodo_contable===8).estado='EN_CIERRE';data=error('EXCLUSION_REQUIERE_AUTORIZACION',id===219?'1 activo sin precio requiere autorización':'Exclusión requiere autorización');}
    else if(id===8&&['codigo_actual','cierre8_500_otro_paso'].includes(nombre)){status=500;data=error('ERROR_INTERNO','Error interno en cierre');auditoria.push({tipo_evento:'CIERRE_PERIODO_FALLIDO',id_referencia:8,id_usuario:1,timestamp_evento:new Date().toISOString(),payload_evento:{paso:nombre==='codigo_actual'?3:2,error:'Error interno'}});}
    else if(!matriz.some(x=>x.tipo_hecho==='DEPRECIACION_ACTIVO_COSTO')){status=422;data=error('CIERRE_BLOQUEADO','Falta cuenta de depreciación');}
    else {const next=id===8?301:id===219?302:303;cerrados.add(id);const pe=periodos.find(x=>x.id_periodo_contable===id);pe.estado='CERRADO';pe.fecha_cierre=new Date().toISOString();pe.ultimo_cierre={id_cierre:id*10,id_usuario_ejecutor:1,fecha_fin:pe.fecha_cierre,precios_congelados:id===8?[{id_especie:39,id_precio_mercado:nombre==='precio_nuevo'?103:17,precio_unitario:nombre==='precio_nuevo'?'10500':'10000',fuente:'MERCADO_ACTIVO',fecha_vigencia:nombre==='precio_nuevo'?fecha:ant(3)}]:[]};periodos.push(periodo(next,pe.numero_id_tributaria));if(id===8){const val=nombre==='precio_nuevo'?'10500':'10000';cal8.push(calculo(801,945,val),calculo(802,947,val));}if(id===220&&nombre==='codigo_actual')cal220.push(calculo(901,1569,10000,true));data={id_cierre:id*10,id_periodo_contable:id,periodo:'2026-11',estado:'CERRADO',activos_procesados:id===219?1:2,activos_excluidos:id===219?[{id_activo_biologico:1568,identificador:'A-1568',motivo:'PENDIENTE_PRECIO',detalle:null}]:id===220?(nombre==='codigo_actual'?[1570,1571]:[1569,1570,1571]).map(x=>({id_activo_biologico:x,identificador:'A-'+x,motivo:'PENDIENTE_PRECIO',detalle:null})):[],lineas_excluidas:id===8?[{id_linea:17,tipo_hecho:'VARIACION_VR_TB',id_activo_biologico:945,faltantes:['lecturas_nic41'],nivel_fallo:'PENDIENTE'}]:[],comprobantes:[],hash_cierre:'LOCAL',id_periodo_siguiente:next,reportes:{estado_resultados:{},informe_revelaciones:{id_informe:44}}};}
   }
   else if(m==='DELETE'&&/^\/test-control\/runs\//.test(p)){if(nombre==='rollback_fallido'){status=500;data=error('ERROR_INTERNO','DELETE local falló');}else{deleted.value=true;periodos.splice(0,periodos.length,...clone(base.periodos));precios.splice(0,precios.length,...clone(base.precios),...(nombre==='precio_persistente'?precios.filter(x=>x.id_precio_mercado===103):[]));matriz.splice(0,matriz.length,...clone(base.matriz));cerrados.clear();cal8.length=0;cal220.length=0;data={};}}
   else{status=404;data=error('NO_ENCONTRADO','Ruta no declarada');}
   if(status>=400)assert(validarError(data));if(extra&&status<400&&m==='GET'){const add=x=>Array.isArray(x)?x.map(add):x&&typeof x==='object'?{...x,campo_qa_desconocido:'ajeno'}:x;data=add(data);}
  }catch(e){status=500;data=error('ERROR_INTERNO',e.message);}res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(data));stats.active--;
 });return{server,stats};
}
const escenarios=[['conforme',['APROBADO','APROBADO','APROBADO','APROBADO'],true],['codigo_actual',['RECHAZADO','APROBADO','RECHAZADO','RECHAZADO'],true],['precio_nuevo',['RECHAZADO','APROBADO','APROBADO','APROBADO'],true],['prevalidacion_distinta',CASOS.map(()=>'NO_CONCLUYENTE'),false],['rollback_fallido',CASOS.map(()=>'APROBADO'),false],['precio_persistente',CASOS.map(()=>'APROBADO'),false],['cypress_cero',CASOS.map(()=>'NO_CONCLUYENTE'),false],['matriz_depreciacion_creada',CASOS.map(()=>'APROBADO'),true],['matriz_sin_origen',CASOS.map(()=>'NO_CONCLUYENTE'),false],['cierre8_500_otro_paso',['RECHAZADO','APROBADO','APROBADO','RECHAZADO'],true]];
for(const [nombre,esperados,oficial] of escenarios)for(const extra of [false,true]){
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g43-')),dir=path.join(tmp,RUN),f=fixture(nombre,extra);fs.mkdirSync(dir);
 try{await new Promise(ok=>f.server.listen(0,'127.0.0.1',ok));const api=`http://127.0.0.1:${f.server.address().port}/api`;const r=await ejecutar({dir,runId:RUN,version:1,ref:'AUT-LOCAL'},{QA_SANDBOX_SECRET:'LOCAL',QA_CONTADOR_EMAIL:'local@example.invalid',QA_CONTADOR_PASSWORD:'LOCAL'},{ensayo:true,api,hijo:cypress(nombre)});
 const estados=CASOS.map(c=>r.casos[c].estado);assert.deepEqual(estados,esperados,`${nombre}: ${JSON.stringify({problemas:r.problemas_tecnicos,casos:r.casos,solicitudes:r.solicitudes})}`);assert.equal(r.oficial,oficial,`${nombre}: ${JSON.stringify({problemas:r.problemas_tecnicos,casos:r.casos,solicitudes:r.solicitudes})}`);assert.equal(f.stats.max,1);assert.equal(f.stats.postHeaders,true);assert.equal(r.total_solicitudes_api,f.stats.total);assert(f.stats.total<=240);
 if(['prevalidacion_distinta','matriz_sin_origen'].includes(nombre))assert.equal(f.stats.writes.filter(x=>x.m!=='DELETE').length,0);
 if(nombre==='codigo_actual')assert(r.incidencias.some(x=>x.id==='INC-M06-G32-01'&&x.certeza.startsWith('PROBABLE')));
 if(nombre==='cierre8_500_otro_paso')assert(r.incidencias.some(x=>x.id==='INC-M06-G43-06'));
 if(nombre==='matriz_depreciacion_creada')assert(f.stats.writes.some(x=>x.p==='/finanzas/configuracion/matriz'&&x.body.tipo_hecho==='DEPRECIACION_ACTIVO_COSTO'));
 for(const [id,cantidad] of [[8,2],[219,2],[220,1]])assert.equal(f.stats.intentos.get(id)??0,['prevalidacion_distinta','matriz_sin_origen'].includes(nombre)?0:cantidad);
 const orden=f.stats.writes.filter(x=>x.m==='POST').map(x=>x.p==='/finanzas/configuracion/matriz'?'matriz':x.p==='/finanzas/precios'?'precio'+x.body.id_especie:x.p.includes('/8/cierre')?'cierre8':x.p.includes('/219/cierre')?'cierre219':x.p.includes('/220/cierre')?'cierre220':x.p);
 const primero=x=>orden.indexOf(x);
 if(!['prevalidacion_distinta','matriz_sin_origen'].includes(nombre)){
   assert(primero('cierre8')<primero('precio39')&&primero('precio39')<primero('precio422')&&primero('precio422')<primero('cierre219')&&primero('cierre219')<primero('precio423')&&primero('precio423')<primero('cierre220'));
   if(primero('matriz')>=0)assert(primero('matriz')<primero('cierre8'));
 }
 if(nombre!=='rollback_fallido')assert(f.stats.postReads>0);
 const saved=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json'))),md=fs.readFileSync(path.join(dir,'TC-M06-G43_resultado.md'),'utf8');assert.deepEqual(CASOS.map(c=>saved.casos[c].estado),estados);assert.equal(saved.oficial,r.oficial);for(const c of CASOS)assert(md.includes(c)&&md.includes(r.casos[c].estado));for(const x of r.incidencias)assert(md.includes(x.id));assert(md.includes(r.rollback.verificado?'Rollback verificado: si':'Rollback verificado: no'));assert(!/\u00C3|(?<=\p{L})\?(?=\p{L})/u.test(md));assert(!/local@example|Bearer LOCAL/i.test(md+JSON.stringify(saved)));
 const presentes=new Set(fs.readdirSync(dir,{recursive:true,withFileTypes:true}).filter(x=>x.isFile()).map(x=>path.relative(dir,path.join(x.parentPath,x.name)).replaceAll('\\','/')));assert.equal(clasificarRegistro(CAPACIDADES,r,presentes,{runId:RUN,version:1,referencia:'AUT-LOCAL'}),oficial);
 if(process.env.QA_VERIFICAR_SALIDAS){const destino=path.join(process.env.QA_VERIFICAR_SALIDAS,`${nombre}${extra?'_inyectado':''}`);fs.cpSync(dir,destino,{recursive:true});}
 for(const archivo of presentes)if(/\.(json|html|md)$/.test(archivo)){const contenido=fs.readFileSync(path.join(dir,archivo),'utf8');assert(!/local@example\.invalid|Bearer LOCAL|LOCAL_FAKE|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\./i.test(contenido),archivo);}
 console.log(`OK escenario_${nombre}${extra?'_inyectado':''}: 024=${estados[0]} 025=${estados[1]} 026=${estados[2]} 027=${estados[3]} oficial=${oficial} solicitudes=${f.stats.total}/240`);
 }finally{await new Promise(ok=>f.server.close(ok));fs.rmSync(tmp,{recursive:true,force:true});}
}
