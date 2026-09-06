/**
 * TC-M09-G82
 * Módulo 09 - Configuración y Personalización
 * RF-25 - Adaptación de interfaz por rol/contexto
 *
 * Validaciones consolidadas:
 * TC-M09-156 - Impedir acceso directo mediante URL a módulo no autorizado
 * TC-M09-157 - Impedir acceso a información de una finca no asignada
 *
 * Herramienta:
 * Cypress + validación API
 *
 * Ambiente:
 * TEST desplegado
 */

describe(
    'TC-M09-G82 - Restricción de acceso a módulos y fincas no autorizados',
    () => {

        // ==========================================================
        // CONFIGURACIÓN
        // ==========================================================

        const FRONTEND_URL =
            'http://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';

        const LOGIN_URL =
            `${FRONTEND_URL}/login`;

        const BACKEND_URL =
            'http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io';

        const API_BASE =
            `${BACKEND_URL}/api-sgpmp-test`;

        const USUARIO =
            'm2m.nuevo@ejemplo.com';

        const PASSWORD =
            'Test1234!';

        const FINCA_NO_ASIGNADA =
            999;


        // ==========================================================
        // PREPARACIÓN
        // ==========================================================

        beforeEach(() => {

            // ------------------------------------------------------
            // Interceptar login
            // ------------------------------------------------------

            cy.intercept(
                'POST',
                '**/sesiones/**'
            ).as('login');


            // ------------------------------------------------------
            // Abrir login
            // ------------------------------------------------------

            cy.visit(LOGIN_URL);

            cy.url()
                .should('include', '/login');


            // ------------------------------------------------------
            // Correo
            // ------------------------------------------------------

            cy.get(
                'input[type="email"], ' +
                'input[name="email"], ' +
                'input[formcontrolname="email"]'
            )
                .first()
                .should('be.visible')
                .clear()
                .type(USUARIO);


            // ------------------------------------------------------
            // Contraseña
            // ------------------------------------------------------

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
                    {
                        log: false
                    }
                );


            // ------------------------------------------------------
            // Ingresar
            // ------------------------------------------------------

            cy.contains(
                'button',
                /ingresar|iniciar sesión|login/i
            )
                .first()
                .should('be.visible')
                .click();


            // ------------------------------------------------------
            // VALIDAR RESPUESTA REAL DEL LOGIN
            // ------------------------------------------------------

            cy.wait(
                '@login',
                {
                    timeout: 15000
                }
            )
                .then(
                    (interception) => {

                        const status =
                            interception.response?.statusCode;

                        const body =
                            interception.response?.body;


                        cy.log(
                            `G82 - Login HTTP: ${status}`
                        );

                        cy.log(
                            `G82 - Respuesta login: ${JSON.stringify(body)}`
                        );


                        console.log(
                            'TC-M09-G82 - Respuesta login',
                            {
                                status,
                                body
                            }
                        );


                        expect(
                            interception.response,
                            'El backend debe responder al intento de autenticación'
                        )
                            .to.exist;


                        expect(
                            status,
                            'El usuario debe autenticarse correctamente'
                        )
                            .to.equal(200);

                    }
                );


            // ------------------------------------------------------
            // Validar salida del login
            // ------------------------------------------------------

            cy.url({
                timeout: 15000
            })
                .should(
                    'not.include',
                    '/login'
                );


            cy.get('body')
                .should('be.visible');

        });


        // ==========================================================
        // CASO ÚNICO G82
        // ==========================================================

        it(
            'TC-M09-G82 - Debe impedir acceso a módulos y fincas no autorizados',
            () => {


                // ==================================================
                // TC-M09-156
                // ==================================================

                cy.log(
                    'TC-M09-156 - Acceso directo a módulo no autorizado'
                );


                /*
                 * Endpoint protegido de configuración.
                 *
                 * Se utiliza como recurso para comprobar
                 * autorización server-side.
                 */

                const MODULO_RESTRINGIDO =
                    '/configuracion/umbrales';


                cy.request({
                    method: 'GET',

                    url:
                        `${API_BASE}${MODULO_RESTRINGIDO}`,

                    failOnStatusCode: false
                })
                    .then(
                        (response) => {

                            cy.log(
                                `TC-M09-156 - HTTP Status: ${response.status}`
                            );

                            cy.log(
                                `TC-M09-156 - Respuesta: ${JSON.stringify(response.body)}`
                            );


                            /*
                             * El recurso no debe quedar expuesto
                             * sin autorización.
                             */

                            expect(
                                response.status,
                                'El servidor no debe entregar el recurso protegido sin autorización'
                            )
                                .to.be.oneOf(
                                    [401, 403]
                                );

                        }
                    );


                // ==================================================
                // Validación de navegación directa
                // ==================================================

                cy.visit(
                    `${FRONTEND_URL}${MODULO_RESTRINGIDO}`,
                    {
                        failOnStatusCode: false
                    }
                );


                cy.get('body')
                    .should('be.visible')
                    .invoke('text')
                    .then(
                        (texto) => {

                            const textoNormalizado =
                                texto
                                    .toLowerCase()
                                    .trim();


                            cy.log(
                                `TC-M09-156 - Texto visible: ${textoNormalizado.substring(0, 500)}`
                            );

                        }
                    );


                // ==================================================
                // TC-M09-157
                // ==================================================

                cy.log(
                    'TC-M09-157 - Acceso a finca no asignada'
                );


                /*
                 * Se autentica nuevamente mediante API para obtener
                 * un token válido para la consulta protegida.
                 */

                cy.request({
                    method: 'POST',

                    url:
                        `${API_BASE}/sesiones/`,

                    body: {
                        correo:
                            USUARIO,

                        contrasena:
                            PASSWORD
                    },

                    failOnStatusCode: false
                })
                    .then(
                        (loginResponse) => {

                            cy.log(
                                `TC-M09-157 - Login API: ${loginResponse.status}`
                            );


                            expect(
                                loginResponse.status,
                                'El usuario debe autenticarse para realizar la prueba de autorización'
                            )
                                .to.equal(200);


                            const token =
                                loginResponse.body?.token ||
                                loginResponse.body?.access_token ||
                                loginResponse.body?.accessToken;


                            expect(
                                token,
                                'La autenticación debe proporcionar un token'
                            )
                                .to.exist;


                            // --------------------------------------------------
                            // Consultar finca no asignada
                            // --------------------------------------------------

                            cy.request({
                                method: 'GET',

                                url:
                                    `${API_BASE}/configuracion/fincas/${FINCA_NO_ASIGNADA}`,

                                headers: {
                                    Authorization:
                                        `Bearer ${token}`
                                },

                                failOnStatusCode: false
                            })
                                .then(
                                    (fincaResponse) => {

                                        cy.log(
                                            `TC-M09-157 - HTTP Status: ${fincaResponse.status}`
                                        );

                                        cy.log(
                                            `TC-M09-157 - Respuesta: ${JSON.stringify(fincaResponse.body)}`
                                        );


                                        console.log(
                                            'TC-M09-G82 - Consulta finca no asignada',
                                            {
                                                status:
                                                    fincaResponse.status,

                                                body:
                                                    fincaResponse.body
                                            }
                                        );


                                        // --------------------------------------------------
                                        // Validación de autorización
                                        // --------------------------------------------------

                                        expect(
                                            fincaResponse.status,
                                            'El servidor debe rechazar el acceso a la finca no asignada'
                                        )
                                            .to.be.oneOf(
                                                [401, 403]
                                            );


                                        expect(
                                            fincaResponse.status,
                                            'La finca no autorizada no debe entregar información'
                                        )
                                            .not
                                            .to.equal(200);

                                    }
                                );

                        }
                    );


                // ==================================================
                // FINAL
                // ==================================================

                cy.log(
                    'TC-M09-G82 FINALIZADO'
                );

            }
        );

    }
);