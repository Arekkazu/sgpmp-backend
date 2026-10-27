// TC-M03-184: UI-184-01 y UI-184-02; solicitudes reales del Productor dentro del RUN.
const { mensajeAusenciaEquivalente, observacionDocumental, clasificarCarga, evaluarOraculoUi, intentarDesactivarAuto } = require('./lib/g93_ui.cjs');
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
const ensayo = e('ENSAYO_G93_SPEC_REAL') === 'SI' && /^ENSAYO-G93-\d{8}-\d{6}-[a-z0-9]+$/.test(RUN || '')
  && /^http:\/\/127\.0\.0\.1:\d+$/.test(API) && /^http:\/\/127\.0\.0\.1:\d+$/.test(FRONT)
  && e('ENSAYO_CONTEXTO_TEMPORAL') === 'SI';
const autorizado = e('AUTORIZADO_RUN') === 'SI' && Number.isSafeInteger(ID) && ID > 0
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
const urlFront = ruta => `${FRONT}${ruta}`;
const rutaApi = url => {
  const base = new URL(API);
  const u = new URL(url);
  return u.pathname.slice(base.pathname.replace(/\/$/, '').length) + u.search;
};
const textoSeguro = valor => {
  let texto = String(valor || '');
  for (const secreto of [e('SANDBOX_SECRET'), e('REFRESH_COOKIE'), cookieActual].filter(Boolean))
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
    if (!['GET', 'OPTIONS'].includes(req.method) && ruta !== '/sesiones/refresh') {
      acta.estado = 'ERROR_QA'; acta.motivo = `ESCRITURA_UI_INESPERADA ${req.method} ${ruta.split('?')[0]}`;
      throw new Error(acta.motivo);
    }
    req.headers['X-Test-Run-Id'] = RUN;
    req.headers['X-Sandbox-Secret'] = e('SANDBOX_SECRET');
    if (ruta === '/sesiones/refresh') {
      req.headers.cookie = `refresh_token=${cookieActual}`;
      req.alias = 'refresh';
    }
    const dashboard = req.method === 'GET' && ruta.split('?')[0] === '/iot/monitoreo/dashboard';
    const filtro = dashboard ? new URL(req.url).searchParams.get('id_infraestructura') : null;
    if (dashboard) req.alias = filtro ? 'dashboardFiltrado' : 'dashboardGlobal';
    if (filtro === String(ID)) req.alias = 'dashboardObjetivo';
    const tipo = req.alias === 'dashboardGlobal' ? 'global'
      : req.alias === 'dashboardObjetivo' ? 'objetivo' : null;
    // Solo se conservan la ruta relativa y el ID; nunca la URL completa ni cabeceras.
    const rutaSegura = dashboard ? `/iot/monitoreo/dashboard${filtro ? `?id_infraestructura=${encodeURIComponent(filtro)}` : ''}` : ruta.split('?')[0];
    const registro = { metodo: req.method, ruta: rutaSegura, alias: req.alias ?? null,
      inicio: new Date().toISOString(), fin: null, duracion_ms: null, http: null,
      eco_run: false, error_red: null };
    acta.peticiones.push(registro);
    const inicio = Date.now();
    req.continue(res => {
      // El alias no es estable aquí; conservar el valor capturado al registrar la petición.
      registro.alias_en_callback = registro.alias;
      registro.fin = new Date().toISOString();
      registro.duracion_ms = Date.now() - inicio;
      registro.http = res?.statusCode ?? null;
      registro.eco_run = res?.headers?.['x-test-run-id'] === RUN;
      registro.error_red = res?.error ? textoSeguro(res.error.message || res.error) : null;
      if (registro.alias === 'refresh' && res?.statusCode === 200) {
        const cabeceras = Object.entries(res.headers || {})
          .find(([nombre]) => nombre.toLowerCase() === 'set-cookie')?.[1];
        const valores = Array.isArray(cabeceras) ? cabeceras : [cabeceras];
        const nueva = valores.map(x => /(?:^|[,\s])refresh_token=([^;\s,]+)/.exec(String(x || ''))?.[1]).find(Boolean);
        if (!nueva) {
          acta.estado = 'ERROR_QA'; acta.criterio = 'COOKIE_ROTADA_AUSENTE';
          throw new Error('Refresco 200 sin cookie rotada');
        }
        cookieActual = nueva;
        cookieRotada = true;
      }
      if (registro.alias === 'dashboardGlobal') {
        registro.espera_disponible = Boolean(esperas.global);
        registro.espera_cerrada_antes = Boolean(esperas.global?.cerrada);
      }
      if (tipo === 'global') esperas.global?.terminar({
        http: registro.http, eco: registro.eco_run, errorRed: registro.error_red, vencio: false });
      if (tipo === 'objetivo') esperas.objetivo?.terminar({
        http: registro.http, eco: registro.eco_run, errorRed: registro.error_red, vencio: false });
    });
  });
}

