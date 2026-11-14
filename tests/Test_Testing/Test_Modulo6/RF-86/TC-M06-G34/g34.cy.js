// RF-86 TC-M06-006: panel real del Contador dentro del mismo sandbox.
const e = k => Cypress.env(k);
const API = String(e('API_BASE') || '').replace(/\/+$/, '');
const FRONT = String(e('FRONT_BASE') || '').replace(/\/+$/, '');
const RUN = String(e('RUN_ID') || '');
const DIR = e('ARTIFACTS_DIR');
const A = String(e('ACTIVO_A') || ''), B = String(e('ACTIVO_B') || ''), PERIODO = String(e('PERIODO_ID') || '');
const IA = String(e('IDENTIFICADOR_A') || ''), IB = String(e('IDENTIFICADOR_B') || '');
const autorizado = /^RUN-G34-V\d+-\d{8}-\d{6}$/.test(RUN) &&
  API === 'https://api.inmero.co/api-sgpmp-test' &&
  FRONT === 'https://api.inmero.co/sigab-test' && Boolean(DIR && A && B && IA && IB && PERIODO &&
    e('PROD_LOGIN_TOKEN') && e('SANDBOX_SECRET'));
const acta = { caso:'TC-M06-006', id:'G34-UI-006-01', estado:'NO_CONCLUYENTE',
  motivo:'No iniciado', periodo:PERIODO, activo_a:A, activo_b:B, fila_a:null, fila_b:null,
  texto_fila_a:null, texto_fila_b:null,
  mediciones_http:null, captura:false, solicitudes:0, peticiones:[], login_sonda:false,
  login_resuelto_localmente:false, host_bloqueado:null };
const rutaApi = url => {
  const u = new URL(url); return u.pathname.slice(new URL(API).pathname.length).split('?')[0] || '/';
};
const sanear = x => String(x ?? '').replace(/Bearer\s+\S+|[\w.+-]+@[\w.-]+|eyJ[\w-]+\.[\w-]+\.[\w-]+/gi,'[RESERVADO]').slice(0,160);
let cola = Promise.resolve();
function interceptar() {
  cy.intercept({ url: /^https?:\/\/(?:www\.)?api\.inmero\.co(?::\d+)?\//, middleware:true }, req => {
    const url = new URL(req.url);
    const frontal = new URL(FRONT || 'https://api.inmero.co/sigab-test');
    if (req.method === 'GET' && url.origin === frontal.origin &&
        (url.pathname === frontal.pathname || url.pathname.startsWith(frontal.pathname + '/'))) {
      req.continue();
      return;
    }
    if (!['api.inmero.co','www.api.inmero.co'].includes(url.hostname) ||
        !(url.pathname === new URL(API || 'https://api.inmero.co/api-sgpmp-test').pathname ||
          url.pathname.startsWith(new URL(API || 'https://api.inmero.co/api-sgpmp-test').pathname + '/'))) {
      acta.host_bloqueado = sanear(url.origin + url.pathname
        .replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi,'[ID]')
        .replace(/\/\d+(?=\/|$)/g,'/[ID]'));
      acta.estado = 'NO_CONCLUYENTE';
      acta.motivo = 'Host o base API inesperada: ' + acta.host_bloqueado;
      req.reply({ forceNetworkError:true });
      return;
    }
    if (++acta.solicitudes > 16) {
      acta.estado='NO_CONCLUYENTE';acta.motivo='Límite UI API 16';
      req.reply({forceNetworkError:true});return;
    }
    const ruta=rutaApi(req.url);
    const registro={metodo:req.method,ruta,http:null,eco:false,local:false};
    acta.peticiones.push(registro);
    if (req.method === 'GET' && ruta === '/__g34_sonda__') {
      req.alias='loginSonda';registro.http=200;registro.eco=true;registro.local=true;
      req.reply({statusCode:200,headers:{'x-test-run-id':RUN},body:{interceptado:true}});
      return;
    }
    if (req.method === 'POST' && ruta === '/sesiones/') {
      req.alias='login';
      registro.http=200;registro.eco=true;registro.local=true;
      acta.login_resuelto_localmente=true;
      req.reply({statusCode:200,headers:{'x-test-run-id':RUN},body:{token:e('PROD_LOGIN_TOKEN')}});
      return;
    }
    if (!['GET','OPTIONS'].includes(req.method)) {
      acta.estado='NO_CONCLUYENTE';acta.motivo='Escritura UI inesperada '+req.method+' '+ruta;
      req.reply({forceNetworkError:true});return;
    }
    if (ruta === '/finanzas/periodos/'+PERIODO+'/mediciones') req.alias='medicionesPeriodo';
    else if (ruta === '/finanzas/periodos/'+PERIODO+'/eventos-pendientes') req.alias='pendientesPeriodo';
    else if (ruta.startsWith('/finanzas/')) req.alias='finanzas';
    let liberar;const turno=cola;cola=new Promise(resolve=>{liberar=resolve;});
    return turno.then(()=>{
      req.headers['X-Test-Run-Id']=RUN;
      req.headers['X-Sandbox-Secret']=e('SANDBOX_SECRET');
      req.continue(res=>{
        registro.http=res.statusCode;
        registro.eco=res.headers?.['x-test-run-id']===RUN;
        if (ruta === '/finanzas/periodos/'+PERIODO+'/mediciones') acta.mediciones_http=res.statusCode;
        liberar();
      });
    });
  });
}
const fila = (body,id,identificador='') => {
  const candidatas=[...body.querySelectorAll('tr,[role="row"],article,li')]
    .filter(x=>new RegExp('(?:^|\\D)'+id+'(?:\\D|$)').test(x.innerText||'') ||
      (identificador.length>=3 && (x.innerText||'').includes(identificador)));
  return candidatas.sort((x,y)=>(x.innerText||'').length-(y.innerText||'').length)[0]??null;
};
const estadoFila = x => x ? (x.querySelector?.('td:nth-child(9) [class*="badge"],td:nth-child(9)')?.innerText ||
  x.innerText || '').match(/Medición pendiente|Medido|Sin medición/ig)?.[0] ?? 'SIN_ESTADO' : 'SIN_FILA';
