// ---- Independiente: no usa configuracion comun ni support file. Reporte propio (mochawesome, HTML autocontenido).
//   Una sola vez:  npm i -D mochawesome
//   Ambientes: frontend TEST https://api.inmero.co/sigab-test  |  backend TEST https://api.inmero.co/api-sgpmp-test  (DEV: /sigab-dev y /api-sgpmp-dev). MAIN (https://inmero.co/sigab) NO se prueba.
//   Credenciales y secreto por variable de entorno (PowerShell), nunca en la linea de comandos ni en el repositorio:
//     $env:CYPRESS_email="..."; $env:CYPRESS_password="..."; $env:CYPRESS_sandbox_secret="..."
//   Desde la raiz del repo:
//     npx cypress run --config-file false --spec "<ruta>\\tc_m03_g116_sin_registros.cy.ts" --config baseUrl=https://api.inmero.co/sigab-test,supportFile=false,video=false,defaultCommandTimeout=8000,screenshotsFolder=<ruta>\\resultados\\capturas --env api_url=https://api.inmero.co/api-sgpmp-test --reporter mochawesome --reporter-options "reportDir=<ruta>\\resultados,reportFilename=resultado_TC-M03-G116,html=true,json=false,overwrite=true,inlineAssets=true"
// ---- Sandbox transaccional (metodologia de regresion): las llamadas que hace la interfaz al backend viajan con X-Test-Run-Id y X-Sandbox-Secret
//      (cy.intercept) y al terminar se hace DELETE /test-control/runs/{run_id} (rollback). Este caso solo LEE el historial; el sandbox aisla ademas el login.
const API_BACK = Cypress.env('api_url') || 'https://api.inmero.co/api-sgpmp-test';
const SANDBOX_SECRET = Cypress.env('sandbox_secret');
const RUN_ID = `test-cy-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
beforeEach(() => {
  if (!SANDBOX_SECRET) { cy.log('SIN sandbox: falta CYPRESS_sandbox_secret; las llamadas de la interfaz no quedan aisladas'); return; }
  cy.intercept(`${API_BACK}/**`, (req) => { req.headers['X-Test-Run-Id'] = RUN_ID; req.headers['X-Sandbox-Secret'] = SANDBOX_SECRET; });
});
after(() => {
  if (!SANDBOX_SECRET) { return; }
  cy.request({ method: 'DELETE', url: `${API_BACK}/test-control/runs/${RUN_ID}`, headers: { 'X-Test-Run-Id': RUN_ID, 'X-Sandbox-Secret': SANDBOX_SECRET }, failOnStatusCode: false });
});
// TC-M03-G116 - subcaso 1.2 (RF-59): sin resultados -> la interfaz muestra "No se encontraron registros para los filtros seleccionados" y sugiere ampliar el rango.
// SCRIPT SIN EJECUTAR: ambiente no listo; selectores (*) por confirmar con el frontend. Variables: baseUrl, email, password, ruta_historial (def. /monitoreo/historial (*)).
Cypress.Screenshot.defaults({ blackout: ['input[type="password"]', 'input[type="email"]'], capture: 'viewport' });

describe('G116 - historial sin registros', () => {
  it('TC-M03-G116 1.2 mensaje de vacio y sugerencia de ampliar el rango', () => {
    cy.visit('/login');
    cy.get('input[type="email"]').type(Cypress.env('email'), { log: false });
    cy.get('input[type="password"]').type(Cypress.env('password'), { log: false });
    cy.get('button[type="submit"]').click();
    cy.location('pathname').should('not.include', 'login');
    cy.intercept('GET', '**/iot/monitoreo/historial*').as('historial');
    cy.visit(Cypress.env('ruta_historial') || '/monitoreo/historial');            // (*)
    // rango sin datos: un dia lejano en el pasado
    cy.get('input[name="fecha_inicio"], [data-testid="filtro-fecha-inicio"]').clear().type('2000-01-01');    // (*)
    cy.get('input[name="fecha_fin"], [data-testid="filtro-fecha-fin"]').clear().type('2000-01-02');          // (*)
    cy.contains('button', /Consultar|Aplicar|Buscar/i).click();                                              // (*)
    cy.wait('@historial').its('response.body.total').should('eq', 0);
    cy.contains('No se encontraron registros para los filtros seleccionados').should('be.visible');
    cy.contains(/ampl(i|í)e el rango|ampliar el rango/i).should('be.visible');
    cy.screenshot('TC-M03-G116-1.2-sin-registros');
  });
});
