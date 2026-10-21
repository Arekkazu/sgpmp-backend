// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

// TC-M03-G87 — verificación visual (RF-58) de TC-M03-177 y TC-M03-178.
//
// Se ejecuta SOLO desde ejecutar_tc_m03_g87.mjs, después de que Newman haya registrado las lecturas dentro
// del sandbox. No usa mocks: cy.intercept solo añade las cabeceras del sandbox a las
// peticiones reales, las serializa y observa las respuestas.
// Los nombres de prueba siguen el formato [CASO][PRE|ASSERT][ID].

const env = (k) => Cypress.env(k);
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const FRONT = String(Cypress.config('baseUrl') || '').replace(/\/+$/, '');
const API_ESPERADA = /^https:\/\//.test(FRONT) ? `${new URL(FRONT).origin}/api-sgpmp-test` : '';
const AUTORIZADO = env('AUTORIZADO_RUN') === 'SI' && !!env('RUN_ID') && !!env('SANDBOX_SECRET')
  && API === API_ESPERADA && /\/sigab-test$/.test(FRONT);
const RUN_ID = env('RUN_ID');
const UNIDAD = env('UNIDAD');
const SENSOR_B = env('SENSOR_B_NOMBRE');
const SENSOR_C = env('SENSOR_C_NOMBRE');
const ID_INFRA = env('ID_INFRA');
const VALOR_B = Number(env('VALOR_B'));
const VALOR_FUERA = Number(env('VALOR_FUERA'));
const VALORES_C = (env('VALORES_C') || []).map(Number);

const estado = { pre: { prod: false, eng: false }, peticionesFueraSandbox: [] };

const cerca = (a, b) => a !== null && Math.abs(a - b) < 0.0001;

// El sandbox atiende todas las peticiones del RUN con UNA sesión de base de datos
// compartida (testing_sandbox.get_or_create_test_session), que no admite uso
// concurrente. La UI lanza peticiones en paralelo, así que se encolan: cada petición
// a la API espera la respuesta de la anterior. Solo cambia el orden temporal; ni la
// petición ni la respuesta se alteran (salvo las cabeceras del sandbox).
let cola = Promise.resolve();

