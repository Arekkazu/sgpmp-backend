// TC-M06-018: panel y bandeja del Contador durante un RUN autorizado.
const {coincideCombinacion,clasificarIntercepcion}=require('./lib/aviso_g40.cjs');
const env=k=>Cypress.env(k),API=String(env('API_BASE')||'').replace(/\/+$/,''),FRONT=String(env('FRONT_BASE')||'').replace(/\/+$/,'');
const RUN=String(env('RUN_ID')||''),DIR=env('ARTIFACTS_DIR'),EXPECTED=Number(env('EXPECTED_COUNT'));
const SPECIES=String(env('SPECIES_ID')||'');
const SPECIES_NAME=String(env('SPECIES_NAME')||'');
const ALERT_SELECTOR='.ds-alert.ds-alert--warning[role="alert"]';
const TITLE=/^(\d+)\s+l[ií]neas?\s+de asiento sin cuenta contable$/i;
const rawBase=env('BASE_NOTICE_IDS')||[];
const BASE_NOTICE_IDS=new Set((Array.isArray(rawBase)?rawBase:JSON.parse(String(rawBase))).map(String));
const canonical=/^https:\/\/(?:www\.)?api\.inmero\.co\/api-sgpmp-test$/;
const trial=env('LOCAL_SMOKE')==='SI';
const loopback=u=>{try{const x=new URL(u);return x.protocol==='http:'&&['127.0.0.1','localhost'].includes(x.hostname)&&Boolean(x.port)&&x.pathname==='/';}catch{return false;}};
const allowed=/^RUN-G40-V\d+-\d{8}-\d{6}$/.test(RUN)&&
  (trial?loopback(API)&&loopback(FRONT):canonical.test(API)&&
  /^https:\/\/(?:www\.)?api\.inmero\.co\/sigab-test$/.test(FRONT))&&DIR&&
  env('PROD_LOGIN_TOKEN')&&env('SANDBOX_SECRET')&&Number.isInteger(EXPECTED)&&EXPECTED>=0;
const acta={caso:'TC-M06-018',id:'G40-UI-018-01',estado:'NO_CONCLUYENTE',motivo:'No iniciado',
  panel_visible:false,conteo:null,campana_visible:false,bandeja_abierta:false,avisos_en_ui:0,
  avisos_nuevos_api:0,combinacion_visible:false,captura:false,
  login_resuelto_localmente:false,host_bloqueado:null,peticiones:[]};
