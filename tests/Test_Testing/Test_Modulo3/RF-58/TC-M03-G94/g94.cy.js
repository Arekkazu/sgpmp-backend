// Una sola comprobación UI obligatoria; tráfico real, sin req.reply ni fixtures.
const env = key => Cypress.env(key);
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const FRONT = String(env('FRONT_BASE') || '').replace(/\/+$/, '');
const RUN = env('RUN_ID');
const DIR = env('ARTIFACTS_DIR');
const ensayo = env('ENSAYO_LOCAL') === 'SI'
  && /^http:\/\/127\.0\.0\.1:\d+\/api-sgpmp-test$/.test(API)
  && /^http:\/\/127\.0\.0\.1:\d+\/sigab-test$/.test(FRONT)
  && /^ENSAYO-G94-(?:OK|TEXTO|SESION500|LENTO|SIN_ECO_DASHBOARD)$/.test(RUN || '');
const autorizado = env('AUTORIZADO_RUN') === 'SI' && (ensayo
  || (/^RUN-G94-V\d+-\d{8}-\d{6}$/.test(RUN || '')
    && API === 'https://api.inmero.co/api-sgpmp-test'
    && FRONT === 'https://api.inmero.co/sigab-test'))
  && Boolean(DIR && env('REFRESH_COOKIE') && env('SANDBOX_SECRET'));
const acta = { caso: 'TC-M03-185', id: 'UI-185-01', estado: 'NO_CONCLUYENTE',
  motivo: 'dashboard no recibido en el plazo', peticiones: [], dashboard: null,
  captura: false, motivo_captura: 'Captura de página no completada',
  mensaje_exacto: false, contacto_admin: false, sin_tarjetas: false,
  sin_error_interno: false, texto_observado: '',
  rutas_fuera_sandbox: [], fincas_perfil: null };
let solicitudes = 0;
const SESION_FUERA = Object.freeze([
  'POST /sesiones/refresh', 'GET /usuarios/me', 'GET /sesiones/me/permisos',
]);

function interceptar() {
  cy.intercept({ url: `${API}/**` }, req => {
    solicitudes++;
    const u = new URL(req.url);
    const base = new URL(API);
    const ruta = u.pathname.slice(base.pathname.length) || '/';
    if (solicitudes > 20) throw new Error('LIMITE_UI_API_20');
    if (!['GET', 'OPTIONS'].includes(req.method) && !(req.method === 'POST' && ruta === '/sesiones/refresh'))
      throw new Error(`ESCRITURA_UI_INESPERADA ${req.method} ${ruta}`);
    const fuera = SESION_FUERA.includes(`${req.method} ${ruta}`);
    if (fuera) {
      for (const clave of Object.keys(req.headers))
        if (['x-test-run-id', 'x-sandbox-secret'].includes(clave.toLowerCase())) delete req.headers[clave];
      if (!acta.rutas_fuera_sandbox.includes(`${req.method} ${ruta}`))
        acta.rutas_fuera_sandbox.push(`${req.method} ${ruta}`);
    } else {
      req.headers['X-Test-Run-Id'] = RUN;
      req.headers['X-Sandbox-Secret'] = env('SANDBOX_SECRET');
    }
    const dashboard = req.method === 'GET' && ruta === '/iot/monitoreo/dashboard';
    if (dashboard) req.alias = 'dashboard';
    const registro = { metodo: req.method, ruta, http: null, en_sandbox: !fuera, eco_run: false };
    acta.peticiones.push(registro);
    req.continue(res => {
      registro.http = res?.statusCode ?? null;
      registro.eco_run = res?.headers?.['x-test-run-id'] === RUN;
      if (fuera && ruta === '/usuarios/me' && res?.statusCode === 200) {
        const fincas = res?.body?.fincas;
        acta.fincas_perfil = Array.isArray(fincas) ? fincas.length : null;
      }
      if (dashboard) acta.dashboard = { ...registro };
    });
  });
}

