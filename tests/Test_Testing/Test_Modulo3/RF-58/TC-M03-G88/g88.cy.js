// Conserva el prefijo BASE en la URL de login y en la navegacion SPA.
const FRONT = String(Cypress.config('baseUrl') || '').replace(/\/+$/, '');
const BASE = new URL(FRONT).pathname.replace(/\/+$/, '');
const ORIGEN_FRONT = new URL(FRONT).origin;
const urlFrontendQA = (ruta) => `${FRONT}${ruta}`;
const navegarSpa = (ruta) => cy.window().then((win) => {
  win.history.pushState({}, '', `${BASE}${ruta}`);
  win.dispatchEvent(new win.PopStateEvent('popstate'));
}).then(() => cy.location('pathname').should('eq', `${BASE}${ruta}`));

// TC-M03-G88 — verificación visual (RF-58) de TC-M03-180: variable sin umbral configurado.
//
// TEST: lo ejecuta g88.mjs despues de Newman y reutiliza el login ya efectuado.
// LOCAL: lo ejecuta pruebas/g88_ui_local.mjs con fixtures sinteticas.
// Los nombres de prueba siguen el formato [CASO][PRE|ASSERT][ID].

const env = (k) => Cypress.env(k);
const LOCAL = env('MODO_LOCAL') === true;
const AUTORIZADO = LOCAL
  ? env('AUTORIZADO_RUN') === 'LOCAL' && /^http:\/\/127\.0\.0\.1:\d+$/.test(FRONT)
    && /^http:\/\/127\.0\.0\.1:\d+$/.test(env('API_BASE') || '') && !!env('LOCAL_FIXTURES')
  : env('AUTORIZADO_RUN') === 'SI' && !!env('RUN_ID') && !!env('SANDBOX_SECRET')
    && /^https:\/\//.test(env('API_BASE') || '');

const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN_ID = env('RUN_ID');
const SENSOR_180 = env('SENSOR_180_NOMBRE');
const ID_INFRA = env('ID_INFRA');
const aliasDashboard = (url) => new URL(url).searchParams.get('id_infraestructura') === String(ID_INFRA)
  ? 'dashboardArea' : 'dashboard';
const VALOR_180 = Number(env('VALOR_180'));
const UNIDAD_180 = env('UNIDAD_180');

const estado = { pre: false, peticionesFueraSandbox: [], sinFixture: [], peticionesApi: 0, operaciones172: [], solicitudes: [],
  excepciones172: [], login: [] };
