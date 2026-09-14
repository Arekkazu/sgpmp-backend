/**
 * Histórico de tc_m09_g95.cy.js (pre-rev1 DEV).
 * Conservado para no perder el caso que corrió contra TEST y quedó Rechazado.
 * No es spec de Cypress (extensión .js, fuera del patrón *.cy.js).
 *
 * Limitaciones del histórico:
 * - baseUrl TEST vía cy.visit('/login')
 * - usuario productor@pecuaria.co
 * - exigía [draggable="true"] (el producto DEV usa clic catálogo + clic celda)
 * - G95-dashboard.txt muestra /dashboard con el formulario de login
 */
describe('TC-M09-G95 - Personalización del dashboard con widgets válidos', () => {
  const email = Cypress.env('TEST_EMAIL') || 'productor@pecuaria.co';
  const password = Cypress.env('TEST_PASSWORD') || 'Test1234!';

  const evidenceDir =
    'tests/Test_Testing/Test_Modulo9/RF-28/TC-M09-G95/Resultados';

  beforeEach(() => {
    cy.visit('/login');
  });

  it('TC-M09-180 - Verifica disponibilidad de widgets y personalización del dashboard', () => {
    cy.get('input[type="email"]', { timeout: 15000 })
      .should('be.visible')
      .clear()
      .type(email);

    cy.get('input[type="password"]', { timeout: 15000 })
      .should('be.visible')
      .clear()
      .type(password);

    cy.get('button[type="submit"]', { timeout: 15000 })
      .should('be.visible')
      .click();

    cy.url({ timeout: 15000 }).should('include', '/dashboard');

    cy.document().then((doc) => {
      const bodyText = doc.body.innerText;

      cy.writeFile(
        `${evidenceDir}/G95-dashboard.txt`,
        [
          'TC-M09-G95 - TC-M09-180',
          'RF-28 - Personalización del dashboard',
          '',
          `URL: ${doc.location.href}`,
          '',
          'Contenido visible del dashboard:',
          bodyText
        ].join('\n')
      );
    });

    cy.get('body').then(($body) => {
      const text = $body.text().toLowerCase();

      const widgetKeywords = [
        'widget',
        'usuarios activos',
        'roles configurados',
        'eventos de auditoría',
        'mi último acceso'
      ];

      const detectedWidgets = widgetKeywords.filter((keyword) =>
        text.includes(keyword.toLowerCase())
      );

      cy.writeFile(
        `${evidenceDir}/G95-widgets-detectados.txt`,
        [
          'TC-M09-G95 - Detección de widgets',
          '',
          `Palabras/elementos detectados: ${
            detectedWidgets.length
              ? detectedWidgets.join(', ')
              : 'ninguno'
          }`,
          '',
          'Nota:',
          'La presencia de una tarjeta KPI no implica que exista un widget personalizable.'
        ].join('\n')
      );
    });

    cy.get('body').then(($body) => {
      const buttons = [...$body.find('button')].map(
        (button) => button.innerText.trim()
      );

      const inputs = [...$body.find('input')].map(
        (input) => ({
          type: input.type,
          ariaLabel: input.getAttribute('aria-label'),
          placeholder: input.getAttribute('placeholder')
        })
      );

      const draggableElements = $body.find(
        '[draggable="true"], [data-draggable="true"]'
      ).length;

      const personalizationText = $body.text().match(
        /personalizar|personalización|configurar dashboard|editar dashboard|widgets?/gi
      ) || [];

      cy.writeFile(
        `${evidenceDir}/G95-personalizacion.txt`,
        [
          'TC-M09-G95 - Mecanismos de personalización',
          '',
          `Botones visibles: ${
            buttons.length ? buttons.join(' | ') : 'ninguno'
          }`,
          '',
          `Inputs visibles: ${JSON.stringify(inputs, null, 2)}`,
          '',
          `Elementos draggable encontrados: ${draggableElements}`,
          '',
          `Texto relacionado con personalización: ${
            personalizationText.length
              ? personalizationText.join(', ')
              : 'ninguno'
          }`
        ].join('\n')
      );

      if (draggableElements === 0) {
        cy.writeFile(
          `${evidenceDir}/G95-resultado.txt`,
          [
            'RESULTADO: BLOQUEADO / NO IMPLEMENTADO',
            '',
            'TC-M09-180 requiere personalización del dashboard mediante widgets',
            'válidos y distribución en una grilla 4x3.',
            '',
            'En la interfaz actual no se identificaron elementos draggable',
            'ni un mecanismo visible de personalización del dashboard.',
            '',
            'Las tarjetas KPI visibles no se consideran widgets personalizables',
            'porque no existe evidencia de selección, arrastre, colocación o',
            'persistencia de su distribución.',
            '',
            'No se fuerza ni simula la funcionalidad para hacer pasar el caso.',
            'Debe verificarse con Desarrollo la implementación de RF-28.'
          ].join('\n')
        );

        throw new Error(
          'TC-M09-G95 / TC-M09-180: BLOQUEADO. No se identificó un mecanismo real de personalización mediante widgets en el dashboard.'
        );
      }
    });
  });
});