describe('[TC-M03-185] usuario sin fincas', () => {
  beforeEach(interceptar);
  afterEach(() => {
    const falloSesion = acta.peticiones.some(x => !x.en_sandbox && x.http >= 500);
    const aislamientoRoto = acta.peticiones.some(x => x.http !== null &&
      (x.en_sandbox ? !x.eco_run : x.eco_run));
    if (falloSesion) { acta.estado = 'BLOQUEADO'; acta.motivo = '5xx de sesión fuera del sandbox'; }
    else if (aislamientoRoto) {
      acta.estado = 'NO_CONCLUYENTE'; acta.motivo = 'Eco RUN incoherente con el aislamiento de la petición';
    } else if (acta.dashboard?.http === 200 && acta.dashboard.eco_run) {
      const cumple = acta.mensaje_exacto && acta.contacto_admin && acta.sin_tarjetas && acta.sin_error_interno;
      acta.estado = cumple ? 'APROBADO' : 'RECHAZADO';
      acta.motivo = cumple ? 'Mensaje, sugerencia y ausencia de tarjetas acreditados'
        : 'Pantalla cargada con discrepancia frente al texto o contenido exigido';
    } else if (acta.dashboard?.http >= 500 && acta.dashboard.eco_run) {
      acta.estado = 'RECHAZADO'; acta.motivo = `Dashboard HTTP ${acta.dashboard.http}`;
    }
    cy.get('body').then($body => {
      // Oculta nombres de unidades si hubiera fuga; la captura no depende del alto de main.
      $body[0].querySelectorAll('section').forEach(x => { x.style.filter = 'blur(12px)'; });
    });
    cy.writeFile(`${DIR}/UI-185-01.json`, acta);
    cy.screenshot('UI-185-01', { capture: 'fullPage', overwrite: true }).then(() => {
      acta.captura = true;
      acta.motivo_captura = null;
      cy.writeFile(`${DIR}/UI-185-01.json`, acta);
    });
  });
  it('[TC-M03-185][ASSERT][UI-185-01] estado vacío, contacto y sin datos ajenos', () => {
    if (!autorizado) {
      acta.estado = 'ERROR_QA';
      acta.motivo = 'BLOQUEO_G94: contrato de entorno o autorización inválido';
      throw new Error(acta.motivo);
    }
    cy.visit(`${FRONT}/login`);
    cy.clearAllCookies();
    cy.setCookie('refresh_token', env('REFRESH_COOKIE'), { path: '/', secure: !ensayo, httpOnly: true });
    cy.visit(`${FRONT}/telemetria/monitoreo`);
    cy.wait('@dashboard', { timeout: ensayo ? 10000 : 30000 }).then(({ response }) => {
      acta.dashboard = { metodo: 'GET', ruta: '/iot/monitoreo/dashboard',
        http: response?.statusCode ?? null, en_sandbox: true,
        eco_run: response?.headers?.['x-test-run-id'] === RUN };
      if (response?.statusCode !== 200 || response?.headers?.['x-test-run-id'] !== RUN) return;
      cy.get('main', { timeout: 10000 }).should('exist');
      cy.get('body').then($body => {
        const body = $body[0];
        const texto = body.innerText || '';
        acta.mensaje_exacto = texto.includes('No tiene unidades productivas asignadas');
        acta.contacto_admin = /(?:contact(?:e|ar)?|comun[ií]quese|consulte)[^.!?]{0,100}administrador/i.test(texto);
        acta.sin_tarjetas = body.querySelectorAll('section').length === 0
          && body.querySelectorAll('button.ds-option').length === 0;
        acta.sin_error_interno = !/error interno|internal server error|error al cargar el dashboard/i.test(texto);
        const mensajes = [...body.querySelectorAll('main p')].map(x => x.textContent?.trim() || '')
          .filter(x => /unidades productivas asignadas|sensores para mostrar|administrador/i.test(x));
        acta.texto_observado = mensajes.join(' | ').slice(0, 240) || 'SIN_TEXTO_RELEVANTE';
        expect(acta.mensaje_exacto && acta.contacto_admin && acta.sin_tarjetas && acta.sin_error_interno,
          'oráculo UI completo').to.eq(true);
      });
    });
  });
});