const carpetaEvidencia = () => String(env('ARTIFACTS_DIR') || '');
const leerCabecera = (headers, nombre) => Object.entries(headers ?? {}).find(([clave]) => clave.toLowerCase() === nombre.toLowerCase())?.[1];
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
  if (LOCAL) {
    cy.intercept({ url: '**' }, (req) => {
      const u = new URL(req.url);
      if (u.hostname !== '127.0.0.1') {
        estado.peticionesFueraSandbox.push(`${req.method} destino externo`); req.destroy(); return;
      }
      if (u.origin === ORIGEN_FRONT) { req.continue(); return; }
      if (u.origin !== API) {
        estado.peticionesFueraSandbox.push(`${req.method} puerto local no previsto`); req.destroy(); return;
      }
      const rol = env('CHECK_172') === 'SI' ? 'admin' : 'prod';
      const f = env('LOCAL_FIXTURES')[rol];
      const ruta = u.pathname;
      const responder = (body, alias) => {
        if (alias) req.alias = alias;
        req.headers['x-test-run-id'] = RUN_ID;
        req.reply({ statusCode: 200, headers: { 'x-test-run-id': RUN_ID,
          'access-control-allow-origin': ORIGEN_FRONT, 'access-control-allow-credentials': 'true' }, body });
      };
      if (req.method === 'OPTIONS') req.reply({ statusCode: 204, headers: {
        'access-control-allow-origin': ORIGEN_FRONT, 'access-control-allow-credentials': 'true',
        'access-control-allow-methods': 'GET, POST, OPTIONS',
        'access-control-allow-headers': 'Authorization, Content-Type, X-Zona-Horaria' } });
      else if (req.method === 'POST' && ruta === '/sesiones/') responder(f.login, 'login');
      else if (req.method === 'GET' && ruta === '/usuarios/me') responder(f.perfil, 'usuarioSesion');
      else if (req.method === 'GET' && ruta === '/sesiones/me/permisos') responder(f.permisos, 'permisosSesion');
      else if (req.method === 'GET' && ruta === '/iot/monitoreo/dashboard') responder(f.dashboard, aliasDashboard(req.url));
      else if (req.method === 'GET' && ruta === '/configuracion/especies') responder(f.especies, 'especies');
      else if (req.method === 'GET' && ruta === '/configuracion/ciclos') responder({ total: 0, items: [] });
      else if (req.method === 'GET' && ruta === '/configuracion/variables-ambientales') responder(f.variables);
      else if (req.method === 'GET' && ruta === '/configuracion/umbrales') responder(f.umbrales);
      else if (req.method === 'GET' && ruta === '/notificaciones') responder({ total: 0, no_leidas: 0, pagina: 1, tamano: 20, items: [] });
      else if (req.method === 'GET' && ruta === '/configuracion/interfaz/contexto') responder(f.contexto);
      else if (req.method === 'GET' && ruta === '/configuracion/personalizacion/dashboard') responder(f.layout);
      else if (req.method === 'GET' && ruta === '/configuracion/personalizacion/dashboard/widgets') responder([]);
      else if (req.method === 'GET' && ruta === '/configuracion/personalizacion/dashboard/datos') responder([]);
      else if (req.method === 'GET' && ruta === '/configuracion/personalizacion/tema') responder({ theme_mode: 1, fuente: 'defecto', id_tema_visual: null });
      else if (req.method === 'GET' && ruta === '/configuracion/personalizacion/idioma') responder({ locale_code: 'es-CO', fuente: 'defecto', id_preferencia_idioma: null });
      else {
        estado.sinFixture.push(`${req.method} ${ruta}`);
        req.reply({ statusCode: 404, body: { message: 'Ruta sin fixture local' } });
      }
    });
    return;
  }
  cy.intercept({ url: `${API}/**` }, (req) => {
    estado.peticionesApi++;
    if (estado.peticionesApi > MAX_UI_API) throw new Error('LIMITE_UI_API: 50 peticiones.');
    const ruta = rutaPublica(req.url);
    if (req.method === 'GET' && ruta === '/iot/monitoreo/dashboard') req.alias = aliasDashboard(req.url);
    if (req.method === 'GET' && ruta === '/configuracion/especies') req.alias = 'especies';
    if (req.method === 'GET' && ruta === '/sesiones/me/permisos') req.alias = 'permisosSesion';
    if (req.method === 'GET' && ruta === '/usuarios/me') req.alias = 'usuarioSesion';
    const registro = { metodo: req.method, ruta, inicio: new Date().toISOString(),
      estado: 'PENDIENTE', duracion_ms: null, http: null, error: null,
      cabecera_run_enviada: false };
    if (req.method === 'POST' && ruta === '/sesiones/') {
      req.alias = 'login';
      const sesion = env(env('CHECK_172') === 'SI' ? 'ADMIN_LOGIN' : 'PROD_LOGIN');
      if (sesion?.token) {
        req.reply({ statusCode: 200, headers: { 'x-test-run-id': RUN_ID }, body: sesion });
        return;
      }
      registro.cookie_previa_presente = !!leerCabecera(req.headers, 'cookie');
      registro.authorization_previa_presente = !!leerCabecera(req.headers, 'authorization');
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
      req.headers['x-test-run-id'] = RUN_ID;
      req.headers['X-Sandbox-Secret'] = env('SANDBOX_SECRET');
      registro.cabecera_run_enviada = true;
      registro.cabecera_sandbox_enviada = !!env('SANDBOX_SECRET');
      req.continue((res) => {
        registro.estado = 'RESPUESTA';
        registro.duracion_ms = Date.now() - inicio;
        registro.http = res.statusCode;
        if (req.method === 'POST' && ruta === '/sesiones/refresh' && res.statusCode === 200
          && typeof res.body?.token === 'string') Cypress.env('TOKEN_REFRESH', res.body.token);
        if (req.method === 'POST' && ruta === '/sesiones/') {
          registro.cookie_refresco_respuesta_presente = !!leerCabecera(res.headers, 'set-cookie');
          registro.token_respuesta_presente = res.statusCode === 200 && !!res.body?.token;
          if (res.statusCode !== 200) estado.login.push({ hora: registro.inicio,
            ruta, http: res.statusCode, cabecera_run_enviada: registro.cabecera_run_enviada,
            eco_run_correcto: leerCabecera(res.headers, 'x-test-run-id') === RUN_ID,
            cuerpo_error_saneado: cuerpoSeguro(res.body) });
        }
        liberar();
        const eco = leerCabecera(res.headers, 'x-test-run-id');
        if (req.method !== 'OPTIONS' && eco !== RUN_ID) {
          estado.peticionesFueraSandbox.push(`${req.method} ${ruta} -> ${res.statusCode}`);
        }
      });
    });
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
  cy.wait('@login', { requestTimeout: 90000, responseTimeout: 90000 }).then(({ response }) => {
    expect(response?.statusCode, 'HTTP login; detalle saneado en UI-*-login-error.json').to.eq(200);
    expect(leerCabecera(response?.headers, 'x-test-run-id'), 'login atendido en el RUN').to.eq(RUN_ID);
    expect(response?.body?.token, 'token vigente de la UI').to.be.a('string');
  });
  // AuthContext consulta ambas rutas tras el login; terminarlas antes de navegar
  // evita que la siguiente sesión del ejecutor herede peticiones pendientes.
  for (const alias of ['@usuarioSesion', '@permisosSesion']) {
    cy.wait(alias, { requestTimeout: 90000, responseTimeout: 90000 }).then(({ request, response }) => {
      expect(leerCabecera(request.headers, 'x-test-run-id'), `${alias} enviado al RUN`).to.eq(RUN_ID);
      expect(response.statusCode, `${alias} HTTP`).to.eq(200);
      expect(leerCabecera(response.headers, 'x-test-run-id'), `${alias} atendido en RUN`).to.eq(RUN_ID);
    });
  }
}

