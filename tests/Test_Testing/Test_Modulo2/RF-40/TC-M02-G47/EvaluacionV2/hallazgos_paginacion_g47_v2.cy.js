/**
 * TC-M02-G47 V2 - reevaluacion dirigida de OBS-G47-01 (V1 §10) / OBS-G47-02 (spec V1):
 * "el listado de activos solo muestra la primera pagina, sin control de paginacion".
 *
 * `hallazgos_g47_v2.cy.js` registro que el control ahora se muestra. Este spec comprueba
 * su COMPORTAMIENTO con el Productor (unico actor con mas de una pagina, 23 activos /
 * 2 paginas por API): pulsar "Siguiente" debe mostrar la pagina 2 con los registros
 * restantes, y "Anterior" volver a la pagina 1.
 *
 * Solo lectura: login por la interfaz y navegacion. No escribe datos de dominio.
 */

const FRONTEND = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const DESTINO = 'tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G47/EvaluacionV2/Resultados/hallazgos_paginacion_v2.json';

describe('TC-M02-G47 V2 - OBS-G47-01/02 - paginacion del listado de activos (Productor)', () => {
  it('Siguiente muestra la pagina 2 y Anterior vuelve a la pagina 1', () => {
    const datos = { inicio_utc: new Date().toISOString() };
    cy.intercept('GET', '**/activos-biologicos*').as('listado');

    cy.viewport(1600, 1000);
    cy.visit(`${FRONTEND}/login`);
    cy.get('input[type="email"]').should('be.visible').type('m2m.nuevo@ejemplo.com');
    cy.get('input[autocomplete="current-password"]').type('Test1234!', { log: false });
    cy.contains('button[type="submit"]', /ingresar/i).click();
    cy.location('pathname', { timeout: 30000 }).should('not.include', '/login');

    cy.get('button.ds-sidebar__item[title="Activos biológicos"]', { timeout: 20000 }).should('be.visible').click();
    cy.contains(/Página 1 de \d+/, { timeout: 30000 }).scrollIntoView().should('be.visible').invoke('text').then((t) => {
      datos.pagina_inicial = t.trim();
    });
    cy.get('tbody tr').then(($f) => {
      datos.filas_pagina_1 = $f.length;
      datos.primera_fila_pagina_1 = $f.first().text().slice(0, 80);
    });

    cy.contains('button', 'Siguiente').scrollIntoView().should('not.be.disabled').click();
    cy.contains(/Página 2 de \d+/, { timeout: 30000 }).scrollIntoView().should('be.visible').invoke('text').then((t) => {
      datos.pagina_tras_siguiente = t.trim();
    });
    cy.get('tbody tr').should('have.length.greaterThan', 0).then(($f) => {
      datos.filas_pagina_2 = $f.length;
      datos.primera_fila_pagina_2 = $f.first().text().slice(0, 80);
    });
    cy.screenshot('listado_productor_pagina_2', { overwrite: true });

    cy.contains('button', 'Anterior').scrollIntoView().should('not.be.disabled').click();
    cy.contains(/Página 1 de \d+/, { timeout: 30000 }).scrollIntoView().should('be.visible');
    cy.get('@listado.all').then((llamadas) => {
      datos.peticiones_listado = llamadas.map((l) => ({
        url: l.request.url.replace(/^https?:\/\/[^/]+/, ''),
        http: l.response ? l.response.statusCode : null,
      }));
    });

    cy.then(() => {
      expect(datos.primera_fila_pagina_2, 'la pagina 2 muestra registros distintos').to.not.equal(datos.primera_fila_pagina_1);
      datos.fin_utc = new Date().toISOString();
      cy.writeFile(DESTINO, datos);
    });
  });
});
