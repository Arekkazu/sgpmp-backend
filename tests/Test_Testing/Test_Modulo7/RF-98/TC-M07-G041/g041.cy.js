const {clasificarIntercepcion}=require('./lib/intercepcion.cjs');
const {sanearError}=require('./lib/privacidad.cjs');
const env=k=>Cypress.env(k),API=String(env('API_BASE')||'').replace(/\/+$/,''),FRONT=String(env('FRONT_BASE')||'').replace(/\/+$/,'');
const DIR=String(env('ARTIFACTS_DIR')||''),local=env('LOCAL_SMOKE')==='SI';
const loop=u=>{try{const x=new URL(u);return x.protocol==='http:'&&['localhost','127.0.0.1'].includes(x.hostname)&&!!x.port;}catch{return false;}};
const allowed=/^RUN-G041-V1-\d{8}-\d{6}$/.test(String(env('RUN_ID')||''))&&!!DIR&&!!env('CONTADOR_TOKEN')&&(local?loop(API)&&loop(FRONT):API==='https://www.api.inmero.co/api-sgpmp-test'&&FRONT==='https://api.inmero.co/sigab-test');
const acta={caso:'TC-M07-22',frontal_cargado:false,login_completado:false,login_interceptado:false,refresh_interceptado:false,pantalla_contrato:false,acceso_denegado:false,registrar_version_visible:null,activar_visible:null,deprecar_visible:null,registrar_anexo_visible:null,captura:false,error:null,peticiones:[]};
let loginEntregado=false;
Cypress.on('fail',e=>{acta.error=sanearError(e.message||e,[env('CONTADOR_TOKEN')]).slice(0,500);throw e;});
function interceptar(){
  cy.intercept({url:/^https?:\/\//,middleware:true},req=>{
    const z=clasificarIntercepcion(req.url,req.method,API,FRONT,local);
    if(z.destino==='FRONTAL'){req.continue();return;}
    if(z.destino!=='API'){req.reply({forceNetworkError:true});return;}
    const ruta=z.ruta,row={metodo:req.method,ruta,http:null};acta.peticiones.push(row);
    if(req.method==='POST'&&ruta==='/sesiones/refresh'){
      acta.refresh_interceptado=true;req.alias='refresh';row.local=true;
      if(!loginEntregado){row.http=401;req.reply({statusCode:401,body:{error_code:'REFRESH_TOKEN_REQUERIDO',message:'Sin sesión previa'}});return;}
      row.http=200;req.reply({statusCode:200,body:{token:env('CONTADOR_TOKEN')}});return;
    }
    if(acta.peticiones.length>30||!['GET','OPTIONS'].includes(req.method)&&!(req.method==='POST'&&ruta==='/sesiones/')){req.reply({forceNetworkError:true});return;}
    if(req.method==='POST'&&ruta==='/sesiones/'){
      req.alias='login';row.http=200;row.local=true;
      loginEntregado=true;
      req.reply({statusCode:200,body:{token:env('CONTADOR_TOKEN')}});return;
    }
    // Sin callback de req.continue: una conexión abortada conserva http:null.
    req.on('after:response',res=>{row.http=res.statusCode;});
    req.continue();
  });
}
describe('TC-M07-22 control de acceso a contratos',()=>{
  beforeEach(interceptar);
  afterEach(()=>{
    if(!acta.frontal_cargado){cy.writeFile(DIR+'/G041-UI-22.json',acta);return;}
    cy.get('body').then($b=>$b[0].querySelectorAll('input').forEach(x=>x.style.filter='blur(8px)'));
    cy.screenshot('G041-UI-22',{capture:'viewport',overwrite:true}).then(()=>{
      acta.captura=true;cy.writeFile(DIR+'/G041-UI-22.json',acta);
    });
  });
  it('el Contador no ve acciones de gestión',()=>{
    if(!allowed)throw Error('BLOQUEO_G041_ENTORNO');
    cy.visit(FRONT+'/integracion/contrato');
    cy.wait('@refresh').its('response.statusCode').should('eq',401);
    cy.location('pathname').should('include','/login');
    cy.get('input[type="email"]').should('exist').then(()=>{acta.frontal_cargado=true;});
    cy.get('input[type="email"]').type('g041-ui@local.invalid',{log:false});
    cy.get('input[type="password"]').type('G041LocalDummy123!',{log:false});
    cy.get('button[type="submit"]').click();
    cy.wait('@login').its('response.statusCode').should('eq',200).then(()=>{acta.login_completado=true;acta.login_interceptado=true;});
    // AuthProvider guarda la ruta al recibir 401; useLogin vuelve con history.replace.
    cy.location('pathname').should('include','/integracion/contrato');
    cy.get('body').should('exist').then($body=>{
      const denegado=/acceso denegado|no tiene permiso/i.test($body.text());
      acta.acceso_denegado=denegado;
      if(denegado){acta.pantalla_contrato=true;acta.registrar_version_visible=false;acta.activar_visible=false;acta.deprecar_visible=false;acta.registrar_anexo_visible=false;}
    });
    cy.then(()=>{if(acta.acceso_denegado)return;cy.get('section[aria-label="Versiones del contrato"] tbody tr',{timeout:15000}).should('have.length.greaterThan',0).then($rows=>{
      const sec=$rows[0].closest('section[aria-label="Versiones del contrato"]');
      if(!sec)throw Error('PANTALLA_CONTRATO_NO_CARGADA');
      acta.pantalla_contrato=true;
      const buttons=[...sec.querySelectorAll('button')].map(x=>x.textContent.trim());
      acta.registrar_version_visible=buttons.some(x=>x.includes('Registrar versión'));
      acta.activar_visible=buttons.some(x=>x==='Activar');
      acta.deprecar_visible=buttons.some(x=>x.includes('Retirar con plazo'));
      acta.registrar_anexo_visible=[...sec.ownerDocument.querySelectorAll('button')].some(x=>x.textContent.includes('Registrar anexo'));
      expect(acta.registrar_version_visible,'Registrar versión').eq(false);
      expect(acta.activar_visible,'Activar').eq(false);
      expect(acta.deprecar_visible,'Retirar con plazo').eq(false);
    });});
  });
});
