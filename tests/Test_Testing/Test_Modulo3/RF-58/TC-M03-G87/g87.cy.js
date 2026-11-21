// TC-M03-G87 — comprobaciones UI de TC-M03-177 y TC-M03-178 (RF-58, vista Monitoreo).
// Lo lanza g87.mjs después de Newman, dentro del mismo RUN. En V2, cy.intercept devuelve al
// formulario el login API ya realizado; las demás peticiones son reales, llevan cabeceras del
// sandbox y se serializan (la sesión de BD del RUN es única).
//
// Una sesión por rol: el JWT del frontend vive en memoria (recargar la página lo pierde) y un segundo
// login de la misma cuenta esperaría la fila de cuenta retenida por el RUN. Por eso cada bloque
// establece la sesión en su `before`, navega por la SPA y sus pruebas leen la misma página.

const env = (k) => Cypress.env(k);
const FRONT = String(Cypress.config('baseUrl') || '').replace(/\/+$/, '');
const BASE = new URL(FRONT).pathname.replace(/\/+$/, '');
const ORIGEN_FRONT = new URL(FRONT).origin;
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN_ID = env('RUN_ID');
const AREA = String(env('AREA_ID'));
const S1 = env('S1_NOMBRE');
const S2 = env('S2_NOMBRE');
const VALOR_25 = Number(env('VALOR_25'));
const VALOR_FUERA = Number(env('VALOR_FUERA'));
const VALORES_ERROR = (env('VALORES_ERROR') || []).map(Number);
const LOCAL = env('MODO_LOCAL') === true;
const UI_177 = env('UI_177') === true;
const UI_178_PROD = env('UI_178_PROD') === true;
const UI_178_ENG = env('UI_178_ENG') === true;
const DASHBOARD_REQUEST_TIMEOUT = 90000; // primera carga perezosa de Monitoreo, especialmente con Vite en frío
const caso177 = UI_177 ? it : () => {};
const caso178 = UI_178_PROD ? it : () => {};
const AUTORIZADO = LOCAL
  ? env('AUTORIZADO') === 'LOCAL' && /^http:\/\/127\.0\.0\.1:\d+$/.test(FRONT)
    && /^http:\/\/127\.0\.0\.1:\d+$/.test(API) && !!env('LOCAL_FIXTURES')
  : env('AUTORIZADO') === 'SI' && !!RUN_ID && !!env('SANDBOX_SECRET') && /^https:\/\//.test(API);

const estado = { pre: {}, fuera: [], sinFixture: [], rol: null };
let cola = Promise.resolve();

