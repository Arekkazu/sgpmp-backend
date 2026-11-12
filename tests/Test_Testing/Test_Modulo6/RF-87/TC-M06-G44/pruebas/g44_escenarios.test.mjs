import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {ejecutar,CAPACIDADES} from '../g44.mjs';
import {validarFormaResultado,clasificarRegistro} from '../lib/infra.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';

const metadata=JSON.parse(fs.readFileSync(new URL('./escenarios_g44.json',import.meta.url),'utf8'));
const raiz=process.env.QA_VERIFICAR_SALIDAS??fs.mkdtempSync(path.join(os.tmpdir(),'g44-escenarios-'));
fs.mkdirSync(raiz,{recursive:true});
const error=(http,code,message)=>({http,data:{error_code:code,message,fields:[],timestamp:'2026-11-10T00:00:00Z'}});
const titular=()=>({id_finca:466,nombre:'Finca QA',tipo_id_tributaria:'NIT',numero_id_tributaria:'900000123',dv:'4',razon_social:'Titular QA'});
function servidor(nombre,inyectados){
  const peticiones=[];let estado;
  const reiniciar=()=>{estado={matriz34:true,matriz49:true,titular:titular(),costo:false,cerrado220:false,cerrado260:false,post8:0};};reiniciar();
  const actual=nombre==='codigo_actual';
  const inyectar=d=>{if(!inyectados)return d;if(Array.isArray(d))return d.map(x=>x&&typeof x==='object'?{...x,campo_inyectado:'ignorar'}:x);return d&&typeof d==='object'?{...d,campo_inyectado:'ignorar'}:d;};
  const responder=(res,http,data,headers={})=>{res.writeHead(http,{'content-type':'application/json',...headers});res.end(JSON.stringify(inyectar(data)));};
  const server=http.createServer(async(req,res)=>{
    const chunks=[];for await(const x of req)chunks.push(x);const body=chunks.length?JSON.parse(Buffer.concat(chunks).toString()):{};
    const url=new URL(req.url,'http://127.0.0.1');const ruta=url.pathname.replace(/^\/api/,'');
    const rol=String(req.headers.authorization??'').replace('Bearer TOKEN_','').toLowerCase();
    peticiones.push({metodo:req.method,ruta,rol,run:Boolean(req.headers['x-test-run-id'])});
    const eco=req.headers['x-test-run-id']?{'x-test-run-id':req.headers['x-test-run-id']}:{ };
    if(ruta==='/sesiones/'&&req.method==='POST'){
      const match=String(body.correo_electronico??'').match(/^qa_(contador|admin|veterinario|prod)@/);return responder(res,200,{token:`TOKEN_${(match?.[1]??'INVALIDO').toUpperCase()}`},eco);
    }
    if(ruta==='/sesiones/me/permisos'){
      const base=[['cierre_periodo',2],['configuracion_contable',2]];
      const porRol={contador:[...base,['cierre_periodo',5],['configuracion_contable',3],['costos_activos',1]],admin:[...base,['fincas',2],['fincas',3]],veterinario:[],prod:[]};
      return responder(res,200,{permisos:(porRol[rol]??[]).map(([nombre_recurso,id_accion])=>({nombre_recurso,id_accion}))},eco);
    }
    if(ruta==='/finanzas/activos'&&req.method==='GET')return responder(res,200,metadata.activos.map(x=>(nombre==='1572_sin_valoracion'&&x.id_activo_biologico===1572||nombre==='sin_activos_por_costo'&&[1572,1573].includes(x.id_activo_biologico))?{...x,valorado_por_costo:false,vida_util_meses:null}:x),eco);
    if(ruta==='/finanzas/periodos'&&req.method==='GET'){
      const ps=[7,8,219,220,260].map(id=>({id_periodo_contable:id,numero_id_tributaria:id<=8?'NIT-A':id===219||id===260?'NIT-B':'NIT-C',fecha_inicio:id===8||id===260?'2026-12-01':'2026-11-01',fecha_fin:id===8||id===260?'2026-12-31':'2026-11-30',fecha_cierre:id===7||id===219||id===220&&(estado.cerrado220||nombre==='220_cerrado_tercero')||id===260&&(estado.cerrado260||nombre==='260_cerrado_tercero')?'2026-11-10T06:18:00Z':null,estado:id===7||id===219||id===220&&(estado.cerrado220||nombre==='220_cerrado_tercero')||id===260&&(estado.cerrado260||nombre==='260_cerrado_tercero')?'CERRADO':'ABIERTO',ultimo_cierre:id===7?{id_cierre:700,id_usuario_ejecutor:77,fecha_fin:'2026-11-09T12:00:00Z'}:id===219?{id_cierre:43,id_usuario_ejecutor:141,fecha_fin:'2026-11-10T06:18:00Z'}:null}));return responder(res,200,ps,eco);
    }
    if(ruta==='/finanzas/configuracion'&&req.method==='GET')return responder(res,200,{general:{pct_umbral_desviacion_precio:'10'},especies:[],matriz:[...(estado.matriz34?[{id_asignacion_cuenta_contable:34,tipo_hecho:'MANO_OBRA_PROPIA',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'158405',cuenta_credito:'250505'}]:[]),...(estado.matriz49?[{id_asignacion_cuenta_contable:49,tipo_hecho:'DEPRECIACION_ACTIVO_COSTO',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'}]:[])]},eco);
    if(ruta==='/finanzas/lineas'&&req.method==='GET'){
      const id=Number(url.searchParams.get('id_periodo_contable'));const resuelta=estado.matriz34&&nombre!=='restauracion_no_limpia';const activoDepreciacion=nombre==='1572_sin_valoracion'?1573:1572;const xs=id===8?[{id_linea_asiento_nic41:17,estado:'PENDIENTE_TRAZABILIDAD',tipo_hecho:'OTRO',id_activo_biologico:945}]:id===220&&estado.costo?[{id_linea_asiento_nic41:51,estado:resuelta?'CONTABILIZADA':'PENDIENTE_CUENTA',tipo_hecho:'MANO_OBRA_PROPIA',id_activo_biologico:1569,cuenta_debito:resuelta?'158405':null,cuenta_credito:resuelta?'250505':null},...(!estado.matriz49?[{id_linea_asiento_nic41:52,estado:'PENDIENTE_CUENTA',tipo_hecho:'DEPRECIACION_ACTIVO_COSTO',id_activo_biologico:activoDepreciacion,cuenta_debito:null,cuenta_credito:null}]:[])]:id===220&&!estado.matriz49?[{id_linea_asiento_nic41:52,estado:'PENDIENTE_CUENTA',tipo_hecho:'DEPRECIACION_ACTIVO_COSTO',id_activo_biologico:activoDepreciacion,cuenta_debito:null,cuenta_credito:null}]:[];return responder(res,200,xs,eco);
    }
    if(/^\/finanzas\/periodos\/\d+\/(comprobantes|variaciones)$/.test(ruta))return responder(res,200,[],eco);
    if(/^\/finanzas\/periodos\/\d+\/prevalidacion$/.test(ruta)){
      const id=Number(ruta.split('/')[3]);const bloqueos=[];
      if(id===220&&nombre==='prevalidacion_distinta')bloqueos.push({codigo:'OTRO_BLOQUEO',mensaje:'Dato distinto'});
      if(id===220&&estado.costo&&(!estado.matriz34||nombre==='restauracion_no_limpia'))bloqueos.push({codigo:'LINEAS_PENDIENTE_CUENTA',mensaje:'MANO_OBRA_PROPIA sin cuentas en matriz'});
      if(id===260&&!estado.titular.tipo_id_tributaria&&nombre==='conforme')bloqueos.push({codigo:'FINCA_SIN_TITULAR',mensaje:'Finca sin titular tributario'});
      return responder(res,200,{bloqueos,activos_sin_precio:[],lineas_sin_trazabilidad:id===8?[{id_linea:17,tipo_hecho:'OTRO',id_activo_biologico:945,faltantes:['soporte'],nivel_fallo:'INCOMPLETO'}]:[],puede_cerrar:bloqueos.length===0,requiere_autorizacion:id===8},eco);
    }
    if(ruta==='/configuracion/fincas/466/titular'&&req.method==='GET')return responder(res,200,estado.titular,eco);
    if(ruta==='/configuracion/fincas/467/titular'&&req.method==='GET')return responder(res,200,{...titular(),id_finca:467},eco);
    if(ruta==='/configuracion/fincas/466/titular'&&req.method==='PUT'){
      if(nombre==='put_rechazado')return responder(res,422,error(422,'DTO_RECHAZADO','PUT rechazado').data,eco);
      estado.titular={...estado.titular,tipo_id_tributaria:null,numero_id_tributaria:null,dv:null,razon_social:null};return responder(res,200,estado.titular,eco);
    }
    if(ruta==='/finanzas/configuracion/matriz/34'&&req.method==='DELETE'){estado.matriz34=false;res.writeHead(204,eco);res.end();return;}
    if(ruta==='/finanzas/configuracion/matriz'&&req.method==='POST'){estado.matriz34=true;return responder(res,201,{id_asignacion_cuenta_contable:70},eco);}
    if(ruta==='/finanzas/configuracion/matriz/49'&&req.method==='DELETE'){estado.matriz49=false;res.writeHead(204,eco);res.end();return;}
    if(ruta==='/finanzas/costos'&&req.method==='POST'){estado.costo=true;return responder(res,201,{registros:[{id_registro_costo:901}]},eco);}
    if(ruta==='/finanzas/costos'&&req.method==='GET')return responder(res,200,estado.costo?[{id_registro_costo:901,subtipo_costo:'MANO_OBRA',naturaleza_costo:'MANTENIMIENTO',monto_costo:'103.00',fecha_costo:'2026-11-10',id_periodo_contable:220,id_activo_biologico:1569}]:[],eco);
    if(/^\/finanzas\/periodos\/\d+\/cierre$/.test(ruta)&&req.method==='POST'){
      const id=Number(ruta.split('/')[3]);
      if(rol!=='contador')return responder(res,403,error(403,'ACCESO_DENEGADO',actual?'Acceso denegado. Su rol no tiene permisos para realizar esta operación.':`Acceso denegado: El proceso de cierre del periodo contable es competencia exclusiva del Contador del sistema. Su rol actual (${rol==='admin'?'Administrador':rol==='prod'?'Productor':'Veterinario'}) no puede iniciar el cierre.`).data,eco);
      if(id===7||id===219)return responder(res,409,error(409,'PERIODO_CERRADO',actual?'El período 2026-11 ya fue cerrado el 2026-11-09.':`Periodo inmutable: El periodo contable ${id} ya fue cerrado el 2026-11-09 por el Contador ${id===7?77:141}.`).data,eco);
      if(id===8){estado.post8++;return responder(res,409,error(409,'EXCLUSION_REQUIERE_AUTORIZACION',actual||estado.post8===1?'Autorice la exclusión de línea 17.':'Conflicto de concurrencia: El periodo 8 está siendo procesado por otro proceso de cierre activo iniciado el 2026-11-10 00:00 por el usuario 5.').data,eco);}
      if(id===220&&!estado.matriz34)return responder(res,422,error(422,'CIERRE_BLOQUEADO','MANO_OBRA_PROPIA sin cuenta en matriz contable.').data,eco);
      const exito={id_cierre:501,id_periodo_contable:id,periodo:'2026-11',estado:'CERRADO',activos_procesados:2,activos_excluidos:[],lineas_excluidas:[],comprobantes:[],hash_cierre:'LOCAL',id_periodo_siguiente:221,reportes:{estado_resultados:{},informe_revelaciones:{}}};
      if(id===260&&estado.titular.tipo_id_tributaria===null){if(actual){estado.cerrado260=true;return responder(res,200,exito,eco);}return responder(res,422,error(422,'CIERRE_BLOQUEADO','Finca sin titular tributario: complete el titular de finca 466.').data,eco);}
      if(id===220&&!estado.matriz49){if(actual){estado.cerrado220=true;return responder(res,200,exito,eco);}return responder(res,422,error(422,'CIERRE_BLOQUEADO','DEPRECIACION_ACTIVO_COSTO sin cuenta en la matriz.').data,eco);}
      return responder(res,409,error(409,'CIERRE_BLOQUEADO','Faltantes de cierre.').data,eco);
    }
    if(ruta.startsWith('/test-control/runs/')&&req.method==='DELETE'){
      if(nombre==='delete_fallido')return responder(res,500,error(500,'DELETE_FALLIDO','No se pudo cerrar RUN').data,eco);
      reiniciar();return responder(res,200,{eliminado:true},eco);
    }
    return responder(res,404,error(404,'NO_ENCONTRADO',ruta).data,eco);
  });
  return{server,peticiones};
}

let indice=0;
for(const nombre of metadata.escenarios)for(const variante of metadata.variantes){
  const {server,peticiones}=servidor(nombre,variante==='campos_inyectados');
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const runId=`RUN-G44-V2-20261110-${String(++indice).padStart(6,'0')}`;
  const dir=path.join(raiz,runId);fs.mkdirSync(dir);
  const e={...process.env,QA_SANDBOX_SECRET:'LOCAL',QA_CONTADOR_EMAIL:'qa_contador@local.invalid',QA_CONTADOR_PASSWORD:'LOCAL',QA_ADMIN_EMAIL:'qa_admin@local.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_PROD_EMAIL:'qa_prod@local.invalid',QA_PROD_PASSWORD:'LOCAL',QA_VETERINARIO_EMAIL:'qa_veterinario@local.invalid',QA_VETERINARIO_PASSWORD:'LOCAL'};
  let r;try{r=await ejecutar({dir,runId,version:2,intento:1,ref:'LOCAL'},e,{ensayo:true,api:`http://127.0.0.1:${server.address().port}/api`,hijo:async(script,input)=>({code:0,data:await ejecutarNewman(input),error:''})});}
  finally{await new Promise(resolve=>server.close(resolve));}
  const esperado=nombre==='conforme'||nombre==='1572_sin_valoracion'?['APROBADO','APROBADO','APROBADO',true]:nombre==='codigo_actual'?['RECHAZADO','RECHAZADO','RECHAZADO',true]:nombre==='prevalidacion_distinta'||nombre==='sin_activos_por_costo'?['NO_CONCLUYENTE','NO_CONCLUYENTE','NO_CONCLUYENTE',false]:nombre==='delete_fallido'?['APROBADO','APROBADO','APROBADO',false]:nombre==='220_cerrado_tercero'||nombre==='260_cerrado_tercero'?['NO_CONCLUYENTE','NO_CONCLUYENTE','NO_CONCLUYENTE',false]:['NO_CONCLUYENTE','APROBADO','APROBADO',false];
  const estados=CAPACIDADES.casos.map(c=>r.casos[c].estado);
  assert.deepEqual([...estados,r.oficial],esperado,`${nombre}/${variante}: ${r.problemas_tecnicos.join('; ')}`);
  assert.deepEqual(validarFormaResultado(r,CAPACIDADES,dir),[]);
  assert(r.total_solicitudes_api<=200);
  assert(Array.isArray(r.preflight_datos)&&r.preflight_datos.length>=12);
  assert(r.preflight_datos.every(x=>['requisito','esperado','observado','cumple','bloqueante'].every(k=>Object.hasOwn(x,k))));
  for(const id of [1572,1573]){const x=r.preflight_datos.find(x=>x.requisito===`activo_${id}_valorado_por_costo`);assert(x);assert.deepEqual(Object.keys(x.observado).sort(),['valorado_por_costo','vida_util_meses']);assert.equal(x.cumple,!['sin_activos_por_costo'].includes(nombre)&&(nombre!=='1572_sin_valoracion'||id!==1572));assert.equal(x.bloqueante,false);}
  const finca=r.preflight_datos.find(x=>x.requisito==='finca_467_activo_por_costo');assert(finca);assert.equal(finca.bloqueante,true);assert.deepEqual(finca.observado,r.activos_por_costo_467);assert.equal(finca.cumple,nombre!=='sin_activos_por_costo');
  assert.deepEqual(r.activos_por_costo_467,nombre==='sin_activos_por_costo'?[]:nombre==='1572_sin_valoracion'?[1573]:[1572,1573]);
  assert.equal(peticiones.filter(x=>x.metodo==='GET'&&x.ruta==='/finanzas/activos').length,1);
  assert(fs.readFileSync(path.join(dir,'TC-M06-G44_reevaluacion_V2.md'),'utf8').includes('## Preflight de datos'));
  const posicion=(metodo,ruta)=>peticiones.findIndex(x=>x.metodo===metodo&&x.ruta===ruta);
  if(!['prevalidacion_distinta','220_cerrado_tercero','260_cerrado_tercero','sin_activos_por_costo'].includes(nombre)){
    assert(posicion('POST','/finanzas/configuracion/matriz')>posicion('POST','/finanzas/costos'));
    if(nombre!=='restauracion_no_limpia')assert(posicion('POST','/finanzas/configuracion/matriz')<posicion('DELETE','/finanzas/configuracion/matriz/49'));
  }
  assert.equal(peticiones.filter(x=>x.metodo==='POST'&&x.ruta==='/finanzas/periodos/220/cierre').length,['prevalidacion_distinta','220_cerrado_tercero','260_cerrado_tercero','sin_activos_por_costo'].includes(nombre)?0:nombre==='restauracion_no_limpia'?4:5);
  if(!['prevalidacion_distinta','220_cerrado_tercero','260_cerrado_tercero','sin_activos_por_costo'].includes(nombre)){
    for(const clave of ['029_admin','029_veterinario','029_productor','030_cerrado','030_cerrado_219','030_primero','030_segundo','028_a',...(nombre==='restauracion_no_limpia'?[]:['028_b'])]){
      const z=r.respuestas_cierre?.[clave];assert(z&&z.cuerpo,`${nombre}/${variante}: cuerpo ${clave}`);
      if(z.http>=400)assert(Object.hasOwn(z.cuerpo,'error_code')&&Object.hasOwn(z.cuerpo,'message')&&Array.isArray(z.cuerpo.fields));
      if(z.http===200)assert(Array.isArray(z.comprobantes)&&Array.isArray(z.lineas));
    }
  }
  if(nombre==='codigo_actual'){
    assert(r.respuestas_cierre['028_c'].cuerpo.activos_procesados!==undefined);
    assert(r.respuestas_cierre['028_b'].lineas.some(x=>x.tipo_hecho==='DEPRECIACION_ACTIVO_COSTO'&&x.estado==='PENDIENTE_CUENTA'&&x.cuenta_debito===null));
  }
  if(!['prevalidacion_distinta','220_cerrado_tercero','260_cerrado_tercero','sin_activos_por_costo'].includes(nombre))assert(r.observacion_030_219.includes('141'));
  if(nombre==='restauracion_no_limpia')assert(!peticiones.some(x=>x.metodo==='DELETE'&&x.ruta==='/finanzas/configuracion/matriz/49'));
  if(['prevalidacion_distinta','220_cerrado_tercero','260_cerrado_tercero','sin_activos_por_costo'].includes(nombre)){
    assert(!peticiones.some(x=>['PUT','DELETE'].includes(x.metodo)&&!x.ruta.startsWith('/test-control/'))&&!peticiones.some(x=>x.ruta==='/finanzas/costos'&&x.metodo==='POST'));
    assert.equal(peticiones.filter(x=>x.metodo==='DELETE'&&x.ruta.startsWith('/test-control/runs/')).length,1);
    assert.equal(r.cierre.run.cierre_http,200);assert.equal(r.rollback.verificado,true);assert.equal(r.oficial,false);
    assert(peticiones.some(x=>x.metodo==='GET'&&x.ruta==='/finanzas/periodos'&&!x.run));
  }
  if(['220_cerrado_tercero','260_cerrado_tercero'].includes(nombre))assert(r.preflight_datos.some(x=>x.requisito===`periodo_${nombre.slice(0,3)}_estado`&&!x.cumple));
  if(nombre==='1572_sin_valoracion')assert(!r.problemas_tecnicos.some(x=>x.includes('activo_1572_valorado_por_costo')));
  if(nombre==='sin_activos_por_costo')assert(r.problemas_tecnicos.some(x=>x.includes('finca_467_activo_por_costo')));
  if(nombre==='delete_fallido')assert.equal(r.cierre.run.cierre_http,500);
  if(r.oficial){const presentes=new Set(fs.readdirSync(dir,{recursive:true}).map(String).map(x=>x.replaceAll('\\','/')));assert(clasificarRegistro(CAPACIDADES,r,presentes,{runId,referencia:'LOCAL',version:2}));}
  console.log(`OK escenario_${nombre}_${variante}: 028=${estados[0]} 029=${estados[1]} 030=${estados[2]} oficial=${r.oficial} solicitudes=${r.total_solicitudes_api}/200`);
}
