// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

// TC-M03-201 / TC-M03-202 (interfaz): máximo 50 sensores renderizados por vista y acceso a todos
// los sensores de la unidad mediante segmentación (paginación, carga incremental u otro control).
// Todo el tráfico al API pasa por el sandbox del RUN; sin respuestas simuladas.
const env = k => Cypress.env(k);
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN = env('RUN_ID');
const UNIDADES = (() => { try { return JSON.parse(env('UNIDADES') || '{}'); } catch (e) { return {}; } })();
const MAX_VISTA = 50;
const CONTROL_SIGUIENTE = /siguiente|next|cargar m[aá]s|ver m[aá]s|mostrar m[aá]s|m[aá]s sensores/i;
let cola = Promise.resolve();
const fugas = [];
const pedidos = [];

function sandbox() {
  // Peticiones en serie: el sandbox comparte una sola sesión de base de datos por RUN.
  cy.intercept({ url: `${API}/**` }, req => {
    let liberar;
    const turno = cola;
    cola = new Promise(resolve => { liberar = resolve; });
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN;
      req.headers['X-Sandbox-Secret'] = env('SANDBOX_SECRET');
      const p = /\/iot\/monitoreo\/dashboard/.test(req.url) ? { url: req.url, respondido: false, eco: null } : null;
      if (p) pedidos.push(p);
      req.continue(res => {
        if (req.method !== 'OPTIONS' && res.headers['x-test-run-id'] !== RUN) fugas.push(req.url);
        if (p) { p.respondido = true; p.eco = res.headers['x-test-run-id']; }
        liberar();
      });
    });
  });
}
const escapar = s => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
/** Tarjetas de sensor visibles en la vista y nombres de los sensores QA de la unidad. */
function vista(doc, u) {
  const rx = new RegExp(`${escapar(u.prefijo)}\\d{3}`);
  const tarjetas = [...doc.querySelectorAll('section button.ds-option')].filter(el => el.offsetParent !== null);
  const nombres = tarjetas.map(el => (el.innerText.match(rx) || [null])[0]).filter(Boolean);
  return { total: tarjetas.length, nombres, ajenas: tarjetas.length - nombres.length };
}
function siguiente(doc) {
  return [...doc.querySelectorAll('button, a[href], [role="button"]')].find(el => el.offsetParent !== null && !el.matches('section button.ds-option') && !el.disabled
    && el.getAttribute('aria-disabled') !== 'true' && CONTROL_SIGUIENTE.test(`${el.innerText || ''} ${el.getAttribute('aria-label') || ''} ${el.getAttribute('title') || ''}`));
}
/** Abre la vista de monitoreo filtrada por la unidad y espera su respuesta dentro del sandbox. */
function abrirUnidad(clave) {
  const u = UNIDADES[clave];
  cy.visit(urlFrontendQA('/telemetria/monitoreo'));
  cy.get('input[type="number"]').first().clear().type(String(u.id), { delay: 0 });
  cy.wrap(null, { timeout: 30000 }).should(() => {
    const propios = pedidos.filter(x => new URL(x.url).searchParams.get('id_infraestructura') === String(u.id));
    expect(propios.length, 'petición del dashboard filtrada por la unidad').to.be.greaterThan(0);
    expect(propios.every(x => x.respondido), 'respuestas recibidas').to.eq(true);
    expect(propios[propios.length - 1].eco, 'respuesta dentro del sandbox del RUN').to.eq(RUN);
  });
  cy.contains('section', u.nombre, { timeout: 30000 }).should('be.visible');
  cy.then(() => expect(fugas, 'peticiones fuera del sandbox').to.have.length(0));
}
/** Recorre los segmentos que ofrezca la vista (máximo 10) registrando cada uno. */
function recorrer(u, acc, paso = 0) {
  cy.document().then(doc => {
    const v = vista(doc, u);
    acc.push(v);
    const control = paso < 9 ? siguiente(doc) : null;
    if (!control) return;
    const firma = v.nombres.join('|');
    const etiqueta = (control.innerText || control.getAttribute('aria-label') || '').trim();
    cy.wrap(control).click();
    cy.document().should(d => {
      const w = vista(d, u);
      expect(w.total > 0 && w.nombres.join('|') !== firma, `el control «${etiqueta}» muestra otro segmento`).to.eq(true);
    });
    recorrer(u, acc, paso + 1);
  });
}
function cobertura(acc, u) {
  const todos = acc.flatMap(v => v.nombres);
  expect(acc.length, 'vistas recorridas').to.be.greaterThan(0);
  expect(acc.map(v => v.total).filter(t => t > MAX_VISTA), 'vistas con más de 50 sensores').to.deep.eq([]);
  expect(acc.reduce((s, v) => s + v.ajenas, 0), 'sensores de otras unidades').to.eq(0);
  expect(new Set(todos).size, 'sin duplicados entre segmentos').to.eq(todos.length);
  expect(new Set(todos).size, `sensores de la unidad consultados mediante segmentación (de ${u.esperados})`).to.eq(u.esperados);
}

