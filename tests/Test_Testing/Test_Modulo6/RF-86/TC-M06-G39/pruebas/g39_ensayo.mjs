import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {randomInt} from 'node:crypto';
import {mock,CONTRATO} from '../lib/g39_core.mjs';
import {principal} from '../g39.mjs';

const g37=JSON.parse(fs.readFileSync(new URL('../../TC-M06-G37/Resultados/RUN-G37-V1-20261108-233956/resultado.json',import.meta.url),'utf8'));
const g38=JSON.parse(fs.readFileSync(new URL('../../TC-M06-G38/Resultados/RUN-G38-V1-20261109-025651/resultado.json',import.meta.url),'utf8'));
assert.equal(g37.observaciones.candidatos.length,16);
assert.equal(g38.casos['TC-M06-014'].estado,'APROBADO');
assert.equal(g37.solicitudes.filter(x=>x.id==='precios_get').length,5);
assert.equal(g38.solicitudes.find(x=>x.id==='configuracion')?.contrato,'coincide');
assert.equal(g38.solicitudes.find(x=>x.id==='lineas')?.contrato,'coincide');
assert.equal(g38.solicitudes.find(x=>x.id==='procesar')?.http,200);
assert.equal(typeof g38.casos['TC-M06-014'].observado.lineas[0].valor,'string');
assert.equal(g38.casos['TC-M06-014'].observado.lineas[0].estado,'REGISTRADA');
const ids=g37.observaciones.candidatos.map(x=>x.activo);
const fecha='2026-11-08';
function catalogo(){return ids.map((id,i)=>({...mock('activos')[0],id_activo_biologico:id,
  id_especie:i<5?39:[40,41,42,43][(i-5)%4],especie:i<5?'Bovino':'Caprino',
  tipo:i>=14?'LOTE':'INDIVIDUAL',estado:i===4?'BAJA':'ACTIVO',valorado_por_costo:false,
  valor_contable_por_costo:null,valor_razonable_neto:'1000.9999'}));}
const matriz=[['MANO_OBRA_PROPIA','UNICO','158405','250505'],['CONSUMO_INSUMO','UNICO','158405','220505'],
  ['BAJA_ACTIVO','UNICO','613505','158405'],['BAJA_ACTIVO','PERDIDA','539510','158405']]
  .map(([tipo_hecho,sentido,cuenta_debito,cuenta_credito],i)=>({id_asignacion_cuenta_contable:i+1,
    tipo_hecho,sentido,id_especie:null,subtipo_costo:null,cuenta_debito,cuenta_credito}));
function linea(id,aid,origen,tipo,sentido,valor,debito,credito,tabla){return {...mock('lineas')[0],
  id_linea_asiento_nic41:id,id_activo_biologico:aid,id_especie:39,id_periodo_contable:8,
  id_origen:origen,tabla_origen:tabla,tipo_hecho:tipo,sentido,valor,cuenta_debito:debito,cuenta_credito:credito,
  estado:'REGISTRADA',fecha_hecho:fecha};}
