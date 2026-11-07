// TC-M03-184: UI-184-01 y UI-184-02; solicitudes reales del Productor dentro del RUN.
const { mensajeAusenciaEquivalente, observacionDocumental, clasificarCarga, sesionCon5xx,
  crearColaPeticiones, peticionesSinRespuesta, sinValoresFabricados, evaluarOraculoUi,
  intentarDesactivarAuto, indicadorCargaActivo, esperarRenderEstable } = require('./lib/g93_ui.cjs');
const e = k => Cypress.env(k);
const API = String(e('API_BASE') || '').replace(/\/+$/, '');
const FRONT = String(Cypress.config('baseUrl') || e('FRONT_BASE') || '').replace(/\/+$/, '');
const RUN = e('RUN_ID');
const FASE = e('FASE');
const ID = Number(e('ID_INFRA'));
const NOMBRE = e('NOMBRE_INFRA');
const FECHA = e('FECHA_HISTORICA');
const CARPETA = e('ARTIFACTS_DIR');
const COOKIE_FILE = e('REFRESH_COOKIE_FILE');
const LOGIN_TOKEN = e('PROD_LOGIN_TOKEN');
const ensayo = e('ENSAYO_G93_SPEC_REAL') === 'SI' && /^ENSAYO-G93-\d{8}-\d{6}-[a-z0-9]+$/.test(RUN || '')
  && /^http:\/\/127\.0\.0\.1:\d+$/.test(API) && /^http:\/\/127\.0\.0\.1:\d+$/.test(FRONT)
  && e('ENSAYO_CONTEXTO_TEMPORAL') === 'SI';
