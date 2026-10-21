// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

// Sin stubs: se espera el vencimiento natural de JWT y refresh cookie.
const env=k=>Cypress.env(k);
const API=String(env('API_BASE')||'').replace(/\/+$/,'');
const RUN=env('RUN_ID');
let cola=Promise.resolve();
const fugas=[];
let respuestasDashboard=0;
function sandbox(){
  cy.intercept({url:`${API}/**`},req=>{
    let liberar;const turno=cola;cola=new Promise(resolve=>{liberar=resolve;});
    return turno.then(()=>{
      req.headers['X-Test-Run-Id']=RUN;req.headers['X-Sandbox-Secret']=env('SANDBOX_SECRET');
      req.continue(res=>{if(req.method!=='OPTIONS'&&res.headers['x-test-run-id']!==RUN)fugas.push(req.url);if(req.url.includes('/iot/monitoreo/dashboard'))respuestasDashboard++;liberar();});
    });
  });
  cy.intercept({method:'POST',url:`${API}/sesiones/`}).as('login');
  cy.intercept({method:'GET',url:`${API}/iot/monitoreo/dashboard*`}).as('dashboard');
}
function ingresar(){
  cy.visit(urlFrontendQA('/login'));
  cy.get('input[type="email"]').type(env('PROD_EMAIL'),{log:false});
  cy.get('input[type="password"]').type(env('PROD_PASSWORD'),{log:false});
  cy.get('button[type="submit"]').click();
  return cy.wait('@login').then(i=>{expect(i.response?.statusCode,'login').to.eq(200);expect(i.response?.headers['x-test-run-id'],'sandbox login').to.eq(RUN);return i.response.body;});
}
function esperarRechazo(deadline){
  if(Date.now()>deadline)throw Error('PRE-186-02: no se observó expiración natural dentro del límite');
  return cy.wait('@dashboard',{timeout:45000}).then(i=>{
    expect(i.response?.headers['x-test-run-id'],'sandbox dashboard').to.eq(RUN);
    if(i.response?.statusCode===401)return i;
    expect(i.response?.statusCode,'polling previo a expiración').to.eq(200);
    return esperarRechazo(deadline);
  });
}
describe('TC-M03-G95 — TC-M03-186',()=>{
  before(()=>{if(env('AUTORIZADO_RUN')!=='SI'||!RUN||!/^https:\/\//.test(API))throw Error('BLOQUEO_G95');sandbox();});
  it('[TC-M03-186] expiración real durante monitoreo activo y recuperación tras reingresar',function(){
    this.timeout(Number(env('MAX_ESPERA_MS'))+180000);
    let inicial;
    ingresar().then(login=>{
      const expira=Number(login.expira_en);
      expect(expira,'PRE-186-01: JWT con caducidad real').to.be.greaterThan(0);
      expect((expira+90)*1000,'PRE-186-02: caducidad dentro del límite autorizado').to.be.lessThan(Number(env('MAX_ESPERA_MS')));
    });
    cy.visit(urlFrontendQA('/telemetria/monitoreo'));
    cy.wait('@dashboard').then(i=>{
      expect(i.response?.statusCode).to.eq(200);
      expect(i.response?.headers['x-test-run-id']).to.eq(RUN);
      inicial=i.response.body;
      expect(inicial.resumen_unidades.some(u=>Number(u.id_infraestructura)===Number(env('ID_UNIDAD'))),'PRE-186-03: unidad activa').to.eq(true);
      const nombre=inicial.resumen_unidades.find(u=>Number(u.id_infraestructura)===Number(env('ID_UNIDAD'))).nombre_infraestructura;
      const sensor=inicial.sensores.find(s=>Number(s.id_sensor)===Number(env('ID_SENSOR')));
      expect(sensor,'PRE-186-03: sensor visible').to.exist;
      cy.contains(nombre).should('be.visible');
      cy.contains('button.ds-option',sensor.nombre_sensor).should('be.visible').within(()=>{
        cy.get('[role="img"][aria-label]').should('have.attr','aria-label').and('include',String(sensor.ultimo_valor));
      }).screenshot('TC-M03-186_dashboard_antes');
    });
    cy.then(()=>esperarRechazo(Date.now()+Number(env('MAX_ESPERA_MS'))));
    cy.url({timeout:30000}).should('include','/login');
    cy.contains(/sesión expirada/i).should('be.visible'); // UI-186-02
    cy.then(()=>{const antes=respuestasDashboard;cy.wait(35000).then(()=>expect(respuestasDashboard,'UI-186-01: polling detenido').to.eq(antes));});
    ingresar();
    cy.visit(urlFrontendQA('/telemetria/monitoreo'));
    cy.wait('@dashboard').then(i=>{
      expect(i.response?.statusCode,'UI-186-04: recarga con GET real').to.eq(200);
      expect(i.response?.headers['x-test-run-id']).to.eq(RUN);
      const nueva=i.response.body;
      const antes=inicial.resumen_unidades.find(u=>Number(u.id_infraestructura)===Number(env('ID_UNIDAD')));
      const despues=nueva.resumen_unidades.find(u=>Number(u.id_infraestructura)===Number(env('ID_UNIDAD')));
      const sensor=nueva.sensores.find(s=>Number(s.id_sensor)===Number(env('ID_SENSOR')));
      expect(despues,'UI-186-03: unidad visual conservada').to.exist;
      expect(despues.nombre_infraestructura,'UI-186-03: identidad visual conservada').to.eq(antes.nombre_infraestructura);
      expect(sensor,'UI-186-04: sensor de la respuesta más reciente').to.exist;
      cy.contains(despues.nombre_infraestructura).should('be.visible');
      cy.contains('button.ds-option',sensor.nombre_sensor).should('be.visible').within(()=>{
        cy.get('[role="img"][aria-label]').should('have.attr','aria-label').and('include',String(sensor.ultimo_valor));
      }).screenshot('TC-M03-186_dashboard_recargado');
    });
    cy.then(()=>expect(fugas,'solicitudes fuera de sandbox').to.have.length(0));
  });
});
