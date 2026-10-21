// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

const API = String(Cypress.env('API_BASE') || '').replace(/\/+$/, '');
const RUN = Cypress.env('RUN_ID');
const sensores = Cypress.env('SENSORES') || [];
let cola = Promise.resolve();
const fuera = [];
const entregas = [];
function instalar() {
  cy.intercept({ url: `${API}/**` }, req => {
    let liberar;
    const turno = cola;
    cola = new Promise(resolve => { liberar = resolve; });
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN;
      req.headers['X-Sandbox-Secret'] = Cypress.env('SANDBOX_SECRET');
      req.continue(res => { if (req.url.includes('/iot/monitoreo/dashboard')) entregas.push(Date.now()); if (req.method !== 'OPTIONS' && res.headers['x-test-run-id'] !== RUN) fuera.push(req.url); liberar(); });
    });
  });
  cy.intercept({ method: 'GET', url: `${API}/iot/monitoreo/dashboard*` }).as('dashboard');
}
function observarCanal(win) {
  const WS = win.WebSocket;
  if (WS) win.WebSocket = class extends WS { constructor(url, ...resto) { const u = new URL(String(url), win.location.href); if (!['localhost', '127.0.0.1'].includes(u.hostname)) { win.__qaPushSinSandbox = true; throw Error('PRE: WebSocket sin contrato de sandbox verificable'); } super(url, ...resto); this.addEventListener('message', () => entregas.push(Date.now())); } };
  const ES = win.EventSource;
  if (ES) win.EventSource = class extends ES { constructor(url, ...resto) { const u = new URL(String(url), win.location.href); if (!['localhost', '127.0.0.1'].includes(u.hostname)) { win.__qaPushSinSandbox = true; throw Error('PRE: EventSource sin contrato de sandbox verificable'); } super(url, ...resto); this.addEventListener('message', () => entregas.push(Date.now())); } };
}
describe('TC-M03-G100 - TC-M03-195 throttling visual', () => {
  before(() => {
    if (Cypress.env('AUTORIZADO_RUN') !== 'SI' || Cypress.env('QA_AUTORIZADO') !== 'SI' || Cypress.env('AMBIENTE') !== 'TEST' || String(Cypress.env('AUTORIZACION') || '').length < 8 || !RUN || !/^https:\/\//.test(API) || API !== Cypress.env('API_TEST_BASE')) throw Error('BLOQUEO_G100');
    instalar();
    cy.visit(urlFrontendQA('/login'), { onBeforeLoad: observarCanal });
    cy.get('input[type="email"]').type(Cypress.env('PROD_EMAIL'), { log: false });
    cy.get('input[type="password"]').type(Cypress.env('PROD_PASSWORD'), { log: false });
    cy.get('button[type="submit"]').click();
    cy.visit(urlFrontendQA('/telemetria/monitoreo'), { onBeforeLoad: observarCanal });
    cy.wait('@dashboard').its('response.statusCode').should('eq', 200);
    cy.get('input[type="number"]').first().clear().type(String(Cypress.env('ID_INFRA')));
    cy.wait('@dashboard');
  });
  it('[TC-M03-195][ASSERT] máximo una actualización visual por sensor cada 2 s, indicador y último dato', () => {
    cy.window().then(win => { if (win.__qaPushSinSandbox) throw Error('PRE: ráfaga push no aislable con contrato actual'); });
    const inicioEntregas = entregas.length;
    const eventos = Object.fromEntries(sensores.map(s => [s.id, []]));
    const observadores = [];
    let indicador = false, operativa = false;
    cy.window().then(win => {
      for (const s of sensores) {
        const card = [...win.document.querySelectorAll('button.ds-option')].find(e => e.textContent.includes(s.nombre));
        expect(card, `tarjeta ${s.id}`).to.exist;
        let ultimo = card.querySelector('[role="img"]')?.getAttribute('aria-label');
        const observer = new win.MutationObserver(() => {
          const actual = card.querySelector('[role="img"]')?.getAttribute('aria-label');
          if (actual !== ultimo) { eventos[s.id].push(win.performance.now()); ultimo = actual; }
        });
        observer.observe(card, { subtree: true, attributes: true, characterData: true, childList: true });
        observadores.push(observer);
      }
      const indicadorObs = new win.MutationObserver(() => { if (win.document.body.textContent.includes('Sincronizando datos...')) indicador = true; });
      indicadorObs.observe(win.document.body, { subtree: true, characterData: true, childList: true });
      observadores.push(indicadorObs);
      const dialogoObs = new win.MutationObserver(() => { if (win.document.querySelector('[role="dialog"]')) operativa = true; });
      dialogoObs.observe(win.document.body, { subtree: true, childList: true });
      observadores.push(dialogoObs);
      win.setTimeout(() => {
        const card = [...win.document.querySelectorAll('button.ds-option')].find(e => e.textContent.includes(sensores[0].nombre));
        card?.click();
        win.setTimeout(() => {
          win.document.querySelector('[role="dialog"] button[aria-label]')?.click();
        }, 100);
      }, 300);
    });
    cy.request({ followRedirect: false,  method: 'POST', url: Cypress.env('CONTROL_URL'), headers: { 'X-QA-Key': Cypress.env('CONTROL_KEY') }, log: false }).then(r => {
      if (!r.body.accepted || !r.body.visible) throw Error(`PRE: ráfaga real no procesada/observable en backend (${JSON.stringify(r.body)})`);
      expect(r.body.count, '30 lecturas procesadas').to.eq(sensores.length * 10);
      expect(r.body.latest).to.eq(35);
    });
    cy.wait(5000);
    cy.then(() => {
      observadores.forEach(o => o.disconnect());
      const rafaga = entregas.slice(inicioEntregas);
      if (rafaga.length < 3 || rafaga[2] - rafaga[0] > 2000) throw Error(`PRE: no se observaron al menos tres entregas reales en dos segundos (${rafaga.length})`);
      expect(indicador, 'indicador Sincronizando datos... durante la ráfaga').to.eq(true);
      expect(operativa, 'tarjeta operativa durante la ráfaga').to.eq(true);
      for (const s of sensores) {
        const intervalos = eventos[s.id].slice(1).map((t, i) => t - eventos[s.id][i]);
        expect(intervalos.every(ms => ms >= 2000), `sensor ${s.id}: intervalos ${intervalos}`).to.eq(true);
        expect(eventos[s.id].length, `sensor ${s.id} actualizado visualmente`).to.be.greaterThan(0);
      }
      expect(fuera, 'sin solicitudes fuera del RUN').to.have.length(0);
    });
    for (const s of sensores) cy.contains('button.ds-option', s.nombre).find('[role="img"]').should('have.attr', 'aria-label').and('include', '35');
  });
});
