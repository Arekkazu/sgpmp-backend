/**
 * TC-M02-G47 / TC-M02-089 - dimension de RENDERIZADO SEGURO (assertions S6 y S7).
 *
 * `test_tc_m02_g47.py` demuestra que el payload se almacena y que la API lo devuelve
 * como dato. Eso no basta: la ficha exige que "al mostrarse en cualquier vista se
 * presenta codificado/escapado, sin XSS almacenado". Esta especificacion comprueba el
 * DOM real de la vista que efectivamente presenta la descripcion, porque la aplicacion
 * la renderiza dinamicamente y el HTML servido por el servidor no contiene el dato.
 *
 * Vista verificada: /activos-biologicos/{id} -> pestana "Historial"
 * (src/biological_assets/components/HistorialSection.tsx, celda `{r.descripcion}`).
 *
 * La navegacion se hace siempre dentro de la SPA (clics reales), nunca con cy.visit
 * despues del login: el access token vive solo en memoria (`tokenStore`) y cualquier
 * recarga de pagina lo perderia.
 *
 * Nunca se navega deliberadamente a evil.test: la peticion se intercepta y se cuenta
 * como fallo si llega a intentarse. Tampoco se desactiva ninguna proteccion.
 *
 * Ejecucion:
 *   npx cypress run --spec "tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G47/verificar_render_tc_m02_g47.cy.js"
 */

const FRONTEND = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';

// Contenido funcional exacto de la ficha TC-M02-089.
const PAYLOAD = '<script>document.location="http://evil.test"</script>';

// Eventos creados por las 3 escrituras oficiales de test_tc_m02_g47.py.
const ACTORES = [
  {
    nombre: 'Productor',
    correo: 'm2m.nuevo@ejemplo.com',
    contrasena: 'Test1234!',
    idActivo: 279,
    identificador: 'QAJE-CREC-OK',
    idEvento: 234,
  },
  {
    nombre: 'Veterinario',
    correo: 'juan.carlos.qa133@sgpmp-test.com',
    contrasena: 'Test1234!',
    idActivo: 311,
    identificador: 'QAJE-CREC-OK-VET',
    idEvento: 235,
  },
  {
    nombre: 'Ingeniero de campo',
    correo: 'ingeniero@pecuaria.co',
    contrasena: 'Pruebas12#',
    idActivo: 312,
    identificador: 'QAJE-CREC-OK-ING',
    idEvento: 236,
  },
];

ACTORES.forEach((actor) => {
  describe(`TC-M02-G47 / TC-M02-089 - renderizado seguro - ${actor.nombre}`, () => {
    it('S6/S7 - la descripcion se muestra como texto escapado y no se ejecuta', () => {
      // Cualquier intento de alcanzar evil.test queda registrado y bloqueado aqui.
      cy.intercept({ hostname: 'evil.test' }, { statusCode: 204, body: '' }).as('evil');

      // Un XSS que se ejecutara provocaria una navegacion cross-origin y, con ella, una
      // excepcion no capturada. Se recoge en vez de silenciarse para poder afirmar que
      // no hubo ninguna.
      const excepciones = [];
      cy.on('uncaught:exception', (err) => {
        excepciones.push(err.message);
        return false;
      });

      // --- Sesion del actor, por la interfaz igual que lo haria una persona ---
      cy.viewport(1600, 1000);
      cy.visit(`${FRONTEND}/login`);
      cy.get('input[type="email"]').should('be.visible').type(actor.correo);
      cy.get('input[autocomplete="current-password"]').type(actor.contrasena, { log: false });
      cy.contains('button[type="submit"]', /ingresar/i).click();
      cy.location('pathname', { timeout: 30000 }).should('not.include', '/login');

      // --- Navegacion dentro de la SPA hasta el activo del actor ---
      // Con el viewport de escritorio (>= 1024px) la barra lateral queda anclada y
      // visible, asi que la entrada del modulo se pulsa directamente.
      cy.get('button.ds-sidebar__item[title="Activos biológicos"]', { timeout: 20000 })
        .should('be.visible')
        .click();
      cy.location('pathname', { timeout: 20000 }).should('include', '/activos-biologicos');

      // Se abre el activo pulsando su fila. El listado (RegistryView) no expone control
      // de paginacion y solo muestra la primera pagina del backend, asi que un activo
      // legitimo situado en una pagina posterior no tiene fila que pulsar. En ese caso
      // se navega por el mismo router de la SPA y a la misma ruta que empuja la propia
      // vista (`history.push('/activos-biologicos/:id')`), sin recargar la pagina y sin
      // tocar ninguna proteccion. Ver observacion OBS-G47-02 del informe.
      cy.get('body', { timeout: 30000 }).then(($cuerpo) => {
        const fila = $cuerpo.find('td').filter((_, td) => td.textContent === actor.identificador);
        if (fila.length) {
          cy.wrap(fila.first()).click();
        } else {
          cy.window().then((win) => {
            win.history.pushState({}, '', `/activos-biologicos/${actor.idActivo}`);
            win.dispatchEvent(new win.PopStateEvent('popstate'));
          });
        }
      });
      cy.location('pathname', { timeout: 20000 }).should('include', `/activos-biologicos/${actor.idActivo}`);

      cy.contains('button', 'Historial').click();

      // La celda que realmente presenta el dato. A12: su origen esta confirmado porque
      // la fila procede del historial de este activo y contiene el evento oficial.
      cy.contains('td', 'evil.test', { timeout: 30000 })
        .should('be.visible')
        .then(($celda) => {
          const celda = $celda[0];

          // S7 - el contenido se ve completo y literal, tratado como texto.
          expect(celda.textContent, 'texto visible en la celda').to.equal(PAYLOAD);

          // S6 - no se materializo ningun elemento a partir de la descripcion.
          expect(celda.querySelector('script'), 'elemento <script> dentro de la celda').to.equal(null);
          expect(celda.children.length, 'nodos hijo generados por el payload').to.equal(0);

          // El marcado quedo codificado: los delimitadores viajan como entidades HTML.
          expect(celda.innerHTML, 'innerHTML de la celda').to.contain('&lt;script&gt;');
          expect(celda.innerHTML, 'innerHTML de la celda').to.not.contain('<script>');
        });

      // Evidencia visual minima: una sola captura, la del Productor, que muestra el
      // payload presentado como texto dentro de la tabla del historial.
      if (actor.nombre === 'Productor') {
        cy.screenshot('render_seguro_historial_productor', { overwrite: true });
      }

      // S6 - en todo el documento no existe ningun script procedente del payload.
      cy.document().then((doc) => {
        const contaminados = Array.from(doc.querySelectorAll('script')).filter(
          (s) => (s.textContent || '').includes('evil.test') || (s.src || '').includes('evil.test'),
        );
        expect(contaminados.length, 'scripts creados a partir del payload').to.equal(0);
      });

      // No hubo navegacion causada por el payload: seguimos en la vista del activo.
      cy.location('hostname').should('eq', new URL(FRONTEND).hostname);
      cy.location('pathname').should('include', `/activos-biologicos/${actor.idActivo}`);

      // Ninguna peticion salio hacia evil.test.
      cy.get('@evil.all').should('have.length', 0);

      // La vista sigue operativa tras mostrar el contenido inyectado.
      cy.contains('button', 'Ficha integral').click();
      cy.contains('button', 'Historial').click();
      cy.contains('td', 'evil.test').should('be.visible');

      cy.then(() => {
        expect(excepciones, 'excepciones no capturadas durante el renderizado').to.deep.equal([]);
      });
    });
  });
});
