// TC-M03-185: sesión reutilizada y lecturas serializadas dentro del RUN.
const e = k => Cypress.env(k);
const API = String(e('API_BASE') || '').replace(/\/+$/, '');
const FRONT = String(e('FRONT_BASE') || '').replace(/\/+$/, '');
const RUN = e('RUN_ID');
const DIR = e('ARTIFACTS_DIR');
const ensayo = e('ENSAYO_LOCAL') === 'SI' && /^http:\/\/127\.0\.0\.1:\d+\/api-sgpmp-test$/.test(API)
  && /^http:\/\/127\.0\.0\.1:\d+\/sigab-test$/.test(FRONT)
  && /^ENSAYO-G94-(?:OK|TEXTO|AJENAS|SESION500|CARGA|LENTO)$/.test(RUN || '');
const autorizado = e('AUTORIZADO_RUN') === 'SI' && Boolean(DIR && e('PROD_LOGIN_TOKEN') && e('SANDBOX_SECRET'))
  && (ensayo || (/^RUN-G94-V\d+-\d{8}-\d{6}$/.test(RUN || '')
    && API === 'https://api.inmero.co/api-sgpmp-test'
    && FRONT === 'https://api.inmero.co/sigab-test'));
const acta = { caso: 'TC-M03-185', id: 'UI-185-01', estado: 'NO_CONCLUYENTE', motivo: 'Sin iniciar',
  criterio: null, peticiones: [], dashboard: null, captura: false, motivo_captura: 'Captura no completada',
  mensaje_exacto: false, contacto_admin: false, sin_tarjetas: false, sin_error_interno: false,
  texto_observado: '', fincas_perfil: null, canario_e7: 'SIN_SENSORES_OBSERVADOS',
  carga_sin_terminar: false, pendiente_al_terminar: false };
let solicitudes = 0;
let cola = Promise.resolve();
const rutaApi = url => new URL(url).pathname.slice(new URL(API).pathname.length).split('?')[0] || '/';
const ocultar = valor => String(valor || '').replace(/Bearer\s+\S+|refresh_token=\S+|[\w.+-]+@[\w.-]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/gi, '[RESERVADO]').slice(0, 240);
const navegarSpa = ruta => cy.window().then(win => {
  const base = new URL(FRONT).pathname.replace(/\/+$/, '');
  win.history.pushState({}, '', `${base}${ruta}`);
  win.dispatchEvent(new win.PopStateEvent('popstate'));
}).then(() => cy.location('pathname').should('eq', `${new URL(FRONT).pathname.replace(/\/+$/, '')}${ruta}`));

function interceptar() {
  cy.intercept({ url: `${API}/**` }, req => {
    if (++solicitudes > 20) throw new Error('LIMITE_UI_API_20');
    const ruta = rutaApi(req.url);
    if (!['GET', 'OPTIONS'].includes(req.method) && !(req.method === 'POST' && ['/sesiones/', '/sesiones/refresh'].includes(ruta)))
      throw new Error(`ESCRITURA_UI_INESPERADA ${req.method} ${ruta}`);
    const alias = { '/sesiones/': 'login', '/usuarios/me': 'usuarioSesion',
      '/sesiones/me/permisos': 'permisosSesion', '/iot/monitoreo/dashboard': 'dashboard' }[ruta];
    if (alias) req.alias = alias;
    const registro = { metodo: req.method, ruta, http: null, en_sandbox: true,
      cabecera_run_enviada: false, eco_run: false, inicio: new Date().toISOString(), fin: null };
    acta.peticiones.push(registro);
    if (ruta === '/sesiones/' || ruta === '/sesiones/refresh') {
      registro.http = ruta === '/sesiones/' ? 200 : 401;
      registro.eco_run = true;
      registro.fin = new Date().toISOString();
      req.reply({ statusCode: registro.http, headers: { 'x-test-run-id': RUN },
        body: ruta === '/sesiones/' ? { token: e('PROD_LOGIN_TOKEN') } : { error_code: 'SIN_SESION_UI' } });
      return;
    }
    let liberar;
    const turno = cola;
    cola = new Promise(resolve => { liberar = resolve; });
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN;
      req.headers['X-Sandbox-Secret'] = e('SANDBOX_SECRET');
      registro.cabecera_run_enviada = true;
      const reloj = setTimeout(() => { registro.error_red = 'RESPUESTA_API_AGOTADA'; liberar(); }, 90000);
      try {
        req.continue(res => {
          registro.http = res?.statusCode ?? null;
          registro.eco_run = res?.headers?.['x-test-run-id'] === RUN;
          registro.fin = new Date().toISOString();
          if (ruta === '/usuarios/me' && registro.http === 200)
            acta.fincas_perfil = Array.isArray(res.body?.fincas) ? res.body.fincas.length : null;
          if (ruta === '/iot/monitoreo/dashboard') {
            acta.dashboard = { http: registro.http, eco_run: registro.eco_run };
            acta.datos_ajenos = Boolean(res.body?.resumen_unidades?.length || res.body?.sensores?.length);
            if (res.body?.sensores?.length) acta.canario_e7 = 'SENSORES_DEVUELTOS';
          }
          clearTimeout(reloj); liberar();
        });
      } catch (error) { clearTimeout(reloj); liberar(); throw error; }
    });
  });
}

