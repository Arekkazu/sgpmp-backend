// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

// TC-M03-204 (RNF-06): a 360 px de ancho permanecen visibles y utilizables el valor, la unidad, el
// semáforo, las alertas y los controles principales, sin superposición ni recorte de información
// crítica, con sensores en VERDE, AMARILLO, ROJO y GRIS. 360 px es decisorio; 768 y 1366 px se
// registran como INFO. Todo el tráfico al API pasa por el sandbox del RUN; sin respuestas simuladas.
const env = k => Cypress.env(k);
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN = env('RUN_ID');
const VARIANTES = (() => { try { return JSON.parse(env('VARIANTES') || '{}'); } catch (e) { return {}; } })();
const ORDEN = ['VERDE', 'AMARILLO', 'ROJO', 'GRIS'];
const PANTALLAS = [{ ancho: 360, alto: 740, tipo: 'ASSERT' }, { ancho: 768, alto: 1024, tipo: 'INFO' }, { ancho: 1366, alto: 768, tipo: 'INFO' }];
const SEMAFORO = /^(normal|advertencia|fuera de rango|sin se[ñn]al|verde|amarillo|rojo|gris)$/i;
const NUMERO = /^-?\d+(?:[.,]\d+)?$/;
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
function abrirUnidad(d) {
  cy.visit(urlFrontendQA('/telemetria/monitoreo'));
  cy.get('input[type="number"]').first().clear().type(String(d.id), { delay: 0 });
  cy.wrap(null, { timeout: 30000 }).should(() => {
    const propios = pedidos.filter(x => new URL(x.url).searchParams.get('id_infraestructura') === String(d.id));
    expect(propios.length, 'petición del dashboard filtrada por la unidad').to.be.greaterThan(0);
    expect(propios.every(x => x.respondido), 'respuestas recibidas').to.eq(true);
    expect(propios[propios.length - 1].eco, 'respuesta dentro del sandbox del RUN').to.eq(RUN);
  });
  cy.document({ timeout: 30000 }).should(doc => expect(tarjeta(doc, d.sensor), `tarjeta del sensor «${d.sensor}»`).to.exist);
  cy.then(() => expect(fugas, 'peticiones fuera del sandbox').to.have.length(0));
}

// ---- Localización (por contenido visible, no por estructura interna) -----------------------
function tarjeta(doc, nombre) {
  return [...doc.querySelectorAll('section button.ds-option')].find(el => (el.innerText || '').split('\n')[0].trim() === nombre);
}
function porTexto(raiz, prueba) {
  const out = [];
  const w = raiz.ownerDocument.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) { const t = n.nodeValue.trim(); if (t && prueba(t)) out.push(n.parentElement); }
  return out;
}
const etiquetaDe = el => `${el.getAttribute('aria-label') || ''} ${el.getAttribute('title') || ''}`;
function criticos(doc, d) {
  const t = tarjeta(doc, d.sensor);
  expect(t, `tarjeta del sensor «${d.sensor}»`).to.exist;
  const valor = porTexto(t, x => NUMERO.test(x))[0];
  const unidad = porTexto(t, x => x === d.medida)[0];
  const semaforo = porTexto(t, x => SEMAFORO.test(x))[0];
  const alerta = [...t.querySelectorAll('[aria-label], [title]')].find(el => /alerta|alert/i.test(etiquetaDe(el)));
  return { tarjeta: t, valor, unidad, semaforo, alerta };
}