function abrirMonitoreo(nombreSensor) {
  navegarSpa('/telemetria/monitoreo');
  cy.wait('@dashboard', { requestTimeout: 90000, responseTimeout: 90000 }).then((i) => {
    expect(i.response.statusCode, 'HTTP del dashboard').to.eq(200);
    expect(leerCabecera(i.response.headers, 'x-test-run-id'), 'X-Test-Run-Id devuelto por el backend').to.eq(RUN_ID);
  });
  cy.contains('desde caché').should('not.exist');
  cy.get('[role="combobox"]#monitoreo-area').clear().type(`${ID_INFRA}{enter}`);
  cy.wait('@dashboardArea', { requestTimeout: 90000, responseTimeout: 90000 }).then((i) => {
    expect(i.request.url, 'filtro por unidad').to.include(`id_infraestructura=${ID_INFRA}`);
    expect(i.response.statusCode).to.eq(200);
    expect(leerCabecera(i.response.headers, 'x-test-run-id')).to.eq(RUN_ID);
  });
  cy.contains('button', /Auto ON/).click();
  cy.contains('desde caché').should('not.exist');
}

function tarjeta(nombre) {
  cy.get(`button[aria-controls="area-${ID_INFRA}"]`).then(($area) => {
    if ($area.attr('aria-expanded') === 'false') cy.wrap($area).click();
  });
  return cy.contains(`#area-${ID_INFRA} button.ds-option--card`, nombre, { timeout: 20000 });
}

