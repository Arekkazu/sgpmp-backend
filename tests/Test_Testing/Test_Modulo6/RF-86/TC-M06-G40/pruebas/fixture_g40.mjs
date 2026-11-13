import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {CASOS,CONTRATO,mock} from '../lib/g40_core.mjs';
import {principal} from '../g40.mjs';

const clone=x=>structuredClone(x);
export async function escenario(nombre,opciones={}){
  const state={stage:'base',requests:0,overlaps:0,busy:false,deleteHttp:null,postBody:null,
    pesajeBody:null,asignacionDesactivada:null,writes:0};
  const avisosPrevios=opciones.avisosPrevios??[];
  const sentido=opciones.sentido??(opciones.modoAuto&&avisosPrevios.includes('GANANCIA')?'PERDIDA':'GANANCIA');
  const previos=avisosPrevios.map((s,i)=>({id_notificacion:12796+i,fecha_envio:'2026-11-12T15:48:19Z',
    mensaje:`Falta la cuenta contable de Variación por transformación biológica (${s.toLowerCase()}) para Bovino. El registro quedó pendiente de cuenta.`}));
  const active={id_asignacion_cuenta_contable:12,tipo_hecho:'VARIACION_VR_TB',sentido,
    id_especie:null,subtipo_costo:null,cuenta_debito:'158405',cuenta_credito:'424805'};
  const line=mock('lineas')[0];Object.assign(line,{id_linea_asiento_nic41:500,tipo_hecho:'VARIACION_VR_TB',sentido,
    estado:'PENDIENTE_CUENTA',id_periodo_contable:241,id_activo_biologico:1833,id_especie:39,id_origen:241,
    cuenta_debito:null,cuenta_credito:null,subtipo_costo:null});
  const preexistente={...clone(line),id_linea_asiento_nic41:400,id_origen:240};
  const variation=mock('variaciones')[0];Object.assign(variation,{id_variacion_valor_razonable:241,id_activo_biologico:1833,
    tipo:`${sentido}_TRANSFORMACION_BIOLOGICA`});
  const alert={id_notificacion:2,fecha_envio:'2026-11-09T09:00:00Z',
    mensaje:opciones.alertaTexto??`Falta la cuenta contable de Variación por transformación biológica (${sentido.toLowerCase()}) para Bovino. El registro quedó pendiente de cuenta.`};
  const audit={id_evento:2,tipo_evento:'LINEA_ASIENTO_PENDIENTE_CUENTA',payload_evento:{tipo_hecho:'VARIACION_VR_TB',sentido,id_especie:39}};
  const allPerm=actor=>[...new Set(CONTRATO.peticiones.filter(x=>x.actor===actor&&x.permiso!=='autenticado:0').map(x=>x.permiso))]
    .filter(x=>!(opciones.permisosFail&&actor==='contador'&&x==='configuracion_contable:1'))
    .map(x=>{const [nombre_recurso,id_accion]=x.split(':');return{nombre_recurso,id_accion:Number(id_accion)}});
  const server=http.createServer(async(req,res)=>{
    if(state.busy){state.overlaps++;res.writeHead(429).end();return;}state.busy=true;state.requests++;
    try{let body='';for await(const chunk of req)body+=chunk;const url=new URL(req.url,'http://localhost');
      const p=url.pathname.replace(/^\/api-sgpmp-test/,'');let status=200,data=null;
      res.setHeader('x-test-run-id',req.headers['x-test-run-id']??'');res.setHeader('content-type','application/json');
      if(p==='/sesiones/'&&req.method==='POST')data={token:body.includes('admin@')?'admin-token':'contador-token'};
      else if(p==='/sesiones/me/permisos')data={permisos:allPerm(req.headers.authorization?.includes('admin-token')?'admin':'contador')};
      else if(p==='/finanzas/activos'){data=opciones.sinCandidato?[]:mock('activos');if(data.length)Object.assign(data[0],{id_activo_biologico:1833,id_especie:39,
        especie:'Bovino',tipo:'INDIVIDUAL',estado:'ACTIVO'});}
      else if(p==='/finanzas/periodos'){data=mock('periodos');Object.assign(data[0],{id_periodo_contable:241,
        numero_id_tributaria:'NIT-D',fecha_inicio:'2026-01-01',fecha_fin:'2026-12-31',estado:'ABIERTO'});}
      else if(p==='/finanzas/activos/1833'){data=mock('activo_detalle');data.activo.numero_id_tributaria='NIT-D';
        data.calculos[0].estado='CALCULADO';}
      else if(p==='/activos-biologicos/1833/ficha-integral'){data=mock('ficha');Object.assign(data,{peso_actual:'100.00',
        unidad_peso:'kg',estado_actual:'ACTIVO'});}
      else if(p==='/finanzas/precios'){data=mock('precios_get');Object.assign(data[0],{id_especie:39,categoria:'PESO_KG',
        fuente:'MERCADO_ACTIVO',fecha_vigencia:'2026-01-01',fecha_vencimiento:null});}
      else if(p==='/finanzas/configuracion'&&req.method==='GET'){data=mock('configuracion');
        data.matriz=state.stage==='base'&&!opciones.matrizSinPar?[active]:state.stage==='resolved'?[{...active,id_asignacion_cuenta_contable:13,id_especie:39}]:[];
        data.lineas_pendientes_cuenta=state.stage==='processed'?(opciones.pendientePreexistente?2:1):
          state.stage==='resolved'?(opciones.conteoFinalAlto?2:0):(opciones.pendientePreexistente?1:0);}
      else if(p==='/finanzas/lineas'){data=opciones.pendientePreexistente?[clone(preexistente)]:[];
        if(['processed','resolved'].includes(state.stage)&&!opciones.lineaAusente)data.push(clone(line));
        if(state.stage==='resolved')for(const row of data){
          if(row.id_linea_asiento_nic41!==500||!opciones.lineaNoRegistra)
            Object.assign(row,{estado:'REGISTRADA',cuenta_debito:'158405',cuenta_credito:'424805'});
          if(row.id_linea_asiento_nic41===500&&opciones.cuentasDistintas)row.cuenta_debito='999999';}
        if(opciones.lineaRegistrada&&state.stage==='processed')Object.assign(data.at(-1),{estado:'REGISTRADA',cuenta_debito:'158405',cuenta_credito:'424805'});
        if(url.searchParams.get('estado'))data=data.filter(x=>x.estado===url.searchParams.get('estado'));}
      else if(p==='/finanzas/periodos/241/variaciones')data=['processed','resolved'].includes(state.stage)?[variation]:[];
      else if(p==='/notificaciones'){const items=[...previos,...((state.stage==='processed'||opciones.alertaVieja)&&opciones.alerta!==false?[alert]:[])];
        if(opciones.newmanFail&&String(req.headers['user-agent']??'').includes('PostmanRuntime')){status=500;data={code:'LOCAL_NEWMAN_FAIL'};}
        else data={items,total:items.length};}
      else if(p==='/finanzas/auditoria'){const eventos=state.stage==='processed'?[audit]:[];
        data={eventos,total_registros:eventos.length};}
      else if(p==='/finanzas/configuracion/matriz/12'&&req.method==='DELETE'){state.writes++;
        if(opciones.deleteFail){status=404;data={code:'ASIGNACION_NO_ENCONTRADA'};}
        else{state.asignacionDesactivada={id:active.id_asignacion_cuenta_contable,
          tipo_hecho:active.tipo_hecho,sentido:active.sentido,id_especie:active.id_especie};
          state.stage='deactivated';status=204;data=null;}}
      else if(p==='/activos-biologicos/1833/eventos/crecimiento'&&req.method==='POST'){state.writes++;
        state.pesajeBody=JSON.parse(body);
        if(opciones.pesajeFail){status=422;data={code:'PESAJE_INVALIDO'};}else{status=201;data=mock('evento_crecimiento');}}
      else if(p==='/finanzas/eventos/procesar'&&req.method==='POST'){state.writes++;
        if(opciones.procesarFail){status=500;data={code:'ERROR'};}else{state.stage='processed';data=mock('procesar');}}
      else if(p==='/finanzas/configuracion/matriz'&&req.method==='POST'){state.writes++;state.postBody=JSON.parse(body);
        state.stage='resolved';status=201;data={id_asignacion_cuenta_contable:13,
          lineas_resueltas:opciones.postSinResueltas?0:opciones.pendientePreexistente?2:1};}
      else if(p.startsWith('/test-control/runs/')&&req.method==='DELETE'){
        state.deleteHttp=opciones.closeFail?500:200;if(!opciones.matrizNoRestaurada&&!opciones.closeFail)state.stage='base';status=state.deleteHttp;data={deleted:!opciones.closeFail};}
      else{status=404;data={code:'SIN_FIXTURE',ruta:p};}
      res.writeHead(status).end(status===204?'':JSON.stringify(data));
    }finally{state.busy=false;}});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const port=server.address().port,api=`http://127.0.0.1:${port}`;
  const version=opciones.version??2,operacion=opciones.operacion??'reevaluar';
  const runId=`RUN-G40-V${version}-20261112-120000`,tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g40-ensayo-')),
    dir=path.join(tmp,runId),context=path.join(dir,'contexto_operacion.json');fs.mkdirSync(dir);
  fs.writeFileSync(context,JSON.stringify({grupo:'G40',run_id:runId,version,intento:1,operacion:operacion.toUpperCase(),
    referencia:'AUT-LOCAL',casos:CASOS,version_anterior:1,alcance_reevaluacion:{casos:CASOS,motivo:'INC-M06-G40-01'},
    ...(opciones.modoAuto?{}:{sentido})}));
  const env={QA_AUTORIZADO:'SI',SIGAB_API_TEST_BASE:api,QA_SANDBOX_SECRET:'secreto-local-simulado',
    QA_CONTADOR_EMAIL:'contador@local.invalid',QA_CONTADOR_PASSWORD:'local',
    QA_ADMIN_EMAIL:'admin@local.invalid',QA_ADMIN_PASSWORD:'local'};
  const doble=async({dir,expected})=>{fs.mkdirSync(dir,{recursive:true});const acta={panel_visible:opciones.panel!==false,
    conteo:opciones.conteoDistinto?expected.conteo+1:expected.conteo,
    campana_visible:opciones.alerta!==false&&!opciones.alertaVieja&&
      !/otra especie|pérdida ajena|ganancia ajena/i.test(opciones.alertaTexto??''),captura:true};
    fs.writeFileSync(path.join(dir,'G40-UI-018-01.json'),JSON.stringify(acta));
    fs.writeFileSync(path.join(dir,'G40-cypress.json'),JSON.stringify({totalTests:1,totalPassed:opciones.cypressFail?0:1,totalFailed:opciones.cypressFail?1:0}));
    return{codigo:opciones.cypressFail?2:0,acta};};
  let result;try{result=await principal(['--operacion',operacion,'--version',String(version),'--intento','1','--run-id',runId,
    '--autorizacion','AUT-LOCAL','--contexto',context,...(opciones.modoAuto?[]:['--sentido',sentido])],
    {proceso:env,archivoEnv:path.join(tmp,'inexistente'),
    ensayo:true,cypressDoble:doble});
    const report=fs.readFileSync(path.join(dir,`TC-M06-G40_reevaluacion_V${version}.md`),'utf8');
    const json=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json'),'utf8'));
    if(opciones.copiarEjemplo){fs.mkdirSync(opciones.copiarEjemplo,{recursive:true});
      fs.cpSync(dir,path.join(opciones.copiarEjemplo,runId),{recursive:true});}
    return{...result,informe:report,requests:state.requests,writes:state.writes,deleteHttp:state.deleteHttp,
      overlaps:state.overlaps,postBody:state.postBody,pesajeBody:state.pesajeBody,
      asignacionDesactivada:state.asignacionDesactivada,
      files:fs.readdirSync(dir),reports:fs.existsSync(path.join(dir,'newman'))?fs.readdirSync(path.join(dir,'newman')):[],
      informeCoherente:report.includes(json.run_id)&&report.includes(json.casos['TC-M06-018'].estado),
      evidenciasPresentes:json.evidencias.every(x=>fs.existsSync(path.join(dir,x))),
      sinSecretos:!report.includes(env.QA_SANDBOX_SECRET)&&!JSON.stringify(json).includes(env.QA_SANDBOX_SECRET)};}
  finally{server.close();fs.rmSync(tmp,{recursive:true,force:true});}}
