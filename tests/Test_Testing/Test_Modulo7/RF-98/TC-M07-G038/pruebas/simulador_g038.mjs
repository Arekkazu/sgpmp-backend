// Contrato local derivado de m07_router.py:181-279, gestionar_contratos_use_case.py:101-129,
// contrato.py:116-140, notificaciones_routers.py:27-54 y testing_sandbox.py:35-84.
// No abre sockets ni consulta TEST. DELETE retira la transacción; la siguiente petición con
// X-Test-Run-Id la reabre desde la base, como get_or_create_test_session().
const copia=x=>structuredClone(x);
const auditId=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');
import http from 'node:http';
const contrato=(id,v,t,estado,anexo=2)=>({id_version_contrato_aaef:id,contrato_version:v,tipo_cambio:t,estado,id_mapeo_anexo_aaef:anexo,periodo_gracia_dias:t==='MAJOR'?90:null,fecha_activacion:estado==='ACTIVO'?'2026-11-17T12:00:00+00:00':null,fecha_deprecacion:null,fecha_inactivacion:null});
const error=(code,message)=>({error_code:code,message,fields:[],timestamp:'2026-11-18T12:00:00Z'});
const instante='2026-11-18T12:00:00+00:00';
const inactiva='2027-02-16T12:00:00+00:00';
export function simuladorG038(opciones={}){let base=[contrato(3,'2.1','MINOR','ACTIVO'),...(!opciones.sinFixture?[contrato(13,'3.9','MINOR','PENDIENTE',1)]:[]),...(opciones.dosVigentes?[contrato(2,'2.0','MAJOR','DEPRECADO')]:[])],actual=copia(base),abierto=false,nextId=20,nextAudit=301,deleteN=0;const auditoriaBase=Array.from({length:opciones.auditoriaInicial??0},(_,i)=>({id_evento_integracion:auditId(i+1),tipo_evento:i%2?'CONTRATO_DEPRECADO':'CONTRATO_ACTIVADO',version_contrato:'historica'}));let auditoria=copia(auditoriaBase),avisos=Array.from({length:opciones.avisosInicial??0},(_,i)=>({id_notificacion:opciones.avisosInicial-i,id_evento:1,tipo_evento:1,mensaje:'Aviso previo',fecha_envio:instante,es_leido:false}));const peticiones=[];const anexos=[{id_mapeo_anexo_aaef:1,estado:'OBSOLETO'},{id_mapeo_anexo_aaef:2,estado:'APROBADO'}];const permisos=[['contratos_aaef',1],['contratos_aaef',2],['contratos_aaef',3],['auditoria_integracion',2]].filter((_,i)=>!opciones.sinPermisos||i!==3).map(([nombre_recurso,id_accion])=>({nombre_recurso,id_accion}));
  function respuesta(status,body,eco){return new Response(JSON.stringify(body),{status,headers:eco?{'X-Test-Run-Id':eco}:{}});}
  function lista(xs){const y=copia(xs);if(opciones.barajado)y.reverse();if(opciones.inyectado)for(const x of y)x.campo_nuevo='ignorar';return y;}
  function pagina(xs,p,t){const items=xs.slice((p-1)*t,p*t);return{items:lista(items),pagina:p,tamano:t,total:xs.length};}
  async function fetcher(url,init={}){const u=new URL(url),ruta=u.pathname.replace(/^\/api-sgpmp-test/,'');const metodo=init.method??'GET',h=init.headers??{},run=h['X-Test-Run-Id'],eco=run?'RUN-G038-V1-20261117-000000':null,publica=!run;peticiones.push({metodo,ruta,run:!!run});if(ruta.startsWith('/test-control/runs/')){deleteN++;abierto=false;if(!((deleteN===1&&opciones.rollbackAFallido)||(deleteN===2&&opciones.rollbackBFallido))){actual=copia(base);auditoria=copia(auditoriaBase);}return respuesta(200,{ok:true});}if(run&&!abierto){actual=copia(base);auditoria=copia(auditoriaBase);abierto=true;}if(metodo==='POST'&&ruta==='/sesiones/')return respuesta(200,{token:'LOCAL'});if(ruta==='/sesiones/me/permisos')return respuesta(200,{permisos},eco);if(ruta==='/integracion/anexos')return respuesta(200,lista(anexos),eco);if(ruta==='/integracion/contratos'&&metodo==='GET')return respuesta(200,lista(publica?actual:actual),eco);
    if(ruta==='/integracion/contratos'&&metodo==='POST'){const b=JSON.parse(init.body),x=contrato(nextId++,b.contrato_version,b.tipo_cambio,'PENDIENTE',b.id_mapeo_anexo_aaef);x.periodo_gracia_dias=b.periodo_gracia_dias??null;actual.push(x);return respuesta(201,x,eco);}
    const activar=ruta.match(/^\/integracion\/contratos\/(\d+)\/activar$/);if(metodo==='POST'&&activar){const x=actual.find(v=>v.id_version_contrato_aaef===Number(activar[1]));if(!x)return respuesta(404,error('CONTRATO_NO_ENCONTRADO','No existe'),eco);if(x.id_mapeo_anexo_aaef===1){if(opciones.fixtureActivada){x.estado='ACTIVO';x.fecha_activacion=instante;return respuesta(200,x,eco);}if(opciones.conAviso)avisos.unshift({id_notificacion:(opciones.avisosInicial??0)+1,id_evento:50,tipo_evento:41,mensaje:`La versión ${x.contrato_version} no pudo activarse: anexo de mapeo no aprobado.`,fecha_envio:instante,es_leido:false});return respuesta(422,error('CONTRATO_NO_VALIDO',`La versión ${x.contrato_version} no tiene anexo aprobado.`),eco);}const vigentes=actual.filter(v=>['ACTIVO','DEPRECADO'].includes(v.estado));if(vigentes.length>=2&&!opciones.limiteNoAplicado)return respuesta(422,error('LIMITE_VERSIONES_EXCEDIDO',`Retire primero la versión ${vigentes[0].contrato_version}.`),eco);if(x.tipo_cambio==='MAJOR'&&!opciones.majorNoDepreca||x.tipo_cambio==='MINOR'&&opciones.minorDepreca){for(const anterior of vigentes.filter(v=>v.estado==='ACTIVO')){anterior.estado='DEPRECADO';anterior.fecha_deprecacion=instante;anterior.fecha_inactivacion=inactiva;auditoria.push({id_evento_integracion:auditId(nextAudit++),tipo_evento:'CONTRATO_DEPRECADO',version_contrato:anterior.contrato_version});}}x.estado='ACTIVO';x.fecha_activacion=instante;auditoria.push({id_evento_integracion:auditId(nextAudit++),tipo_evento:'CONTRATO_ACTIVADO',version_contrato:x.contrato_version});return respuesta(200,x,eco);}
    if(ruta==='/integracion/auditoria'){const p=Number(u.searchParams.get('pagina')??1),t=Number(u.searchParams.get('tamano')??50),tipo=u.searchParams.get('tipo_evento');return respuesta(200,pagina(auditoria.filter(x=>x.tipo_evento===tipo),p,t),eco);}
    if(ruta==='/notificaciones'){const p=Number(u.searchParams.get('pagina')??1),t=Number(u.searchParams.get('tamano')??20);return respuesta(200,{...pagina(avisos,p,t),no_leidas:avisos.length},eco);}
    return respuesta(404,error('NO_ENCONTRADO','Ruta no definida'),eco);
  }
  return{fetcher,peticiones,api:'http://127.0.0.1:8765',get deleteN(){return deleteN;}};
}
export async function servidorG038(opciones={}){
  const sim=simuladorG038(opciones);
  const server=http.createServer(async(req,res)=>{
    try{
      let body='';for await(const chunk of req)body+=chunk;
      const headers=Object.fromEntries(Object.entries(req.headers).map(([k,v])=>[k.toLowerCase()==='x-test-run-id'?'X-Test-Run-Id':k,Array.isArray(v)?v[0]:v]));
      const respuesta=await sim.fetcher(`http://127.0.0.1${req.url}`,{method:req.method,headers,...(body?{body}:{})});
      res.writeHead(respuesta.status,Object.fromEntries(respuesta.headers));res.end(await respuesta.text());
    }catch(error){res.writeHead(500);res.end(JSON.stringify({error_code:'SIMULADOR_LOCAL',message:String(error.message)}));}
  });
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  return{...sim,api:`http://127.0.0.1:${server.address().port}/api-sgpmp-test`,cerrar:()=>new Promise(resolve=>server.close(resolve))};
}
