// ---- Independiente: no usa configuracion comun ni support file. Reporte propio (mochawesome, HTML autocontenido).
//   Una sola vez:  npm i -D mochawesome
//   Ambientes: frontend TEST https://api.inmero.co/sigab-test  |  backend TEST https://api.inmero.co/api-sgpmp-test  (DEV: /sigab-dev y /api-sgpmp-dev). MAIN (https://inmero.co/sigab) NO se prueba.
//   Credenciales y secreto por variable de entorno (PowerShell), nunca en la linea de comandos ni en el repositorio:
//     $env:CYPRESS_email="..."; $env:CYPRESS_password="..."; $env:CYPRESS_sandbox_secret="..."
//   Desde la raiz del repo:
//     npx cypress run --config-file false --spec "<ruta>\\tc_m03_g118_tendencia.cy.ts" --config baseUrl=https://api.inmero.co/sigab-test,supportFile=false,video=false,defaultCommandTimeout=8000,screenshotsFolder=<ruta>\\resultados\\capturas --env api_url=https://api.inmero.co/api-sgpmp-test --reporter mochawesome --reporter-options "reportDir=<ruta>\\resultados,reportFilename=resultado_TC-M03-G118,html=true,json=false,overwrite=true,inlineAssets=true"
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
// TC-M03-G118 - subcaso 3.2 (RF-59): la grafica de tendencia representa solo variables numericas; los estados categoricos solo en tabla.
// SCRIPT SIN EJECUTAR: ambiente no listo; selectores (*) por confirmar. Variables: baseUrl, email, password, ruta_historial.
Cypress.Screenshot.defaults({ blackout: ['input[type="password"]', 'input[type="email"]'], capture: 'viewport' });

describe('G118 - grafica solo numerica', () => {
  it('TC-M03-G118 3.2 variables numericas en grafica; categoricas solo en tabla', () => {
    cy.visit('/login');
    cy.get('input[type="email"]').type(Cypress.env('email'), { log: false });
    cy.get('input[type="password"]').type(Cypress.env('password'), { log: false });
    cy.get('button[type="submit"]').click();
    cy.location('pathname').should('not.include', 'login');
    cy.visit(Cypress.env('ruta_historial') || '/monitoreo/historial');            // (*)
    const numericas = ['TEMPERATURA_AMBIENTAL', 'HUMEDAD_RELATIVA'];
    const categoricas = ['ESTADO_ALIMENTACION', 'ACTIVIDAD_CATEGORICA'];           // (*) variables categoricas del catalogo del ambiente
    numericas.forEach((v) => {
      cy.get('[data-testid="filtro-variable"], select[name="tipo_variable"]').select(v);                      // (*)
      cy.contains('button', /Consultar|Aplicar|Buscar/i).click();
      cy.get('[data-testid="grafica-tendencia"] svg, [data-testid="grafica-tendencia"] canvas').should('exist');   // (*)
      cy.get('[data-testid="tabla-historial"] tbody tr').should('have.length.greaterThan', 0);                  // (*)
    });
    categoricas.forEach((v) => {
      cy.get('[data-testid="filtro-variable"], select[name="tipo_variable"]').select(v);
      cy.contains('button', /Consultar|Aplicar|Buscar/i).click();
      cy.get('[data-testid="tabla-historial"] tbody tr').should('have.length.greaterThan', 0);
      cy.get('[data-testid="grafica-tendencia"] svg path.serie, [data-testid="grafica-tendencia"] canvas').should('not.exist');   // (*) sin serie graficada
    });
    cy.screenshot('TC-M03-G118-3.2-grafica-numerica');
  });
});
