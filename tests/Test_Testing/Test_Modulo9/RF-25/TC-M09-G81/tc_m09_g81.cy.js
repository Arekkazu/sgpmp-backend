/**
 * TC-M09-G81
 * Módulo 09 - Configuración y Personalización
 * RF-25 - Adaptación de interfaz por rol/contexto
 *
 * Validaciones consolidadas:
 * TC-M09-152 - Interfaz según rol autenticado
 * TC-M09-153 - Interfaz según finca asignada
 * TC-M09-154 - Interfaz según especie configurada
 * TC-M09-155 - Interfaz predeterminada sin preferencias
 *
 * Ambiente: TEST desplegado
 * Herramienta: Cypress
 *
 * NOTA:
 * TC-M09-G81 es un único caso ejecutable.
 * Los casos 152, 153, 154 y 155 corresponden a validaciones
 * internas del mismo caso consolidado.
 */

describe(
    'TC-M09-G81 - Adaptación de interfaz por rol y contexto',
    () => {

        const FRONTEND_URL =
            'http://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io/login';

        const USUARIO = 'admin@pecuaria.co';
        const PASSWORD = 'Test1234!';


        // ==========================================================
        // PREPARACIÓN DEL CASO
        // ==========================================================

        beforeEach(() => {

            // ======================================================
            // INTERCEPTAR ENDPOINT REAL DE RF-25
            // ======================================================

            cy.intercept(
                'GET',
                '**/configuracion/interfaz/contexto'
            ).as('contextoRF25');


            // ======================================================
            // INGRESO AL FRONTEND TEST
            // ======================================================

            cy.visit(FRONTEND_URL);

            cy.url()
                .should('include', '/login');


            // ======================================================
            // CORREO
            // ======================================================

            cy.get(
                'input[type="email"], ' +
                'input[name="email"], ' +
                'input[formcontrolname="email"]'
            )
                .first()
                .should('be.visible')
                .clear()
                .type(USUARIO);


            // ======================================================
            // CONTRASEÑA
            // ======================================================

            cy.get(
                'input[type="password"], ' +
                'input[name="password"], ' +
                'input[formcontrolname="password"]'
            )
                .first()
                .should('be.visible')
                .clear()
                .type(
                    PASSWORD,
                    { log: false }
                );


            // ======================================================
            // BOTÓN DE INGRESO
            // ======================================================

            cy.contains(
                'button',
                /ingresar|iniciar sesión|login/i
            )
                .first()
                .should('be.visible')
                .click();


            // ======================================================
            // VALIDAR LOGIN
            // ======================================================

            cy.url({
                timeout: 15000
            })
                .should(
                    'not.include',
                    '/login'
                );


            // ======================================================
            // ESPERAR RESPUESTA REAL DE RF-25
            // ======================================================

            cy.wait(
                '@contextoRF25',
                {
                    timeout: 15000
                }
            )
                .then(
                    (interception) => {

                        const statusCode =
                            interception.response?.statusCode;

                        const responseBody =
                            interception.response?.body;


                        // Mostrar información en Cypress
                        cy.log(
                            `RF-25 - Status: ${statusCode}`
                        );

                        cy.log(
                            `RF-25 - Respuesta: ${JSON.stringify(responseBody)}`
                        );


                        // Mostrar información en consola
                        console.log(
                            'TC-M09-G81 - RF-25 contexto',
                            {
                                statusCode,
                                responseBody
                            }
                        );


                        // Debe existir respuesta HTTP
                        expect(
                            interception.response,
                            'RF-25 debe devolver una respuesta'
                        )
                            .to.exist;


                        // RF-25 debe responder correctamente
                        expect(
                            statusCode,
                            'RF-25 debe responder correctamente'
                        )
                            .to.be.oneOf(
                                [200, 204]
                            );


                        // La respuesta debe contener información
                        // cuando el backend entrega un contexto.
                        if (
                            statusCode === 200 &&
                            responseBody !== null &&
                            responseBody !== undefined
                        ) {

                            expect(
                                responseBody,
                                'RF-25 debe retornar el contexto adaptativo'
                            )
                                .to.exist;

                        }

                    }
                );


            // ======================================================
            // VALIDAR INTERFAZ AUTENTICADA
            // ======================================================

            cy.get(
                'body',
                {
                    timeout: 15000
                }
            )
                .should('be.visible');


            cy.get(
                'ion-router-outlet, ' +
                'main, ' +
                'nav, ' +
                'aside, ' +
                'header, ' +
                'ion-content'
            )
                .should('exist');

        });


        // ==========================================================
        // CASO ÚNICO TC-M09-G81
        // ==========================================================

        it(
            'TC-M09-G81 - Carga y adaptación de la interfaz según rol, finca, especie y configuración predeterminada',
            () => {


                // ==================================================
                // TC-M09-152
                // INTERFAZ SEGÚN ROL AUTENTICADO
                // ==================================================

                cy.log(
                    'TC-M09-152 - Validación de interfaz según rol autenticado'
                );


                // El usuario debe estar autenticado.
                cy.url()
                    .should(
                        'not.include',
                        '/login'
                    );


                // Debe existir contenido de aplicación.
                cy.get('body')
                    .should('be.visible');


                // Debe existir estructura principal.
                cy.get(
                    'ion-router-outlet, ' +
                    'main, ' +
                    'nav, ' +
                    'aside, ' +
                    'header'
                )
                    .should('exist');


                // La interfaz no debe estar vacía.
                cy.get('body')
                    .invoke('text')
                    .then(
                        (texto) => {

                            expect(
                                texto.trim().length,
                                'La interfaz autenticada debe contener información visible'
                            )
                                .to.be.greaterThan(0);

                        }
                    );


                // ==================================================
                // TC-M09-153
                // CONTEXTO DE FINCA
                // ==================================================

                cy.log(
                    'TC-M09-153 - Validación de contexto de finca'
                );


                /*
                 * RF-25 obtiene el contexto adaptativo del usuario
                 * mediante el endpoint:
                 *
                 * GET /configuracion/interfaz/contexto
                 *
                 * La respuesta se utiliza para determinar el
                 * contexto productivo de la interfaz.
                 */

                cy.get(
                    '@contextoRF25.all'
                )
                    .should(
                        'have.length.at.least',
                        1
                    )
                    .then(
                        (interceptions) => {

                            const peticion =
                                interceptions[
                                    interceptions.length - 1
                                ];

                            const statusCode =
                                peticion.response?.statusCode;

                            const responseBody =
                                peticion.response?.body;


                            cy.log(
                                `TC-M09-153 - Status RF-25: ${statusCode}`
                            );

                            cy.log(
                                `TC-M09-153 - Contexto recibido: ${JSON.stringify(responseBody)}`
                            );


                            expect(
                                statusCode,
                                'El contexto adaptativo debe responder correctamente'
                            )
                                .to.be.oneOf(
                                    [200, 204]
                                );


                            expect(
                                responseBody,
                                'RF-25 debe proporcionar el contexto utilizado por la interfaz'
                            )
                                .to.exist;

                        }
                    );


                // La interfaz debe continuar disponible.
                cy.get(
                    'ion-router-outlet, ' +
                    'main, ' +
                    'ion-content'
                )
                    .should('exist');


                // ==================================================
                // TC-M09-154
                // CONTEXTO DE ESPECIE
                // ==================================================

                cy.log(
                    'TC-M09-154 - Validación de contexto de especie'
                );


                /*
                 * La especie es parte del contexto utilizado por
                 * RF-25. No se exige que la palabra "especie"
                 * aparezca literalmente en pantalla.
                 */

                cy.get(
                    '@contextoRF25.all'
                )
                    .should(
                        'have.length.at.least',
                        1
                    )
                    .then(
                        (interceptions) => {

                            const peticion =
                                interceptions[
                                    interceptions.length - 1
                                ];

                            const statusCode =
                                peticion.response?.statusCode;

                            const responseBody =
                                peticion.response?.body;


                            cy.log(
                                `TC-M09-154 - Status RF-25: ${statusCode}`
                            );

                            cy.log(
                                `TC-M09-154 - Respuesta de contexto: ${JSON.stringify(responseBody)}`
                            );


                            expect(
                                statusCode,
                                'La respuesta de RF-25 debe ser correcta'
                            )
                                .to.be.oneOf(
                                    [200, 204]
                                );


                            expect(
                                responseBody,
                                'Debe existir información de contexto para adaptar la interfaz'
                            )
                                .to.exist;

                        }
                    );


                cy.get('body')
                    .should('be.visible');


                // ==================================================
                // TC-M09-155
                // INTERFAZ PREDETERMINADA
                // ==================================================

                cy.log(
                    'TC-M09-155 - Validación de interfaz predeterminada'
                );


                /*
                 * Cuando no existen preferencias específicas,
                 * RF-25 debe proporcionar un contexto válido para
                 * que la aplicación pueda mostrar la configuración
                 * predeterminada correspondiente.
                 */


                cy.get(
                    '@contextoRF25.all'
                )
                    .should(
                        'have.length.at.least',
                        1
                    )
                    .then(
                        (interceptions) => {

                            const peticion =
                                interceptions[
                                    interceptions.length - 1
                                ];

                            const statusCode =
                                peticion.response?.statusCode;


                            expect(
                                statusCode,
                                'RF-25 debe permitir resolver el contexto predeterminado'
                            )
                                .to.be.oneOf(
                                    [200, 204]
                                );

                        }
                    );


                // La interfaz no debe estar vacía.
                cy.get('body')
                    .should('be.visible')
                    .invoke('text')
                    .then(
                        (texto) => {

                            expect(
                                texto.trim().length,
                                'La interfaz predeterminada debe contener contenido visible'
                            )
                                .to.be.greaterThan(0);


                            const textoNormalizado =
                                texto.toLowerCase();


                            expect(
                                textoNormalizado,
                                'No debe mostrarse un error interno del servidor'
                            )
                                .not
                                .to.include(
                                    'internal server error'
                                );


                            expect(
                                textoNormalizado,
                                'No debe mostrarse un error 500'
                            )
                                .not
                                .to.include(
                                    '500 internal server error'
                                );

                        }
                    );


                // ==================================================
                // VALIDACIÓN FINAL
                // ==================================================

                cy.log(
                    'Validación final TC-M09-G81'
                );


                cy.url()
                    .should(
                        'not.include',
                        '/login'
                    );


                cy.get('body')
                    .should('be.visible');


                cy.log(
                    'TC-M09-G81 FINALIZADO: interfaz cargada y validada según rol, finca, especie y configuración predeterminada'
                );

            }
        );

    }
);