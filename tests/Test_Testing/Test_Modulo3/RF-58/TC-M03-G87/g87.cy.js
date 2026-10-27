// TC-M03-G87 — comprobaciones UI de TC-M03-177 y TC-M03-178 (RF-58, vista Monitoreo).
// Lo lanza g87.mjs después de Newman, dentro del mismo RUN. Sin mocks: cy.intercept solo añade las
// cabeceras del sandbox a las peticiones reales y las serializa (la sesión de BD del RUN es única).
//
// Un login por rol: el JWT del frontend vive en memoria (recargar la página lo pierde) y un segundo
// login de la misma cuenta esperaría la fila de cuenta retenida por el RUN. Por eso cada bloque
// inicia sesión en su `before`, navega por la SPA y sus pruebas leen la misma página.

const env = (k) => Cypress.env(k);
const FRONT = String(Cypress.config('baseUrl') || '').replace(/\/+$/, '');
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN_ID = env('RUN_ID');
const AREA = String(env('AREA_ID'));
const S1 = env('S1_NOMBRE');
const S2 = env('S2_NOMBRE');
const VALOR_25 = Number(env('VALOR_25'));
const VALOR_FUERA = Number(env('VALOR_FUERA'));
const VALORES_ERROR = (env('VALORES_ERROR') || []).map(Number);
const UI_177 = env('UI_177') === true;
const UI_178 = env('UI_178') === true;
const caso177 = UI_177 ? it : () => {};
const caso178 = UI_178 ? it : () => {};
const AUTORIZADO = env('AUTORIZADO') === 'SI' && !!RUN_ID && !!env('SANDBOX_SECRET') && /^https:\/\//.test(API);

const estado = { pre: {}, fuera: [] };
let cola = Promise.resolve();

function sandbox() {
  cy.intercept({ url: /^https:\/\/[^/]+\/api-sgpmp(?:-[^/]+)?(?:\/|$)/ }, (req) => {
    if (!req.url.startsWith(`${API}/`)) { estado.fuera.push(`${req.method} host no autorizado`); req.destroy(); return; }
    const url = new URL(req.url);
    const ruta = url.pathname.replace(/^\/api-sgpmp-test/, '');
    if (req.method === 'GET' && ruta === '/iot/monitoreo/dashboard') {
      req.alias = url.searchParams.get('id_infraestructura') === AREA ? 'dashboardArea' : 'dashboard';
    }
    if (req.method === 'POST' && ruta === '/sesiones/') { req.alias = 'login'; req.continue(); return; } // login real, fuera del RUN
    if (ruta.startsWith('/sesiones/') && req.method !== 'GET') { estado.fuera.push(`${req.method} ${ruta}`); req.destroy(); return; }
    let liberar;
    const turno = cola;
    cola = new Promise((r) => { liberar = r; });
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN_ID;
      req.headers['X-Sandbox-Secret'] = env('SANDBOX_SECRET');
      req.continue((res) => {
        liberar();
        if (req.method !== 'OPTIONS' && res.headers['x-test-run-id'] !== RUN_ID) estado.fuera.push(`${req.method} ${ruta} -> ${res.statusCode}`);
      });
    });
  });
}

function sesionUi(rol, correo, clave) {
  estado.pre[rol] = false;
  estado.fuera = [];
  cola = Promise.resolve();
  sandbox();
  cy.clearCookies();
  cy.clearLocalStorage();
  cy.visit(`${FRONT}/login`, {
    onBeforeLoad(win) { // caché local del dashboard (IndexedDB): se descarta
      if (win.indexedDB?.databases) win.indexedDB.databases().then((d) => d.forEach((x) => x.name && win.indexedDB.deleteDatabase(x.name)));
    },
  });
  cy.get('input[type="email"]').clear().type(correo, { log: false });
  cy.get('input[type="password"]').clear().type(clave, { log: false });
  cy.get('button[type="submit"]').click();
  cy.wait('@login').then((i) => {
    expect(i.response?.statusCode, 'login UI').to.eq(200);
    cy.task('registrarSesionG87', { rol, token: i.response.body.token }, { log: false });
  });
  // El menú abre Telemetría y su pestaña abre Monitoreo, sin recargar el JWT.
  // Si el rol no tiene permiso, el PRE debe mostrarlo sin forzar el clic.
  cy.get('nav.ds-sidebar a[href$="/telemetria"]', { timeout: 20000 })
    .should('have.attr', 'aria-disabled', 'false').click();
  cy.get('nav[aria-label] button[title="Monitoreo"]', { timeout: 20000 })
    .should('have.attr', 'aria-disabled', 'false').click();
  cy.location('pathname', { timeout: 20000 }).should('match', /\/telemetria\/monitoreo$/);
  cy.wait('@dashboard').its('response.statusCode').should('eq', 200);
  cy.get('input[type="number"]').first().clear().type(AREA); // filtro por el área del escenario
  cy.wait('@dashboardArea').then((i) => {
    expect(i.response.statusCode, 'dashboard del área').to.eq(200);
    expect(i.response.headers['x-test-run-id'], 'eco del RUN').to.eq(RUN_ID);
  });
  cy.contains('button', /Auto ON/).click(); // sin polling entre pruebas
  cy.contains('desde caché').should('not.exist');
  cy.then(() => { estado.pre[rol] = estado.fuera.length === 0; });
}

