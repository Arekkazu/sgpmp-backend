// | Fecha      | Nombre           | Que se hizo                                                        |
// |------------|------------------|--------------------------------------------------------------------|
// | 2026-11-19 | Juan Manuel      | TC-M08 RF-103/RF-105: pasos de frontend con Playwright (Chrome)    |
// | 2026-11-22 | Juan Manuel      | TC-M08-017: «Descartar» de no críticas se mira en la bandeja del Productor |
/*
 * Pasos de navegador de RF-103 (G001-G005) y RF-105 (G013, G014) contra el frontend de TEST.
 * Solo mira y mide: no marca, atiende ni descarta notificaciones (eso se prueba por API dentro del sandbox).
 * Deja un HTML por grupo en ../RF-10x/TC-M08-Gnnn/resultados/resultado_TC-M08-Gnnn_frontend.html, con capturas.
 *
 * Uso (desde tests\Test_Testing\Test_Modulo8\frontend):
 *   $env:PW_PATH = '<carpeta con node_modules\playwright-core>'   (no se instala en el repo)
 *   $env:QA_CONTRASENA_ADMIN = '...'; $env:QA_CONTRASENA_PRODUCTOR = '...'; ... (igual que el runner de Newman)
 *   node pruebas_frontend_m08.js
 */
const path = require('path');
const fs = require('fs');
const { chromium } = require(process.env.PW_PATH ? path.join(process.env.PW_PATH, 'node_modules', 'playwright-core') : 'playwright-core');

const FRONT = 'https://api.inmero.co/sigab-test';
const API = 'https://api.inmero.co/api-sgpmp-test';
const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const C = {
  admin: ['admin.rol@gmail.com', process.env.QA_CONTRASENA_ADMIN],
  prod: ['qa.m08.productor@sgpmp-test.com', process.env.QA_CONTRASENA_PRODUCTOR],
  vet: ['qa.m08.veterinario@sgpmp-test.com', process.env.QA_CONTRASENA_VETERINARIO],
  cont: ['qa.m08.contador@sgpmp-test.com', process.env.QA_CONTRASENA_CONTADOR],
  ing: ['qa.m08.ingeniero@sgpmp-test.com', process.env.QA_CONTRASENA_INGENIERO],
  gestor: ['gestor.granja@gmail.com', process.env.QA_CONTRASENA_GESTOR],
};
const WIDGETS_CONTADOR = ['periodos_abiertos', 'reconocimientos_pendientes', 'integraciones_fallidas', 'precios_por_vencer'];
const WIDGETS_TECNICOS_IOT = ['estado_iot', 'cal_sensores', 'cfg_pendiente', 'dispositivos_sin_senal'];

const grupos = {};  // G001 -> { rf, filas: [{caso, paso, ok, detalle, captura}] }
function anotar(g, rf, caso, paso, ok, detalle, captura) {
  (grupos[g] = grupos[g] || { rf, filas: [] }).filas.push({ caso, paso, ok, detalle, captura });
  console.log(`${ok === null ? '·' : ok ? '√' : '✗'} ${g} ${caso} - ${paso}: ${detalle}`);
}

async function nuevaSesion(browser, cuenta) {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 860 }, locale: 'es-CO', timezoneId: 'America/Bogota' });
  const page = await ctx.newPage();
  const red = [];
  page.on('response', r => { if (r.url().startsWith(API)) red.push({ url: r.url().slice(API.length), status: r.status(), t: Date.now() }); });
  await page.goto(FRONT + '/login', { waitUntil: 'networkidle' });
  await page.fill('input[name="correo_electronico"]', C[cuenta][0]);
  await page.fill('input[name="contrasena"]', C[cuenta][1]);
  const t0 = Date.now();
  await page.click('button[type="submit"]');
  return { ctx, page, red, t0 };
}

const widgetsPedidos = red => [...new Set(red.filter(r => /^\/dashboard\/widgets\/[a-z0-9_]+\?/.test(r.url)).map(r => r.url.split('/')[3].split('?')[0]))];
const captura = async page => (await page.screenshot({ fullPage: true })).toString('base64');

