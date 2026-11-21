import http from 'node:http';
import {randomUUID} from 'node:crypto';
import {esquema} from '../lib/contrato.mjs';

const fecha='2027-02-16T13:53:12.939277Z';
const base=[
 {id_version_contrato_aaef:18,contrato_version:'3.0',tipo_cambio:'MAJOR',estado:'ACTIVO',id_mapeo_anexo_aaef:1,mapeadores:['LOCAL'],endpoint_asociado:'/integracion/aaef/productores/{nit}',fecha_vigencia:'2026-01-01',periodo_gracia_dias:null,fecha_activacion:'2026-01-01T00:00:00Z',fecha_deprecacion:null,fecha_inactivacion:null},
 {id_version_contrato_aaef:3,contrato_version:'2.1',tipo_cambio:'MINOR',estado:'DEPRECADO',id_mapeo_anexo_aaef:1,mapeadores:['LOCAL'],endpoint_asociado:'/integracion/aaef/productores/{nit}',fecha_vigencia:'2025-01-01',periodo_gracia_dias:90,fecha_activacion:'2025-01-01T00:00:00Z',fecha_deprecacion:'2026-11-18T00:00:00Z',fecha_inactivacion:fecha},
 {id_version_contrato_aaef:1,contrato_version:'1.0',tipo_cambio:'MAJOR',estado:'INACTIVO',id_mapeo_anexo_aaef:1,mapeadores:['LOCAL'],endpoint_asociado:'/integracion/aaef/productores/{nit}',fecha_vigencia:'2024-01-01',periodo_gracia_dias:90,fecha_activacion:'2024-01-01T00:00:00Z',fecha_deprecacion:'2025-01-01T00:00:00Z',fecha_inactivacion:'2025-04-01T00:00:00Z'}
];
const error=(code,message,field='Accept-Version')=>({error_code:code,message,fields:[{field,message}],timestamp:'2026-11-18T00:00:00Z'});
export async function servidorG040(opciones={}){
 const contratos=base.filter(x=>!(opciones.sinDeprecado&&x.estado==='DEPRECADO')&&!(opciones.sinInactivo&&x.estado==='INACTIVO'));
 let reloj=Date.parse('2026-11-18T18:00:00Z'),tokenEmitido=null,tokenValido=false,qaToken=false,cerrado=false,limiteInyectado=false;
 const aaeF=[],peticiones=[];const avanzar=ms=>{reloj+=ms;};
 const server=http.createServer(async(req,res)=>{
  const u=new URL(req.url,'http://local'),route=u.pathname,run=req.headers['x-test-run-id'];
  let status=200,body=null,h={'Content-Type':'application/json','X-Test-Run-Id':run??''};
  const send=()=>{res.writeHead(status,h);res.end(JSON.stringify(body));};
  peticiones.push({metodo:req.method,ruta:route.replace(/(\/productores\/)(\d+)/,(_,a,b)=>a+'***'+b.slice(-3)),sandbox:!!run,cabecerasSandbox:!!run||!!req.headers['x-sandbox-secret'],http:()=>status});
  const leerCuerpo=async()=>{let texto='';for await(const parte of req)texto+=parte;try{return JSON.parse(texto);}catch{return null;}};
  const validarCuerpo=(valor,campos)=>{if(!valor||typeof valor!=='object'||Array.isArray(valor))return campos[0];for(const campo of campos)if(typeof valor[campo]!=='string'||!valor[campo].trim())return campo;if(opciones.estricto!==false){const contrato=esquema(req.method,route);const extra=Object.keys(valor).find(k=>!Object.hasOwn(contrato.solicitud,k));if(extra)return extra;}return null;};
  if(req.method==='DELETE'&&route.startsWith('/test-control/runs/')){status=200;cerrado=true;body={status:'Rollback exitoso'};send();return;}
  if(req.method==='POST'&&route==='/sesiones/'){const data=await leerCuerpo(),fallo=validarCuerpo(data,['correo_electronico','contrasena']);if(opciones.loginInvalido||fallo){status=400;body=error('VAL_ENTRADA',`${fallo??'correo_electronico'}: Este campo es obligatorio`,fallo??'correo_electronico');}else{qaToken=true;body={token:'LOCAL_ADMIN_TOKEN'};}send();return;}
  if(!qaToken){status=401;body=error('NO_AUTORIZADO','Sin sesión');send();return;}
  if(route==='/sesiones/me/permisos'){body={permisos:opciones.sinPermisos?[]:[{nombre_recurso:'contratos_aaef',id_accion:2},{nombre_recurso:'fincas',id_accion:2},{nombre_recurso:'auditoria_integracion',id_accion:2}]};send();return;}
  if(route==='/integracion/anexos'){body=[{id_mapeo_anexo_aaef:1,estado:'APROBADO'}];send();return;}
  if(route==='/integracion/contratos'){body=opciones.rollbackFallido&&cerrado?contratos.map((x,i)=>i===0?{...x,estado:'INACTIVO'}:x):opciones.barajado?[...contratos].reverse():contratos;send();return;}
  if(route==='/configuracion/fincas/463/titular'){body={numero_id_tributaria:'900123456',tipo_id_tributaria:'NIT'};send();return;}
  if(route==='/finanzas/periodos'){const nit=u.searchParams.get('numero_id_tributaria');if(opciones.estricto!==false&&([...u.searchParams.keys()].some(k=>k!=='numero_id_tributaria')||!/^\d{6,15}$/.test(nit??''))){status=400;body=error('VAL_ENTRADA','numero_id_tributaria inválido','numero_id_tributaria');}else body=[{id_periodo_contable:7,fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30',estado:'CERRADO'}];send();return;}
  if(route==='/integracion/auditoria'){body={items:[],pagina:1,tamano:100,total:0};send();return;}
  if(req.method==='POST'&&route==='/integraciones/agrofusion/token'){const data=await leerCuerpo(),fallo=validarCuerpo(data,['client_id','client_secret','email']);if(fallo){status=400;body=error('VAL_ENTRADA',`${fallo}: Este campo es obligatorio`,fallo);}else if(req.headers.authorization){status=400;body=error('CABECERA_INVALIDA','Authorization no corresponde al token de canal','Authorization');}else if(opciones.tokenRechazado||data.client_id!=='LOCAL_CLIENT'||data.client_secret!=='LOCAL_SECRET'||data.email!=='local@example.invalid'){status=401;body=error('CREDENCIALES_INVALIDAS','Cliente rechazado');}else{tokenEmitido=reloj;tokenValido=true;body={access_token:'LOCAL_CHANNEL_TOKEN',expires_in:300};}send();return;}
  if(req.method==='GET'&&route.startsWith('/integracion/aaef/productores/')){
   const nit=route.split('/').at(-1),desde=u.searchParams.get('desde'),hasta=u.searchParams.get('hasta'),auth=req.headers.authorization??'';
   const fail=(s,c,m)=>{status=s;body=error(c,m);send();};
   if([...u.searchParams.keys()].some(k=>/client_id|client_secret|token/i.test(k)))return fail(400,'CREDENCIALES_EN_URL','Credenciales en URL');
   if(opciones.estricto!==false&&[...u.searchParams.keys()].some(k=>!['desde','hasta'].includes(k)))return fail(400,'VAL_ENTRADA','Campo fuera del contrato');
   if(!/^\d+$/.test(nit)||!desde||!hasta||desde>hasta)return fail(400,'PARAMETROS_INVALIDOS','NIT o fechas inválidas');
   if(!tokenValido||auth!=='Bearer LOCAL_CHANNEL_TOKEN'||reloj-tokenEmitido>=300000)return fail(401,'TOKEN_INVALIDO','Token vencido');
   const ventana=aaeF.filter(t=>reloj-t<60000);if(ventana.length>=5)return fail(429,'RATE_LIMIT_EXCEDIDO','Límite por minuto');if(opciones.limite429&&!limiteInyectado&&aaeF.length===3){limiteInyectado=true;return fail(429,'RATE_LIMIT_EXCEDIDO','Límite por minuto');}aaeF.push(reloj);
   if(opciones.sinPermisoExportacion)return fail(403,'PERMISO_INSUFICIENTE','Permiso insuficiente');
   if(nit!=='900123456')return fail(404,'TITULAR_NO_ENCONTRADO','Titular no encontrado');
   if(opciones.alcanceInsuficiente)return fail(403,'ALCANCE_INSUFICIENTE','Finca no asignada');
   let version=req.headers['accept-version'];
   if(version&&!/^\d{1,3}\.\d{1,3}$/.test(version)&&!opciones.formatoAceptado)return fail(400,'VERSION_FORMATO_INVALIDO','Formato inválido');
   let contrato=version?contratos.find(x=>x.contrato_version===version):[...contratos].filter(x=>x.estado==='ACTIVO').sort((a,b)=>Number(b.contrato_version.split('.')[0])-Number(a.contrato_version.split('.')[0]))[0];
   if(opciones.formatoAceptado&&version&&!/^\d{1,3}\.\d{1,3}$/.test(version))contrato=contratos.find(x=>x.estado==='ACTIVO');
   if(!contrato&&version)return fail(opciones.http19Otro?409:404,opciones.codigo19Otro?'VERSION_OTRA':opciones.codigo19Correcto?'VERSION_NO_ENCONTRADA':'VERSION_NO_REGISTRADA','La versión no está disponible');
   if(contrato?.estado==='INACTIVO'&&!opciones.inactivaAtendida)return fail(410,'VERSION_INACTIVA','Versión inactiva');
   if(!contrato)return fail(404,'VERSION_NO_REGISTRADA','Versión no disponible');
   if(opciones.envelope422&&(['3.0','2.1'].includes(contrato.contrato_version)))return fail(422,'RANGO_INVALIDO','Rango inválido');
   h['X-Version-Contrato-AAEF']=opciones.versionEquivocada&&!version?'2.1':contrato.contrato_version;
   h['X-Request-Id']=randomUUID();h['X-Content-SHA256']='a'.repeat(64);
   if(contrato.estado==='DEPRECADO'&&!opciones.sinAdvertencia){h.Deprecation='true';h.Sunset=new Date(Date.parse(contrato.fecha_inactivacion)+(opciones.sunsetDistinto?1000:0)).toUTCString();}
   body={metadata:{StandardVersion:'1.0'},invoices:[],...(opciones.inyectado?{extra:'permitido'}:{})};send();return;
  }
  status=404;body=error('RUTA_NO_ENCONTRADA','Ruta no encontrada');send();
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 return{api:`http://127.0.0.1:${server.address().port}`,avanzar,peticiones,cerrar:()=>new Promise(resolve=>{server.close(resolve);server.closeAllConnections();})};
}
