const {clasificarIntercepcion}=require('./lib/intercepcion.cjs');
const {sanearError}=require('./lib/privacidad.cjs');
const env=k=>Cypress.env(k),API=String(env('API_BASE')||'').replace(/\/+$/,''),FRONT=String(env('FRONT_BASE')||'').replace(/\/+$/,'');
const RUN=String(env('RUN_ID')||''),DIR=String(env('ARTIFACTS_DIR')||''),local=env('LOCAL_SMOKE')==='SI',version=String(env('VERSION_LIBRE')||'');
const loop=u=>{try{const x=new URL(u);return x.protocol==='http:'&&['localhost','127.0.0.1'].includes(x.hostname)&&!!x.port;}catch{return false;}};
const allowed=/^RUN-G036-V2-\d{8}-\d{6}$/.test(RUN)&&!!DIR&&!!env('ADMIN_TOKEN')&&!!env('SANDBOX_SECRET')&&/^\d{1,3}\.\d{1,3}$/.test(version)&&(local?loop(API)&&loop(FRONT):API==='https://www.api.inmero.co/api-sgpmp-test'&&FRONT==='https://api.inmero.co/sigab-test');
const acta={caso:'TC-M07-05',http_registro:null,version_visible:false,pendiente_activar:false,activar_visible:false,activar_deshabilitado:null,motivo_servidor_visible:false,activo_deprecar:null,deprecado_sin_accion:null,inactivo_sin_accion:null,subcomprobaciones_sin_dato:[],captura:false,peticiones:[],hitos:{frontal_cargado:false,login_interceptado:false,refresh_interceptado:false,pantalla_contrato:false,modal_abierto:false,registro_enviado:false},error:null,asercion_producto:null};
let loginEntregado=false,motivoServidor=null;
let cola=Promise.resolve();
Cypress.on('fail',e=>{acta.error=sanearError(e.message||e,[env('ADMIN_TOKEN'),env('SANDBOX_SECRET')]).slice(0,500);throw e;});
function interceptar(){
  cy.intercept({url:/^https?:\/\//,middleware:true},req=>{
    const z=clasificarIntercepcion(req.url,req.method,API,FRONT,local);
    if(z.destino==='FRONTAL'){req.continue();return;}
    if(z.destino!=='API'){req.reply({forceNetworkError:true});return;}
    const ruta=z.ruta,row={metodo:req.method,ruta,http:null,actor:'administrador'};acta.peticiones.push(row);
    if(req.method==='POST'&&ruta==='/sesiones/refresh'){
      acta.hitos.refresh_interceptado=true;req.alias='refresh';row.local=true;
      if(!loginEntregado){row.http=401;req.reply({statusCode:401,body:{error_code:'REFRESH_TOKEN_REQUERIDO',message:'Sin sesión previa'}});return;}
      row.http=200;req.reply({statusCode:200,body:{token:env('ADMIN_TOKEN')}});return;
    }
    if(req.method==='POST'&&ruta==='/sesiones/'){
      req.alias='login';row.http=200;row.local=true;loginEntregado=true;
      req.reply({statusCode:200,body:{token:env('ADMIN_TOKEN')}});return;
    }
    if(acta.peticiones.length>50||!['GET','OPTIONS'].includes(req.method)&&!(req.method==='POST'&&ruta==='/integracion/contratos')||/\/(?:activar|deprecar)/.test(ruta)){req.reply({forceNetworkError:true});return;}
    if(req.method==='POST'&&ruta==='/integracion/contratos')req.alias='registro';
    let liberar;
    const turno=cola;
    cola=new Promise(resolve=>{liberar=resolve;});
    let liberado=false;
    let vigilancia;
    const terminar=()=>{if(!liberado){liberado=true;clearTimeout(vigilancia);liberar();}};
    req.on('after:response',res=>{row.http=res.statusCode;if(req.method==='GET'&&ruta==='/integracion/contratos'){let datos=res.body;try{if(typeof datos==='string')datos=JSON.parse(datos);}catch{}if(Array.isArray(datos))motivoServidor=datos.find(x=>x.contrato_version===version)?.motivo_no_activable??null;}terminar();});
    return turno.then(()=>{req.headers['X-Test-Run-Id']=RUN;req.headers['X-Sandbox-Secret']=env('SANDBOX_SECRET');vigilancia=setTimeout(()=>{row.cortada=true;terminar();},Number(Cypress.config('responseTimeout')||30000)+1000);try{req.continue();}catch(e){row.cortada=true;terminar();throw e;}});
  });
}
const fila=v=>cy.contains('section[aria-label="Versiones del contrato"] tbody tr strong',new RegExp('^'+String(v).replaceAll('.','\\.')+'$')).closest('tr');
const campo=(label,tipo)=>cy.contains('[role="dialog"] .ds-field > label',label).closest('.ds-field').find(tipo);
describe('TC-M07-05 contrato V2',()=>{
  beforeEach(interceptar);
  afterEach(()=>{
    if(!acta.hitos.frontal_cargado){cy.writeFile(DIR+'/G036-UI-05.json',acta);return;}
    cy.get('body').then($b=>$b[0].querySelectorAll('input').forEach(x=>x.style.filter='blur(8px)'));
    cy.screenshot('G036-UI-05',{capture:'viewport',overwrite:true}).then(()=>{acta.captura=true;cy.writeFile(DIR+'/G036-UI-05.json',acta);});
  });
  it('registra una versión libre y comprueba acciones por estado',()=>{
    if(!allowed)throw Error('BLOQUEO_G036_ENTORNO');
    cy.visit(FRONT+'/integracion/contrato');
    cy.wait('@refresh').its('response.statusCode').should('eq',401);
    cy.location('pathname').should('include','/login');
    cy.get('input[type="email"]').should('exist').then(()=>{acta.hitos.frontal_cargado=true;});
    cy.get('input[type="email"]').type('g036-ui@local.invalid',{log:false});
    cy.get('input[type="password"]').type('G036LocalDummy123!',{log:false});
    cy.get('button[type="submit"]').click();
    cy.wait('@login').its('response.statusCode').should('eq',200).then(()=>{acta.hitos.login_interceptado=true;});
    cy.location('pathname').should('include','/integracion/contrato');
    cy.get('section[aria-label="Versiones del contrato"] tbody tr').should('exist').then(()=>{acta.hitos.pantalla_contrato=true;});
    for(const [key,estado,texto,accion] of [['activo_deprecar','ACTIVO','Activa','Retirar con plazo'],['deprecado_sin_accion','DEPRECADO','En retiro',null],['inactivo_sin_accion','INACTIVO','Retirada',null]]){
      const v=env('VERSION_'+estado);
      if(v)fila(String(v)).should('contain.text',texto).then($row=>{acta.asercion_producto=key;acta[key]=accion?$row.find('button').toArray().some(b=>b.textContent.includes(accion)):$row.find('button').length===0;});
      else acta.subcomprobaciones_sin_dato.push(estado);
    }
    cy.then(()=>{acta.asercion_producto=null;});
    cy.contains('button','Registrar versión').click();
    cy.get('[role="dialog"]').should('exist').then(()=>{acta.hitos.modal_abierto=true;});
    campo('Versión','input').clear().type(version);
    campo('Tipo de cambio','select').select('MAJOR');
    campo('Fecha de vigencia','input').clear().type(String(env('FECHA_FUTURA')));
    campo('Anexo de mapeo','select').select(String(env('ANEXO_APROBADO_ID')));
    cy.get('[role="dialog"] input[type="checkbox"]').first().should('be.checked');
    campo('Plazo de retiro de la versión anterior (días)','input').clear().type('90');
    cy.contains('[role="dialog"] button','Guardar').click();
    cy.wait('@registro').then(({response})=>{acta.hitos.registro_enviado=true;acta.asercion_producto='http_registro';acta.http_registro=response?.statusCode;expect(acta.http_registro).eq(201);});
    cy.then(()=>{acta.asercion_producto='version_visible';});
    fila(version).should('contain.text','Pendiente').and('contain.text','Cambio mayor (retira la anterior con plazo)').and('contain.text','Facturas de compra').and('contain.text',String(env('ANEXO_APROBADO_CODIGO'))).then(()=>{acta.version_visible=true;});
    fila(version).then($row=>{
      acta.asercion_producto='pendiente_activar';
      const b=$row.find('button').toArray().find(x=>x.textContent.trim()==='Activar');
      acta.activar_visible=!!b;
      acta.activar_deshabilitado=b?.disabled??null;
      const motivo=b?.getAttribute('aria-describedby');
      const texto=motivo?$row[0].querySelector('#'+CSS.escape(motivo))?.textContent?.trim():'';
      acta.motivo_servidor_visible=Boolean(motivoServidor&&texto===motivoServidor);
      acta.pendiente_activar=!!b&&(motivoServidor?b.disabled&&acta.motivo_servidor_visible:!b.disabled);
      expect(acta.pendiente_activar,'Activar segun motivo_no_activable del servidor').eq(true);
    });
    cy.then(()=>{for(const key of ['activo_deprecar','deprecado_sin_accion','inactivo_sin_accion'])if(acta[key]===false){acta.asercion_producto=key;expect(acta[key],key).eq(true);}});
  });
});

