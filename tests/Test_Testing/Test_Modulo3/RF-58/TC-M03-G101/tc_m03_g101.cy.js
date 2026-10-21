// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

// Datos reales de SIGAB. La inyección local altera latencia/conectividad, jamás el cuerpo de respuesta.
const API = String(Cypress.env('API_BASE') || '').replace(/\/+$/, '');
const RUN = Cypress.env('RUN_ID');
const sensores = Cypress.env('SENSORES') || [];
const etiquetas = { VERDE: 'Normal', AMARILLO: 'Advertencia', ROJO: 'Fuera de rango', GRIS: 'Sin señal' };
const solicitudes = [];
const latencias = [];
const fuera = [];
let cola = Promise.resolve();
function instalar() {
  cy.intercept({ url: `${API}/**` }, req => {
    let liberar;
    const turno = cola;
    cola = new Promise(resolve => { liberar = resolve; });
    return turno.then(() => {
      const seguro = setTimeout(liberar, 30000);
      req.headers['X-Test-Run-Id'] = RUN;
      req.headers['X-Sandbox-Secret'] = Cypress.env('SANDBOX_SECRET');
      const dashboard = req.url.includes('/iot/monitoreo/dashboard');
      const inicio = Date.now();
      if (dashboard) solicitudes.push(inicio);
      req.continue(res => { clearTimeout(seguro); if (dashboard) latencias.push(Date.now() - inicio); if (req.method !== 'OPTIONS' && res.headers['x-test-run-id'] !== RUN) fuera.push(req.url); liberar(); });
    });
  });
  cy.intercept({ method: 'GET', url: `${API}/iot/monitoreo/dashboard*` }).as('dash');
}
function red(latency, offline = false) {
  return cy.then(() => Promise.resolve().then(async () => {
    await Cypress.automation('remote:debugger:protocol', { command: 'Network.enable', params: {} });
    return Cypress.automation('remote:debugger:protocol', {
    command: 'Network.emulateNetworkConditions',
    params: { offline, latency, downloadThroughput: -1, uploadThroughput: -1 },
    });
  }).catch(e => { throw Error(`PRE: control de red de navegador no disponible: ${e.message}`); }));
}
function esperarDash(n, timeout = 15000) {
  const tiempos = [];
  for (let i = 0; i < n; i++) cy.wait('@dash', { timeout }).then(x => {
    expect(x.response?.statusCode).to.eq(200);
    tiempos.push(Date.now());
  });
  return cy.then(() => tiempos);
}
function tarjeta() { return cy.contains('button.ds-option', sensores[0].nombre); }
function semaforo() { return tarjeta().find('[role="img"]').invoke('attr', 'aria-label'); }
function observarPush(win) {
  const WS = win.WebSocket;
  if (WS) win.WebSocket = class extends WS { constructor(url, ...resto) { const u = new URL(String(url), win.location.href); if (!['localhost', '127.0.0.1'].includes(u.hostname)) { win.__qaPushSinSandbox = true; throw Error('PRE: WebSocket sin contrato de sandbox verificable'); } super(url, ...resto); win.__qaPushCount = (win.__qaPushCount || 0) + 1; (win.__qaPushUrls ||= []).push(String(url)); (win.__qaPushAttempts ||= []).push(Date.now()); (win.__qaPushSockets ||= []).push(this); this.addEventListener('open', () => { win.__qaPushOpen = (win.__qaPushOpen || 0) + 1; }); this.addEventListener('close', () => { win.__qaPushOpen = Math.max(0, (win.__qaPushOpen || 0) - 1); }); } };
  const ES = win.EventSource;
  if (ES) win.EventSource = class extends ES { constructor(url, ...resto) { const u = new URL(String(url), win.location.href); if (!['localhost', '127.0.0.1'].includes(u.hostname)) { win.__qaPushSinSandbox = true; throw Error('PRE: EventSource sin contrato de sandbox verificable'); } super(url, ...resto); win.__qaPushCount = (win.__qaPushCount || 0) + 1; (win.__qaPushUrls ||= []).push(String(url)); (win.__qaPushAttempts ||= []).push(Date.now()); (win.__qaPushSockets ||= []).push(this); this.addEventListener('open', () => { win.__qaPushOpen = (win.__qaPushOpen || 0) + 1; }); this.addEventListener('error', () => { win.__qaPushOpen = Math.max(0, (win.__qaPushOpen || 0) - 1); }); } };
}

