describe('TC-M02-G20 - RF-35 Gestion Individual de Activos Biologicos (TC-M02-033 / TC-M02-034)', () => {

  const baseUrl =
    'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';

  let tokenAdmin;
  let idActivo;

  const idEspecie = 4;
  const idInfraestructura = 6;
  const identificadorActivo = `QA-G20-CY-${Date.now()}`;

  const razaOriginal = 'Cachama QA-G20-CY original';
  const sexoOriginal = 'Macho';
  const fechaNacimientoOriginal = '2025-01-15T00:00:00Z';
  const pesoInicialOriginal = '2.500';

  const razaNueva = 'Cachama QA-G20-CY actualizada';
  const sexoNuevo = 'Hembra';
  const fechaNacimientoNueva = '2025-02-20T00:00:00Z';
  const pesoInicialNuevo = '3.750';


  // ============================================================
  // PRECONDICIONES: login admin + activo INDIVIDUAL propio de la prueba
  // ============================================================
  before(() => {

    cy.request({
      method: 'POST',
      url: `${baseUrl}/sesiones/`,
      body: {
        correo_electronico: 'admin.test@sgpmp.com.co',
        contrasena: 'Administrador123#'
      }
    }).then((response) => {

      expect(response.status).to.equal(200);

      tokenAdmin = response.body.token;

      expect(tokenAdmin).to.exist;
      expect(tokenAdmin).to.be.a('string');

      cy.log('Administrador autenticado correctamente en TEST');

    }).then(() => {

      const hoy = new Date().toISOString().slice(0, 10);

      return cy.request({
        method: 'POST',
        url: `${baseUrl}/activos-biologicos`,
        headers: { Authorization: `Bearer ${tokenAdmin}` },
        body: {
          tipo_activo: 'INDIVIDUAL',
          id_especie: idEspecie,
          fecha_inicio_ciclo: hoy,
          origen_financiero: 'nacimiento',
          id_infraestructura: idInfraestructura,
          identificador: identificadorActivo,
          raza: razaOriginal,
          sexo: sexoOriginal,
          fecha_nacimiento: fechaNacimientoOriginal,
          peso_inicial: pesoInicialOriginal
        }
      });

    }).then((response) => {

      cy.log(`Respuesta creacion activo de prueba: ${JSON.stringify(response.body)}`);

      expect(response.status).to.equal(201);

      idActivo = response.body.id_activo_biologico;

      expect(idActivo).to.be.a('number');
      expect(response.body.tipo).to.equal('INDIVIDUAL');
      expect(response.body.detalle_individual.raza).to.equal(razaOriginal);

      cy.log(`Activo INDIVIDUAL de prueba creado con id ${idActivo}`);

    });

  });


  // ============================================================
  // TC-M02-033 (1/2) - Consultar activo individual existente
  // ============================================================
  it('TC-M02-033: Debe consultar el activo individual existente y mostrar su informacion actual', () => {

    cy.request({
      method: 'GET',
      url: `${baseUrl}/activos-biologicos/${idActivo}`,
      headers: { Authorization: `Bearer ${tokenAdmin}` }
    }).then((response) => {

      expect(response.status).to.equal(200);

      expect(response.body.id_activo_biologico).to.equal(idActivo);
      expect(response.body.tipo).to.equal('INDIVIDUAL');
      expect(response.body.id_especie).to.equal(idEspecie);

      expect(response.body.detalle_individual).to.exist;
      expect(response.body.detalle_individual.raza).to.equal(razaOriginal);
      expect(response.body.detalle_individual.sexo).to.equal(sexoOriginal);
      expect(String(response.body.detalle_individual.peso_inicial)).to.equal(pesoInicialOriginal);

      cy.log(`Ficha del activo ${idActivo} consultada correctamente`);

    });

  });


  // ============================================================
  // TC-M02-033 (2/2) - El historial del activo esta disponible
  // ============================================================
  it('TC-M02-033: El historial del activo debe estar disponible para consulta', () => {

    cy.request({
      method: 'GET',
      url: `${baseUrl}/activos-biologicos/${idActivo}/historial`,
      headers: { Authorization: `Bearer ${tokenAdmin}` }
    }).then((response) => {

      expect(response.status).to.equal(200);

      expect(response.body).to.have.property('registros');
      expect(response.body.registros).to.be.an('array');

      cy.log(`Historial disponible: ${response.body.total_registros} registro(s)`);

    });

  });


  // ============================================================
  // TC-M02-034 (1/3) - Actualizar atributos permitidos
  // ============================================================
  it('TC-M02-034: Debe actualizar raza, sexo, fecha_nacimiento y peso_inicial', () => {

    cy.request({
      method: 'PATCH',
      url: `${baseUrl}/activos-biologicos/${idActivo}`,
      headers: { Authorization: `Bearer ${tokenAdmin}` },
      body: {
        raza: razaNueva,
        sexo: sexoNuevo,
        fecha_nacimiento: fechaNacimientoNueva,
        peso_inicial: pesoInicialNuevo,
        // Campos que el RF NO permite editar por este endpoint. El DTO ni
        // siquiera los declara, por lo que deben quedar ignorados.
        tipo: 'POBLACIONAL',
        id_especie: 999,
        estado_activo: 'BAJA'
      }
    }).then((response) => {

      cy.log(`Respuesta PATCH: ${JSON.stringify(response.body)}`);

      expect(response.status).to.equal(200);

      expect(response.body.detalle_individual.raza).to.equal(razaNueva);
      expect(response.body.detalle_individual.sexo).to.equal(sexoNuevo);
      expect(String(response.body.detalle_individual.peso_inicial)).to.equal(pesoInicialNuevo);

      // Campos no editables: deben permanecer intactos
      expect(response.body.tipo).to.equal('INDIVIDUAL');
      expect(response.body.id_especie).to.equal(idEspecie);
      expect(response.body.nombre_estado).to.equal('ACTIVO');

    });

  });


  // ============================================================
  // TC-M02-034 (2/3) - Verificar persistencia real tras recargar
  // ============================================================
  it('TC-M02-034: Los cambios deben persistir al recargar la ficha del activo', () => {

    cy.request({
      method: 'GET',
      url: `${baseUrl}/activos-biologicos/${idActivo}`,
      headers: { Authorization: `Bearer ${tokenAdmin}` }
    }).then((response) => {

      expect(response.status).to.equal(200);

      expect(response.body.detalle_individual.raza).to.equal(razaNueva);
      expect(response.body.detalle_individual.sexo).to.equal(sexoNuevo);
      expect(String(response.body.detalle_individual.peso_inicial)).to.equal(pesoInicialNuevo);
      expect(response.body.detalle_individual.fecha_nacimiento.slice(0, 10))
        .to.equal(fechaNacimientoNueva.slice(0, 10));

      expect(response.body.tipo).to.equal('INDIVIDUAL');
      expect(response.body.id_especie).to.equal(idEspecie);

    });

  });


  // ============================================================
  // TC-M02-034 (3/3) - Verificar registro en la bitacora de auditoria (RF-52)
  // ============================================================
  it('TC-M02-034: La actualizacion debe quedar registrada en la bitacora de auditoria', () => {

    cy.request({
      method: 'GET',
      url: `${baseUrl}/activos-biologicos/auditoria`,
      headers: { Authorization: `Bearer ${tokenAdmin}` },
      qs: {
        rf_origen: 'RF35',
        id_activo_biologico: idActivo
      }
    }).then((response) => {

      expect(response.status).to.equal(200);

      const encontrado = (response.body.registros || []).some(
        (r) => r.tipo_evento === 'ACTIVO_INDIVIDUAL_ACTUALIZADO'
          && r.id_activo_biologico === idActivo
      );

      expect(encontrado).to.equal(true);

      cy.log(`Bitacora RF-52 confirma la actualizacion del activo ${idActivo}`);

    });

  });

});