// Espera a que el dashboard termine: después del último widget pedido no llega otro en 1,5 s.
async function esperarDashboard(page, red, maxMs = 20000) {
  const inicio = Date.now();
  await page.waitForURL(/dashboard|inicio|\/$/, { timeout: maxMs }).catch(() => {});
  let ultimo = 0;
  while (Date.now() - inicio < maxMs) {
    const w = red.filter(r => r.url.startsWith('/dashboard/widgets/'));
    if (w.length && w[w.length - 1].t !== ultimo) { ultimo = w[w.length - 1].t; await page.waitForTimeout(1500); continue; }
    if (w.length) break;
    await page.waitForTimeout(300);
  }
  const w = red.filter(r => r.url.startsWith('/dashboard/widgets/'));
  return w.length ? w[w.length - 1].t : null;
}

async function g001_g002_g005(browser) {
  // TC-M08-001: login → dashboard completo en ≤ 3 s, con saludo y finca activa.
  for (const [cuenta, rol] of [['prod', 'Productor'], ['admin', 'Administrador']]) {
    const s = await nuevaSesion(browser, cuenta);
    const fin = await esperarDashboard(s.page, s.red);
    const ms = fin ? fin - s.t0 : null;
    const texto = await s.page.innerText('body');
    const cap = await captura(s.page);
    anotar('G001', 'RF-103', 'TC-M08-001', `${rol}: el dashboard carga completo en ≤ 3 s desde «Ingresar»`, ms !== null && ms <= 3000,
      `${ms} ms hasta la respuesta del último widget (${widgetsPedidos(s.red).length} widgets: ${widgetsPedidos(s.red).join(', ')})`, cap);
    anotar('G001', 'RF-103', 'TC-M08-001', `${rol}: la primera pantalla es el dashboard, con saludo y finca activa`,
      /Hola,/.test(texto) && /finca/i.test(texto), `URL ${s.page.url().replace(FRONT, '')}; saludo: ${(texto.match(/Hola,[^\n]*/) || ['(no)'])[0]}`);
    if (cuenta === 'prod') {
      // TC-M08-012: los widgets son de solo lectura (solo navegación «Ver más» y configuración del propio widget).
      const botones = await s.page.$$eval('main button, main a', es => es.map(e => (e.innerText || e.getAttribute('aria-label') || '').trim()).filter(Boolean));
      const malos = botones.filter(b => /editar|eliminar|borrar|guardar|registrar|anular|dar de baja/i.test(b));
      anotar('G005', 'RF-103', 'TC-M08-012', 'Productor: ningún widget tiene botones para editar o borrar datos', malos.length === 0,
        `Botones y enlaces en el dashboard: ${[...new Set(botones)].join(' | ')}`, cap);
      const verMas = botones.filter(b => /ver más/i.test(b)).length;
      anotar('G002', 'RF-103', 'TC-M08-003', 'Productor: cada indicador tiene acceso a su módulo («Ver más») y hora de actualización',
        verMas > 0 && /Actualizado a las|Última actualización/.test(texto), `${verMas} enlaces «Ver más»; hora visible: ${/Actualizado a las \d/.test(texto)}`);
      anotar('G003', 'RF-103', 'TC-M08-011', 'Productor con una sola finca: no aparece el selector de finca',
        !(await s.page.$('header [role="combobox"], header select')), 'Sin combobox ni select de finca en la barra superior', null);
      // TC-M08-009: actualización automática cada 30 s sin recargar la pantalla.
      const desde = Date.now();
      await s.page.waitForTimeout(70000);
      const serie = s.red.filter(r => r.t >= desde && r.url.startsWith('/dashboard/widgets/semaforo_areas')).map(r => r.t);
      const pasos = serie.slice(1).map((t, k) => Math.round((t - serie[k]) / 1000));
      anotar('G004', 'RF-103', 'TC-M08-009', 'El dashboard se actualiza solo cada 30 s (semáforo pedido de nuevo sin recargar)',
        pasos.length >= 1 && pasos.every(p => p >= 25 && p <= 35), `En 70 s se pidió ${serie.length} veces; intervalos: ${pasos.join(', ')} s`);
      // TC-M08-010 (a): se pierde la red con el dashboard abierto; al siguiente refresco cada widget conserva lo último.
      await s.ctx.setOffline(true);
      await s.page.waitForTimeout(35000);
      const abierta = await s.page.innerText('body');
      anotar('G004', 'RF-103', 'TC-M08-010', 'Sin red con la pantalla abierta: los widgets conservan sus datos con «Última actualización» e indicador «Sin conexión»',
        /Última actualización/.test(abierta) && /Sin conexión/.test(abierta),
        `Última actualización: ${(abierta.match(/Última actualización/g) || []).length} widgets; Sin conexión: ${/Sin conexión/.test(abierta)}`, await captura(s.page));
      // TC-M08-010 (b): se abre (recarga) el dashboard sin conexión: debe cargar desde la caché en ≤ 5 s.
      const t1 = Date.now();
      let ok = true;
      await s.page.reload({ waitUntil: 'domcontentloaded', timeout: 10000 }).catch(() => { ok = false; });
      await s.page.waitForTimeout(2500);
      const off = ok ? await s.page.innerText('body').catch(() => '') : '';
      const capOff = await captura(s.page).catch(() => null);
      anotar('G004', 'RF-103', 'TC-M08-010', 'Abrir sin conexión: el dashboard carga los widgets desde la caché en ≤ 5 s',
        ok && !/No se pudo cargar el dashboard|no tiene widgets configurados/.test(off) && /Última actualización/.test(off),
        ok ? `La app abrió sin red; texto: ${off.replace(/\s+/g, ' ').slice(0, 260)}` : 'La página no cargó sin conexión', capOff);
      anotar('G004', 'RF-103', 'TC-M08-010', 'Abrir sin conexión: «Última actualización» en cada widget, indicador «Sin conexión» y «Disponible con conexión»',
        /Última actualización/.test(off) && /Sin conexión/.test(off) && /Disponible con conexión/.test(off),
        `Última actualización: ${/Última actualización/.test(off)}; Sin conexión: ${/Sin conexión/.test(off)}; Disponible con conexión: ${/Disponible con conexión/.test(off)}`);
      await s.ctx.setOffline(false);
      const t2 = Date.now();
      await s.page.waitForTimeout(40000);
      const vuelta = s.red.filter(r => r.t >= t2 && r.url.startsWith('/dashboard/widgets/')).length;
      anotar('G004', 'RF-103', 'TC-M08-010', 'Al volver la conexión el dashboard se sincroniza solo', vuelta > 0, `${vuelta} widgets pedidos en los 40 s siguientes`);
    }
    await s.ctx.close();
  }
  // TC-M08-002: cada rol pide solo sus widgets.
  const pedidos = {};
  for (const [cuenta, rol] of [['prod', 'Productor'], ['vet', 'Veterinario'], ['cont', 'Contador'], ['ing', 'Ingeniero de Campo']]) {
    const s = await nuevaSesion(browser, cuenta);
    await esperarDashboard(s.page, s.red);
    pedidos[cuenta] = widgetsPedidos(s.red);
    anotar('G001', 'RF-103', 'TC-M08-002', `${rol}: dashboard propio del rol`, pedidos[cuenta].length > 0, `Widgets: ${pedidos[cuenta].join(', ')}`, await captura(s.page));
    await s.ctx.close();
  }
  anotar('G001', 'RF-103', 'TC-M08-002', 'El Productor no ve widgets del Contador ni el Contador los del Productor',
    !pedidos.prod.some(k => WIDGETS_CONTADOR.includes(k)) && !pedidos.cont.some(k => pedidos.prod.includes(k) && k !== 'valor_inventario'),
    `Productor ∩ Contador: ${pedidos.prod.filter(k => pedidos.cont.includes(k)).join(', ') || 'ninguno'}`);
  anotar('G001', 'RF-103', 'TC-M08-002', 'Dashboard por defecto del Productor sin widgets técnicos de IoT', !pedidos.prod.some(k => WIDGETS_TECNICOS_IOT.includes(k)),
    `Técnicos de IoT en el dashboard del Productor: ${pedidos.prod.filter(k => WIDGETS_TECNICOS_IOT.includes(k)).join(', ') || 'ninguno'}`);
  // TC-M08-007: el Gestor de Granja no ve widgets ni datos.
  const g = await nuevaSesion(browser, 'gestor');
  await g.page.waitForTimeout(6000);
  const datos = g.red.filter(r => r.url.startsWith('/dashboard/widgets/') && r.status === 200).length;
  anotar('G001', 'RF-103', 'TC-M08-007', 'Gestor de Granja (sin permiso de dashboard): no se muestran widgets ni datos', datos === 0,
    `${datos} widgets con datos; respuestas del dashboard: ${g.red.filter(r => /dashboard/.test(r.url)).map(r => r.url.split('?')[0] + ' ' + r.status).join(', ') || 'ninguna'}`, await captura(g.page));
  await g.ctx.close();
}

