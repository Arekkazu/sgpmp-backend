describe('TC-M01-105 - Gestión de cuenta de usuario', () => {

  const baseUrl =
    'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

  let tokenAdmin;
  let tokenUsuarioPrueba;
  let idUsuarioPrueba;
  let estadoOriginal;


  // ============================================================
  // FUNCIÓN PARA DECODIFICAR EL PAYLOAD DE UN JWT
  // ============================================================
  const decodificarJWT = (token) => {

    const base64Url = token.split('.')[1];

    const base64 = base64Url
      .replace(/-/g, '+')
      .replace(/_/g, '/');

    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => {
          return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        })
        .join('')
    );

    return JSON.parse(jsonPayload);
  };


  // ============================================================
  // PRECONDICIONES
  // ============================================================
  before(() => {

    // ----------------------------------------------------------
    // LOGIN COMO ADMINISTRADOR
    // ----------------------------------------------------------
    cy.request({
      method: 'POST',
      url: `${baseUrl}/sesiones/`,
      body: {
        correo_electronico: 'admin@pecuaria.co',
        contrasena: 'Test1234!'
      }
    }).then((response) => {

      expect(response.status).to.equal(200);

      tokenAdmin = response.body.token;

      expect(tokenAdmin).to.exist;
      expect(tokenAdmin).to.be.a('string');

      cy.log('Administrador autenticado correctamente');

    });


    // ----------------------------------------------------------
    // LOGIN COMO USUARIO DE PRUEBA
    // Se utiliza un correo con dominio válido para EmailStr
    // ----------------------------------------------------------
    cy.request({
      method: 'POST',
      url: `${baseUrl}/sesiones/`,
      body: {
        correo_electronico: 'juan.carlos@email.com',
        contrasena: 'Test1234!'
      },
      failOnStatusCode: false
    }).then((response) => {

      // Mostrar respuesta para facilitar depuración
      cy.log(
        `Respuesta login usuario de prueba: ${JSON.stringify(response.body)}`
      );

      expect(response.status).to.equal(200);

      tokenUsuarioPrueba = response.body.token;

      expect(tokenUsuarioPrueba).to.exist;
      expect(tokenUsuarioPrueba).to.be.a('string');

      // Decodificar JWT para obtener el ID del usuario
      const payload = decodificarJWT(tokenUsuarioPrueba);

      expect(payload).to.have.property('sub');

      idUsuarioPrueba = Number(payload.sub);

      expect(idUsuarioPrueba).to.be.a('number');
      expect(idUsuarioPrueba).to.be.greaterThan(0);

      cy.log(`ID del usuario de prueba: ${idUsuarioPrueba}`);

    });

  });


  // ============================================================
  // CASO DE PRUEBA 1
  // INICIO DE SESIÓN DEL ADMINISTRADOR
  // ============================================================
  it('Debe iniciar sesión correctamente como administrador', () => {

    expect(tokenAdmin).to.exist;
    expect(tokenAdmin).to.be.a('string');

  });


  // ============================================================
  // CASO DE PRUEBA 2
  // LISTAR USUARIOS DISPONIBLES
  // ============================================================
  it('Debe listar los usuarios disponibles para administración', () => {

    cy.request({
      method: 'GET',
      url: `${baseUrl}/usuarios/admin`,
      headers: {
        Authorization: `Bearer ${tokenAdmin}`
      },
      qs: {
        pagina: 1,
        tamano: 50
      }
    }).then((response) => {

      expect(response.status).to.equal(200);

      expect(response.body).to.have.property('items');

      expect(response.body.items).to.be.an('array');

      expect(response.body.items.length).to.be.greaterThan(0);

      cy.log(
        `Total de usuarios encontrados: ${response.body.items.length}`
      );

    });

  });


  // ============================================================
  // CASO DE PRUEBA 3
  // IDENTIFICAR USUARIO DE PRUEBA
  // ============================================================
  it('Debe identificar correctamente el usuario para realizar la gestión de cuenta', () => {

    expect(idUsuarioPrueba).to.exist;

    expect(idUsuarioPrueba).to.be.a('number');

    expect(idUsuarioPrueba).to.be.greaterThan(0);

    cy.log(
      `Usuario de prueba identificado con ID: ${idUsuarioPrueba}`
    );

  });


  // ============================================================
  // CASO DE PRUEBA 4
  // CONSULTAR DETALLE DEL USUARIO
  // ============================================================
  it('Debe consultar correctamente el detalle del usuario seleccionado', () => {

    cy.request({
      method: 'GET',
      url: `${baseUrl}/usuarios/${idUsuarioPrueba}/detalle`,
      headers: {
        Authorization: `Bearer ${tokenAdmin}`
      }
    }).then((response) => {

      expect(response.status).to.equal(200);

      expect(response.body).to.have.property('id_usuario');

      expect(response.body).to.have.property('correo_electronico');

      expect(response.body).to.have.property('estado_cuenta');

      expect(response.body.id_usuario).to.equal(idUsuarioPrueba);

      expect(response.body.correo_electronico).to.equal(
        'juan.carlos@email.com'
      );

      // Guardar estado original para fines de restauración
      estadoOriginal = response.body.estado_cuenta;

      cy.log(
        `Usuario encontrado: ${response.body.correo_electronico}`
      );

      cy.log(
        `Estado original: ${estadoOriginal}`
      );

    });

  });


  // ============================================================
  // CASO DE PRUEBA 5
  // BLOQUEAR CUENTA
  // ============================================================
  it('Debe bloquear correctamente la cuenta del usuario', () => {

    cy.request({
      method: 'POST',
      url: `${baseUrl}/usuarios/${idUsuarioPrueba}/gestionar`,
      headers: {
        Authorization: `Bearer ${tokenAdmin}`
      },
      body: {
        accion_cuenta: 'bloquear'
      },
      failOnStatusCode: false
    }).then((response) => {

      cy.log(
        `Respuesta bloqueo: ${JSON.stringify(response.body)}`
      );

      expect(response.status).to.equal(200);

    });

  });


  // ============================================================
  // CASO DE PRUEBA 6
  // VERIFICAR QUE LA CUENTA FUE BLOQUEADA
  // ============================================================
  it('Debe reflejar el cambio de estado después de bloquear la cuenta', () => {

    cy.request({
      method: 'GET',
      url: `${baseUrl}/usuarios/${idUsuarioPrueba}/detalle`,
      headers: {
        Authorization: `Bearer ${tokenAdmin}`
      }
    }).then((response) => {

      expect(response.status).to.equal(200);

      expect(response.body).to.have.property('estado_cuenta');

      const estadoActual =
        response.body.estado_cuenta.toLowerCase();

      cy.log(
        `Estado después del bloqueo: ${response.body.estado_cuenta}`
      );

      expect(estadoActual).to.include('bloque');

    });

  });


  // ============================================================
  // CASO DE PRUEBA 7
  // RESTAURAR LA CUENTA
  // ============================================================
  it('Debe restaurar la cuenta después de la prueba', () => {

    cy.request({
      method: 'POST',
      url: `${baseUrl}/usuarios/${idUsuarioPrueba}/gestionar`,
      headers: {
        Authorization: `Bearer ${tokenAdmin}`
      },
      body: {
        accion_cuenta: 'activar'
      },
      failOnStatusCode: false
    }).then((response) => {

      cy.log(
        `Respuesta restauración: ${JSON.stringify(response.body)}`
      );

      expect(response.status).to.equal(200);

    });

  });


  // ============================================================
  // CASO DE PRUEBA 8
  // VERIFICAR QUE LA CUENTA QUEDÓ ACTIVA
  // ============================================================
  it('Debe verificar que la cuenta quedó activa después de la restauración', () => {

    cy.request({
      method: 'GET',
      url: `${baseUrl}/usuarios/${idUsuarioPrueba}/detalle`,
      headers: {
        Authorization: `Bearer ${tokenAdmin}`
      }
    }).then((response) => {

      expect(response.status).to.equal(200);

      expect(response.body).to.have.property('estado_cuenta');

      const estadoFinal =
        response.body.estado_cuenta.toLowerCase();

      cy.log(
        `Estado final de la cuenta: ${response.body.estado_cuenta}`
      );

      expect(estadoFinal).to.include('activo');

    });

  });

});