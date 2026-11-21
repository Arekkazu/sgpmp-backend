/**
 * TC-M02-G47 V2 - reevaluacion dirigida de hallazgos V1 (parte de interfaz).
 *
 * No forma parte de TC-M02-089 ni de sus assertions S6/S7 (esas estan en
 * verificar_render_tc_m02_g47_v2.cy.js). Solo registra evidencia de:
 *
 * - OBS-G47-01 (V1 §10) / OBS-G47-02 (comentario del spec V1): el listado de activos
 *   muestra solo la primera pagina y no expone control de paginacion.
 * - OBS-G47-03 (V1 §8.3): `POST /sesiones/refresh` -> HTTP 500. Contexto V1: sesion
 *   iniciada por la interfaz y, a continuacion, `cy.visit()` a la ruta del activo, que
 *   recarga la pagina, descarta el access token en memoria y hace que la SPA intente
 *   `POST /sesiones/refresh` con la cookie HttpOnly. Aqui se repite ese mismo escenario.
 *
 * No escribe datos de dominio. La evidencia se vuelca a Resultados/hallazgos_ui_v2.json.
 */

const FRONTEND = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const DESTINO = 'tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G47/EvaluacionV2/Resultados/hallazgos_ui_v2.json';

const ACTORES = [
  { nombre: 'Productor', correo: 'm2m.nuevo@ejemplo.com', contrasena: 'Test1234!', idActivo: 450, identificador: 'QAJE-G47-V2-PROD' },
  { nombre: 'Veterinario', correo: 'juan.carlos.qa133@sgpmp-test.com', contrasena: 'Test1234!', idActivo: 451, identificador: 'QAJE-G47-V2-VET' },
  { nombre: 'Ingeniero de campo', correo: 'ingeniero@pecuaria.co', contrasena: 'Pruebas12#', idActivo: 452, identificador: 'QAJE-G47-V2-ING' },
];

const evidencia = {};

after(() => {
  cy.writeFile(DESTINO, evidencia);
});

ACTORES.forEach((actor) => {
  describe(`TC-M02-G47 V2 - hallazgos V1 - ${actor.nombre}`, () => {
    it('registra el listado de activos y el refresh tras recargar la pagina', () => {
      const datos = { actor: actor.nombre, inicio_utc: new Date().toISOString() };
      evidencia[actor.nombre] = datos;
      cy.on('uncaught:exception', (err) => {
        (datos.excepciones = datos.excepciones || []).push(err.message);
        return false;
      });

      cy.intercept('GET', '**/activos-biologicos?*').as('listado');
      cy.intercept('GET', '**/activos-biologicos').as('listadoSinQuery');
      cy.intercept('POST', '**/sesiones/refresh').as('refresh');

      // --- Sesion por la interfaz (misma secuencia que el spec V1) ---
      cy.viewport(1600, 1000);
      cy.visit(`${FRONTEND}/login`);
      cy.get('input[type="email"]').should('be.visible').type(actor.correo);
      cy.get('input[autocomplete="current-password"]').type(actor.contrasena, { log: false });
      cy.contains('button[type="submit"]', /ingresar/i).click();
      cy.location('pathname', { timeout: 30000 }).should('not.include', '/login');

      // --- OBS-G47-01/02: listado de activos ---
      cy.get('button.ds-sidebar__item[title="Activos biológicos"]', { timeout: 20000 }).should('be.visible').click();
      cy.location('pathname', { timeout: 20000 }).should('include', '/activos-biologicos');
      cy.contains(/\d+ activo\(s\)/, { timeout: 30000 }).should('be.visible');
      cy.wait(1500);
      cy.get('body').then(($cuerpo) => {
        const texto = $cuerpo.text();
        const contador = texto.match(/(\d+) activo\(s\)/);
        datos.listado_ui = {
          contador_visible: contador ? Number(contador[1]) : null,
          filas_tabla: $cuerpo.find('tbody tr').length,
          texto_pagina_x_de_y: /Página \d+ de \d+/.test(texto),
          boton_siguiente: $cuerpo.find('button').filter((_, b) => /Siguiente/.test(b.textContent)).length,
          boton_anterior: $cuerpo.find('button').filter((_, b) => /Anterior/.test(b.textContent)).length,
          fila_fixture_visible: $cuerpo.find('td').filter((_, td) => td.textContent === actor.identificador).length > 0,
        };
      });
      cy.screenshot(`listado_activos_${actor.idActivo}`, { overwrite: true });

      // --- OBS-G47-03: recarga de pagina tras el login (escenario V1) ---
      cy.visit(`${FRONTEND}/activos-biologicos/${actor.idActivo}`);
      cy.wait(8000);
      cy.location('pathname').then((ruta) => {
        datos.ruta_tras_recarga = ruta;
      });
      cy.get('@refresh.all').then((llamadas) => {
        datos.refresh_tras_recarga = llamadas.map((l) => ({
          http: l.response ? l.response.statusCode : null,
          body: l.response && l.response.body && typeof l.response.body === 'object'
            ? { ...l.response.body, token: l.response.body.token ? '<redactado>' : undefined }
            : (l.response ? String(l.response.body).slice(0, 300) : null),
          cookie_enviada: Boolean(l.request.headers && l.request.headers.cookie
            && String(l.request.headers.cookie).includes('refresh_token')),
        }));
      });
      cy.screenshot(`tras_recarga_${actor.idActivo}`, { overwrite: true });
      cy.then(() => {
        datos.fin_utc = new Date().toISOString();
      });
    });
  });
});
