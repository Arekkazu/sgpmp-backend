// ---- Independiente: no usa configuracion comun ni support file. Reporte propio (mochawesome, HTML autocontenido).
//   Una sola vez:  npm i -D mochawesome
//   Ambientes: frontend TEST https://api.inmero.co/sigab-test  |  backend TEST https://api.inmero.co/api-sgpmp-test  (DEV: /sigab-dev y /api-sgpmp-dev). MAIN (https://inmero.co/sigab) NO se prueba.
//   Credenciales y secreto por variable de entorno (PowerShell), nunca en la linea de comandos ni en el repositorio:
//     $env:CYPRESS_email="..."; $env:CYPRESS_password="..."; $env:CYPRESS_sandbox_secret="..."
//   Desde la raiz del repo:
//     npx cypress run --config-file false --spec "<ruta>\\tc_m03_g131_flujo_productor.cy.ts" --config baseUrl=https://api.inmero.co/sigab-test,supportFile=false,video=false,defaultCommandTimeout=8000,screenshotsFolder=<ruta>\\resultados\\capturas --env api_url=https://api.inmero.co/api-sgpmp-test --reporter mochawesome --reporter-options "reportDir=<ruta>\\resultados,reportFilename=resultado_TC-M03-G131,html=true,json=false,overwrite=true,inlineAssets=true"
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
// TC-M03-G131 - subcaso 1.1 (RF-59): el Productor aplica un filtro de fecha y variable, interpreta la tendencia e identifica un vacio de datos, sin asistencia tecnica.
// NOTA: la VALORACION de usabilidad (que una persona lo logre sin ayuda) es inherentemente humana y sigue siendo una sesion con un Productor real.
// Este script automatiza la parte tecnica verificable del flujo: accesibilidad desde la sesion del Productor, numero de pasos/clics, tiempo total y presencia
// de los elementos que permiten interpretar la tendencia y el vacio; deja capturas y tiempos como evidencia para la sesion. SCRIPT SIN EJECUTAR; selectores (*) por confirmar.
// Variables: baseUrl, email_productor, password_productor, ruta_historial.
Cypress.Screenshot.defaults({ blackout: ['input[type="password"]', 'input[type="email"]'], capture: 'viewport' });

describe('G131 - flujo del Productor (apoyo a la prueba de usabilidad)', () => {
  it('TC-M03-G131 1.1 filtrar por fecha y variable, ver tendencia e identificar el vacio en pocos pasos', () => {
    const t0 = Date.now(); let clics = 0;
    cy.visit('/login');
    cy.get('input[type="email"]').type(Cypress.env('email_productor'), { log: false });
    cy.get('input[type="password"]').type(Cypress.env('password_productor'), { log: false });
    cy.get('button[type="submit"]').click();
    cy.location('pathname').should('not.include', 'login');
    cy.visit(Cypress.env('ruta_historial') || '/monitoreo/historial');                              // (*)
    cy.get('[data-testid="filtro-variable"], select[name="tipo_variable"]').should('be.visible').select('TEMPERATURA_AMBIENTAL').then(() => { clics++; });   // (*)
    cy.get('input[name="fecha_inicio"], [data-testid="filtro-fecha-inicio"]').clear().type('2026-09-01').then(() => { clics++; });
    cy.get('input[name="fecha_fin"], [data-testid="filtro-fecha-fin"]').clear().type('2026-09-30').then(() => { clics++; });
    cy.contains('button', /Consultar|Aplicar|Buscar/i).click().then(() => { clics++; });
    cy.get('[data-testid="grafica-tendencia"]').should('be.visible');                                 // tendencia visible
    cy.get('[data-testid="grafica-tendencia"]').contains(/Sin datos/i).should('be.visible');          // vacio identificable (*)
    cy.get('[data-testid="leyenda-grafica"], [data-testid="grafica-tendencia"] [aria-label]').should('exist');   // leyenda/ejes interpretables
    cy.then(() => {
      const dt = (Date.now() - t0) / 1000;
      cy.log(`pasos (clics): ${clics} | tiempo total: ${dt.toFixed(1)} s`);
      expect(clics, 'pasos para completar la tarea').to.be.at.most(8);
      cy.writeFile('tests/Test_Testing/Test_Modulo3/RF-59/TC-M03-G131/Resultados/usabilidad_apoyo.json', { clics, segundos: dt, fecha: new Date().toISOString() });
    });
    cy.screenshot('TC-M03-G131-1.1-flujo-productor');
  });
});