function capturaFila(nombre, archivo) {
  tarjeta(nombre).scrollIntoView().should('be.visible').then(($fila) => {
    const rect = $fila[0].getBoundingClientRect();
    const vista = $fila[0].ownerDocument.defaultView;
    if (rect.width < 20 || rect.height < 20 || rect.top < 0 || rect.bottom > vista.innerHeight
      || rect.left < 0 || rect.right > vista.innerWidth)
      throw new Error(`ERROR_QA_EVIDENCIA: ${archivo}: fila fuera de vista o menor de 20 px`);
    const pill = [...$fila.find('span')].filter((e) => /^Sin umbral configurado$/i.test((e.textContent || '').trim()) && e.querySelector('svg')).at(-1);
    if (pill) {
      const caja = pill.getBoundingClientRect();
      const estilo = vista.getComputedStyle(pill);
      const recorta = (modo, visible, total) => /^(auto|hidden|clip|scroll)$/.test(modo) && visible > 0 && total > visible + 1;
      if (caja.height < 8 || caja.top < 0 || caja.bottom > vista.innerHeight
        || recorta(estilo.overflowX, pill.clientWidth, pill.scrollWidth)
        || recorta(estilo.overflowY, pill.clientHeight, pill.scrollHeight))
        throw new Error(`ERROR_QA_EVIDENCIA: ${archivo}: píldora recortada o menor de 8 px`);
    }
  });
  cy.screenshot(archivo, { capture: 'viewport' });
  cy.task('verificarCapturaG88', archivo, { log: false }).then((e) => {
    if (!e.ok) throw new Error(`ERROR_QA_EVIDENCIA: ${archivo}: ${e.motivo}`);
  });
}

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
  const patron = new RegExp(`^\\s*(-?\\d+(?:[.,]\\d+)?)\\s*${unidad}\\s*$`, 'i');
  for (const e of $card.find('span')) {
    if (e.querySelector('span')) continue;
    const m = (e.textContent || '').match(patron);
    if (m) return Number(m[1].replace(',', '.'));
  }
  return null;
}

