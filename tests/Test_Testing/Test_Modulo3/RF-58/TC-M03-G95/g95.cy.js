const { elegirUnidad } = require('./lib/g95_unidad.cjs');
const { LIMITE_LECTURAS_DASHBOARD } = require('./lib/g95_presupuesto.cjs');
const env = k => Cypress.env(k);
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const FRONT = String(env('FRONT_BASE') || '').replace(/\/+$/, '');
const ARTEFACTOS = String(env('ARTIFACTS_DIR') || '');
const local = env('ENSAYO_LOCAL') === 'SI';
const acta = {
  caso: 'TC-M03-186', id: 'UI-186-01/UI-186-02', mecanismo: 'segundo_login_real',
  captura: false, dashboard_inicial_200: false, auto_on: false, periodica_200: false,
  auto_motivo: null, filtro_fijado: false, filtro_id: null, segundo_login_200: false,
  dashboard_rechazado_401: false, redirigido_login: false, aviso_sesion_terminada: false,
  sin_200_vencida: false, auto_detenido: false, estado_visual_conservado: false,
  aviso_texto: null, filtro_conservado: false, auto_conservado: false,
  retorno_automatico: false, ruta_aterrizaje: null, navegacion_manual: false,
  reingreso_200: false, monitoreo_cargado: false, error_interno_visible: false,
  recarga_200_posterior: false, infra_5xx: false,
  error_qa: null, error_selector: null, bloqueo_datos: null, e7_riesgo: false, e7_motivo: null,
  lecturas_dashboard: 0, peticiones: [],
};
let cierre = false;
let totalDashboard = 0;
let respuestas200Vencida = 0;
let filtroElegido = null;
let tokenAnterior = null;
let inicioPeriodo = 0;
let respuestasPeriodicas = 0;
let inicioReingreso = 0;
let selectorActual = null;

function buscar(etapa, selector) {
  return cy.then(() => { selectorActual = { etapa, selector }; }).get(selector);
}
Cypress.on('fail', error => {
  if (selectorActual && /Expected to find (?:element|content)|expected .* to (?:exist|be\.visible)/i.test(error.message)) {
    acta.error_selector = selectorActual;
    acta.error_qa = `ERROR_SELECTOR:${selectorActual.etapa}:${selectorActual.selector}`;
  }
  throw error;
});

function ruta(r) { return `${FRONT}${r}`; }
function registrar(req, res, inicioSolicitud) {
  const pathname = new URL(req.url).pathname;
  acta.peticiones.push({ metodo: req.method, ruta: pathname, http: res.statusCode,
    fuera_sandbox: true, posterior_reingreso: Boolean(inicioReingreso && inicioSolicitud >= inicioReingreso) });
  if (res.statusCode >= 500) acta.infra_5xx = true;
  if (pathname.includes('/iot/monitoreo/dashboard')) {
    totalDashboard++;
    acta.lecturas_dashboard = totalDashboard;
    if (totalDashboard > LIMITE_LECTURAS_DASHBOARD) acta.error_qa = 'PRESUPUESTO_DASHBOARD_SUPERADO';
    if (inicioPeriodo && res.statusCode === 200
      && new URL(req.url).searchParams.get('id_infraestructura') === String(filtroElegido))
      respuestasPeriodicas++;
    if (cierre && res.statusCode === 200) respuestas200Vencida++;
  }
}
function ingresar() {
  buscar('login_correo', 'input[type="email"]').type(env('PROD_EMAIL'), { log: false });
  buscar('login_clave', 'input[type="password"]').type(env('PROD_PASSWORD'), { log: false });
  buscar('login_enviar', 'button[type="submit"]').click();
  return cy.wait('@login', { timeout: 30000 });
}

function seleccionarArea(id) {
  cy.then(() => { selectorActual = { etapa: 'etiqueta_area', selector: 'label:Área' }; });
  cy.contains('label', /^Área$/).invoke('attr', 'for').then(idCampo => {
    const campo = `input[role="combobox"][id="${idCampo}"]`;
    buscar('combobox_area', campo).clear().type(String(id));
    // idDeCatalogo admite el ID aunque la lista de useAreas todavía esté cargando.
    buscar('valor_area', campo).invoke('val').then(valor => {
      acta.filtro_fijado = String(valor) === String(id) || String(valor).endsWith(`(#${id})`);
    });
  });
}