export async function escenario(nombre){
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'g39-ensayo-'));
  const runId=`RUN-G39-V1-20261108-${String(randomInt(1000000)).padStart(6,'0')}`;
  const dir=path.join(temp,runId);fs.mkdirSync(dir);
  const ctx=path.join(dir,'contexto_operacion.json'),ref='AUT-G39-ENSAYO';
  fs.writeFileSync(ctx,JSON.stringify({grupo:'G39',run_id:runId,version:1,intento:1,operacion:'EVALUAR',
    referencia:ref,casos:['TC-M06-016','TC-M06-017']}));
  let activos=catalogo(),costos=[],lineas=[],eventos=[],proximoCosto=100,proximaLinea=900,proximoEvento=500,
    activas=0,solapamientos=0,peticiones=0,newmanPeticiones=0,escrituras=0,deleteHttp=null;
  if(nombre==='seleccion')activos=[];
  const server=http.createServer(async(req,res)=>{
    assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'preflight.json'),'utf8')).ok,true);
    const run=req.headers['x-test-run-id']===runId;
    if(run&&activas){solapamientos++;res.writeHead(500,{'Content-Type':'application/json','X-Test-Run-Id':runId});res.end('{}');return;}
    if(run)activas++;peticiones++;if(req.headers['user-agent']?.includes('PostmanRuntime'))newmanPeticiones++;
    await new Promise(resolve=>setTimeout(resolve,15));
    const send=(http,body)=>{if(run)activas--;res.writeHead(http,{'Content-Type':'application/json','X-Test-Run-Id':runId});res.end(JSON.stringify(body));};
    const u=new URL(req.url,'http://localhost'),ruta=u.pathname;let body={};
    if(req.method==='POST'){let raw='';for await(const x of req)raw+=x;try{body=JSON.parse(raw);}catch{}}
    if(ruta==='/sesiones/'&&req.method==='POST')return send(200,{token:body.correo_electronico?.includes('admin')?'admin-local':'contador-local'});
    if(ruta==='/sesiones/me/permisos'){
      if(nombre==='permisos')return send(200,{permisos:[]});
      const rol=req.headers.authorization?.includes('admin-local')?'admin':'contador';
      return send(200,{permisos:Object.entries(CONTRATO.roles[rol].permisos).flatMap(([recurso,acciones],i)=>
        acciones.map(id_accion=>({id_recurso:i+1,id_accion,nombre_recurso:recurso})))});
    }
    if(ruta===`/test-control/runs/${runId}`&&req.method==='DELETE'){
      deleteHttp=nombre==='cierre'?500:200;if(deleteHttp===200){costos=[];lineas=[];eventos=[];}
      return send(deleteHttp,{ok:deleteHttp===200});}
    if(ruta==='/finanzas/activos')return send(200,activos);
    if(ruta==='/finanzas/periodos')return send(200,[{id_periodo_contable:8,numero_id_tributaria:'900000001',
      fecha_inicio:'2020-01-01',fecha_fin:'2030-12-31',estado:'ABIERTO',ultimo_cierre:null}]);
    if(ruta==='/finanzas/precios')return send(200,[{id_precio_mercado:1,id_especie:Number(u.searchParams.get('id_especie')),
      categoria:'PESO_KG',fuente:'MERCADO_ACTIVO',precio_unitario:'1000.00',fecha_vigencia:'2020-01-01',fecha_vencimiento:null}]);
    if(/^\/finanzas\/activos\/\d+$/.test(ruta)){
      if(nombre==='detalle')return send(500,{});
      const d=mock('activo_detalle');d.activo.numero_id_tributaria='900000001';
      d.calculos[0].estado='CALCULADO';d.calculos[0].valor_neto='1000.9999';d.calculos[0].fecha_calculo=fecha;
      d.calculos[0].json_metodo_costo={};return send(200,d);}
    if(/^\/activos-biologicos\/\d+\/ficha-integral$/.test(ruta))return send(200,{peso_actual:'100.00',unidad_peso:'kg',estado_actual:'ACTIVO'});
    if(ruta==='/finanzas/configuracion'){
      const m=nombre==='matriz_sin_par'?matriz.filter(x=>x.tipo_hecho!=='CONSUMO_INSUMO'):
        nombre==='matriz_sin_perdida'?matriz.filter(x=>!(x.tipo_hecho==='BAJA_ACTIVO'&&x.sentido==='PERDIDA')):matriz;
      return send(200,{matriz:m,costos_venta:[]});}
    if(ruta==='/finanzas/lineas')return send(200,lineas);
    if(ruta==='/finanzas/costos'&&req.method==='GET')return send(200,costos.filter(x=>x.id_activo_biologico===Number(u.searchParams.get('id_activo_biologico'))));
    if(ruta==='/finanzas/costos'&&req.method==='POST'){
      const aid=body.id_activo_biologico;
      if(body.origen_costo==='CONSUMO_INVENTARIO'){
        if(nombre==='422_201')return send(201,{registros:[]});
        if(nombre==='422_otro')return send(422,{error_code:'OTRO_CODIGO'});
        if(nombre==='422_crea_costo')costos.push({id_registro_costo:++proximoCosto,id_activo_biologico:aid,
          origen_costo:'CONSUMO_INVENTARIO',vehiculo_contable:'NINGUNO',monto_costo:'123.45'});
        return send(422,{error_code:'ORIGEN_RESERVADO_M05'});
      }
      if(nombre==='factura_422'&&body.origen_costo==='COMPRA_PROVEEDOR')return send(422,{error_code:'CUENTA_NO_CONFIGURADA'});
      escrituras++;const id=++proximoCosto,mano=body.origen_costo==='MANO_OBRA_PROPIA';
      const registro={id_registro_costo:id,id_activo_biologico:aid,monto_costo:'123.45',naturaleza_costo:'MANTENIMIENTO',
        vehiculo_contable:mano?'ASIENTO_NIC41':'FACTURA_COMPRA',estado:'REGISTRADO',id_linea_asiento:null};
      costos.push({id_registro_costo:id,id_activo_biologico:aid,origen_costo:body.origen_costo,
        vehiculo_contable:registro.vehiculo_contable,monto_costo:'123.45'});
      if(mano&&nombre!=='mano_sin_linea'){
        const l=linea(++proximaLinea,aid,id,'MANO_OBRA_PROPIA','UNICO','123.45',
          nombre==='mano_cuenta'?'000000':'158405','250505','registros_costos');
        lineas.push(l);registro.id_linea_asiento=l.id_linea_asiento_nic41;
      }
      if(!mano&&nombre==='factura_linea')lineas.push(linea(++proximaLinea,aid,id,'CONSUMO_INSUMO','UNICO','123.45',
        '158405','220505','registros_costos'));
      return send(201,{registros:[registro],id_grupo_reparto:null,aviso:null});
    }
    if(/^\/activos-biologicos\/\d+\/eventos\/baja$/.test(ruta)&&req.method==='POST'){
      if(nombre==='baja_4xx')return send(422,{error_code:'BAJA_INVALIDA'});
      escrituras++;const aid=Number(ruta.split('/')[2]),id=++proximoEvento;
      eventos.push({id_eventos:id,id_activo_biologico:aid,tipo:body.tipo_baja});
      return send(201,{id_eventos:id,id_activo_biologico:aid});}
    if(/^\/activos-biologicos\/\d+\/eventos$/.test(ruta))return send(200,{eventos:eventos.filter(x=>x.id_activo_biologico===Number(ruta.split('/')[2]))});
    if(ruta==='/finanzas/eventos/procesar'&&req.method==='POST'){
      if(nombre==='procesar')return send(500,{error_code:'PROCESAR_ERROR'});
      for(const ev of eventos.filter(x=>!x.procesado)){
        ev.procesado=true;const venta=ev.tipo==='venta';
        if(nombre!=='baja_sin_linea')lineas.push(linea(++proximaLinea,ev.id_activo_biologico,ev.id_eventos,
          'BAJA_ACTIVO',nombre==='baja_sentido'?'GANANCIA':venta?'UNICO':'PERDIDA',
          nombre==='baja_valor'?'1001.00':'1000.99',venta?'613505':'539510','158405','procesamientos_eventos_m02'));
        if(venta&&nombre==='venta_ingreso')lineas.push(linea(++proximaLinea,ev.id_activo_biologico,ev.id_eventos,
          'INGRESO_VENTA','UNICO','1200.00','130505','413505','procesamientos_eventos_m02'));
      }return send(200,{eventos:[],provisiones_m05:[]});}
    return send(404,{error_code:'RUTA_NO_SIMULADA'});
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const api=`http://127.0.0.1:${server.address().port}`;
  let salida;try{salida=await principal(['--operacion','evaluar','--version','1','--intento','1','--run-id',runId,
    '--autorizacion',ref,'--contexto',ctx],{ensayo:true,proceso:{QA_AUTORIZADO:'SI',SIGAB_API_TEST_BASE:api,
      QA_SANDBOX_SECRET:'local-secret',QA_CONTADOR_EMAIL:'contador@local.test',QA_CONTADOR_PASSWORD:'local',
      QA_ADMIN_EMAIL:'admin@local.test',QA_ADMIN_PASSWORD:'local'}});}finally{await new Promise(resolve=>server.close(resolve));}
  const r=salida.resultado;assert.equal(solapamientos,0,`solapamientos ${nombre}`);
  assert.ok(peticiones<=150,`${nombre}: ${peticiones} solicitudes`);
  assert.equal(fs.readdirSync(dir).filter(x=>x.endsWith('.md')).length,1);
  assert.equal(r.run_id,runId);assert.equal(r.cierre.run.cierre_http,deleteHttp);
  const estados=['TC-M06-016','TC-M06-017'].map(x=>r.casos[x].estado);
  console.log(`OK escenario_${nombre}: 016=${estados[0]} 017=${estados[1]} oficial=${r.oficial?'sí':'no'} solicitudes=${peticiones}/150`);
  fs.rmSync(temp,{recursive:true,force:true});return{estados,oficial:r.oficial,peticiones,newmanPeticiones,escrituras,r};
}
for(const [nombre,esperados,oficial] of [
  ['conforme',['APROBADO','APROBADO'],true],['factura_linea',['RECHAZADO','APROBADO'],true],
  ['venta_ingreso',['APROBADO','RECHAZADO'],true],['matriz_sin_perdida',['APROBADO','BLOQUEADO'],false]]){
  const x=await escenario(nombre);assert.deepEqual(x.estados,esperados);assert.equal(x.oficial,oficial);
  assert.equal(x.newmanPeticiones,3,`Newman real ${nombre}`);
}
// Una variante por fila de la tabla de decisiones; todas atraviesan principal() y loopback.
for(const [nombre,esperados] of [
  ['seleccion',['BLOQUEADO','BLOQUEADO']],
  ['permisos',['NO_CONCLUYENTE','NO_CONCLUYENTE']],
  ['detalle',['NO_CONCLUYENTE','NO_CONCLUYENTE']],
  ['matriz_sin_par',['BLOQUEADO','APROBADO']],
  ['422_otro',['RECHAZADO','APROBADO']],
  ['422_201',['RECHAZADO','APROBADO']],
  ['422_crea_costo',['RECHAZADO','APROBADO']],
  ['mano_sin_linea',['RECHAZADO','APROBADO']],
  ['mano_cuenta',['RECHAZADO','APROBADO']],
  ['factura_422',['BLOQUEADO','APROBADO']],
  ['baja_4xx',['APROBADO','RECHAZADO']],
  ['procesar',['APROBADO','RECHAZADO']],
  ['baja_sin_linea',['APROBADO','RECHAZADO']],
  ['baja_valor',['APROBADO','RECHAZADO']],
  ['baja_sentido',['APROBADO','RECHAZADO']],
  ['cierre',['APROBADO','APROBADO']]]){
  const x=await escenario(nombre);assert.deepEqual(x.estados,esperados,nombre);
  if(nombre==='cierre')assert.equal(x.oficial,false);
}