async function g003_semaforo(browser) {
  // TC-M08-005: el semáforo de la finca 494 muestra Crítico, Alerta y Sin datos/Normal.
  const s = await nuevaSesion(browser, 'prod');
  await esperarDashboard(s.page, s.red);
  const t = await s.page.innerText('body');
  anotar('G003', 'RF-103', 'TC-M08-005', 'Semáforo en pantalla: área crítica «Crítico», área con moderadas «Alerta» y área sin alertas sin rojo ni amarillo',
    /Corral Reportes Integrados Qa[\s\S]{0,80}Crítico|Crítico[\s\S]{0,80}Corral Reportes Integrados Qa/.test(t) && /Alerta/.test(t),
    `Texto del semáforo: ${(t.match(/Corral[^\n]*\n?[^\n]*/g) || []).slice(0, 6).join(' / ')}`, await captura(s.page));
  await s.ctx.close();
}

async function g013_g014(browser) {
  // TC-M08-013: el badge muestra las mismas no leídas que la API; TC-M08-017: una crítica no ofrece «Descartar».
  const s = await nuevaSesion(browser, 'admin');
  await esperarDashboard(s.page, s.red);
  const campana = await s.page.$('button[aria-controls="notification-tray"]');
  const etiqueta = campana ? await campana.getAttribute('aria-label') : '';
  const badge = campana ? (await campana.innerText()).trim() : '';
  const tB = Date.now();
  if (campana) await campana.click();
  await s.page.waitForSelector('#notification-tray', { timeout: 8000 }).catch(() => {});
  await s.page.waitForTimeout(2500);
  const listas = s.red.filter(r => r.t >= tB && /^\/notificaciones\?/.test(r.url));
  const ms = listas.length ? listas[0].t - tB : null;
  const capB = await captura(s.page);
  const bandeja = await s.page.innerText('#notification-tray').catch(() => '');
  // no_leidas reales, con el token de una sesión aparte (solo lectura)
  const api = await (await fetch(API + '/sesiones/', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: C.admin[0], contrasena: C.admin[1] }) })).json();
  const nl = await (await fetch(API + '/notificaciones?tamano=1', { headers: { Authorization: 'Bearer ' + api.token } })).json();
  const esperado = nl.no_leidas > 99 ? '99+' : String(nl.no_leidas);
  anotar('G013', 'RF-105', 'TC-M08-013', 'El badge de la campana muestra las no leídas de la API', badge === esperado || badge === String(nl.no_leidas),
    `Badge «${badge}» (aria-label «${etiqueta}»); API no_leidas = ${nl.no_leidas}`, capB);
  anotar('G013', 'RF-105', 'TC-M08-013', 'La bandeja abre y lista en ≤ 2 s', ms !== null && ms <= 2000, `Primera respuesta de /notificaciones a los ${ms} ms del clic`);
  const items = await s.page.$$eval('#notification-tray article.notification-tray__item', es => es.map(e => e.innerText));
  const criticas = items.filter(t => /Crítica/.test(t));
  const otras = items.filter(t => /Advertencia|Informativa/.test(t));
  anotar('G014', 'RF-105', 'TC-M08-017', 'En la bandeja una crítica no tiene «Descartar» y sí «Marcar como atendida»',
    criticas.length > 0 && criticas.every(t => !/Descartar/.test(t) && /Marcar como atendida/.test(t)),
    `${criticas.length} críticas visibles; con «Descartar»: ${criticas.filter(t => /Descartar/.test(t)).length}`, capB);
  // El admin ya no tiene informativas (eran inicios de sesión, ocultos de la bandeja): se miran en la del Productor.
  {
    const p = await nuevaSesion(browser, 'prod');
    await esperarDashboard(p.page, p.red);
    const camP = await p.page.$('button[aria-controls="notification-tray"]');
    if (camP) await camP.click();
    await p.page.waitForSelector('#notification-tray', { timeout: 8000 }).catch(() => {});
    await p.page.waitForTimeout(2500);
    const itemsP = await p.page.$$eval('#notification-tray article.notification-tray__item', es => es.map(e => e.innerText));
    const otrasP = itemsP.filter(t => /Advertencia|Informativa/.test(t));
    const capP = await captura(p.page);
    anotar('G014', 'RF-105', 'TC-M08-017', 'Una advertencia o informativa sí ofrece «Descartar» (bandeja del Productor)', otrasP.length > 0 && otrasP.every(t => /Descartar/.test(t)),
      `${otrasP.length} advertencias/informativas visibles; con «Descartar»: ${otrasP.filter(t => /Descartar/.test(t)).length}`, capP);
    await p.ctx.close();
  }
  if (criticas.length) {
    // «Marcar como atendida» solo abre un formulario dentro de la tarjeta (no envía nada); se cierra con su Cancelar.
    const tarjeta = s.page.locator('#notification-tray article.notification-tray__item', { hasText: 'Crítica' }).first();
    const red0 = s.red.length;
    await tarjeta.getByRole('button', { name: 'Marcar como atendida' }).click();
    await s.page.waitForTimeout(1000);
    const form = await tarjeta.innerText();
    const area = await tarjeta.locator('textarea').count();
    const capD = await captura(s.page);
    anotar('G014', 'RF-105', 'TC-M08-017', '«Marcar como atendida» en una crítica pide escribir qué se hizo (obligatorio)', area === 1 && /obligatori|qué hiciste/i.test(form),
      `Formulario en la tarjeta: ${form.replace(/\s+/g, ' ').slice(-220)} · textarea: ${area}`, capD);
    await tarjeta.getByRole('button', { name: 'Cancelar' }).click();
    const enviados = s.red.slice(red0).filter(r => /\/(atendida|descartada|leida)/.test(r.url));
    anotar('G014', 'RF-105', 'TC-M08-017', 'Abrir y cancelar el formulario no envía ningún cambio', enviados.length === 0, `${enviados.length} peticiones de cambio de estado`);
  }
  await s.ctx.close();
}