describe('TC-M03-G95 — TC-M03-186', () => {
  before(() => {
    const remotoCorrecto = API === 'https://api.inmero.co/api-sgpmp-test'
      && FRONT === 'https://api.inmero.co/sigab-test';
    const localCorrecto = /^http:\/\/127\.0\.0\.1:\d+\/api-sgpmp-test$/.test(API)
      && /^http:\/\/127\.0\.0\.1:\d+\/sigab-test$/.test(FRONT);
    if (env('AUTORIZADO_RUN') !== 'SI' || !env('RUN_ID') || !ARTEFACTOS
      || !(local ? localCorrecto : remotoCorrecto)) throw Error('BLOQUEO_G95_CONFIG');
    cy.intercept({ url: `${API}/**` }, req => {
      const rutaApi = new URL(req.url).pathname;
      if (req.method === 'POST' && rutaApi.endsWith('/sesiones/')) req.alias = 'login';
      if (req.method === 'GET' && rutaApi.endsWith('/iot/monitoreo/dashboard')) {
        const porPagina = new URL(req.url).searchParams.get('por_pagina');
        req.alias = porPagina === '50' ? 'dashboardVista' : porPagina === '1' ? 'dashboardAreas' : 'dashboard';
      }
      if (req.method === 'POST' && rutaApi.endsWith('/sesiones/refresh')) req.alias = 'refresh';
      const inicioSolicitud = Date.now();
      req.continue(res => registrar(req, res, inicioSolicitud));
    });
  });

  afterEach(() => {
    if (acta.peticiones.length > 60) acta.error_qa = 'PRESUPUESTO_UI_API_SUPERADO';
    if (totalDashboard > LIMITE_LECTURAS_DASHBOARD) acta.error_qa = 'PRESUPUESTO_DASHBOARD_SUPERADO';
    if (cierre) acta.sin_200_vencida = respuestas200Vencida === 0;
    acta.captura = true; // acta escrita ANTES de la captura; el runner exige PNG real.
    cy.writeFile(`${ARTEFACTOS}/UI-186-01.json`, acta, { log: false });
    cy.screenshot('UI-186-01-pagina-completa', { capture: 'fullPage',
      blackout: ['section', 'aside', 'nav', 'header', 'input', '[role="img"]'] });
  });

  it('[TC-M03-186][ASSERT][UI-186-01][UI-186-02] expiración forzada por sesión única', () => {
    cy.visit(ruta('/login'));
    ingresar().then(i => {
      if (i.response?.statusCode !== 200) {
        acta.infra_5xx = i.response?.statusCode >= 500;
        return;
      }
      cy.visit(ruta('/telemetria/monitoreo'));
      cy.wait('@dashboardVista', { timeout: 30000 }).then(d => {
        const body = d.response?.body ?? {};
        acta.dashboard_inicial_200 = d.response?.statusCode === 200;
        if (!acta.dashboard_inicial_200) return;
        tokenAnterior = String(d.request.headers.authorization ?? d.request.headers.Authorization ?? '').replace(/^Bearer /i, '');
        const eleccion = elegirUnidad(body);
        filtroElegido = eleccion.id;
        acta.e7_riesgo = eleccion.e7_riesgo;
        acta.e7_motivo = eleccion.motivo;
        acta.bloqueo_datos = eleccion.bloqueo_datos;
        if (filtroElegido == null && !acta.bloqueo_datos) acta.auto_motivo = eleccion.motivo;
        if (filtroElegido != null) {
          acta.filtro_id = filtroElegido;
          seleccionarArea(filtroElegido);
          cy.wait('@dashboardVista', { timeout: 30000 }).then(f => {
            if (f.response?.statusCode >= 500) acta.infra_5xx = true;
            if (f.response?.statusCode !== 200) return;
            acta.filtro_fijado = acta.filtro_fijado
              && new URL(f.request.url).searchParams.get('id_infraestructura') === String(filtroElegido);
            cy.wait(local ? 100 : 700, { log: false });
            cy.get('body').then($body => {
              const boton = [...$body.find('button')].find(b => /^Auto (ON|OFF)$/.test((b.textContent ?? '').trim()));
              if (!boton) { acta.error_selector = { etapa: 'boton_auto', selector: 'button:Auto ON|OFF' }; acta.error_qa = 'ERROR_SELECTOR:boton_auto:button:Auto ON|OFF'; return; }
              if (/Auto OFF/.test(boton.textContent ?? '')) cy.wrap(boton).click();
            });
            buscar('auto_on', 'button').contains(/^Auto ON$/).then(() => {
              acta.auto_on = true;
              if (!acta.auto_on) acta.auto_motivo = 'AUTO_NO_SE_PUDO_ACTIVAR';
              else inicioPeriodo = Date.now();
            });
            cy.then(() => {
              if (!acta.auto_on) return;
              cy.wait('@dashboardVista', { timeout: local ? 6000 : 35000 }).then(periodica => {
                acta.periodica_200 = periodica.response?.statusCode === 200
                  && new URL(periodica.request.url).searchParams.get('id_infraestructura') === String(filtroElegido)
                  && respuestasPeriodicas > 0;
                inicioPeriodo = 0;
                if (!acta.periodica_200) acta.auto_motivo = 'SIN_PETICION_PERIODICA_200';
              });
            });
            cy.then(() => {
              if (!acta.auto_on || !acta.periodica_200 || !acta.filtro_fijado) return;
            cy.getCookie('refresh_token').then(cookie => {
              if (!tokenAnterior || !cookie?.value) { acta.error_qa = 'TOKEN_O_COOKIE_NO_ACREDITADOS'; return; }
              cy.task('reemplazarSesion', { tokenAnterior, cookieAnterior: cookie.value }, { log: false }).then(x => {
                acta.segundo_login_200 = x.http === 200;
                if (x.http >= 500) acta.infra_5xx = true;
                if (!acta.segundo_login_200) return;
                cierre = true;
                buscar('refresco_manual', 'button[aria-label="Refrescar ahora"]').click();
                cy.wait('@dashboardVista', { timeout: 45000 }).then(v => {
                  acta.dashboard_rechazado_401 = v.response?.statusCode === 401;
                  if (v.response?.statusCode >= 500) acta.infra_5xx = true;
                  if (!acta.dashboard_rechazado_401) return;
                  cy.wait(local ? 500 : 5000, { log: false });
                  cy.location('pathname').then(p => {
                    acta.redirigido_login = p.includes('/login');
                    if (!acta.redirigido_login) return;
                    cy.get('body').then($body => {
                      const texto = $body.find('.auth-alert:visible').first().text();
                      acta.aviso_texto = texto;
                      const aviso = acta.aviso_texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
                      acta.aviso_sesion_terminada = /(?:\bsesion\b.{0,100}\b(?:expir\w*|venc\w*|cerr\w*|finaliz\w*)\b|\b(?:expir\w*|venc\w*|cerr\w*|finaliz\w*)\b.{0,100}\bsesion\b|\b(?:inicia\w*|ingresa\w*|vuelve\w*|volver)\b.{0,60}\b(?:sesion|de nuevo|nuevamente|otra vez)\b)/i.test(aviso);
                    });
                    const antes = totalDashboard;
                    // Es el único intervalo fijo: supera el polling de 30 s para comprobar que se detuvo.
                    cy.wait(local ? 3500 : 32000, { log: false }).then(() => {
                      acta.auto_detenido = totalDashboard === antes;
                      acta.sin_200_vencida = respuestas200Vencida === 0;
                    });
                    inicioReingreso = Date.now();
                    ingresar().then(nuevo => {
                      acta.reingreso_200 = nuevo.response?.statusCode === 200;
                      if (nuevo.response?.statusCode >= 500) acta.infra_5xx = true;
                      if (!acta.reingreso_200) return;
                      cierre = false;
                      cy.wait(local ? 500 : 5000, { log: false });
                      cy.location('pathname').then(p => {
                        acta.ruta_aterrizaje = p.replace(/^\/sigab-test/, '').replace(/\/$/, '') || '/';
                        acta.retorno_automatico = acta.ruta_aterrizaje === '/telemetria/monitoreo';
                        if (!acta.retorno_automatico) {
                          acta.navegacion_manual = true;
                          cy.visit(ruta('/telemetria/monitoreo'));
                        }
                        cy.location('pathname').then(actual => {
                          acta.monitoreo_cargado = actual.replace(/\/$/, '').endsWith('/telemetria/monitoreo');
                        });
                        cy.wait('@dashboardVista', { timeout: 30000 }).then(recarga => {
                        acta.recarga_200_posterior = recarga.response?.statusCode === 200
                          && acta.peticiones.some(x => x.ruta.endsWith('/iot/monitoreo/dashboard')
                            && x.http === 200 && x.posterior_reingreso);
                        cy.get('body').then($body => {
                            const textoVisible = [...$body.find('*:visible')]
                              .filter(el => el.children.length === 0).map(el => el.textContent ?? '').join(' ');
                            acta.error_interno_visible = /error interno|internal server error|algo salió mal|no se pudo cargar/i
                              .test(textoVisible);
                            const valor = $body.find('label').filter((_, el) => (el.textContent ?? '').trim() === 'Área').first().next().find('[role="combobox"]').val();
                            const autoRestaurado = [...$body.find('button')]
                              .some(b => /Auto ON/.test(b.textContent ?? ''));
                            acta.filtro_conservado = String(valor) === String(filtroElegido) || String(valor).endsWith(`(#${filtroElegido})`);
                            acta.auto_conservado = autoRestaurado;
                            acta.estado_visual_conservado = acta.filtro_conservado && acta.auto_conservado;
                        });
                        });
                      });
                    });
                  });
                });
              });
            });
            });
          });
        }
      });
    });
  });
});
