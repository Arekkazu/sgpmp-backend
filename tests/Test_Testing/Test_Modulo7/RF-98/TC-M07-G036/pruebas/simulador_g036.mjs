// Doble local de las rutas públicas de M07. Citas: m07_router.py:181-223,252-279;
// gestionar_contratos_use_case.py:70-96 (formato, gracia, mappers, NIC41, anexo,
// duplicado); gestionar_anexos_use_case.py:92-100; contrato.py:37-40;
// m07_dto.py:95-102 (Pydantic); error_handlers.py:40-68,306-332;
// consultar_auditoria_integracion_use_case.py:56-60 (items,pagina,tamano,total).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const DIR=path.dirname(fileURLToPath(import.meta.url));
const fixture=JSON.parse(fs.readFileSync(path.join(DIR,'fixture_g036.json')));
const permisos=[['contratos_aaef',1],['contratos_aaef',2],['auditoria_integracion',2]].map(([nombre_recurso,id_accion])=>({nombre_recurso,id_accion}));
const error=(code,field,status)=>({status,body:{error_code:code,message:code,fields:field?[{field,message:code}]:[],timestamp:new Date().toISOString()}});
export async function simuladorG036(op={}){
  const baseAnexos=structuredClone(fixture.anexos).filter(x=>(!op.sinRevision||x.estado!=='EN_REVISION')&&(!op.sinAprobado||x.estado!=='APROBADO')),baseContratos=structuredClone(fixture.contratos);
  let anexos=structuredClone(baseAnexos),contratos=structuredClone(baseContratos),eventos=[];
  const peticiones=[],runId='RUN-G036-V1-20261117-000000';
  const token=`e30.${Buffer.from(JSON.stringify({sub:7})).toString('base64url')}.sig`;
  // Textos: integracion.json contrato.*, estado.*, tipo_cambio.*, mapeador.* y comun.guardar.
  const html=`<!doctype html><html lang="es"><body><form id="login"><input type="email"><input type="password"><button type="submit">Entrar</button></form><main id="app" hidden><section aria-label="Versiones del contrato"><h2>Versiones del contrato</h2><button id="registrar">Registrar versión</button><table><tbody id="versiones"></tbody></table></section><div id="modal"></div></main><script>
  const api=location.origin+'/api-sgpmp-test';let anexos=[],contratos=[],autenticado=false;
  const nombre=id=>anexos.find(x=>x.id_mapeo_anexo_aaef===id)?.codigo_anexo||'Sin anexo';
  async function cargar(){anexos=await(await fetch(api+'/integracion/anexos')).json();contratos=await(await fetch(api+'/integracion/contratos')).json();document.querySelector('#versiones').innerHTML=contratos.map(c=>'<tr><td><strong>'+c.contrato_version+'</strong> '+({MAJOR:'Cambio mayor (retira la anterior con plazo)',MINOR:'Cambio menor (convive con la anterior)'}[c.tipo_cambio])+'</td><td>'+({PENDIENTE:'Pendiente',ACTIVO:'Activa',DEPRECADO:'En retiro',INACTIVO:'Retirada'}[c.estado])+'</td><td>'+(c.mapeadores.includes('COMPRAS')?'Facturas de compra':'')+' '+nombre(c.id_mapeo_anexo_aaef)+'</td><td>'+(c.estado==='PENDIENTE'?'<button>Activar</button>':c.estado==='ACTIVO'?'<button>Retirar con plazo</button>':'')+'</td></tr>').join('');}
  document.querySelector('#login').onsubmit=async e=>{e.preventDefault();const z=await fetch(api+'/sesiones/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({correo_electronico:document.querySelector('input[type=email]').value,contrasena:document.querySelector('input[type=password]').value})});if(z.ok){autenticado=true;document.querySelector('#login').hidden=true;}};
  window.addEventListener('popstate',()=>{if(autenticado&&location.pathname.endsWith('/integracion/contrato')){document.querySelector('#app').hidden=false;cargar();}});
  document.querySelector('#registrar').onclick=()=>{document.querySelector('#modal').innerHTML='<div role="dialog"><h2>Registrar versión</h2><div class="ds-field"><label for="version">Versión</label><input id="version" value="3.0"></div><div class="ds-field"><label for="tipo">Tipo de cambio</label><select id="tipo"><option value="MAJOR">Cambio mayor (retira la anterior con plazo)</option></select></div><div class="ds-field"><label for="fecha">Fecha de vigencia</label><input id="fecha" type="date" value="2026-11-17"></div><div class="ds-field"><label for="anexo">Anexo de mapeo</label><select id="anexo">'+anexos.filter(x=>x.estado!=='BORRADOR').map(x=>'<option value="'+x.id_mapeo_anexo_aaef+'">'+x.codigo_anexo+'</option>').join('')+'</select></div><fieldset><legend>Qué envía</legend><label><input type="checkbox" checked disabled>Facturas de compra</label></fieldset><div class="ds-field"><label for="gracia">Plazo de retiro de la versión anterior (días)</label><input id="gracia" type="number" value="90"></div><button id="guardar">Guardar</button></div>';document.querySelector('#guardar').onclick=async()=>{const b={contrato_version:document.querySelector('#version').value,tipo_cambio:'MAJOR',fecha_vigencia:document.querySelector('#fecha').value,id_mapeo_anexo_aaef:Number(document.querySelector('#anexo').value),mapeadores:['COMPRAS'],periodo_gracia_dias:Number(document.querySelector('#gracia').value)};const z=await fetch(api+'/integracion/contratos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});if(z.ok){document.querySelector('#modal').innerHTML='';await cargar();}};};
  </script></body></html>`;
  const server=http.createServer(async(req,res)=>{
    const u=new URL(req.url,'http://localhost'),p=u.pathname.replace(/^\/(api-sgpmp-test|sigab-test)/,''),run=req.headers['x-test-run-id'];
    peticiones.push({metodo:req.method,ruta:p,run:!!run});
    const send=(status,body)=>{res.writeHead(status,{'content-type':'application/json',...(run?{'x-test-run-id':run}:{})});res.end(JSON.stringify(op.inyectar&&status<400&&body&&typeof body==='object'?Array.isArray(body)?body.map(x=>({...x,campo_inyectado:'local'})):{...body,campo_inyectado:'local'}:body));};
    if(u.pathname.startsWith('/sigab-test')){res.writeHead(200,{'content-type':'text/html'});res.end(html);return;}
    if(req.method==='POST'&&p==='/sesiones/'){send(200,{token});return;}
    if(p==='/sesiones/me/permisos'){send(200,{permisos:op.sinPermisos?[]:permisos});return;}
    if(req.method==='DELETE'&&p.startsWith('/test-control/runs/')){if(!op.rollbackFallido){anexos=structuredClone(baseAnexos);contratos=structuredClone(baseContratos);eventos=[];}send(200,{message:'cerrado'});return;}
    if(req.method==='GET'&&p==='/integracion/anexos'){send(200,op.barajar?[...anexos].reverse():anexos);return;}
    if(req.method==='GET'&&p==='/integracion/contratos'){send(200,op.barajar?[...contratos].reverse():contratos);return;}
    if(req.method==='GET'&&p==='/integracion/auditoria'){const pagina=Number(u.searchParams.get('pagina')||1),tamano=Number(u.searchParams.get('tamano')||100),items=eventos.slice((pagina-1)*tamano,pagina*tamano);send(200,{items,pagina,tamano,total:eventos.length});return;}
    let b={};if(req.method==='POST'){let raw='';for await(const chunk of req)raw+=chunk;b=JSON.parse(raw||'{}');}
    if(req.method==='POST'&&p==='/integracion/anexos'){const a={id_mapeo_anexo_aaef:Math.max(...anexos.map(x=>x.id_mapeo_anexo_aaef))+1,...b,estado:'BORRADOR',fecha_aprobacion_interna:null,fecha_aprobacion:null,evidencia:null};anexos.push(a);send(201,a);return;}
    if(req.method==='POST'&&p==='/integracion/contratos'){
      // DTO previo al caso de uso: m07_dto.py:95-102; error_handlers.py:306-332.
      if(!Array.isArray(b.mapeadores)||b.mapeadores.length===0||b.mapeadores.some(x=>!['COMPRAS','COMPROBANTE_NIC41'].includes(x))){const z=error('VAL_ENTRADA','mapeadores',422);send(z.status,z.body);return;}
      // Orden del caso de uso: gestionar_contratos_use_case.py:70-96.
      let z=null;if(!/^\d{1,3}\.\d{1,3}$/.test(b.contrato_version))z=error('VERSION_INVALIDA','contrato_version',422);
      else if(b.tipo_cambio==='MAJOR'&&Number(b.periodo_gracia_dias)<30)z=error('PERIODO_GRACIA_INVALIDO','periodo_gracia_dias',422);
      else if(b.mapeadores.includes('COMPROBANTE_NIC41'))z=error('MAPPER_NO_DISPONIBLE','mapeadores',422);
      else {const a=anexos.find(x=>x.id_mapeo_anexo_aaef===b.id_mapeo_anexo_aaef);if(!a||!['APROBADO','EN_REVISION'].includes(a.estado)||op.rechazarRevision&&a.estado==='EN_REVISION')z=error('ANEXO_MAPEO_INVALIDO','id_mapeo_anexo_aaef',422);else if(contratos.some(x=>x.contrato_version===b.contrato_version))z=error('VERSION_DUPLICADA','contrato_version',409);}
      if(!z&&op.fallar01&&b.contrato_version==='4.0')z=error('REGISTRO_LOCAL_FALLIDO','contrato_version',422);
      if(z){send(z.status,z.body);return;}
      const v={id_version_contrato_aaef:Math.max(...contratos.map(x=>x.id_version_contrato_aaef))+1,...b,endpoint_asociado:'/integracion/aaef/productores/{nit}',descripcion:b.descripcion??null,estado:'PENDIENTE',fecha_activacion:null,fecha_deprecacion:null,fecha_inactivacion:null};contratos.push(v);
      eventos.push({id_evento_integracion:String(eventos.length+1),tipo_evento:'CONTRATO_REGISTRADO',version_contrato:v.contrato_version,id_usuario:7,fecha_evento:new Date().toISOString(),json_detalle:{estado:'PENDIENTE'},integridad:'OK'});send(201,v);return;
    }
    send(404,error('NO_ENCONTRADO',null,404).body);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
  return{api:origin+'/api-sgpmp-test',front:origin+'/sigab-test',peticiones,runId,cerrar:()=>new Promise(resolve=>server.close(resolve))};
}