(env('CHECK_180') === 'SI' ? describe : describe.skip)('TC-M03-G88 — UI de Monitoreo (RF-58, TC-M03-180)', () => {
  afterEach(() => {
    if (LOCAL) cy.task('registrarRutasLocalesG88', estado.sinFixture, { log: false });
    if (!LOCAL && env('TOKEN_REFRESH')) cy.task('guardarTokenRefrescoG88', env('TOKEN_REFRESH'), { log: false });
    if (!AUTORIZADO || !carpetaEvidencia()) return;
    cy.writeFile(`${carpetaEvidencia()}/UI-180-solicitudes.json`, estado.solicitudes);
    cy.writeFile(`${carpetaEvidencia()}/UI-180-login-error.json`, estado.login);
  });
  before(() => {
    if (!AUTORIZADO) {
      throw new Error('BLOQUEO_G88: spec sin autorización de ejecución; usar g88.mjs.');
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
    cy.screenshot('TC-M03-180_vista_monitoreo', { capture: 'viewport' });
    cy.task('verificarCapturaG88', 'TC-M03-180_vista_monitoreo', { log: false }).then((e) => {
      if (!e.ok) throw new Error(`ERROR_QA_EVIDENCIA: vista 180: ${e.motivo}`);
    });
    capturaFila(SENSOR_180, 'TC-M03-180_productor_sensor_sin_umbral');
  });

  it('[TC-M03-180][ASSERT][UI-180-02] La tarjeta muestra el valor y la unidad', () => {
    tarjeta(SENSOR_180).then(($c) => {
      const v = valorMostrado($c, UNIDAD_180);
      expect(v !== null && Math.abs(v - VALOR_180) < 0.0001, `valor mostrado ${v} ${UNIDAD_180}`).to.eq(true);
    });
  });

  it('[TC-M03-180][ASSERT][UI-180-03] La tarjeta muestra la etiqueta «Sin umbral configurado»', () => {
    tarjeta(SENSOR_180).then(($c) => {
      const texto = $c.text();
      const etiquetas = [...$c.find('[aria-label],[title]')].map((e) => `${e.getAttribute('aria-label') || ''} ${e.getAttribute('title') || ''}`);
      const visible = /sin umbral configurado/i.test(texto) || etiquetas.some((e) => /sin umbral configurado/i.test(e));
      expect(visible, `texto="${texto}"`).to.eq(true);
      const pill = [...$c.find('span')].filter((e) => /^Sin umbral configurado$/i.test((e.textContent || '').trim()) && e.querySelector('svg')).at(-1);
      expect(pill, 'píldora GRIS de variable sin umbral').to.exist;
      expect(pill.style.color, 'color neutro del semáforo GRIS').to.eq('var(--text-muted)');
    });
    tarjeta(SENSOR_180).contains('Sin umbral configurado').should('be.visible');
  });
});

// Lectura pública de la pantalla M09. Se bloquea toda escritura ajena a sesiones.
(env('CHECK_172') === 'SI' ? describe : describe.skip)('TC-M03-172 — T configurable en M09', () => {
  afterEach(() => {
    if (LOCAL) cy.task('registrarRutasLocalesG88', estado.sinFixture, { log: false });
    if (!LOCAL && env('TOKEN_REFRESH')) cy.task('guardarTokenRefrescoG88', env('TOKEN_REFRESH'), { log: false });
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
    navegarSpa('/configuracion');
    cy.contains('button', /por especie/i).click();
    cy.wait('@especies', { requestTimeout: 90000, responseTimeout: 90000 }).then(({ response }) => {
      expect(response?.statusCode, 'GET especies').to.eq(200);
      const especie = (response?.body?.items ?? []).find((x) => Number(x.id_especie) === Number(env('ID_ESPECIE')));
      expect(especie?.nombre, 'nombre de la especie del dispositivo').to.be.a('string');
      cy.contains('button', especie.nombre).click();
    });
    cy.contains('button', /umbrales ambientales/i).click();
    cy.get('body').then(() => {
      estado.excepciones172.forEach((e) => { e.navegacion_m09_verificada = true; });
    });
    cy.get('button[aria-label]').filter((_, e) => e.getAttribute('aria-label') === `Editar umbral ${env('VARIABLE_NOMBRE')}`).click();
    cy.get('[role="dialog"]').scrollIntoView().should('be.visible');
    cy.screenshot('TC-M03-172_formulario_umbral_sin_guardar', { capture: 'viewport' });
    cy.task('verificarCapturaG88', 'TC-M03-172_formulario_umbral_sin_guardar', { log: false }).then((e) => {
      if (!e.ok) throw new Error(`ERROR_QA_EVIDENCIA: formulario 172: ${e.motivo}`);
    });
    cy.get('[role="dialog"]').then(($dialogo) => {
      const controles = [...$dialogo.find('label,input,select')].map((e) =>
        [e.textContent, e.getAttribute('name'), e.getAttribute('id'), e.getAttribute('aria-label')].join(' '));
      const hayT = controles.some((x) => /toleran|toleranc|tolerance|(?:^|\s)T(?:\s|$)/i.test(x));
      expect(hayT, 'control de T o tolerancia en formulario').to.eq(true);
      const entradaT = [...$dialogo.find('input,select')].find((e) => {
        const label = e.id ? $dialogo.find('label').filter((_, l) => l.htmlFor === e.id).text() : '';
        return /toleran|toleranc|tolerance|(?:^|\s)T(?:\s|$)/i.test(
          [label, e.name, e.id, e.getAttribute('aria-label')].join(' '));
      });
      expect(entradaT, 'entrada editable de T en formulario').to.exist;
      if (entradaT.tagName === 'SELECT') cy.wrap(entradaT).select('2').should('have.value', '2');
      else cy.wrap(entradaT).clear().type('2').should('have.value', '2');
    });
  });
});

