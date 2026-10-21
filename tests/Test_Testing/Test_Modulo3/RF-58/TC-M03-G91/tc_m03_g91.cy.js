// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

// Respuestas del producto siempre reales. Solo se interrumpe la entrega de
// solicitudes de polling para reproducir una pérdida de actualización.
const env = (k) => Cypress.env(k);
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN = env('RUN_ID');
const estado = { token: '', perdida: false, online: true, wallNow: 0, fuera: [], interrupciones: 0 };
let cola = Promise.resolve();

function sandbox() {
  cy.intercept({ url: `${API}/**` }, (req) => {
    let liberar;
    const turno = cola;
    cola = new Promise((resolve) => { liberar = resolve; });
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN;
      req.headers['X-Sandbox-Secret'] = env('SANDBOX_SECRET');
      if (estado.perdida && req.method === 'GET' && req.url.includes('/iot/monitoreo/dashboard')) {
        estado.interrupciones += 1;
        req.destroy();
        liberar();
        return;
      }
      req.continue((res) => {
        if (req.method !== 'OPTIONS' && res.headers['x-test-run-id'] !== RUN) estado.fuera.push(req.url);
        liberar();
      });
    });
  });
  cy.intercept({ method: 'POST', url: `${API}/sesiones/` }).as('login');
  cy.intercept({ method: 'GET', url: `${API}/iot/monitoreo/dashboard*` }).as('dashboard');
}
const card = (k) => cy.contains('button.ds-option', env(`SENSOR_${k}_NOMBRE`), { timeout: 20000 });
function valor(k, esperado) {
  card(k).find('[role="img"][aria-label]').should('have.attr', 'aria-label').and('include', String(esperado));
}
function api(metodo, ruta, body) {
  return cy.request({ followRedirect: false,  method: metodo, url: `${API}${ruta}`, failOnStatusCode: false, log: false,
    headers: { 'X-Test-Run-Id': RUN, 'X-Sandbox-Secret': env('SANDBOX_SECRET'),
      ...(metodo === 'GET' ? { Authorization: `Bearer ${estado.token}` } : {}) },
    ...(body ? { body } : {}) }).then((r) => {
      expect(r.headers['x-test-run-id'], 'respuesta real dentro del sandbox').to.eq(RUN);
      return r;
    });
}
function lecturaB(k) {
  return api('POST', '/iot/telemetria', {
    device_id: Number(env('DEVICE_ID')), sensor_id: Number(env(`SENSOR_${k}_ID`)),
    tipo_variable: 'TEMPERATURA_AMBIENTAL', valor: 26, unidad: '°C',
    timestamp_captura: new Date(estado.wallNow + 1000).toISOString(),
    access_key: env('ACCESS_KEY'), origen: 'TIEMPO_REAL', frecuencia_muestreo: 5,
    estado_conectividad: true,
  }).then((r) => { expect(r.status, 'ingesta real de B').to.eq(201); });
}
function confirmarB(k) {
  return api('GET', `/iot/monitoreo/dashboard?id_infraestructura=${env('ID_INFRA')}&por_pagina=50`)
    .then((r) => {
      expect(r.status).to.eq(200);
      const s = r.body.sensores.find((x) => Number(x.id_sensor) === Number(env(`SENSOR_${k}_ID`)));
      expect(s, 'sensor del RUN en backend').to.be.an('object');
      expect(Number(s.ultimo_valor), 'lectura B persistida').to.eq(26);
    });
}

describe('TC-M03-G91 — recuperación del dashboard', () => {
  before(() => {
    if (env('AUTORIZADO_RUN') !== 'SI' || !RUN || !/^https:\/\//.test(API)) throw new Error('BLOQUEO_G91');
    sandbox();
    cy.visit(urlFrontendQA('/login'), { onBeforeLoad(win) {
      if (win.indexedDB?.databases) win.indexedDB.databases().then((dbs) => dbs.forEach((d) => d.name && win.indexedDB.deleteDatabase(d.name)));
    } });
    cy.get('input[type="email"]').type(env('PROD_EMAIL'), { log: false });
    cy.get('input[type="password"]').type(env('PROD_PASSWORD'), { log: false });
    cy.get('button[type="submit"]').click();
    cy.wait('@login').then((i) => { expect(i.response?.statusCode).to.eq(200); estado.token = i.response.body.token; });
    cy.then(() => { estado.wallNow = Date.now(); });
    cy.visit(urlFrontendQA('/telemetria/monitoreo'));
    cy.wait('@dashboard').its('response.statusCode').should('eq', 200);
    cy.get('input[type="number"]').first().clear().type(String(env('ID_INFRA')));
    cy.wait('@dashboard').its('response.statusCode').should('eq', 200);
    cy.clock();
    // Recrear el intervalo de polling bajo el reloj de Cypress.
    cy.contains('button', 'Auto ON').click();
    cy.contains('button', 'Auto OFF').click();
    cy.then(() => { expect(estado.fuera).to.have.length(0); });
  });

  it('[TC-M03-179][PRE][PRE-179-02] B real en backend mientras la vista conserva A', () => {
    valor('179', 25);
    cy.then(() => { estado.perdida = true; });
    lecturaB('179');
    confirmarB('179');
    valor('179', 25);
  });
  it('[TC-M03-179][ASSERT][UI-179-01] A permanece visible sin nulos durante pérdida', () => {
    cy.tick(720000);
    valor('179', 25);
    card('179').should('not.contain.text', 'sin dato').screenshot('TC-M03-179_lectura_A_retenida');
    cy.then(() => expect(estado.interrupciones, 'polling perdido').to.be.greaterThan(0));
  });
  it('[TC-M03-179][ASSERT][UI-179-02] tras 12 min recupera B sin recarga manual', () => {
    cy.then(() => { estado.perdida = false; });
    cy.tick(31000);
    valor('179', 26);
    card('179').screenshot('TC-M03-179_resincronizado_B');
    cy.then(() => expect(estado.fuera).to.have.length(0));
  });

  it('[TC-M03-194][PRE][PRE-194-02] desconexión observada y B real en backend', () => {
    valor('194', 25);
    cy.window().then((win) => {
      Object.defineProperty(win.navigator, 'onLine', { configurable: true, get: () => estado.online });
      estado.online = false;
      win.dispatchEvent(new Event('offline'));
    });
    cy.contains('Sin conexión').should('be.visible');
    lecturaB('194');
    confirmarB('194');
  });
  it('[TC-M03-194][ASSERT][UI-194-01] indicador desaparece al reconectar', () => {
    cy.window().then((win) => { estado.online = true; win.dispatchEvent(new Event('online')); });
    cy.contains('Sin conexión').should('not.exist');
  });
  it('[TC-M03-194][ASSERT][UI-194-02] B aparece sin recarga manual ni nulos', () => {
    cy.tick(31000);
    valor('194', 26);
    card('194').should('not.contain.text', 'sin dato').screenshot('TC-M03-194_reconexion_B');
    cy.then(() => expect(estado.fuera).to.have.length(0));
  });
});