function esperarCarga(win) {
  const limite = ensayo && e('ENSAYO_TIMEOUT_CORTO') === 'SI' ? 2000 : 90000;
  return new Promise(resolve => {
    const inicio = Date.now(); let anterior = null; let estable = inicio;
    const revisar = () => {
      const vista = win.document.querySelector('main') || win.document.body;
      const texto = vista?.innerText || '';
      const bloquesCarga = vista?.querySelectorAll('[style*="animation: pulse"]').length || 0;
      const contenido = [...(vista?.querySelectorAll('p, section, [role="alert"]') || [])]
        .some(x => x.tagName === 'SECTION' || /unidad|granja|finca|sensor|administrador|error/i.test(x.innerText || ''));
      const cargando = /\bcargando(?:…|\.\.\.)?/i.test(texto) || bloquesCarga > 0;
      const firma = `${texto}|${bloquesCarga}|${vista?.querySelectorAll('section').length || 0}`;
      if (firma !== anterior || cargando) estable = Date.now();
      anterior = firma;
      if (acta.dashboard && !cargando && contenido && Date.now() - estable >= 300) return resolve(false);
      if (Date.now() - inicio >= limite) return resolve(true);
      win.setTimeout(revisar, 100);
    }; revisar();
  });
}

function evaluarPantalla(body) {
  const vista = body.querySelector('main') || body;
  const texto = vista.innerText || '';
  const mensaje_exacto = /no tiene (?:ninguna )?(?:unidades? productivas?|granjas?) asignadas?/i.test(texto);
  const contacto_admin = /(?:contact(?:e|ar)?|comuníquese|consulte)[^.!?]{0,100}administrador/i.test(texto);
  const sin_tarjetas = vista.querySelectorAll('section, button.ds-option').length === 0 && !acta.datos_ajenos;
  const sin_error_interno = !/error interno|internal server error|error al cargar el dashboard/i.test(texto);
  const texto_observado = ocultar([...vista.querySelectorAll('p, [role="alert"]')]
    .map(x => x.textContent?.trim()).filter(x => /unidad|granja|sensor|administrador|error/i.test(x || ''))
    .join(' | ') || texto || 'SIN_TEXTO_RELEVANTE');
  return { mensaje_exacto, contacto_admin, sin_tarjetas, sin_error_interno, texto_observado };
}

