import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { randomInt } from 'node:crypto';
import { mock, validarMock, truncar2, redondear2, CONTRATO } from '../lib/g38_core.mjs';
import { principal, predecir } from '../g38.mjs';

const g37=JSON.parse(fs.readFileSync(new URL('../../TC-M06-G37/Resultados/RUN-G37-V1-20261108-233956/resultado.json',import.meta.url),'utf8'));
assert.equal(g37.observaciones.candidatos.length,16);
assert.equal(g37.solicitudes.filter(x=>x.id==='precios_get').length,5);
assert.deepEqual(g37.observaciones.paso_3.variaciones.map(x=>[x.id,x.linea]),[[257,904],[256,903]]);
function replayG37(){
  const paso=g37.observaciones.paso_3;
  const precio=mock('precios_get');precio[0].id_precio_mercado=paso.precio;
  const evento=mock('evento_crecimiento');evento.evento.id_eventos=paso.evento;
  const procesar=mock('procesar');
  const variaciones=paso.variaciones.map(x=>({...mock('variaciones')[0],
    id_variacion_valor_razonable:x.id,tipo:x.tipo,monto_variacion:x.monto,id_linea:x.linea}));
  const mediciones=mock('mediciones');mediciones[0].id_medicion_posterior=g37.observaciones.nuevos.mediciones[2];
  for(const [id,cuerpo] of [['precios_get',precio],['evento_crecimiento',evento],
    ['procesar',procesar],['variaciones',variaciones],['mediciones',mediciones]])
    assert.equal(validarMock(id,cuerpo),true,id);
  console.log(`OK replay_run_g37: 16 activos, 5 especies, evento ${paso.evento}, precio ${paso.precio}, variaciones ${variaciones.length}, medicion con ID observado`);
}
replayG37();

const matriz=[
  {id_asignacion_cuenta_contable:12,tipo_hecho:'VARIACION_VR_TB',sentido:'GANANCIA',id_especie:null,subtipo_costo:null,
    cuenta_debito:'158405',cuenta_credito:'424805'},
  {id_asignacion_cuenta_contable:18,tipo_hecho:'VARIACION_VR_PM',sentido:'PERDIDA',id_especie:null,subtipo_costo:null,
    cuenta_debito:'539505',cuenta_credito:'158405'}];
const costos={id_especie:39,region:'GENERAL',es_activo:true,pct_transporte:'0.0137',pct_comisiones:'0',pct_impuestos:'0'};
// Cardinalidad y candidatos del resultado oficial G37; los cuerpos no conservados allí son mocks de contrato.
const idsCatalogo=g37.observaciones.candidatos.map(x=>x.activo);
function catalogo(){return idsCatalogo.map((id,i)=>{
  const a=mock('activos')[0];return {...a,id_activo_biologico:id,id_especie:i<6?39:[40,41,42,43][(i-6)%4],
    especie:i<6?'Bovino':'Caprino',tipo:i>=14?'LOTE':'INDIVIDUAL',
    estado:i===5?'BAJA':'ACTIVO',valorado_por_costo:i>=6&&i<=10};
});}
const linea=(id,origen,tipo,sentido,valor,cuentas)=>({
  id_linea_asiento_nic41:id,tipo_hecho:tipo,sentido,estado:'REGISTRADA',valor:Number(valor),fecha_hecho:'2026-11-08',
  id_periodo_contable:8,id_activo_biologico:943,id_especie:39,id_finca:1,numero_id_tributaria:'900000001',
  tabla_origen:'variaciones_valor_razonable',id_origen:origen,tipo_evidencia:'REGISTRO_MANUAL',subtipo_costo:null,
  es_estimacion:false,es_reverso:false,tipo_hecho_corregido:null,id_linea_corregida:null,
  cuenta_debito:cuentas[0],cuenta_credito:cuentas[1],justificacion:null,id_usuario:null,
  estado_trazabilidad:'VERIFICACION_PENDIENTE',id_comprobante_nic41:null,
  extra:{estado_trazabilidad:'VERIFICACION_PENDIENTE',id_comprobante_nic41:null}});