const clean=x=>String(x??'').replace(/Bearer\s+\S+|[\w.+-]+@[\w.-]+|eyJ[\w-]+\.[\w-]+\.[\w-]+/gi,'[RESERVADO]').slice(0,160);
let cola=Promise.resolve();
function interceptar(){cy.intercept({url:/^https?:\/\//,middleware:true},req=>{
  const u=new URL(req.url);
  const {destino,ruta}=clasificarIntercepcion(req.url,req.method,API,FRONT,trial);
  if(destino==='FRONTAL'){req.continue();return;}
  if(destino==='BLOQUEADO'){
    acta.host_bloqueado=clean(u.origin+u.pathname.replace(/\/\d+(?=\/|$)/g,'/[ID]'));
    req.reply({forceNetworkError:true});return;}
  const row={metodo:req.method,ruta:clean(ruta),http:null,eco:false,local:false};acta.peticiones.push(row);
  if(acta.peticiones.length>24){req.reply({forceNetworkError:true});return;}
  if(req.method==='GET'&&ruta==='/__g40_sonda__'){
    req.alias='sonda';Object.assign(row,{http:200,eco:true,local:true});
    req.reply({statusCode:200,headers:{'x-test-run-id':RUN},body:{interceptado:true}});return;}
  if(req.method==='POST'&&ruta==='/sesiones/'){
    req.alias='login';acta.login_resuelto_localmente=true;Object.assign(row,{http:200,eco:true,local:true});
    req.reply({statusCode:200,headers:{'x-test-run-id':RUN},body:{token:env('PROD_LOGIN_TOKEN')}});return;}
  if(!['GET','OPTIONS'].includes(req.method)){req.reply({forceNetworkError:true});return;}
  if(ruta==='/finanzas/configuracion')req.alias='configuracion';
  if(ruta==='/notificaciones')req.alias='notificaciones';
  let release;const turn=cola;cola=new Promise(resolve=>release=resolve);
  return turn.then(()=>{req.headers['X-Test-Run-Id']=RUN;req.headers['X-Sandbox-Secret']=env('SANDBOX_SECRET');
    req.continue(res=>{row.http=res.statusCode;row.eco=res.headers?.['x-test-run-id']===RUN;release();});});
});}
describe('[TC-M06-018] configuración y alerta',()=>{
  beforeEach(interceptar);
  afterEach(()=>{cy.get('body').then($body=>{$body[0].querySelectorAll('*').forEach(x=>{
      if(x.children.length===0&&!x.closest('[role="alert"]'))x.style.filter='blur(9px)';
      if(x.tagName==='IMG'||x.tagName==='CANVAS')x.style.filter='blur(16px)';});});
    cy.writeFile(DIR+'/G40-UI-018-01.json',acta);cy.screenshot('G40-UI-018-01',{capture:'fullPage',overwrite:true}).then(()=>{
      acta.captura=true;cy.writeFile(DIR+'/G40-UI-018-01.json',acta);});});
  it('[G40-UI-018-01] aviso y bandeja',()=>{
    if(!allowed)throw Error('BLOQUEO_G40: RUN o entorno inválido');
    cy.visit(FRONT+'/login');
    cy.window().then(win=>win.fetch(API+'/__g40_sonda__')).then(x=>x.json()).then(x=>expect(x.interceptado).eq(true));
    cy.wait('@sonda').its('response.statusCode').should('eq',200);
    cy.get('input[type="email"]').clear().type('g40-ui@local.invalid',{log:false});
    cy.get('input[type="password"]').clear().type('G40LocalDummy123!',{log:false});
    cy.get('button[type="submit"]').click();cy.wait('@login').its('response.statusCode').should('eq',200);
    cy.window().then(win=>{const base=new URL(FRONT).pathname.replace(/\/+$/,'');
      win.history.pushState({},'',base+'/finanzas/configuracion');win.dispatchEvent(new win.PopStateEvent('popstate'));});
    cy.location('pathname').should('include','/finanzas/configuracion');
    cy.wait('@configuracion',{requestTimeout:30000,responseTimeout:30000}).then(({response})=>{
      expect(response?.statusCode).eq(200);expect(response?.headers?.['x-test-run-id']).eq(RUN);
      expect(response?.body?.lineas_pendientes_cuenta).eq(EXPECTED);});
    const deadline=Date.now()+30000;
    function leerPanel(){return cy.get('body').then($body=>{
      const alert=[...$body[0].querySelectorAll(ALERT_SELECTOR)].find(el=>
        Cypress.dom.isVisible(el)&&TITLE.test(el.querySelector('.ds-alert__title')?.textContent?.trim()||''));
      if(alert){const match=alert.querySelector('.ds-alert__title').textContent.trim().match(TITLE);
        acta.panel_visible=true;acta.conteo=Number(match[1]);return;}
      if(Date.now()<deadline)return cy.wait(250).then(leerPanel);
    });}
    leerPanel();
    cy.get('body').then($body=>{const text=$body[0].innerText||'';
      acta.combinacion_visible=coincideCombinacion(text,SPECIES,SPECIES_NAME);});
    cy.get('body').then($body=>{const bell=$body[0].querySelector('button[aria-controls="notification-tray"]');
      if(bell)cy.wrap(bell).click();});
    let avisosNuevos=[];
    cy.wait('@notificaciones',{requestTimeout:30000,responseTimeout:30000}).then(({response})=>{
      expect(response?.statusCode).eq(200);expect(response?.headers?.['x-test-run-id']).eq(RUN);
      avisosNuevos=(response?.body?.items||[]).map((x,index)=>({index,id:x.id_notificacion,mensaje:String(x.mensaje)}))
        .filter(x=>!BASE_NOTICE_IDS.has(String(x.id)))
        .filter(x=>coincideCombinacion(x.mensaje,SPECIES,SPECIES_NAME));
      acta.avisos_nuevos_api=avisosNuevos.length;});
    function leerBandeja(restantes){return cy.get('body').then($body=>{
      const tray=$body[0].querySelector('#notification-tray');
      const abierta=Boolean(tray&&Cypress.dom.isVisible(tray));
      const articles=abierta?[...tray.querySelectorAll('article.notification-tray__item p')]:[];
      const visible=avisosNuevos.some(x=>articles[x.index]?.textContent?.trim()===x.mensaje.trim());
      if(restantes>0&&(!abierta||(avisosNuevos.length&&!visible)))
        return cy.wait(250).then(()=>leerBandeja(restantes-1));
      acta.bandeja_abierta=abierta;acta.avisos_en_ui=articles.length;acta.campana_visible=visible;
    });}
    leerBandeja(20);
    cy.get('body').then(()=>{acta.estado=acta.panel_visible&&acta.conteo===EXPECTED&&
      avisosNuevos.length>0&&acta.campana_visible?'APROBADO':'RECHAZADO';
      acta.motivo=`panel ${acta.panel_visible}, conteo ${acta.conteo}, avisos nuevos API ${acta.avisos_nuevos_api}, bandeja abierta ${acta.bandeja_abierta}, avisos UI ${acta.avisos_en_ui}, combinación visible ${acta.campana_visible}`;
      if(acta.host_bloqueado||acta.peticiones.some(x=>x.http!=null&&!x.eco)){
        acta.estado='NO_CONCLUYENTE';acta.motivo='Host o eco RUN inesperado';}});
  });
});