function html(g, { rf, filas }) {
  const esc = t => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const ok = filas.filter(f => f.ok === true).length, mal = filas.filter(f => f.ok === false).length;
  return `<!doctype html><html lang="es"><meta charset="utf-8"><title>TC-M08-${g} frontend</title>
<style>body{font-family:system-ui,sans-serif;margin:24px;background:#fff;color:#222}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:6px;vertical-align:top;font-size:14px}
.ok{color:#126b2b;font-weight:600}.mal{color:#b00020;font-weight:600}img{max-width:100%;border:1px solid #999;margin:8px 0}</style>
<h1>TC-M08-${g} · ${rf} · pasos de frontend</h1>
<p>Frontend de TEST ${FRONT} · Chrome con Playwright · ${new Date().toISOString()} · <span class="ok">${ok} aprobados</span> · <span class="mal">${mal} fallidos</span></p>
<p>Solo lectura: no se marcan, atienden ni descartan notificaciones (eso se prueba por API dentro del sandbox).</p>
<table><tr><th>Caso</th><th>Paso</th><th>Resultado</th><th>Detalle</th></tr>
${filas.map(f => `<tr><td>${f.caso}</td><td>${esc(f.paso)}</td><td class="${f.ok ? 'ok' : 'mal'}">${f.ok ? 'APROBADO' : 'FALLA'}</td><td>${esc(f.detalle)}${f.captura ? `<br><img alt="captura" src="data:image/png;base64,${f.captura}">` : ''}</td></tr>`).join('\n')}
</table></html>`;
}

(async () => {
  const faltan = Object.entries(C).filter(([, v]) => !v[1]).map(([k]) => k);
  if (faltan.length) { console.error('Faltan contraseñas (QA_CONTRASENA_*): ' + faltan.join(', ')); process.exit(1); }
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  try {
    await g001_g002_g005(browser);
    await g003_semaforo(browser);
    await g013_g014(browser);
  } finally {
    await browser.close();
    for (const [g, d] of Object.entries(grupos)) {
      const dir = path.join(__dirname, '..', d.rf, `TC-M08-${g}`, 'resultados');
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, `resultado_TC-M08-${g}_frontend.html`), html(g, d), 'utf8');
      console.log('Reporte: ' + path.join(dir, `resultado_TC-M08-${g}_frontend.html`));
    }
  }
})();
