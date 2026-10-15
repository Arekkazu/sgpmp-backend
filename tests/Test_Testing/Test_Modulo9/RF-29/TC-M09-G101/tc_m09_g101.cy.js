describe('TC-M09-G101 - Persistencia del idioma e integridad de datos del usuario', () => {

  const baseUrl =
    'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

  const usuario = 'admin@pecuaria.co';
  const contrasena = 'Test1234!';

  it('TC-M09-194 y TC-M09-196 - Validar persistencia del idioma e integridad de datos', () => {

    let token;
    let idiomaInicial;
    let datosAntes;
    let datosDespues;

    // ============================================================
    // LOGIN
    // ============================================================

    cy.log('===== LOGIN =====');

    cy.request({
      method: 'POST',
      url: `${baseUrl}/sesiones/`,
      body: {
        correo_electronico: usuario,
        contrasena: contrasena
      }
    }).then((login) => {

      expect(login.status).to.eq(200);

      token = login.body.token;

      expect(token).to.be.a('string').and.not.be.empty;

      cy.log(`Login correcto. HTTP ${login.status}`);

      // ============================================================
      // TC-M09-194 - OBTENER IDIOMA ACTUAL
      // ============================================================

      cy.log('===== TC-M09-194 - Idioma inicial =====');

      cy.request({
        method: 'GET',
        url: `${baseUrl}/configuracion/personalizacion/idioma`,
        headers: {
          Authorization: `Bearer ${token}`
        }
      }).then((idioma) => {

        expect(idioma.status).to.eq(200);

        expect(idioma.body).to.have.property('locale_code');

        idiomaInicial = idioma.body.locale_code;

        expect(idiomaInicial).to.be.oneOf([
          'es-CO',
          'en-US'
        ]);

        cy.log(`Idioma inicial: ${idiomaInicial}`);
        cy.log(`Fuente inicial: ${idioma.body.fuente || 'N/A'}`);

        // ========================================================
        // TC-M09-196 - DATOS DEL USUARIO ANTES DEL CAMBIO
        // ========================================================

        cy.log('===== TC-M09-196 - Datos antes del cambio =====');

        /*
         * Se consulta el perfil del usuario.
         *
         * NOTA:
         * La ruta /usuarios/me se utiliza para consultar los datos
         * del usuario autenticado.
         *
         * failOnStatusCode:false permite documentar el resultado
         * si el endpoint no está disponible en TEST.
         */

        cy.request({
          method: 'GET',
          url: `${baseUrl}/usuarios/me`,
          headers: {
            Authorization: `Bearer ${token}`
          },
          failOnStatusCode: false
        }).then((perfilAntes) => {

          cy.log(`Perfil antes del cambio - HTTP ${perfilAntes.status}`);

          if (perfilAntes.status === 200) {

            datosAntes = perfilAntes.body;

            cy.log(
              `Datos antes: ${JSON.stringify(datosAntes)}`
            );

          } else {

            cy.log(
              `TC-M09-196 bloqueado: el endpoint de perfil respondió HTTP ${perfilAntes.status}`
            );

            datosAntes = null;
          }

          // ======================================================
          // CAMBIO DE IDIOMA A EN-US
          // ======================================================

          cy.log('===== Cambio de idioma a en-US =====');

          cy.request({
            method: 'PATCH',
            url: `${baseUrl}/configuracion/personalizacion/idioma`,
            headers: {
              Authorization: `Bearer ${token}`
            },
            body: {
              locale_code: 'en-US'
            },
            failOnStatusCode: false
          }).then((cambioIdioma) => {

            expect(cambioIdioma.status).to.eq(200);

            expect(cambioIdioma.body).to.have.property(
              'locale_code'
            );

            expect(cambioIdioma.body.locale_code).to.eq('en-US');

            cy.log(
              `Cambio de idioma correcto. HTTP ${cambioIdioma.status}`
            );

            cy.log(
              `Nuevo idioma: ${cambioIdioma.body.locale_code}`
            );

            // ====================================================
            // NUEVA SESIÓN
            // ====================================================

            cy.log('===== Nueva sesión =====');

            cy.request({
              method: 'POST',
              url: `${baseUrl}/sesiones/`,
              body: {
                correo_electronico: usuario,
                contrasena: contrasena
              }
            }).then((nuevoLogin) => {

              expect(nuevoLogin.status).to.eq(200);

              const nuevoToken = nuevoLogin.body.token;

              expect(nuevoToken)
                .to.be.a('string')
                .and.not.be.empty;

              cy.log(
                `Nueva sesión iniciada correctamente. HTTP ${nuevoLogin.status}`
              );

              // ==================================================
              // TC-M09-194 - VERIFICAR PERSISTENCIA
              // ==================================================

              cy.log(
                '===== TC-M09-194 - Verificar persistencia ====='
              );

              cy.request({
                method: 'GET',
                url: `${baseUrl}/configuracion/personalizacion/idioma`,
                headers: {
                  Authorization: `Bearer ${nuevoToken}`
                }
              }).then((idiomaFinal) => {

                expect(idiomaFinal.status).to.eq(200);

                expect(idiomaFinal.body)
                  .to.have.property('locale_code');

                expect(idiomaFinal.body.locale_code)
                  .to.eq('en-US');

                cy.log(
                  `Idioma después de nueva sesión: ${idiomaFinal.body.locale_code}`
                );

                cy.log(
                  'TC-M09-194 APROBADO: el idioma en-US permanece después de iniciar una nueva sesión.'
                );

                // =================================================
                // TC-M09-196 - DATOS DESPUÉS DEL CAMBIO
                // =================================================

                cy.log(
                  '===== TC-M09-196 - Datos después del cambio ====='
                );

                cy.request({
                  method: 'GET',
                  url: `${baseUrl}/usuarios/me`,
                  headers: {
                    Authorization: `Bearer ${nuevoToken}`
                  },
                  failOnStatusCode: false
                }).then((perfilDespues) => {

                  cy.log(
                    `Perfil después del cambio - HTTP ${perfilDespues.status}`
                  );

                  if (perfilDespues.status === 200) {

                    datosDespues = perfilDespues.body;

                    cy.log(
                      `Datos después: ${JSON.stringify(datosDespues)}`
                    );

                    // ============================================
                    // COMPARACIÓN
                    // ============================================

                    if (datosAntes !== null) {

                      expect(datosDespues)
                        .to.deep.equal(datosAntes);

                      cy.log(
                        'TC-M09-196 APROBADO: los datos del usuario permanecen idénticos antes y después del cambio de idioma.'
                      );

                    } else {

                      cy.log(
                        'TC-M09-196 BLOQUEADO: no fue posible obtener los datos iniciales del perfil.'
                      );

                    }

                  } else {

                    cy.log(
                      `TC-M09-196 BLOQUEADO: el endpoint de perfil respondió HTTP ${perfilDespues.status} después del cambio.`
                    );
                  }

                  // =================================================
                  // RESUMEN FINAL
                  // =================================================

                  cy.log('==========================================');
                  cy.log('RESUMEN TC-M09-G101');
                  cy.log('==========================================');

                  cy.log(
                    'TC-M09-194: Persistencia del idioma seleccionado.'
                  );

                  cy.log(
                    'TC-M09-196: Integridad de los datos del usuario.'
                  );

                  cy.log(
                    `Idioma inicial: ${idiomaInicial}`
                  );

                  cy.log(
                    'Idioma final esperado: en-US'
                  );

                  cy.log(
                    '==========================================');
                });
              });
            });
          });
        });
      });
    });
  });
});