describe('TC-M03-G101 - niveles RF-58', { testIsolation: false }, () => {
  beforeEach(() => {
    cy.request({ followRedirect: false,  method: 'GET', url: Cypress.env('CONTROL_URL').replace(/\/ingest$/, '/guard/status'), headers: { 'X-QA-Key': Cypress.env('CONTROL_KEY') }, failOnStatusCode: false, log: false }).then(r => {
      if (r.status !== 200 || !r.body?.ok) throw Error('PRE: mantenimiento del sandbox falló; se omite el escenario dependiente');
    });
  });
  afterEach(() => {
    cy.then(() => Promise.resolve().then(() => Cypress.automation('remote:debugger:protocol', { command: 'Network.setBlockedURLs', params: { urls: [] } })).catch(() => null));
    cy.then(() => Promise.resolve().then(() => Cypress.automation('remote:debugger:protocol', { command: 'Network.emulateNetworkConditions', params: { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 } })).catch(() => null));
    cy.then(() => { if (fuera.length) throw Error(`PRE: ${fuera.length} respuestas sin eco del sandbox`); });
  });
  before(() => {
    if (Cypress.env('AUTORIZADO_RUN') !== 'SI' || Cypress.env('QA_AUTORIZADO') !== 'SI' || Cypress.env('AMBIENTE') !== 'TEST' || String(Cypress.env('AUTORIZACION') || '').length < 8 || !RUN || !/^https:\/\//.test(API) || API !== Cypress.env('API_TEST_BASE') || sensores.length !== 50) throw Error('BLOQUEO_G101');
    instalar();
    cy.visit(urlFrontendQA('/login'), { onBeforeLoad: observarPush });
    cy.get('input[type="email"]').type(Cypress.env('PROD_EMAIL'), { log: false });
    cy.get('input[type="password"]').type(Cypress.env('PROD_PASSWORD'), { log: false });
    cy.get('button[type="submit"]').click();
    cy.visit(urlFrontendQA('/telemetria/monitoreo'), { onBeforeLoad: observarPush });
    cy.wait('@dash').its('response.statusCode').should('eq', 200);
    cy.get('input[type="number"]').first().clear().type(String(Cypress.env('ID_INFRA')));
    cy.wait('@dash');
    cy.get('button.ds-option').should('have.length.at.least', 50);
  });

  it('[TC-M03-196][ASSERT] Nivel 0: confirmación RF-53 a vista <=500 ms, 50 sensores', () => {
    let cambio = null, previo = null;
    cy.window().then(win => {
      const card = [...win.document.querySelectorAll('button.ds-option')].find(x => x.textContent.includes(sensores[0].nombre));
      expect(card).to.exist;
      previo = card.querySelector('[role="img"]')?.getAttribute('aria-label');
      const obs = new win.MutationObserver(() => {
        const actual = card.querySelector('[role="img"]')?.getAttribute('aria-label');
        if (actual !== previo && cambio === null) cambio = { at: Date.now(), valor: actual };
      });
      obs.observe(card, { subtree: true, attributes: true, characterData: true, childList: true });
      win.__qaObserver = obs;
    });
    cy.request({ followRedirect: false,  method: 'POST', url: Cypress.env('CONTROL_URL'), headers: { 'X-QA-Key': Cypress.env('CONTROL_KEY') }, log: false }).then(r => {
      if (!r.body.accepted || !r.body.visible) throw Error('PRE: lectura confirmada por RF-53 no observable en dashboard del RUN');
      if (!r.body.transition || !etiquetas[r.body.semaforo]) throw Error('PRE: lectura del RUN no produjo transición de semáforo observable; falta preparar umbral adecuado');
      cy.wait(700).then(() => {
        expect(cambio, 'actualización automática').not.to.eq(null);
        expect(cambio.at - r.body.committedAt, 'almacenamiento confirmado hasta cambio visual').to.be.at.most(500);
        expect(cambio.valor).to.include(String(r.body.valor));
      });
      tarjeta().should('contain.text', etiquetas[r.body.semaforo]);
    });
    cy.window().then(win => win.__qaObserver?.disconnect());
    cy.then(() => expect(fuera).to.have.length(0));
  });

  it('[TC-M03-197][ASSERT] Nivel 1: 1200 ms durante cinco ciclos, push y polling 2 s sin indicador', () => {
    cy.window().then(win => { if (win.__qaPushSinSandbox) throw Error('PRE: canal push de Nivel 1 no aislable'); });
    const desde = latencias.length;
    red(1200);
    cy.window().then(win => expect(win.__qaPushOpen || 0, 'push real mantenido').to.be.greaterThan(0));
    esperarDash(5, 18000).then(ts => {
      const intervalos = ts.slice(1).map((t, i) => t - ts[i]);
      const medidos = latencias.slice(desde).slice(-5);
      if (medidos.length < 5 || medidos.some(ms => ms <= 500 || ms > 2000)) throw Error(`PRE: latencia 1200 ms no confirmada en cinco ciclos: ${medidos}`);
      expect(intervalos.every(ms => ms >= 1600 && ms <= 3500), `polling de respaldo 2 s: ${intervalos}`).to.eq(true);
    });
    cy.window().then(win => expect(win.__qaPushOpen || 0, 'push persistente tras cinco ciclos').to.be.greaterThan(0));
    cy.contains('Actualización con retraso').should('not.exist');
    cy.contains(/degradación|sin conexión/i).should('not.exist');
  });

  it('[TC-M03-198][ASSERT] Nivel 2: 3500 ms, polling 5 s, aviso, último semáforo', () => {
    cy.window().then(win => { if (win.__qaPushSinSandbox) throw Error('PRE: no se puede verificar abandono de canal push no aislable'); });
    const desde = latencias.length;
    red(3500);
    esperarDash(3, 18000).then(ts => {
      const intervalos = ts.slice(1).map((t, i) => t - ts[i]);
      const medidos = latencias.slice(desde).slice(-3);
      if (medidos.length < 3 || medidos.some(ms => ms <= 2000 || ms > 5000)) throw Error(`PRE: latencia 3500 ms no confirmada: ${medidos}`);
      expect(intervalos.every(ms => ms >= 4300 && ms <= 7200), `polling 5 s: ${intervalos}`).to.eq(true);
    });
    cy.contains('Actualización con retraso').should('be.visible');
    cy.window().then(win => expect(win.__qaPushOpen || 0, 'push abandonado en Nivel 2').to.eq(0));
    cy.contains(/\d{1,2}:\d{2}/).should('exist');
    semaforo().should('not.be.empty');
  });

  it('[TC-M03-199][ASSERT] Nivel 3: tres minutos sin backend, caché, backoff 5-60 s', () => {
    const desde = Date.now();
    let ultimoSemaforo;
    semaforo().then(x => { ultimoSemaforo = x; });
    cy.window().then(win => {
      const urls = [`${API}/*`, ...new Set(win.__qaPushUrls || [])];
      return Promise.resolve().then(() => Cypress.automation('remote:debugger:protocol', {
        command: 'Network.setBlockedURLs', params: { urls },
      })).then(() => { for (const socket of win.__qaPushSockets || []) socket.close(); })
        .catch(e => { throw Error(`PRE: corte de backend no disponible: ${e.message}`); });
    });
    cy.request({ followRedirect: false,  method: 'POST', url: Cypress.env('CONTROL_URL').replace(/\/ingest$/, '/guard/wait'), headers: { 'X-QA-Key': Cypress.env('CONTROL_KEY') }, body: {}, responseTimeout: 200000, failOnStatusCode: false, log: false }).then(r => {
      if (r.status !== 200 || !r.body?.ok) throw Error(`PRE: mantenimiento del sandbox falló durante la espera: ${r.body?.motivo || 'vigencia no confirmada'}`);
    });
    cy.contains('Trabajando sin conexión').should('be.visible');
    cy.contains(/\d{1,2}:\d{2}/).should('exist');
    tarjeta().should('be.visible');
    semaforo().then(x => expect(x, 'último estado sincronizado conservado').to.eq(ultimoSemaforo));
    cy.get('body').should('not.contain.text', 'Error bloqueante');
    cy.window().then(win => {
      const http = solicitudes.filter(x => x >= desde);
      const push = (win.__qaPushAttempts || []).filter(x => x >= desde);
      const reintentos = http.length >= 4 ? http : push;
      const intervalos = reintentos.slice(1).map((t, i) => t - reintentos[i]);
      expect(intervalos.length, 'reintentos observables').to.be.greaterThan(2);
      expect(intervalos[0], 'primer reintento base 5 s').to.be.within(4500, 6500);
      expect(intervalos.every(ms => ms >= 4500 && ms <= 65000), `backoff 5-60 s: ${intervalos}`).to.eq(true);
      expect(intervalos.slice(1).every((ms, i) => ms >= Math.min(60000, intervalos[i] * 1.5)), 'crecimiento exponencial').to.eq(true);
    });
    cy.then(() => Cypress.automation('remote:debugger:protocol', { command: 'Network.setBlockedURLs', params: { urls: [] } }));
  });

  it('[TC-M03-200][ASSERT] recuperación desde Nivel 2 tras tres mediciones <=500 ms', () => {
    cy.window().then(win => { if (win.__qaPushSinSandbox) throw Error('PRE: recuperación push no aislable'); });
    const desde = latencias.length;
    red(3500);
    esperarDash(2, 18000).then(() => {
      const medidos = latencias.slice(desde).slice(-2);
      if (medidos.length < 2 || medidos.some(ms => ms <= 2000 || ms > 5000)) throw Error(`PRE: Nivel 2 no preparado: ${medidos}`);
    });
    cy.contains('Actualización con retraso').should('be.visible');
    red(300);
    const rapidoDesde = latencias.length;
    cy.wait('@dash', { timeout: 15000 });
    cy.contains('Actualización con retraso').should('be.visible');
    cy.wait('@dash', { timeout: 15000 });
    cy.contains('Actualización con retraso').should('be.visible');
    cy.wait('@dash', { timeout: 15000 });
    cy.contains('Actualización con retraso').should('not.exist');
    cy.then(() => {
      const medidos = latencias.slice(rapidoDesde).slice(-4);
      if (medidos.length < 4 || medidos.some(ms => ms > 500)) throw Error(`PRE: cuatro mediciones <=500 ms no confirmadas: ${medidos}`);
    });
    cy.wait('@dash', { timeout: 15000 });
    cy.contains('Actualización con retraso').should('not.exist');
    red(0);
    cy.then(() => expect(fuera).to.have.length(0));
  });
});
