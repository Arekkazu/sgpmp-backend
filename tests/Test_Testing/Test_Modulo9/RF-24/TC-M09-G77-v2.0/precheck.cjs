// Precondiciones de TC-M09-G77-v2.0: SOLO autenticación y GET. Ninguna escritura.
//
// Comprueba contrato, fixture, cuentas de los actores negativos y su estado original, y deja
// constancia de si alguno necesitaría activación temporal. No ejecuta POST de calibración ni
// de gestión de cuentas: eso corresponde a run-newman.cjs.
//
// Uso:
//   $env:G77_RUN_ID="run-YYYYMMDD-HHMMSS"   (opcional: si falta, no escribe evidencia)
//   node .\precheck.cjs

const H = require('./helpers.cjs'); // Incluye la guarda de directorio autorizado.

const runId = process.env.G77_RUN_ID || null;
const log = (...a) => console.log(...a);

(async () => {
  const resultado = { grupo: H.GROUP_ID, caso: H.CASO, fecha: new Date().toISOString(), soloLectura: true };

  // Contrato
  const openapi = await (await fetch(H.base() + '/openapi.json', { signal: AbortSignal.timeout(30000) })).json();
  const requeridos = [
    ['post', '/usuarios/{id_usuario}/gestionar'],
    ['post', '/configuracion/sensores/{id_sensor}/calibrar'],
    ['get', '/configuracion/sensores/{id_sensor}/calibraciones'],
    ['get', '/usuarios/admin'],
    ['get', '/usuarios/{id_usuario}/detalle']
  ];
  resultado.contrato = {};
  for (const [m, p] of requeridos) {
    const op = openapi.paths?.[p]?.[m] || null;
    resultado.contrato[`${m.toUpperCase()} ${p}`] = {
      presente: Boolean(op), codigosDeclarados: op ? Object.keys(op.responses || {}) : []
    };
  }
  resultado.contrato.declara403EnCalibrar =
    (resultado.contrato['POST /configuracion/sensores/{id_sensor}/calibrar'].codigosDeclarados || []).includes('403');
  resultado.contrato.modo_calibracion_declarado = JSON.stringify(openapi).includes('modo_calibracion');
  resultado.contrato.nota =
    'modo_calibracion=SENSOR se envía como exige el caso aunque el schema no lo declare. G77 no prueba sus valores válidos/invalidos.';

  // Actor de discovery y Administrador
  const tokenIng = await H.loginOk(process.env.TEST_ENGINEER_EMAIL, process.env.TEST_ENGINEER_PASSWORD, 'Ingeniero');
  let tokenAdmin = null, adminUsado = null;
  const intentosAdmin = [];
  for (const email of [process.env.TEST_ADMIN_PRIMARY, process.env.TEST_ADMIN_SECONDARY].filter(Boolean)) {
    const r = await H.login(email, process.env.TEST_ADMIN_PASSWORD);
    if (r.status === 200 && r.token) { tokenAdmin = r.token; adminUsado = email; intentosAdmin.push({ email, resultado: 'autentica' }); break; }
    intentosAdmin.push({ email, resultado: `no autentica (HTTP ${r.status}${r.errorCode ? ' ' + r.errorCode : ''})` });
  }
  resultado.administrador = { intentos: intentosAdmin, usado: adminUsado };
  if (!tokenAdmin) throw new Error('BLOQUEADO: ningún Administrador autenticó; sin él no se pueden localizar las cuentas de los actores.');

  // Fixture
  const usoAdmin = [];
  const { fixture, origen } = await H.construirFixture(tokenIng, tokenAdmin, usoAdmin);
  resultado.fixture = { origen, ...fixture };
  resultado.getsConAdministrador = usoAdmin;

  // Cuentas de los actores negativos y su estado original
  resultado.actores = {};
  for (const a of H.ACTORES) {
    const correo = process.env[a.envEmail];
    const cuenta = await H.localizarCuenta(correo, tokenAdmin);
    const plan = H.planDeEstado(cuenta.estado_cuenta);
    const rolCoincide = cuenta.nombre_rol === a.rolEsperado;
    // El login solo se intenta si la cuenta ya está Activa: no se activa nada aquí.
    let login = null;
    if (cuenta.estado_cuenta === 'Activo') {
      const r = await H.login(correo, process.env[a.envPass]);
      login = { status: r.status, autenticado: r.status === 200 && Boolean(r.token), error_code: r.errorCode };
      if (login.autenticado) {
        const me = await H.getOk('/usuarios/me', r.token);
        const permisos = await H.getOk('/sesiones/me/permisos', r.token);
        const acciones = (permisos.permisos || []).filter(p => p.id_recurso === H.RECURSO_CALIBRACIONES).map(p => p.id_accion).sort();
        login.perfil = { id_usuario: me.id_usuario, nombre_rol: me.nombre_rol, estado_cuenta: me.estado_cuenta };
        login.accionesSobreCalibraciones = acciones;
        // Un permiso de creación inesperado es riesgo a observar, no motivo de bloqueo.
        login.permisoDeCreacionInesperado = acciones.includes(1);
      }
    }
    resultado.actores[a.key] = {
      correo, rolEsperado: a.rolEsperado, cuenta, rolCoincide,
      planDeEstado: plan, login,
      ejecutable: rolCoincide && (cuenta.estado_cuenta === 'Activo' || plan.permitido),
      motivoSiNoEjecutable: !rolCoincide
        ? `la cuenta tiene rol ${cuenta.nombre_rol} y el subescenario exige ${a.rolEsperado}; no se cambian roles para preparar la prueba`
        : (!plan.permitido ? plan.motivo : null)
    };
  }

  resultado.credenciales = '[REDACTED]';
  if (runId) H.save(runId, 'precheck.json', resultado);

  log(`contrato: calibrar declara 403 = ${resultado.contrato.declara403EnCalibrar}`);
  log(`fixture: ${origen} | valor ${fixture.valor} en rango ${fixture.rango.min}–${fixture.rango.max}`);
  for (const [k, v] of Object.entries(resultado.actores)) {
    log(`${k}: id ${v.cuenta.id_usuario} | rol ${v.cuenta.nombre_rol} (esperado ${v.rolEsperado}) | estado ${v.cuenta.estado_cuenta} | activacion temporal necesaria: ${v.planDeEstado.requiereActivacion ? 'SI' : 'NO'} | ejecutable: ${v.ejecutable}`);
    if (v.login && v.login.accionesSobreCalibraciones) {
      log(`   acciones sobre el recurso 12: ${JSON.stringify(v.login.accionesSobreCalibraciones)}${v.login.permisoDeCreacionInesperado ? '  AVISO: incluye creacion' : ''}`);
    }
  }
  if (runId) log(`precheck.json escrito en RESULTADOS/${runId}/`);
})().catch((e) => { console.error('PRECHECK NO COMPLETADO:', e.message); process.exitCode = 1; });
