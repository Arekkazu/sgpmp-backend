// Simulador HTTP local estricto. Estado del RUN aislado de las lecturas públicas.
import http from 'node:http';
import {validarSolicitud} from '../lib/contrato.mjs';

const error=(code='VAL_ENTRADA',field=null)=>({error_code:code,message:'Entrada inválida',fields:[{field,message:'Valor inválido'}],timestamp:new Date().toISOString()});
const contrato=(id,v,s,g=null)=>({id_version_contrato_aaef:id,contrato_version:v,tipo_cambio:'MAJOR',fecha_vigencia:'2027-12-22',id_mapeo_anexo_aaef:7,mapeadores:['COMPRAS'],endpoint_asociado:'/integracion/aaef/productores/{nit}',periodo_gracia_dias:g,descripcion:null,estado:s,fecha_activacion:null,fecha_deprecacion:null,fecha_inactivacion:null});
const parametros=(g,usuario)=>[
  ['aaef_gracia_minima_dias',g.min,30],['aaef_gracia_defecto_dias',g.def,90]
].map(([nombre,valor,base])=>({nombre,descripcion:'Período de gracia AAEF',valor:g.configurado?String(valor):base,valor_configurado:g.configurado?String(valor):null,valor_base:base,fuente:g.configurado?'CONFIGURADO':'VALOR_BASE',rango_minimo:'1',rango_maximo:'3650',nombre_usuario:usuario??null,nombre_cliente:usuario??null,correo_usuario:usuario?'usuario@local.invalid':null}));
export async function simuladorG037(op={}){
  const runId=op.runId??'RUN-G037-V3-20261118-000000';
  const original=[contrato(1,'1.0','INACTIVO'),contrato(2,'2.1','DEPRECADO'),contrato(3,'3.0',op.sinActivo?'INACTIVO':'ACTIVO'),contrato(4,'4.0','PENDIENTE')];
  const base={contratos:structuredClone(original),gracia:{min:op.minInicial??30,def:op.defInicial??90,configurado:false},siguiente:5,eventos:[]};
  const run=structuredClone(base),peticiones=[];
  const permisos=[1,2,3].filter(a=>a!==1||!op.sinPermisoCrear).filter(a=>a!==3||!op.sinPermisoDeprecar).map(id_accion=>({nombre_recurso:'contratos_aaef',id_accion}));
  if(!op.sinPermisos&&!op.sinPermisoR)permisos.push({nombre_recurso:'configuraciones_globales',id_accion:2});
  if(!op.sinPermisos&&!op.sinPermisoU)permisos.push({nombre_recurso:'configuraciones_globales',id_accion:3});
  if(!op.sinPermisos)permisos.push({nombre_recurso:'auditoria_integracion',id_accion:2});
  const server=http.createServer(async(req,res)=>{
    const u=new URL(req.url,'http://127.0.0.1'),p=u.pathname.replace(/^\/api-sgpmp-test/,'');
    const enRun=req.headers['x-test-run-id']===runId,estado=enRun?run:base;
    peticiones.push({metodo:req.method,ruta:p,run:enRun});
    const enviar=(status,body)=>{res.writeHead(status,{'Content-Type':'application/json',...(enRun?{'X-Test-Run-Id':runId}:{})});res.end(JSON.stringify(body));};
    if(req.method==='POST'&&p==='/sesiones/'){
      let b;try{b=JSON.parse(await leer(req));validarSolicitud('POST',p,b);}catch{enviar(400,error());return;}
      enviar(op.loginInvalido?401:200,op.loginInvalido?error('CREDENCIALES_INVALIDAS'):{token:'local-token'});return;
    }
    if(!enRun&&req.method!=='DELETE'&&p!=='/integracion/contratos'&&p!=='/configuracion/parametros-integracion-contable'){
      enviar(403,error('SIN_RUN'));return;
    }
    if(req.method==='GET'&&p==='/sesiones/me/permisos'){enviar(200,{permisos:op.sinPermisos?[]:permisos});return;}
    if(req.method==='GET'&&p==='/integracion/anexos'){enviar(200,op.sinAnexo?[]:[{id_mapeo_anexo_aaef:7,estado:'APROBADO'}]);return;}
    if(req.method==='GET'&&p==='/integracion/contratos'){enviar(200,structuredClone(op.barajar?[...estado.contratos].reverse():estado.contratos));return;}
    if(req.method==='GET'&&p==='/integracion/auditoria'){enviar(200,{items:structuredClone(estado.eventos).reverse(),pagina:1,tamano:100,total:estado.eventos.length});return;}
    if(p==='/configuracion/parametros-integracion-contable'){
      if(op.m09SinRuta){enviar(404,error('RUTA_NO_ENCONTRADA'));return;}
      if(req.method==='GET'){
        if(op.sinPermisoR){enviar(403,error('SIN_PERMISO'));return;}
        enviar(200,parametros(estado.gracia,op.nombreUsuario));return;
      }
      if(req.method==='PATCH'){
        if(op.sinPermisoU){enviar(403,error('SIN_PERMISO'));return;}
        let b;try{b=JSON.parse(await leer(req));validarSolicitud('PATCH',p,b);}catch{enviar(400,error('VAL_ENTRADA','parametros'));return;}
        const cambios=b.parametros,keys=Object.keys(cambios);
        const minimo=cambios.aaef_gracia_minima_dias??estado.gracia.min;
        const defecto=cambios.aaef_gracia_defecto_dias??estado.gracia.def;
        if(!keys.length||keys.some(k=>!['aaef_gracia_minima_dias','aaef_gracia_defecto_dias'].includes(k))||[minimo,defecto].some(v=>!Number.isInteger(v)||v<1||v>3650)||defecto<minimo){
          if(op.patchInvalidoAceptado){enviar(200,parametros(estado.gracia,op.nombreUsuario));return;}
          if(op.patchInvalidoCambiaGracia)estado.gracia={...estado.gracia,def:minimo};
          if(op.patchInvalido422){enviar(422,error('VALIDACION_INESPERADA','parametros'));return;}
          if(op.patchInvalidoCodigoGenerico){enviar(400,{error_code:'PARAMETRO_MLOPS_INVALIDO',message:'El período de gracia por defecto no puede ser menor que el mínimo.',field:null,fields:[]});return;}
          enviar(400,error('PARAMETRO_INTEGRACION_CONTABLE_INVALIDO','parametros'));return;
        }
        estado.gracia={min:minimo,def:defecto,configurado:true};
        enviar(200,parametros(estado.gracia,op.nombreUsuario));return;
      }
    }
    if(req.method==='DELETE'&&p===`/test-control/runs/${runId}`){
      if(op.deleteHttp){enviar(op.deleteHttp,error('CIERRE_NO_CONFIRMADO'));return;}
      if(op.rollbackFallido){base.contratos=structuredClone(run.contratos);base.gracia=structuredClone(run.gracia);}
      enviar(200,{message:'cerrado'});return;
    }
    if(req.method==='POST'&&p==='/integracion/contratos'){
      let b;try{b=JSON.parse(await leer(req));validarSolicitud('POST',p,b);}catch{enviar(400,error('VAL_ENTRADA'));return;}
      if(!/^\d{1,3}\.\d{1,3}$/.test(b.contrato_version)&&!op.formatoAceptado){enviar(400,error('VAL_ENTRADA','contrato_version'));return;}
      if(b.id_mapeo_anexo_aaef!==7||b.tipo_cambio!=='MAJOR'||b.mapeadores.length!==1||b.mapeadores[0]!=='COMPRAS'){enviar(400,error('VAL_ENTRADA'));return;}
      const g=op.graciaFija?base.gracia:estado.gracia;
      if(b.periodo_gracia_dias!==undefined&&b.periodo_gracia_dias<g.min){enviar(400,error('PERIODO_GRACIA_INVALIDO','periodo_gracia_dias'));return;}
      if(estado.contratos.some(x=>x.contrato_version===b.contrato_version)){enviar(409,error('VERSION_DUPLICADA','contrato_version'));return;}
      const v={...contrato(estado.siguiente++,b.contrato_version,'PENDIENTE',b.periodo_gracia_dias??g.def),fecha_vigencia:b.fecha_vigencia,id_mapeo_anexo_aaef:b.id_mapeo_anexo_aaef};
      estado.contratos.push(v);estado.eventos.push({id_evento_integracion:`EV-${estado.eventos.length+1}`,tipo_evento:'CONTRATO_REGISTRADO',version_contrato:v.contrato_version,fecha_evento:new Date().toISOString()});enviar(201,v);return;
    }
    const m=p.match(/^\/integracion\/contratos\/(\d+)\/deprecar$/);
    if(req.method==='POST'&&m){
      let b;try{b=JSON.parse(await leer(req));validarSolicitud('POST',p,b);}catch{enviar(400,error('VAL_ENTRADA'));return;}
      const v=estado.contratos.find(x=>x.id_version_contrato_aaef===Number(m[1]));
      if(!v||v.estado!=='ACTIVO'){enviar(422,error('ESTADO_INVALIDO'));return;}
      const g=estado.gracia;
      if(b.dias_gracia<g.min){enviar(400,error('PERIODO_GRACIA_INVALIDO','dias_gracia'));return;}
      const fecha=new Date('2026-11-18T12:00:00.000Z');
      v.estado='DEPRECADO';v.fecha_deprecacion=fecha.toISOString();
      v.fecha_inactivacion=new Date(fecha.getTime()+(op.fechasMal?b.dias_gracia-1:b.dias_gracia)*86400000).toISOString();
      estado.eventos.push({id_evento_integracion:`EV-${estado.eventos.length+1}`,tipo_evento:'CONTRATO_DEPRECADO',version_contrato:v.contrato_version,fecha_evento:fecha.toISOString()});
      enviar(200,v);return;
    }
    enviar(404,error('RUTA_NO_ENCONTRADA'));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return{api:`http://127.0.0.1:${server.address().port}/api-sgpmp-test`,runId,peticiones,cerrar:()=>new Promise(resolve=>server.close(resolve))};
}
async function leer(req){let raw='';for await(const c of req)raw+=c;return raw;}