describe('TC-M03-G102 — RF-58 / CU04 (interfaz)', () => {
  before(() => {
    if (env('AUTORIZADO_RUN') !== 'SI' || !RUN || !/^https:\/\//.test(API) || !UNIDADES.U50 || !UNIDADES.U51 || !UNIDADES.U200) throw Error('BLOQUEO_G102');
    sandbox();
    cy.viewport(1366, 768);
    cy.visit(urlFrontendQA('/login'), { onBeforeLoad(win) {
      win.localStorage.clear(); win.sessionStorage.clear();
      if (win.indexedDB && win.indexedDB.databases) win.indexedDB.databases().then(dbs => dbs.forEach(d => d.name && win.indexedDB.deleteDatabase(d.name)));
    } });
    cy.get('input[type="email"]').type(env('EMAIL'), { log: false });
    cy.get('input[type="password"]').type(env('PASSWORD'), { log: false });
    cy.get('button[type="submit"]').click();
    cy.location('pathname', { timeout: 30000 }).should('not.include', '/login');
  });

  it('[TC-M03-201][PRE][V:U50] vista filtrada por la unidad con 50 sensores dentro del sandbox', () => abrirUnidad('U50'));
  it('[TC-M03-201][ASSERT][UI-201-01][V:U50] con 50 sensores se renderizan todos', () => {
    cy.document().should(doc => {
      const v = vista(doc, UNIDADES.U50);
      expect(v.total, 'tarjetas renderizadas').to.eq(50);
      expect(new Set(v.nombres).size, 'sensores distintos de la unidad').to.eq(50);
      expect(v.ajenas, 'sensores de otras unidades').to.eq(0);
    });
  });

  it('[TC-M03-201][PRE][V:U51] vista filtrada por la unidad con 51 sensores dentro del sandbox', () => abrirUnidad('U51'));
  it('[TC-M03-201][ASSERT][UI-201-02][V:U51] con 51 sensores no se renderizan más de 50 simultáneamente', () => {
    cy.document().should(doc => {
      const v = vista(doc, UNIDADES.U51);
      expect(v.total, 'tarjetas renderizadas').to.be.greaterThan(0);
      expect(v.total, 'tarjetas renderizadas a la vez').to.be.at.most(MAX_VISTA);
    });
  });
  it('[TC-M03-201][ASSERT][UI-201-03][V:U51] la segmentación permite consultar el sensor restante', () => {
    const acc = [];
    recorrer(UNIDADES.U51, acc);
    cy.then(() => cobertura(acc, UNIDADES.U51));
  });

  const recorrido200 = [];
  it('[TC-M03-202][PRE][V:U200] vista filtrada por la unidad con 200 sensores dentro del sandbox', () => abrirUnidad('U200'));
  it('[TC-M03-202][ASSERT][UI-202-01][V:U200] ningún segmento renderiza más de 50 sensores simultáneamente', () => {
    cy.document().should(doc => expect(vista(doc, UNIDADES.U200).total, 'tarjetas renderizadas').to.be.greaterThan(0));
    recorrer(UNIDADES.U200, recorrido200);
    cy.then(() => expect(recorrido200.map(v => v.total).filter(t => t > MAX_VISTA), 'segmentos con más de 50 sensores').to.deep.eq([]));
  });
  it('[TC-M03-202][ASSERT][UI-202-02][V:U200] mediante la segmentación se consultan los 200 sensores sin duplicados, omisiones ni sensores ajenos', () => {
    cy.then(() => cobertura(recorrido200, UNIDADES.U200));
    cy.then(() => expect(fugas, 'peticiones fuera del sandbox').to.have.length(0));
  });
});