describe('[TC-M03-185] usuario sin fincas', () => {
  beforeEach(interceptar);
  afterEach(() => {
    acta.pendiente_al_terminar = acta.peticiones.some(x => !x.fin);
    if (acta.peticiones.some(x => ['/usuarios/me', '/sesiones/me/permisos'].includes(x.ruta) && x.http >= 500)) {
      acta.estado = 'NO_CONCLUYENTE'; acta.criterio = 'SESION_5XX'; acta.motivo = '5xx de sesión dentro del RUN';
    } else if (acta.pendiente_al_terminar || acta.carga_sin_terminar) {
      acta.estado = 'NO_CONCLUYENTE'; acta.criterio = 'CARGA_SIN_TERMINAR'; acta.motivo = 'Carga o petición UI sin terminar';
    } else if (acta.peticiones.some(x => x.http != null && !x.eco_run)) {
      acta.estado = 'NO_CONCLUYENTE'; acta.criterio = 'ECO_RUN_AUSENTE'; acta.motivo = 'Petición UI sin eco RUN';
    }
    cy.get('body').then($body => {
      $body[0].querySelectorAll('section').forEach(x => { x.style.filter = 'blur(12px)'; });
      if (acta.datos_ajenos) $body[0].querySelectorAll('main').forEach(x => { x.style.filter = 'blur(12px)'; });
    });
    cy.writeFile(`${DIR}/UI-185-01.json`, acta);
    cy.screenshot('UI-185-01', { capture: 'fullPage', overwrite: true }).then(() => {
      acta.captura = true; acta.motivo_captura = null; cy.writeFile(`${DIR}/UI-185-01.json`, acta);
    });
  });
  it('[TC-M03-185][ASSERT][UI-185-01] estado vacío, contacto y sin datos ajenos', () => {
    if (!autorizado) {
      acta.estado = 'ERROR_QA'; acta.motivo = 'BLOQUEO_G94: contrato de entorno o autorización inválido';
      throw new Error(acta.motivo);
    }
    cy.visit(`${FRONT}/login`);
    cy.get('input[type="email"]').clear().type('g94-ui@local.invalid', { log: false });
    cy.get('input[type="password"]').clear().type('G94LocalDummy123!', { log: false });
    cy.get('button[type="submit"]').click();
    cy.wait('@login', { requestTimeout: 90000, responseTimeout: 90000 }).then(({ response }) => {
      expect(response?.statusCode).to.eq(200); expect(response?.headers?.['x-test-run-id']).to.eq(RUN);
    });
    const esperarSesion = alias => cy.wait(alias, { requestTimeout: 90000, responseTimeout: 90000 }).then(({ response }) => {
        if (response?.statusCode >= 500) {
          acta.estado = 'NO_CONCLUYENTE'; acta.criterio = 'SESION_5XX'; acta.motivo = `${alias} HTTP ${response.statusCode}`;
          return;
        }
        expect(response?.statusCode).to.eq(200); expect(response?.headers?.['x-test-run-id']).to.eq(RUN);
      });
    esperarSesion('@usuarioSesion').then(() => {
      if (acta.criterio !== 'SESION_5XX') esperarSesion('@permisosSesion');
    });
    cy.then(() => {
      if (acta.criterio === 'SESION_5XX') return;
      if (acta.fincas_perfil !== 0) {
        acta.estado = 'NO_CONCLUYENTE'; acta.criterio = 'PERFIL_CON_FINCAS';
        acta.motivo = 'Perfil UI no acredita cero fincas'; return;
      }
      navegarSpa('/telemetria/monitoreo');
      cy.window().then(win => esperarCarga(win)).then(vencio => {
        acta.carga_sin_terminar = vencio;
        if (vencio) return;
        cy.get('body').then($body => {
          Object.assign(acta, evaluarPantalla($body[0]));
          const cumple = acta.dashboard?.http === 200 && acta.dashboard.eco_run
            && acta.mensaje_exacto && acta.contacto_admin && acta.sin_tarjetas && acta.sin_error_interno;
          acta.estado = cumple ? 'APROBADO' : 'RECHAZADO';
          acta.criterio = cumple ? 'ORACULO_UI_COMPLETO' : 'ORACULO_UI_INCUMPLIDO';
          acta.motivo = cumple ? 'Mensaje, contacto y ausencia de datos ajenos acreditados'
            : `Pantalla cargada con discrepancia: ${acta.texto_observado}`;
        });
      });
    });
  });
});
