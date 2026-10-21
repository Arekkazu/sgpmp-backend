// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

const env=k=>Cypress.env(k);
const API=String(env('API_BASE')||'').replace(/\/+$/,'');
const RUN=env('RUN_ID');
let cola=Promise.resolve();
const fugas=[];
function sandbox(){
  cy.intercept({url:`${API}/**`},req=>{
    let liberar;const turno=cola;cola=new Promise(resolve=>{liberar=resolve;});
    return turno.then(()=>{
      req.headers['X-Test-Run-Id']=RUN;req.headers['X-Sandbox-Secret']=env('SANDBOX_SECRET');
      req.continue(res=>{if(req.method!=='OPTIONS'&&res.headers['x-test-run-id']!==RUN)fugas.push(req.url);liberar();});
    });
  });
  cy.intercept({method:'GET',url:`${API}/iot/monitoreo/dashboard*`}).as('dashboard');
}
describe('TC-M03-G94 — TC-M03-185',()=>{
  before(()=>{
    if(env('AUTORIZADO_RUN')!=='SI'||!RUN||!/^https:\/\//.test(API))throw Error('BLOQUEO_G94');
    sandbox();
    cy.visit(urlFrontendQA('/login'),{onBeforeLoad(win){if(win.indexedDB?.databases)win.indexedDB.databases().then(dbs=>dbs.forEach(d=>d.name&&win.indexedDB.deleteDatabase(d.name)));}});
    cy.get('input[type="email"]').type(env('PROD_EMAIL'),{log:false});
    cy.get('input[type="password"]').type(env('PROD_PASSWORD'),{log:false});
    cy.get('button[type="submit"]').click();
    cy.visit(urlFrontendQA('/telemetria/monitoreo'));
    cy.wait('@dashboard').then(i=>{expect(i.response?.statusCode).to.eq(200);expect(i.response?.headers['x-test-run-id']).to.eq(RUN);});
  });
  it('[TC-M03-185][ASSERT][UI-185-01] mensaje exacto de usuario sin unidades',()=>{
    cy.contains('No tiene unidades productivas asignadas').should('be.visible').screenshot('TC-M03-185_sin_unidades');
    cy.then(()=>expect(fugas).to.have.length(0));
  });
  it('[TC-M03-185][ASSERT][UI-185-02] sugiere contactar al administrador y no muestra unidades ajenas',()=>{
    cy.contains(/(contact|comun[ií]quese|consulte).*(administrador)/i).should('be.visible');
    cy.get('section').filter((_,el)=>el.textContent.includes('GRIS')||el.textContent.includes('VERDE')).should('have.length',0);
    cy.then(()=>expect(fugas).to.have.length(0));
  });
});