const tarjeta = (nombre) => cy.contains('button.ds-option', nombre, { timeout: 20000 });
function captura(nombre, archivo) {
  cy.get('body').then(($b) => { if (!$b.find(`button.ds-option:contains("${nombre}")`).length) cy.screenshot(`${archivo}_sin_tarjeta`); });
  tarjeta(nombre).scrollIntoView().should('be.visible').screenshot(archivo);
}
/** Valor del indicador de la tarjeta (aria-label "…: <valor> °C" o "sin dato"). */
function valorMostrado($c) {
  for (const et of [...$c.find('[aria-label]')].map((e) => e.getAttribute('aria-label') || '')) {
    if (/sin dato/i.test(et)) return null;
    const m = et.includes('°C') && et.match(/(-?\d+(?:\.\d+)?)\s*°C/);
    if (m) return Number(m[1]);
  }
  return null;
}
const igual = (a, b) => a !== null && Math.abs(a - b) < 0.0001;

describe('TC-M03-G87 — Monitoreo (RF-58)', () => {
  before(() => { if (!AUTORIZADO) throw new Error('BLOQUEO_G87: ejecutar solo mediante g87.mjs con autorización.'); });
  beforeEach(() => sandbox()); // Cypress retira las intercepciones antes de cada prueba

  describe('Productor', { testIsolation: false }, () => {
    before(() => sesionUi('prod', env('PROD_EMAIL'), env('PROD_PASSWORD')));

    caso177('[TC-M03-177][PRE][PRE-UI-01] Productor: la UI recibe el dashboard real del RUN', () => {
      cy.then(() => expect(estado.pre.prod, `peticiones fuera del RUN: ${estado.fuera.join(', ')}`).to.eq(true));
    });
    caso178('[TC-M03-178][PRE][PRE-UI-01] Productor: la UI recibe el dashboard real del RUN', () => {
      cy.then(() => expect(estado.pre.prod).to.eq(true));
    });
    caso177('[TC-M03-177][ASSERT][UI-177-01] Productor: la tarjeta de S1 es visible', () => captura(S1, 'TC-M03-177_productor_S1'));
    caso177('[TC-M03-177][ASSERT][UI-177-02] Productor: S1 muestra 25 como valor operativo, no el anómalo', () => {
      tarjeta(S1).then(($c) => {
        const v = valorMostrado($c);
        expect(igual(v, VALOR_25), `valor mostrado ${v}`).to.eq(true);
        expect(igual(v, VALOR_FUERA), `valor mostrado ${v}`).to.eq(false);
      });
    });
    caso177('[TC-M03-177][ASSERT][UI-177-03] Productor: la anomalía de S1 es visible (ROJO / ícono)', () => {
      tarjeta(S1).then(($c) => {
        const pill = [...$c.find('span')].find((e) => /fuera de rango/i.test(e.textContent || '') && e.querySelector('svg'));
        expect(pill, 'semáforo ROJO con ícono visible').to.exist;
        expect(pill.getAttribute('style') || '', 'tono de error del semáforo').to.include('var(--sem-error)');
      });
    });
    caso178('[TC-M03-178][ASSERT][UI-178-01] Productor: la tarjeta de S2 es visible', () => captura(S2, 'TC-M03-178_productor_S2'));
    caso178('[TC-M03-178][ASSERT][UI-178-02] Productor: ERROR_CALIBRACION no se muestra como lectura operativa', () => {
      tarjeta(S2).then(($c) => {
        const v = valorMostrado($c);
        expect(VALORES_ERROR.some((x) => igual(v, x)), `valor mostrado ${v}`).to.eq(false);
        expect([...$c.find('[aria-label]')].filter((e) => /alerta activa/i.test(e.getAttribute('aria-label') || '')).length,
          'sin alerta operativa').to.eq(0);
      });
    });
    caso178('[TC-M03-178][ASSERT][UI-178-03] Productor: sin información técnica (batería %, dBm)', () => {
      tarjeta(S2).then(($c) => {
        expect(/\d+(?:\.\d+)?\s*%/.test($c.text()), `batería en "${$c.text()}"`).to.eq(false);
        expect(/-?\d+(?:\.\d+)?\s*dBm/.test($c.text()), `RSSI en "${$c.text()}"`).to.eq(false);
      });
    });
  });

  if (UI_178) describe('Ingeniero de Campo', { testIsolation: false }, () => {
    before(() => sesionUi('eng', env('ENG_EMAIL'), env('ENG_PASSWORD')));

    it('[TC-M03-178][PRE][PRE-UI-01] Ingeniero: la UI recibe el dashboard real del RUN', () => {
      cy.then(() => expect(estado.pre.eng, `peticiones fuera del RUN: ${estado.fuera.join(', ')}`).to.eq(true));
    });
    it('[TC-M03-178][ASSERT][UI-178-04] Ingeniero: la tarjeta de S2 es visible', () => captura(S2, 'TC-M03-178_ingeniero_S2'));
    it('[TC-M03-178][ASSERT][UI-178-05] Ingeniero: el detalle muestra ERROR_CALIBRACION / requiere calibración', () => {
      tarjeta(S2).click();
      cy.get('[role="dialog"]', { timeout: 10000 }).should('be.visible').then(($d) => {
        expect(/ERROR_CALIBRACION|requiere calibraci/i.test($d.text()), `detalle="${$d.text()}"`).to.eq(true);
      });
      cy.get('[role="dialog"]').screenshot('TC-M03-178_ingeniero_detalle_S2');
    });
  });
});
