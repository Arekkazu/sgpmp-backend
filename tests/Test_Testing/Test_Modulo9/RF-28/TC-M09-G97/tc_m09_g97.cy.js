describe('TC-M09-G97 - Restauración y persistencia del dashboard', () => {

  const baseUrl =
    'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

  const usuario = 'admin@pecuaria.co';
  const contrasena = 'Test1234!';

  it('TC-M09-186 y TC-M09-188 - Restaurar y verificar persistencia del dashboard', () => {

    // ============================================================
    // LOGIN
    // ============================================================
    cy.request({
      method: 'POST',
      url: `${baseUrl}/sesiones/`,
      body: {
        correo_electronico: usuario,
        contrasena: contrasena
      }
    }).then((login) => {

      expect(login.status).to.eq(200);

      const token = login.body.token;

      cy.log('Login exitoso');

      // ============================================================
      // TC-M09-186 - RESTAURAR DASHBOARD
      // ============================================================
      cy.request({
        method: 'POST',
        url: `${baseUrl}/configuracion/personalizacion/dashboard/restaurar`,
        headers: {
          Authorization: `Bearer ${token}`
        },
        failOnStatusCode: false
      }).then((restaurar) => {

        cy.log(`TC-M09-186 - Status restaurar: ${restaurar.status}`);
        cy.log(
          `TC-M09-186 - Respuesta: ${JSON.stringify(restaurar.body)}`
        );

        // Evidencia del comportamiento real
        cy.writeFile(
          'tests/Test_Testing/Test_Modulo9/RF-28/TC-M09-G97/Resultados/G97-restaurar.txt',
          `TC-M09-186 - Restaurar dashboard\n\n` +
          `HTTP Status: ${restaurar.status}\n` +
          `Respuesta:\n${JSON.stringify(restaurar.body, null, 2)}\n`
        );

        if (restaurar.status === 200) {

          expect(restaurar.body).to.have.property('grid');
          expect(restaurar.body).to.have.property('active_widget');

          cy.log('Restauración realizada correctamente');

        } else {

          cy.log(
            `BLOQUEADO: el endpoint de restauración respondió ${restaurar.status}`
          );

          expect(restaurar.status).to.eq(200);

        }

        // ============================================================
        // TC-M09-188 - PERSISTENCIA
        // ============================================================
        cy.request({
          method: 'GET',
          url: `${baseUrl}/configuracion/personalizacion/dashboard`,
          headers: {
            Authorization: `Bearer ${token}`
          },
          failOnStatusCode: false
        }).then((dashboard) => {

          cy.log(`TC-M09-188 - Status dashboard: ${dashboard.status}`);
          cy.log(
            `TC-M09-188 - Respuesta: ${JSON.stringify(dashboard.body)}`
          );

          cy.writeFile(
            'tests/Test_Testing/Test_Modulo9/RF-28/TC-M09-G97/Resultados/G97-persistencia.txt',
            `TC-M09-188 - Persistencia del dashboard\n\n` +
            `HTTP Status: ${dashboard.status}\n` +
            `Respuesta:\n${JSON.stringify(dashboard.body, null, 2)}\n`
          );

          if (dashboard.status === 200) {

            expect(dashboard.body).to.have.property('grid');
            expect(dashboard.body).to.have.property('active_widget');

            cy.log('Dashboard consultado correctamente');

          } else {

            cy.log(
              `BLOQUEADO: el endpoint del dashboard respondió ${dashboard.status}`
            );

            expect(dashboard.status).to.eq(200);
          }

        });

      });

    });

  });

});