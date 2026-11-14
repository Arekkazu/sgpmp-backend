import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {ejecutar,CAPACIDADES} from '../g44.mjs';
import {LIMITE} from '../lib/g44_core.mjs';
import {validarFormaResultado,clasificarRegistro} from '../lib/infra.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';

const raiz=process.env.QA_VERIFICAR_SALIDAS??fs.mkdtempSync(path.join(os.tmpdir(),'g44-v3-'));
fs.mkdirSync(raiz,{recursive:true});
const escenarios=['conforme','8_abierto','bloqueos_defecto','a_cierra','mensajes_distintos','mensaje_sin_rol','cerrado_sin_fecha','cerrado_fecha_bogota','hora_utc','hora_bogota','hora_ausente','segundo_cierre','220_cerrado_anterior','260_cerrado_anterior','preflight_invalido','sin_activo_467','restauracion_no_limpia','put_rechazado','presupuesto_rollback','delete_fallido','admin_permiso_5','vet_permiso_5','permisos_aborto','contrato_invalido'];
const error=(code,message)=>({error_code:code,message,fields:[],timestamp:'2026-11-13T08:00:00Z'});
const titular=id=>({id_finca:id,nombre:'Finca local',tipo_id_tributaria:'NIT',numero_id_tributaria:id===466?'NIT-B':'NIT-C',dv:'4',razon_social:'Titular local'});
function servidor(nombre,inyectados){
  const peticiones=[];let s;
  const reset=()=>{s={matriz34:true,matriz49:true,titulares:new Map([[466,titular(466)],[467,titular(467)]]),costo:false,estado8:nombre==='8_abierto'?'ABIERTO':'EN_CIERRE',cierre8:nombre==='8_abierto'?null:67,post8:0,cerrado220:false,cerrado260:false};};reset();
  const enviar=(res,code,data,eco)=>{const extra=x=>Array.isArray(x)?x.map(extra):x&&typeof x==='object'?{...x,campo_inyectado:'ignorar'}:x;res.writeHead(code,{'content-type':'application/json',...eco});res.end(JSON.stringify(inyectados?extra(data):data));};
  const server=http.createServer(async(req,res)=>{
    const chunks=[];for await(const ch of req)chunks.push(ch);const body=chunks.length?JSON.parse(Buffer.concat(chunks).toString()):{};
    const url=new URL(req.url,'http://127.0.0.1'),ruta=url.pathname.replace(/^\/api/,'');
    const rol=String(req.headers.authorization??'').replace('Bearer TOKEN_','').toLowerCase();
    const eco=req.headers['x-test-run-id']?{'x-test-run-id':req.headers['x-test-run-id']}:{ };
    peticiones.push({metodo:req.method,ruta,rol,run:Boolean(req.headers['x-test-run-id'])});
    if(ruta==='/sesiones/'&&req.method==='POST'){
      const rolLogin=String(body.correo_electronico??'').match(/^qa_(contador|admin|veterinario|prod)@/)?.[1];return enviar(res,200,{token:`TOKEN_${(rolLogin??'INVALIDO').toUpperCase()}`},eco);
    }
    if(ruta==='/sesiones/me/permisos'){
      const base=[['cierre_periodo',2]],porRol={contador:[...base,...(nombre==='permisos_aborto'?[]:[['cierre_periodo',5]]),['configuracion_contable',3],['costos_activos',1]],admin:[...base,['fincas',3],['cierre_periodo',5]],veterinario:nombre==='vet_permiso_5'?[['cierre_periodo',5]]:[],prod:[]};
      return enviar(res,200,{permisos:(porRol[rol]??[]).map(([nombre_recurso,id_accion])=>({nombre_recurso,id_accion}))},eco);
    }
    if(ruta==='/finanzas/activos')return enviar(res,200,[
      {id_activo_biologico:1567,id_finca:466,valorado_por_costo:true,vida_util_meses:120},
      {id_activo_biologico:1569,id_finca:467,valorado_por_costo:false,vida_util_meses:null},
      {id_activo_biologico:1572,id_finca:467,valorado_por_costo:false,vida_util_meses:null},
      ...(nombre==='sin_activo_467'?[]:[{id_activo_biologico:1573,id_finca:467,valorado_por_costo:true,vida_util_meses:120}])],eco);
    if(ruta==='/finanzas/periodos'&&req.method==='GET'){
      const ps=[7,8,219,220,260].map(id=>{
        const cerrado=[7,219].includes(id)||id===220&&(s.cerrado220||nombre==='220_cerrado_anterior')||id===260&&(s.cerrado260||nombre==='260_cerrado_anterior');
        const ultimo=id===7?{id_cierre:1,id_usuario_ejecutor:141,nombre_usuario_ejecutor:'Ejecutor local',estado:'COMPLETADO',paso_actual:9,fecha_inicio:'2026-11-07T12:00:00Z',fecha_fin:'2026-11-07T12:10:00Z'}:id===219?{id_cierre:43,id_usuario_ejecutor:141,nombre_usuario_ejecutor:'Ejecutor local',estado:'COMPLETADO',paso_actual:9,fecha_inicio:'2026-11-07T12:00:00Z',fecha_fin:'2026-11-07T12:10:00Z'}:id===8&&s.estado8==='EN_CIERRE'?{id_cierre:s.cierre8,id_usuario_ejecutor:141,nombre_usuario_ejecutor:'Ejecutor local',estado:'EN_PROCESO',paso_actual:3,fecha_inicio:s.cierre8===67?'2026-11-11T16:37:00Z':'2026-11-13T08:00:00Z',fecha_fin:null}:null;
        if(ultimo)ultimo.precios_congelados=nombre==='contrato_invalido'&&id===7?42:id===8?null:[{id_especie:[39,false],id_precio_mercado:81,precio_unitario:'120.00',fuente:'LOCAL',fecha_vigencia:'2026-11-07'}];
        return{id_periodo_contable:id,numero_id_tributaria:id===260?'NIT-B':id===220?'NIT-C':'NIT-A',fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30',fecha_cierre:cerrado?'2026-11-07T02:10:00Z':null,estado:id===8?s.estado8:cerrado?'CERRADO':'ABIERTO',ultimo_cierre:ultimo};
      });return enviar(res,200,ps,eco);
    }
    if(ruta==='/finanzas/configuracion')return enviar(res,200,{general:{pct_umbral_desviacion_precio:'10'},especies:[],matriz:[...(s.matriz34?[{id_asignacion_cuenta_contable:34,tipo_hecho:'MANO_OBRA_PROPIA',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'158405',cuenta_credito:'250505'}]:[]),...(s.matriz49?[{id_asignacion_cuenta_contable:49,tipo_hecho:'DEPRECIACION_ACTIVO_COSTO',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'}]:[])]},eco);
    if(ruta==='/finanzas/lineas'){
      const id=Number(url.searchParams.get('id_periodo_contable'));
      const lineas=id===8?[{id_linea_asiento_nic41:17,id_activo_biologico:945,id_finca:467,estado:'PENDIENTE_TRAZABILIDAD',tipo_hecho:'OTRO'}]:id===220?[...Array.from({length:7},(_,i)=>({id_linea_asiento_nic41:100+i,id_activo_biologico:1573,id_finca:467,estado:'REGISTRADA',tipo_hecho:'OTRO'})),...(s.costo?[{id_linea_asiento_nic41:151,id_activo_biologico:1569,id_finca:467,estado:s.matriz34?'CONTABILIZADA':'PENDIENTE_CUENTA',tipo_hecho:'MANO_OBRA_PROPIA'}]:[])]:[];
      return enviar(res,200,lineas,eco);
    }
    if(/^\/finanzas\/periodos\/\d+\/(comprobantes|variaciones)$/.test(ruta))return enviar(res,200,[],eco);
    if(/^\/finanzas\/periodos\/\d+\/prevalidacion$/.test(ruta)){
      const id=Number(ruta.split('/')[3]),bloqueos=[];
      if(id===220&&s.costo&&!s.matriz34)bloqueos.push({codigo:'LINEAS_PENDIENTE_CUENTA',mensaje:'Falta cuenta para MANO_OBRA_PROPIA en la matriz.'});
      if(id===220&&s.costo&&s.matriz34&&nombre==='restauracion_no_limpia')bloqueos.push({codigo:'LINEAS_PENDIENTE_CUENTA',mensaje:'La línea de mano de obra siguió sin cuenta.'});
      if(id===260&&!s.matriz49)bloqueos.push({codigo:'MATRIZ_CONTABLE_INCOMPLETA',mensaje:'Falta cuenta para depreciación de especie 423 del activo 1567.'});
      if(id===220&&!s.titulares.get(467).numero_id_tributaria)bloqueos.push({codigo:'FINCA_SIN_TITULAR',mensaje:'La finca 467 no tiene titular tributario.'});
      if(id===220&&nombre==='preflight_invalido')bloqueos.push({codigo:'OTRO',mensaje:'Dato incompatible'});
      return enviar(res,200,{bloqueos,activos_sin_precio:[],lineas_sin_trazabilidad:id===8?[{id_linea:17,tipo_hecho:'OTRO',id_activo_biologico:945,faltantes:['soporte'],nivel_fallo:'INCOMPLETO'}]:[],puede_cerrar:bloqueos.length===0,requiere_autorizacion:id===8},eco);
    }
    const finca=ruta.match(/^\/configuracion\/fincas\/(466|467)\/titular$/);
    if(finca){const id=Number(finca[1]);if(req.method==='GET')return enviar(res,200,s.titulares.get(id),eco);if(id===467&&nombre==='put_rechazado'&&body.numero_id_tributaria===null)return enviar(res,422,error('DTO_RECHAZADO','Titular rechazado.'),eco);s.titulares.set(id,{...s.titulares.get(id),...body});return enviar(res,200,s.titulares.get(id),eco);}
    if(ruta==='/finanzas/configuracion/matriz/34'&&req.method==='DELETE'){s.matriz34=false;res.writeHead(204,eco);res.end();return;}
    if(ruta==='/finanzas/configuracion/matriz/49'&&req.method==='DELETE'){s.matriz49=false;res.writeHead(204,eco);res.end();return;}
    if(ruta==='/finanzas/configuracion/matriz'&&req.method==='POST'){if(body.tipo_hecho==='MANO_OBRA_PROPIA')s.matriz34=true;else s.matriz49=true;return enviar(res,201,{id_asignacion_cuenta_contable:body.tipo_hecho==='MANO_OBRA_PROPIA'?34:49},eco);}
    if(ruta==='/finanzas/costos'&&req.method==='POST'){s.costo=true;return enviar(res,201,{registros:[{id_registro_costo:901}]},eco);}
    if(ruta==='/finanzas/costos'&&req.method==='GET')return enviar(res,200,s.costo?[{id_registro_costo:901}]:[],eco);
    if(ruta==='/finanzas/periodos/8/cierre/cancelacion'&&req.method==='POST'){const id=s.cierre8;s.estado8='ABIERTO';s.cierre8=null;return enviar(res,200,{id_periodo_contable:8,id_cierre:id,estado:'ABIERTO'},eco);}
    if(/^\/finanzas\/periodos\/\d+\/cierre$/.test(ruta)&&req.method==='POST'){
      const id=Number(ruta.split('/')[3]);
      if(rol!=='contador'){
        const etiqueta=rol==='admin'?'Administrador':rol==='prod'?'Productor':'Veterinario';
        const message=nombre==='mensaje_sin_rol'?'El cierre es exclusivo del Contador.':nombre==='mensajes_distintos'?`El cierre es exclusivo del Contador; su rol ${etiqueta} no puede iniciarlo.`:`Acceso denegado: El proceso de cierre del periodo contable es competencia exclusiva del Contador del sistema. Su rol actual (${etiqueta}) no tiene permisos de cierre contable bajo la política RBAC del módulo M06.`;
        return enviar(res,403,error('ACCESO_DENEGADO',message),eco);
      }
      if(id===7||id===219)return enviar(res,409,error('PERIODO_CERRADO',nombre==='cerrado_sin_fecha'?'El período ya fue cerrado por Ejecutor local.':nombre==='cerrado_fecha_bogota'?'Periodo inmutable: El período ya fue cerrado el 2026-11-06 por Ejecutor local.':nombre==='mensajes_distintos'?'El período ya fue cerrado el 2026-11-07 por Ejecutor local.':`Periodo inmutable: El período ya fue cerrado el 2026-11-07 por Ejecutor local.`),eco);
      if(id===8){
        if(s.estado8==='ABIERTO'){s.estado8='EN_CIERRE';s.cierre8=68;s.post8++;return enviar(res,409,error('EXCLUSION_REQUIERE_AUTORIZACION','Autorice la exclusión de la línea 17.'),eco);}
        if(nombre==='segundo_cierre')s.cierre8=69;
        return enviar(res,409,error('CIERRE_EN_EJECUCION',nombre==='hora_utc'?'Conflicto de concurrencia: cierre iniciado el 2026-11-13 08:00 por Ejecutor local.':nombre==='hora_ausente'?'Conflicto de concurrencia: cierre iniciado por Ejecutor local.':nombre==='mensajes_distintos'?'El cierre activo empezó el 2026-11-13 03:00 por Ejecutor local.':'Conflicto de concurrencia: cierre iniciado el 2026-11-13 03:00 por Ejecutor local.'),eco);
      }
      if(nombre==='a_cierra'&&id===220&&s.costo&&!s.matriz34){s.cerrado220=true;return enviar(res,200,{id_cierre:500,estado:'CERRADO'},eco);}
      if(nombre==='bloqueos_defecto'&&id===260&&!s.matriz49){s.cerrado260=true;return enviar(res,200,{id_cierre:501,estado:'CERRADO'},eco);}
      if(nombre==='bloqueos_defecto'&&id===220&&!s.titulares.get(467).numero_id_tributaria){s.cerrado220=true;return enviar(res,200,{id_cierre:502,estado:'CERRADO'},eco);}
      if(id===220&&s.costo&&!s.matriz34)return enviar(res,422,error('CIERRE_BLOQUEADO','Falta cuenta para MANO_OBRA_PROPIA en la matriz.'),eco);
      if(id===260&&!s.matriz49)return enviar(res,422,error('CIERRE_BLOQUEADO','Falta cuenta para depreciación de especie 423 del activo 1567.'),eco);
      if(id===220&&!s.titulares.get(467).numero_id_tributaria)return enviar(res,422,error('CIERRE_BLOQUEADO','La finca 467 no tiene titular tributario.'),eco);
      return enviar(res,409,error('CIERRE_BLOQUEADO','No se puede cerrar.'),eco);
    }
    if(ruta.startsWith('/test-control/runs/')&&req.method==='DELETE'){if(nombre==='delete_fallido')return enviar(res,500,error('DELETE_FALLIDO','No se pudo cerrar RUN'),eco);reset();return enviar(res,200,{eliminado:true},eco);}
    return enviar(res,404,error('NO_ENCONTRADO',ruta),eco);
  });
  return{server,peticiones};
}

let numero=0;
for(const nombre of escenarios)for(const inyectados of [false,true]){
  const {server,peticiones}=servidor(nombre,inyectados);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const runId=`RUN-G44-V3-20261113-${String(++numero).padStart(6,'0')}`,dir=path.join(raiz,runId);fs.mkdirSync(dir);
  const env={...process.env,QA_SANDBOX_SECRET:'LOCAL',QA_CONTADOR_EMAIL:'qa_contador@local.invalid',QA_CONTADOR_PASSWORD:'LOCAL',QA_ADMIN_EMAIL:'qa_admin@local.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_PROD_EMAIL:'qa_prod@local.invalid',QA_PROD_PASSWORD:'LOCAL',QA_VETERINARIO_EMAIL:'qa_veterinario@local.invalid',QA_VETERINARIO_PASSWORD:'LOCAL'};
  const limite=LIMITE.solicitudes_totales;if(nombre==='presupuesto_rollback')LIMITE.solicitudes_totales=75;
  let r;try{r=await ejecutar({dir,runId,version:3,intento:1,ref:'LOCAL'},env,{ensayo:true,api:`http://127.0.0.1:${server.address().port}/api`,hijo:async(_script,input)=>({code:0,data:await ejecutarNewman(input),error:''})});}
  finally{LIMITE.solicitudes_totales=limite;await new Promise(resolve=>server.close(resolve));}
  assert.deepEqual(validarFormaResultado(r,CAPACIDADES,dir),[]);
  const estados=CAPACIDADES.casos.map(c=>r.casos[c].estado);
  if(['conforme','8_abierto','mensajes_distintos','admin_permiso_5','cerrado_fecha_bogota','hora_utc','hora_bogota'].includes(nombre))assert.deepEqual([...estados,r.oficial],['APROBADO','APROBADO','APROBADO',true],nombre);
  if(nombre==='hora_utc')assert(r.observaciones.some(x=>x.includes('OBS-G44-03')&&x.includes('UTC')));
  if(nombre==='hora_bogota')assert(!r.observaciones.some(x=>x.includes('OBS-G44-03')));
  if(nombre==='hora_ausente'){assert.equal(r.casos['TC-M06-030'].comprobaciones.find(x=>x.id==='030_concurrencia')?.estado,'RECHAZADO');assert(!r.observaciones.some(x=>x.includes('OBS-G44-03')));}
  if(nombre==='admin_permiso_5'){assert(r.observaciones.some(x=>x.includes('OBS-G44-02')&&x.includes('observado')));assert(!peticiones.some(x=>x.metodo==='POST'&&x.ruta==='/finanzas/periodos/220/cierre'&&x.rol==='admin'));}
  if(['vet_permiso_5','permisos_aborto'].includes(nombre)){assert(estados.every(x=>x==='NO_CONCLUYENTE'));assert(r.rollback.verificado&&r.rollback.motivo==='Sin escrituras; DELETE 200');assert.equal(r.clasificacion_fallo,'PERMISO');assert(!peticiones.some(x=>x.metodo==='POST'&&x.ruta.endsWith('/cierre')));assert(r.preflight_datos.some(x=>x.requisito===(nombre==='vet_permiso_5'?'permiso_veterinario_cierre_periodo_5':'permiso_contador_cierre_periodo_5')&&!x.cumple&&x.bloqueante));}
  if(nombre==='contrato_invalido'){assert(estados.every(x=>x==='NO_CONCLUYENTE'));assert.equal(r.aborto_contrato?.ruta,'/finanzas/periodos');assert.equal(r.aborto_contrato?.http,200);assert(String(r.aborto_contrato?.campo).includes('precios_congelados'));assert(Array.isArray(r.aborto_contrato?.cuerpo));assert.equal(r.rollback.motivo,'Sin escrituras; DELETE 200');}
  if(nombre==='conforme'){assert(r.respuestas_escritura_fallida?.some(x=>x.ruta==='/finanzas/periodos/220/cierre'&&x.http===403&&x.cuerpo?.error_code));}
  if(nombre==='mensajes_distintos')assert(r.observaciones.some(x=>x.includes('OBS-G44-01')));
  if(nombre==='bloqueos_defecto')assert.equal(estados[0],'RECHAZADO');
  if(nombre==='a_cierra')assert(r.casos['TC-M06-028'].comprobaciones.find(x=>x.id==='028_c')?.estado==='NO_CONCLUYENTE'&&r.casos['TC-M06-028'].comprobaciones.find(x=>x.id==='028_b')?.estado==='APROBADO');
  if(nombre==='mensaje_sin_rol')assert.equal(estados[1],'RECHAZADO');
  if(nombre==='cerrado_sin_fecha'||nombre==='segundo_cierre')assert.equal(estados[2],'RECHAZADO');
  if(['220_cerrado_anterior','260_cerrado_anterior','preflight_invalido','sin_activo_467'].includes(nombre))assert(!r.oficial&&!peticiones.some(x=>x.metodo==='POST'&&x.ruta.endsWith('/cierre')));
  if(nombre==='restauracion_no_limpia')assert(r.problemas_tecnicos.some(x=>x.includes('RESTAURACION_NO_LIMPIA'))&&peticiones.some(x=>x.ruta==='/finanzas/periodos/260/cierre'));
  if(nombre==='put_rechazado')assert(r.casos['TC-M06-028'].comprobaciones.find(x=>x.id==='028_c')?.estado==='NO_CONCLUYENTE');
  if(nombre==='presupuesto_rollback')assert(r.problemas_tecnicos.some(x=>x.includes('PRESUPUESTO'))&&r.rollback.verificado&&peticiones.some(x=>x.metodo==='GET'&&!x.run));
  if(nombre==='delete_fallido')assert.equal(r.cierre.run.cierre_http,500);
  if(!['220_cerrado_anterior','260_cerrado_anterior','preflight_invalido','sin_activo_467','vet_permiso_5','permisos_aborto','contrato_invalido'].includes(nombre))assert(peticiones.some(x=>x.ruta==='/finanzas/periodos/8/cierre/cancelacion'));
  const reporte=fs.readFileSync(path.join(dir,'TC-M06-G44_reevaluacion_V3.md'),'utf8');assert(reporte.includes('reevaluación V3'));
  assert(!/NIT-[ABC]|Ejecutor local/.test(reporte));
  if(r.oficial){const presentes=new Set(fs.readdirSync(dir,{recursive:true}).map(String).map(x=>x.replaceAll('\\','/')));assert(clasificarRegistro(CAPACIDADES,r,presentes,{runId,referencia:'LOCAL',version:3}));}
  console.log(`OK ${nombre}/${inyectados?'extra':'normal'}: ${estados.join('/')} oficial=${r.oficial}`);
}