const autorizado = e('AUTORIZADO_RUN') === 'SI' && typeof LOGIN_TOKEN === 'string' && LOGIN_TOKEN.length > 0
  && Number.isSafeInteger(ID) && ID > 0
  && (ensayo || /^RUN-G93-V\d+-\d{8}-\d{6}$/.test(RUN || '')
    && /^https:\/\//.test(API) && /^https:\/\//.test(FRONT));
const acta = { caso: 'TC-M03-184', id: `UI-184-${FASE === 'V2' ? '02' : '01'}`,
  fase: FASE, estado: 'NO_CONCLUYENTE', motivo: 'Sin iniciar', criterio: null,
  http: null, error_red: null, peticiones: [], ui_inicial: null, ui_objetivo: null,
  incidencias_tecnicas: [], observaciones_documentales: [], pendiente_al_terminar: false };
let peticiones = 0;
let cookieActual = e('REFRESH_COOKIE');
let cookieRotada = false;
const esperas = {};
const colaApi = crearColaPeticiones();
const urlFront = ruta => `${FRONT}${ruta}`;
const baseFront = FRONT ? new URL(FRONT).pathname.replace(/\/+$/, '') : '';
const navegarSpa = ruta => cy.window().then(win => {
  win.history.pushState({}, '', `${baseFront}${ruta}`);
  win.dispatchEvent(new win.PopStateEvent('popstate'));
}).then(() => cy.location('pathname').should('eq', `${baseFront}${ruta}`));
const rutaApi = url => {
  const base = new URL(API);
  const u = new URL(url);
  return u.pathname.slice(base.pathname.replace(/\/$/, '').length) + u.search;
};
const textoSeguro = valor => {
  let texto = String(valor || '');
  for (const secreto of [e('SANDBOX_SECRET'), e('REFRESH_COOKIE'), cookieActual, LOGIN_TOKEN].filter(Boolean))
    texto = texto.replaceAll(String(secreto), '[RESERVADO]');
  return texto.replace(/Bearer\s+\S+|refresh_token=\S+|[\w.+-]+@[\w.-]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/gi, '[RESERVADO]').slice(0, 300);
};

function crearEspera(ms) {
  let resolver;
  const espera = { cerrada: false, promise: new Promise(resolve => { resolver = resolve; }) };
  const reloj = setTimeout(() => {
    if (!espera.cerrada) { espera.cerrada = true; resolver({ vencio: true, http: null, eco: false }); }
  }, ms);
  espera.terminar = dato => {
    if (espera.cerrada) return;
    espera.cerrada = true;
    clearTimeout(reloj);
    resolver(dato);
  };
  return espera;
}

function interceptar() {
  cy.intercept({ url: `${API}/**` }, req => {
    peticiones++;
    if (peticiones > 25) {
      acta.estado = 'ERROR_QA'; acta.motivo = 'LIMITE_UI_API_25';
      throw new Error(acta.motivo);
    }
    const ruta = rutaApi(req.url);
    if (!['GET', 'OPTIONS'].includes(req.method) && !(req.method === 'POST' && ['/sesiones/', '/sesiones/refresh'].includes(ruta))) {
      acta.estado = 'ERROR_QA'; acta.motivo = `ESCRITURA_UI_INESPERADA ${req.method} ${ruta.split('?')[0]}`;
      throw new Error(acta.motivo);
    }
    if (ruta === '/sesiones/refresh') req.alias = 'refresh';
    if (ruta === '/sesiones/') req.alias = 'login';
    if (ruta === '/usuarios/me') req.alias = 'usuarioSesion';
    if (ruta === '/sesiones/me/permisos') req.alias = 'permisosSesion';
    const dashboard = req.method === 'GET' && ruta.split('?')[0] === '/iot/monitoreo/dashboard';
    const filtro = dashboard ? new URL(req.url).searchParams.get('id_infraestructura') : null;
    const filtroAplicadoPorSpec = dashboard && !filtro;
    if (filtroAplicadoPorSpec) {
      const urlFiltrada = new URL(req.url);
      urlFiltrada.searchParams.set('id_infraestructura', String(ID));
      req.url = urlFiltrada.toString();
    }
    const tamano = dashboard ? new URL(req.url).searchParams.get('por_pagina') : null;
    if (dashboard) req.alias = filtro ? 'dashboardFiltrado'
      : tamano === '1' ? 'dashboardAreas' : 'dashboardGlobal';
    if (filtro === String(ID)) req.alias = 'dashboardObjetivo';
    const tipo = req.alias === 'dashboardGlobal' ? 'global'
      : req.alias === 'dashboardObjetivo' ? 'objetivo' : null;
    // Solo se conservan la ruta relativa y el ID; nunca la URL completa ni cabeceras.
    const rutaSegura = dashboard ? `/iot/monitoreo/dashboard?id_infraestructura=${encodeURIComponent(filtro || ID)}` : ruta.split('?')[0];
    const registro = { metodo: req.method, ruta: rutaSegura, alias: req.alias ?? null,
      filtro_aplicado_por_spec: filtroAplicadoPorSpec,
      inicio: new Date().toISOString(), fin: null, duracion_ms: null, http: null,
      eco_run: false, cabecera_run_enviada: false, error_red: null };
    acta.peticiones.push(registro);
    const inicio = Date.now();
    if (ruta === '/sesiones/' || ruta === '/sesiones/refresh') {
      // La UI usa la sesión ya obtenida por el ejecutor; no rota la cookie ni hace refresh remoto.
      registro.fin = new Date().toISOString();
      registro.duracion_ms = Date.now() - inicio;
      registro.http = ruta === '/sesiones/' ? 200 : 401;
      registro.eco_run = true;
      req.reply({ statusCode: registro.http, headers: { 'x-test-run-id': RUN },
        body: ruta === '/sesiones/' ? { token: LOGIN_TOKEN } : { error_code: 'SIN_SESION_UI' } });
      return;
    }
    return colaApi.tomar(liberar => {
      // Marcar el envio al tomar el turno; cy.wait puede conservar una copia previa del request.
      req.headers['x-test-run-id'] = RUN;
      req.headers['X-Sandbox-Secret'] = e('SANDBOX_SECRET');
      registro.cabecera_run_enviada = true;
      req.continue(res => {
        try {
      // El alias no es estable aquí; conservar el valor capturado al registrar la petición.
          registro.alias_en_callback = registro.alias;
          registro.fin = new Date().toISOString();
          registro.duracion_ms = Date.now() - inicio;
          registro.http = res?.statusCode ?? null;
          registro.eco_run = res?.headers?.['x-test-run-id'] === RUN;
          registro.error_red = res?.error ? textoSeguro(res.error.message || res.error) : null;
          if (registro.alias === 'dashboardGlobal') {
            registro.espera_disponible = Boolean(esperas.global);
            registro.espera_cerrada_antes = Boolean(esperas.global?.cerrada);
          }
          if (tipo === 'global') esperas.global?.terminar({
            http: registro.http, eco: registro.eco_run, errorRed: registro.error_red, vencio: false });
          if (tipo === 'objetivo') esperas.objetivo?.terminar({
            http: registro.http, eco: registro.eco_run, errorRed: registro.error_red, vencio: false });
        } finally { liberar(); }
      });
    }, { alVencer: () => { registro.error_red = 'RESPUESTA_API_AGOTADA'; } });
  });
}

function iniciarSesion() {
  cy.clearCookies();
  cy.clearLocalStorage();
  cy.visit(urlFront('/login'), {
    onBeforeLoad(win) {
      if (win.indexedDB && typeof win.indexedDB.databases === 'function') {
        win.indexedDB.databases().then(bases =>
          bases.forEach(base => base.name && win.indexedDB.deleteDatabase(base.name)));
      }
    },
  });
  // Los datos del formulario son sintéticos: el POST recibe el token del login previo del ejecutor.
  cy.get('input[type="email"]').clear().type('g93-ui@local.invalid', { log: false });
  cy.get('input[type="password"]').clear().type('G93LocalDummy123!', { log: false });
  cy.get('button[type="submit"]').click();
  const login = cy.wait('@login', { requestTimeout: 90000, responseTimeout: 90000 }).then(({ response }) => {
    expect(response?.statusCode, 'HTTP login UI').to.eq(200);
    expect(response?.headers?.['x-test-run-id'], 'eco del RUN en login UI').to.eq(RUN);
  });
  const esperarSesion = alias => cy.wait(alias, { requestTimeout: 90000, responseTimeout: 90000 }).then(({ response }) => {
      if (response?.statusCode >= 500) {
        acta.estado = 'NO_CONCLUYENTE'; acta.criterio = 'SESION_5XX';
        acta.motivo = `${alias} HTTP ${response.statusCode}; dashboard sin evaluación fiable`;
        return;
      }
      const registro = acta.peticiones.filter(x => x.alias === alias.slice(1)).at(-1);
      expect(registro?.cabecera_run_enviada, `${alias} enviado al RUN`).to.eq(true);
      expect(response?.statusCode, `${alias} HTTP`).to.eq(200);
      expect(response?.headers?.['x-test-run-id'], `${alias} atendido en RUN`).to.eq(RUN);
    });
  return login.then(() => esperarSesion('@usuarioSesion')).then(() => {
    if (acta.criterio !== 'SESION_5XX') return esperarSesion('@permisosSesion');
  });
}

function observar($body, filtrada = false) {
  const cuerpo = $body[0];
  const secciones = [...cuerpo.querySelectorAll('section')];
  const normalizar = x => String(x || '').replace(/\s+/g, ' ').trim();
  const nombreObjetivo = normalizar(NOMBRE);
  const unidad = nombreObjetivo && secciones.find(x =>
    normalizar(x.querySelector('button.ds-option > div:first-child > div:nth-child(2) > div:first-child')?.textContent)
      === nombreObjetivo);
  const texto = unidad?.textContent || '';
  const pill = [...(unidad?.firstElementChild?.querySelectorAll('span') || [])]
    .filter(x => x.style.borderRadius === 'var(--r-full)' && x.getClientRects().length).at(-1);
  const textoEstado = pill?.textContent.trim() || '';
  const condicionDistinta = /^(sin\s+señal|sin\s+umbral\s+configurado|error|cargando)$/i
    .test(textoEstado.replace(/\s+/g, ' '));
  const mensajeAusencia = condicionDistinta ? ''
    : mensajeAusenciaEquivalente(textoEstado) ? textoEstado : '';
  const captura = FECHA ? new Date(FECHA) : null;
  const fechaTexto = texto.split(/último dato/i)[1] || '';
  const hoy = new Date();
  const mismoDia = captura && captura.getFullYear() === hoy.getFullYear()
    && captura.getMonth() === hoy.getMonth() && captura.getDate() === hoy.getDate();
  const fecha = !FECHA ? !/último dato/i.test(texto)
    : (Number.isFinite(captura?.getTime()) && /último dato/i.test(texto)
    && fechaTexto.includes(String(captura.getMinutes()).padStart(2, '0'))
    && (mismoDia || fechaTexto.includes(String(captura.getDate()).padStart(2, '0'))));
  const sinValores = sinValoresFabricados(texto);
  const alerta = [...cuerpo.querySelectorAll('[role="alert"]')].map(x => x.textContent.trim()).find(Boolean) || '';
  return { cargando: indicadorCargaActivo(cuerpo.textContent), error: textoSeguro(alerta),
    unidades_visibles: secciones.length, unidad_objetivo_presente: Boolean(unidad),
    gris: Boolean(pill && pill.style.color === 'var(--text-muted)'),
    texto_estado: textoSeguro(textoEstado), mensaje_ausencia: textoSeguro(mensajeAusencia),
    fecha_historica: fecha, fecha_visible: /último dato/i.test(texto), fecha_observada: textoSeguro(fechaTexto.trim()),
    sin_valores_fabricados: sinValores,
    desde_cache: cuerpo.textContent.includes('desde caché') };
}

function registrarCarga(carga, ui, etapa) {
  const sesion5xx = sesionCon5xx(acta.peticiones);
  if (sesion5xx) {
    acta.estado = 'NO_CONCLUYENTE';
    acta.criterio = 'SESION_5XX';
    acta.motivo = `Sesión UI HTTP ${sesion5xx.http} en ${sesion5xx.ruta}; dashboard sin evaluación fiable`;
    return { estado: 'NO_CONCLUYENTE', criterio: acta.criterio };
  }
  const decision = clasificarCarga({ ...carga, ui });
  acta.criterio = `${etapa}:${decision.criterio}`;
  acta.http = carga.http;
  acta.error_red = carga.errorRed || (carga.http == null ? ui.error || null : null);
  if (decision.estado !== 'EVALUAR_UI') {
    acta.estado = decision.estado;
    acta.motivo = `${acta.criterio}; HTTP ${carga.http ?? 'sin respuesta'}; ${carga.vencio ? 'espera agotada; ' : ''}UI cargando ${ui.cargando}; error ${ui.error}`;
  }
  return decision;
}

function esperarVistaEstable(carga) {
  if (carga.http !== 200) return cy.wrap(carga, { log: false });
  const limite = ensayo && e('ENSAYO_TIMEOUT_CORTO') === 'SI' ? 2000 : 90000;
  return cy.window().then({ timeout: limite + 5000 }, win =>
    esperarRenderEstable(win, { limiteMs: limite }).then(renderVencio => ({ ...carga, renderVencio })));
}

(autorizado && ['V1', 'V2'].includes(FASE) ? describe : describe.skip)(`[TC-M03-184] UI ${FASE}`, () => {
  beforeEach(() => {
    cy.on('fail', error => {
      if (!['SESION_5XX', 'PETICIONES_API_SIN_RESPUESTA'].includes(acta.criterio)) {
        acta.estado = 'ERROR_QA';
        acta.criterio = 'FALLO_CYPRESS';
        acta.motivo = textoSeguro(error.message);
      }
      throw error;
    });
    interceptar();
  });
  afterEach(() => {
    if (cookieRotada && COOKIE_FILE) cy.task('guardarCookieRotada', { ruta: COOKIE_FILE, cookie: cookieActual }, { log: false });
    const ahora = new Date();
    for (const registro of peticionesSinRespuesta(acta.peticiones)) {
      registro.fin_observacion = ahora.toISOString();
      registro.duracion_observada_ms = ahora.getTime() - Date.parse(registro.inicio);
    }
    acta.pendiente_al_terminar = peticionesSinRespuesta(acta.peticiones).length > 0;
    acta.observaciones_documentales = [['panel global', acta.ui_inicial], ['vista filtrada', acta.ui_objetivo]]
      .map(([vista, ui]) => observacionDocumental(acta.fase, vista, ui?.mensaje_ausencia))
      .filter(Boolean);
    const sesion5xx = sesionCon5xx(acta.peticiones);
    if (sesion5xx) {
      acta.estado = 'NO_CONCLUYENTE';
      acta.criterio = 'SESION_5XX';
      acta.motivo = `Sesión UI HTTP ${sesion5xx.http} en ${sesion5xx.ruta}; vista sin evaluación fiable`;
    }
    const escenarioNormal = ['APROBADO', 'RECHAZADO'].includes(acta.estado);
    if (escenarioNormal && acta.pendiente_al_terminar) {
      acta.estado = 'ERROR_QA';
      acta.criterio = 'PETICIONES_API_SIN_RESPUESTA';
      acta.motivo = 'El escenario termino con peticiones API sin respuesta';
    }
    cy.writeFile(`${CARPETA}/UI-184-${FASE}.json`, acta);
    cy.screenshot(`UI-184-${FASE}`, { capture: 'fullPage', overwrite: true });
    if (escenarioNormal) cy.then(() =>
      expect(acta.pendiente_al_terminar, 'ninguna peticion API sin respuesta').to.eq(false));
  });
  it(`[TC-M03-184][ASSERT][${acta.id}] unidad GRIS, mensaje de ausencia y fecha histórica si existe`, () => {
    iniciarSesion().then(() => {
      if (acta.criterio === 'SESION_5XX') return;
      esperas.global = crearEspera(ensayo && e('ENSAYO_TIMEOUT_CORTO') === 'SI' ? 2000 : 90000);
      navegarSpa('/telemetria/monitoreo');
      // Un único intento de apagar el polling; su ausencia no convierte el oráculo en RECHAZADO.
      cy.get('body').then($body => {
        const incidencia = intentarDesactivarAuto($body[0]);
        if (incidencia) acta.incidencias_tecnicas.push(incidencia);
      });
      cy.then(() => cy.wrap(esperas.global.promise, { timeout: 95000 })).then(esperarVistaEstable).then(carga => {
      cy.get('body').then($body => {
        acta.ui_inicial = observar($body);
        if (!acta.incidencias_tecnicas.length
          && ![...$body[0].querySelectorAll('button')].some(x => x.textContent.trim() === 'Auto OFF'))
          acta.incidencias_tecnicas.push('CONTROL_AUTO_ON_NO_DESACTIVADO');
        if (registrarCarga(carga, acta.ui_inicial, 'INICIAL').estado !== 'EVALUAR_UI') return;
        const global = evaluarOraculoUi(acta.ui_inicial, acta.ui_inicial);
        if (global.estado === 'RECHAZADO') {
          acta.estado = global.estado;
          acta.criterio = global.criterio;
          acta.motivo = `HTTP global 200; ${global.criterio}; panel global ${JSON.stringify(acta.ui_inicial)}`;
        }
        esperas.objetivo = crearEspera(40000);
        cy.get('#monitoreo-area').clear().type(String(ID), { delay: 0 });
        cy.then(() => cy.wrap(esperas.objetivo.promise, { timeout: 45000 })).then(esperarVistaEstable).then(filtrada => {
          cy.get('body').then($filtrado => {
            acta.ui_objetivo = observar($filtrado, true);
            if (registrarCarga(filtrada, acta.ui_objetivo, 'FILTRADA').estado !== 'EVALUAR_UI') {
              return;
            }
            const u = acta.ui_objetivo;
            const decision = evaluarOraculoUi(acta.ui_inicial, u);
            acta.estado = decision.estado;
            acta.criterio = decision.criterio;
            acta.motivo = `HTTP 200; ${decision.criterio === 'UNIDAD_DESAPARECE_DEL_PANEL' ? 'la unidad desaparece del panel; ' : ''}`
              + `global ${JSON.stringify(acta.ui_inicial)}; filtrada ${JSON.stringify(u)}`;
          });
        });
      });
      });
    });
  });
});