const textoFila = (x, identificador) => x ? sanear(identificador)+' | '+estadoFila(x)+' | [RESTO_DE_FILA_OMITIDO]' : 'SIN_FILA';
const evaluarFilas = (a,b) => {
  if (!b) return {estado:'NO_CONCLUYENTE',motivo:'No se cargó la fila B después de la lectura de mediciones y la búsqueda'};
  if (!a) return {estado:'NO_CONCLUYENTE',motivo:'No se cargó la fila A después de confirmar B'};
  const bienA=estadoFila(a)==='Medición pendiente';
  const bienB=estadoFila(b)==='Medido';
  return {estado:bienA&&bienB?'APROBADO':'RECHAZADO',motivo:bienA&&bienB?
    'Filas A y B visibles con estado esperado':sanear('A '+estadoFila(a)+'; B '+estadoFila(b))};
};
describe('[TC-M06-006] panel de medición M06',()=>{
  beforeEach(interceptar);
  afterEach(()=>{
    if (!acta.login_sonda || !acta.login_resuelto_localmente) {
      acta.estado='NO_CONCLUYENTE';acta.motivo='Intercept local del login no confirmado';
    }
    if (acta.peticiones.some(x=>x.http!=null && !x.eco)) {
      acta.estado='NO_CONCLUYENTE';acta.motivo='Respuesta API sin eco RUN';
    }
    if (acta.peticiones.some(x=>x.http>=500)) {
      acta.estado='NO_CONCLUYENTE';acta.motivo='API 5xx durante carga UI';
    }
    if (acta.host_bloqueado) {
      acta.estado='NO_CONCLUYENTE';acta.motivo='Host o base API inesperada: '+acta.host_bloqueado;
    }
    cy.get('body').then($body=>{
      const body=$body[0];
      body.querySelectorAll('input,button,nav,aside,#fin-periodo,.fin-periodo,[for="fin-periodo"]')
        .forEach(x=>{x.style.filter='blur(8px)';});
      const textos=body.ownerDocument.createTreeWalker(body,body.ownerDocument.defaultView.NodeFilter.SHOW_TEXT);
      while (textos.nextNode()) {
        if (/\bNIT\b|\b\d{8,12}(?:-\d)?\b/i.test(textos.currentNode.textContent||''))
          textos.currentNode.parentElement.style.filter='blur(8px)';
      }
      body.querySelectorAll('tr,[role="row"],article,li').forEach(x=>{
        if (x!==fila(body,A,IA) && x!==fila(body,B,IB)) x.style.filter='blur(8px)';
      });
      [fila(body,A,IA),fila(body,B,IB)].filter(Boolean).forEach(row=>{
        row.querySelectorAll('td,span,p,div').forEach(x=>{
          if (!/MEDICION_PENDIENTE|COMPLETADO|PROCESADO|Medici[oó]n pendiente|Medido|Measured/i.test(x.innerText||'')) x.style.filter='blur(8px)';
        });
      });
    });
    cy.writeFile(DIR+'/G34-UI-006-01.json',acta);
    cy.screenshot('G34-UI-006-01',{capture:'fullPage',overwrite:true}).then(()=>{
      acta.captura=true;cy.writeFile(DIR+'/G34-UI-006-01.json',acta);
    });
  });
  it('[TC-M06-006][ASSERT][G34-UI-006-01] A pendiente y B completado',()=>{
    if (!autorizado) throw Error('BLOQUEO_G34: entorno o autorización RUN inválido');
    acta.motivo='Comprobación UI iniciada';
    cy.visit(FRONT+'/login');
    cy.window().then(win=>win.fetch(API+'/__g34_sonda__',{
      headers:{'X-Test-Run-Id':RUN,'X-Sandbox-Secret':e('SANDBOX_SECRET')}
    })).then(res=>res.json()).then(body=>{
      expect(body.interceptado).to.eq(true);
    });
    cy.wait('@loginSonda',{requestTimeout:30000,responseTimeout:30000}).then(({response})=>{
      expect(response?.statusCode).to.eq(200);
      expect(response?.headers?.['x-test-run-id']).to.eq(RUN);
      acta.login_sonda=true;
    });
    cy.then(()=>expect(acta.login_sonda,'intercept de login activo').to.eq(true));
    cy.get('input[type="email"]').clear().type('g34-ui@local.invalid',{log:false});
    cy.get('input[type="password"]').clear().type('G34LocalDummy123!',{log:false});
    cy.get('button[type="submit"]').click();
    cy.wait('@login',{requestTimeout:30000,responseTimeout:30000}).then(({response})=>{
      expect(response?.statusCode).to.eq(200);
      expect(acta.login_resuelto_localmente).to.eq(true);
    });
    cy.window().then(win=>{
      const base=new URL(FRONT).pathname.replace(/\/+$/,'');
      win.history.pushState({},'',base+'/finanzas/medicion');
      win.dispatchEvent(new win.PopStateEvent('popstate'));
    });
    cy.location('pathname').should('include','/finanzas/medicion');
    const opcionPeriodo='#fin-periodo option[value="'+PERIODO+'"]';
    cy.on('fail',error=>{
      if (error.message.includes(opcionPeriodo)) {
        acta.estado='NO_CONCLUYENTE';
        acta.motivo='Período '+PERIODO+' no disponible en el selector';
      }
      throw error;
    });
    acta.motivo='Esperando período '+PERIODO+' en el selector';
    cy.get(opcionPeriodo,{timeout:30000}).should('exist');
    cy.get('#fin-periodo').select(PERIODO,{log:false}).should('have.value',PERIODO);
    cy.wait('@medicionesPeriodo',{requestTimeout:30000,responseTimeout:30000}).then(({response})=>{
      expect(response?.statusCode).to.eq(200);
      expect(response?.headers?.['x-test-run-id']).to.eq(RUN);
    });
    cy.wait('@pendientesPeriodo',{requestTimeout:30000,responseTimeout:30000}).then(({response})=>{
      expect(response?.statusCode).to.eq(200);
      expect(response?.headers?.['x-test-run-id']).to.eq(RUN);
    });
    cy.get('#medicion-buscar',{timeout:30000}).should('be.visible').clear().type(IB,{log:false});
    acta.motivo='Esperando fila B tras lectura de mediciones';
    cy.contains('tbody tr',IB,{timeout:30000}).should('be.visible').then($b=>{
      const b=$b[0];acta.fila_b=estadoFila(b);acta.texto_fila_b=textoFila(b,IB);
    });
    cy.get('#medicion-buscar').clear().type(IA,{log:false});
    cy.contains('tbody tr',IA,{timeout:30000}).should('be.visible').then($a=>{
      const a=$a[0];acta.fila_a=estadoFila(a);acta.texto_fila_a=textoFila(a,IA);
      const decision=evaluarFilas(a,{innerText:acta.fila_b});
      acta.estado=decision.estado;acta.motivo=decision.motivo;
    });
  });
});