function sandbox() {
  if (LOCAL) {
    cy.intercept({ url: '**' }, (req) => {
      const url = new URL(req.url);
      if (url.hostname !== '127.0.0.1') {
        estado.fuera.push(`${req.method} destino externo`);
        req.destroy();
        return;
      }
      if (url.origin === ORIGEN_FRONT) { req.continue(); return; }
      if (url.origin !== API) {
        estado.fuera.push(`${req.method} puerto local no previsto`);
        req.destroy();
        return;
      }
      const ruta = url.pathname;
      const rol = estado.rol;
      const fixture = env('LOCAL_FIXTURES');
      const responder = (body, alias) => {
        if (alias) req.alias = alias;
        req.reply({ statusCode: 200, headers: { 'x-test-run-id': RUN_ID,
          'access-control-allow-origin': ORIGEN_FRONT, 'access-control-allow-credentials': 'true' }, body });
      };
      if (req.method === 'OPTIONS') {
        req.reply({ statusCode: 204, headers: { 'access-control-allow-origin': ORIGEN_FRONT,
          'access-control-allow-credentials': 'true', 'access-control-allow-methods': 'GET, POST, OPTIONS',
          'access-control-allow-headers': 'Authorization, Content-Type, X-Zona-Horaria' } });
      } else if (req.method === 'POST' && ruta === '/sesiones/') {
        responder(fixture[rol].login, 'login');
      } else if (req.method === 'GET' && ruta === '/usuarios/me') {
        responder(fixture[rol].perfil);
      } else if (req.method === 'GET' && ruta === '/notificaciones') {
        responder({ total: 0, no_leidas: 0, pagina: Number(url.searchParams.get('pagina') || 1),
          tamano: Number(url.searchParams.get('tamano') || 20), items: [] });
      } else if (req.method === 'GET' && ruta === '/sesiones/me/permisos') {
        responder(fixture[rol].permisos);
      } else if (req.method === 'GET' && ruta === '/iot/monitoreo/dashboard') {
        responder(fixture[rol].dashboard, url.searchParams.get('id_infraestructura') === AREA ? 'dashboardArea' : 'dashboard');
      } else if (req.method === 'GET' && ruta === '/configuracion/personalizacion/dashboard') {
        responder(fixture[rol].layout);
      } else if (req.method === 'GET' && ruta === '/configuracion/personalizacion/dashboard/widgets') {
        responder([]);
      } else if (req.method === 'GET' && ruta === '/configuracion/personalizacion/dashboard/datos') {
        responder([]);
      } else if (req.method === 'GET' && ruta === '/configuracion/interfaz/contexto') {
        responder(fixture[rol].contexto);
      } else if (req.method === 'GET' && ruta === '/configuracion/personalizacion/tema') {
        responder({ theme_mode: 1, fuente: 'defecto', id_tema_visual: null });
      } else if (req.method === 'GET' && ruta === '/configuracion/personalizacion/idioma') {
        responder({ locale_code: 'es-CO', fuente: 'defecto', id_preferencia_idioma: null });
      } else {
        estado.sinFixture.push(`${req.method} ${ruta}`);
        estado.fuera.push(`${req.method} ruta API sin fixture: ${ruta}`);
        req.reply({ statusCode: 404, body: { message: 'Ruta sin fixture local' } });
      }
    });
    return;
  }
  cy.intercept({ url: /^https:\/\/[^/]+\/api-sgpmp(?:-[^/]+)?(?:\/|$)/ }, (req) => {
    if (!req.url.startsWith(`${API}/`)) { estado.fuera.push(`${req.method} host no autorizado`); req.destroy(); return; }
    const url = new URL(req.url);
    const ruta = url.pathname.replace(/^\/api-sgpmp-test/, '');
    if (req.method === 'GET' && ruta === '/iot/monitoreo/dashboard') {
      req.alias = url.searchParams.get('id_infraestructura') === AREA ? 'dashboardArea' : 'dashboard';
    }
    if (req.method === 'POST' && ruta === '/sesiones/') {
      req.alias = 'login';
      const respuesta = estado.rol === 'prod' ? env('PROD_LOGIN') : env('ENG_LOGIN');
      if (respuesta?.token) req.reply({ statusCode: 200, body: respuesta });
      else req.continue(); // V1: login real fuera del RUN
      return;
    }
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
  estado.rol = rol;
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
  cy.get('input[type="password"]').clear().type(clave || 'sesion-reutilizada', { log: false });
  cy.get('button[type="submit"]').click();
  cy.wait('@login').then((i) => {
    expect(i.response?.statusCode, 'login UI').to.eq(200);
    if (!LOCAL && !env(rol === 'prod' ? 'PROD_LOGIN' : 'ENG_LOGIN'))
      cy.task('registrarSesionG87', { rol, token: i.response.body.token }, { log: false });
  });
  cy.location('pathname', { timeout: 60000 }).should('eq', `${BASE}/dashboard`);
  // React Router escucha popstate. Navegar dentro de la SPA conserva el JWT en memoria
  // y no depende del estado del menú lateral ni del viewport.
  cy.window().then((win) => {
    win.history.pushState({}, '', `${BASE}/telemetria/monitoreo`);
    win.dispatchEvent(new win.PopStateEvent('popstate'));
  });
  cy.location('pathname', { timeout: 20000 }).should('eq', `${BASE}/telemetria/monitoreo`);
  cy.wait('@dashboard', { requestTimeout: DASHBOARD_REQUEST_TIMEOUT }).its('response.statusCode').should('eq', 200);
  // SelectorArea -> Combobox: etiqueta visible «Área», entrada libre por ID.
  cy.contains('label', /^Área$/, { timeout: 20000 }).should('be.visible')
    .invoke('attr', 'for').then((id) => {
      expect(id, 'combobox de monitoreo').to.eq('monitoreo-area');
      cy.get(`[role="combobox"][id="${id}"]`).should('have.attr', 'aria-autocomplete', 'list')
        .clear().type(AREA);
    });
  cy.wait('@dashboardArea', { requestTimeout: DASHBOARD_REQUEST_TIMEOUT }).then((i) => {
    expect(i.response.statusCode, 'dashboard del área').to.eq(200);
    expect(i.response.headers['x-test-run-id'], 'eco del RUN').to.eq(RUN_ID);
  });
  cy.contains('button', /Auto ON/).click(); // sin polling entre pruebas
  cy.contains('desde caché').should('not.exist');
  cy.screenshot(`${rol}_PRE-UI-01_area_filtrada`);
  cy.then(() => { estado.pre[rol] = estado.fuera.length === 0; });
}

function tarjeta(nombre) {
  // MonitoreoView agrupa por área; un sensor VERDE es SensorFila y uno sin dato
  // puede estar en <details>. Ambos son botones OptionCard con nombre visible.
  cy.get(`button[aria-controls="area-${AREA}"]`).then(($area) => {
    if ($area.attr('aria-expanded') === 'false') cy.wrap($area).click();
  });
  return cy.get(`#area-${AREA}`).then(($area) => {
    const cerrado = [...$area.find('details')].find((d) => !d.open && d.textContent.includes(nombre));
    if (cerrado) cy.wrap(cerrado).find('summary').click();
  }).then(() => cy.contains(`#area-${AREA} button.ds-option--card`, nombre, { timeout: 20000 })
    .should('be.visible'));
}
function etiquetaAnomaliaRecortada(etiqueta, vista) {
  const caja = etiqueta.getBoundingClientRect();
  if (caja.width <= 0 || caja.height < 8 || caja.top < 0 || caja.bottom > vista.innerHeight
    || caja.left < 0 || caja.right > vista.innerWidth) return true;
  const estilo = vista.getComputedStyle(etiqueta);
  const recorta = (desborde, visible, total) => /^(auto|hidden|clip|scroll)$/.test(desborde)
    && visible > 0 && total > visible + 1;
  return recorta(estilo.overflowX, etiqueta.clientWidth, etiqueta.scrollWidth)
    || recorta(estilo.overflowY, etiqueta.clientHeight, etiqueta.scrollHeight);
}
function captura(nombre, archivo) {
  tarjeta(nombre).scrollIntoView().should('be.visible').then(($boton) => {
    const r = $boton[0].getBoundingClientRect();
    const vista = $boton[0].ownerDocument.defaultView;
    if (r.width < 20 || r.height < 20 || r.top < 0 || r.bottom > vista.innerHeight
      || r.left < 0 || r.right > vista.innerWidth)
      throw new Error(`ERROR_QA_EVIDENCIA: ${archivo}: fila fuera de vista o caja menor de 20 px`);
    if (archivo === 'UI-177-03_anomalia') {
      const etiqueta = [...$boton.find('span')].filter((e) =>
        /^lectura fuera de rango$/i.test((e.textContent || '').trim()) && e.querySelector('svg')).at(-1);
      if (etiqueta && etiquetaAnomaliaRecortada(etiqueta, vista))
        throw new Error(`ERROR_QA_EVIDENCIA: ${archivo}: etiqueta de anomalía recortada o fuera de vista`);
    }
  });
  cy.screenshot(archivo, { capture: 'viewport' });
  cy.task('verificarCapturaG87', archivo, { log: false }).then((e) => {
    if (!e.ok) throw new Error(`ERROR_QA_EVIDENCIA: ${archivo}: ${e.motivo}`);
  });
}
function capturaDetalle(archivo) {
  cy.get('[role="dialog"]').should('be.visible');
  cy.screenshot(archivo, { capture: 'viewport' });
  cy.task('verificarCapturaG87', archivo, { log: false }).then((e) => {
    if (!e.ok) throw new Error(`ERROR_QA_EVIDENCIA: ${archivo}: ${e.motivo}`);
  });
}
/** Gauge en SensorCard o texto de valor en SensorFila, ambos del frontend real. */
function valorMostrado($c) {
  for (const et of [...$c.find('[role="img"][aria-label]')].map((e) => e.getAttribute('aria-label') || '')) {
    if (/sin dato/i.test(et)) return null;
    const m = et.match(/(-?\d+(?:[.,]\d+)?)\s*°C/);
    if (m) return Number(m[1]);
  }
  const fila = [...$c.find('span')].find((e) => /^\s*-?\d+(?:[.,]\d+)?\s*°C\s*$/.test(e.textContent || '') && !e.querySelector('span'));
  if (fila) return Number((fila.textContent.match(/-?\d+(?:[.,]\d+)?/) || [''])[0].replace(',', '.'));
  return null;
}
const igual = (a, b) => a !== null && Math.abs(a - b) < 0.0001;

describe('TC-M03-G87 — Monitoreo (RF-58)', () => {
  before(() => { if (!AUTORIZADO) throw new Error('BLOQUEO_G87: ejecutar solo mediante g87.mjs con autorización.'); });
  beforeEach(() => sandbox()); // Cypress retira las intercepciones antes de cada prueba
  afterEach(() => {
    if (LOCAL) cy.then(() => cy.task('registrarRutasLocalesG87', estado.sinFixture, { log: false }));
  });
  after(() => {
    if (LOCAL) cy.task('registrarRutasLocalesG87', estado.sinFixture, { log: false });
  });

  if (UI_177 || UI_178_PROD) describe('Productor', { testIsolation: false }, () => {
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
      captura(S1, 'UI-177-02_valor_25');
    });
    caso177('[TC-M03-177][ASSERT][UI-177-03] Productor: la anomalía de S1 es visible (ROJO / ícono)', () => {
      tarjeta(S1).then(($c) => {
        const indicador = [...$c.find('span')].find((e) => /lectura fuera de rango/i.test(e.textContent || '') && e.querySelector('svg'));
        const rojo = [...$c.find('span')].some((e) => /rojo/i.test(e.textContent || ''));
        expect(!!indicador || rojo, 'anomalía visible mediante etiqueta e ícono o ROJO').to.eq(true);
      });
      captura(S1, 'UI-177-03_anomalia');
    });
    caso178('[TC-M03-178][ASSERT][UI-178-01] Productor: la tarjeta de S2 es visible', () => captura(S2, 'TC-M03-178_productor_S2'));
    caso178('[TC-M03-178][ASSERT][UI-178-02] Productor: ERROR_CALIBRACION no se muestra como lectura operativa', () => {
      tarjeta(S2).then(($c) => {
        const v = valorMostrado($c);
        expect(VALORES_ERROR.some((x) => igual(v, x)), `valor mostrado ${v}`).to.eq(false);
        expect([...$c.find('[aria-label]')].filter((e) => /alerta activa/i.test(e.getAttribute('aria-label') || '')).length,
          'sin alerta operativa').to.eq(0);
      });
      captura(S2, 'UI-178-02_sin_valor_error');
    });
    caso178('[TC-M03-178][ASSERT][UI-178-03] Productor: sin información técnica (batería %, dBm)', () => {
      tarjeta(S2).then(($c) => {
        expect(/\d+(?:\.\d+)?\s*%/.test($c.text()), `batería en "${$c.text()}"`).to.eq(false);
        expect(/-?\d+(?:\.\d+)?\s*dBm/.test($c.text()), `RSSI en "${$c.text()}"`).to.eq(false);
        expect(/ERROR_CALIBRACION|Requiere calibración/i.test($c.text()), 'diagnóstico reservado').to.eq(false);
      });
      tarjeta(S2).click();
      cy.get('[role="dialog"]').should('be.visible').then(($d) => {
        expect(/ERROR_CALIBRACION|Requiere calibración/i.test($d.text()), 'diagnóstico reservado en detalle').to.eq(false);
        expect(/-?\d+(?:\.\d+)?\s*dBm|\d+(?:\.\d+)?\s*dB\b|\d+(?:\.\d+)?\s*%/.test($d.text()), 'datos técnicos en detalle').to.eq(false);
      });
      capturaDetalle('UI-178-03_productor_detalle');
      cy.get('[role="dialog"] button[aria-label]').first().click();
    });
  });

  if (UI_178_ENG) describe('Ingeniero de Campo', { testIsolation: false }, () => {
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
      capturaDetalle('TC-M03-178_ingeniero_detalle_S2');
    });
  });
});
