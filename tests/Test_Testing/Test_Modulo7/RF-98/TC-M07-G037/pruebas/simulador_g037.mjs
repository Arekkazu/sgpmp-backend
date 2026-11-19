// Doble local. Rutas: m07_router.py:181-184,211-237; configuracion_global_router.py:79-102;
// DTO: m07_dto.py:95-106; dominio: contrato.py:78-84; use case: gestionar_contratos_use_case.py:70-78.
import http from 'node:http';
const error=(field)=>({error_code:'VAL_ENTRADA',message:'Entrada inválida',fields:[{field,message:'Input should match pattern'}],timestamp:new Date().toISOString()});
const contrato=(id,v,s,g=null)=>({id_version_contrato_aaef:id,contrato_version:v,tipo_cambio:'MAJOR',fecha_vigencia:'2027-12-22',id_mapeo_anexo_aaef:2,mapeadores:['COMPRAS'],endpoint_asociado:'/integracion/aaef/productores/{nit}',periodo_gracia_dias:g,descripcion:null,estado:s,fecha_activacion:null,fecha_deprecacion:null,fecha_inactivacion:null});
export async function simuladorG037(op={}){
  const runId='RUN-G037-V1-20261117-000000';
  const base=[contrato(1,'1.0','INACTIVO'),contrato(2,'2.0','DEPRECADO'),contrato(3,'2.1',op.sinActivo?'INACTIVO':'ACTIVO'),contrato(4,'2.2','PENDIENTE')];
  let contratos=structuredClone(base),siguiente=5;
  const anexos=[{id_mapeo_anexo_aaef:1,estado:'OBSOLETO'},{id_mapeo_anexo_aaef:2,estado:'APROBADO'},{id_mapeo_anexo_aaef:3,estado:'EN_REVISION'}];
  const permisos=[1,2,3].map(id_accion=>({nombre_recurso:'contratos_aaef',id_accion}));
  if(!op.sinPermisoM09)permisos.push({nombre_recurso:'configuraciones_globales',id_accion:2});
  const peticiones=[];
  const server=http.createServer(async(req,res)=>{
    const u=new URL(req.url,'http://127.0.0.1'),p=u.pathname.replace(/^\/api-sgpmp-test/,'');
    const run=req.headers['x-test-run-id'];peticiones.push({metodo:req.method,ruta:p,run:!!run});
    const enviar=(status,body)=>{res.writeHead(status,{'Content-Type':'application/json',...(run?{'X-Test-Run-Id':run}:{})});res.end(JSON.stringify(op.inyectar&&body&&typeof body==='object'&&status<400?Array.isArray(body)?body.map(x=>({...x,campo_extra:'local'})):{...body,campo_extra:'local'}:body));};
    if(req.method==='POST'&&p==='/sesiones/'){enviar(200,{token:'local-token'});return;}
    if(req.method==='GET'&&p==='/sesiones/me/permisos'){enviar(200,{permisos:op.sinPermisos?[]:permisos});return;}
    if(req.method==='GET'&&p==='/integracion/anexos'){enviar(200,anexos);return;}
    if(req.method==='GET'&&p==='/integracion/contratos'){enviar(200,op.barajar?[...contratos].reverse():contratos);return;}
    if(req.method==='GET'&&p==='/configuracion/parametros'){enviar(200,op.m09ExponeGracia?{id_configuracion_global:1,frecuencia_muestreo:5,heartbeat:10,fecha_actualizacion:new Date().toISOString(),id_usuario:1,nombre_usuario:op.nombreUsuario??null,es_activo:true,umbral_sin_senal:10,periodo_gracia_dias:90}:{id_configuracion_global:1,frecuencia_muestreo:5,heartbeat:10,fecha_actualizacion:new Date().toISOString(),id_usuario:1,nombre_usuario:op.nombreUsuario??null,es_activo:true,umbral_sin_senal:10});return;}
    if(req.method==='DELETE'&&p.startsWith('/test-control/runs/')){if(!op.rollbackFallido)contratos=structuredClone(base);enviar(200,{message:'cerrado'});return;}
    let b={};if(req.method==='POST'){let raw='';for await(const c of req)raw+=c;b=JSON.parse(raw||'{}');}
    if(req.method==='POST'&&p==='/integracion/contratos'){
      if(!/^\d{1,3}\.\d{1,3}$/.test(b.contrato_version)&&!op.formatoAceptado){enviar(400,error('contrato_version'));return;}
      if(b.periodo_gracia_dias!==undefined&&b.periodo_gracia_dias<30&&!op.gracia29Aceptada){enviar(400,error('periodo_gracia_dias'));return;}
      if(contratos.some(x=>x.contrato_version===b.contrato_version)){enviar(409,error('contrato_version'));return;}
      const v={...contrato(siguiente++,b.contrato_version,'PENDIENTE',b.periodo_gracia_dias??90),fecha_vigencia:b.fecha_vigencia,id_mapeo_anexo_aaef:b.id_mapeo_anexo_aaef};contratos.push(v);enviar(201,v);return;
    }
    const m=p.match(/^\/integracion\/contratos\/(\d+)\/deprecar$/);
    if(req.method==='POST'&&m){const v=contratos.find(x=>x.id_version_contrato_aaef===Number(m[1]));if(!v||v.estado!=='ACTIVO'){enviar(422,error('estado'));return;}if(b.dias_gracia<30&&!op.deprecar29Aceptado){enviar(400,error('dias_gracia'));return;}const fecha=new Date('2026-11-18T12:00:00.000Z');v.estado='DEPRECADO';v.fecha_deprecacion=fecha.toISOString();v.fecha_inactivacion=new Date(fecha.getTime()+(op.inactivacionIncorrecta?29:b.dias_gracia)*86400000).toISOString();enviar(200,v);return;}
    enviar(404,error('ruta'));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return{api:`http://127.0.0.1:${server.address().port}/api-sgpmp-test`,runId,peticiones,cerrar:()=>new Promise(resolve=>server.close(resolve))};
}
