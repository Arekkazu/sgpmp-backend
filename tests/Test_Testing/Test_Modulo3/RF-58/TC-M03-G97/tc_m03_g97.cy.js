// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

const env = k => Cypress.env(k);
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN = env('RUN_ID');
const ROLE = env('ROLE');
let cola = Promise.resolve();
const fugas = [];
// Última respuesta del dashboard recibida por la vista (fuente del estado que debe representar).
let ultimaVista = null;
// Semáforo RF-58 → indicadores válidos en pantalla: etiqueta de la interfaz (SemaforoPill) o el nombre del estado.
const ETIQUETAS = { VERDE: ['normal', 'verde'], AMARILLO: ['advertencia', 'amarillo'], ROJO: ['fuera de rango', 'rojo'], GRIS: ['sin señal', 'gris'] };
function indicadoresSemaforo(raiz) {
  const out = [];
  const w = raiz.ownerDocument.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const t = n.nodeValue.trim().toLowerCase();
    const estado = Object.keys(ETIQUETAS).find(k => ETIQUETAS[k].includes(t));
    if (estado) out.push({ estado, el: n.parentElement });
  }
  return out;
}
function estadoDelSensor() {
  let cuerpo = ultimaVista;
  if (typeof cuerpo === 'string') { try { cuerpo = JSON.parse(cuerpo); } catch (e) { cuerpo = null; } }
  return ((cuerpo && cuerpo.sensores) || []).find(s => Number(s.id_sensor) === Number(env('ID_SENSOR')))?.estado_semaforo;
}
function sandbox() {
  cy.intercept({ url: `${API}/**` }, req => {
    let liberar;
    const turno = cola;
    cola = new Promise(resolve => { liberar = resolve; });
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN;
      req.headers['X-Sandbox-Secret'] = env('SANDBOX_SECRET');
      req.continue(res => {
        if (req.method !== 'OPTIONS' && res.headers['x-test-run-id'] !== RUN) fugas.push(req.url);
        if (/\/iot\/monitoreo\/dashboard/.test(req.url) && res.statusCode === 200) ultimaVista = res.body;
        liberar();
      });
    });
  });
  cy.intercept({ method: 'GET', url: `${API}/iot/monitoreo/dashboard*` }).as('dashboard');
}
function tarjeta() { return cy.contains('button', env('NOMBRE_SENSOR')); }
function unidad() { return cy.contains('section', env('NOMBRE_UNIDAD')); }

describe('TC-M03-G97 — RF-58 / CU04', () => {
  before(() => {
    if (env('AUTORIZADO_RUN') !== 'SI' || !RUN || !/^https:\/\//.test(API) || !['PROD', 'ENG', 'VET'].includes(ROLE)) throw Error('BLOQUEO_G97');
    sandbox();
    cy.visit(urlFrontendQA('/login'), { onBeforeLoad(win) {
      win.localStorage.clear(); win.sessionStorage.clear();
      if (win.indexedDB?.databases) win.indexedDB.databases().then(dbs => dbs.forEach(d => d.name && win.indexedDB.deleteDatabase(d.name)));
    } });
    cy.get('input[type="email"]').type(env('EMAIL'), { log: false });
    cy.get('input[type="password"]').type(env('PASSWORD'), { log: false });
    cy.get('button[type="submit"]').click();
    cy.visit(urlFrontendQA('/telemetria/monitoreo'));
    cy.get('input[type="number"]').clear().type(String(env('ID_UNIDAD')));
    cy.wait('@dashboard').then(i => { expect(i.response?.headers['x-test-run-id']).to.eq(RUN); });
  });

  if (ROLE === 'PROD') {
    it('[TC-M03-188][ASSERT][UI-188-01] semaforo, valor con unidad y nombre descriptivo', () => {
      tarjeta().should('be.visible').within(() => {
        cy.contains(env('NOMBRE_SENSOR')).should('be.visible');
        cy.contains(env('UNIDAD_MEDIDA')).should('be.visible');
      });
      // La tarjeta muestra un único indicador de semáforo, visible y correspondiente al estado
      // que el dashboard entrega para este sensor (no basta una palabra en cualquier parte).
      tarjeta().should($t => {
        const estado = estadoDelSensor();
        expect(estado, 'estado_semaforo del sensor en la respuesta del dashboard').to.be.oneOf(Object.keys(ETIQUETAS));
        const marcas = indicadoresSemaforo($t[0]);
        expect(marcas.map(m => m.estado), 'indicadores de semáforo en la tarjeta').to.deep.eq([estado]);
        expect(Cypress.$(marcas[0].el).is(':visible'), 'indicador de semáforo visible').to.eq(true);
      });
      tarjeta().click();
      cy.get('[role="dialog"]').should('contain.text', String(Number(env('VALOR'))));
      cy.get('[role="dialog"] button').first().click();
      cy.then(() => expect(fugas).to.have.length(0));
    });
    it('[TC-M03-188][ASSERT][UI-188-02] ubicacion y alerta activa destacada', () => {
      unidad().within(() => { cy.get('svg.lucide-map-pin').should('exist'); cy.contains(/alerta/i).should('be.visible'); });
      tarjeta().within(() => cy.get('[aria-label]').filter((_, el) => /alerta/i.test(el.getAttribute('aria-label') || '')).should('exist'));
      cy.then(() => expect(fugas).to.have.length(0));
    });
    it('[TC-M03-188][ASSERT][UI-188-03] sin indicadores tecnicos visibles', () => {
      tarjeta().should('not.contain.text', 'dBm');
      tarjeta().click();
      cy.get('[role="dialog"]').should('not.contain.text', 'RSSI').and('not.contain.text', 'SNR').and('not.contain.text', 'Batería');
      cy.get('[role="dialog"] button').first().click();
      cy.then(() => expect(fugas).to.have.length(0));
    });
  }
  if (ROLE === 'ENG') {
    it('[TC-M03-189][ASSERT][UI-189-01] conectividad, bateria, RSSI, SNR y tiempo sin reporte', () => {
      tarjeta().should('be.visible').click();
      cy.get('[role="dialog"]').within(() => {
        cy.contains(/conectividad/i).should('be.visible');
        cy.contains(/bater[ií]a/i).should('be.visible');
        cy.contains('RSSI').should('be.visible');
        cy.contains('SNR').should('be.visible');
        cy.contains(/sin reporte/i).should('be.visible');
      });
      cy.then(() => expect(fugas).to.have.length(0));
    });
  }
  if (ROLE === 'VET') {
    it('[TC-M03-190][ASSERT][UI-190-01] biometria y alerta con contexto clinico', () => {
      unidad().should('be.visible');
      tarjeta().should('be.visible').click();
      cy.get('[role="dialog"]').within(() => {
        cy.contains(/biom[eé]tric|animal/i).should('be.visible');
        cy.contains(String(env('ID_ALERTA'))).should('be.visible');
        cy.contains(String(env('ID_ACTIVO'))).should('be.visible');
      });
      cy.get('[role="dialog"] button').first().click();
      cy.then(() => expect(fugas).to.have.length(0));
    });
    it('[TC-M03-190][ASSERT][UI-190-02] acceso al historial reciente del activo', () => {
      tarjeta().click();
      cy.get('[role="dialog"]').contains(/historial reciente/i).should('be.visible').click();
      cy.url().should('include', String(env('ID_ACTIVO')));
      cy.then(() => expect(fugas).to.have.length(0));
    });
  }
});
