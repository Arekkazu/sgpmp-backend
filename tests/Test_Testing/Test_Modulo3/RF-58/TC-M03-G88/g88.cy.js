// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

// TC-M03-G88 â€” verificaciÃ³n visual (RF-58) de TC-M03-180: variable sin umbral configurado.
//
// Se ejecuta SOLO desde g88.mjs (configuraciÃ³n en lÃ­nea), despuÃ©s de
// que Newman haya registrado la lectura dentro del sandbox. No usa mocks: cy.intercept
// solo aÃ±ade las cabeceras del sandbox a las peticiones reales, las serializa y observa
// las respuestas. Los nombres de prueba siguen el formato [CASO][PRE|ASSERT][ID].

const env = (k) => Cypress.env(k);
const AUTORIZADO = env('AUTORIZADO_RUN') === 'SI' && !!env('RUN_ID') && /^https:\/\//.test(env('API_BASE') || '');

const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN_ID = env('RUN_ID');
const SENSOR_180 = env('SENSOR_180_NOMBRE');
const ID_INFRA = env('ID_INFRA');
const VALOR_180 = Number(env('VALOR_180'));
const UNIDAD_180 = env('UNIDAD_180');

const estado = { pre: false, peticionesFueraSandbox: [], peticionesApi: 0, operaciones172: [], solicitudes: [],
  excepciones172: [], login: [] };