const variacion=(id,tipo,valor,lineaId)=>({id_variacion_valor_razonable:id,id_activo_biologico:943,
  tipo,monto_variacion:Number(truncar2(valor))*(String(valor).startsWith('-')?-1:1),
  valor_razonable_anterior:98630,valor_razonable_nuevo:103068.35,fecha_registro:'2026-11-08',
  id_linea:lineaId,tipo_evidencia:'REGISTRO_MANUAL',estado_trazabilidad:'VERIFICACION_PENDIENTE'});

async function escenario(nombre,fila=false){
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'g38-ensayo-'));
  const runId=`RUN-G38-V1-20261108-${String(randomInt(1000000)).padStart(6,'0')}`;
  const dir=path.join(temp,runId);fs.mkdirSync(dir);
  const contexto=path.join(dir,'contexto_operacion.json'),ref='AUT-G38-ENSAYO';
  fs.writeFileSync(contexto,JSON.stringify({grupo:'G38',run_id:runId,version:1,intento:1,
    operacion:'EVALUAR',referencia:ref,casos:['TC-M06-014','TC-M06-015']}));
  let cerrada=false,escrituras=0,precio='1000.00',peso=100,calc={id_calculo_valor_razonable:1,
    id_precio_mercado:nombre.includes('rebase')?99:1,estado:'CALCULADO',magnitud:'100.00',valor_neto:'98630.0000',
    fecha_calculo:'2026-11-08',json_metodo_costo:{}},pendiente=null;
  const lineas=[],mediciones=[],variaciones=[];
  if(nombre==='id_cambiado')lineas.push({...linea(700,700,'VARIACION_VR_TB','GANANCIA','10.00',
    ['158405','424805']),id_activo_biologico:999});
  let activas=0,solapamientos=0,peticiones=0,newmanPeticiones=0,deleteHttp=null,rebaseProcesado=false;
  const servidor=http.createServer(async(req,res)=>{
    assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'preflight.json'),'utf8')).ok,true,
      'preflight debe existir antes de la primera petición');
    const mismo=req.headers['x-test-run-id']===runId;
    if(mismo&&activas){solapamientos++;res.writeHead(500,{'Content-Type':'application/json','X-Test-Run-Id':runId});
      res.end(JSON.stringify({code:'CONCURRENCIA'}));return;}
    if(mismo)activas++;
    peticiones++;if(req.headers['user-agent']?.includes('PostmanRuntime'))newmanPeticiones++;
    await new Promise(resolve=>setTimeout(resolve,55));
    const enviar=(status,body)=>{if(mismo)activas--;res.writeHead(status,{'Content-Type':'application/json','X-Test-Run-Id':runId});res.end(JSON.stringify(body));};
    const url=new URL(req.url,'http://localhost'),ruta=url.pathname;
    let body={};if(req.method==='POST'){
      let raw='';for await(const x of req)raw+=x;try{body=JSON.parse(raw);}catch{} }
    if(ruta==='/sesiones/'&&req.method==='POST')return enviar(200,{token:body.correo_electronico?.includes('admin')?'admin-local':'contador-local'});
    if(ruta==='/sesiones/me/permisos'&&nombre==='permisos')return enviar(200,{permisos:[]});
    if(ruta==='/sesiones/me/permisos')return enviar(200,{permisos:Object.entries(CONTRATO.roles[
      req.headers.authorization?.includes('admin-local')?'admin':'contador'].permisos).flatMap(([recurso,acciones],i)=>
      acciones.map(accion=>({id_recurso:i+1,id_accion:accion,nombre_recurso:recurso})))});
    if(ruta===`/test-control/runs/${runId}`&&req.method==='DELETE'){
      deleteHttp=nombre==='cierre'?500:200;cerrada=deleteHttp===200;return enviar(deleteHttp,{ok:deleteHttp===200});}
    if(ruta==='/finanzas/activos')return enviar(nombre==='seleccion'?200:200,nombre==='seleccion'?[]:catalogo());
    if(ruta==='/finanzas/periodos')return enviar(200,[{id_periodo_contable:8,numero_id_tributaria:'900000001',
      fecha_inicio:'2020-01-01',fecha_fin:'2030-12-31',estado:'ABIERTO',ultimo_cierre:null}]);
    if(ruta==='/finanzas/precios'&&req.method==='GET')return enviar(200,[{id_precio_mercado:1,
      id_especie:Number(url.searchParams.get('id_especie')),categoria:'PESO_KG',fuente:'MERCADO_ACTIVO',
      precio_unitario:'1000.00',fecha_vigencia:'2020-01-01',fecha_vencimiento:null}]);
    if(ruta==='/finanzas/precios'&&req.method==='POST'&&nombre==='precio')return enviar(400,{code:'PRECIO_INVALIDO'});
    if(ruta==='/finanzas/precios'&&req.method==='POST'){escrituras++;precio=String(body.precio_unitario);
      return enviar(201,{id_precio_mercado:2,estado:'VIGENTE',unidad_medida:'kg',desviacion_pct:null,fecha_vigencia:'2026-11-08'});}
    if(/^\/finanzas\/activos\/(943|944|945|946|947)$/.test(ruta))return enviar(nombre==='seleccion_500'&&ruta.endsWith('/943')?500:200,{activo:{numero_id_tributaria:'900000001',id_dispositivo_iot:null},
      calculos:[calc],mediciones:[]});
    if(/^\/activos-biologicos\/(943|944|945|946|947)\/ficha-integral$/.test(ruta))return enviar(200,{peso_actual:String(peso),unidad_peso:'kg',estado_actual:'ACTIVO'});
    if(ruta==='/finanzas/configuracion'&&nombre==='lecturas_previas')return enviar(500,{code:'ERROR_INTERNO'});
    if(ruta==='/finanzas/configuracion'&&nombre==='newman'&&req.headers['user-agent']?.includes('PostmanRuntime'))return enviar(500,{code:'ERROR_INTERNO'});
    if(ruta==='/finanzas/configuracion')return enviar(200,{matriz:nombre==='matriz_sin_par'?[matriz[0]]:matriz,
      costos_venta:[costos],general:{},especies:[],lineas_pendientes_cuenta:0});
    if(ruta==='/finanzas/periodos/8/variaciones'&&nombre==='lecturas_posteriores'&&mediciones.length)return enviar(500,{code:'ERROR_INTERNO'});
    if(ruta==='/finanzas/periodos/8/variaciones')return enviar(200,cerrada?[]:variaciones);
    if(ruta==='/finanzas/periodos/8/mediciones')return enviar(200,cerrada?[]:mediciones);
    if(ruta==='/finanzas/lineas')return enviar(200,cerrada?[]:lineas);
    if(/^\/activos-biologicos\/(943|944|945|946|947)\/eventos$/.test(ruta)&&req.method==='GET')return enviar(200,{eventos:[]});
    if(/^\/activos-biologicos\/(943|944|945|946|947)\/eventos\/crecimiento$/.test(ruta)&&req.method==='POST'&&nombre==='pesaje')return enviar(400,{code:'FECHA_INVALIDA'});
    if(/^\/activos-biologicos\/(943|944|945|946|947)\/eventos\/crecimiento$/.test(ruta)&&req.method==='POST'){
      escrituras++;pendiente={id:1300+escrituras,peso:Number(body.valor_medicion)};
      return enviar(201,{evento:{id_eventos:pendiente.id}});
    }
    if(ruta==='/finanzas/eventos/procesar'&&req.method==='POST'&&nombre==='procesar')return enviar(500,{code:'ERROR_INTERNO'});
    if(ruta==='/finanzas/eventos/procesar'&&req.method==='POST'){
      if(!pendiente)return enviar(200,{eventos:[],provisiones_m05:[]});
      if(nombre.includes('rebase')&&!rebaseProcesado){rebaseProcesado=true;
        calc={...calc,id_precio_mercado:1};pendiente=null;
        return enviar(200,{eventos:[{estado:'MEDIDO'}],provisiones_m05:[]});}
      const pred=predecir(precio,String(pendiente.peso),calc,costos),step=mediciones.length;
      const mid=200+step,vid=256+step*2,lid=903+step*2;
      const tbReal=nombre.includes('no_discriminante')?'100.0000':pred.tb;
      mediciones.push({id_medicion_posterior:mid,id_activo_biologico:943,estado:'MEDIDO',
        ganancia_perdida_transformacion:Number(tbReal),ganancia_perdida_precio_mercado:Number(nombre==='pm_redondeada'&&step===0?'-4931.5059':pred.pm),
        variacion_total:Number(pred.tb)+Number(pred.pm)});
      variaciones.push(variacion(vid,'GANANCIA_TRANSFORMACION_BIOLOGICA',pred.tb,lid));
      lineas.push(linea(lid,vid,'VARIACION_VR_TB','GANANCIA',truncar2(tbReal),['158405','424805']));
      if(step===0){variaciones.push(variacion(vid+1,'PERDIDA_PRECIO_MERCADO',pred.pm,lid+1));
        if(nombre!=='linea_faltante')lineas.push(linea(lid+1,vid+1,'VARIACION_VR_PM','PERDIDA',
          nombre==='pm_redondeada'?redondear2('-4931.5059'):truncar2(pred.pm),
          nombre==='cuentas_iguales'?['158405','158405']:['539505','158405']));
        if(nombre==='pendiente_cuenta')lineas.at(-1).estado='PENDIENTE_CUENTA';}
      if(nombre==='id_duplicado'&&step===0)lineas[lineas.length-1].id_linea_asiento_nic41=903;
      if(nombre==='id_cambiado'&&step===0)lineas[0].id_linea_asiento_nic41=999;
      peso=pendiente.peso;calc={...calc,id_calculo_valor_razonable:2+step,
        id_precio_mercado:nombre.includes('rebase')&&step===0?1:2,
        magnitud:String(peso),valor_neto:pred.neto,fecha_calculo:`2026-11-${String(9+step).padStart(2,'0')}`};
      pendiente=null;return enviar(200,{eventos:[{estado:'MEDIDO'}],provisiones_m05:[]});
    }
    enviar(404,{error_code:'NO_ENCONTRADO'});
  });
  await new Promise(r=>servidor.listen(0,'127.0.0.1',r));
  try{
    const base=`http://127.0.0.1:${servidor.address().port}`;
    const proceso={QA_AUTORIZADO:'SI',SIGAB_API_TEST_BASE:base,QA_SANDBOX_SECRET:'LOCAL',
      QA_CONTADOR_EMAIL:'contador@local.test',QA_CONTADOR_PASSWORD:'LOCAL',
      QA_ADMIN_EMAIL:'admin@local.test',QA_ADMIN_PASSWORD:'LOCAL'};
    const args=['--operacion','evaluar','--version','1','--intento','1','--run-id',runId,'--autorizacion',ref,'--contexto',contexto];
    const x=await principal(args,{proceso,archivoEnv:path.join(temp,'inexistente'),ensayo:true,
      sinNewman:nombre==='conforme_sin_newman'});
    const r=x.resultado;assert.equal(x.preflight.ok,true);
    assert.ok(r,JSON.stringify(x.preflight));
    assert.equal(fs.readdirSync(dir).filter(x=>x.endsWith('.md')).length,1);
    const persistido=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json'),'utf8'));
    assert.equal(persistido.run_id,runId);
    assert.deepEqual(Object.keys(persistido.casos).sort(),['TC-M06-014','TC-M06-015']);
    assert.equal(fs.readFileSync(path.join(dir,'TC-M06-G38_resultado.md'),'utf8').includes(runId),true);
    if(r.herramientas.newman?.codigo===0){
      for(const archivo of ['newman-G38.json','newman-G38.html']){
        const texto=fs.readFileSync(path.join(dir,'newman',archivo),'utf8');
        assert.ok(!texto.includes('contador-local')&&!texto.includes('admin-local')&&!texto.includes('LOCAL'));
      }
    }
    const esperado={conforme:['APROBADO','APROBADO',true],conforme_sin_newman:['APROBADO','APROBADO',false],
      pm_redondeada:['RECHAZADO','RECHAZADO',true],
      matriz_sin_par:['BLOQUEADO','NO_CONCLUYENTE',false],id_duplicado:['APROBADO','RECHAZADO',true],
      seleccion:['NO_CONCLUYENTE','NO_CONCLUYENTE',false],seleccion_500:['NO_CONCLUYENTE','NO_CONCLUYENTE',false],
      permisos:['NO_CONCLUYENTE','NO_CONCLUYENTE',false],lecturas_previas:['NO_CONCLUYENTE','NO_CONCLUYENTE',false],
      rebase:['APROBADO','APROBADO',true],rebase_no_discriminante:['APROBADO','NO_CONCLUYENTE',false],
      precio:['NO_CONCLUYENTE','NO_CONCLUYENTE',false],
      pesaje:['NO_CONCLUYENTE','NO_CONCLUYENTE',false],procesar:['NO_CONCLUYENTE','NO_CONCLUYENTE',false],
      lecturas_posteriores:['NO_CONCLUYENTE','NO_CONCLUYENTE',false],
      linea_faltante:['RECHAZADO','APROBADO',true],pendiente_cuenta:['RECHAZADO','RECHAZADO',true],
      cuentas_iguales:['RECHAZADO','RECHAZADO',true],componente_no_discriminante:['APROBADO','NO_CONCLUYENTE',false],
      id_cambiado:['APROBADO','RECHAZADO',true],cierre:['APROBADO','APROBADO',false],
      newman:['APROBADO','APROBADO',false]}[nombre];
    assert.deepEqual([r.casos['TC-M06-014'].estado,r.casos['TC-M06-015'].estado,r.oficial],esperado,
      `${nombre}: ${JSON.stringify(r.problemas_tecnicos)}`);
    if(nombre==='matriz_sin_par')assert.equal(escrituras,0);
    assert.equal(solapamientos,0);assert.equal(activas,0);
    assert.equal(deleteHttp,nombre==='cierre'?500:200);
    assert.ok(peticiones<=140,`Solicitudes reales ${peticiones}/150`);
    console.log(`OK ${fila?'escenario_fila':'escenario'}_${nombre}: 014=${r.casos['TC-M06-014'].estado} 015=${r.casos['TC-M06-015'].estado} oficial=${r.oficial?'sí':'no'} solicitudes=${peticiones}/150`);
    if(nombre==='conforme'||nombre==='conforme_sin_newman')console.log(`OK flujo_completo_serie: ${peticiones} peticiones (ejecutor ${peticiones-newmanPeticiones}, Newman ${newmanPeticiones}), ${solapamientos} solapamientos, DELETE ${deleteHttp}`);
    if(nombre==='conforme'&&!r.oficial)console.log(JSON.stringify({newman:r.herramientas.newman,problemas:r.problemas_tecnicos,cierre:r.cierre}));
  }finally{
    await new Promise(r=>servidor.close(r));
    if(!path.resolve(temp).startsWith(path.resolve(os.tmpdir())+path.sep))throw Error('Limpieza fuera de temp');
    fs.rmSync(temp,{recursive:true,force:true});
  }
}
const filtro=process.argv.includes('--escenario')?process.argv[process.argv.indexOf('--escenario')+1]:null;
for(const nombre of ['conforme','conforme_sin_newman','pm_redondeada','matriz_sin_par','id_duplicado'])
  if(!filtro||filtro===nombre)await escenario(nombre);
for(const nombre of ['seleccion','seleccion_500','permisos','lecturas_previas','rebase','precio','pesaje',
  'procesar','lecturas_posteriores','linea_faltante','pendiente_cuenta','cuentas_iguales',
  'pm_redondeada','componente_no_discriminante','rebase_no_discriminante','id_cambiado','cierre','newman'])
  if(!filtro||filtro===nombre)await escenario(nombre,true);