function observar($body, filtrada = false) {
  const cuerpo = $body[0];
  const secciones = [...cuerpo.querySelectorAll('section')];
  const normalizar = x => String(x || '').replace(/\s+/g, ' ').trim();
  const nombreObjetivo = normalizar(NOMBRE);
  const unidad = nombreObjetivo && secciones.find(x => normalizar(x.firstElementChild?.firstElementChild?.children?.[1]?.firstElementChild?.textContent)
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
  const fecha = !FECHA || (Number.isFinite(captura?.getTime()) && /último dato/i.test(texto)
    && fechaTexto.includes(String(captura.getMinutes()).padStart(2, '0'))
    && (mismoDia || fechaTexto.includes(String(captura.getDate()).padStart(2, '0'))));
  const tarjetas = [...(unidad?.querySelectorAll('button.ds-option') || [])];
  const sinValores = FASE === 'V1' ? tarjetas.length === 0
    : (!filtrada || tarjetas.length > 0) && tarjetas.every(x => x.textContent.includes('desactualizado'));
  const alerta = [...cuerpo.querySelectorAll('[role="alert"]')].map(x => x.textContent.trim()).find(Boolean) || '';
  return { cargando: cuerpo.textContent.includes('Cargando…'), error: textoSeguro(alerta),
    unidades_visibles: secciones.length, unidad_objetivo_presente: Boolean(unidad),
    gris: Boolean(pill && pill.style.color === 'var(--text-muted)'),
    texto_estado: textoSeguro(textoEstado), mensaje_ausencia: textoSeguro(mensajeAusencia),
    fecha_historica: fecha, fecha_visible: /último dato/i.test(texto), fecha_observada: textoSeguro(fechaTexto.trim()),
    sin_valores_fabricados: sinValores,
    desde_cache: cuerpo.textContent.includes('desde caché') };
}

function registrarCarga(carga, ui, etapa) {
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

(autorizado && ['V1', 'V2'].includes(FASE) ? describe : describe.skip)(`[TC-M03-184] UI ${FASE}`, () => {
  beforeEach(() => {
    cy.on('fail', error => {
      acta.estado = 'ERROR_QA';
      acta.criterio = 'FALLO_CYPRESS';
      acta.motivo = textoSeguro(error.message);
      throw error;
    });
    interceptar();
  });
  afterEach(() => {
    if (cookieRotada && COOKIE_FILE) cy.task('guardarCookieRotada', { ruta: COOKIE_FILE, cookie: cookieActual }, { log: false });
    const ahora = new Date();
    for (const registro of acta.peticiones.filter(x => !x.fin)) {
      registro.fin_observacion = ahora.toISOString();
      registro.duracion_observada_ms = ahora.getTime() - Date.parse(registro.inicio);
    }
    acta.pendiente_al_terminar = acta.peticiones.some(x => !x.fin);
    acta.observaciones_documentales = [['panel global', acta.ui_inicial], ['vista filtrada', acta.ui_objetivo]]
      .map(([vista, ui]) => observacionDocumental(acta.fase, vista, ui?.mensaje_ausencia))
      .filter(Boolean);
    cy.writeFile(`${CARPETA}/UI-184-${FASE}.json`, acta);
    cy.screenshot(`UI-184-${FASE}`, { capture: 'fullPage', overwrite: true });
  });
  it(`[TC-M03-184][ASSERT][${acta.id}] unidad GRIS, mensaje de ausencia y fecha histórica si existe`, () => {
    esperas.global = crearEspera(ensayo && e('ENSAYO_TIMEOUT_CORTO') === 'SI' ? 2000 : 60000);
    cy.visit(urlFront('/telemetria/monitoreo'), { timeout: 65000 });
    cy.wait('@refresh', { timeout: 30000 }).then(({ response }) => {
      if (response?.statusCode !== 200 || response.headers['x-test-run-id'] !== RUN) {
        acta.estado = 'ERROR_QA'; acta.criterio = 'SESION_O_ECO_RUN';
        acta.motivo = 'Refresco de sesión UI no acreditado';
        throw new Error(acta.motivo);
      }
    });
    // Un único intento de apagar el polling; su ausencia no convierte el oráculo en RECHAZADO.
    cy.get('body').then($body => {
      const incidencia = intentarDesactivarAuto($body[0]);
      if (incidencia) acta.incidencias_tecnicas.push(incidencia);
    });
    cy.then(() => cy.wrap(esperas.global.promise, { timeout: 65000 })).then(carga => {
      cy.window().then(win => new Promise(resolve => win.requestAnimationFrame(() => win.requestAnimationFrame(resolve))));
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
        cy.get('input[type="number"]').type(String(ID), { delay: 0 });
        cy.then(() => cy.wrap(esperas.objetivo.promise, { timeout: 45000 })).then(filtrada => {
          cy.window().then(win => new Promise(resolve => win.requestAnimationFrame(() => win.requestAnimationFrame(resolve))));
          cy.get('body').then($filtrado => {
            acta.ui_objetivo = observar($filtrado, true);
            if (registrarCarga(filtrada, acta.ui_objetivo, 'FILTRADA').estado !== 'EVALUAR_UI') {
              if (global.estado === 'RECHAZADO') {
                acta.estado = global.estado;
                acta.criterio = global.criterio;
                acta.motivo = `HTTP global 200; ${global.criterio}; vista filtrada: ${acta.motivo}`;
              }
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