const carpetaEvidencia = () => String(env('ARTIFACTS_DIR') || '');
function textoSeguro(valor) {
  let limpio = String(valor ?? '').slice(0, 1500);
  for (const secreto of [env('SANDBOX_SECRET'), env('PROD_PASSWORD'), env('ADMIN_PASSWORD'),
    env('PROD_EMAIL'), env('ADMIN_EMAIL')]) {
    if (typeof secreto === 'string' && secreto.length >= 4) limpio = limpio.split(secreto).join('[REDACTADO]');
  }
  return limpio
    .replace(/\?[^\s'"<>]*/g, '?[QUERY_OMITIDA]')
    .replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g, '[JWT_REDACTADO]')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[CORREO_REDACTADO]')
    .replace(/Bearer\s+\S+/gi, 'Bearer [REDACTADO]')
    .replace(/[A-Za-z0-9_\-]{40,}/g, '[VALOR_REDACTADO]');
}
function cuerpoSeguro(valor) {
  if (typeof valor === 'string') return textoSeguro(valor);
  if (Array.isArray(valor)) return valor.slice(0, 10).map(cuerpoSeguro);
  if (!valor || typeof valor !== 'object') return valor;
  return Object.fromEntries(Object.entries(valor).slice(0, 20).map(([k, v]) =>
    [k,
      /password|contrasena|token|secret|cookie|authorization|email|correo|serial/i.test(k)
        ? '[REDACTADO]' : cuerpoSeguro(v)]));
}
// Solo se tolera la promesa del dashboard inicial de UI-172. La prueba debe llegar
// después al formulario M09; cualquier otra excepción conserva el fallo de Cypress.
Cypress.on('uncaught:exception', (error) => {
  const mensaje = String(error?.message ?? '');
  const origen = '/configuracion/personalizacion/dashboard/datos';
  const ruta = Cypress.state('window')?.location?.pathname ?? '';
  if (env('CHECK_172') === 'SI' && /unhandled promise rejection/i.test(mensaje)
      && mensaje.includes(origen) && /\/dashboard\/?$/.test(ruta)) {
    estado.excepciones172.push({ tipo: 'PROMESA_RECHAZADA_DASHBOARD', mensaje: textoSeguro(mensaje),
      ruta_pagina: ruta, ruta_api: origen, hora: new Date().toISOString(),
      http: estado.solicitudes.findLast((x) => x.ruta === origen)?.http ?? null,
      navegacion_m09_verificada: false });
    return false;
  }
  return undefined;
});
Cypress.on('fail', (error) => {
  const pendiente = [...estado.solicitudes].reverse().find((x) =>
    x.estado === 'PENDIENTE' && x.cabecera_run_enviada);
  if (pendiente) {
    pendiente.estado = 'ERROR_SIN_RESPUESTA';
    pendiente.duracion_ms = Date.now() - Date.parse(pendiente.inicio);
    pendiente.error = String(error.message).split('\n')[0];
  }
  throw error;
});
const MAX_UI_API = 50;
const SESIONES_UI_172 = new Set(['POST /sesiones/', 'POST /sesiones/refresh', 'DELETE /sesiones/']);
function rutaPublica(url) {
  try { return new URL(url).pathname.replace(new URL(API).pathname.replace(/\/+$/, ''), '') || '/'; }
  catch { return '[RUTA_INVALIDA]'; }
}
function escrituraUi172(method, url) {
  const ruta = rutaPublica(url);
  return method !== 'GET' && method !== 'OPTIONS' && !SESIONES_UI_172.has(`${method} ${ruta}`)
    ? `UI-172: escritura inesperada ${method} ${ruta}` : null;
}
function finalidadUi172(method, ruta) {
  if (method === 'POST' && ruta === '/sesiones/') return 'AUTENTICACION';
  if (method === 'POST' && ruta === '/sesiones/refresh') return 'REFRESCO_SESION';
  if (method === 'DELETE' && ruta === '/sesiones/') return 'CIERRE_SESION';
  if (method === 'GET') return 'CONSULTA_LECTURA';
  if (method === 'OPTIONS') return 'PREFLIGHT_CORS';
  return 'ESCRITURA_NO_AUTORIZADA';
}

// El sandbox comparte una Session por RUN; la UI espera la respuesta anterior.
let cola = Promise.resolve();

function registrarSandbox() {
  cy.intercept({ url: `${API}/**` }, (req) => {
    estado.peticionesApi++;
    if (estado.peticionesApi > MAX_UI_API) throw new Error('LIMITE_UI_API: 50 peticiones.');
    const ruta = rutaPublica(req.url);
    if (req.method === 'GET' && ruta === '/sesiones/me/permisos') req.alias = 'permisosSesion';
    if (req.method === 'GET' && ruta === '/usuarios/me') req.alias = 'usuarioSesion';
    const registro = { metodo: req.method, ruta, inicio: new Date().toISOString(),
      estado: 'PENDIENTE', duracion_ms: null, http: null, error: null,
      cabecera_run_enviada: false };
    if (req.method === 'POST' && ruta === '/sesiones/') {
      registro.cookie_previa_presente = !!req.headers.cookie;
      registro.authorization_previa_presente = !!req.headers.authorization;
    }
    estado.solicitudes.push(registro);
    const inicio = Date.now();
    if (env('CHECK_172') === 'SI') estado.operaciones172.push({
      metodo: req.method, ruta, finalidad: finalidadUi172(req.method, ruta),
      permitida: !escrituraUi172(req.method, req.url),
    });
    if (req.method !== 'GET' && req.method !== 'OPTIONS'
      && /^\/configuracion\/umbrales(?:\/|\?|$)/.test(ruta))
      throw new Error(`SEGURIDAD_M09: escritura UI prohibida ${req.method} ${ruta}`);
    const escritura = env('CHECK_172') === 'SI' ? escrituraUi172(req.method, req.url) : null;
    if (escritura) throw new Error(escritura);
    let liberar;
    const turno = cola;
    cola = new Promise((resolve) => { liberar = resolve; });
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN_ID;
      req.headers['X-Sandbox-Secret'] = env('SANDBOX_SECRET');
      registro.cabecera_run_enviada = true;
      registro.cabecera_sandbox_enviada = !!env('SANDBOX_SECRET');
      req.continue((res) => {
        registro.estado = 'RESPUESTA';
        registro.duracion_ms = Date.now() - inicio;
        registro.http = res.statusCode;
        if (req.method === 'POST' && ruta === '/sesiones/') {
          registro.cookie_refresco_respuesta_presente = !!res.headers['set-cookie'];
          registro.token_respuesta_presente = res.statusCode === 200 && !!res.body?.token;
          if (res.statusCode !== 200) estado.login.push({ hora: registro.inicio,
            ruta, http: res.statusCode, cabecera_run_enviada: registro.cabecera_run_enviada,
            eco_run_correcto: res.headers['x-test-run-id'] === RUN_ID,
            cuerpo_error_saneado: cuerpoSeguro(res.body) });
        }
        liberar();
        const eco = res.headers['x-test-run-id'];
        if (req.method !== 'OPTIONS' && eco !== RUN_ID) {
          estado.peticionesFueraSandbox.push(`${req.method} ${ruta} -> ${res.statusCode}`);
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
      // El dashboard tiene cachÃ© local (IndexedDB); se descarta para no mezclar datos previos.
      if (win.indexedDB && typeof win.indexedDB.databases === 'function') {
        win.indexedDB.databases().then((dbs) => dbs.forEach((d) => d.name && win.indexedDB.deleteDatabase(d.name)));
      }
    },
  });
  cy.get('input[type="email"]').clear().type(correo, { log: false });
  cy.get('input[type="password"]').clear().type(clave, { log: false });
  cy.get('button[type="submit"]').click();
  cy.wait('@login').then(({ response }) => {
    expect(response?.statusCode, 'HTTP login; detalle saneado en UI-*-login-error.json').to.eq(200);
    expect(response?.headers['x-test-run-id'], 'login atendido en el RUN').to.eq(RUN_ID);
  });
  // AuthContext consulta ambas rutas tras el login; terminarlas antes de navegar
  // evita que la siguiente sesión del ejecutor herede peticiones pendientes.
  for (const alias of ['@usuarioSesion', '@permisosSesion']) {
    cy.wait(alias).then(({ request, response }) => {
      expect(request.headers['X-Test-Run-Id'], `${alias} enviado al RUN`).to.eq(RUN_ID);
      expect(response.statusCode, `${alias} HTTP`).to.eq(200);
      expect(response.headers['x-test-run-id'], `${alias} atendido en RUN`).to.eq(RUN_ID);
    });
  }
}

function abrirMonitoreo(nombreSensor) {
  cy.visit(urlFrontendQA('/telemetria/monitoreo'));
  cy.wait('@dashboard').then((i) => {
    expect(i.response.statusCode, 'HTTP del dashboard').to.eq(200);
    expect(i.response.headers['x-test-run-id'], 'X-Test-Run-Id devuelto por el backend').to.eq(RUN_ID);
  });
  cy.contains('desde cachÃ©').should('not.exist');
  // Si el sensor no estÃ¡ en la primera pÃ¡gina, se filtra por la unidad productiva del RUN.
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

/** Valor numÃ©rico mostrado por el indicador (aria-label "â€¦: <valor> <unidad>"). */
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

(env('CHECK_180') === 'SI' ? describe : describe.skip)('TC-M03-G88 — UI de Monitoreo (RF-58, TC-M03-180)', () => {
  afterEach(() => {
    if (!AUTORIZADO || !carpetaEvidencia()) return;
    cy.writeFile(`${carpetaEvidencia()}/UI-180-solicitudes.json`, estado.solicitudes);
    cy.writeFile(`${carpetaEvidencia()}/UI-180-login-error.json`, estado.login);
  });
  beforeEach(() => {
    if (!AUTORIZADO) {
      throw new Error('BLOQUEO_G88: spec sin autorizaciÃ³n de ejecuciÃ³n; usar g88.mjs.');
    }
    registrarSandbox();
    iniciarSesion(env('PROD_EMAIL'), env('PROD_PASSWORD'));
    abrirMonitoreo(SENSOR_180);
  });

  it('[TC-M03-180][PRE][PRE-UI-01] Productor: la UI recibe el dashboard real del sandbox', () => {
    cy.then(() => {
      expect(estado.peticionesFueraSandbox, 'peticiones no atendidas en el sandbox').to.have.length(0);
      estado.pre = true;
    });
  });

  it('[TC-M03-180][ASSERT][UI-180-01] La tarjeta de la variable sin umbral es visible', () => {
    cy.get('body').then(($b) => {
      // Una sola captura de la vista si la tarjeta no aparece; si aparece, solo la tarjeta.
      if (!$b.find(`button.ds-option:contains("${SENSOR_180}")`).length) cy.screenshot('TC-M03-180_sin_tarjeta', { capture: 'viewport' });
      tarjeta(SENSOR_180).scrollIntoView().should('be.visible').screenshot('TC-M03-180_productor_sensor_sin_umbral');
    });
  });

  it('[TC-M03-180][ASSERT][UI-180-02] La tarjeta muestra el valor y la unidad', () => {
    tarjeta(SENSOR_180).then(($c) => {
      const v = valorMostrado($c, UNIDAD_180);
      expect(v !== null && Math.abs(v - VALOR_180) < 0.0001, `valor mostrado ${v} ${UNIDAD_180}`).to.eq(true);
    });
  });

  it('[TC-M03-180][ASSERT][UI-180-03] La tarjeta muestra la etiqueta Â«Sin umbral configuradoÂ»', () => {
    tarjeta(SENSOR_180).then(($c) => {
      const texto = $c.text();
      const etiquetas = [...$c.find('[aria-label],[title]')].map((e) => `${e.getAttribute('aria-label') || ''} ${e.getAttribute('title') || ''}`);
      const visible = /sin umbral configurado/i.test(texto) || etiquetas.some((e) => /sin umbral configurado/i.test(e));
      expect(visible, `texto="${texto}"`).to.eq(true);
    });
  });
});

// Lectura pública de la pantalla M09. Se bloquea toda escritura ajena a sesiones.
(env('CHECK_172') === 'SI' ? describe : describe.skip)('TC-M03-172 — T configurable en M09', () => {
  afterEach(() => {
    if (!AUTORIZADO || !carpetaEvidencia()) return;
    cy.writeFile(`${carpetaEvidencia()}/UI-172-operaciones.json`, estado.operaciones172);
    cy.writeFile(`${carpetaEvidencia()}/UI-172-solicitudes.json`, estado.solicitudes);
    cy.writeFile(`${carpetaEvidencia()}/UI-172-login-error.json`, estado.login);
    cy.writeFile(`${carpetaEvidencia()}/UI-172-excepciones.json`, estado.excepciones172);
  });
  it('[TC-M03-172][ASSERT][UI-172] El formulario de umbral permite configurar T', () => {
    if (!AUTORIZADO) throw new Error('BLOQUEO_G88: falta RUN autorizado.');
    registrarSandbox();
    cy.intercept({ method: 'GET', url: `${API}/configuracion/especies*` }).as('especies');
    iniciarSesion(env('ADMIN_EMAIL'), env('ADMIN_PASSWORD'));
    cy.visit(urlFrontendQA('/configuracion'));
    cy.contains('button', /por especie/i).click();
    cy.wait('@especies').then(({ response }) => {
      expect(response?.statusCode, 'GET especies').to.eq(200);
      const especie = (response?.body?.items ?? []).find((x) => Number(x.id_especie) === Number(env('ID_ESPECIE')));
      expect(especie?.nombre, 'nombre de la especie del dispositivo').to.be.a('string');
      cy.contains('button', especie.nombre).click();
    });
    cy.contains('button', /umbrales ambientales/i).click();
    cy.get('body').then(() => {
      estado.excepciones172.forEach((e) => { e.navegacion_m09_verificada = true; });
    });
    cy.contains('button', `Editar umbral ${env('VARIABLE_NOMBRE')}`).click();
    cy.get('[role="dialog"]').should('be.visible').screenshot('TC-M03-172_formulario_umbral_sin_guardar').then(($dialogo) => {
      const controles = [...$dialogo.find('label,input,select')].map((e) =>
        [e.textContent, e.getAttribute('name'), e.getAttribute('id'), e.getAttribute('aria-label')].join(' '));
      const hayT = controles.some((x) => /toleran|toleranc|tolerance|(?:^|\s)T(?:\s|$)/i.test(x));
      expect(hayT, 'control de T o tolerancia en formulario').to.eq(true);
    });
  });
});