function registrarSandbox() {
  // El frontend TEST usa api.inmero.co. Cualquier otro host API se corta antes
  // de salir, pues no habría prueba de que comparta la transacción del RUN.
  cy.intercept({ url: /^https:\/\/[^/]+\/api-sgpmp-test(?:\/|$)/ }, (req) => {
    if (!req.url.startsWith(`${API}/`)) {
      estado.peticionesFueraSandbox.push(`${req.method} host API no autorizado`);
      req.destroy();
      return;
    }
    const ruta = new URL(req.url).pathname;
    if (req.method === 'GET' && ruta === '/api-sgpmp-test/iot/monitoreo/dashboard') req.alias = 'dashboard';
    if (req.method === 'POST' && ruta === '/api-sgpmp-test/sesiones/') req.alias = 'login';
    let liberar;
    const turno = cola;
    cola = new Promise((resolve) => { liberar = resolve; });
    // Si una petición no obtiene respuesta, la cola se libera a los 35 s para no bloquear la prueba.
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
}

/**
 * Tarjeta del sensor. Si no aparece, se deja UNA captura de la vista como evidencia
 * de la ausencia y la prueba falla; si aparece, se captura solo la tarjeta.
 */
function capturarTarjeta(nombre, archivo) {
  return cy.get('body').then(($b) => {
    if (!$b.find(`button.ds-option:contains("${nombre}")`).length) {
      cy.screenshot(`${archivo}_sin_tarjeta`, { capture: 'viewport' });
    }
    tarjeta(nombre).scrollIntoView().should('be.visible').screenshot(archivo);
  });
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

/** Abre Monitoreo y devuelve (vía alias) la respuesta real del dashboard. */
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
function valorMostrado($card) {
  const etiquetas = [...$card.find('[aria-label]')].map((e) => e.getAttribute('aria-label'));
  for (const et of etiquetas) {
    if (et && et.includes(UNIDAD)) {
      const m = et.match(/(-?\d+(?:\.\d+)?)\s*\S*$/) || et.match(/(-?\d+(?:\.\d+)?)/);
      if (/sin dato/i.test(et)) return null;
      if (m) return Number(m[1]);
    }
  }
  return null;
}

describe('TC-M03-G87 — UI de Monitoreo (RF-58)', () => {
  before(() => {
    if (!AUTORIZADO) {
      throw new Error('BLOQUEO_G87: spec sin autorización de ejecución; usar ejecutar_tc_m03_g87.mjs.');
    }
  });

  describe('Productor Agropecuario', () => {
    it('[TC-M03-177][PRE][PRE-UI-01] Productor: la UI recibe el dashboard real del sandbox', () => {
      registrarSandbox();
      iniciarSesion(env('PROD_EMAIL'), env('PROD_PASSWORD'));
      abrirMonitoreo(SENSOR_B);
      cy.then(() => {
        expect(estado.peticionesFueraSandbox, 'peticiones no atendidas en el sandbox').to.have.length(0);
        estado.pre.prod = true;
      });
    });

    it('[TC-M03-178][PRE][PRE-UI-01] Productor: sesión UI dentro del sandbox disponible para TC-M03-178', () => {
      expect(estado.pre.prod, 'precondición UI del Productor').to.eq(true);
    });

    it('[TC-M03-177][ASSERT][UI-177-01] Productor: Monitoreo muestra la tarjeta del sensor B', () => {
      capturarTarjeta(SENSOR_B, 'TC-M03-177_productor_sensor_B');
    });

    it('[TC-M03-177][ASSERT][UI-177-02] Productor: la tarjeta del sensor B muestra 25 y no el valor anómalo', () => {
      tarjeta(SENSOR_B).then(($c) => {
        const v = valorMostrado($c);
        expect(cerca(v, VALOR_B), `valor mostrado ${v}`).to.eq(true);
        expect(cerca(v, VALOR_FUERA), `valor mostrado ${v} frente al anómalo ${VALOR_FUERA}`).to.eq(false);
      });
    });

    it('[TC-M03-177][ASSERT][UI-177-03] Productor: la tarjeta del sensor B señala la anomalía (ROJO / ícono)', () => {
      tarjeta(SENSOR_B).then(($c) => {
        const texto = $c.text();
        const etiquetas = [...$c.find('[aria-label]')].map((e) => e.getAttribute('aria-label') || '');
        const indicador = /fuera de rango/i.test(texto) || etiquetas.some((e) => /anomal|advertencia|fuera de rango/i.test(e));
        expect(indicador, `texto="${texto}"; aria=${JSON.stringify(etiquetas)}`).to.eq(true);
      });
    });

    it('[TC-M03-178][ASSERT][UI-178-01] Productor: la tarjeta del sensor C es visible', () => {
      capturarTarjeta(SENSOR_C, 'TC-M03-178_productor_sensor_C');
    });

    it('[TC-M03-178][ASSERT][UI-178-02] Productor: no muestra el valor ERROR_CALIBRACION como lectura operativa', () => {
      tarjeta(SENSOR_C).then(($c) => {
        const v = valorMostrado($c);
        expect(VALORES_C.some((x) => cerca(v, x)), `valor mostrado ${v}`).to.eq(false);
      });
    });

    it('[TC-M03-178][ASSERT][UI-178-03] Productor: la tarjeta no muestra datos técnicos (batería %, dBm)', () => {
      tarjeta(SENSOR_C).then(($c) => {
        const texto = $c.text();
        expect(/\d+(?:\.\d+)?\s*%/.test(texto), `batería en "${texto}"`).to.eq(false);
        expect(/-?\d+(?:\.\d+)?\s*dBm/.test(texto), `RSSI en "${texto}"`).to.eq(false);
      });
    });
  });

  describe('Ingeniero de Campo', () => {
    it('[TC-M03-178][PRE][PRE-UI-01] Ingeniero: la UI recibe el dashboard real del sandbox', () => {
      estado.peticionesFueraSandbox = [];
      registrarSandbox();
      iniciarSesion(env('ENG_EMAIL'), env('ENG_PASSWORD'));
      abrirMonitoreo(SENSOR_C);
      cy.then(() => {
        expect(estado.peticionesFueraSandbox, 'peticiones no atendidas en el sandbox').to.have.length(0);
        estado.pre.eng = true;
      });
    });

    it('[TC-M03-178][ASSERT][UI-178-04] Ingeniero: la tarjeta del sensor C es visible', () => {
      capturarTarjeta(SENSOR_C, 'TC-M03-178_ingeniero_sensor_C');
    });

    it('[TC-M03-178][ASSERT][UI-178-05] Ingeniero: el detalle muestra ERROR_CALIBRACION / requiere calibración', () => {
      tarjeta(SENSOR_C).click();
      cy.get('[role="dialog"]', { timeout: 10000 }).should('be.visible').then(($d) => {
        const texto = $d.text();
        expect(/ERROR_CALIBRACION|requiere calibraci/i.test(texto), `detalle="${texto}"`).to.eq(true);
      });
      cy.get('[role="dialog"]').screenshot('TC-M03-178_ingeniero_detalle_sensor_C');
    });
  });
});