// ---- Usabilidad geométrica ------------------------------------------------------------------
/** Visible, dentro del ancho, no recortado por un contenedor y no tapado por otro elemento. */
function usable(win, el, nombre) {
  expect(el, `${nombre}: presente`).to.exist;
  el.scrollIntoView({ block: 'center', inline: 'nearest' });
  const r = el.getBoundingClientRect();
  const cs = win.getComputedStyle(el);
  expect(r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && Number(cs.opacity) > 0, `${nombre}: visible`).to.eq(true);
  expect(r.left >= -0.5 && r.right <= win.innerWidth + 0.5, `${nombre}: dentro del ancho de la pantalla (${Math.round(r.left)}–${Math.round(r.right)} de ${win.innerWidth} px)`).to.eq(true);
  for (let p = el.parentElement; p && p !== win.document.body; p = p.parentElement) {
    const s = win.getComputedStyle(p);
    if (/hidden|clip|auto|scroll/.test(`${s.overflowX} ${s.overflowY}`)) {
      const q = p.getBoundingClientRect();
      expect(r.left >= q.left - 0.5 && r.right <= q.right + 0.5 && r.top >= q.top - 0.5 && r.bottom <= q.bottom + 0.5, `${nombre}: no recortado por su contenedor`).to.eq(true);
    }
  }
  if (/hidden|clip/.test(cs.overflowX) && el.scrollWidth) expect(el.scrollWidth <= el.clientWidth + 1, `${nombre}: texto sin recortar`).to.eq(true);
  const arriba = win.document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  expect(!!arriba && (arriba === el || el.contains(arriba) || arriba.contains(el)), `${nombre}: no tapado por otro elemento`).to.eq(true);
}
function sinSuperposicion(pares) {
  for (const [[na, a], [nb, b]] of pares) {
    if (!a || !b || a.contains(b) || b.contains(a)) continue;
    const r = a.getBoundingClientRect(), s = b.getBoundingClientRect();
    const area = Math.max(0, Math.min(r.right, s.right) - Math.max(r.left, s.left)) * Math.max(0, Math.min(r.bottom, s.bottom) - Math.max(r.top, s.top));
    expect(area, `${na} y ${nb} no se superponen`).to.be.at.most(1);
  }
}
/** Controles principales de la vista: los de la cabecera que contiene el filtro y el título. */
function controles(doc) {
  const filtro = doc.querySelector('input[type="number"]');
  expect(filtro, 'filtro de la vista').to.exist;
  let cabecera = filtro.parentElement;
  while (cabecera && !cabecera.querySelector('h1')) cabecera = cabecera.parentElement;
  const zona = cabecera && cabecera !== doc.body ? cabecera : filtro.parentElement;
  return [...zona.querySelectorAll('button, input, select, a[href], [role="button"]')].filter(el => el.offsetParent !== null && !el.matches('section button.ds-option'));
}
function comprobarPagina(win, doc) {
  expect(doc.documentElement.scrollWidth, 'sin desplazamiento horizontal de la página').to.be.at.most(win.innerWidth + 1);
  const cs = controles(doc);
  expect(cs.length, 'controles principales visibles').to.be.greaterThan(0);
  cs.forEach((el, i) => usable(win, el, `control «${(el.getAttribute('aria-label') || el.innerText || el.getAttribute('placeholder') || `#${i + 1}`).trim()}»`));
}
function comprobarSensor(win, doc, d) {
  const c = criticos(doc, d);
  usable(win, c.valor, 'valor');
  usable(win, c.unidad, 'unidad');
  usable(win, c.semaforo, 'semáforo');
  sinSuperposicion([[['valor', c.valor], ['semáforo', c.semaforo]], [['unidad', c.unidad], ['semáforo', c.semaforo]]]);
}
function comprobarAlerta(win, doc, d) {
  const c = criticos(doc, d);
  usable(win, c.alerta, 'alerta activa');
  sinSuperposicion([[['alerta', c.alerta], ['valor', c.valor]], [['alerta', c.alerta], ['semáforo', c.semaforo]], [['alerta', c.alerta], ['unidad', c.unidad]]]);
}

describe('TC-M03-G104 — RF-58 / RNF-06 (interfaz responsive)', () => {
  before(() => {
    if (env('AUTORIZADO_RUN') !== 'SI' || !RUN || !/^https:\/\//.test(API) || !Object.keys(VARIANTES).length) throw Error('BLOQUEO_G104');
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

  for (const p of PANTALLAS) {
    for (const k of ORDEN.filter(x => VARIANTES[x])) {
      const d = VARIANTES[k];
      if (p.tipo === 'ASSERT') {
        it(`[TC-M03-204][PRE][V:${k}] ${p.ancho} px: vista de la unidad del sensor ${k} dentro del sandbox`, () => { cy.viewport(p.ancho, p.alto); abrirUnidad(d); });
        it(`[TC-M03-204][ASSERT][UI-204-01][V:${k}] ${p.ancho} px: sin desplazamiento horizontal; controles principales visibles y utilizables`, () => {
          cy.window().then(win => cy.document().then(doc => comprobarPagina(win, doc)));
        });
        it(`[TC-M03-204][ASSERT][UI-204-02][V:${k}] ${p.ancho} px: valor, unidad y semáforo visibles, sin recorte ni superposición`, () => {
          cy.window().then(win => cy.document().then(doc => comprobarSensor(win, doc, d)));
        });
        if (d.alerta) it(`[TC-M03-204][ASSERT][UI-204-03][V:${k}] ${p.ancho} px: la alerta activa es visible, sin recorte ni superposición`, () => {
          cy.window().then(win => cy.document().then(doc => comprobarAlerta(win, doc, d)));
        });
        if (k === 'VERDE') it(`[TC-M03-204][ASSERT][UI-204-04][V:${k}] ${p.ancho} px: la tarjeta abre su detalle, que cabe en pantalla y se puede cerrar`, () => {
          cy.document().then(doc => cy.wrap(tarjeta(doc, d.sensor)).click());
          cy.get('[role="dialog"]').should('be.visible').then($d => {
            cy.window().then(win => {
              const r = $d[0].getBoundingClientRect();
              expect(r.left >= -0.5 && r.right <= win.innerWidth + 0.5, 'el detalle cabe en el ancho de la pantalla').to.eq(true);
              const cerrar = [...$d[0].querySelectorAll('button')].find(b => /cerrar|close|×|✕/i.test(`${b.getAttribute('aria-label') || ''} ${b.innerText || ''}`)) || $d[0].querySelector('button');
              usable(win, cerrar, 'cerrar el detalle');
              cy.wrap(cerrar).click();
            });
          });
          cy.get('[role="dialog"]').should('not.exist');
        });
      } else {
        it(`[TC-M03-204][INFO][V:${k}] ${p.ancho} px: misma comprobación en una resolución superior`, () => {
          cy.viewport(p.ancho, p.alto); abrirUnidad(d);
          cy.window().then(win => cy.document().then(doc => { comprobarPagina(win, doc); comprobarSensor(win, doc, d); if (d.alerta) comprobarAlerta(win, doc, d); }));
        });
      }
    }
  }
});
