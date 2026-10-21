// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

const env = (k) => Cypress.env(k);
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN = env('RUN_ID');
let cola = Promise.resolve();
const fugas = [];

function sandbox() {
  cy.intercept({ url: `${API}/**` }, (req) => {
    let liberar;
    const turno = cola;
    cola = new Promise(resolve => { liberar = resolve; });
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN;
      req.headers['X-Sandbox-Secret'] = env('SANDBOX_SECRET');
      req.continue(res => {
        if (req.method !== 'OPTIONS' && res.headers['x-test-run-id'] !== RUN) fugas.push(req.url);
        liberar();
      });
    });
  });
  cy.intercept({ method:'GET', url:`${API}/iot/monitoreo/dashboard*` }).as('dashboard');
}
function entrar() {
  cy.visit(urlFrontendQA('/login'), { onBeforeLoad(win) { if(win.indexedDB?.databases) win.indexedDB.databases().then(dbs => dbs.forEach(d => d.name && win.indexedDB.deleteDatabase(d.name))); } });
  cy.get('input[type="email"]').type(env('PROD_EMAIL'), {log:false});
  cy.get('input[type="password"]').type(env('PROD_PASSWORD'), {log:false});
  cy.get('button[type="submit"]').click();
  cy.visit(urlFrontendQA('/telemetria/monitoreo'));
  cy.wait('@dashboard').then(i => {
    expect(i.response?.statusCode).to.eq(200);
    expect(i.response?.headers['x-test-run-id']).to.eq(RUN);
  });
}
describe('TC-M03-G93 — TC-M03-184', () => {
  before(() => { if(env('AUTORIZADO_RUN')!=='SI'||!RUN||!/^https:\/\//.test(API)) throw Error('BLOQUEO_G93'); sandbox(); entrar(); });
  it('[TC-M03-184][ASSERT][UI-184-01] unidad sin lecturas visible en GRIS con mensaje', () => {
    cy.get('input[type="number"]').first().clear().type(String(env('ID_UNIDAD')));
    cy.wait('@dashboard').then(i => expect(i.response?.headers['x-test-run-id']).to.eq(RUN));
    cy.contains(env('NOMBRE_UNIDAD')).should('be.visible');
    cy.contains(env('NOMBRE_UNIDAD')).closest('section').should('contain.text','GRIS').and('contain.text','Sin datos disponibles').screenshot('TC-M03-184_unidad_sin_datos');
    cy.then(() => expect(fugas).to.have.length(0));
  });
  it('[TC-M03-184][ASSERT][UI-184-02] segunda unidad sin señal sigue visible con fecha histórica', function () {
    if (!env('ID_SEGUNDA')) this.skip();
    cy.get('input[type="number"]').first().clear().type(String(env('ID_SEGUNDA')));
    cy.wait('@dashboard').then(i => {
      expect(i.response?.statusCode).to.eq(200);
      expect(i.response?.headers['x-test-run-id']).to.eq(RUN);
      const u=i.response.body.resumen_unidades.find(x=>Number(x.id_infraestructura)===Number(env('ID_SEGUNDA')));
      expect(u).to.exist;
      cy.contains(u.nombre_infraestructura).closest('section').should('be.visible').and('contain.text','GRIS').and('contain.text','Sin datos disponibles');
      if(u.ultimo_dato_recibido) cy.contains(u.nombre_infraestructura).closest('section').should('contain.text','último dato');
    });
    cy.then(() => expect(fugas).to.have.length(0));
  });
});
