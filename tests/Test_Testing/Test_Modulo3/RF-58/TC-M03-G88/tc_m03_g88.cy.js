// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

// TC-M03-G88 — verificación visual (RF-58) de TC-M03-180: variable sin umbral configurado.
//
// Se ejecuta SOLO desde ejecutar_tc_m03_g88.mjs (configuración en línea), después de
// que Newman haya registrado la lectura dentro del sandbox. No usa mocks: cy.intercept
// solo añade las cabeceras del sandbox a las peticiones reales, las serializa y observa
// las respuestas. Los nombres de prueba siguen el formato [CASO][PRE|ASSERT][ID].

const env = (k) => Cypress.env(k);
const AUTORIZADO = env('AUTORIZADO_RUN') === 'SI' && !!env('RUN_ID') && /^https:\/\//.test(env('API_BASE') || '');

const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN_ID = env('RUN_ID');
const SENSOR_H = env('SENSOR_180H_NOMBRE');
const ID_INFRA = env('ID_INFRA');
const VALOR_H = Number(env('VALOR_H'));
const UNIDAD_H = env('UNIDAD_H');

const estado = { pre: false, peticionesFueraSandbox: [] };

// El sandbox atiende todas las peticiones del RUN con UNA sesión de base de datos
// compartida, que no admite uso concurrente: las peticiones de la UI se encolan.
// Solo cambia el orden temporal; ni la petición ni la respuesta se alteran (salvo las
// cabeceras del sandbox).
let cola = Promise.resolve();

function registrarSandbox() {
  cy.intercept({ url: `${API}/**` }, (req) => {
    let liberar;
    const turno = cola;
    cola = new Promise((resolve) => { liberar = resolve; });
    const seguro = setTimeout(() => liberar(), 35000);
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN_ID;
      req.headers['X-Sandbox-Secret'] = env('SANDBOX_SECRET');
      req.continue((res) => {
        clearTimeout(seguro);
        liberar();
        const eco = res.headers['x-test-run-id'];
        if (req.method !== 'OPTIONS' && eco !== RUN_ID) {
          estado.peticionesFueraSandbox.push(`${req.method} ${req.url.replace(API, '')} -> ${res.statusCode}`);
        }
      });
    });
  });
  cy.intercept({ method: 'GET', url: `${API}/iot/monitoreo/dashboard*` }).as('dashboard');
  cy.intercept({ method: 'POST', url: `${API}/sesiones/` }).as('login');
}

function iniciarSesion(correo, clave) {
  cy.clearCookies();
  cy.clearLocalStorage();
  cy.visit(urlFrontendQA('/login'), {
    onBeforeLoad(win) {
      // El dashboard tiene caché local (IndexedDB); se descarta para no mezclar datos previos.
      if (win.indexedDB && typeof win.indexedDB.databases === 'function') {
        win.indexedDB.databases().then((dbs) => dbs.forEach((d) => d.name && win.indexedDB.deleteDatabase(d.name)));
      }
    },
  });
  cy.get('input[type="email"]').clear().type(correo, { log: false });
  cy.get('input[type="password"]').clear().type(clave, { log: false });
  cy.get('button[type="submit"]').click();
  cy.wait('@login').its('response.statusCode').should('eq', 200);
}

function abrirMonitoreo(nombreSensor) {
  cy.visit(urlFrontendQA('/telemetria/monitoreo'));
  cy.wait('@dashboard').then((i) => {
    expect(i.response.statusCode, 'HTTP del dashboard').to.eq(200);
    expect(i.response.headers['x-test-run-id'], 'X-Test-Run-Id devuelto por el backend').to.eq(RUN_ID);
  });
  cy.contains('desde caché').should('not.exist');
  // Si el sensor no está en la primera página, se filtra por la unidad productiva del RUN.
  cy.get('body').then(($b) => {
    if (!$b.find(`button.ds-option:contains("${nombreSensor}")`).length) {
      cy.get('input[type="number"]').first().clear().type(`${ID_INFRA}{enter}`);
      cy.wait('@dashboard').then((i) => {
        expect(i.request.url, 'filtro por unidad').to.include(`id_infraestructura=${ID_INFRA}`);
        expect(i.response.statusCode).to.eq(200);
        expect(i.response.headers['x-test-run-id']).to.eq(RUN_ID);
      });
    }
  });
}

const tarjeta = (nombre) => cy.contains('button.ds-option', nombre, { timeout: 20000 });

/** Valor numérico mostrado por el indicador (aria-label "…: <valor> <unidad>"). */
function valorMostrado($card, unidad) {
  for (const e of $card.find('[aria-label]')) {
    const et = e.getAttribute('aria-label') || '';
    if (et.includes(unidad)) {
      if (/sin dato/i.test(et)) return null;
      const m = et.match(/(-?\d+(?:\.\d+)?)\s*\S*$/) || et.match(/(-?\d+(?:\.\d+)?)/);
      if (m) return Number(m[1]);
    }
  }
  return null;
}

describe('TC-M03-G88 — UI de Monitoreo (RF-58, TC-M03-180)', () => {
  before(() => {
    if (!AUTORIZADO) {
      throw new Error('BLOQUEO_G88: spec sin autorización de ejecución; usar ejecutar_tc_m03_g88.mjs.');
    }
  });

  it('[TC-M03-180][PRE][PRE-UI-01] Productor: la UI recibe el dashboard real del sandbox', () => {
    registrarSandbox();
    iniciarSesion(env('PROD_EMAIL'), env('PROD_PASSWORD'));
    abrirMonitoreo(SENSOR_H);
    cy.then(() => {
      expect(estado.peticionesFueraSandbox, 'peticiones no atendidas en el sandbox').to.have.length(0);
      estado.pre = true;
    });
  });

  it('[TC-M03-180][ASSERT][UI-180-01] La tarjeta de la variable sin umbral es visible', () => {
    cy.get('body').then(($b) => {
      // Una sola captura de la vista si la tarjeta no aparece; si aparece, solo la tarjeta.
      if (!$b.find(`button.ds-option:contains("${SENSOR_H}")`).length) cy.screenshot('TC-M03-180_sin_tarjeta', { capture: 'viewport' });
      tarjeta(SENSOR_H).scrollIntoView().should('be.visible').screenshot('TC-M03-180_productor_sensor_sin_umbral');
    });
  });

  it('[TC-M03-180][ASSERT][UI-180-02] La tarjeta muestra el valor y la unidad', () => {
    tarjeta(SENSOR_H).then(($c) => {
      const v = valorMostrado($c, UNIDAD_H);
      expect(v !== null && Math.abs(v - VALOR_H) < 0.0001, `valor mostrado ${v} ${UNIDAD_H}`).to.eq(true);
    });
  });

  it('[TC-M03-180][ASSERT][UI-180-03] La tarjeta muestra la etiqueta «Sin umbral configurado»', () => {
    tarjeta(SENSOR_H).then(($c) => {
      const texto = $c.text();
      const etiquetas = [...$c.find('[aria-label],[title]')].map((e) => `${e.getAttribute('aria-label') || ''} ${e.getAttribute('title') || ''}`);
      const visible = /sin umbral configurado/i.test(texto) || etiquetas.some((e) => /sin umbral configurado/i.test(e));
      expect(visible, `texto="${texto}"`).to.eq(true);
    });
  });
});
