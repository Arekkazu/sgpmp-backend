// ---- Independiente: no usa configuracion comun ni support file. Reporte propio (mochawesome, HTML autocontenido).
//   Una sola vez:  npm i -D mochawesome
//   Ambientes: frontend TEST https://api.inmero.co/sigab-test  |  backend TEST https://api.inmero.co/api-sgpmp-test  (DEV: /sigab-dev y /api-sgpmp-dev). MAIN (https://inmero.co/sigab) NO se prueba.
//   Credenciales y secreto por variable de entorno (PowerShell), nunca en la linea de comandos ni en el repositorio:
//     $env:CYPRESS_email="..."; $env:CYPRESS_password="..."; $env:CYPRESS_sandbox_secret="..."
//   Desde la raiz del repo:
//     npx cypress run --config-file false --spec "<ruta>\\tc_m03_g121_vacios_grafica.cy.ts" --config baseUrl=https://api.inmero.co/sigab-test,supportFile=false,video=false,defaultCommandTimeout=8000,screenshotsFolder=<ruta>\\resultados\\capturas --env api_url=https://api.inmero.co/api-sgpmp-test --reporter mochawesome --reporter-options "reportDir=<ruta>\\resultados,reportFilename=resultado_TC-M03-G121,html=true,json=false,overwrite=true,inlineAssets=true"
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
// TC-M03-G121 - subcasos 1.2 y 2.2 (RF-59): un vacio de datos se representa como linea discontinua o zona sombreada con la etiqueta "Sin datos".
// 1.2 es un FALLO ESPERADO en la grafica actual (hallazgo): el test esta escrito segun el RF.
// SCRIPT SIN EJECUTAR: ambiente no listo; selectores (*) por confirmar. Variables: baseUrl, email, password, ruta_historial, sensor_con_vacio (rango con vacio conocido: fecha_ini_vacio / fecha_fin_vacio).
Cypress.Screenshot.defaults({ blackout: ['input[type="password"]', 'input[type="email"]'], capture: 'viewport' });

function abrirHistorialConVacio() {
  cy.visit('/login');
  cy.get('input[type="email"]').type(Cypress.env('email'), { log: false });
  cy.get('input[type="password"]').type(Cypress.env('password'), { log: false });
  cy.get('button[type="submit"]').click();
  cy.location('pathname').should('not.include', 'login');
  cy.visit(Cypress.env('ruta_historial') || '/monitoreo/historial');                 // (*)
  cy.get('input[name="fecha_inicio"], [data-testid="filtro-fecha-inicio"]').clear().type(Cypress.env('fecha_ini_vacio') || '2026-09-01');   // (*)
  cy.get('input[name="fecha_fin"], [data-testid="filtro-fecha-fin"]').clear().type(Cypress.env('fecha_fin_vacio') || '2026-09-30');         // (*)
  cy.contains('button', /Consultar|Aplicar|Buscar/i).click();
}

describe('G121 - vacios en la grafica', () => {
  it('TC-M03-G121 1.2 el vacio se muestra como linea discontinua o zona sombreada con etiqueta "Sin datos"', () => {
    abrirHistorialConVacio();
    cy.get('[data-testid="grafica-tendencia"]').should('be.visible');                                          // (*)
    cy.get('[data-testid="grafica-tendencia"] [stroke-dasharray], [data-testid="grafica-tendencia"] .zona-sin-datos').should('exist');   // (*)
    cy.get('[data-testid="grafica-tendencia"]').contains('Sin datos').should('be.visible');
    cy.screenshot('TC-M03-G121-1.2-vacio');
  });

  it('TC-M03-G121 2.2 la grafica muestra la discontinuidad del periodo sin datos', () => {
    abrirHistorialConVacio();
    // la serie no debe unir con una linea continua los puntos a ambos lados del vacio: debe haber >= 2 segmentos
    cy.get('[data-testid="grafica-tendencia"] svg path.serie').should('have.length.greaterThan', 1);          // (*)
    cy.screenshot('TC-M03-G121-2.2-discontinuidad');
  });
});
